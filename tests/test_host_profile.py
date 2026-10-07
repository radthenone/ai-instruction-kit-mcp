"""Testy wykrywania profilu hosta VPS (issue #152)."""

from __future__ import annotations

import unittest

from guides.host_profile import (
    VPS_LIGHTWEIGHT_MODULE,
    detect_host_profile,
    normalize_host_profile_override,
    read_override,
)


def _env(**overrides: str) -> dict[str, str]:
    base: dict[str, str] = {}
    base.update(overrides)
    return base


class TestHostProfileOverride(unittest.TestCase):
    def test_override_vps_case_insensitive(self) -> None:
        self.assertEqual(normalize_host_profile_override("VPS"), "vps")
        self.assertEqual(normalize_host_profile_override(" local "), "local")

    def test_override_unknown_is_none(self) -> None:
        self.assertIsNone(normalize_host_profile_override(None))
        self.assertIsNone(normalize_host_profile_override("prod"))
        self.assertIsNone(normalize_host_profile_override(""))

    def test_kit_host_profile_wins(self) -> None:
        env = _env(KIT_HOST_PROFILE="vps")
        self.assertEqual(read_override(env), "vps")
        self.assertEqual(detect_host_profile(env=env, platform="win32"), "vps")

    def test_guides_alias_supported(self) -> None:
        env = _env(GUIDES_HOST_PROFILE="local")
        self.assertEqual(read_override(env), "local")

    def test_no_hardcoded_hostnames(self) -> None:
        import guides.host_profile as module
        import pathlib

        src = pathlib.Path(module.__file__).read_text(encoding="utf-8").lower()
        for hostname in ("mikrus", "olivin", "hetzner", "ovh"):
            self.assertNotIn(hostname, src)


class TestHostProfileHeuristic(unittest.TestCase):
    def test_mikrus_like_vps(self) -> None:
        env = _env()
        profile = detect_host_profile(
            env=env,
            platform="linux",
            cpu_count=1,
            mem_total_bytes=int(4.5 * 1024**3),
            swap_total_bytes=0,
            virt="lxc",
            has_desktop=False,
            is_ci=False,
            is_wsl=False,
        )
        self.assertEqual(profile, "vps")

    def test_large_dev_machine_is_local(self) -> None:
        env = _env()
        profile = detect_host_profile(
            env=env,
            platform="linux",
            cpu_count=8,
            mem_total_bytes=32 * 1024**3,
            swap_total_bytes=8 * 1024**3,
            virt="none",
            has_desktop=True,
            is_ci=False,
            is_wsl=False,
        )
        self.assertEqual(profile, "local")

    def test_small_bare_metal_with_desktop_is_local(self) -> None:
        env = _env()
        profile = detect_host_profile(
            env=env,
            platform="linux",
            cpu_count=2,
            mem_total_bytes=4 * 1024**3,
            swap_total_bytes=0,
            virt="none",
            has_desktop=True,
            is_ci=False,
            is_wsl=False,
        )
        self.assertEqual(profile, "local")

    def test_ci_forces_local(self) -> None:
        env = _env(CI="true")
        profile = detect_host_profile(
            env=env,
            platform="linux",
            cpu_count=1,
            mem_total_bytes=4 * 1024**3,
            swap_total_bytes=0,
            virt="kvm",
            has_desktop=False,
            is_ci=None,
            is_wsl=False,
        )
        self.assertEqual(profile, "local")

    def test_wsl_forces_local(self) -> None:
        env = _env(WSL_DISTRO_NAME="Ubuntu")
        profile = detect_host_profile(
            env=env,
            platform="linux",
            cpu_count=1,
            mem_total_bytes=4 * 1024**3,
            swap_total_bytes=0,
            virt="wsl",
            has_desktop=False,
            is_ci=False,
            is_wsl=None,
        )
        self.assertEqual(profile, "local")

    def test_non_linux_is_local(self) -> None:
        env = _env()
        self.assertEqual(
            detect_host_profile(
                env=env,
                platform="win32",
                cpu_count=1,
                mem_total_bytes=4 * 1024**3,
                swap_total_bytes=0,
                virt="",
                has_desktop=False,
                is_ci=False,
                is_wsl=False,
            ),
            "local",
        )

    def test_module_constant(self) -> None:
        self.assertEqual(VPS_LIGHTWEIGHT_MODULE, "infra:vps-lightweight")


if __name__ == "__main__":
    unittest.main()
