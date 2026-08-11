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

from guides.manifest import find_kit_root, load_manifest

KIT_ROOT = find_kit_root(Path(__file__))

# Katalogi, które bootstrap wypełnia z templates/shared/agents/.
DOGFOOD_DIRS = (".cursor/agents", ".claude/agents", ".claude/commands")


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
        result = subprocess.run(
            [str(boot), str(target), "--clients", "claude,cursor", "--from", str(KIT_ROOT)],
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
