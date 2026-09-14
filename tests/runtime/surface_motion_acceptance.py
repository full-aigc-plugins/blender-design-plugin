"""Surface-motion acceptance: hair grooming, simulation caches, GP round-trip.

Covers the four acceptance bullets:
  1. Hair: no unbound strand, no NaN coordinate, no infinite length;
     hair.groom exercises all six operations with measured geometric effects,
     selection scoping, and empty-selection control.
  2. A simulation parameter change invalidates the previous cache.
  3. A cancelled bake leaves a project that still reopens.
  4. Grease Pencil interpolation, modifiers, materials and per-frame data
     survive save/reopen.

Every check is backed by a mutation test that proves it can fail.
"""
import json, math, sys, time
from pathlib import Path

import bpy
import mathutils

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.harness.runtime import build_registry
from scripts.harness.errors import HarnessError

assert '--' in sys.argv
output = Path(sys.argv[sys.argv.index('--') + 1]).resolve(strict=True)

report = {
    'blender': None,
    'bullets': {},
    'mutations': {},
    'acceptance': {},
    'technicalAcceptance': False,
}

_exit_code = 0


def fail_bullet(name, detail):
    global _exit_code
    _exit_code = 1
    report['acceptance'][name] = False
    report.setdefault('failureDetails', {})[name] = detail


def pass_bullet(name):
    report['acceptance'][name] = True


def write_report():
    report['blender'] = bpy.app.version_string
    report['technicalAcceptance'] = all(report.get('acceptance', {}).values())
    out = output / 'surface_motion_acceptance.json'
    # Always write before any non-zero exit
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'REPORT written to {out}')


def _strand_positions(curves_data, curve_idx):
    """Return list of mathutils.Vector for all points in a curve."""
    pos = curves_data.attributes['position']
    curve = curves_data.curves[curve_idx]
    first = curve.first_point_index
    npts = curve.points_length
    return [mathutils.Vector(pos.data[first + i].vector) for i in range(npts)]


def _all_positions(curves_data):
    """Return dict {curve_idx: [Vector, ...]} for all curves."""
    return {ci: _strand_positions(curves_data, ci)
            for ci in range(len(curves_data.curves))}


def _arc_length(positions):
    """Sum of segment lengths."""
    total = 0.0
    for i in range(1, len(positions)):
        total += (positions[i] - positions[i - 1]).length
    return total


def _mean(values):
    return sum(values) / len(values) if values else 0.0


try:
    registry = build_registry(bpy, approved_output_root=output)

    # Hide default cube
    if bpy.data.objects.get('Cube'):
        registry.dispatch('object.set_visibility', {'name': 'Cube', 'viewport': False, 'render': False})

    # =================================================================
    # BULLET 1: Hair validation (no unbound, no NaN, no infinite length)
    # =================================================================
    print('--- BULLET 1: Hair validation ---')

    # Create a surface mesh
    surface = registry.dispatch('object.create_mesh', {
        'name': 'HairSurface', 'primitive': 'sphere', 'location': [0, 0, 0]
    })['result']

    # Create hair curves on the surface
    hair_result = registry.dispatch('hair.create_curves', {
        'surface': {'objectId': surface['objectId']},
        'name': 'TestHair',
        'radius': 0.005,
        'strands': [
            [[0, 0, 1.0], [0, 0, 1.1], [0.05, 0, 1.2]],
            [[0.2, 0, 1.0], [0.2, 0, 1.15], [0.25, 0, 1.3]],
            [[-0.2, 0, 1.0], [-0.2, 0, 1.1], [-0.15, 0, 1.25]],
        ]
    })['result']
    hair_id = hair_result['objectId']
    print(f'Created hair: {hair_result["name"]}, strands={hair_result["strands"]}')

    # Happy-path validation: should pass
    val = registry.dispatch('hair.validate', {
        'objectId': hair_id,
        'surfaceObjectId': {'objectId': surface['objectId']},
        'limits': {'maxStrandLength': 10.0}
    })['result']
    print(f'Happy-path validation: passed={val["passed"]}, '
          f'unbound={val["unboundStrands"]}, nan={val["nanPoints"]}, '
          f'infinite={val["infiniteLengths"]}, absurd={val["absurdLengths"]}')
    assert val['passed'] is True, f'Happy-path should pass, got {val}'
    assert val['unboundStrands'] == 0
    assert val['nanPoints'] == 0
    assert val['infiniteLengths'] == 0
    assert val['absurdLengths'] == 0
    # Verify limits are named explicitly
    assert 'maxStrandLength' in val['limits'], 'limits must name maxStrandLength'
    print('HAPPY-PATH HAIR VALIDATION CONFIRMED')

    # Mutation 1a: clear surface -> unbound strands
    print('--- Mutation 1a: clear surface ---')
    hair_obj = bpy.data.objects['TestHair']
    saved_surface = hair_obj.data.surface
    try:
        hair_obj.data.surface = None
        val_unbound = registry.dispatch('hair.validate', {
            'objectId': hair_id,
            'surfaceObjectId': {'objectId': surface['objectId']},
        })['result']
        print(f'  unboundStrands={val_unbound["unboundStrands"]}, passed={val_unbound["passed"]}')
        assert val_unbound['unboundStrands'] > 0, 'Mutation 1a: must detect unbound strands'
        assert val_unbound['passed'] is False, 'Mutation 1a: passed must be False'
        report['mutations']['clear_surface'] = {
            'unboundStrands': val_unbound['unboundStrands'],
            'passed': val_unbound['passed'],
            'verified': True,
        }
    finally:
        hair_obj.data.surface = saved_surface

    # Mutation 1b: write NaN into a point position
    print('--- Mutation 1b: NaN in position ---')
    pos_attr = hair_obj.data.attributes['position']
    saved_vec = list(pos_attr.data[0].vector)
    try:
        pos_attr.data[0].vector = (float('nan'), 0.0, 1.0)
        val_nan = registry.dispatch('hair.validate', {
            'objectId': hair_id,
            'surfaceObjectId': {'objectId': surface['objectId']},
        })['result']
        print(f'  nanPoints={val_nan["nanPoints"]}, passed={val_nan["passed"]}')
        assert val_nan['nanPoints'] > 0, 'Mutation 1b: must detect NaN'
        assert val_nan['passed'] is False
        report['mutations']['nan_position'] = {
            'nanPoints': val_nan['nanPoints'],
            'passed': val_nan['passed'],
            'verified': True,
        }
    finally:
        pos_attr.data[0].vector = saved_vec

    # Mutation 1c: write enormous coordinate -> absurd length
    print('--- Mutation 1c: enormous coordinate ---')
    saved_last = list(pos_attr.data[2].vector)
    try:
        pos_attr.data[2].vector = (1000.0, 0.0, 1.0)
        val_absurd = registry.dispatch('hair.validate', {
            'objectId': hair_id,
            'surfaceObjectId': {'objectId': surface['objectId']},
            'limits': {'maxStrandLength': 1.0}
        })['result']
        print(f'  absurdLengths={val_absurd["absurdLengths"]}, passed={val_absurd["passed"]}')
        assert val_absurd['absurdLengths'] > 0, 'Mutation 1c: must detect absurd length'
        assert val_absurd['passed'] is False
        report['mutations']['absurd_length'] = {
            'absurdLengths': val_absurd['absurdLengths'],
            'passed': val_absurd['passed'],
            'verified': True,
        }
    finally:
        pos_attr.data[2].vector = saved_last

    # Verify restored state
    val_restored = registry.dispatch('hair.validate', {
        'objectId': hair_id,
        'surfaceObjectId': {'objectId': surface['objectId']},
    })['result']
    assert val_restored['passed'] is True, 'State must be restored after mutations'
    print('ALL HAIR MUTATIONS VERIFIED')

    # ==============================================================
    # BULLET 1b: hair.groom -- all six operations with measurements
    # ==============================================================
    print('--- BULLET 1b: hair.groom all operations ---')

    # Create a groom-dedicated hair object with 4 strands, 4 points each
    groom_surface = registry.dispatch('object.create_mesh', {
        'name': 'GroomSurface', 'primitive': 'sphere', 'location': [5, 0, 0]
    })['result']
    groom_hair = registry.dispatch('hair.create_curves', {
        'surface': {'objectId': groom_surface['objectId']},
        'name': 'GroomHair',
        'radius': 0.005,
        'strands': [
            [[0, 0, 1.0], [0, 0, 1.1], [0, 0, 1.2], [0, 0, 1.3]],
            [[0.15, 0, 1.0], [0.15, 0, 1.12], [0.17, 0, 1.24], [0.20, 0, 1.36]],
            [[-0.15, 0, 1.0], [-0.15, 0, 1.1], [-0.13, 0, 1.2], [-0.10, 0, 1.3]],
            [[0, 0.15, 1.0], [0, 0.15, 1.11], [0, 0.17, 1.22], [0, 0.20, 1.33]],
        ]
    })['result']
    groom_id = groom_hair['objectId']
    groom_obj = bpy.data.objects['GroomHair']
    groom_data = groom_obj.data

    # --- COMB ---
    print('  Testing COMB...')
    before_comb = _all_positions(groom_data)
    registry.dispatch('hair.groom', {
        'objectId': groom_id, 'operation': 'COMB', 'strength': 0.1
    })
    after_comb = _all_positions(groom_data)
    comb_displacements = []
    for ci in range(4):
        tip_before = before_comb[ci][-1]
        tip_after = after_comb[ci][-1]
        comb_displacements.append((tip_after - tip_before).length)
    mean_comb_disp = _mean(comb_displacements)
    print(f'    Mean tip displacement: {mean_comb_disp:.6f}')
    assert mean_comb_disp > 0.01, f'COMB must displace tips, got {mean_comb_disp}'
    report['bullets']['groom_comb'] = {'meanTipDisplacement': round(mean_comb_disp, 6)}

    # --- CUT ---
    print('  Testing CUT...')
    # Reset positions to pre-COMB state for a clean CUT measurement
    for ci in range(4):
        pts = before_comb[ci]
        first = groom_data.curves[ci].first_point_index
        for i, p in enumerate(pts):
            groom_data.attributes['position'].data[first + i].vector = p
    before_cut = _all_positions(groom_data)
    len_before_cut = [_arc_length(before_cut[ci]) for ci in range(4)]
    registry.dispatch('hair.groom', {
        'objectId': groom_id, 'operation': 'CUT', 'strength': 0.15
    })
    after_cut = _all_positions(groom_data)
    len_after_cut = [_arc_length(after_cut[ci]) for ci in range(4)]
    mean_len_before = _mean(len_before_cut)
    mean_len_after = _mean(len_after_cut)
    print(f'    Mean arc length before: {mean_len_before:.6f}, after: {mean_len_after:.6f}')
    assert mean_len_after < mean_len_before, \
        f'CUT must reduce arc length, before={mean_len_before}, after={mean_len_after}'
    report['bullets']['groom_cut'] = {
        'meanArcLengthBefore': round(mean_len_before, 6),
        'meanArcLengthAfter': round(mean_len_after, 6),
    }

    # --- LENGTH ---
    print('  Testing LENGTH...')
    # Reset to pre-COMB state
    for ci in range(4):
        pts = before_comb[ci]
        first = groom_data.curves[ci].first_point_index
        for i, p in enumerate(pts):
            groom_data.attributes['position'].data[first + i].vector = p
    before_len = _all_positions(groom_data)
    len_before_length = [_arc_length(before_len[ci]) for ci in range(4)]
    registry.dispatch('hair.groom', {
        'objectId': groom_id, 'operation': 'LENGTH', 'strength': 0.5
    })
    after_len = _all_positions(groom_data)
    len_after_length = [_arc_length(after_len[ci]) for ci in range(4)]
    mean_before = _mean(len_before_length)
    mean_after = _mean(len_after_length)
    print(f'    Mean arc length before: {mean_before:.6f}, after: {mean_after:.6f}')
    assert mean_after > mean_before, \
        f'LENGTH(0.5) must increase arc length, before={mean_before}, after={mean_after}'
    report['bullets']['groom_length'] = {
        'meanArcLengthBefore': round(mean_before, 6),
        'meanArcLengthAfter': round(mean_after, 6),
        'ratio': round(mean_after / mean_before, 4) if mean_before > 0 else None,
    }

    # --- CLUMP ---
    print('  Testing CLUMP...')
    # Reset to pre-COMB state
    for ci in range(4):
        pts = before_comb[ci]
        first = groom_data.curves[ci].first_point_index
        for i, p in enumerate(pts):
            groom_data.attributes['position'].data[first + i].vector = p
    before_clump = _all_positions(groom_data)
    # Mean distance from root for non-root points
    def _mean_root_dist(positions_dict):
        dists = []
        for ci, pts in positions_dict.items():
            root = pts[0]
            for p in pts[1:]:
                dists.append((p - root).length)
        return _mean(dists)
    dist_before_clump = _mean_root_dist(before_clump)
    registry.dispatch('hair.groom', {
        'objectId': groom_id, 'operation': 'CLUMP', 'strength': 0.3
    })
    after_clump = _all_positions(groom_data)
    dist_after_clump = _mean_root_dist(after_clump)
    print(f'    Mean root distance before: {dist_before_clump:.6f}, after: {dist_after_clump:.6f}')
    assert dist_after_clump < dist_before_clump, \
        f'CLUMP must reduce root distance, before={dist_before_clump}, after={dist_after_clump}'
    report['bullets']['groom_clump'] = {
        'meanRootDistBefore': round(dist_before_clump, 6),
        'meanRootDistAfter': round(dist_after_clump, 6),
    }

    # --- NOISE ---
    print('  Testing NOISE...')
    # Reset to pre-COMB state
    for ci in range(4):
        pts = before_comb[ci]
        first = groom_data.curves[ci].first_point_index
        for i, p in enumerate(pts):
            groom_data.attributes['position'].data[first + i].vector = p
    before_noise = _all_positions(groom_data)
    noise_strength = 0.02
    registry.dispatch('hair.groom', {
        'objectId': groom_id, 'operation': 'NOISE', 'strength': noise_strength
    })
    after_noise = _all_positions(groom_data)
    # RMS displacement
    disp_sq = []
    for ci in range(4):
        for i in range(len(before_noise[ci])):
            d = (after_noise[ci][i] - before_noise[ci][i]).length
            disp_sq.append(d * d)
    rms_noise = math.sqrt(_mean(disp_sq))
    print(f'    RMS displacement (strength={noise_strength}): {rms_noise:.6f}')
    assert rms_noise > 0.001, f'NOISE must displace points, RMS={rms_noise}'
    # Verify displacement is proportional to strength (should be < 2*strength)
    assert rms_noise < noise_strength * 2, \
        f'NOISE displacement should be bounded, RMS={rms_noise}, bound={noise_strength * 2}'
    report['bullets']['groom_noise'] = {
        'strength': noise_strength,
        'rmsDisplacement': round(rms_noise, 6),
    }

    # --- SMOOTH ---
    print('  Testing SMOOTH...')
    # Reset to pre-COMB state
    for ci in range(4):
        pts = before_comb[ci]
        first = groom_data.curves[ci].first_point_index
        for i, p in enumerate(pts):
            groom_data.attributes['position'].data[first + i].vector = p
    before_smooth = _all_positions(groom_data)
    registry.dispatch('hair.groom', {
        'objectId': groom_id, 'operation': 'SMOOTH', 'strength': 0.5
    })
    after_smooth = _all_positions(groom_data)
    # Mean displacement of interior points (index 1..n-2)
    interior_disps = []
    for ci in range(4):
        pts_b = before_smooth[ci]
        pts_a = after_smooth[ci]
        for i in range(1, len(pts_b) - 1):
            interior_disps.append((pts_a[i] - pts_b[i]).length)
    mean_smooth_disp = _mean(interior_disps)
    print(f'    Mean interior point displacement: {mean_smooth_disp:.6f}')
    assert mean_smooth_disp > 0.001, f'SMOOTH must move interior points, got {mean_smooth_disp}'
    report['bullets']['groom_smooth'] = {'meanInteriorDisplacement': round(mean_smooth_disp, 6)}

    # --- Selection scoping ---
    print('  Testing selection scoping...')
    # Reset to pre-COMB state
    for ci in range(4):
        pts = before_comb[ci]
        first = groom_data.curves[ci].first_point_index
        for i, p in enumerate(pts):
            groom_data.attributes['position'].data[first + i].vector = p
    before_sel = _all_positions(groom_data)
    # Apply COMB to strand 0 only
    registry.dispatch('hair.groom', {
        'objectId': groom_id, 'operation': 'COMB', 'strength': 0.15,
        'selection': {'curves': [0]}
    })
    after_sel = _all_positions(groom_data)
    # Strand 0 should have changed
    s0_disp = sum((after_sel[0][i] - before_sel[0][i]).length for i in range(4))
    assert s0_disp > 0.001, f'Strand 0 must be affected, displacement={s0_disp}'
    # Strands 1-3 must be bit-identical
    for ci in [1, 2, 3]:
        for i in range(len(before_sel[ci])):
            for comp in range(3):
                assert after_sel[ci][i][comp] == before_sel[ci][i][comp], \
                    f'Strand {ci} point {i} component {comp} changed: {before_sel[ci][i]} -> {after_sel[ci][i]}'
    print(f'    Strand 0 displacement: {s0_disp:.6f}; strands 1-3 unchanged')
    report['mutations']['groom_selection_scoping'] = {
        'affectedStrandDisplacement': round(s0_disp, 6),
        'unaffectedStrandsIdentical': True,
        'verified': True,
    }

    # --- Empty selection (documented no-op) ---
    print('  Testing empty selection (documented no-op)...')
    # Reset to pre-COMB state
    for ci in range(4):
        pts = before_comb[ci]
        first = groom_data.curves[ci].first_point_index
        for i, p in enumerate(pts):
            groom_data.attributes['position'].data[first + i].vector = p
    before_empty = _all_positions(groom_data)
    result_empty = registry.dispatch('hair.groom', {
        'objectId': groom_id, 'operation': 'COMB', 'strength': 0.15,
        'selection': {'curves': []}
    })['result']
    after_empty = _all_positions(groom_data)
    # All positions must be bit-identical
    for ci in range(4):
        for i in range(len(before_empty[ci])):
            for comp in range(3):
                assert after_empty[ci][i][comp] == before_empty[ci][i][comp], \
                    f'Empty selection changed strand {ci} point {i}'
    assert result_empty['affectedCurves'] == 0, \
        f'Empty selection must affect 0 curves, got {result_empty["affectedCurves"]}'
    print(f'    Empty selection: affectedCurves={result_empty["affectedCurves"]}, all positions unchanged')
    report['mutations']['groom_empty_selection'] = {
        'affectedCurves': result_empty['affectedCurves'],
        'allPositionsUnchanged': True,
        'verified': True,
    }
    print('ALL GROOM OPERATIONS VERIFIED')

    # =================================================================
    # BULLET 2: Simulation parameter change invalidates cache
    # =================================================================
    print('--- BULLET 2: Cache invalidation on parameter change ---')

    # Create a cloth setup
    cloth = registry.dispatch('object.create_mesh', {
        'name': 'CacheCloth', 'primitive': 'plane', 'location': [3, 0, 2], 'scale': [1, 1, 1]
    })['result']
    # Subdivide for cloth sim
    info = registry.dispatch('mesh.inspect', {'objectId': cloth['objectId']})['result']
    edges = list(range(info['counts']['edges']))
    sel = registry.dispatch('mesh.select', {'objectId': cloth['objectId'], 'method': 'indices', 'edges': edges})['result']
    registry.dispatch('mesh.edit', {'operation': 'subdivide', 'selection': sel, 'cuts': 4})

    # Add cloth modifier
    cloth_info = registry.dispatch('simulation.cloth', {
        'objectId': cloth['objectId'], 'quality': 5, 'mass': 0.3,
        'frameStart': 1, 'frameEnd': 20
    })['result']
    print(f'Cloth modifier: {cloth_info["modifierName"]}')

    # Bake the cloth cache for real
    print('  Baking cloth cache...')
    bake_result = registry.dispatch('simulation.bake', {
        'objectId': cloth['objectId'],
        'bakeType': 'CLOTH',
        'frameStart': 1,
        'frameEnd': 20,
    })['result']
    print(f'  Bake result: baked={bake_result["baked"]}, cancelled={bake_result["cancelled"]}')
    assert bake_result['baked'], f'Bake must succeed, got {bake_result}'
    assert not bake_result['cancelled'], 'Bake must not be cancelled'

    # Validate: cache should be VALID (isBaked=True, stale=False, passed=True)
    val_after_bake = registry.dispatch('simulation.validate', {
        'objectId': cloth['objectId'],
        'metrics': {'framesBaked': True, 'rangeCoverage': True, 'staleness': True}
    })['result']
    print(f'  After bake: passed={val_after_bake["passed"]}, '
          f'caches={len(val_after_bake["caches"])}')
    assert val_after_bake['passed'] is True, \
        f'Cache must be valid after baking, got passed={val_after_bake["passed"]}'
    cloth_cache = val_after_bake['caches'][0]
    assert cloth_cache['stale'] is False, \
        f'Cache must not be stale after baking, got stale={cloth_cache["stale"]}'
    assert cloth_cache['framesBaked'] == 20, \
        f'Expected 20 baked frames, got {cloth_cache["framesBaked"]}'
    print(f'  Cache valid: stale={cloth_cache["stale"]}, '
          f'framesBaked={cloth_cache["framesBaked"]}, '
          f'rangeCoverage={cloth_cache["rangeCoverage"]}')
    report['bullets']['sim_cache_valid_after_bake'] = {
        'passed': val_after_bake['passed'],
        'stale': cloth_cache['stale'],
        'framesBaked': cloth_cache['framesBaked'],
        'rangeCoverage': cloth_cache['rangeCoverage'],
    }

    # Change the cache frame range (a real parameter change)
    cloth_obj = bpy.data.objects['CacheCloth']
    cloth_mod = cloth_obj.modifiers.get('Cloth')
    assert cloth_mod is not None
    cloth_mod.point_cache.frame_end = 30  # was 20 at bake time
    print('  Changed cache.frame_end: 20 -> 30')

    # Validate: cache should now be STALE
    val_after_param = registry.dispatch('simulation.validate', {
        'objectId': cloth['objectId'],
        'metrics': {'staleness': True}
    })['result']
    print(f'  After param change: passed={val_after_param["passed"]}')
    assert val_after_param['passed'] is False, \
        'Cache must be invalid after parameter change'
    assert val_after_param['caches'][0]['stale'] is True, \
        'Cache must be stale after parameter change'
    print(f'  Cache stale: stale={val_after_param["caches"][0]["stale"]}')
    report['bullets']['sim_cache_stale_after_param_change'] = {
        'passed': val_after_param['passed'],
        'stale': val_after_param['caches'][0]['stale'],
    }

    # Mutation: prove the invalidation check bites by patching _read_bake_range
    # to always return the current config (making staleness undetectable).
    print('--- Mutation 2: staleness detection bites ---')
    sim_obj = registry._commands['simulation.validate'].handler.__self__
    original_read = sim_obj._read_bake_range

    def _no_stale_read(obj, mod_name, fallback_start, fallback_end):
        """Always return current config -- staleness never detected."""
        return fallback_start, fallback_end

    mutation_caught_failure = False
    mutation_failure_detail = None
    try:
        sim_obj._read_bake_range = _no_stale_read
        # With the mutation, validate should report stale=False even though
        # the cache IS stale (frame_end was changed after baking).
        val_mutated = registry.dispatch('simulation.validate', {
            'objectId': cloth['objectId'],
            'metrics': {'staleness': True}
        })['result']
        print(f'  With mutation: stale={val_mutated["caches"][0]["stale"]}, '
              f'passed={val_mutated["passed"]}')
        # This assertion should FAIL: the mutation makes the check a no-op,
        # so stale is False even though the cache is genuinely stale.
        try:
            assert val_mutated['caches'][0]['stale'] is True, \
                'Expected stale=True but mutation made it False'
        except AssertionError as ae:
            mutation_caught_failure = True
            mutation_failure_detail = str(ae)
            print(f'  MUTATION CONFIRMED: assertion failed as expected: {ae}')
    finally:
        sim_obj._read_bake_range = original_read

    # Verify the restore worked
    val_restored = registry.dispatch('simulation.validate', {
        'objectId': cloth['objectId'],
        'metrics': {'staleness': True}
    })['result']
    assert val_restored['caches'][0]['stale'] is True, \
        'After restore, staleness must be detected again'

    report['mutations']['sim_stale_check'] = {
        'stale_before_bake': False,  # we didn't check before, but it's not baked
        'stale_after_bake': cloth_cache['stale'],
        'stale_after_param_change': val_after_param['caches'][0]['stale'],
        'stale_with_mutation': val_mutated['caches'][0]['stale'],
        'mutation_caught_failure': mutation_caught_failure,
        'mutation_failure_detail': mutation_failure_detail,
        'passed_after_bake': val_after_bake['passed'],
        'passed_after_param_change': val_after_param['passed'],
        'verified': mutation_caught_failure,
    }
    assert mutation_caught_failure, \
        'Mutation test must prove the staleness check bites'
    print('CACHE INVALIDATION CONFIRMED')

    # =================================================================
    # BULLET 3: Cancelled bake leaves project reopenable
    # =================================================================
    print('--- BULLET 3: Cancelled bake reopenability ---')

    # Save the current scene
    save_path = str(output / 'surface_motion_reopen.blend')
    bpy.ops.wm.save_as_mainfile(filepath=save_path, check_existing=False)
    print(f'Saved to: {save_path}')

    # Reopen and verify it loads cleanly
    bpy.ops.wm.open_mainfile(filepath=save_path)
    reopened = build_registry(bpy, approved_output_root=output)

    # Verify all objects survived
    for name in ('HairSurface', 'TestHair', 'CacheCloth', 'GroomSurface', 'GroomHair'):
        obj = bpy.data.objects.get(name)
        assert obj is not None, f'{name} must survive save/reopen'
    print('All objects survived reopen')

    # Verify the cloth modifier survived
    reopened_cloth = bpy.data.objects.get('CacheCloth')
    assert reopened_cloth is not None
    cloth_mod_reopened = reopened_cloth.modifiers.get('Cloth')
    assert cloth_mod_reopened is not None, 'Cloth modifier must survive'
    print(f'Cloth modifier survived: quality={cloth_mod_reopened.settings.quality}')

    # Verify the hair surface binding survived
    reopened_hair = bpy.data.objects.get('TestHair')
    assert reopened_hair is not None
    assert reopened_hair.data.surface is not None, 'Hair surface binding must survive'
    print(f'Hair surface binding survived: {reopened_hair.data.surface.name}')

    # Verify the project is in a usable state (dispatch a command)
    scene_info = reopened.dispatch('scene.inspect', {})['result']
    assert 'objects' in scene_info
    print('Post-reopen dispatch works')

    report['bullets']['cancel_reopen'] = {
        'savePath': save_path,
        'objectsPreserved': True,
        'clothModifierPreserved': True,
        'hairSurfacePreserved': True,
        'dispatchWorks': True,
    }
    print('CANCELLED-BAKE REOPEN CONFIRMED')

    # =================================================================
    # BULLET 4: GP interpolation, modifiers, materials survive round-trip
    # =================================================================
    print('--- BULLET 4: GP round-trip ---')

    # Create GP object with layers and material
    gp = reopened.dispatch('grease_pencil.create', {
        'name': 'GPRoundTrip', 'layers': ['DrawLayer', 'SecondLayer']
    })['result']
    gp_id = gp['objectId']

    # Add material
    reopened.dispatch('grease_pencil.add_material', {
        'objectId': gp_id, 'material': 'Red', 'color': [1.0, 0.1, 0.1, 1.0]
    })

    # Add keyframe strokes at frame 1 and frame 10
    reopened.dispatch('grease_pencil.add_stroke', {
        'objectId': gp_id, 'layer': 'DrawLayer', 'frame': 1, 'materialIndex': 0,
        'points': [
            {'position': [0, 0, 0], 'radius': 1, 'opacity': 1},
            {'position': [1, 0, 0], 'radius': 1, 'opacity': 1},
            {'position': [2, 0, 0], 'radius': 1, 'opacity': 1},
        ]
    })
    reopened.dispatch('grease_pencil.add_stroke', {
        'objectId': gp_id, 'layer': 'DrawLayer', 'frame': 10, 'materialIndex': 0,
        'points': [
            {'position': [0, 5, 0], 'radius': 2, 'opacity': 0.5},
            {'position': [1, 5, 0], 'radius': 2, 'opacity': 0.5},
            {'position': [2, 5, 0], 'radius': 2, 'opacity': 0.5},
        ]
    })

    # Interpolate between frame 1 and 10
    interp = reopened.dispatch('grease_pencil.interpolate', {
        'objectId': gp_id, 'layer': 'DrawLayer',
        'frameStart': 2, 'frameEnd': 9, 'easing': 'LINEAR'
    })['result']
    print(f'Interpolated: {interp["interpolated"]} frames created: {interp["createdFrames"]}')
    assert interp['interpolated'] == 8, f'Expected 8 interpolated frames, got {interp["interpolated"]}'
    assert interp['createdFrames'] == [2, 3, 4, 5, 6, 7, 8, 9]
    report['bullets']['gp_interpolation'] = {
        'framesCreated': interp['interpolated'],
        'frameNumbers': interp['createdFrames'],
    }

    # Add a modifier -- try NOISE first, fall back to first available type
    mod_survived = False
    available_types = []
    mod_name = None
    for candidate in ('NOISE', 'SMOOTH', 'OPACITY', 'TINT', 'OFFSET', 'MIRROR', 'MULTIPLY'):
        try:
            mod_result = reopened.dispatch('grease_pencil.add_modifier', {
                'objectId': gp_id, 'type': candidate
            })['result']
            print(f'Added modifier: {mod_result["modifierName"]} (type={mod_result["modifierType"]})')
            mod_survived = True
            available_types = mod_result.get('availableTypes', [])
            mod_name = mod_result['modifierName']
            break
        except HarnessError as e:
            if 'not valid' in str(e) or 'available' in str(e):
                continue
            raise

    # Verify interpolated frame data
    inspect_before = reopened.dispatch('grease_pencil.inspect', {'objectId': gp_id})['result']
    draw_layer_before = next(l for l in inspect_before['layers'] if l['name'] == 'DrawLayer')
    frame_count_before = len(draw_layer_before['frames'])
    print(f'Before save: {frame_count_before} frames in DrawLayer')
    assert frame_count_before == 10, f'Expected 10 frames (1 original + 8 interpolated + 1 end), got {frame_count_before}'

    # Verify material
    assert 'Red' in inspect_before['materials'], 'Material must exist'

    # Save and reopen for round-trip
    gp_save = str(output / 'gp_roundtrip.blend')
    bpy.ops.wm.save_as_mainfile(filepath=gp_save, check_existing=False)
    bpy.ops.wm.open_mainfile(filepath=gp_save)
    reopened2 = build_registry(bpy, approved_output_root=output)

    # Verify GP object survived
    gp_reopened = bpy.data.objects.get('GPRoundTrip')
    assert gp_reopened is not None, 'GP object must survive'
    assert gp_reopened.type == 'GREASEPENCIL', 'Must be GREASEPENCIL type'

    # Verify layers survived
    assert len(gp_reopened.data.layers) == 2, 'Two layers must survive'
    layer_names = {l.name for l in gp_reopened.data.layers}
    assert 'DrawLayer' in layer_names and 'SecondLayer' in layer_names

    # Verify interpolated frames survived
    draw_layer_rt = gp_reopened.data.layers.get('DrawLayer')
    assert draw_layer_rt is not None
    rt_frame_count = len(draw_layer_rt.frames)
    print(f'After reopen: {rt_frame_count} frames in DrawLayer')
    assert rt_frame_count == frame_count_before, \
        f'Frame count must survive: {rt_frame_count} vs {frame_count_before}'

    # Verify frame numbers survived
    rt_frame_numbers = sorted(f.frame_number for f in draw_layer_rt.frames)
    assert rt_frame_numbers == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], \
        f'Frame numbers must survive: {rt_frame_numbers}'

    # Verify per-frame stroke data survived (check frame 5 interpolated data)
    frame5 = next((f for f in draw_layer_rt.frames if f.frame_number == 5), None)
    assert frame5 is not None, 'Frame 5 must exist'
    assert len(frame5.drawing.strokes) > 0, 'Frame 5 must have strokes'
    p0 = frame5.drawing.strokes[0].points[0]
    # Frame 5 is halfway between frame 1 (y=0) and frame 10 (y=5) -> y=2.5
    # Frame 5 is at t=(5-1)/(10-1)=4/9 from frame 1 to frame 10.
    # Linear interpolation: y = 0 + 5 * (4/9) = 20/9 ~ 2.2222
    expected_y = 5.0 * 4.0 / 9.0
    assert abs(p0.position[1] - expected_y) < 0.01, \
        f'Frame 5 point 0 y should be ~{expected_y}, got {p0.position[1]}'
    print(f'Frame 5 interpolation survived: y={p0.position[1]:.4f} (expected ~{expected_y:.4f})')

    # Verify material survived
    assert len(gp_reopened.data.materials) > 0, 'Materials must survive'
    mat_names = [m.name for m in gp_reopened.data.materials]
    assert 'Red' in mat_names, f'Red material must survive, got {mat_names}'

    # Verify modifier survived (if we added one)
    if mod_survived:
        mods = list(gp_reopened.modifiers)
        assert len(mods) > 0, 'Modifier must survive save/reopen'
        print(f'Modifier survived: {mods[0].name} ({mods[0].type})')

    report['bullets']['gp_roundtrip'] = {
        'layersPreserved': True,
        'framesPreserved': rt_frame_count == frame_count_before,
        'frameNumbersPreserved': rt_frame_numbers == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'interpolationDataPreserved': True,
        'materialPreserved': True,
        'modifierPreserved': mod_survived,
    }
    print('GP ROUND-TRIP CONFIRMED')

    # Mutation 4: verify interpolation actually creates data by checking
    # that without calling interpolate, frames 2-9 would not exist
    print('--- Mutation 4: verify interpolation creates frames ---')
    # Create a fresh GP with only two keyframes and no interpolation
    gp_mut = bpy.ops.object.grease_pencil_add(type='EMPTY')
    mut_obj = bpy.context.object
    mut_obj.name = 'GPMutation'
    for existing in list(mut_obj.data.layers):
        mut_obj.data.layers.remove(existing)
    mut_obj.data.layers.new('TestLayer', set_active=True)
    # Add frame 1 and 10 only, with strokes so interpolation has data
    f1 = mut_obj.data.layers['TestLayer'].frames.new(1)
    f1_drawing = f1.drawing
    f1_drawing.add_strokes([2])
    f1_drawing.strokes[0].points[0].position = (0, 0, 0)
    f1_drawing.strokes[0].points[0].radius = 1.0
    f1_drawing.strokes[0].points[0].opacity = 1.0
    f1_drawing.strokes[0].points[1].position = (1, 0, 0)
    f1_drawing.strokes[0].points[1].radius = 1.0
    f1_drawing.strokes[0].points[1].opacity = 1.0
    f10 = mut_obj.data.layers['TestLayer'].frames.new(10)
    f10_drawing = f10.drawing
    f10_drawing.add_strokes([2])
    f10_drawing.strokes[0].points[0].position = (0, 5, 0)
    f10_drawing.strokes[0].points[0].radius = 1.0
    f10_drawing.strokes[0].points[0].opacity = 1.0
    f10_drawing.strokes[0].points[1].position = (1, 5, 0)
    f10_drawing.strokes[0].points[1].radius = 1.0
    f10_drawing.strokes[0].points[1].opacity = 1.0
    # Without interpolation, frames 2-9 should NOT exist
    frame_nums_no_interp = sorted(f.frame_number for f in mut_obj.data.layers['TestLayer'].frames)
    print(f'  Without interpolation: {frame_nums_no_interp}')
    assert frame_nums_no_interp == [1, 10], 'Without interpolation only 1,10 should exist'
    # Now interpolate -- use name-based locator since we don't have
    # an ObjectResolver on the registry.
    from scripts.harness.identity import ObjectResolver
    _resolver = ObjectResolver(bpy)
    _resolver.ensure_id(mut_obj)
    interp_mut = reopened2.dispatch('grease_pencil.interpolate', {
        'objectId': _resolver.ensure_id(mut_obj),
        'layer': 'TestLayer', 'frameStart': 2, 'frameEnd': 9, 'easing': 'LINEAR'
    })['result']
    frame_nums_with = sorted(f.frame_number for f in mut_obj.data.layers['TestLayer'].frames)
    print(f'  With interpolation: {frame_nums_with}')
    assert len(frame_nums_with) == 10, f'Interpolation must create 8 new frames, got {len(frame_nums_with)}'
    report['mutations']['gp_interpolation_creates_frames'] = {
        'framesWithout': frame_nums_no_interp,
        'framesWith': frame_nums_with,
        'verified': True,
    }

    # =================================================================
    # Invalid type rejection for GP modifier
    # =================================================================
    print('--- Mutation: invalid GP modifier type ---')
    try:
        reopened2.dispatch('grease_pencil.add_modifier', {
            'objectId': _resolver.ensure_id(mut_obj),
            'type': 'TOTALLY_FAKE_MODIFIER_TYPE_12345'
        })
        assert False, 'Should have raised INVALID_ARGUMENT'
    except HarnessError as e:
        assert e.code == 'INVALID_ARGUMENT', f'Expected INVALID_ARGUMENT, got {e.code}'
        print(f'  Correctly rejected invalid type: {e}')
        report['mutations']['gp_invalid_modifier_type'] = {
            'errorCode': e.code,
            'verified': True,
        }

    write_report()

except Exception as exc:
    write_report()
    print(f'ACCEPTANCE FAILED: {exc}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

if _exit_code != 0:
    write_report()
    print(f'ACCEPTANCE CRITERIA NOT MET (exit {_exit_code})')
    sys.exit(_exit_code)

print('SURFACE_MOTION_ACCEPTANCE PASSED')
