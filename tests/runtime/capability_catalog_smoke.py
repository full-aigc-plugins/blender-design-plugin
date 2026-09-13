"""Run in an isolated Blender process, never against a user's open project."""
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.harness.runtime import build_registry
from scripts.harness.errors import HarnessError

registry = build_registry(bpy)
before = set(bpy.data.objects.keys())
before_materials = set(bpy.data.materials.keys())
for command, args in [
    ('camera.create', {'lens': -1}),
    ('camera.create', {'lens': float('nan')}),
    ('light.create', {'color': [1]}),
    ('light.create', {'energy': float('inf')}),
    ('material.create_pbr', {'roughness': 2}),
    ('object.create_curve', {'bevelDepth': -1}),
    ('object.create_text', {'text': 'invalid', 'extrude': -1}),
]:
    try:
        registry.dispatch(command, {'name': 'MustNotExist', **args})
        raise AssertionError(f'{command} accepted invalid arguments')
    except HarnessError as exc:
        assert exc.code == 'INVALID_ARGUMENT', exc
    assert set(bpy.data.objects.keys()) == before
    assert set(bpy.data.materials.keys()) == before_materials
catalog = registry.dispatch('capability.list', {'limit': 100})['result']
assert catalog['domains']['sculpt']['maturity'] == 'L0'
assert catalog['domains']['rig']['maturity'] == 'L0'
assert registry.describe_capability({'id': 'view.set'})['availability']['status'] == 'unavailable'
assert registry.describe_capability({'id': 'preview.capture'})['availability']['status'] == 'unavailable'
assert registry.describe_capability({'id': 'object.transform'})['input']['properties']['location']['type'] == 'array'
for item in catalog['items']:
    detail = registry.dispatch('capability.describe', {'id': item['id']})['result']
    assert detail['id'] == item['id']
assert set(bpy.data.objects.keys()) == before
for bad in ([0, 0], [0, float('nan'), 1], [0, float('inf'), 1]):
    try:
        registry.dispatch('object.create_mesh', {'name': 'MustNotExist', 'primitive': 'cube', 'scale': bad})
        raise AssertionError('invalid vector accepted')
    except HarnessError as exc:
        assert exc.code == 'INVALID_ARGUMENT'
    assert set(bpy.data.objects.keys()) == before
registry.dispatch('object.create_mesh', {'name': 'PrevalidationFixture', 'primitive': 'cube'})
obj = bpy.data.objects['PrevalidationFixture']
try:
    registry.dispatch('modifier.add', {'name': obj.name, 'modifier': 'BEVEL',
                                      'settings': {'width': .1, 'not_a_property': 1}})
    raise AssertionError('invalid modifier accepted')
except HarnessError:
    assert len(obj.modifiers) == 0
original = tuple(obj.location)
try:
    registry.dispatch('object.transform', {'name': obj.name, 'location': [5, 6, 7], 'scale': [1]})
    raise AssertionError('invalid late field accepted')
except HarnessError:
    assert tuple(obj.location) == original
report = {'blender': bpy.app.version_string, 'background': bpy.app.background,
          'registeredCommands': catalog['total'], 'checks': ['catalog_read_only', 'no_placeholder_commands',
          'invalid_create_has_no_side_effect', 'invalid_transform_has_no_partial_change',
          'lookdev_curve_text_prevalidation', 'modifier_failure_removes_new_modifier'],
          'productionAcceptance': False}
print('CAPABILITY_SMOKE=' + json.dumps(report, ensure_ascii=False))
if '--' in sys.argv:
    # Optional exclusive-create receipt, inside a caller-provided fresh directory.
    directory = Path(sys.argv[sys.argv.index('--') + 1]).resolve(strict=True)
    for filename, payload in [('catalog.json', catalog), ('verification.json', report)]:
        with (directory / filename).open('x', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
