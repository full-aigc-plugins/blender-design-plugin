"""Drive the 5 foreground-only lifecycle commands over a live session.

These commands require a VIEW_3D area that background mode cannot provide,
so they are exercised against a foreground Blender session via the Harness
transport.  This script is the foreground sibling of
``lifecycle_commands_acceptance.py`` (which covers the 13 commands that
work in background mode).

Usage (opt-in; never discovered by unittest):
    python3 tests/runtime/foreground_lifecycle_acceptance.py \
        --descriptor <runtime-dir>/<session-id>.json \
        --report <report.json> \
        [--output-root <dir>]

The ``--output-root`` is where preview.capture writes milestone PNGs.
If omitted the script uses the output root from the descriptor.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.managed_launcher import load_descriptor
from scripts.harness.transport import Endpoint, send_request

# ---------------------------------------------------------------------------
# Commands that graduate to L3 with foreground runtime evidence.
# ---------------------------------------------------------------------------
GRADUATED = [
    'view.set',
    'view.focus',
    'view.present',
    'playback.set',
    'preview.capture',
]


def run_acceptance(descriptor_path: Path, report_path: Path,
                   output_root: Path | None = None) -> dict:
    """Exercise each foreground command and write a machine-readable report."""
    descriptor = load_descriptor(descriptor_path)
    endpoint = Endpoint(descriptor['transport'], descriptor['address'])
    token = descriptor['token']
    records: list[dict] = []
    errors: list[dict] = []
    results: dict[str, dict] = {}
    revision = 0
    tx = 'fg-accept-' + uuid.uuid4().hex[:8]

    def call(command, arguments=None, expect=None):
        """Send one command; return the result dict.

        Each ``transaction.begin`` starts a fresh transaction, so ``tx`` is
        rotated before begin/commit sequences (same pattern as
        foreground_smoke.py).
        """
        nonlocal revision, tx
        # Each transaction.begin must carry a fresh id.
        if command == 'transaction.begin':
            tx = 'fg-accept-' + uuid.uuid4().hex[:8]
        payload = {
            'protocolVersion': 'codex-blender/v1',
            'sessionId': descriptor['sessionId'],
            'requestId': str(uuid.uuid4()),
            'transactionId': tx,
            'command': command,
            'arguments': arguments or {},
            'expectedSceneRevision': revision,
        }
        result = send_request(endpoint, token, payload, timeout=30)
        status = result.get('status')
        error = result.get('error')
        new_rev = result.get('sceneRevision', revision)
        records.append({
            'command': command,
            'status': status,
            'error': error,
            'sceneRevision': new_rev,
        })
        if expect:
            assert (error or {}).get('code') == expect, \
                f'{command}: expected {expect}, got {result}'
        else:
            assert status == 'succeeded', \
                f'{command}: expected succeeded, got {result}'
        revision = new_rev
        return result

    # Determine output root for preview.capture.
    if output_root is None:
        output_root = Path(descriptor.get('outputRoot', '/tmp/fg-acceptance'))

    # ---- view.set: exercise multiple orientations ----
    for orientation in ('FRONT', 'SIDE', 'TOP', 'CAMERA'):
        call('view.set', {'view': orientation})
    results['view.set'] = {
        'views_exercised': ['FRONT', 'SIDE', 'TOP', 'CAMERA'],
        'count': 4,
    }

    # ---- view.focus ----
    # Create a throwaway object so view.focus has something to target.
    call('transaction.begin')
    call('object.create_mesh', {'primitive': 'cube', 'name': 'FgAcceptFocusTarget'})
    call('transaction.commit')
    call('view.focus', {'object': 'FgAcceptFocusTarget'})
    results['view.focus'] = {'target': 'FgAcceptFocusTarget'}

    # ---- view.present ----
    r = call('view.present')
    window_count = r.get('result', {}).get('windowCount', 0)
    results['view.present'] = {'windowCount': window_count}

    # ---- playback.set ----
    r_on = call('playback.set', {'playing': True})
    r_off = call('playback.set', {'playing': False})
    results['playback.set'] = {
        'start_playing': r_on.get('result', {}).get('playing'),
        'stop_playing': r_off.get('result', {}).get('playing'),
    }

    # ---- preview.capture ----
    # Needs a committed snapshot: transaction.begin -> object.create ->
    # transaction.commit -> preview.capture.
    call('transaction.begin')
    call('object.create_mesh', {'primitive': 'cube', 'name': 'FgAcceptPreview'})
    tx_result = call('transaction.commit')
    snapshot_id = tx_result.get('snapshotId', '')
    assert snapshot_id, 'transaction.commit did not return a snapshotId'

    r = call('preview.capture', {
        'snapshotId': snapshot_id,
        'milestone': 'foreground-certification',
        'width': 256,
        'height': 256,
    })
    milestone = (r.get('result') or {}).get('milestone', {})
    views = milestone.get('views', [])
    view_info = [{'name': v['name'], 'sha256': v['sha256']} for v in views]
    results['preview.capture'] = {
        'status': r.get('status'),
        'snapshotId': snapshot_id,
        'views': view_info,
    }

    # ---- Build report ----
    report = {
        'blender': descriptor.get('blender', None),
        'platform': sys.platform,
        'architecture': os.uname().machine if hasattr(os, 'uname') else 'unknown',
        'background': False,
        'sessionId': descriptor['sessionId'],
        'graduatedCommands': len(GRADUATED),
        'executedCommands': len(results),
        'skippedCommands': 0,
        'results': results,
        'commands': records,
        'errors': errors,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({
        'passed': len(errors) == 0,
        'commands': len(results),
        'errors': len(errors),
        'sessionId': descriptor['sessionId'],
    }))
    return report


def main():
    parser = argparse.ArgumentParser(
        description='Foreground lifecycle command acceptance')
    parser.add_argument('--descriptor', required=True,
                        help='Path to session descriptor JSON')
    parser.add_argument('--report', required=True,
                        help='Path to write the acceptance report JSON')
    parser.add_argument('--output-root',
                        help='Output root for preview capture (default: from descriptor)')
    args = parser.parse_args()

    descriptor_path = Path(args.descriptor)
    report_path = Path(args.report)
    output_root = Path(args.output_root) if args.output_root else None

    report = run_acceptance(descriptor_path, report_path, output_root)
    if report['errors']:
        print(f'FAILURES: {len(report["errors"])} command(s) failed',
              file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
