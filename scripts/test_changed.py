#!/usr/bin/env python3
"""
Szybki lokalny runner testów dla ai-instruction-kit-mcp (#419).

Wybiera moduły testów powiązane ze zmienionymi plikami (git diff względem bazy +
niezacommitowane i nietrackowane zmiany), pilnuje ciszy w logu (watchdog)
i uruchamia każdy moduł w osobnym procesie.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

# Korzeń repozytorium
ROOT = Path(__file__).resolve().parents[1]

# Dołączamy tests/ do sys.path, aby korzystać z _shell.py
sys.path.insert(0, str(ROOT / "tests"))
try:
    from _shell import posix_path, resolve_bash
except ImportError:
    def posix_path(path: Path) -> str:
        return str(path).replace("\\", "/")

    def resolve_bash() -> str | None:
        return shutil.which("bash")

# Szybki rdzeń: zawsze uruchamiany przy każdym przebiegu
FAST_CORE: tuple[str, ...] = (
    "test_resolver",
    "test_manifest_mappings",
    "test_mcp_compat",
)

# Ścieżki całkowicie ignorowane — sam szybki rdzeń
IGNORED_PATHS: set[str] = {
    "LICENSE",
}

# Jawny słownik wyjątków dla mapowania (decyzja 3)
EXCEPTIONS: dict[str, list[str]] = {
    "agent_classes": ["test_agent_classification"],
    "manifest": ["test_manifest_mappings"],
    "server": ["test_server_instructions", "test_mcp_compat"],
    "server_guard": ["test_guards"],
    "__main__": ["test_server_instructions"],
    "__init__": ["test_mcp_compat"],
    # Skrypty pomocnicze
    "project_brief": ["test_resolver", "test_doctor", "test_server_instructions"],
    "install_agent_skills": ["test_bootstrap_clients.sh", "test_generated_artifacts"],
    "render_agent_commands": ["test_bootstrap_clients.sh", "test_generated_artifacts"],
    "render_server_guard": ["test_guards", "test_lf_writes"],
    "render_worktree": ["test_worktree"],
    "render_brief_rules": ["test_brief_rules"],
    "render_integrations": ["test_integrations"],
    "antigravity_hooks": ["test_antigravity_hooks"],
    "test_changed": ["test_test_changed"],
}

# Zbiór aktywnych procesów potomnych
ACTIVE_PROCS: set[subprocess.Popen] = set()


def kill_active_processes() -> None:
    """Zabij wszystkie aktywne procesy potomne runnera."""
    for proc in list(ACTIVE_PROCS):
        try:
            if os.name != "nt":
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGKILL)
            else:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except OSError:
            pass


def get_base_branch(root: Path = ROOT) -> str:
    """Odczytaj gałąź bazową z .ai/project.md lub domyślną dev/main."""
    project_md = root / ".ai" / "project.md"
    if project_md.is_file():
        match = re.search(r"^base:\s*([^\s]+)", project_md.read_text(encoding="utf-8"), re.MULTILINE)
        if match:
            return match.group(1).strip()
    return "dev"


def get_merge_base_and_changes(base_branch: str | None = None, root: Path = ROOT) -> list[str]:
    """
    Wybierz zmienione pliki: diff względem merge-base z origin/<base> (lub <base>),
    plus zmiany w indeksie, w drzewie roboczym i pliki nietrackowane.
    """
    if base_branch is None:
        base_branch = get_base_branch(root)

    # Ustal ref bazy: preferuj origin/<base>, potem lokalny <base>
    target_ref = f"origin/{base_branch}"
    res = subprocess.run(["git", "rev-parse", "--verify", target_ref], cwd=str(root), capture_output=True, text=True)
    if res.returncode != 0:
        target_ref = base_branch
        res = subprocess.run(["git", "rev-parse", "--verify", target_ref], cwd=str(root), capture_output=True, text=True)
        if res.returncode != 0:
            target_ref = "HEAD"

    mb_res = subprocess.run(["git", "merge-base", "HEAD", target_ref], cwd=str(root), capture_output=True, text=True)
    merge_base = mb_res.stdout.strip() if mb_res.returncode == 0 else ""

    changed: set[str] = set()

    def run_git(args: list[str]) -> list[str]:
        cmd = ["git", "-c", "core.quotepath=false", *args]
        r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
        if r.returncode == 0:
            return [line.strip().replace("\\", "/") for line in r.stdout.splitlines() if line.strip()]
        return []

    if merge_base:
        changed.update(run_git(["diff", "--name-only", merge_base, "HEAD"]))
    elif target_ref != "HEAD":
        # Fallback dla shallow clone lub odłączonej historii
        branch_diff = run_git(["diff", "--name-only", f"{target_ref}...HEAD"])
        if branch_diff:
            changed.update(branch_diff)
        else:
            changed.update(run_git(["diff", "--name-only", "HEAD"]))
    else:
        changed.update(run_git(["diff", "--name-only", "HEAD"]))

    changed.update(run_git(["diff", "--cached", "--name-only"]))
    changed.update(run_git(["diff", "--name-only"]))
    changed.update(run_git(["ls-files", "--others", "--exclude-standard"]))

    return sorted(changed)


def _get_test_contents(root: Path) -> dict[str, str]:
    """Wczytaj treść testów z tests/ do szybkiego fallback grepa."""
    tests_dir = root / "tests"
    test_files = list(tests_dir.glob("test_*.py")) + list(tests_dir.glob("test_*.sh"))
    contents: dict[str, str] = {}
    for p in test_files:
        try:
            contents[p.name] = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            pass
    return contents


def normalize_repo_path(path_str: str, root: Path = ROOT) -> str:
    """Znormalizuj ścieżkę do formatu względnego wobec root z separatorami '/'."""
    raw = path_str.replace("\\", "/").strip()
    if not raw:
        return ""
    p = Path(raw)
    if p.is_absolute():
        try:
            return str(p.resolve().relative_to(root.resolve())).replace("\\", "/")
        except ValueError:
            return str(p).replace("\\", "/")
    # Usuń wiodące ./
    return re.sub(r"^\./+", "", raw)


def resolve_modules_for_file(
    file_path: str,
    root: Path = ROOT,
    test_contents: dict[str, str] | None = None,
) -> tuple[list[str], str]:
    """
    Znajdź moduły testowe dla pojedynczego pliku:
    0. Plik sam jest testem w tests/ (tests/test_X.py -> test_X)
    1. Ścieżki ignorowane (LICENSE) -> []
    2. Słownik wyjątków (EXCEPTIONS)
    3. Konwencja: src/guides/X.py lub scripts/X.py -> test_X
    4. Fallback grep: wyszukiwanie pełnej ścieżki lub nazwy pliku w tests/*.py i tests/*.sh
    """
    norm_path = normalize_repo_path(file_path, root=root)
    if not norm_path:
        return [], "pusta ścieżka pominięta"

    p = Path(norm_path)

    # 0. Sam plik testowy
    if norm_path.startswith("tests/"):
        if not (root / norm_path).is_file():
            return [], f"{norm_path} usunięty/brakujący plik testu (pominięto)"
        if norm_path.endswith(".py") and p.name != "_shell.py":
            return [p.stem], f"{norm_path} → {p.stem} (sam moduł testu)"
        if norm_path.endswith(".sh"):
            return [p.name], f"{norm_path} → {p.name} (sama suita powłoki)"

    if norm_path in IGNORED_PATHS or p.name in IGNORED_PATHS:
        return [], f"{norm_path} ignorowany (sam szybki rdzeń)"

    stem = p.stem

    # 1. Wyjątki
    if stem in EXCEPTIONS:
        mods = EXCEPTIONS[stem]
        return mods, f"{norm_path} → {', '.join(mods)} (wyjątek)"

    # 2. Konwencja
    candidate = f"test_{stem}"
    tests_dir = root / "tests"
    if (tests_dir / f"{candidate}.py").is_file():
        return [candidate], f"{norm_path} → {candidate} (konwencja)"
    if (tests_dir / f"{candidate}.sh").is_file():
        return [f"{candidate}.sh"], f"{norm_path} → {candidate}.sh (konwencja)"

    # 3. Fallback grep
    if test_contents is None:
        test_contents = _get_test_contents(root)

    matches: list[str] = []
    file_name = p.name
    for t_name, content in test_contents.items():
        if norm_path in content or file_name in content:
            mod_name = Path(t_name).stem if t_name.endswith(".py") else t_name
            # Unikaj dodawania test_shell_suites jeśli suity .sh są odpalane bezpośrednio
            if mod_name != "test_shell_suites":
                matches.append(mod_name)

    matches = sorted(set(matches))
    if matches:
        return matches, f"{norm_path} → {', '.join(matches)} (fallback grep)"

    return [], f"ostrzeżenie: brak powiązanych testów dla {norm_path}"


def resolve_test_targets(
    files: list[str], root: Path = ROOT
) -> tuple[list[str], bool, list[str]]:
    """
    Zwraca: (lista_unikalnych_modułów, czy_uruchomić_wszystko, lista_powodów).
    Zawsze dołącza FAST_CORE.
    Gdy którykolwiek plik nie ma trafień -> ostrzeżenie i is_all = True.
    """
    selected: set[str] = set(FAST_CORE)
    reasons: list[str] = [f"szybki rdzeń: {', '.join(FAST_CORE)}"]
    is_all = False
    test_contents = _get_test_contents(root)

    for f in files:
        norm = normalize_repo_path(f, root=root)
        if not norm:
            continue

        mods, reason = resolve_modules_for_file(norm, root=root, test_contents=test_contents)
        reasons.append(reason)
        if mods:
            selected.update(mods)
        else:
            # Ignorowane lub usunięte pliki testów nie wyzwalają pełnej suity
            if norm in IGNORED_PATHS or Path(norm).name in IGNORED_PATHS:
                continue
            if norm.startswith("tests/") and not (root / norm).is_file():
                continue
            is_all = True

    if is_all:
        tests_dir = root / "tests"
        # Wykluczamy _shell.py oraz test_shell_suites.py (bo suity .sh odpalamy osobno)
        all_py = [p.stem for p in tests_dir.glob("test_*.py") if p.name not in ("_shell.py", "test_shell_suites.py")]
        all_sh = [p.name for p in tests_dir.glob("test_*.sh")]
        selected.update(all_py)
        selected.update(all_sh)
        reasons.append("wykryto plik bez trafień grep → uruchamianie pełnej suity (--all)")

    # Sortowanie: szybki rdzeń najpierw, potem reszta alfabetycznie
    sorted_mods = list(FAST_CORE) + sorted(selected - set(FAST_CORE))
    return sorted_mods, is_all, reasons


def _read_last_test_line(log_path: Path) -> str:
    """Odczytaj ostatnią istotną linię z logu z buforem od końca pliku."""
    if not log_path.is_file():
        return "(brak pliku logu)"
    try:
        with open(log_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size == 0:
                return "(log pusty)"
            read_size = min(size, 8192)
            f.seek(size - read_size)
            chunk = f.read().decode("utf-8", errors="replace")
            lines = [line.strip() for line in chunk.splitlines() if line.strip()]
            if not lines:
                return "(log pusty)"
            return lines[-1]
    except OSError:
        return "(błąd odczytu logu)"


def run_with_watchdog(
    cmd: list[str],
    log_path: Path,
    stall_seconds: float = 600.0,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> tuple[int, str, bool]:
    """
    Uruchom zadanie podprocesu, przekierowując stdout/stderr do log_path.
    Jeśli plik logu nie zmienia rozmiaru przez ponad stall_seconds:
    ubija całe drzewo procesów i zwraca kod != 0 oraz stalled=True.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "wb")

    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    # Upewnij się, że PYTHONPATH zawiera katalogi tests i src
    tests_dir = str(cwd / "tests")
    src_dir = str(cwd / "src")
    existing_pp = run_env.get("PYTHONPATH", "")
    prefix = f"{tests_dir}{os.pathsep}{src_dir}"
    run_env["PYTHONPATH"] = f"{prefix}{os.pathsep}{existing_pp}" if existing_pp else prefix

    # Wyłącz buforowanie w Pythonie, aby watchdog widział aktualny log
    run_env["PYTHONUNBUFFERED"] = "1"

    kwargs: dict = {
        "cwd": str(cwd),
        "env": run_env,
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
    }
    if os.name != "nt":
        kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except Exception as exc:
        log_file.write(f"Nie udało się uruchomić procesu: {exc}\n".encode("utf-8"))
        log_file.close()
        return (1, f"błąd uruchomienia: {exc}", False)

    ACTIVE_PROCS.add(proc)
    last_change_time = time.time()
    last_size = 0
    stalled = False

    try:
        while proc.poll() is None:
            time.sleep(0.05)
            try:
                current_size = log_path.stat().st_size
            except OSError:
                current_size = 0

            if current_size != last_size:
                last_size = current_size
                last_change_time = time.time()
            elif time.time() - last_change_time > stall_seconds:
                stalled = True
                break
    except (KeyboardInterrupt, SystemExit):
        stalled = False
        if os.name != "nt":
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGKILL)
            except OSError:
                pass
        else:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                check=False,
            )
        raise
    finally:
        ACTIVE_PROCS.discard(proc)
        if stalled:
            if os.name != "nt":
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(0.2)
                    os.killpg(pgid, signal.SIGKILL)
                except OSError:
                    pass
            else:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    check=False,
                )
            try:
                proc.wait(timeout=2.0)
            except (subprocess.TimeoutExpired, OSError):
                proc.kill()

        log_file.flush()
        log_file.close()

    last_line = _read_last_test_line(log_path)
    returncode = 124 if stalled else (proc.returncode if proc.returncode is not None else 1)
    return (returncode, last_line, stalled)


def run_module(
    module_name: str,
    log_dir: Path,
    stall_seconds: float,
    root: Path = ROOT,
) -> dict[str, str | float | int]:
    """Uruchom pojedynczy moduł testów i zwróć metryki."""
    log_path = log_dir / f"{module_name}.log"
    tests_dir = root / "tests"

    if module_name.endswith(".sh"):
        bash = resolve_bash()
        if not bash:
            return {
                "module": module_name,
                "status": "SKIP",
                "time": 0.0,
                "log": "-",
                "returncode": 0,
                "last_line": "pominięto: brak bash w PATH",
            }
        script_path = tests_dir / module_name
        cmd = [bash, "--noprofile", "--norc", posix_path(script_path)]
    else:
        # Moduł Pythona
        mod_arg = f"tests.{module_name}" if not module_name.startswith("tests.") else module_name
        cmd = [sys.executable, "-m", "unittest", mod_arg]

    start = time.time()
    try:
        code, last_line, stalled = run_with_watchdog(cmd, log_path=log_path, stall_seconds=stall_seconds, cwd=root)
    except Exception as exc:
        code, last_line, stalled = 1, f"błąd: {exc}", False

    elapsed = time.time() - start

    try:
        log_rel = str(log_path.relative_to(root)).replace("\\", "/")
    except ValueError:
        log_rel = str(log_path).replace("\\", "/")

    status = "STALL" if stalled else ("OK" if code == 0 else "FAIL")
    return {
        "module": module_name,
        "status": status,
        "time": round(elapsed, 2),
        "log": log_rel,
        "returncode": code,
        "last_line": last_line,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Szybki lokalny runner testów dla zmienionych plików.")
    parser.add_argument("files", nargs="*", help="Ścieżki zmienionych plików (domyślnie wykrywane z gita)")
    parser.add_argument("--dry-run", action="store_true", help="Wypisz wybrane moduły bez uruchamiania")
    parser.add_argument("--all", action="store_true", help="Uruchom wszystkie moduły testów")
    parser.add_argument("-j", "--jobs", type=int, default=1, help="Liczba równoległych zadań (domyślnie 1)")
    parser.add_argument("--stall-min", type=float, default=10.0, help="Limit ciszy w logu w minutach (domyślnie 10)")
    parser.add_argument("--base", type=str, default=None, help="Gałąź bazowa (domyślnie z .ai/project.md)")

    args = parser.parse_args(argv)

    if args.jobs < 1:
        parser.error("Liczba zadań (-j) musi być większa lub równa 1")
    if args.stall_min <= 0:
        parser.error("Limit ciszy (--stall-min) musi być większy od 0")

    # Obsługa sygnałów do czyszczenia procesów potomnych
    def sig_handler(signum, frame):
        kill_active_processes()
        sys.exit(130)

    try:
        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)
    except (ValueError, OSError):
        pass

    if args.all:
        tests_dir = ROOT / "tests"
        selected = list(FAST_CORE)
        py_mods = sorted(p.stem for p in tests_dir.glob("test_*.py") if p.name not in ("_shell.py", "test_shell_suites.py") and p.stem not in FAST_CORE)
        sh_mods = sorted(p.name for p in tests_dir.glob("test_*.sh"))
        selected.extend(py_mods)
        selected.extend(sh_mods)
        reasons = ["wymuszono flagę --all"]
    elif args.files:
        selected, is_all, reasons = resolve_test_targets(args.files, root=ROOT)
    else:
        changed_files = get_merge_base_and_changes(base_branch=args.base, root=ROOT)
        if not changed_files:
            selected = list(FAST_CORE)
            reasons = ["czyste drzewo robocze na bazie → sam szybki rdzeń"]
        else:
            selected, is_all, reasons = resolve_test_targets(changed_files, root=ROOT)

    print("Powody wyboru modułów:")
    for r in reasons:
        print(f"  • {r}")
    print()

    print(f"Wybrane moduły testów ({len(selected)}):")
    for m in selected:
        print(f"  - {m}")
    print()

    if args.dry_run:
        return 0

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = ROOT / ".cache" / "test-runs" / timestamp
    log_dir.mkdir(parents=True, exist_ok=True)
    stall_sec = args.stall_min * 60.0

    print(f"Uruchamianie testów (-j {args.jobs}, stall timeout {args.stall_min} min)...")
    print(f"Katalog logów: {log_dir.relative_to(ROOT)}\n")

    results: list[dict] = []
    try:
        if args.jobs > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
                futures = [
                    executor.submit(run_module, m, log_dir, stall_sec, ROOT)
                    for m in selected
                ]
                for future in concurrent.futures.as_completed(futures):
                    res = future.result()
                    results.append(res)
                    print(f"[{res['status']}] {res['module']} ({res['time']}s)")
        else:
            for m in selected:
                res = run_module(m, log_dir, stall_sec, ROOT)
                results.append(res)
                print(f"[{res['status']}] {res['module']} ({res['time']}s)")
    except KeyboardInterrupt:
        kill_active_processes()
        print("\nPrzerwano działanie runnera (SIGINT).")
        return 130

    # Sortuj wyniki wg kolejności wyboru
    order_map = {name: i for i, name in enumerate(selected)}
    results.sort(key=lambda r: order_map.get(str(r["module"]), 999))

    print("\n" + "=" * 80)
    print(f"{'moduł':<35} | {'wynik':<7} | {'czas':<7} | {'log'}")
    print("-" * 80)
    all_ok = True
    for r in results:
        if r["returncode"] != 0:
            all_ok = False
        print(f"{r['module']:<35} | {r['status']:<7} | {r['time']!s:>5}s | {r['log']}")
        if r["status"] == "STALL":
            print(f"    └─ STALL! Ostatnia linia: {r.get('last_line')}")
        elif r["status"] == "FAIL":
            print(f"    └─ BŁĄD! Ostatnia linia: {r.get('last_line')}")
    print("=" * 80 + "\n")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
