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

PLUGIN_ID = "blender-design"
DISPLAY_NAME = "Blender Design"
REPOSITORY = "https://github.com/full-aigc-plugins/blender-design-plugin"
BRAND_COLOR = "#E87D0D"
EXPECTED_SKILLS = (
    "blender-use",
    "blender-inspect",
    "blender-managed",
    "blender-connector",
    "blender-design",
    "blender-preview",
    "blender-export",
    "blender-recover",
    "blender-to-dreamina",
    "blender-harness-driving",
    "blender-visual-loop",
    "blender-mcp-setup",
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
        self.assertRegex(manifest["version"], r"^0\.13\.0(?:\+codex\.[0-9A-Za-z.-]+)?$")
        self.assertEqual(manifest["repository"], REPOSITORY)
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["mcpServers"], "./.mcp.json")

    def test_native_mcp_uses_pinned_partme_stdio_adapter(self) -> None:
        config = load_json(".mcp.json")
        self.assertEqual(config, {"mcpServers": {"partme_blender": {
            "type": "stdio",
            "command": "python",
            "args": ["scripts/mcp_bootstrap.py"],
            "cwd": ".",
        }}})
        entrypoint = ROOT / "scripts" / "blender_mcp_server.py"
        self.assertTrue(entrypoint.is_file())
        self.assertIn("from scripts.partme_runtime import activate_runtime",
                      entrypoint.read_text(encoding="utf-8"))
        bootstrap = ROOT / "scripts" / "mcp_bootstrap.py"
        self.assertTrue(bootstrap.is_file())
        self.assertIn("os.execv", bootstrap.read_text(encoding="utf-8"))

    def test_zcode_mcp_bootstrap_is_zero_configuration(self) -> None:
        """Optional ZCode values must not become required template variables.

        ZCode resolves every ``${user_config.*}`` placeholder before launching
        the MCP process, even when the corresponding schema entry says
        ``required: false``.  Session descriptors and ffprobe already have
        runtime auto-discovery, so the portable manifest must launch the same
        bootstrap without unresolved user configuration.
        """
        manifest_path = ROOT / ".zcode-plugin" / "plugin.json"
        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_text)
        server = manifest["mcpServers"]["partme_blender"]
        self.assertEqual(server["command"], "python3")
        self.assertEqual(
            server["args"],
            ["${ZCODE_PLUGIN_ROOT}/scripts/mcp_bootstrap.py"],
        )
        self.assertNotIn("env", server)
        self.assertNotIn("userConfig", manifest)
        self.assertNotIn("${user_config.", manifest_text)

    def test_receipt_contracts_are_packaged_without_unsupported_manifest_fields(self) -> None:
        manifest = load_json(".codex-plugin/plugin.json")
        self.assertNotIn("receipt_contract_versions", manifest)
        for schema in ("artifact_receipt.schema.json", "milestone_receipt.schema.json",
                       "video_artifact_receipt.schema.json"):
            self.assertTrue((ROOT / "schemas" / schema).is_file(), schema)

    def test_preview_adapter_is_executable(self) -> None:
        adapter = ROOT / "bin" / "blender_adapter"
        self.assertTrue(adapter.is_file())
        self.assertTrue(os.access(adapter, os.X_OK))

    def test_preview_adapter_imports_the_published_implementation(self) -> None:
        adapter = (ROOT / "bin" / "blender_adapter").read_text(encoding="utf-8")
        self.assertIn("from dreamina_adapter import main", adapter)

    def test_name_is_a_codex_kebab_identifier(self) -> None:
        manifest = load_json(".codex-plugin/plugin.json")
        name = manifest["name"]
        self.assertRegex(name, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertIsNone(validate_segment(name, "plugin name"))

    def test_display_name_is_in_interface_not_name(self) -> None:
        manifest = load_json(".codex-plugin/plugin.json")
        self.assertEqual(manifest["interface"]["displayName"], DISPLAY_NAME)
        self.assertNotIn(" ", manifest["name"])

    def test_interface_branding_and_prompts(self) -> None:
        interface = load_json(".codex-plugin/plugin.json")["interface"]
        self.assertEqual(interface["brandColor"], BRAND_COLOR)
        self.assertEqual(interface["logo"], "./assets/official-logo.png")
        self.assertEqual(interface["logoDark"], "./assets/official-logo.png")
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
            {"source": "url", "url": REPOSITORY + ".git", "ref": "v0.13.0"},
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
        self.assertEqual(png_shape("assets/official-logo.png"), (1024, 1024, 6))
        self.assertEqual(png_shape("assets/composer-icon.png"), (256, 256, 6))
        self.assertEqual(png_shape("assets/getting-started/blender-preferences-menu.png")[:2], (610, 469))
        self.assertEqual(png_shape("assets/getting-started/blender-enable-mcp-addon.png")[:2], (840, 582))

    def test_third_party_notices_disclose_pinned_partme_runtime(self) -> None:
        text = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("PartMe Blender MCP 0.7.0-rc.1", text)
        self.assertIn("runtime.lock.json", text)
        self.assertNotIn("jimeng_blender_uploader", text)


class TestSegmentRule(unittest.TestCase):
    """Mirrors validate_plugin_segment() in codex-rs/plugin/src/plugin_id.rs."""

    def test_accepts_kebab_case(self):
        self.assertIsNone(validate_segment("blender-design", "plugin name"))

    def test_rejects_space(self):
        # The exact defect this project shipped: a display name in `name`.
        self.assertIsNotNone(validate_segment("Blender Design", "plugin name"))

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
        self._mutate(self.manifest, lambda d: d.update(name="Blender Design"))
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

    def test_rejects_wrong_mcp_configuration(self):
        self._mutate(self.manifest, lambda d: d.update(mcpServers="./missing.json"))
        self._rejects()

    def test_rejects_missing_partme_runtime_lock(self):
        (self.repo / "runtime.lock.json").unlink()
        self._rejects()

    def test_rejects_corrupt_pinned_partme_runtime(self):
        target = self.repo / "vendor/partme-blender-mcp-runtime-0.7.0-rc.1.zip"
        target.write_bytes(target.read_bytes() + b"corrupt")
        self._rejects()

    def test_rejects_unlocked_oversized_binary(self):
        target = self.repo / "vendor/unlocked-large.zip"
        target.write_bytes(b"x" * (1024 * 1024 + 1))
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
            self.repo / "skills" / "blender-use",
            self.repo / "skills" / "mismatched-name",
        )
        self._rejects()

    def test_rejects_skill_without_frontmatter(self):
        (self.repo / "skills" / "blender-use" / "SKILL.md").write_text(
            "# no frontmatter here\n", encoding="utf-8"
        )
        self._rejects()

    def test_rejects_missing_required_legal_file(self):
        (self.repo / "PRIVACY.md").unlink()
        self._rejects()

    def test_rejects_wrong_brand_asset_shape(self):
        (self.repo / "assets" / "official-logo.png").write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
        )
        self._rejects()

    def test_rejects_symlink_in_tree(self):
        os.symlink(self.repo / "README.md", self.repo / "link.md")
        self._rejects()

    def test_rejects_wrong_base_version(self):
        self._mutate(self.manifest, lambda d: d.update(version="0.2.0"))
        self._rejects()

    def test_accepts_cachebuster_build_suffix(self):
        """Local iteration requires 0.13.0+codex.<cachebuster>.

        Hard-pinning the version would reject the documented form, so this
        guards against reintroducing that pin.
        """
        self._mutate(
            self.manifest,
            lambda d: d.update(version="0.13.0+codex.local-20260921-120000"),
        )
        self.assertEqual(validate_main(str(self.repo)), 0)


if __name__ == "__main__":
    unittest.main()
