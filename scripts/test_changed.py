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
import threading
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

# Szybki rdzeń - uruchamiany ZAWSZE (< 1 s łącznie)
FAST_CORE: tuple[str, ...] = (
    "test_resolver",
    "test_manifest_mappings",
    "test_mcp_compat",
)

# Ścieżki ignorowane (sam szybki rdzeń, brak --all)
IGNORED_PATHS: set[str] = {
    "LICENSE",
}

# Jawna mapa wyjątków: stem pliku źródłowego -> moduły testów
EXCEPTIONS: dict[str, list[str]] = {
    "agent_classes": ["test_agent_classification"],
    "manifest": ["test_manifest_mappings"],
    "server": ["test_server_instructions", "test_mcp_compat"],
    "server_guard": ["test_guards"],
    "worktree": ["test_worktree"],
    "headless": ["test_headless"],
    "brief": ["test_brief_rules"],
    "bootstrap": ["test_bootstrap"],
    "install_agent_skills": ["test_bootstrap_clients.sh", "test_generated_artifacts"],
    "render_agent_commands": ["test_bootstrap_clients.sh", "test_generated_artifacts"],
    "render_server_guard": ["test_guards", "test_lf_writes"],
    "render_worktree": ["test_worktree"],
    "render_brief_rules": ["test_brief_rules"],
    "render_integrations": ["test_integrations"],
    "antigravity_hooks": ["test_antigravity_hooks"],
    "test_changed": ["test_test_changed"],
    "__main__": ["test_server_instructions", "test_mcp_compat"],
    "project_brief": ["test_kit_brief", "test_resolver"],
}

# Zbiór aktywnych procesów potomnych oraz flaga anulowania
ACTIVE_PROCS: set[subprocess.Popen] = set()
CANCEL_EVENT = threading.Event()


def kill_active_processes() -> None:
    """Zabij wszystkie aktywne procesy potomne runnera."""
    for proc in list(ACTIVE_PROCS):
        try:
            if os.name != "nt":
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
                try:
                    proc.kill()
                except OSError:
                    pass
            else:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                try:
                    proc.kill()
                except OSError:
                    pass
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

    root_resolved = root.resolve()
    cwd_resolved = Path.cwd().resolve()

    p = Path(raw)
    if p.is_absolute():
        try:
            return str(p.resolve().relative_to(root_resolved)).replace("\\", "/")
        except ValueError:
            return str(p).replace("\\", "/")

    # Jeśli podano ścieżkę z poziomu podkatalogu roboczego (np. z cwd)
    try:
        from_cwd = (cwd_resolved / raw).resolve()
        if from_cwd.exists() and from_cwd.is_relative_to(root_resolved):
            return str(from_cwd.relative_to(root_resolved)).replace("\\", "/")
    except (ValueError, AttributeError):
        pass

    # Rozwiąż ewentualne .. lub ./ względem root
    try:
        from_root = (root / raw).resolve()
        if from_root.is_relative_to(root_resolved):
            return str(from_root.relative_to(root_resolved)).replace("\\", "/")
    except (ValueError, AttributeError):
        pass

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
        is_test_file = (norm_path.endswith(".py") and p.name.startswith("test_")) or norm_path.endswith(".sh")
        if not (root / norm_path).is_file():
            if is_test_file:
                return [], f"{norm_path} usunięty plik testu (pominięto)"
            # Plik pomocniczy w tests/ (np. tests/_shell.py) przechodzi dalej do wyjątków i fallback grepa
        else:
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

    # 3. Fallback grep w tests/*.py i tests/*.sh
    if test_contents is None:
        test_contents = _get_test_contents(root)

    matched_modules: set[str] = set()
    patterns = [norm_path, p.name]

    for test_file_name, content in test_contents.items():
        if test_file_name == "_shell.py":
            continue
        for pat in patterns:
            if pat in content:
                if test_file_name.endswith(".py"):
                    matched_modules.add(Path(test_file_name).stem)
                elif test_file_name.endswith(".sh"):
                    matched_modules.add(test_file_name)
                break

    if matched_modules:
        # Usuwamy test_shell_suites jeśli dopasowano bezpośrednie skrypty .sh
        sh_found = [m for m in matched_modules if m.endswith(".sh")]
        if sh_found and "test_shell_suites" in matched_modules:
            matched_modules.remove("test_shell_suites")
        mods = sorted(matched_modules)
        return mods, f"{norm_path} → {', '.join(mods)} (fallback grep)"

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
            is_test_file = (norm.endswith(".py") and Path(norm).name.startswith("test_")) or norm.endswith(".sh")
            if norm.startswith("tests/") and is_test_file and not (root / norm).is_file():
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
    """Odczytaj ostatnią niepustą linię logu testu."""
    if not log_path.is_file():
        return "brak pliku logu"
    try:
        lines = [line.strip() for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        return lines[-1] if lines else "pusty log"
    except Exception as exc:
        return f"błąd odczytu logu: {exc}"


def run_with_watchdog(
    cmd: list[str],
    log_path: Path,
    stall_seconds: float,
    cwd: Path = ROOT,
) -> tuple[int, str, bool]:
    """
    Uruchom polecenie z przekierowaniem stdout/stderr do log_path.
    Jeśli plik logu nie powiększy się przez stall_seconds, zabij całą grupę procesów.

    Zwraca: (kod_zakończenia, ostatnia_linia, czy_stall).
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8", buffering=1)

    # Uruchamiamy w nowej sesji, by móc ubić całą grupę procesów potomnych
    kwargs: dict = {
        "cwd": str(cwd),
        "stdin": subprocess.DEVNULL,
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
    }
    if os.name != "nt":
        kwargs["start_new_session"] = True
    else:
        # CREATE_NEW_PROCESS_GROUP na Windows
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    # Zapewnij widoczność tests/ i src/ na PYTHONPATH
    run_env = os.environ.copy()
    tests_dir = str((cwd / "tests").resolve())
    src_dir = str((cwd / "src").resolve())
    existing_pythonpath = run_env.get("PYTHONPATH", "")
    parts = [tests_dir, src_dir]
    if existing_pythonpath:
        parts.append(existing_pythonpath)
    run_env["PYTHONPATH"] = os.pathsep.join(parts)
    kwargs["env"] = run_env

    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except Exception as exc:
        log_file.write(f"Błąd uruchomienia procesu: {exc}\n")
        log_file.close()
        return (1, f"błąd uruchomienia: {exc}", False)

    ACTIVE_PROCS.add(proc)
    if CANCEL_EVENT.is_set():
        kill_active_processes()
    last_change_time = time.time()
    last_size = 0
    stalled = False

    try:
        while True:
            ret = proc.poll()
            if ret is not None:
                break

            time.sleep(0.1)

            try:
                current_size = log_path.stat().st_size
            except OSError:
                current_size = last_size

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
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                proc.kill()
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
                    os.killpg(proc.pid, signal.SIGTERM)
                    time.sleep(0.2)
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
                try:
                    proc.kill()
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
    if CANCEL_EVENT.is_set():
        return {
            "module": module_name,
            "status": "FAIL",
            "time": 0.0,
            "log": "anulowano",
            "returncode": 130,
            "last_line": "anulowano (SIGINT/SIGTERM)",
        }

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
    parser = argparse.ArgumentParser(description="Szybki runner testów dla zmienionych plików")
    parser.add_argument("files", nargs="*", help="Jawna lista plików do przetestowania")
    parser.add_argument("--dry-run", action="store_true", help="Tylko wypisz wybrane moduły bez uruchamiania")
    parser.add_argument("--all", action="store_true", help="Uruchom wszystkie moduły testów")
    parser.add_argument("-j", "--jobs", type=int, default=1, help="Liczba równoległych zadań (domyślnie 1)")
    parser.add_argument("--stall-min", type=float, default=10.0, help="Limit ciszy w logu w minutach (domyślnie 10)")
    parser.add_argument("--base", type=str, default=None, help="Gałąź bazowa (domyślnie z .ai/project.md)")

    args = parser.parse_args(argv)

    if args.jobs < 1:
        parser.error("Liczba zadań (-j) musi być większa lub równa 1")
    if args.stall_min <= 0:
        parser.error("Limit ciszy (--stall-min) musi być większy od 0")

    executor: concurrent.futures.ThreadPoolExecutor | None = None

    # Obsługa sygnałów do czyszczenia procesów potomnych
    def sig_handler(signum, frame):
        CANCEL_EVENT.set()
        kill_active_processes()
        if executor is not None:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
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
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs)
            futures = [
                executor.submit(run_module, m, log_dir, stall_sec, ROOT)
                for m in selected
            ]
            for future in concurrent.futures.as_completed(futures):
                if CANCEL_EVENT.is_set():
                    break
                res = future.result()
                results.append(res)
                print(f"[{res['status']}] {res['module']} ({res['time']}s)")
            executor.shutdown(wait=True)
            executor = None
        else:
            for m in selected:
                if CANCEL_EVENT.is_set():
                    break
                res = run_module(m, log_dir, stall_sec, ROOT)
                results.append(res)
                print(f"[{res['status']}] {res['module']} ({res['time']}s)")
    except (KeyboardInterrupt, SystemExit):
        CANCEL_EVENT.set()
        kill_active_processes()
        if executor is not None:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
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
