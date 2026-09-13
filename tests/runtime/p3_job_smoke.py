"""Real parent and child Blender background job isolation/cancellation."""
import json,sys,time
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
registry=build_registry(bpy,approved_output_root=output,approved_asset_roots=(output,))
snapshot=registry.dispatch('object.create_mesh',{'name':'SnapshotOnly','primitive':'cube'})['result']
submitted=registry.dispatch('job.submit',{'jobId':'job_export_isolation','kind':'EXPORT','format':'glb'})['result']
registry.dispatch('object.create_mesh',{'name':'AfterSnapshot','primitive':'sphere'})
assert bpy.data.objects.get('AfterSnapshot') is not None
deadline=time.monotonic()+30
while time.monotonic()<deadline:
    status=registry.dispatch('job.status',{'jobId':submitted['jobId']})['result']
    if status['state'] in {'completed','failed','cancelled','interrupted'}:break
    time.sleep(.1)
assert status['state']=='completed',status
assert Path(status['artifact']['path']).is_relative_to(output/'jobs'/'job_export_isolation')
artifact=Path(status['artifact']['path'])
bpy.ops.wm.read_factory_settings(use_empty=True)
imported=build_registry(bpy,approved_asset_roots=(output,)).dispatch('asset.import_file',{'path':str(artifact)})['result']
names={item['name'] for item in imported['objects']}
assert 'SnapshotOnly' in names and 'AfterSnapshot' not in names

cancel_registry=build_registry(bpy,approved_output_root=output)
cancel=cancel_registry.dispatch('job.submit',{'jobId':'job_cancel_render','kind':'RENDER_STILL',
 'parameters':{'width':4096,'height':4096}})['result']
cancelled=cancel_registry.dispatch('job.cancel',{'jobId':cancel['jobId']})['result']
assert cancelled['state']=='cancelled'
print('P3_JOBS='+json.dumps({'blender':bpy.app.version_string,'export':status,'cancel':cancelled,
 'checks':['snapshot_isolation','parent_continues','child_output_scope','artifact_validation','cancel'],'productionAcceptance':False}))
