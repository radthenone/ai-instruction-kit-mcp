"""
Prefiks komend per klient (#525, expand): manifest, podstawienie i zapis plików.

Seam 2: ``load_manifest`` zwraca trzy pola na cel (sigil, namespace, name_prefix).
Seam 1: bootstrap w tymczasowym workspace nie zostawia nierozwiązanego
``@KIT_CMD_PREFIX@`` ani ``@KIT_NAME_PREFIX@``, także przy kopiach ``cp`` (cel shared).
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from guides.bootstrap import find_bash
from guides.manifest import find_kit_root, load_manifest

KIT_ROOT = find_kit_root()
SCRIPTS = KIT_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    # render_agent_commands.py importuje command_prefix; przy uruchomieniu z bash jest to automatyczne.
    sys.path.insert(0, str(SCRIPTS))
TARGETS = ("claude", "codex", "vscode", "antigravity", "opencode", "shared", "cursor", "kiro", "kilo")
CLIENTS = "claude,codex,vscode,antigravity,opencode"
PLACEHOLDERS = (b"@KIT_CMD_PREFIX@", b"@KIT_NAME_PREFIX@")


def _load_script(name: str):
    """Załaduj skrypt z ``scripts/`` jako moduł, bez zmiany sys.path."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_kit(dest: Path) -> None:
    """Skopiuj kit do ``dest``, żeby bootstrap działał na kopii, a nie na repo."""
    shutil.copytree(
        KIT_ROOT,
        dest,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"),
    )


def _init_workspace(path: Path) -> Path:
    """Utwórz pusty workspace z gitem, tak jak przy pierwszej instalacji."""
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def _run_bootstrap(kit: Path, workspace: Path, config_home: Path) -> subprocess.CompletedProcess[str]:
    """Uruchom ``bootstrap-project.sh`` z ``kit`` w ``workspace`` na interpreterze testu."""
    env = {**os.environ, "KIT_PYTHON": sys.executable, "XDG_CONFIG_HOME": str(config_home)}
    return subprocess.run(
        [find_bash(), str(kit / "scripts" / "bootstrap-project.sh"), str(workspace), "--clients", CLIENTS],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        stdin=subprocess.DEVNULL,
    )


class TestManifestCommandPrefixes(unittest.TestCase):
    """Seam 2: ``load_manifest`` daje trzy pola na każdy cel."""

    def test_every_target_has_default_triple(self) -> None:
        manifest = load_manifest(KIT_ROOT)
        for target in TARGETS:
            prefix = manifest.command_prefix(target)
            self.assertEqual((prefix.sigil, prefix.namespace, prefix.name_prefix), ("/", "", ""), target)

    def test_unknown_target_raises(self) -> None:
        with self.assertRaises(ValueError):
            load_manifest(KIT_ROOT).command_prefix("nie-ma-takiego-celu")

    def test_sigil_other_than_slash_or_dollar_is_rejected(self) -> None:
        raw = yaml.safe_load((KIT_ROOT / "manifest.yaml").read_text(encoding="utf-8"))
        raw["command_prefixes"]["claude"]["sigil"] = "!"
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "manifest.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_manifest(Path(tmp))

    def test_null_namespace_becomes_empty_string(self) -> None:
        raw = yaml.safe_load((KIT_ROOT / "manifest.yaml").read_text(encoding="utf-8"))
        raw["command_prefixes"]["claude"]["namespace"] = None
        raw["command_prefixes"]["claude"]["name_prefix"] = None
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "manifest.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
            prefix = load_manifest(Path(tmp)).command_prefix("claude")
        self.assertEqual((prefix.namespace, prefix.name_prefix), ("", ""))


class TestPlaceholderResolution(unittest.TestCase):
    """Podstawienie w treści i we frontmatter ``name:``."""

    def test_body_placeholder_takes_sigil_and_namespace(self) -> None:
        resolve = _load_script("command_prefix").resolve
        self.assertEqual(
            resolve("Uruchom @KIT_CMD_PREFIX@git-start", sigil="$", namespace="kit-ai:", name_prefix="kit-ai:"),
            "Uruchom $kit-ai:git-start",
        )

    def test_name_placeholder_takes_name_prefix(self) -> None:
        resolve = _load_script("command_prefix").resolve
        self.assertEqual(
            resolve("name: @KIT_NAME_PREFIX@git-start", sigil="$", namespace="kit-ai:", name_prefix="kit-ai:"),
            "name: kit-ai:git-start",
        )
        self.assertEqual(
            resolve("name: @KIT_NAME_PREFIX@git-start", sigil="/", namespace="", name_prefix=""),
            "name: git-start",
        )

    def test_no_placeholder_survives(self) -> None:
        resolve = _load_script("command_prefix").resolve
        out = resolve("@KIT_CMD_PREFIX@git-start @KIT_NAME_PREFIX@git-start", sigil="/", namespace="", name_prefix="")
        self.assertNotIn("@KIT_", out)


class TestStdlibReaderAgreesWithManifest(unittest.TestCase):
    """Skrypt bash-owy czyta te same wartości co ``load_manifest``."""

    def test_reader_returns_same_values_as_load_manifest(self) -> None:
        module = _load_script("command_prefix")
        manifest = load_manifest(KIT_ROOT)
        for target in TARGETS:
            expected = manifest.command_prefix(target)
            got = module.read_values(KIT_ROOT / "manifest.yaml", target)
            self.assertEqual(got, (expected.sigil, expected.namespace, expected.name_prefix), target)

    def test_duplicate_target_entry_last_wins_in_both_readers(self) -> None:
        text = (KIT_ROOT / "manifest.yaml").read_text(encoding="utf-8")
        text += '  claude: {sigil: "$", namespace: "kit-ai:", name_prefix: "kit-ai:"}\n'
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.yaml"
            manifest_path.write_text(text, encoding="utf-8")
            stdlib = _load_script("command_prefix").read_values(manifest_path, "claude")
            yaml_prefix = load_manifest(Path(tmp)).command_prefix("claude")
        self.assertEqual(stdlib, (yaml_prefix.sigil, yaml_prefix.namespace, yaml_prefix.name_prefix))
        self.assertEqual(stdlib, ("$", "kit-ai:", "kit-ai:"))


class TestCopyTemplate(unittest.TestCase):
    """Kopia szablonu zastępuje placeholdery i zachowuje bit wykonania."""

    def test_copy_resolves_placeholders_and_keeps_exec_bit(self) -> None:
        module = _load_script("command_prefix")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.sh"
            src.write_text("echo @KIT_CMD_PREFIX@git-start\n", encoding="utf-8")
            src.chmod(0o755)
            dest = Path(tmp) / "out" / "dest.sh"
            module.copy_template(KIT_ROOT / "manifest.yaml", "shared", src, dest)
            self.assertEqual(dest.read_text(encoding="utf-8"), "echo /git-start\n")
            self.assertTrue(dest.stat().st_mode & stat.S_IXUSR)


class TestRenderAgentCommands(unittest.TestCase):
    """Renderer formatów vscode/kilo/opencode rozwiązuje placeholdery."""

    def test_rendered_commands_resolve_placeholders(self) -> None:
        module = _load_script("render_agent_commands")
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "src"
            src_dir.mkdir()
            (src_dir / "git-start.md").write_text(
                "---\nname: @KIT_NAME_PREFIX@git-start\ndescription: Start\n---\n\n"
                "Uruchom @KIT_CMD_PREFIX@git-start\n",
                encoding="utf-8",
            )
            dest_dir = Path(tmp) / "dest"
            rc = module.main(["render_agent_commands.py", "opencode", str(src_dir), str(dest_dir)])
            self.assertEqual(rc, 0)
            out = (dest_dir / "git-start.md").read_text(encoding="utf-8")
            self.assertIn("Uruchom /git-start", out)
            self.assertNotIn("@KIT_", out)


class TestBootstrapWiring(unittest.TestCase):
    """Seam 1: bootstrap w tymczasowym workspace."""

    def test_shared_copy_resolves_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kit = root / "kit"
            _copy_kit(kit)
            t3 = kit / "templates" / "shared" / "night-run" / "t3.md"
            t3.write_text(t3.read_text(encoding="utf-8") + "\nTest: @KIT_CMD_PREFIX@git-start\n", encoding="utf-8")
            workspace = _init_workspace(root / "ws")
            result = _run_bootstrap(kit, workspace, root / "config")
            self.assertEqual(result.returncode, 0, result.stderr)
            out = (workspace / ".ai" / "night-run-t3.md").read_text(encoding="utf-8")
            self.assertIn("Test: /git-start", out)
            self.assertNotIn("@KIT_", out)

    def test_real_kit_install_leaves_no_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = _init_workspace(root / "ws")
            result = _run_bootstrap(KIT_ROOT, workspace, root / "config")
            self.assertEqual(result.returncode, 0, result.stderr)
            leftovers = [
                path
                for path in workspace.rglob("*")
                if path.is_file() and ".git" not in path.parts and any(p in path.read_bytes() for p in PLACEHOLDERS)
            ]
            self.assertEqual(leftovers, [])
