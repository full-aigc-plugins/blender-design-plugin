import tempfile
import unittest
from pathlib import Path

from scripts.harness.errors import HarnessError
from scripts.harness.path_policy import PathPolicy


class TestPathPolicy(unittest.TestCase):
    def test_accepts_file_under_approved_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "texture.png"
            file.write_bytes(b"png")
            self.assertEqual(PathPolicy([root]).require_file(file), file.resolve())

    def test_rejects_file_outside_roots(self):
        with tempfile.TemporaryDirectory() as approved, tempfile.TemporaryDirectory() as outside:
            file = Path(outside) / "texture.png"
            file.write_bytes(b"png")
            with self.assertRaises(HarnessError) as caught:
                PathPolicy([Path(approved)]).require_file(file)
            self.assertEqual(caught.exception.code, "ASSET_NOT_AUTHORIZED")

    def test_rejects_symlink_even_when_target_is_inside(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "texture.png"
            target.write_bytes(b"png")
            link = root / "link.png"
            link.symlink_to(target)
            with self.assertRaises(HarnessError):
                PathPolicy([root]).require_file(link)


if __name__ == "__main__":
    unittest.main()
