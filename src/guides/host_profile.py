"""Wykrywanie profilu hosta — lekki tryb VPS bez wpisywania nazw hostów.

Heurystyka zasobów + wirtualizacja + brak desktopu; nadpisanie zmienną
środowiskową ``KIT_HOST_PROFILE`` (alias ``GUIDES_HOST_PROFILE``).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

VPS_PROFILE = "vps"
LOCAL_PROFILE = "local"

HOST_PROFILE_ENV_VARS = ("KIT_HOST_PROFILE", "GUIDES_HOST_PROFILE")

SMALL_CPU_MAX = 2
SMALL_RAM_MAX_BYTES = 8 * 1024**3

VPS_LIGHTWEIGHT_MODULE = "infra:vps-lightweight"

_CI_ENV_VARS = (
    "CI",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "JENKINS_URL",
    "BUILDKITE",
    "CIRCLECI",
    "TRAVIS",
    "TF_BUILD",
)

_DESKTOP_ENV_VARS = (
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XDG_CURRENT_DESKTOP",
    "DESKTOP_SESSION",
)


def normalize_host_profile_override(raw: object | None) -> str | None:
    """Znormalizuj nadpisanie profilu hosta do ``vps`` / ``local``.

    Args:
        raw: Wartość zmiennej środowiskowej (dowolny case, białe znaki).

    Returns:
        str | None: ``vps`` / ``local`` albo ``None`` gdy brak / nierozpoznane.
    """
    if not isinstance(raw, str):
        return None
    key = raw.strip().lower()
    if key in (VPS_PROFILE, LOCAL_PROFILE):
        return key
    return None


def read_override(env: dict[str, str] | os._Environ = os.environ) -> str | None:
    """Odczytaj nadpisanie profilu hosta ze zmiennych środowiskowych.

    Args:
        env: Mapowanie zmiennych (domyślnie ``os.environ``).

    Returns:
        str | None: ``vps`` / ``local`` albo ``None``.
    """
    for var in HOST_PROFILE_ENV_VARS:
        override = normalize_host_profile_override(env.get(var))
        if override is not None:
            return override
    return None


def _read_meminfo(path: Path = Path("/proc/meminfo")) -> tuple[int | None, int | None]:
    """Odczytaj RAM i swap z ``/proc/meminfo`` (Linux).

    Args:
        path: Ścieżka do pliku meminfo (do testów).

    Returns:
        tuple: ``(mem_total_bytes, swap_total_bytes)`` — ``None`` gdy brak pliku.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None, None
    mem_total = swap_total = None
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            mem_total = _parse_kb_line(line)
        elif line.startswith("SwapTotal:"):
            swap_total = _parse_kb_line(line)
    return mem_total, swap_total


def _parse_kb_line(line: str) -> int | None:
    """Przekształć linię ``Klucz: <liczba> kB`` na bajty."""
    parts = line.split()
    if len(parts) < 2:
        return None
    try:
        return int(parts[1]) * 1024
    except ValueError:
        return None


def _detect_virt() -> str:
    """Wykryj wirtualizację przez ``systemd-detect-virt``.

    Returns:
        str: Wynik komendy (lowercase), ``"none"`` na bare metal,
            ``""`` gdy komendy brak / błąd.
    """
    binary = shutil.which("systemd-detect-virt")
    if not binary:
        return ""
    try:
        proc = subprocess.run(
            [binary],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (proc.stdout or "").strip().lower()


def _is_ci(env: dict[str, str] | os._Environ) -> bool:
    """Czy proces działa w CI (pełna weryfikacja należy do CI, nie do VPS)."""
    ci_flag = str(env.get("CI", "")).strip().lower()
    if ci_flag in ("1", "true", "yes"):
        return True
    return any(str(env.get(var, "")).strip() for var in _CI_ENV_VARS[1:])


def _has_desktop(env: dict[str, str] | os._Environ) -> bool:
    """Czy sesja ma desktop (DISPLAY / Wayland / XDG desktop)."""
    return any(str(env.get(var, "")).strip() for var in _DESKTOP_ENV_VARS)


def _is_wsl(env: dict[str, str] | os._Environ) -> bool:
    """Czy to WSL (dev na Windows, nie VPS mimo małych zasobów)."""
    if str(env.get("WSL_DISTRO_NAME", "")).strip() or str(env.get("WSL_INTEROP", "")).strip():
        return True
    try:
        version = Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return "microsoft" in version or "wsl" in version


def detect_host_profile(
    *,
    env: dict[str, str] | os._Environ | None = None,
    platform: str | None = None,
    cpu_count: int | None = None,
    mem_total_bytes: int | None = None,
    swap_total_bytes: int | None = None,
    virt: str | None = None,
    has_desktop: bool | None = None,
    is_ci: bool | None = None,
    is_wsl: bool | None = None,
) -> str:
    """Wykryj profil hosta heurystyką (bez nazw hostów).

    VPS to Linux bez CI, z małymi zasobami (CPU ≤ 2, RAM ≤ 8 GB, brak swapu)
    i sygnałem serwerowym (wirtualizacja albo brak desktopu). WSL zawsze local.

    Args:
        env: Zmienne środowiskowe (do nadpisania i sygnałów CI/desktop/WSL).
        platform: ``sys.platform`` (testy podają ``"linux"`` / ``"win32"``).
        cpu_count: Liczba vCPU (domyślnie ``os.cpu_count()``).
        mem_total_bytes: RAM z ``/proc/meminfo`` (domyślnie odczyt live).
        swap_total_bytes: Swap z ``/proc/meminfo`` (domyślnie odczyt live).
        virt: Wynik ``systemd-detect-virt`` (domyślnie wywołanie live na Linuxie).
        has_desktop: Nadpisanie wykrywania desktopu (domyślnie z env).
        is_ci: Nadpisanie wykrywania CI (domyślnie z env).
        is_wsl: Nadpisanie wykrywania WSL (domyślnie z ``/proc/version`` + env).

    Returns:
        str: ``vps`` albo ``local``.
    """
    env = os.environ if env is None else env
    override = read_override(env)
    if override is not None:
        return override

    plat = sys.platform if platform is None else platform
    if not plat.startswith("linux"):
        return LOCAL_PROFILE

    ci = _is_ci(env) if is_ci is None else is_ci
    if ci:
        return LOCAL_PROFILE

    wsl = _is_wsl(env) if is_wsl is None else is_wsl
    if wsl:
        return LOCAL_PROFILE

    cpu = os.cpu_count() if cpu_count is None else cpu_count
    if mem_total_bytes is None or swap_total_bytes is None:
        live_mem, live_swap = _read_meminfo()
        if mem_total_bytes is None:
            mem_total_bytes = live_mem
        if swap_total_bytes is None:
            swap_total_bytes = live_swap
    if cpu is None or mem_total_bytes is None or swap_total_bytes is None:
        return LOCAL_PROFILE

    small_resources = (
        cpu <= SMALL_CPU_MAX
        and mem_total_bytes <= SMALL_RAM_MAX_BYTES
        and swap_total_bytes == 0
    )
    if not small_resources:
        return LOCAL_PROFILE

    virt_value = _detect_virt() if virt is None else virt.strip().lower()
    virtualized = bool(virt_value) and virt_value not in ("none", "unknown")
    desktop = _has_desktop(env) if has_desktop is None else has_desktop
    headless = not desktop

    if virtualized or headless:
        return VPS_PROFILE
    return LOCAL_PROFILE


def get_host_profile() -> str:
    """Profil bieżącego hosta (env override albo heurystyka)."""
    return detect_host_profile()


def is_vps_host() -> bool:
    """Czy bieżący host to VPS (lekki tryb agenta)."""
    return get_host_profile() == VPS_PROFILE
