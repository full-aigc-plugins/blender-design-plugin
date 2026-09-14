"""Real Blender acceptance for durable frames, explicit resume, and FFmpeg composition."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry
from scripts.validate_document import validate_document

assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
registry=build_registry(bpy,approved_output_root=output)

bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(location=(0,0,0));cube=bpy.context.object;cube.name='FramePipelineCube'
bpy.ops.object.camera_add(location=(4,-5,3));camera=bpy.context.object;bpy.context.scene.camera=camera
direction=(cube.location-camera.location).to_track_quat('-Z','Y');camera.rotation_euler=direction.to_euler()
bpy.ops.object.light_add(type='AREA',location=(2,-2,4));bpy.context.object.data.energy=800
if sys.platform.startswith('win'):
    bpy.context.scene.render.engine='CYCLES';bpy.context.scene.cycles.device='CPU';bpy.context.scene.cycles.samples=1
else:bpy.context.scene.render.engine='BLENDER_EEVEE'
bpy.context.scene.render.fps=24

def wait(job_id,timeout=120):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        status=registry.dispatch('job.status',{'jobId':job_id})['result']
        if status['state'] in {'completed','failed','cancelled','interrupted'}:return status
        time.sleep(.1)
    raise AssertionError(f'job timed out: {job_id}')

registry.dispatch('job.submit',{'kind':'RENDER_ANIMATION_FRAMES','jobId':'job_p8_frames','parameters':{
  'frameStart':1,'frameEnd':3,'frameStep':1,'width':320,'height':240,'imageFormat':'PNG','includeAudio':False}})
first=wait('job_p8_frames');assert first['state']=='completed',first
task=output/'jobs'/'job_p8_frames';manifest_path=task/'frame-sequence.json';manifest=json.loads(manifest_path.read_text())
assert manifest['validation']['status']=='passed' and len(manifest['frames'])==3
frame1=Path(manifest['frames'][0]['path']);frame2=Path(manifest['frames'][1]['path']);frame3=Path(manifest['frames'][2]['path'])
frame1_hash=hashlib.sha256(frame1.read_bytes()).hexdigest();frame1_mtime=frame1.stat().st_mtime_ns
frame2.write_bytes(b'corrupt');frame3.unlink()
status_path=task/'status.json';interrupted=json.loads(status_path.read_text());interrupted['state']='interrupted';status_path.write_text(json.dumps(interrupted))
registry.dispatch('job.resume',{'jobId':'job_p8_frames'})
resumed=wait('job_p8_frames');assert resumed['state']=='completed',resumed
manifest=json.loads(manifest_path.read_text());assert manifest['reusedFrames']==[1] and manifest['renderedFrames']==[2,3],manifest
assert validate_document('frame_sequence_receipt',manifest)==[],validate_document('frame_sequence_receipt',manifest)
assert hashlib.sha256(frame1.read_bytes()).hexdigest()==frame1_hash and frame1.stat().st_mtime_ns==frame1_mtime

registry.dispatch('job.submit',{'kind':'RENDER_ANIMATION_FRAMES','jobId':'job_p8_exr','parameters':{
  'frameStart':1,'frameEnd':1,'frameStep':1,'width':320,'height':240,'imageFormat':'OPEN_EXR_MULTILAYER',
  'colorMode':'RGBA','colorDepth':'16','includeAudio':False}})
exr=wait('job_p8_exr');assert exr['state']=='completed',exr
exr_manifest=exr['artifact'];assert exr_manifest['format']=='OPEN_EXR_MULTILAYER'
assert Path(exr_manifest['frames'][0]['path']).read_bytes()[:4]==b'\x76\x2f\x31\x01'

registry.dispatch('job.submit',{'kind':'COMPOSE_VIDEO','jobId':'job_p8_compose','parameters':{
  'sourceJobId':'job_p8_frames','codec':'H264','crf':24,'preset':'veryfast','includeAudio':False}})
composed=wait('job_p8_compose');assert composed['state']=='completed',composed
artifact=composed['artifact'];video=Path(artifact['path']);assert video.is_file() and artifact['validation']['status']=='passed'
assert validate_document('video_artifact_receipt',artifact)==[],validate_document('video_artifact_receipt',artifact)
probe=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_name,width,height','-of','json',str(video)],
                     capture_output=True,text=True,check=True)
media=json.loads(probe.stdout)['streams'][0];assert media['codec_name']=='h264' and media['width']==320 and media['height']==240
assert composed['artifact']['media']['fps']==24.0,composed['artifact']['media']
assert abs(composed['artifact']['media']['duration_seconds']-(3/24))<.01,composed['artifact']['media']
report={'blender':bpy.app.version_string,'frameJob':resumed,'exrJob':exr,'composeJob':composed,'frameManifest':manifest,
        'faultInjection':'frame 2 corrupt + frame 3 missing','verifiedFrameUnchanged':1,'technicalAcceptance':True,
        'visualAcceptance':'simple-cube-smoke','productionAcceptance':sys.platform.startswith('win')}
(output/'p8-frame-pipeline-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('P8_FRAME_PIPELINE='+json.dumps(report))
