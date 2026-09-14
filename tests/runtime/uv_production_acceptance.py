"""Runtime acceptance for uv.detect_overlap and uv.measure_texel_density.

Runs inside a real Blender process (headless).  Demonstrates:
  1. Real overlap found with face indices, area, and ratio.
  2. Zero-area UV reported separately, not in overlap list.
  3. Texel density within 5% of hand-computed expectation.
  4. UDIM: faces at identical local UVs on different tiles do NOT overlap.
  5. Read-only: pre/post scene comparison holds.
"""
import json
import math
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.harness.runtime import build_registry
from scripts.harness.errors import HarnessError

registry = build_registry(bpy)


def _snapshot_scene():
    """Return a lightweight fingerprint of the scene for read-only verification."""
    objs = [(o.name, o.type, len(o.data.polygons) if o.type == 'MESH' else 0)
            for o in bpy.data.objects]
    return sorted(objs)


# ===========================================================================
# 1. Overlap detection on two overlapping quads
# ===========================================================================

bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, 0))
plane_overlap = bpy.context.active_object
plane_overlap.name = 'OverlapPlane'

# Edit: subdivide once to get 4 quads.  Set face 0 and 1 to identical UVs
# so they overlap; faces 2 and 3 get non-overlapping UVs.
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.subdivide()
bpy.ops.object.mode_set(mode='OBJECT')

mesh = plane_overlap.data
uv_layer = mesh.uv_layers.active
if uv_layer is None:
    uv_layer = mesh.uv_layers.new(name='UVMap')

# Face 0 and 1: identical UV region [0,0]-[0.5,0]-[0.5,0.5]-[0,0.5]
# Face 2: [0.6,0.6]-[1.0,0.6]-[1.0,1.0]-[0.6,1.0] (no overlap with 0/1)
# Face 3: [0.0,0.6]-[0.4,0.6]-[0.4,1.0]-[0.0,1.0] (no overlap with 0/1)
face_uvs = {
    0: [(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)],
    1: [(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)],
    2: [(0.6, 0.6), (1.0, 0.6), (1.0, 1.0), (0.6, 1.0)],
    3: [(0.0, 0.6), (0.4, 0.6), (0.4, 1.0), (0.0, 1.0)],
}
for face_idx, uvs in face_uvs.items():
    poly = mesh.polygons[face_idx]
    for loop_idx in poly.loop_indices:
        local = loop_idx - poly.loop_start
        uv_layer.data[loop_idx].uv = uvs[local]

created = registry.dispatch('object.describe', {'name': 'OverlapPlane'})
overlap_id = created['result']['objectId']

snapshot_before = _snapshot_scene()

result_overlap = registry.dispatch('uv.detect_overlap', {'objectId': overlap_id})
res = result_overlap['result']

snapshot_after = _snapshot_scene()
assert snapshot_before == snapshot_after, 'detect_overlap modified the scene!'

print(f"=== Overlap Detection ===")
print(f"hasUV: {res['hasUV']}")
print(f"hasOverlaps: {res['hasOverlaps']}")
print(f"overlap count: {len(res['overlaps'])}")
for o in res['overlaps']:
    print(f"  faceA={o['faceA']} faceB={o['faceB']} area={o['area']:.6f} ratio={o['ratio']:.6f}")
print(f"degenerateFaces: {res['degenerateFaces']}")
assert res['hasOverlaps'], 'Expected overlapping faces to be detected'
assert len(res['overlaps']) >= 1, 'Expected at least 1 overlap pair'
pair = res['overlaps'][0]
assert pair['area'] > 0, 'Overlap area must be positive'
assert pair['ratio'] > 0, 'Overlap ratio must be positive'
print("PASS: overlap detected with face indices, area, and ratio\n")


# ===========================================================================
# 2. Zero-area (degenerate) UV face reported separately
# ===========================================================================

bpy.ops.mesh.primitive_plane_add(size=1, location=(5, 0, 0))
degen_obj = bpy.context.active_object
degen_obj.name = 'DegeneratePlane'
degen_mesh = degen_obj.data
degen_uv = degen_mesh.uv_layers.active
if degen_uv is None:
    degen_uv = degen_mesh.uv_layers.new(name='UVMap')

# Set all 4 vertices to the same UV point => zero area
for poly in degen_mesh.polygons:
    for loop_idx in poly.loop_indices:
        degen_uv.data[loop_idx].uv = (0.5, 0.5)

degen_created = registry.dispatch('object.describe', {'name': 'DegeneratePlane'})
degen_id = degen_created['result']['objectId']

result_degen = registry.dispatch('uv.detect_overlap', {'objectId': degen_id})
res_d = result_degen['result']

print(f"=== Degenerate UV ===")
print(f"degenerateFaces: {res_d['degenerateFaces']}")
print(f"hasOverlaps: {res_d['hasOverlaps']}")
print(f"overlaps: {res_d['overlaps']}")
assert 0 in res_d['degenerateFaces'], 'Face 0 should be degenerate'
# Degenerate must NOT appear in overlaps
for o in res_d['overlaps']:
    assert o['faceA'] != 0 and o['faceB'] != 0, 'Degenerate face must not be in overlaps'
print("PASS: zero-area UV reported separately, not in overlaps\n")


# ===========================================================================
# 3. Texel density on a known-size plane
# ===========================================================================

# Create a 2m x 2m plane.  UVs cover [0,1]x[0,1] (area=1).
# Texture: 1024x1024.
# Expected texel density = sqrt(1024*1024 * uv_area /3d_area)
#   uv_area of one face (quad) = 1.0
#   3d_area of one face = (2/2)*(2/2) = ... wait, the plane is 2x2, 1 quad.
#   3D area = 4.0.  UV area = 1.0.
#   td = sqrt(1024*1024 * 1.0 / 4.0) = sqrt(262144) = 512.0 px/m

bpy.ops.mesh.primitive_plane_add(size=2, location=(10, 0, 0))
density_obj = bpy.context.active_object
density_obj.name = 'DensityPlane'
density_mesh = density_obj.data
density_uv = density_mesh.uv_layers.active
if density_uv is None:
    density_uv = density_mesh.uv_layers.new(name='UVMap')

# Default plane UVs may not be [0,1].  Force them.
for poly in density_mesh.polygons:
    for loop_idx in poly.loop_indices:
        local = loop_idx - poly.loop_start
        # Default plane has 4 verts in order: BL, BR, TR, TL
        uvs_per_local = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        density_uv.data[loop_idx].uv = uvs_per_local[local]

density_created = registry.dispatch('object.describe', {'name': 'DensityPlane'})
density_id = density_created['result']['objectId']

result_density = registry.dispatch('uv.measure_texel_density', {
    'objectId': density_id,
    'textureWidth': 1024,
    'textureHeight': 1024,
})
res_td = result_density['result']

print(f"=== Texel Density ===")
print(f"textureWidth: {res_td['textureWidth']}")
print(f"textureHeight: {res_td['textureHeight']}")
print(f"face count: {len(res_td['faces'])}")
for f in res_td['faces']:
    print(f"  face={f['face']} td={f['texelDensity']:.2f} uvArea={f['uvArea']:.6f} 3dArea={f['threeDArea']:.6f}")

# Expected: td = sqrt(1024*1024 * 1.0 / 4.0) = 512.0
expected_td = math.sqrt(1024 * 1024 * 1.0 / 4.0)
face_td = res_td['faces'][0]
error_pct = abs(face_td['texelDensity'] - expected_td) / expected_td * 100
print(f"expected={expected_td:.2f} measured={face_td['texelDensity']:.2f} error={error_pct:.2f}%")
assert error_pct <= 5.0, f'Texel density error {error_pct:.2f}% exceeds 5%'
print(f"PASS: texel density within 5% (error={error_pct:.2f}%)\n")


# ===========================================================================
# 4. UDIM: identical local UVs on different tiles must NOT overlap
# ===========================================================================

bpy.ops.mesh.primitive_plane_add(size=1, location=(15, 0, 0))
udim_obj = bpy.context.active_object
udim_obj.name = 'UDIMPlane'
udim_mesh = udim_obj.data
udim_uv = udim_mesh.uv_layers.active
if udim_uv is None:
    udim_uv = udim_mesh.uv_layers.new(name='UVMap')

# Subdivide to get 4 quads, then assign different tiles to faces 0 and 1.
# Faces 2 and 3 get non-overlapping UVs on tile (0,1).
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.subdivide()
bpy.ops.object.mode_set(mode='OBJECT')

udim_mesh = udim_obj.data
udim_uv = udim_mesh.uv_layers.active

# Face 0: tile (0,0) local coords [0,0]-[0.5,0]-[0.5,0.5]-[0,0.5]
# Face 1: tile (1,0) local coords [0,0]-[0.5,0]-[0.5,0.5]-[0,0.5] (global +1.0 U)
# Face 2: tile (0,1) local coords [0,0]-[0.5,0]-[0.5,0.5]-[0,0.5] (global +1.0 V)
# Face 3: tile (0,1) local coords [0.6,0.6]-[1.0,0.6]-[1.0,1.0]-[0.6,1.0]
tile_uvs = [(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)]
for poly_idx, u_off, v_off in [(0, 0.0, 0.0), (1, 1.0, 0.0), (2, 0.0, 1.0), (3, 0.0, 1.0)]:
    poly = udim_mesh.polygons[poly_idx]
    for loop_idx in poly.loop_indices:
        local = loop_idx - poly.loop_start
        lu, lv = tile_uvs[local]
        if poly_idx == 3:
            lu, lv = 0.6 + lu * 0.4, 0.6 + lv * 0.4
        udim_uv.data[loop_idx].uv = (lu + u_off, lv + v_off)

udim_created = registry.dispatch('object.describe', {'name': 'UDIMPlane'})
udim_id = udim_created['result']['objectId']

result_udim = registry.dispatch('uv.detect_overlap', {'objectId': udim_id})
res_u = result_udim['result']

print(f"=== UDIM Tile Isolation ===")
print(f"hasOverlaps: {res_u['hasOverlaps']}")
print(f"overlaps: {res_u['overlaps']}")
assert not res_u['hasOverlaps'], 'Faces on different UDIM tiles must not overlap'
assert res_u['overlaps'] == [], 'No overlap pairs expected for different tiles'
print("PASS: different UDIM tiles do not produce false overlap\n")


# ===========================================================================
# 5. Read-only verification on texel density
# ===========================================================================

snapshot_td_before = _snapshot_scene()
registry.dispatch('uv.measure_texel_density', {
    'objectId': density_id,
    'textureWidth': 512,
    'textureHeight': 512,
})
snapshot_td_after = _snapshot_scene()
assert snapshot_td_before == snapshot_td_after, 'measure_texel_density modified the scene!'
print("=== Read-Only Verification ===")
print("PASS: measure_texel_density does not modify scene\n")


# ===========================================================================
# Summary
# ===========================================================================

print("=== UV PRODUCTION ACCEPTANCE COMPLETE ===")
print("All 5 acceptance criteria demonstrated.")
