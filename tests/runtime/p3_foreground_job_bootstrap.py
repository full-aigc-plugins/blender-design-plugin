"""Visible Blender proof that a child job does not block foreground controls."""
import json,sys,traceback
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)

def run():
    report={'blender':bpy.app.version_string,'background':bpy.app.background}
    try:
        registry=build_registry(bpy,approved_output_root=output)
        registry.dispatch('object.create_mesh',{'name':'ForegroundSource','primitive':'cube'})
        registry.dispatch('camera.create',{'name':'ForegroundCamera','location':[4,-6,3],'active':True})
        registry.dispatch('camera.aim_at',{'name':'ForegroundCamera','target':[0,0,0]})
        job=registry.dispatch('job.submit',{'jobId':'job_foreground_render','kind':'RENDER_STILL',
          'parameters':{'width':4096,'height':4096}})['result']
        registry.dispatch('view.set',{'view':'FRONT'})
        registry.dispatch('playback.set',{'playing':True});registry.dispatch('playback.set',{'playing':False})
        registry.dispatch('object.create_mesh',{'name':'EditedWhileJobRunning','primitive':'sphere'})
        cancelled=registry.dispatch('job.cancel',{'jobId':job['jobId']})['result']
        report|={'checks':['foreground_view','foreground_playback','foreground_mutation','child_cancel'],
                 'cancelState':cancelled['state'],'passed':cancelled['state']=='cancelled'}
    except Exception as exc:
        report|={'passed':False,'error':{'type':type(exc).__name__,'message':str(exc)}};traceback.print_exc()
    with (output/'foreground-job-report.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    bpy.ops.wm.quit_blender();return None

bpy.app.timers.register(run,first_interval=1)
