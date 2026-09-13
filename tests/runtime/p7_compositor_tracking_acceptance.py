"""Attach a tracked clip and editable mask to the Blender 5 compositor."""
import json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry
assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
registry=build_registry(bpy,approved_output_root=output)
clip=next(iter(bpy.data.movieclips),None);assert clip is not None
registry.dispatch('compositor.configure',{'exposure':0,'glare':False})
mask=registry.dispatch('compositor.add_tracking_mask',{'clip':clip.name,'maskName':'TrackedForeground',
 'points':[[.35,.3],[.65,.3],[.7,.7],[.3,.7]]})['result']
inspection=registry.dispatch('compositor.inspect',{})['result']
assert bpy.data.masks['TrackedForeground'].layers[0].splines[0].use_cyclic
assert all(any(node['name']==name for node in inspection['nodes']) for name in mask['nodes'])
artifact=registry.dispatch('export.file',{'path':str(output/'tracking_composite.blend'),'snapshotId':'p7-composite','sessionId':'p7'})['result']['artifact']
bpy.ops.wm.open_mainfile(filepath=artifact['path']);assert bpy.data.masks.get('TrackedForeground') and bpy.context.scene.compositing_node_group
report={'blender':bpy.app.version_string,'mask':mask,'nodes':len(inspection['nodes']),'links':len(inspection['links']),
 'artifact':artifact,'passed':True,'productionAcceptance':True}
with (output/'acceptance.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
print('P7_COMPOSITOR='+json.dumps(report))
