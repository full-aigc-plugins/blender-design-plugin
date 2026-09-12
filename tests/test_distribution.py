"""Tests for the distribution validator.

Two layers, both needed:

  - **Positive**: the committed distribution satisfies project policy AND the
    Codex manifest rules. Asserted against the real tree so a regression in
    either the manifests or the assets fails the suite.
  - **Negative**: a corrupted copy of the repository must be *rejected*. These
    are the tests that prove a check actually works — a validator that passes
    everything is indistinguishable from one that checks nothing.
"""

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from validate_distribution import main as validate_main, validate_segment

PLUGIN_ID = "codex-blender"
DISPLAY_NAME = "Codex Blender"
REPOSITORY = "https://github.com/partme-ai/codex-blender-plugin"
BRAND_COLOR = "#F97316"
EXPECTED_SKILLS = (
    "codex-blender-use",
    "codex-blender-inspect",
    "codex-blender-export-preview",
    "codex-blender-link",
)


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def png_shape(relative: str) -> tuple[int, int, int]:
    data = (ROOT / relative).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"not PNG: {relative}")
    width, height = struct.unpack(">II", data[16:24])
    return width, height, data[25]


class TestManifestAndMarketplace(unittest.TestCase):
    """Positive assertions on the committed manifests."""

    def test_validator_accepts_distribution(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_distribution.py"), str(ROOT)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_manifest_identity(self) -> None:
        manifest = load_json(".codex-plugin/plugin.json")
        self.assertEqual(manifest["name"], PLUGIN_ID)
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["repository"], REPOSITORY)
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertNotIn("mcpServers", manifest)

    def test_name_is_a_codex_kebab_identifier(self) -> None:
        manifest = load_json(".codex-plugin/plugin.json")
        name = manifest["name"]
        self.assertTrue(name.startswith("codex-"))
        self.assertRegex(name, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertIsNone(validate_segment(name, "plugin name"))

    def test_display_name_is_in_interface_not_name(self) -> None:
        manifest = load_json(".codex-plugin/plugin.json")
        self.assertEqual(manifest["interface"]["displayName"], DISPLAY_NAME)
        self.assertNotIn(" ", manifest["name"])

    def test_interface_branding_and_prompts(self) -> None:
        interface = load_json(".codex-plugin/plugin.json")["interface"]
        self.assertEqual(interface["brandColor"], BRAND_COLOR)
        self.assertEqual(interface["logo"], "./assets/logo.png")
        self.assertEqual(interface["logoDark"], "./assets/logo-dark.png")
        self.assertEqual(interface["composerIcon"], "./assets/composer-icon.png")
        prompts = interface["defaultPrompt"]
        self.assertTrue(1 <= len(prompts) <= 3)
        self.assertTrue(all(len(prompt) <= 128 for prompt in prompts))

    def test_manifest_has_no_meaningless_fields(self) -> None:
        """`id`/`entryPoint` are neither manifest fields nor local conventions."""
        manifest = load_json(".codex-plugin/plugin.json")
        for meaningless in ("id", "entryPoint"):
            self.assertNotIn(meaningless, manifest)

    def test_marketplace_pins_this_repository(self) -> None:
        marketplace = load_json(".agents/plugins/marketplace.json")
        entries = [e for e in marketplace["plugins"] if e["name"] == PLUGIN_ID]
        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0]["source"],
            {"source": "url", "url": REPOSITORY + ".git", "ref": "main"},
        )
        self.assertEqual(
            entries[0]["policy"],
            {"installation": "AVAILABLE", "authentication": "ON_USE"},
        )

    def test_skills_have_matching_frontmatter(self) -> None:
        for skill in EXPECTED_SKILLS:
            skill_md = ROOT / "skills" / skill / "SKILL.md"
            self.assertTrue(skill_md.is_file(), f"missing Skill: {skill}")
            text = skill_md.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---"), f"{skill} has no frontmatter")
            body = text[3:text.find("\n---", 3)]
            fields = dict(
                line.split(":", 1) for line in body.splitlines() if ":" in line
            )
            self.assertEqual(fields["name"].strip().strip("\"'"), skill)
            self.assertTrue(fields.get("description", "").strip())


class TestStructureLegalAndAssets(unittest.TestCase):
    def test_required_directories(self) -> None:
        for directory in ("assets", "skills", "schemas", "scripts", "tests"):
            self.assertTrue((ROOT / directory).is_dir(), directory)

    def test_required_legal_files(self) -> None:
        for filename in ("LICENSE", "NOTICE", "PRIVACY.md", "TERMS.md",
                         "THIRD_PARTY_NOTICES.md", ".gitignore",
                         "docs/portable-migration.md"):
            self.assertTrue((ROOT / filename).is_file(), filename)

    def test_portable_manifests_are_inactive(self) -> None:
        self.assertFalse((ROOT / "plugin.json").exists())
        self.assertFalse((ROOT / "mcp.json").exists())

    def test_brand_asset_shapes(self) -> None:
        self.assertEqual(png_shape("assets/logo.png"), (1024, 1024, 6))
        self.assertEqual(png_shape("assets/logo-dark.png"), (1024, 1024, 6))
        self.assertEqual(png_shape("assets/composer-icon.png"), (256, 256, 6))

    def test_third_party_notices_disclose_the_vendored_source(self) -> None:
        """The vendored add-on must be disclosed, not described as absent."""
        text = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("jimeng_blender_uploader", text)
        self.assertIn("UPSTREAM.md", text)
        self.assertIn("unresolved", text.lower())


class TestSegmentRule(unittest.TestCase):
    """Mirrors validate_plugin_segment() in codex-rs/plugin/src/plugin_id.rs."""

    def test_accepts_kebab_case(self):
        self.assertIsNone(validate_segment("codex-blender", "plugin name"))

    def test_rejects_space(self):
        # The exact defect this project shipped: a display name in `name`.
        self.assertIsNotNone(validate_segment("Codex Blender", "plugin name"))

    def test_rejects_empty(self):
        self.assertIsNotNone(validate_segment("", "plugin name"))

    def test_rejects_path_traversal(self):
        for value in (".", "..", ".hidden", "trailing.", "a..b"):
            self.assertIsNotNone(validate_segment(value, "plugin name"), value)

    def test_marketplace_name_rejects_dots(self):
        self.assertIsNotNone(validate_segment("a.b", "marketplace name"))


class TestValidatorRejectsDefects(unittest.TestCase):
    """Corrupt a copy of the repository; the validator must reject it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        shutil.copytree(
            ROOT, self.repo,
            ignore=shutil.ignore_patterns(".git", ".superpowers", "__pycache__"),
        )
        self.manifest = self.repo / ".codex-plugin" / "plugin.json"
        self.marketplace = self.repo / ".agents" / "plugins" / "marketplace.json"

    def _mutate(self, path, mutate):
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _rejects(self):
        self.assertNotEqual(validate_main(str(self.repo)), 0)

    def test_rejects_name_with_space(self):
        self._mutate(self.manifest, lambda d: d.update(name="Codex Blender"))
        self._rejects()

    def test_rejects_non_codex_prefixed_name(self):
        self._mutate(self.manifest, lambda d: d.update(name="blender"))
        self._rejects()

    def test_rejects_missing_skills_field(self):
        self._mutate(self.manifest, lambda d: d.pop("skills"))
        self._rejects()

    def test_rejects_skills_path_without_dot_slash(self):
        self._mutate(self.manifest, lambda d: d.update(skills="skills/"))
        self._rejects()

    def test_rejects_skills_path_with_parent_escape(self):
        self._mutate(self.manifest, lambda d: d.update(skills="./../skills/"))
        self._rejects()

    def test_rejects_too_many_default_prompts(self):
        def mutate(data):
            data["interface"]["defaultPrompt"] = ["a", "b", "c", "d"]
        self._mutate(self.manifest, mutate)
        self._rejects()

    def test_rejects_over_long_default_prompt(self):
        def mutate(data):
            data["interface"]["defaultPrompt"] = ["x" * 200]
        self._mutate(self.manifest, mutate)
        self._rejects()

    def test_rejects_mcp_servers_declared(self):
        self._mutate(self.manifest, lambda d: d.update(mcpServers={}))
        self._rejects()

    def test_rejects_inactive_portable_manifest_activated(self):
        (self.repo / "plugin.json").write_text("{}", encoding="utf-8")
        self._rejects()

    def test_rejects_missing_marketplace_plugins_array(self):
        self._mutate(self.marketplace, lambda d: d.pop("plugins"))
        self._rejects()

    def test_rejects_marketplace_plugin_name_mismatch(self):
        def mutate(data):
            data["plugins"][0]["name"] = "something-else"
        self._mutate(self.marketplace, mutate)
        self._rejects()

    def test_rejects_marketplace_entry_without_source(self):
        self._mutate(self.marketplace, lambda d: d["plugins"][0].pop("source"))
        self._rejects()

    def test_rejects_wrong_marketplace_source(self):
        def mutate(data):
            data["plugins"][0]["source"] = {"source": "url", "url": "https://example.com/x.git", "ref": "main"}
        self._mutate(self.marketplace, mutate)
        self._rejects()

    def test_rejects_skill_name_not_matching_directory(self):
        shutil.copytree(
            self.repo / "skills" / "codex-blender-use",
            self.repo / "skills" / "mismatched-name",
        )
        self._rejects()

    def test_rejects_skill_without_frontmatter(self):
        (self.repo / "skills" / "codex-blender-use" / "SKILL.md").write_text(
            "# no frontmatter here\n", encoding="utf-8"
        )
        self._rejects()

    def test_rejects_missing_required_legal_file(self):
        (self.repo / "PRIVACY.md").unlink()
        self._rejects()

    def test_rejects_wrong_brand_asset_shape(self):
        (self.repo / "assets" / "logo.png").write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
        )
        self._rejects()

    def test_rejects_symlink_in_tree(self):
        os.symlink(self.repo / "README.md", self.repo / "link.md")
        self._rejects()

    def test_rejects_missing_provenance_record(self):
        (self.repo / "vendor" / "jimeng_blender_uploader" / "UPSTREAM.md").unlink()
        self._rejects()


if __name__ == "__main__":
    unittest.main()
