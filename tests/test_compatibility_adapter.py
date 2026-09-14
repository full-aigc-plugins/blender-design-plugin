"""Tests for the Blender version compatibility adapter layer.

These tests use synthetic RuntimeIdentity values and fake bpy surfaces.
The v4.x/v50_v51 adapters cannot be exercised against real Blender here
because only Blender 5.2.1 is installed.
"""
import unittest

from scripts.harness.compat.base import RuntimeIdentity
from scripts.harness.compat.selector import select_adapter
from scripts.harness.errors import HarnessError


def _identity(major, minor, patch=0):
    return RuntimeIdentity(
        blender_version=(major, minor, patch),
        platform='Darwin',
        architecture='arm64',
        runtime_mode='managed',
    )


class TestAdapterSelection(unittest.TestCase):
    """select_adapter must return distinct adapter classes for version boundaries."""

    def test_v42_returns_adapter(self):
        proxy = select_adapter(_identity(4, 2, 23))
        self.assertIsNotNone(proxy)

    def test_v43_returns_adapter(self):
        proxy = select_adapter(_identity(4, 3, 2))
        self.assertIsNotNone(proxy)

    def test_v44_returns_adapter(self):
        proxy = select_adapter(_identity(4, 4, 3))
        self.assertIsNotNone(proxy)

    def test_v45_returns_adapter(self):
        proxy = select_adapter(_identity(4, 5, 13))
        self.assertIsNotNone(proxy)

    def test_v50_returns_adapter(self):
        proxy = select_adapter(_identity(5, 0, 1))
        self.assertIsNotNone(proxy)

    def test_v51_returns_adapter(self):
        proxy = select_adapter(_identity(5, 1, 2))
        self.assertIsNotNone(proxy)

    def test_v52_returns_adapter(self):
        proxy = select_adapter(_identity(5, 2, 1))
        self.assertIsNotNone(proxy)

    def test_v42_and_v45_differ(self):
        a42 = select_adapter(_identity(4, 2, 23))
        a45 = select_adapter(_identity(4, 5, 13))
        self.assertIsNot(a42.adapter_class, a45.adapter_class)

    def test_v45_and_v52_differ(self):
        a45 = select_adapter(_identity(4, 5, 13))
        a52 = select_adapter(_identity(5, 2, 1))
        self.assertIsNot(a45.adapter_class, a52.adapter_class)

    def test_v42_and_v52_differ(self):
        a42 = select_adapter(_identity(4, 2, 23))
        a52 = select_adapter(_identity(5, 2, 1))
        self.assertIsNot(a42.adapter_class, a52.adapter_class)

    def test_v43_and_v44_share_adapter(self):
        a43 = select_adapter(_identity(4, 3, 2))
        a44 = select_adapter(_identity(4, 4, 3))
        self.assertIs(a43.adapter_class, a44.adapter_class)

    def test_v50_and_v51_share_adapter(self):
        a50 = select_adapter(_identity(5, 0, 1))
        a51 = select_adapter(_identity(5, 1, 2))
        self.assertIs(a50.adapter_class, a51.adapter_class)


class TestOutOfRangeVersions(unittest.TestCase):
    """Out-of-range versions must be rejected, not silently defaulted."""

    def test_v36_rejected(self):
        with self.assertRaises(HarnessError) as ctx:
            select_adapter(_identity(3, 6, 0))
        self.assertEqual(ctx.exception.code, 'CAPABILITY_UNAVAILABLE')

    def test_v60_rejected(self):
        with self.assertRaises(HarnessError) as ctx:
            select_adapter(_identity(6, 0, 0))
        self.assertEqual(ctx.exception.code, 'CAPABILITY_UNAVAILABLE')

    def test_v41_rejected(self):
        with self.assertRaises(HarnessError) as ctx:
            select_adapter(_identity(4, 1, 0))
        self.assertEqual(ctx.exception.code, 'CAPABILITY_UNAVAILABLE')

    def test_v53_rejected(self):
        with self.assertRaises(HarnessError) as ctx:
            select_adapter(_identity(5, 3, 0))
        self.assertEqual(ctx.exception.code, 'CAPABILITY_UNAVAILABLE')


class TestAdapterMethodPresence(unittest.TestCase):
    """Every adapter must expose all ten required methods."""

    REQUIRED_METHODS = [
        'create_compositor_tree',
        'configure_file_output',
        'create_sequence_strip',
        'create_sequence_effect',
        'configure_geometry_node_interface',
        'create_grease_pencil_data',
        'configure_hair_curves',
        'enable_rigify',
        'configure_render_engine',
        'export_asset',
    ]

    def _fake_bpy(self):
        class FakeOps:
            class pose:
                pass
            class object:
                pass
        class FakeBpy:
            ops = FakeOps()
            data = type('Data', (), {'objects': {}, 'node_groups': {}})()
            context = type('Ctx', (), {
                'scene': type('Scene', (), {})(),
                'preferences': type('Prefs', (), {'addons': {}})(),
            })()
            app = type('App', (), {'version_string': '0.0.0'})()
        return FakeBpy()

    def test_v42_has_all_methods(self):
        proxy = select_adapter(_identity(4, 2, 23))
        adapter = proxy.bind(self._fake_bpy())
        for method in self.REQUIRED_METHODS:
            self.assertTrue(hasattr(adapter, method), f'v42 missing {method}')
            self.assertTrue(callable(getattr(adapter, method)), f'v42.{method} not callable')

    def test_v45_has_all_methods(self):
        proxy = select_adapter(_identity(4, 5, 13))
        adapter = proxy.bind(self._fake_bpy())
        for method in self.REQUIRED_METHODS:
            self.assertTrue(hasattr(adapter, method), f'v45 missing {method}')

    def test_v52_has_all_methods(self):
        proxy = select_adapter(_identity(5, 2, 1))
        adapter = proxy.bind(self._fake_bpy())
        for method in self.REQUIRED_METHODS:
            self.assertTrue(hasattr(adapter, method), f'v52 missing {method}')


class TestCapCapabilityUnavailable(unittest.TestCase):
    """Unknown socket, node, or operator must return CAPABILITY_UNAVAILABLE."""

    def test_base_default_raises_capability_unavailable(self):
        """Methods not overridden by a version adapter raise CAPABILITY_UNAVAILABLE."""
        from scripts.harness.compat.base import BlenderCompatibilityAdapter
        class FakeBpy:
            pass
        adapter = BlenderCompatibilityAdapter(FakeBpy())
        for method_name in [
            'create_sequence_strip',
            'create_sequence_effect',
            'configure_hair_curves',
            'export_asset',
        ]:
            method = getattr(adapter, method_name)
            with self.subTest(method=method_name):
                with self.assertRaises(HarnessError) as ctx:
                    if method_name == 'create_sequence_strip':
                        method(None, None, None, None, None)
                    elif method_name == 'create_sequence_effect':
                        method(None, None, None, None, None, None)
                    elif method_name == 'configure_hair_curves':
                        method(None, None, None)
                    elif method_name == 'export_asset':
                        method(None, None, None)
                self.assertEqual(ctx.exception.code, 'CAPABILITY_UNAVAILABLE')


class TestRuntimeIdentityReExport(unittest.TestCase):
    """RuntimeIdentity must be importable from compat.base and be the same class."""

    def test_import_from_compat_base(self):
        from scripts.harness.compat.base import RuntimeIdentity as CompatRI
        from scripts.harness.production_profile import RuntimeIdentity as ProfileRI
        self.assertIs(CompatRI, ProfileRI)

    def test_identity_fields(self):
        ri = _identity(5, 2, 1)
        self.assertEqual(ri.blender_version, (5, 2, 1))
        self.assertEqual(ri.platform, 'Darwin')
        self.assertEqual(ri.architecture, 'arm64')
        self.assertEqual(ri.runtime_mode, 'managed')


if __name__ == '__main__':
    unittest.main()
