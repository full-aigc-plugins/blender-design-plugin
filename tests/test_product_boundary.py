import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestProductBoundary(unittest.TestCase):
    def test_distribution_has_no_vendored_jimeng_runtime(self):
        self.assertFalse((ROOT / "vendor" / "jimeng_blender_uploader").exists())

    def test_no_runtime_skill_claims_dreamina_or_jimeng(self):
        for path in (ROOT / "skills").glob("*/SKILL.md"):
            text = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("jimeng", text, path)
            self.assertNotIn("dreamina", text, path)

    def test_manifest_is_blender_only(self):
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
        text = json.dumps(manifest).lower()
        self.assertNotIn("jimeng", text)
        self.assertNotIn("dreamina", text)


if __name__ == "__main__":
    unittest.main()
