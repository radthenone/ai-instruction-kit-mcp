"""
Spójność artefaktów generowanych z jednego źródła.

Dwie luki, które ten moduł zamyka:

1. Wpis w `manifest.yaml` może wskazywać na nieistniejący plik — dotąd ujawniało
   się to dopiero przy `get_module()` u użytkownika.
2. To repo dogfooduje własny kit: `.cursor/agents/`, `.claude/agents/` i
   `.claude/commands/` to kopie `templates/shared/agents/`. Dodanie agenta bez
   regeneracji kopii przechodziło CI niezauważone.

Parytet kopii sprawdzamy **wywołując prawdziwy bootstrap**, a nie powtarzając tu
jego logikę transformacji — test powtarzający kod produkcyjny powtórzyłby też
jego błędy.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

# Jedno źródło wykrywania Git Basha — to samo, którego używa test_shell_suites.
from test_bash_hook_launcher import is_ci, posix_path, resolve_bash

from guides.manifest import find_kit_root, load_manifest

KIT_ROOT = find_kit_root(Path(__file__))

# Katalogi, które bootstrap wypełnia z templates/shared/agents/.
DOGFOOD_DIRS = (".cursor/agents", ".claude/agents", ".claude/commands")

# Guardraile mają jedno źródło (templates/shared/guards) i trafiają do katalogu
# hooków każdego klienta, który potrafi je egzekwować. Kopia w tym repo musi być
# identyczna ze źródłem — inaczej Cursor i Claude rozjeżdżają się na polityce,
# co jest dokładnie tą luką, dla której guardraile trafiły do shared.
GUARD_COPIES: tuple[tuple[str, str], ...] = (
    (".cursor/hooks", "gate-destructive.sh"),
    (".cursor/hooks", "gate-push.sh"),
    (".cursor/hooks", "invoke-hook.js"),
    (".claude/hooks", "gate-destructive.sh"),
    (".claude/hooks", "gate-push.sh"),
    (".claude/hooks", "invoke-hook.js"),
    (".claude/hooks", "gate-file-writes.mjs"),
)


class TestManifestPaths(unittest.TestCase):
    """Każdy moduł z rejestru musi mieć plik na dysku."""

    def test_every_module_path_exists(self) -> None:
        """Literówka w `path:` nie może przejść do wydania."""
        manifest = load_manifest(KIT_ROOT)
        missing = sorted(
            f"{module_id} -> {info.path.relative_to(KIT_ROOT)}"
            for module_id, info in manifest.modules.items()
            if not info.path.is_file()
        )
        self.assertEqual(missing, [], msg=f"moduły bez pliku: {missing}")


class TestDogfoodCopies(unittest.TestCase):
    """Kopie agentów w tym repo == to, co wygenerowałby bootstrap."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp(prefix="kit-dogfood-")
        target = Path(cls._tmp) / "generated"
        boot = KIT_ROOT / "scripts" / "bootstrap-project.sh"

        # Windows nie umie odpalić `.sh` przez CreateProcess (WinError 193) — bootstrap
        # trzeba podać bashowi jawnie, tak samo jak robią to pozostałe suity.
        bash = resolve_bash()
        if not bash:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            if is_ci():
                raise AssertionError("brak bash na CI — parytet kopii musi być sprawdzony")
            raise unittest.SkipTest("brak bash — pomijam parytet kopii")

        result = subprocess.run(
            [
                bash,
                "--noprofile",
                "--norc",
                posix_path(boot),
                str(target),
                "--clients",
                "claude,cursor",
                "--from",
                str(KIT_ROOT),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise AssertionError(f"bootstrap nie wystartował ({result.returncode}): {result.stderr}")
        cls.generated = target

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def _shared_agents(self) -> list[Path]:
        agents = sorted((KIT_ROOT / "templates" / "shared" / "agents").glob("*.md"))
        self.assertNotEqual(agents, [], msg="brak agentów w templates/shared/agents")
        return agents

    def test_copies_match_bootstrap_output(self) -> None:
        """Każdy shared agent ma w repo kopię identyczną z wygenerowaną."""
        stale: list[str] = []
        for agent in self._shared_agents():
            for rel_dir in DOGFOOD_DIRS:
                in_repo = KIT_ROOT / rel_dir / agent.name
                expected = self.generated / rel_dir / agent.name
                if not in_repo.is_file():
                    stale.append(f"{rel_dir}/{agent.name} — brak kopii w repo")
                elif in_repo.read_text(encoding="utf-8") != expected.read_text(encoding="utf-8"):
                    stale.append(f"{rel_dir}/{agent.name} — kopia rozjechała się ze źródłem")
        self.assertEqual(
            stale,
            [],
            msg="uruchom bootstrap na tym repo albo zregeneruj kopie: " + "; ".join(stale),
        )

    def test_guard_copies_match_shared_source(self) -> None:
        """Hook u klienta == plik w `templates/shared/guards/`, bajt w bajt."""
        source_dir = KIT_ROOT / "templates" / "shared" / "guards"
        stale: list[str] = []
        for rel_dir, name in GUARD_COPIES:
            source = source_dir / name
            self.assertTrue(source.is_file(), msg=f"brak źródła {source}")
            in_repo = KIT_ROOT / rel_dir / name
            if not in_repo.is_file():
                stale.append(f"{rel_dir}/{name} — brak kopii w repo")
            elif in_repo.read_bytes() != source.read_bytes():
                stale.append(f"{rel_dir}/{name} — kopia rozjechała się ze źródłem")
        self.assertEqual(
            stale,
            [],
            msg="uruchom bootstrap na tym repo: " + "; ".join(stale),
        )

    def test_guard_copies_match_bootstrap_output(self) -> None:
        """To samo, ale względem tego, co naprawdę instaluje bootstrap."""
        stale = [
            f"{rel_dir}/{name}"
            for rel_dir, name in GUARD_COPIES
            if (KIT_ROOT / rel_dir / name).read_bytes()
            != (self.generated / rel_dir / name).read_bytes()
        ]
        self.assertEqual(stale, [], msg=f"kopie niezgodne z bootstrapem: {stale}")

    def test_cursor_does_not_get_file_write_guard(self) -> None:
        """Cursor ma tylko `afterFileEdit` — bramka przed zapisem nie ma tam sensu."""
        self.assertFalse((self.generated / ".cursor/hooks/gate-file-writes.mjs").exists())
        self.assertFalse((KIT_ROOT / ".cursor/hooks/gate-file-writes.mjs").exists())

    def test_no_orphan_copies(self) -> None:
        """Kopia bez odpowiednika w shared to pozostałość po usuniętym agencie."""
        known = {agent.name for agent in self._shared_agents()}
        orphans = sorted(
            f"{rel_dir}/{found.name}"
            for rel_dir in DOGFOOD_DIRS
            for found in (KIT_ROOT / rel_dir).glob("*.md")
            if found.name not in known
        )
        self.assertEqual(orphans, [], msg=f"kopie bez źródła w shared: {orphans}")


if __name__ == "__main__":
    unittest.main()
