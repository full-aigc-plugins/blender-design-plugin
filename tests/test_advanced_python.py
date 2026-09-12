import unittest
from types import SimpleNamespace

from scripts.harness.advanced_python import AdvancedPythonExecutor
from scripts.harness.errors import HarnessError


class TestAdvancedPythonExecutor(unittest.TestCase):
    def setUp(self):
        self.bpy = SimpleNamespace(context=SimpleNamespace(scene=SimpleNamespace(frame_start=1)))
        self.executor = AdvancedPythonExecutor(self.bpy)

    def test_executes_reviewed_script_and_returns_hash(self):
        result = self.executor.execute({"script": "bpy.context.scene.frame_start = 10"})
        self.assertEqual(self.bpy.context.scene.frame_start, 10)
        self.assertEqual(len(result["result"]["scriptSha256"]), 64)

    def test_rejects_import(self):
        with self.assertRaises(HarnessError) as caught:
            self.executor.execute({"script": "import os\nos.system('id')"})
        self.assertEqual(caught.exception.code, "PYTHON_POLICY_REJECTED")

    def test_rejects_dunder_access(self):
        with self.assertRaises(HarnessError):
            self.executor.execute({"script": "x = bpy.__class__"})

    def test_rejects_oversized_script(self):
        with self.assertRaises(HarnessError):
            self.executor.execute({"script": "x=1\n" * 20000})


if __name__ == "__main__":
    unittest.main()
