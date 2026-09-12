"""Tests for the vendored jimeng_blender_uploader headless core.

Covers:
  - UPSTREAM.md records every upstream SHA-256 (all vendored files)
  - Each vendored file hashes to its recorded value (anti-drift guard)
  - The package legitimately requires bpy (it is the real add-on)
  - The whole add-on imports against a bpy stub (the headless premise)
  - Four modules deliberately stay bpy-free
"""

import hashlib
import os
import re
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

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
    """The vendored package is the real add-on: it needs bpy, and it must load
    cleanly once a bpy stub is present — which is how the headless driver runs."""

    _MODULES = [
        "vendor.jimeng_blender_uploader.__init__".replace(".__init__", ""),
        "vendor.jimeng_blender_uploader.dcc_config",
        "vendor.jimeng_blender_uploader.operators",
        "vendor.jimeng_blender_uploader.panel",
        "vendor.jimeng_blender_uploader.settings",
        "vendor.jimeng_blender_uploader.state",
        "vendor.jimeng_blender_uploader.upload_bridge",
        "vendor.jimeng_blender_uploader.variant",
        "vendor.jimeng_blender_uploader.viewport_render",
    ]

    def _run_child(self, script):
        return subprocess.run(
            [sys.executable, "-c", textwrap.dedent(script)],
            capture_output=True, text=True,
            env={**os.environ, "_REPO_ROOT": _REPO_ROOT},
        )

    def test_package_requires_bpy(self):
        """With bpy unavailable the add-on must fail to import.

        This proves we vendored the real add-on rather than a stripped copy:
        if the package imported without bpy, its operator logic would have had
        to be rewritten — which is exactly what this repository must not do.
        """
        script = """\
            import os, sys
            class _Blocker:
                def find_spec(self, name, path, target=None):
                    if name == 'bpy' or name.startswith('bpy.'):
                        from importlib.machinery import ModuleSpec
                        return ModuleSpec(name, self)
                    return None
                def create_module(self, spec):
                    return None
                def exec_module(self, module):
                    raise ImportError('bpy blocked for test')
            sys.meta_path.insert(0, _Blocker())
            if os.environ['_REPO_ROOT'] not in sys.path:
                sys.path.insert(0, os.environ['_REPO_ROOT'])
            try:
                import vendor.jimeng_blender_uploader  # noqa: F401
            except ImportError:
                print('OK'); sys.exit(0)
            print('FAIL: package imported without bpy', file=sys.stderr); sys.exit(1)
        """
        result = self._run_child(script)
        self.assertEqual(result.returncode, 0,
                         f"stdout:{result.stdout} stderr:{result.stderr}")
        self.assertIn("OK", result.stdout)

    def test_all_modules_import_with_stub_bpy(self):
        """With a bpy stub present the whole add-on imports — the headless premise."""
        script = """\
            import importlib, os, sys, types
            if os.environ['_REPO_ROOT'] not in sys.path:
                sys.path.insert(0, os.environ['_REPO_ROOT'])

            class _Prop:
                def __init__(self, **kw):
                    self.kw = kw
            props = types.SimpleNamespace(
                EnumProperty=_Prop, StringProperty=_Prop, PointerProperty=_Prop,
                IntProperty=_Prop, BoolProperty=_Prop,
            )
            types_ns = types.SimpleNamespace(
                Scene=type('Scene', (), {}),
                Operator=type('Operator', (), {}),
                Panel=type('Panel', (), {}),
                Object=type('Object', (), {}),
            )
            utils = types.SimpleNamespace(register_class=lambda c: None,
                                          unregister_class=lambda c: None)
            handlers = types.ModuleType('bpy.app.handlers')
            handlers.persistent = lambda fn: fn
            handlers.load_post = []
            app = types.ModuleType('bpy.app')
            app.handlers = handlers
            app.timers = types.SimpleNamespace(is_registered=lambda cb: False,
                                               register=lambda cb, **kw: None)
            bpy = types.ModuleType('bpy')
            bpy.__path__ = []
            bpy.props, bpy.types, bpy.utils, bpy.app = props, types_ns, utils, app
            sys.modules.update({'bpy': bpy, 'bpy.app': app, 'bpy.app.handlers': handlers})

            for mod in %r:
                try:
                    importlib.import_module(mod)
                except Exception as exc:
                    print(f"FAIL: {mod}: {exc}", file=sys.stderr); sys.exit(1)
            print('OK')
        """ % (self._MODULES,)
        result = self._run_child(script)
        self.assertEqual(result.returncode, 0,
                         f"stdout:{result.stdout} stderr:{result.stderr}")
        self.assertIn("OK", result.stdout)

    def test_bpy_free_modules_do_not_import_bpy(self):
        """Four vendored modules deliberately have no bpy dependency.

        They are the ones that are safe to exercise without Blender (protocol
        config, exec discovery, settings, the generated variant), so their
        bpy-freedom is worth keeping even though the package as a whole needs bpy.
        """
        vendor_dir = Path(_REPO_ROOT) / "vendor" / "jimeng_blender_uploader"
        for name in ("dcc_config.py", "upload_bridge.py", "settings.py", "variant.py"):
            source = (vendor_dir / name).read_text()
            self.assertNotIn("import bpy", source,
                             f"{name} unexpectedly imports bpy")


if __name__ == "__main__":
    unittest.main()
