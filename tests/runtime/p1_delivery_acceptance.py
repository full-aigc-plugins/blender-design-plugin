"""Create and reopen the P1 acceptance project exclusively through public commands."""
import json
import sys
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
registry=build_registry(bpy,approved_output_root=output)
registry.dispatch('scene.set_units',{'system':'METRIC','scaleLength':1})
if bpy.data.objects.get('Cube'):
    registry.dispatch('object.set_visibility',{'name':'Cube','viewport':False,'render':False})
shell=registry.dispatch('recipe.hard_surface_shell',{'name':'ParametricHousing','dimensions':[1.2,.7,.5],
 'wallThickness':.025,'bevelWidth':.015})['result']
registry.dispatch('object.transform',{'objectId':shell['shell']['objectId'],'location':[-1,0,.25]})
registry.dispatch('object.transform',{'objectId':shell['helper']['objectId'],'location':[-1,0,.275]})
spear=registry.dispatch('recipe.spear',{'name':'SingleSpear','length':3.2,'shaftRadius':.025,
 'headLength':.32,'headRadius':.09})['result']
registry.dispatch('object.transform',{'objectId':spear['spear']['objectId'],'rotation':[0,1.5707963267948966,0],
                                      'location':[1,0,.65]})
ground=registry.dispatch('object.create_mesh',{'name':'Ground','primitive':'plane','scale':[3,2,2]})['result']
liner=registry.dispatch('object.create_mesh',{'name':'HousingInteriorLiner','primitive':'cube',
 'location':[-1,0,.04],'scale':[.56,.31,.01]})['result']
registry.dispatch('material.create_pbr',{'name':'HousingMat','baseColor':[.18,.2,.24,1],'metallic':.4,'roughness':.28})
registry.dispatch('material.create_pbr',{'name':'SpearMat','baseColor':[.3,.12,.04,1],'metallic':.25,'roughness':.35})
registry.dispatch('material.create_pbr',{'name':'GroundMat','baseColor':[.08,.09,.1,1],'roughness':.8})
registry.dispatch('material.create_pbr',{'name':'InteriorMat','baseColor':[.015,.018,.022,1],'roughness':.9})
for object_id,material in [(shell['shell']['objectId'],'HousingMat'),(spear['spear']['objectId'],'SpearMat'),(ground['objectId'],'GroundMat')]:
    registry.dispatch('material.assign',{'object':registry.dispatch('object.describe',{'objectId':object_id})['result']['name'],'material':material})
registry.dispatch('material.assign',{'object':'HousingInteriorLiner','material':'InteriorMat'})
registry.dispatch('light.set_world_color',{'color':[.035,.04,.05]})
registry.dispatch('light.create',{'name':'Key','type':'AREA','location':[-2,-3,5],'energy':1100,'size':4})
registry.dispatch('light.create',{'name':'Fill','type':'AREA','location':[4,1,3],'energy':700,'size':3,'color':[.55,.7,1]})
preview=registry.dispatch('preview.capture',{'snapshotId':'p1-acceptance','milestone':'p1_modeling','width':640,'height':480})['result']['milestone']
blend_path=output/'p1_shell_spear.blend'
artifact=registry.dispatch('export.file',{'path':str(blend_path),'snapshotId':'p1-acceptance','sessionId':'p1'})['result']['artifact']
bpy.ops.wm.open_mainfile(filepath=str(blend_path))
reopened=build_registry(bpy,approved_output_root=output)
housing=reopened.dispatch('object.describe',{'objectId':shell['shell']['objectId']})['result']
spear_after=reopened.dispatch('object.describe',{'objectId':spear['spear']['objectId']})['result']
assert housing['name']=='ParametricHousing' and spear_after['name']=='SingleSpear'
assert [m.type for m in bpy.data.objects['ParametricHousing'].modifiers]==['BOOLEAN','BEVEL']
assert [m.type for m in bpy.data.objects['SingleSpear'].modifiers]==['BEVEL']
assert len([obj for obj in bpy.data.objects if obj.name=='SingleSpear'])==1
report={'blender':bpy.app.version_string,'platform':'macOS Apple Silicon','artifact':artifact,
 'preview':preview,'reopen':{'stableIds':True,'editableModifierChains':True,'singleSpearObject':True},
 'technicalAcceptance':True,'visualAcceptance':'pending-human-or-model-review','productionAcceptance':False}
with (output/'acceptance.json').open('x',encoding='utf-8') as stream: json.dump(report,stream,ensure_ascii=False,indent=2)
print('P1_DELIVERY='+json.dumps(report,ensure_ascii=False))
