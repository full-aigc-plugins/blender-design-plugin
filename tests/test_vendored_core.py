"""Tests for the vendored jimeng_blender_uploader headless core.

Covers:
  - UPSTREAM.md records all five upstream SHA-256 values
  - Each vendored file hashes to its recorded value (anti-drift guard)
  - Four modules (dcc_config, upload_bridge, settings, variant) import
    in a child process where importing bpy raises ImportError
  - viewport_render imports against a stub bpy module (no real Blender)
"""

import hashlib
import os
import re
import subprocess
import sys
import textwrap
import unittest

# Ensure the repo root is importable so vendor.jimeng_blender_uploader resolves.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_VENDORED_DIR = os.path.join(_REPO_ROOT, "vendor", "jimeng_blender_uploader")
_UPSTREAM_MD = os.path.join(_VENDORED_DIR, "UPSTREAM.md")

# The five vendored files and their expected SHA-256 values.
_EXPECTED_HASHES = {
    "dcc_config.py": "d559a7d3202a0621bc986e3069f6069d3a2c400908377fc521b6a20f75663cc4",
    "upload_bridge.py": "714d34aa2426e8a2f2fba61cb3fca54cf4f60e6252e7e79079b4471c68593393",
    "settings.py": "69454485ff3db83acb05145899af166398a132927b96203565ff42f78b598db8",
    "variant.py": "3e6fa3b54953634ff44aa3df0f00774ab7279644d8b12c3d49d8c4e174c7fba3",
    "viewport_render.py": "b9f1e6fcecd1ca704262f407fb9854540b37f6aab28a2635f3f0c8567f5f252b",
}


def _sha256_of_file(path):
    """Return the hex SHA-256 digest of the file at *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_hashes_from_upstream_md():
    """Parse SHA-256 hash lines from UPSTREAM.md.

    Expected format (one per file):
        | `filename.py` | `<sha256hex>` |
    Returns dict {filename: sha256hex}.
    """
    with open(_UPSTREAM_MD, "r", encoding="utf-8") as f:
        text = f.read()
    pattern = re.compile(
        r"\|\s*`([^`]+\.py)`\s*\|\s*`([0-9a-f]{64})`\s*\|"
    )
    return {m.group(1): m.group(2) for m in pattern.finditer(text)}


class TestUpstreamProvenance(unittest.TestCase):
    """UPSTREAM.md must record all five SHA-256 values and they must match."""

    def test_upstream_md_exists(self):
        self.assertTrue(
            os.path.isfile(_UPSTREAM_MD),
            f"UPSTREAM.md not found at {_UPSTREAM_MD}",
        )

    def test_upstream_md_records_all_five_hashes(self):
        recorded = _parse_hashes_from_upstream_md()
        for filename in _EXPECTED_HASHES:
            self.assertIn(
                filename,
                recorded,
                f"{filename} hash not found in UPSTREAM.md",
            )

    def test_recorded_hashes_match_expected(self):
        recorded = _parse_hashes_from_upstream_md()
        for filename, expected in _EXPECTED_HASHES.items():
            self.assertEqual(
                recorded.get(filename),
                expected,
                f"UPSTREAM.md records wrong hash for {filename}",
            )

    def test_vendored_files_hash_to_recorded_values(self):
        """Anti-drift guard: each vendored file must hash to the value
        recorded in UPSTREAM.md.  A future edit to a vendored file must
        fail this test until someone deliberately updates UPSTREAM.md."""
        recorded = _parse_hashes_from_upstream_md()
        for filename, recorded_hash in recorded.items():
            filepath = os.path.join(_VENDORED_DIR, filename)
            self.assertTrue(
                os.path.isfile(filepath),
                f"Vendored file {filename} not found at {filepath}",
            )
            actual = _sha256_of_file(filepath)
            self.assertEqual(
                actual,
                recorded_hash,
                f"Hash mismatch for {filename}: "
                f"UPSTREAM.md says {recorded_hash}, file is {actual}",
            )


class TestHeadlessImportability(unittest.TestCase):
    """Prove the vendored package is importable without real Blender."""

    def test_four_modules_import_bpy_absent(self):
        """dcc_config, upload_bridge, settings, variant must import in a
        child process where ``import bpy`` raises ImportError."""
        script = textwrap.dedent("""\
            import importlib
            import sys
            import types

            # Insert a meta_path finder that blocks bpy.
            class _BpyBlocker:
                def find_spec(self, name, path, target=None):
                    if name == 'bpy' or name.startswith('bpy.'):
                        from importlib.machinery import ModuleSpec
                        return ModuleSpec(name, self)
                    return None
                def create_module(self, spec):
                    return None
                def exec_module(self, module):
                    raise ImportError(
                        f"No module named '{module.__name__}' (bpy blocked for headless test)"
                    )

            sys.meta_path.insert(0, _BpyBlocker())

            # Ensure repo root is importable.
            import os
            repo_root = os.environ['_REPO_ROOT']
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)

            modules = [
                'vendor.jimeng_blender_uploader.dcc_config',
                'vendor.jimeng_blender_uploader.upload_bridge',
                'vendor.jimeng_blender_uploader.settings',
                'vendor.jimeng_blender_uploader.variant',
            ]
            for mod_name in modules:
                try:
                    importlib.import_module(mod_name)
                except Exception as e:
                    print(f"FAIL: {mod_name}: {e}", file=sys.stderr)
                    sys.exit(1)
            print("OK")
        """)
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env={**os.environ, "_REPO_ROOT": _REPO_ROOT},
        )
        self.assertEqual(
            result.returncode, 0,
            f"Import failed:\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertIn("OK", result.stdout)

    def test_viewport_render_imports_with_stub_bpy(self):
        """viewport_render does ``import bpy`` at the top level but only
        uses it inside functions.  An empty module object suffices to
        make the import succeed."""
        script = textwrap.dedent("""\
            import importlib
            import sys
            import types
            import os

            repo_root = os.environ['_REPO_ROOT']
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)

            # Provide a stub bpy module so the top-level import succeeds.
            bpy_stub = types.ModuleType('bpy')
            sys.modules['bpy'] = bpy_stub

            try:
                importlib.import_module('vendor.jimeng_blender_uploader.viewport_render')
            except Exception as e:
                print(f"FAIL: {e}", file=sys.stderr)
                sys.exit(1)
            print("OK")
        """)
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env={**os.environ, "_REPO_ROOT": _REPO_ROOT},
        )
        self.assertEqual(
            result.returncode, 0,
            f"Import failed:\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
