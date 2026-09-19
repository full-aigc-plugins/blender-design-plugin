import hashlib
import unittest

from scripts.check_harness_drift import _feed, validate


class HarnessBoundaryTests(unittest.TestCase):
    def test_tree_digest_ignores_checkout_line_endings(self):
        lf = hashlib.sha256()
        crlf = hashlib.sha256()
        _feed(lf, "runtime.py", b"first\nsecond\n")
        _feed(crlf, "runtime.py", b"first\r\nsecond\r\n")
        self.assertEqual(lf.hexdigest(), crlf.hexdigest())

    def test_retained_compatibility_tree_and_locked_runtime_are_pinned(self):
        self.assertEqual(validate(), [])


if __name__ == "__main__":
    unittest.main()
