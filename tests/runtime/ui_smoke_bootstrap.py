"""Opt-in real Blender UI operator smoke, leaving the verified panel open."""
import argparse
import json
import sys
import uuid
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.harness.execution_policy import ExecutionPolicy
from scripts.harness.server import start_harness

parser=argparse.ArgumentParser()
parser.add_argument('--output-root',required=True)
parser.add_argument('--runtime-dir',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
output=Path(args.output_root); output.mkdir(parents=True,exist_ok=True)
handle=start_harness(bpy,session_id='foreground-ui-verified',runtime_dir=Path(args.runtime_dir),
                     approved_output_root=output,execution_policy=ExecutionPolicy.review_only())

def verify():
    try:
        assert bpy.types.VIEW3D_PT_codex_session.is_registered
        assert bpy.ops.codex_blender.pause_work()=={'FINISHED'}
        assert handle.session.paused
        assert bpy.ops.codex_blender.resume_work()=={'FINISHED'}
        assert not handle.session.paused and handle.session.needs_inspection
        assert bpy.ops.codex_blender.change_view(view='FRONT')=={'FINISHED'}
        assert bpy.ops.codex_blender.jump_marker(frame=24)=={'FINISHED'}
        assert bpy.context.scene.frame_current==24
        def call(command,arguments):
            result=handle.session.handle({'protocolVersion':'codex-blender/v1','sessionId':'foreground-ui-verified',
                'requestId':str(uuid.uuid4()),'transactionId':'ui-inspect','command':command,'arguments':arguments})
            assert result['status']=='succeeded',result
            return result
        call('scene.inspect',{})
        a=call('view.present',{})['result']['windowCount']
        b=call('view.present',{})['result']['windowCount']
        assert a==b
        call('session.set_progress',{'stage':'前台控件已验证 · 可接管','progress':1})
        report={'passed':True,'native_pause_resume':True,'native_view_change':True,'native_frame_jump':True,
                'ephemeral_panel_registered':True,'present_idempotent':True,'state':handle.session.status()}
        (output/'ui-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print('FOREGROUND_UI_VERIFIED',flush=True)
    except Exception as exc:  # noqa: BLE001
        (output/'ui-report.json').write_text(json.dumps({'passed':False,'error':str(exc)},indent=2))
        print('FOREGROUND_UI_FAILED '+str(exc),flush=True)

bpy.app.timers.register(verify,first_interval=.5)
bpy.app.handlers.quit_pre.append(lambda _:handle.close())
