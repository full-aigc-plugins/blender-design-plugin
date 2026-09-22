import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestProductBoundary(unittest.TestCase):
    def test_distribution_has_no_vendored_jimeng_runtime(self):
        legacy_root = ROOT / "vendor" / "jimeng_blender_uploader"
        self.assertFalse((legacy_root / "UPSTREAM.md").exists())
        self.assertFalse((legacy_root / "upload_bridge.py").exists())

    def test_only_official_handoff_skill_names_jimeng_and_never_claims_generation(self):
        for path in (ROOT / "skills").glob("*/SKILL.md"):
            text = path.read_text(encoding="utf-8").lower()
            if path.parent.name == "blender-to-dreamina":
                self.assertIn("jimenglinkready", text, path)
                self.assertIn("does not mean seedance completed", text, path)
            elif path.parent.name == "blender-use":
                self.assertIn("jimeng_web", text, path)
                self.assertIn("jimenglinkready", text, path)
            else:
                self.assertNotIn("jimeng", text, path)

    def test_manifest_is_blender_only(self):
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
        text = json.dumps(manifest).lower()
        self.assertNotIn("jimeng", text)
        self.assertNotIn("dreamina", text)

    def test_router_exposes_three_explicit_delivery_choices(self):
        text = (ROOT / "skills" / "blender-use" / "SKILL.md").read_text(encoding="utf-8")
        for route in ("preview_only", "jimeng_web", "downstream_seedance"):
            self.assertIn(route, text)

    def test_user_guide_defines_missing_asset_and_handoff_decisions(self):
        guide = (ROOT / "docs" / "getting-started.zh-CN.md").read_text(encoding="utf-8")
        self.assertIn("素材就绪检查", guide)
        self.assertIn("要求你补充素材", guide)
        self.assertIn("白模交付清单", guide)
        self.assertIn("codex-dreamina-3d-plugin", guide)


if __name__ == "__main__":
    unittest.main()
