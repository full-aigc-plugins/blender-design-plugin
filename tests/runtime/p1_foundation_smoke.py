"""P1 foundation integration against a factory-started Blender process."""
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.harness.runtime import build_registry
from scripts.harness.errors import HarnessError


registry = build_registry(bpy)
registry.dispatch('scene.set_units', {'system': 'METRIC', 'scaleLength': 1})
registry.dispatch('collection.create', {'name': 'ProductParts'})
created = registry.dispatch('object.create_mesh', {'name': 'Housing', 'primitive': 'cube',
                                                   'location': [1, 2, 3], 'scale': [2, 1, .5]})['result']
stable_id = created['objectId']
registry.dispatch('collection.move_object', {'objectId': stable_id, 'collection': 'ProductParts'})
copy = registry.dispatch('object.duplicate', {'objectId': stable_id, 'newName': 'HousingCopy'})['result']
instance = registry.dispatch('object.instance', {'objectId': stable_id, 'newName': 'HousingInstance'})['result']
assert copy['objectId'] != stable_id != instance['objectId']
assert bpy.data.objects['Housing'].data is not bpy.data.objects['HousingCopy'].data
assert bpy.data.objects['Housing'].data is bpy.data.objects['HousingInstance'].data
bpy.data.objects['Housing'].name = 'HousingRenamed'
described = registry.dispatch('object.describe', {'objectId': stable_id})['result']
assert described['name'] == 'HousingRenamed'
registry.dispatch('object.set_visibility', {'objectId': stable_id, 'viewport': False, 'render': False})
assert bpy.data.objects['HousingRenamed'].hide_viewport and bpy.data.objects['HousingRenamed'].hide_render
registry.dispatch('object.set_visibility', {'objectId': stable_id, 'viewport': True, 'render': True})
try:
    registry.dispatch('object.apply_transform', {'objectId': stable_id, 'scale': True})
    raise AssertionError('shared-data transform should require an explicit duplicate')
except HarnessError as exc:
    assert exc.code == 'OPERATION_FAILED'
registry.dispatch('object.apply_transform', {'objectId': copy['objectId'], 'scale': True})
assert all(abs(value - 1) < 1e-8 for value in bpy.data.objects['HousingCopy'].scale)
registry.dispatch('object.set_origin', {'objectId': stable_id, 'origin': 'GEOMETRY'})
edit_obj=bpy.data.objects['HousingCopy']
for selected in bpy.context.selected_objects:selected.select_set(False)
edit_obj.select_set(True);bpy.context.view_layer.objects.active=edit_obj;bpy.ops.object.mode_set(mode='EDIT')
registry.dispatch('object.set_origin',{'objectId':copy['objectId'],'origin':'GEOMETRY'})
assert bpy.context.mode=='EDIT_MESH';bpy.ops.object.mode_set(mode='OBJECT')
parent = registry.dispatch('object.create_mesh', {'name':'Parent','primitive':'cube','location':[10,0,0]})['result']
child = registry.dispatch('object.create_mesh', {'name':'Child','primitive':'cube','location':[2,0,0]})['result']
world_before = bpy.data.objects['Child'].matrix_world.copy()
registry.dispatch('object.parent', {'childObjectId':child['objectId'],'parentObjectId':parent['objectId'],'keepWorld':True})
assert all(abs(a-b)<1e-8 for row_a,row_b in zip(world_before,bpy.data.objects['Child'].matrix_world)
           for a,b in zip(row_a,row_b))
registry.dispatch('object.transform', {'objectId':child['objectId'],'space':'WORLD','location':[4,0,0]})
assert abs(bpy.data.objects['Child'].matrix_world.translation.x-4)<1e-8
registry.dispatch('object.rename', {'objectId':child['objectId'],'newName':'ChildRenamed'})
temporary=registry.dispatch('object.create_mesh',{'name':'DeleteById','primitive':'cube'})['result']
registry.dispatch('object.delete',{'objectId':temporary['objectId']}); assert bpy.data.objects.get('DeleteById') is None
assert bpy.context.scene.unit_settings.system == 'METRIC'
assert [collection.name for collection in bpy.data.objects['HousingRenamed'].users_collection] == ['ProductParts']
print('P1_FOUNDATION=' + json.dumps({'blender': bpy.app.version_string,
      'stableId': stable_id, 'checks': ['units', 'collection', 'rename_stability', 'duplicate',
      'linked_instance', 'visibility', 'shared_transform_refusal', 'apply_transform', 'origin',
      'edit_mode_restore', 'keep_world_parent', 'world_transform', 'rename_by_id', 'delete_by_id'],
      'productionAcceptance': False}))
