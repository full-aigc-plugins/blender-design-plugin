"""Exercise every P1 BMesh operation in Blender 5.2 factory scene."""
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.harness.errors import HarnessError
from scripts.harness.runtime import build_registry

registry = build_registry(bpy)

def cube(name):
    return registry.dispatch('object.create_mesh', {'name': name, 'primitive': 'cube'})['result']

checks = []
item = cube('Extrude')
top = registry.dispatch('mesh.select', {'objectId': item['objectId'], 'method': 'normal',
                                        'direction': [0, 0, 1], 'angleDegrees': 1})['result']
assert len(top['faces']) == 1
registry.dispatch('mesh.edit', {'operation': 'extrude', 'selection': top, 'offset': [0, 0, 1]})
try:
    registry.dispatch('mesh.edit', {'operation': 'triangulate', 'selection': top})
    raise AssertionError('stale selection accepted')
except HarnessError as exc:
    assert exc.code == 'STALE_TOPOLOGY_SELECTION'
checks += ['normal_select', 'extrude', 'stale_selection']

for operation, params, selection_fields in [
    ('inset', {'thickness': .1, 'depth': .05}, {'faces': [1]}),
    ('bevel', {'width': .08, 'segments': 2}, {'edges': [0, 1, 2, 3]}),
    ('subdivide', {'cuts': 2}, {'edges': [0, 1, 2, 3]}),
    ('triangulate', {}, {'faces': [0, 1, 2, 3, 4, 5]}),
    ('recalculate_normals', {}, {'faces': [0, 1, 2, 3, 4, 5]}),
    ('weld', {'distance': .0001}, {'vertices': list(range(8))}),
    ('delete', {}, {'faces': [0]}),
]:
    item = cube(operation.title())
    selection = registry.dispatch('mesh.select', {'objectId': item['objectId'], 'method': 'indices',
                                                  **selection_fields})['result']
    registry.dispatch('mesh.edit', {'operation': operation, 'selection': selection, **params})
    checks.append(operation)

# Two square edge loops for bridge.
mesh = bpy.data.meshes.new('BridgeMesh')
mesh.from_pydata([(-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)],
                 [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4)], [])
obj = bpy.data.objects.new('Bridge', mesh); bpy.context.scene.collection.objects.link(obj)
bridge = registry.dispatch('mesh.select', {'name': 'Bridge', 'method': 'indices', 'edges': list(range(8))})['result']
registry.dispatch('mesh.edit', {'operation': 'bridge', 'selection': bridge})
assert len(mesh.polygons) == 4
checks.append('bridge')

plane = registry.dispatch('object.create_mesh', {'name': 'OpenSurface', 'primitive': 'plane'})['result']
strict = registry.dispatch('mesh.inspect', {'objectId': plane['objectId']})['result']
allowed = registry.dispatch('mesh.inspect', {'objectId': plane['objectId'], 'allowOpenSurface': True})['result']
assert strict['issues'][0]['severity'] == 'error' and allowed['issues'][0]['severity'] == 'info'
connected = registry.dispatch('mesh.select', {'objectId': plane['objectId'], 'method': 'connected', 'seedVertex': 0})['result']
spatial = registry.dispatch('mesh.select', {'objectId': plane['objectId'], 'method': 'spatial',
                                            'min': [-2,-2,-1], 'max': [0,2,1]})['result']
assert len(connected['vertices']) == 4 and len(spatial['vertices']) == 2
checks += ['inspect_open_semantics', 'connected_select', 'spatial_select']
print('P1_MESH=' + json.dumps({'blender': bpy.app.version_string, 'checks': checks,
                               'productionAcceptance': False}))
