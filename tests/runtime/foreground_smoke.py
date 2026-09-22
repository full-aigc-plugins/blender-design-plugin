"""Opt-in real foreground smoke. Uses only the public Harness and new files.

Run with a freshly launched auto_with_budget session permitting blend export.
Never starts Blender, installs an addon, overwrites files or calls a cloud service.
"""
import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.harness.transport import Endpoint, send_request
from scripts.managed_launcher import load_descriptor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--descriptor', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--read-only', action='store_true')
    parser.add_argument('--present', action='store_true')
    args = parser.parse_args()
    descriptor = load_descriptor(Path(args.descriptor))
    endpoint = Endpoint(descriptor['transport'], descriptor['address'])
    records = []
    revision = 0
    tx = 'smoke-' + uuid.uuid4().hex[:8]

    def call(command, arguments=None, expect=None, request_id=None, authorization=None):
        nonlocal revision
        payload = {'protocolVersion':'codex-blender/v1','sessionId':descriptor['sessionId'],
                   'requestId':request_id or str(uuid.uuid4()),'transactionId':tx,'command':command,
                   'arguments':arguments or {},'expectedSceneRevision':revision}
        if authorization: payload['authorization'] = authorization
        result = send_request(endpoint, descriptor['token'], payload, timeout=30)
        if expect:
            assert result.get('error',{}).get('code') == expect, result
        else:
            assert result.get('status') == 'succeeded', result
        revision = result.get('sceneRevision', revision)
        records.append({'command':command,'status':result.get('status'),'error':result.get('error'),
                        'sceneRevision':revision})
        return result

    status = call('session.status')['result']
    before = call('scene.inspect')['result']
    if args.present:
        first=call('view.present')['result']
        second=call('view.present')['result']
        assert first['windowCount']==second['windowCount']
    if args.read_only:
        assert status['executionPolicy']['mode'] == 'review_only'
        call('object.create_mesh', {'primitive':'cube','name':'MustNotExist'}, expect='READ_ONLY_POLICY')
        call('export.file', {'path':str(Path(descriptor['outputRoot'])/'forbidden.blend'),'snapshotId':'none'},expect='READ_ONLY_POLICY')
        after = call('scene.inspect')['result']
        assert before['objects'] == after['objects']
        assert not (Path(descriptor['outputRoot'])/'forbidden.blend').exists()
    else:
        assert status['executionPolicy']['mode'] == 'auto_with_budget'
        call('session.set_progress', {'stage':'Foreground modeling','progress':.1})
        call('transaction.begin')
        call('object.create_mesh', {'primitive':'cube','name':'ForegroundDemo','location':[0,0,1]})
        call('material.create_pbr', {'name':'ForegroundOrange','baseColor':[.8,.23,.04,1]})
        call('material.assign', {'object':'ForegroundDemo','material':'ForegroundOrange'})
        call('animation.set_frame_range', {'start':1,'end':48})
        call('animation.insert_keyframe', {'object':'ForegroundDemo','dataPath':'location','frame':1})
        call('object.transform', {'name':'ForegroundDemo','location':[2,0,1]})
        call('animation.insert_keyframe', {'object':'ForegroundDemo','dataPath':'location','frame':48})
        call('transaction.commit')
        call('view.focus', {'object':'ForegroundDemo'})
        for view in ['FRONT','SIDE','TOP','CAMERA']:
            call('view.set', {'view':view})
        call('playback.set_frame', {'frame':1})
        assert call('playback.set', {'playing':True})['result']['playing'] is True
        assert call('playback.set', {'playing':True})['result']['playing'] is True
        assert call('playback.set', {'playing':False})['result']['playing'] is False
        call('session.pause')
        call('object.transform', {'name':'ForegroundDemo','location':[9,9,9]}, expect='SESSION_PAUSED')
        rid = str(uuid.uuid4())
        claim = call('session.authorize', {'action':'session.resume','requestId':rid,'userConfirmed':True})['result']['authorization']
        call('session.resume', request_id=rid, authorization=claim)
        call('object.transform', {'name':'ForegroundDemo','location':[9,9,9]}, expect='REINSPECTION_REQUIRED')
        call('scene.inspect')
        tx = 'export-' + uuid.uuid4().hex[:8]
        call('transaction.begin')
        snap = call('transaction.commit')['snapshotId']
        target = Path(descriptor['outputRoot'])/'foreground_demo.blend'
        result = call('export.file', {'path':str(target),'snapshotId':snap})
        assert target.is_file()
        call('export.file', {'path':str(target),'snapshotId':snap}, expect='AUTHORIZATION_REQUIRED')
        call('session.set_progress', {'stage':'Local smoke passed','progress':1})
        call('view.set', {'view':'FRONT'})
        call('view.focus', {'object':'ForegroundDemo'})
    report = {'passed':True,'mode':status['executionPolicy']['mode'],'commands':records,
              'final_status':call('session.status')['result']}
    Path(args.report).write_text(json.dumps(report,indent=2))
    print(json.dumps({'passed':True,'commands':len(records),'mode':report['mode']}))


if __name__ == '__main__': main()
