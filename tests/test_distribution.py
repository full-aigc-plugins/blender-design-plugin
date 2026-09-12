"""Tests for the distribution validator."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
_REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
for _d in (_SCRIPTS_DIR, _REPO_ROOT):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from validate_distribution import main as validate_main


class TestDistributionValidator(unittest.TestCase):
    """Run the real validator against the actual repo structure."""

    def test_validator_passes_on_current_tree(self):
        """The distribution as committed must pass validation."""
        # Run in a subprocess so we get the real exit code
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(_SCRIPTS_DIR, "validate_distribution.py")],
            capture_output=True, text=True, cwd=_REPO_ROOT,
        )
        self.assertEqual(result.returncode, 0, f"Validator failed:\n{result.stdout}\n{result.stderr}")
        self.assertIn("passed", result.stdout.lower())

    def test_plugin_json_has_required_fields(self):
        plugin_path = os.path.join(_REPO_ROOT, ".codex-plugin", "plugin.json")
        with open(plugin_path) as f:
            plugin = json.load(f)
        for field in ("id", "version", "name", "description", "license", "skills", "entryPoint"):
            self.assertIn(field, plugin, f"plugin.json missing {field}")

    def test_plugin_json_has_repository(self):
        plugin_path = os.path.join(_REPO_ROOT, ".codex-plugin", "plugin.json")
        with open(plugin_path) as f:
            plugin = json.load(f)
        self.assertIn("repository", plugin)
        self.assertIn("github.com", plugin["repository"])

    def test_four_skills_exist(self):
        skills_dir = os.path.join(_REPO_ROOT, "skills")
        expected = [
            "codex-blender-use",
            "codex-blender-inspect",
            "codex-blender-export-preview",
            "codex-blender-link",
        ]
        for skill in expected:
            skill_path = os.path.join(skills_dir, skill, "SKILL.md")
            self.assertTrue(os.path.isfile(skill_path), f"Missing Skill: {skill}")

    def test_upstream_md_exists_and_records_hashes(self):
        upstream_path = os.path.join(_REPO_ROOT, "vendor", "jimeng_blender_uploader", "UPSTREAM.md")
        self.assertTrue(os.path.isfile(upstream_path))
        with open(upstream_path) as f:
            content = f.read()
        for name in ("dcc_config.py", "upload_bridge.py", "settings.py", "variant.py", "viewport_render.py"):
            self.assertIn(name, content, f"UPSTREAM.md missing record for {name}")

    def test_no_symlinks_in_tree(self):
        for root, dirs, files in os.walk(_REPO_ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", ".superpowers", "__pycache__")]
            for name in files + dirs:
                path = os.path.join(root, name)
                if os.path.islink(path):
                    rel = os.path.relpath(path, _REPO_ROOT)
                    self.fail(f"Symlink found: {rel}")

    def test_no_large_binaries(self):
        binary_exts = {".png", ".jpg", ".mp4", ".mov", ".exe", ".dll", ".so", ".dylib", ".bin", ".zip"}
        for root, dirs, files in os.walk(_REPO_ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", ".superpowers", "__pycache__")]
            for name in files:
                _, ext = os.path.splitext(name)
                if ext.lower() in binary_exts:
                    path = os.path.join(root, name)
                    size = os.path.getsize(path)
                    self.assertLessEqual(
                        size, 1024 * 1024,
                        f"Binary too large: {os.path.relpath(path, _REPO_ROOT)} ({size} bytes)"
                    )


if __name__ == "__main__":
    unittest.main()
