"""Run in an isolated Blender process, never against a user's open project.

Exercises the core lifecycle and introspection commands that graduate from
L1 to L3 in the production profile.  Foreground-only commands (view.set,
view.focus, view.present, playback.set, preview.capture) are explicitly
skipped because they require a VIEW_3D area that background mode cannot
provide.

Usage:
    blender --background --factory-startup --python-exit-code 1 \
        --python tests/runtime/lifecycle_commands_acceptance.py -- <evidence-dir>
"""
import json
import os
import struct
import sys
import tempfile
import zlib
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.harness.runtime import build_registry

# ---------------------------------------------------------------------------
# Commands that graduate to L3 with runtime evidence from this script.
# ---------------------------------------------------------------------------
GRADUATED = [
    'capability.list',
    'capability.describe',
    'session.status',
    'session.capabilities',
    'session.pause',
    'session.resume',
    'session.set_progress',
    'scene.inspect',
    'object.create_curve',
    'object.create_text',
    'material.attach_image_texture',
    'playback.set_frame',
    'production.status',
]

# Foreground-only: cannot run in --background; recorded as skipped.
FOREGROUND_ONLY = {
    'view.set', 'view.focus', 'view.present',
    'playback.set',
    'preview.capture',
}


def _make_minimal_png(path: Path) -> None:
    """Write a 1x1 red pixel PNG so bpy.data.images.load can read it."""
    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)  # 1x1 RGB 8-bit
    raw = b'\x00\xff\x00\x00'  # filter-byte + red pixel
    idat = zlib.compress(raw)
    with path.open('wb') as f:
        f.write(sig)
        f.write(_chunk(b'IHDR', ihdr))
        f.write(_chunk(b'IDAT', idat))
        f.write(_chunk(b'IEND', b''))


def run_acceptance(evidence_dir: Path) -> dict:
    """Exercise each graduated command and write per-command evidence."""
    asset_root = Path(tempfile.mkdtemp(prefix='lifecycle-asset-'))
    try:
        _make_minimal_png(asset_root / 'test.png')
        registry = build_registry(
            bpy,
            approved_output_root=evidence_dir,
            approved_asset_roots=[asset_root],
        )

        results = {}
        skipped = {}
        errors = []

        def _run(name, fn):
            """Run fn(); capture the result or record the error."""
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                errors.append({'command': name, 'error': str(exc)})
                return None

        # --- capability.list ---
        r = _run('capability.list', lambda: registry.dispatch('capability.list', {'limit': 100}))
        if r is not None:
            items = r['result']['items']
            results['capability.list'] = {'count': len(items), 'domains': len(r['result'].get('domains', {}))}

        # --- capability.describe ---
        r = _run('capability.describe', lambda: registry.dispatch('capability.describe', {'id': 'object.transform'}))
        if r is not None:
            results['capability.describe'] = {'id': r['result']['id'], 'maturity': r['result']['maturity']}

        # --- session.status ---
        r = _run('session.status', lambda: registry.dispatch('session.status', {}))
        if r is not None:
            results['session.status'] = r['result']

        # --- session.capabilities ---
        r = _run('session.capabilities', lambda: registry.dispatch('session.capabilities', {}))
        if r is not None:
            results['session.capabilities'] = {'commandCount': len(r['result']['commands'])}

        # --- session.pause ---
        r = _run('session.pause', lambda: registry.dispatch('session.pause', {}))
        if r is not None:
            results['session.pause'] = {'status': 'succeeded'}

        # --- session.resume ---
        r = _run('session.resume', lambda: registry.dispatch('session.resume', {}))
        if r is not None:
            results['session.resume'] = {'status': 'succeeded'}

        # --- session.set_progress ---
        r = _run('session.set_progress', lambda: registry.dispatch('session.set_progress', {'stage': 'lifecycle_acceptance', 'progress': 0.5}))
        if r is not None:
            results['session.set_progress'] = {'status': 'succeeded'}

        # --- scene.inspect ---
        r = _run('scene.inspect', lambda: registry.dispatch('scene.inspect', {}))
        if r is not None:
            results['scene.inspect'] = r['result']

        # --- object.create_curve ---
        r = _run('object.create_curve', lambda: registry.dispatch('object.create_curve', {'name': 'LifecycleTestCurve'}))
        if r is not None:
            results['object.create_curve'] = {'created': 'LifecycleTestCurve'}

        # --- object.create_text ---
        r = _run('object.create_text', lambda: registry.dispatch('object.create_text', {'name': 'LifecycleTestText', 'text': 'hello'}))
        if r is not None:
            results['object.create_text'] = {'created': 'LifecycleTestText'}

        # --- material.attach_image_texture ---
        bpy.data.materials.new(name='LifecycleTestMat')
        r = _run('material.attach_image_texture', lambda: registry.dispatch('material.attach_image_texture', {
            'material': 'LifecycleTestMat',
            'path': str(asset_root / 'test.png'),
        }))
        if r is not None:
            results['material.attach_image_texture'] = r['result']

        # --- playback.set_frame ---
        scene = bpy.context.scene
        scene.frame_start = 1
        scene.frame_end = 10
        r = _run('playback.set_frame', lambda: registry.dispatch('playback.set_frame', {'frame': 5}))
        if r is not None:
            results['playback.set_frame'] = r['result']

        # --- production.status ---
        r = _run('production.status', lambda: registry.dispatch('production.status', {}))
        if r is not None:
            ps = r['result']
            results['production.status'] = {
                'status': ps['status'],
                'l1CommandCount': len(ps.get('l1Commands', [])),
                'productionCommandCount': len(ps.get('productionCommands', [])),
                'blockedCommandCount': len(ps.get('blockedCommands', [])),
            }

        # Record foreground-only skips.
        for cmd in FOREGROUND_ONLY:
            skipped[cmd] = 'Requires foreground VIEW_3D area; blocked in background mode'

        report = {
            'blender': bpy.app.version_string,
            'platform': sys.platform,
            'architecture': os.uname().machine if hasattr(os, 'uname') else 'unknown',
            'background': bpy.app.background,
            'graduatedCommands': len(GRADUATED),
            'executedCommands': len(results),
            'skippedCommands': len(skipped),
            'results': results,
            'skipped': skipped,
            'errors': errors,
        }

        # Write evidence file (exclusive create).
        evidence_file = evidence_dir / 'lifecycle_acceptance.json'
        with evidence_file.open('x', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print('LIFECYCLE_ACCEPTANCE=' + json.dumps(report, ensure_ascii=False))
        return report

    finally:
        import shutil
        shutil.rmtree(asset_root, ignore_errors=True)


def main():
    if '--' not in sys.argv:
        print('ERROR: pass -- <evidence-dir> after the script path', file=sys.stderr)
        sys.exit(1)
    evidence_dir = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    report = run_acceptance(evidence_dir)
    if report['errors']:
        print(f'FAILURES: {len(report["errors"])} command(s) failed', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
