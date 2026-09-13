import tempfile
import unittest
from pathlib import Path

from scripts.harness.milestone import build_milestone_receipt, view_positions


class TestMilestone(unittest.TestCase):
    def test_view_positions_surround_bounds(self):
        views = view_positions((-1, -2, -1), (3, 2, 5))
        self.assertEqual(set(views), {"front", "side", "top"})
        self.assertLess(views["front"][1], -2)
        self.assertGreater(views["side"][0], 3)
        self.assertGreater(views["top"][2], 5)

    def test_receipt_hashes_fresh_views(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {}
            for name in ("camera", "front", "side", "top"):
                path = root / f"{name}.png"
                path.write_bytes(name.encode())
                paths[name] = path
            receipt = build_milestone_receipt(
                "modeling",
                scene_revision=4,
                snapshot_id="snapshot-4",
                view_paths=paths,
                scene_summary={"objects": 1, "materials": 1, "lights": 1, "cameras": 1},
            )
            self.assertEqual(len(receipt["views"]), 4)
            self.assertTrue(all(len(view["sha256"]) == 64 for view in receipt["views"]))

    def test_animation_receipt_keeps_sample_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ("camera", "front", "side", "top", "first", "middle", "last")
            paths = {}
            for name in names:
                path = root / f"{name}.png"
                path.write_bytes(name.encode())
                paths[name] = path
            receipt = build_milestone_receipt(
                "animation", scene_revision=5, snapshot_id="snap-5", view_paths=paths,
                scene_summary={"objects": 1, "materials": 0, "lights": 0, "cameras": 1},
            )
            self.assertEqual([view["name"] for view in receipt["views"][-3:]], ["first", "middle", "last"])


if __name__ == "__main__":
    unittest.main()
