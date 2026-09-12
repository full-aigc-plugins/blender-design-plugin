"""Tests for the distribution validator.

The validator implements Codex's own plugin manifest rules (see the module
docstring of scripts/validate_distribution.py). The negative tests matter most:
they prove the validator actually rejects the defects it claims to check.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
_REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from validate_distribution import main as validate_main, validate_segment


def _run_validator(root):
    """Run the validator in-process against `root`; return its exit code."""
    return validate_main(root)


class TestSegmentRule(unittest.TestCase):
    """Mirrors validate_plugin_segment() from codex-rs."""

    def test_accepts_kebab_case(self):
        self.assertIsNone(validate_segment("codex-blender", "plugin name"))

    def test_accepts_digits_and_underscore(self):
        self.assertIsNone(validate_segment("plugin_2", "plugin name"))

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


class TestCurrentTreePasses(unittest.TestCase):
    def test_validator_passes_on_current_tree(self):
        result = subprocess.run(
            [sys.executable, os.path.join(_SCRIPTS_DIR, "validate_distribution.py")],
            capture_output=True, text=True, cwd=_REPO_ROOT,
        )
        self.assertEqual(result.returncode, 0,
                         f"Validator failed:\n{result.stdout}\n{result.stderr}")
        self.assertIn("passed", result.stdout.lower())

    def test_manifest_declares_required_and_no_meaningless_fields(self):
        """Codex tolerates extra keys, but `id`/`entryPoint` are not conventions here.

        `RawPluginManifest` has no `deny_unknown_fields`, so `author`, `license`,
        `repository` and `homepage` are accepted and ignored — conventional
        metadata rather than errors. The hard rules are the name segment and the
        skills path syntax.
        """
        with open(os.path.join(_REPO_ROOT, ".codex-plugin", "plugin.json")) as f:
            plugin = json.load(f)
        for field in ("name", "version", "description", "skills"):
            self.assertIn(field, plugin)
        for meaningless in ("id", "entryPoint"):
            self.assertNotIn(meaningless, plugin,
                             f"{meaningless} is neither a manifest field nor a convention")

    def test_display_name_lives_in_interface(self):
        with open(os.path.join(_REPO_ROOT, ".codex-plugin", "plugin.json")) as f:
            plugin = json.load(f)
        self.assertEqual(plugin["interface"]["displayName"], "Codex Blender")
        self.assertNotIn(" ", plugin["name"])

    def test_marketplace_declares_plugins_array(self):
        with open(os.path.join(_REPO_ROOT, ".agents", "plugins", "marketplace.json")) as f:
            marketplace = json.load(f)
        self.assertIn("plugins", marketplace)
        self.assertTrue(marketplace["plugins"])
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["source"]["source"], "local")
        self.assertIn("path", entry["source"])

    def test_four_skills_exist(self):
        for skill in ("codex-blender-use", "codex-blender-inspect",
                      "codex-blender-export-preview", "codex-blender-link"):
            self.assertTrue(
                os.path.isfile(os.path.join(_REPO_ROOT, "skills", skill, "SKILL.md")),
                f"Missing Skill: {skill}",
            )

    def test_upstream_md_records_every_vendored_module(self):
        path = os.path.join(_REPO_ROOT, "vendor", "jimeng_blender_uploader", "UPSTREAM.md")
        with open(path) as f:
            content = f.read()
        for name in ("dcc_config.py", "upload_bridge.py", "settings.py", "variant.py",
                     "viewport_render.py", "operators.py", "panel.py", "state.py",
                     "__init__.py"):
            self.assertIn(name, content, f"UPSTREAM.md missing record for {name}")


class TestValidatorRejectsDefects(unittest.TestCase):
    """Each case corrupts a copy of the repo and asserts the validator fails."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = os.path.join(self._tmp.name, "repo")
        shutil.copytree(
            _REPO_ROOT, self.repo,
            ignore=shutil.ignore_patterns(".git", ".superpowers", "__pycache__"),
        )
        self.manifest = os.path.join(self.repo, ".codex-plugin", "plugin.json")
        self.marketplace = os.path.join(self.repo, ".agents", "plugins", "marketplace.json")
        self.addCleanup(self._restore)

    def _restore(self):
        # setUp's cleanup removes the whole copy; nothing else to do.
        pass

    def _mutate(self, path, mutate):
        with open(path) as f:
            data = json.load(f)
        mutate(data)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def test_rejects_name_with_space(self):
        self._mutate(self.manifest, lambda d: d.update(name="Codex Blender"))
        self.assertNotEqual(_run_validator(self.repo), 0)

    def test_rejects_missing_skills_field(self):
        self._mutate(self.manifest, lambda d: d.pop("skills"))
        self.assertNotEqual(_run_validator(self.repo), 0)

    def test_rejects_skills_path_without_dot_slash(self):
        self._mutate(self.manifest, lambda d: d.update(skills="skills/"))
        self.assertNotEqual(_run_validator(self.repo), 0)

    def test_rejects_skills_path_with_parent_escape(self):
        self._mutate(self.manifest, lambda d: d.update(skills="./../skills/"))
        self.assertNotEqual(_run_validator(self.repo), 0)

    def test_rejects_missing_marketplace_plugins_array(self):
        self._mutate(self.marketplace, lambda d: d.pop("plugins"))
        self.assertNotEqual(_run_validator(self.repo), 0)

    def test_rejects_marketplace_plugin_name_mismatch(self):
        def mutate(data):
            data["plugins"][0]["name"] = "something-else"
        self._mutate(self.marketplace, mutate)
        self.assertNotEqual(_run_validator(self.repo), 0)

    def test_rejects_marketplace_entry_without_source(self):
        self._mutate(self.marketplace, lambda d: d["plugins"][0].pop("source"))
        self.assertNotEqual(_run_validator(self.repo), 0)

    def test_rejects_skill_name_not_matching_directory(self):
        src = os.path.join(self.repo, "skills", "codex-blender-use")
        dst = os.path.join(self.repo, "skills", "mismatched-name")
        shutil.copytree(src, dst)
        self.assertNotEqual(_run_validator(self.repo), 0)

    def test_rejects_skill_without_frontmatter(self):
        skill_md = os.path.join(self.repo, "skills", "codex-blender-use", "SKILL.md")
        with open(skill_md, "w") as f:
            f.write("# no frontmatter here\n")
        self.assertNotEqual(_run_validator(self.repo), 0)

    def test_rejects_symlink_in_tree(self):
        os.symlink(os.path.join(self.repo, "README.md"),
                   os.path.join(self.repo, "link.md"))
        self.assertNotEqual(_run_validator(self.repo), 0)


if __name__ == "__main__":
    unittest.main()
