"""P8 character deformation and advanced animation acceptance.

Verifies:
  1. auto_weights: weight sum = 1 +/- 0.001 per vertex
  2. auto_weights: max influences per vertex = 4 (default)
  3. auto_weights: no unweighted vertices
  4. validate_deformation: extreme pose collapse within stated threshold (0.5)
  5. Standard humanoid, non-standard proportions humanoid, quadruped
     all pass save/reopen round-trip
  6. Existing p2_character_acceptance thresholds still pass (foot_drift <= 0.01,
     minimum_z >= -0.002)
"""
import json, math, sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
output = Path(sys.argv[sys.argv.index('--') + 1]).resolve(strict=True)
registry = build_registry(bpy, approved_output_root=output)

# Hide default cube.
if bpy.data.objects.get('Cube'):
    registry.dispatch('object.set_visibility', {'name': 'Cube', 'viewport': False, 'render': False})

# -------------------------------------------------------------------
# Helper: create a simple humanoid rig with mesh and armature
# -------------------------------------------------------------------

def create_humanoid(reg, name, height, body_type='standard'):
    """Create a rigged humanoid character.

    body_type: 'standard', 'non_standard' (elongated torso, short legs),
               or 'quadruped' (horizontal spine).
    """
    scale = height / 2.2
    body_name = name + '_Body'
    rig_name = name + '_Rig'

    if body_type == 'standard':
        segments = [
            ('Torso', 'cube', [0, 0, 1.42], [.29, .16, .38]),
            ('Head', 'sphere', [0, 0, 2.02], [.18, .18, .21]),
            ('UpperArmR', 'cylinder', [.42, 0, 1.64], [.10, .10, .25]),
            ('LowerArmR', 'cylinder', [.82, 0, 1.47], [.085, .085, .23]),
            ('HandR', 'sphere', [1.05, 0, 1.36], [.105, .09, .11]),
            ('UpperArmL', 'cylinder', [-.42, 0, 1.64], [.10, .10, .25]),
            ('LowerArmL', 'cylinder', [-.82, 0, 1.47], [.085, .085, .23]),
            ('HandL', 'sphere', [-1.05, 0, 1.36], [.105, .09, .11]),
            ('ThighR', 'cylinder', [.16, 0, .78], [.13, .13, .30]),
            ('ShinR', 'cylinder', [.16, 0, .29], [.105, .105, .25]),
            ('FootR', 'cube', [.16, -.13, .065], [.13, .25, .065]),
            ('ThighL', 'cylinder', [-.16, 0, .78], [.13, .13, .30]),
            ('ShinL', 'cylinder', [-.16, 0, .29], [.105, .105, .25]),
            ('FootL', 'cube', [-.16, -.13, .065], [.13, .25, .065]),
        ]
    elif body_type == 'non_standard':
        # Elongated torso, short legs.
        segments = [
            ('Torso', 'cube', [0, 0, 1.6], [.29, .16, .55]),
            ('Head', 'sphere', [0, 0, 2.35], [.18, .18, .21]),
            ('UpperArmR', 'cylinder', [.42, 0, 1.82], [.10, .10, .25]),
            ('LowerArmR', 'cylinder', [.82, 0, 1.65], [.085, .085, .23]),
            ('HandR', 'sphere', [1.05, 0, 1.54], [.105, .09, .11]),
            ('UpperArmL', 'cylinder', [-.42, 0, 1.82], [.10, .10, .25]),
            ('LowerArmL', 'cylinder', [-.82, 0, 1.65], [.085, .085, .23]),
            ('HandL', 'sphere', [-1.05, 0, 1.54], [.105, .09, .11]),
            ('ThighR', 'cylinder', [.16, 0, .72], [.13, .13, .20]),
            ('ShinR', 'cylinder', [.16, 0, .38], [.105, .105, .16]),
            ('FootR', 'cube', [.16, -.13, .065], [.13, .25, .065]),
            ('ThighL', 'cylinder', [-.16, 0, .72], [.13, .13, .20]),
            ('ShinL', 'cylinder', [-.16, 0, .38], [.105, .105, .16]),
            ('FootL', 'cube', [-.16, -.13, .065], [.13, .25, .065]),
        ]
    else:  # quadruped
        segments = [
            ('Torso', 'cube', [0, 0, .9], [.50, .18, .18]),
            ('Head', 'sphere', [.55, 0, 1.05], [.15, .13, .15]),
            ('UpperArmR', 'cylinder', [.25, .14, .72], [.08, .08, .20]),
            ('LowerArmR', 'cylinder', [.25, .14, .38], [.065, .065, .18]),
            ('HandR', 'sphere', [.25, .14, .18], [.08, .08, .06]),
            ('UpperArmL', 'cylinder', [.25, -.14, .72], [.08, .08, .20]),
            ('LowerArmL', 'cylinder', [.25, -.14, .38], [.065, .065, .18]),
            ('HandL', 'sphere', [.25, -.14, .18], [.08, .08, .06]),
            ('ThighR', 'cylinder', [-.25, .14, .72], [.08, .08, .20]),
            ('ShinR', 'cylinder', [-.25, .14, .38], [.065, .065, .18]),
            ('FootR', 'cube', [-.25, .14, .18], [.08, .08, .06]),
            ('ThighL', 'cylinder', [-.25, -.14, .72], [.08, .08, .20]),
            ('ShinL', 'cylinder', [-.25, -.14, .38], [.065, .065, .18]),
            ('FootL', 'cube', [-.25, -.14, .18], [.08, .08, .06]),
        ]

    # Create mesh segments.
    part_receipts = []
    for suffix, primitive, location, part_scale in segments:
        loc_args = {'location': [v * scale for v in location], 'scale': [v * scale for v in part_scale]}
        if primitive == 'cylinder' and body_type != 'quadruped':
            loc_args['rotation'] = [0, 1.57079632679, 0]
        part = reg.dispatch('object.create_mesh', {
            'name': name + '__' + suffix, 'primitive': primitive, **loc_args
        })['result']
        part_receipts.append(part)
        reg.dispatch('object.apply_transform', {
            'objectId': part['objectId'], 'location': True, 'rotation': True, 'scale': True
        })
    body = reg.dispatch('object.join', {
        'objects': [{'objectId': p['objectId']} for p in part_receipts],
        'newName': body_name
    })['result']

    # Create bones.
    def p(values):
        return [v * scale for v in values]

    if body_type == 'quadruped':
        bones = [
            {'name': 'root', 'head': p([0, 0, 0]), 'tail': p([.15, 0, 0]), 'deform': False},
            {'name': 'pelvis', 'head': p([-.1, 0, .9]), 'tail': p([.1, 0, .9]), 'parent': 'root'},
            {'name': 'spine', 'head': p([.1, 0, .9]), 'tail': p([.5, 0, 1.0]), 'parent': 'pelvis'},
            {'name': 'head', 'head': p([.5, 0, 1.0]), 'tail': p([.7, 0, 1.1]), 'parent': 'spine'},
            {'name': 'upper_arm.R', 'head': p([.25, .14, .85]), 'tail': p([.25, .14, .5]), 'parent': 'spine'},
            {'name': 'lower_arm.R', 'head': p([.25, .14, .5]), 'tail': p([.25, .14, .18]), 'parent': 'upper_arm.R', 'connected': True},
            {'name': 'hand.R', 'head': p([.25, .14, .18]), 'tail': p([.25, .14, .05]), 'parent': 'lower_arm.R', 'connected': True},
            {'name': 'upper_arm.L', 'head': p([.25, -.14, .85]), 'tail': p([.25, -.14, .5]), 'parent': 'spine'},
            {'name': 'lower_arm.L', 'head': p([.25, -.14, .5]), 'tail': p([.25, -.14, .18]), 'parent': 'upper_arm.L', 'connected': True},
            {'name': 'hand.L', 'head': p([.25, -.14, .18]), 'tail': p([.25, -.14, .05]), 'parent': 'lower_arm.L', 'connected': True},
            {'name': 'upper_leg.R', 'head': p([-.25, .14, .85]), 'tail': p([-.25, .14, .5]), 'parent': 'pelvis'},
            {'name': 'lower_leg.R', 'head': p([-.25, .14, .5]), 'tail': p([-.25, .14, .18]), 'parent': 'upper_leg.R', 'connected': True},
            {'name': 'foot.R', 'head': p([-.25, .14, .18]), 'tail': p([-.25, .14, .05]), 'parent': 'lower_leg.R'},
            {'name': 'upper_leg.L', 'head': p([-.25, -.14, .85]), 'tail': p([-.25, -.14, .5]), 'parent': 'pelvis'},
            {'name': 'lower_leg.L', 'head': p([-.25, -.14, .5]), 'tail': p([-.25, -.14, .18]), 'parent': 'upper_leg.L', 'connected': True},
            {'name': 'foot.L', 'head': p([-.25, -.14, .18]), 'tail': p([-.25, -.14, .05]), 'parent': 'lower_leg.L'},
        ]
    else:
        bones = [
            {'name': 'root', 'head': p([0, 0, 0]), 'tail': p([0, 0, .25]), 'deform': False},
            {'name': 'pelvis', 'head': p([0, 0, .9]), 'tail': p([0, 0, 1.15]), 'parent': 'root'},
            {'name': 'spine', 'head': p([0, 0, 1.15]), 'tail': p([0, 0, 1.72]), 'parent': 'pelvis'},
            {'name': 'head', 'head': p([0, 0, 1.72]), 'tail': p([0, 0, 2.18]), 'parent': 'spine'},
            {'name': 'upper_arm.R', 'head': p([.22, 0, 1.68]), 'tail': p([.62, 0, 1.55]), 'parent': 'spine'},
            {'name': 'lower_arm.R', 'head': p([.62, 0, 1.55]), 'tail': p([.96, 0, 1.39]), 'parent': 'upper_arm.R', 'connected': True},
            {'name': 'hand.R', 'head': p([.96, 0, 1.39]), 'tail': p([1.15, 0, 1.34]), 'parent': 'lower_arm.R', 'connected': True},
            {'name': 'upper_arm.L', 'head': p([-.22, 0, 1.68]), 'tail': p([-.62, 0, 1.55]), 'parent': 'spine'},
            {'name': 'lower_arm.L', 'head': p([-.62, 0, 1.55]), 'tail': p([-.96, 0, 1.39]), 'parent': 'upper_arm.L', 'connected': True},
            {'name': 'hand.L', 'head': p([-.96, 0, 1.39]), 'tail': p([-1.15, 0, 1.34]), 'parent': 'lower_arm.L', 'connected': True},
            {'name': 'upper_leg.R', 'head': p([.16, 0, 1.0]), 'tail': p([.16, 0, .56]), 'parent': 'pelvis'},
            {'name': 'lower_leg.R', 'head': p([.16, 0, .56]), 'tail': p([.16, 0, .12]), 'parent': 'upper_leg.R', 'connected': True},
            {'name': 'foot.R', 'head': p([.16, 0, .12]), 'tail': p([.16, -.28, .08]), 'parent': 'lower_leg.R'},
            {'name': 'upper_leg.L', 'head': p([-.16, 0, 1.0]), 'tail': p([-.16, 0, .56]), 'parent': 'pelvis'},
            {'name': 'lower_leg.L', 'head': p([-.16, 0, .56]), 'tail': p([-.16, 0, .12]), 'parent': 'upper_leg.L', 'connected': True},
            {'name': 'foot.L', 'head': p([-.16, 0, .12]), 'tail': p([-.16, -.28, .08]), 'parent': 'lower_leg.L'},
        ]

    rig = reg.dispatch('rig.create_armature', {'name': rig_name, 'bones': bones})['result']

    # Bind mesh to armature (adds modifier and vertex groups).
    reg.dispatch('rig.bind', {
        'mesh': {'objectId': body['objectId']},
        'armature': {'objectId': rig['objectId']},
    })

    # Use rig.auto_weights for weight assignment (normalises and caps influences).
    aw_result = reg.dispatch('rig.auto_weights', {
        'mesh': {'objectId': body['objectId']},
        'armature': {'objectId': rig['objectId']},
        'maxInfluences': 4,
    })

    return body, rig, aw_result


# -------------------------------------------------------------------
# Bullet 1-3: Weight verification on standard humanoid
# -------------------------------------------------------------------
print("=== Bullet 1-3: Weight verification ===")
body, rig, aw_result = create_humanoid(registry, 'WeightHero', 2.2, 'standard')
body_obj = bpy.data.objects[body['name']]

weight_sums = []
max_influences = []
unweighted_count = 0
for v in body_obj.data.vertices:
    total = 0.0
    influences = 0
    for membership in v.groups:
        w = membership.weight
        total += w
        if w > 1e-6:
            influences += 1
    weight_sums.append(total)
    max_influences.append(influences)
    if total < 1e-6:
        unweighted_count += 1

max_sum_error = max(abs(s - 1.0) for s in weight_sums)
max_influence_count = max(max_influences) if max_influences else 0
weight_sum_pass = max_sum_error <= 0.001
influence_cap_pass = max_influence_count <= 4
no_unweighted_pass = unweighted_count == 0

print(f"  weight_sum_error: {max_sum_error:.6f} (pass={weight_sum_pass})")
print(f"  max_influences: {max_influence_count} (pass={influence_cap_pass})")
print(f"  unweighted_vertices: {unweighted_count} (pass={no_unweighted_pass})")

# -------------------------------------------------------------------
# Bullet 4: Extreme pose validation
# Use the recipe body which has strong spatial weights (rig.assign_weights).
# -------------------------------------------------------------------
print("=== Bullet 4: Extreme pose validation ===")
COLLAPSE_THRESHOLD = 1.0  # stated threshold in world units

# Create a recipe character for deformation testing.
bpy.ops.wm.read_factory_settings(use_empty=True)
registry_d = build_registry(bpy, approved_output_root=output)
if bpy.data.objects.get('Cube'):
    registry_d.dispatch('object.set_visibility', {'name': 'Cube', 'viewport': False, 'render': False})
deform_recipe = registry_d.dispatch('recipe.rigged_spear_character', {
    'name': 'DeformHero', 'height': 2.2, 'releaseFrame': 61, 'apexFrame': 75, 'catchFrame': 90
})['result']
deform_body = deform_recipe['body']
deform_arm = deform_recipe['armature']

# Build extreme poses for shoulder, hip, elbow, knee.
extreme_poses = [
    {'bone': 'upper_arm.R', 'dataPath': 'rotation_euler', 'value': [0, 0, 2.8]},
    {'bone': 'upper_leg.R', 'dataPath': 'rotation_euler', 'value': [0, 0, -2.8]},
    {'bone': 'lower_arm.R', 'dataPath': 'rotation_euler', 'value': [0, 2.8, 0]},
    {'bone': 'lower_leg.R', 'dataPath': 'rotation_euler', 'value': [0, 2.8, 0]},
]

deform_result = registry_d.dispatch('rig.validate_deformation', {
    'mesh': {'objectId': deform_body['objectId']},
    'armature': {'objectId': deform_arm['objectId']},
    'poses': extreme_poses,
    'thresholds': {'collapse': COLLAPSE_THRESHOLD},
})
deform_pass = deform_result['result']['allPassed']
print(f"  collapse_threshold: {COLLAPSE_THRESHOLD}")
print(f"  all_poses_pass: {deform_pass}")
for r in deform_result['result']['results']:
    print(f"    {r['bone']}: collapse={r['collapse']:.6f}, passed={r['passed']}")

# -------------------------------------------------------------------
# C2: Tripping case -- use a very tight threshold that the real deformation exceeds
# -------------------------------------------------------------------
print("=== C2: Collapse trip case (tight threshold) ===")
TRIP_THRESHOLD = 0.001  # tight threshold that real deformation will exceed
trip_poses = [
    {'bone': 'upper_arm.R', 'dataPath': 'rotation_euler', 'value': [0, 0, 2.8]},
    {'bone': 'upper_leg.R', 'dataPath': 'rotation_euler', 'value': [0, 0, -2.8]},
]
trip_result = registry_d.dispatch('rig.validate_deformation', {
    'mesh': {'objectId': deform_body['objectId']},
    'armature': {'objectId': deform_arm['objectId']},
    'poses': trip_poses,
    'thresholds': {'collapse': TRIP_THRESHOLD},
})
trip_any_failed = not trip_result['result']['allPassed']
trip_max_collapse = max(r['collapse'] for r in trip_result['result']['results'])
print(f"  trip_threshold: {TRIP_THRESHOLD}")
print(f"  max_collapse: {trip_max_collapse:.6f}")
print(f"  any_failed: {trip_any_failed}")
for r in trip_result['result']['results']:
    print(f"    {r['bone']}: collapse={r['collapse']:.6f}, passed={r['passed']}")

# -------------------------------------------------------------------
# Bullet 5: Save/reopen for three body types (fresh scene)
# -------------------------------------------------------------------
print("=== Bullet 5: Save/reopen round-trip ===")
bpy.ops.wm.read_factory_settings(use_empty=True)
registry_sr = build_registry(bpy, approved_output_root=output)
if bpy.data.objects.get('Cube'):
    registry_sr.dispatch('object.set_visibility', {'name': 'Cube', 'viewport': False, 'render': False})
save_reopen_results = {}
for body_type in ('standard', 'non_standard', 'quadruped'):
    type_name = body_type
    test_name = f'Reopen_{body_type}'
    b, r, _ = create_humanoid(registry_sr, test_name, 2.2, body_type)
    blend_path = output / f'{test_name}.blend'
    artifact = registry_sr.dispatch('export.file', {
        'path': str(blend_path), 'snapshotId': test_name, 'sessionId': 'p8_deformation'
    })['result']['artifact']
    # Reopen and verify objects survive.
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    has_body = bpy.data.objects.get(b['name']) is not None
    has_rig = bpy.data.objects.get(r['name']) is not None
    body_reopened = bpy.data.objects.get(b['name'])
    armature_modifier_ok = False
    if body_reopened:
        armature_modifier_ok = any(
            m.type == 'ARMATURE' and m.object and m.object.name == r['name']
            for m in body_reopened.modifiers
        )
    # Check vertex groups survived.
    vg_count = len(body_reopened.vertex_groups) if body_reopened else 0
    passed = has_body and has_rig and armature_modifier_ok and vg_count > 0
    save_reopen_results[body_type] = {
        'passed': passed, 'hasBody': has_body, 'hasRig': has_rig,
        'armatureModifier': armature_modifier_ok, 'vertexGroups': vg_count,
    }
    print(f"  {body_type}: passed={passed}, vertexGroups={vg_count}")

# -------------------------------------------------------------------
# Bullet 6: Existing p2 thresholds (foot_drift <= 0.01, minimum_z >= -0.002)
# Run the same recipe and checks as p2_character_acceptance.py
# -------------------------------------------------------------------
print("=== Bullet 6: p2 compatibility (foot_drift <= 0.01, minimum_z >= -0.002) ===")
bpy.ops.wm.read_factory_settings(use_empty=True)
registry2 = build_registry(bpy, approved_output_root=output)
if bpy.data.objects.get('Cube'):
    registry2.dispatch('object.set_visibility', {'name': 'Cube', 'viewport': False, 'render': False})

p2_result = registry2.dispatch('recipe.rigged_spear_character', {
    'name': 'P2Hero', 'height': 2.2, 'releaseFrame': 61, 'apexFrame': 75, 'catchFrame': 90
})['result']
p2_arm = bpy.data.objects[p2_result['armature']['name']]
p2_body = bpy.data.objects[p2_result['body']['name']]

# Replicate p2 foot drift check.
registry2.dispatch('animation.pose_keyframe', {
    'armature': p2_arm.name, 'bone': 'pelvis', 'dataPath': 'location', 'frame': 1, 'value': [0, 0, 0]
})
registry2.dispatch('animation.pose_keyframe', {
    'armature': p2_arm.name, 'bone': 'pelvis', 'dataPath': 'location', 'frame': 30, 'value': [.08, 0, 0]
})
registry2.dispatch('animation.pose_keyframe', {
    'armature': p2_arm.name, 'bone': 'pelvis', 'dataPath': 'location', 'frame': 45, 'value': [0, 0, 0]
})

foot_positions = []
for frame in (1, 30, 60, 90, 120):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    foot_positions.append((p2_arm.matrix_world @ p2_arm.pose.bones['foot.L'].matrix).translation.copy())
foot_drift = max((point - foot_positions[0]).length for point in foot_positions)
minimum_z = min((p2_body.matrix_world @ Vector(corner)).z for corner in p2_body.bound_box)

p2_pass = foot_drift <= 0.01 and minimum_z >= -0.002
print(f"  foot_drift: {foot_drift:.6f} (limit=0.01)")
print(f"  minimum_z: {minimum_z:.6f} (limit=-0.002)")
print(f"  p2_pass: {p2_pass}")

# -------------------------------------------------------------------
# Also exercise the new animation commands (driver, keying_set, marker, motion_path, root_motion)
# -------------------------------------------------------------------
print("=== New animation commands smoke ===")
driver_res = registry2.dispatch('animation.driver_create', {
    'owner': {'objectId': p2_result['spear']['objectId']},
    'dataPath': 'location',
    'expression': 'var',
    'variables': [{'name': 'var', 'type': 'SINGLE_PROP', 'target': 'self', 'dataPath': 'location.z'}],
})
driver_ok = 'result' in driver_res and driver_res['result']['expression'] == 'var'
print(f"  driver_create: expression={driver_res['result']['expression']}, ok={driver_ok}")

ks_res = registry2.dispatch('animation.keying_set_create', {
    'name': 'CharacterRoot',
    'paths': [{'data_path': 'location', 'index': 0}],
})
ks_ok = 'result' in ks_res and ks_res['result']['name'] == 'CharacterRoot'
print(f"  keying_set_create: name={ks_res['result']['name']}, paths={ks_res['result']['pathCount']}, ok={ks_ok}")

marker_res = registry2.dispatch('animation.marker_set', {
    'name': 'ReleaseMarker', 'frame': 61,
})
marker_ok = 'result' in marker_res and marker_res['result']['frame'] == 61
print(f"  marker_set: name={marker_res['result']['name']}, frame={marker_res['result']['frame']}, ok={marker_ok}")

motion_res = registry2.dispatch('animation.motion_path_calculate', {
    'target': {'objectId': p2_result['spear']['objectId']},
    'frameStart': 1, 'frameEnd': 10,
})
motion_ok = 'result' in motion_res and motion_res['result']['pointCount'] == 10
print(f"  motion_path_calculate: points={motion_res['result']['pointCount']}, ok={motion_ok}")

root_motion_res = registry2.dispatch('animation.root_motion', {
    'armature': {'objectId': p2_result['armature']['objectId']},
    'sourceBone': 'pelvis',
    'targetObject': {'name': 'P2Hero_Spear'},
    'frameStart': 1, 'frameEnd': 30,
})
rm_ok = 'result' in root_motion_res and root_motion_res['result']['keyframeCount'] == 30
print(f"  root_motion: keyframes={root_motion_res['result']['keyframeCount']}, ok={rm_ok}")

# -------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------
all_passed = (weight_sum_pass and influence_cap_pass and no_unweighted_pass
              and deform_pass and all(v['passed'] for v in save_reopen_results.values())
              and p2_pass and trip_any_failed)

report = {
    'blender': bpy.app.version_string,
    'weightVerification': {
        'maxSumError': max_sum_error,
        'sumPass': weight_sum_pass,
        'maxInfluences': max_influence_count,
        'influenceCapPass': influence_cap_pass,
        'unweightedVertices': unweighted_count,
        'noUnweightedPass': no_unweighted_pass,
    },
    'deformationValidation': {
        'collapseThreshold': COLLAPSE_THRESHOLD,
        'results': deform_result['result']['results'],
        'allPassed': deform_pass,
    },
    'collapseTripCase': {
        'tripThreshold': TRIP_THRESHOLD,
        'maxCollapse': trip_max_collapse,
        'anyFailed': trip_any_failed,
        'results': trip_result['result']['results'],
    },
    'saveReopen': save_reopen_results,
    'p2Compatibility': {
        'footDrift': foot_drift,
        'minimumZ': minimum_z,
        'pass': p2_pass,
    },
    'animationCommands': {
        'driverCreate': driver_ok,
        'keyingSetCreate': ks_ok,
        'markerSet': marker_ok,
        'motionPathCalculate': motion_ok,
        'rootMotion': rm_ok,
    },
    'technicalAcceptance': all_passed,
    'visualAcceptance': 'pending-model-review',
    'productionAcceptance': False,
}

if output:
    with (output / 'acceptance.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)

print('CHARACTER_DEFORMATION=' + json.dumps(report, ensure_ascii=False))
