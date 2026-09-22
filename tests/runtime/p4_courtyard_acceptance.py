"""P4 Geometry Nodes and stable-name courtyard update acceptance."""
import json
import sys
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
registry=build_registry(bpy,approved_output_root=output)
if bpy.data.objects.get('Cube'):registry.dispatch('object.set_visibility',{'name':'Cube','viewport':False,'render':False})
result=registry.dispatch('recipe.procedural_courtyard',{'name':'RuinCourtyard','dimensions':[10,7,3],
 'archCount':3,'rubbleDensity':1.5})['result']
objects=result['objects'];stable={key:value['objectId'] for key,value in objects.items()}
graph=registry.dispatch('geometry_nodes.inspect',{'groupName':result['nodeGroup']['groupName']})['result']
assert len(graph['nodes'])==7 and len(graph['links'])==8
ground=bpy.data.objects[objects['ground']['name']];evaluated=ground.evaluated_get(bpy.context.evaluated_depsgraph_get())
assert len(evaluated.data.vertices)>len(ground.data.vertices)
updated=registry.dispatch('recipe.update_procedural_courtyard',{'name':'RuinCourtyard','dimensions':[12,8,3],
 'archCount':5,'rubbleDensity':3})['result']
assert updated['stableObjects']==['RuinCourtyard_Ground','RuinCourtyard_Arches','RuinCourtyard_Steps','RuinCourtyard_Slabs']
assert bpy.data.objects['RuinCourtyard_Arches'].modifiers['Arch Array'].count==5
assert {key:registry.dispatch('object.describe',{'name':value['name']})['result']['objectId'] for key,value in objects.items()}==stable
registry.dispatch('material.create_pbr',{'name':'RuinStone','baseColor':[.16,.13,.1,1],'roughness':.9})
for value in objects.values():registry.dispatch('material.assign',{'object':value['name'],'material':'RuinStone'})
registry.dispatch('light.set_world_color',{'color':[.025,.03,.04]});registry.dispatch('light.create',{'name':'RuinSun','type':'SUN','location':[0,0,6],'energy':3,'color':[1,.72,.48]})
registry.dispatch('camera.create',{'name':'RuinCamera','location':[11,-15,9],'lens':45,'active':True});registry.dispatch('camera.aim_at',{'name':'RuinCamera','target':[0,0,1]})
preview=registry.dispatch('preview.capture',{'snapshotId':'p4-courtyard','milestone':'procedural_courtyard','width':640,'height':480})['result']['milestone']
artifact=registry.dispatch('export.file',{'path':str(output/'procedural_courtyard.blend'),'snapshotId':'p4-courtyard','sessionId':'p4'})['result']['artifact']
bpy.ops.wm.open_mainfile(filepath=artifact['path']);group=bpy.data.node_groups['RuinCourtyard_RubbleNodes']
assert len(group.interface.items_tree)>=3 and bpy.data.objects['RuinCourtyard_Arches'].modifiers['Arch Array'].count==5
report={'blender':bpy.app.version_string,'artifact':artifact,'preview':preview,'stableIds':stable,
 'nodeCount':len(graph['nodes']),'linkCount':len(graph['links']),'archCount':5,'dimensions':[12,8,3],
 'technicalAcceptance':True,'visualAcceptance':'pending-model-review','productionAcceptance':False}
with (output/'acceptance.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
print('P4_COURTYARD='+json.dumps(report))
