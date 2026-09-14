"""Unit tests for retopo commands (argument validation and registration)."""
import unittest
from types import SimpleNamespace

from scripts.harness.errors import HarnessError
from scripts.harness.runtime import build_registry
from tests.test_design_commands import FakeBpy, FakeObject, FakeObjects


class PropertyObject(FakeObject):
    def __init__(self, name, object_type='MESH'):
        super().__init__(name, object_type)
        self.properties = {}

    def get(self, key, default=None):
        return self.properties.get(key, default)

    def __setitem__(self, key, value):
        self.properties[key] = value


class RetopoRegistrationTests(unittest.TestCase):
    """All four retopo commands must be registered."""

    def test_retopo_commands_are_registered(self):
        registry = build_registry(FakeBpy())
        for cmd in ('retopo.setup_surface', 'retopo.project',
                    'retopo.transfer_layers', 'retopo.validate'):
            result = registry.dispatch('capability.describe', {'id': cmd})
            self.assertEqual(result['result']['id'], cmd)

    def test_retopo_domain_is_known(self):
        registry = build_registry(FakeBpy())
        result = registry.dispatch('capability.list', {'domain': 'retopo'})
        names = [item['id'] for item in result['result']['items']]
        self.assertIn('retopo.setup_surface', names)
        self.assertIn('retopo.project', names)
        self.assertIn('retopo.transfer_layers', names)
        self.assertIn('retopo.validate', names)


class SetupSurfaceArgumentTests(unittest.TestCase):
    def test_requires_sourceObjectId(self):
        registry = build_registry(FakeBpy())
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.setup_surface', {'targetName': 'T'})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_requires_targetName(self):
        bpy = FakeBpy()
        obj = PropertyObject('Source')
        bpy.data.objects['Source'] = obj
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.setup_surface', {'sourceObjectId': {'name': 'Source'}})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_rejects_invalid_symmetry(self):
        bpy = FakeBpy()
        obj = PropertyObject('Source')
        bpy.data.objects['Source'] = obj
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.setup_surface', {
                'sourceObjectId': {'name': 'Source'}, 'targetName': 'T', 'symmetry': 'w'})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')


class ProjectArgumentTests(unittest.TestCase):
    def test_requires_objectId(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        bpy.data.objects['Source'] = src
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.project', {'sourceObjectId': {'name': 'Source'}})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_requires_sourceObjectId(self):
        bpy = FakeBpy()
        tgt = PropertyObject('Target')
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.project', {'objectId': {'name': 'Target'}})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_rejects_invalid_method(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        tgt = PropertyObject('Target')
        bpy.data.objects['Source'] = src
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.project', {
                'objectId': {'name': 'Target'}, 'sourceObjectId': {'name': 'Source'},
                'method': 'invalid'})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')


class TransferLayersArgumentTests(unittest.TestCase):
    def test_requires_layers(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        tgt = PropertyObject('Target')
        bpy.data.objects['Source'] = src
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.transfer_layers', {
                'sourceObjectId': {'name': 'Source'},
                'targetObjectId': {'name': 'Target'}})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_rejects_empty_layers(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        tgt = PropertyObject('Target')
        bpy.data.objects['Source'] = src
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.transfer_layers', {
                'sourceObjectId': {'name': 'Source'},
                'targetObjectId': {'name': 'Target'}, 'layers': []})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_rejects_non_string_layers(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        tgt = PropertyObject('Target')
        bpy.data.objects['Source'] = src
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.transfer_layers', {
                'sourceObjectId': {'name': 'Source'},
                'targetObjectId': {'name': 'Target'}, 'layers': [123]})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')


class ValidateArgumentTests(unittest.TestCase):
    def test_requires_objectId(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        bpy.data.objects['Source'] = src
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.validate', {'sourceObjectId': {'name': 'Source'}})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_requires_sourceObjectId(self):
        bpy = FakeBpy()
        tgt = PropertyObject('Target')
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.validate', {'objectId': {'name': 'Target'}})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_rejects_invalid_maxPoleValence(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        tgt = PropertyObject('Target')
        bpy.data.objects['Source'] = src
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.validate', {
                'objectId': {'name': 'Target'},
                'sourceObjectId': {'name': 'Source'}, 'maxPoleValence': 2})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_rejects_non_integer_maxPoleValence(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        tgt = PropertyObject('Target')
        bpy.data.objects['Source'] = src
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.validate', {
                'objectId': {'name': 'Target'},
                'sourceObjectId': {'name': 'Source'}, 'maxPoleValence': 4.5})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_risk_is_read(self):
        registry = build_registry(FakeBpy())
        caps = registry.capabilities()
        validate_cap = next(c for c in caps if c['command'] == 'retopo.validate')
        self.assertEqual(validate_cap['risk'], 'read')

    def test_source_type_mismatch_rejected(self):
        bpy = FakeBpy()
        src = PropertyObject('Source', 'CAMERA')
        bpy.data.objects['Source'] = src
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.validate', {
                'objectId': {'name': 'Source'},
                'sourceObjectId': {'name': 'Source'}})
        self.assertEqual(ctx.exception.code, 'OBJECT_TYPE_MISMATCH')


if __name__ == '__main__':
    unittest.main()
