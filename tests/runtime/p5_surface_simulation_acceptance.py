"""P5 sculpt, Hair Curves, simulation configuration and cache acceptance."""
import json
import sys
import time
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
registry=build_registry(bpy,approved_output_root=output)
if bpy.data.objects.get('Cube'):registry.dispatch('object.set_visibility',{'name':'Cube','viewport':False,'render':False})

surface=registry.dispatch('object.create_mesh',{'name':'SculptSurface','primitive':'sphere','location':[-2,0,1]})['result']
selection=registry.dispatch('mesh.select',{'objectId':surface['objectId'],'method':'spatial','min':[-2,-2,0],'max':[2,2,2]})['result']
before=[v.co.copy() for v in bpy.data.objects['SculptSurface'].data.vertices]
registry.dispatch('sculpt.set_mask',{'selection':selection,'value':0})
registry.dispatch('sculpt.displace',{'selection':selection,'strength':.08})
assert any((v.co-before[v.index]).length>.01 for v in bpy.data.objects['SculptSurface'].data.vertices)
remesh=registry.dispatch('object.duplicate',{'objectId':surface['objectId'],'newName':'VoxelSurface'})['result']
remeshed=registry.dispatch('sculpt.voxel_remesh',{'objectId':remesh['objectId'],'voxelSize':.18})['result']
assert remeshed['topologyVersion']>0
multires=registry.dispatch('object.create_mesh',{'name':'MultiresSurface','primitive':'cube','location':[-3,0,.5]})['result']
assert registry.dispatch('sculpt.multires',{'objectId':multires['objectId'],'levels':2})['result']['levels']==2
registry.dispatch('sculpt.cleanup',{'objectId':remesh['objectId'],'ratio':.8,'target':{'objectId':surface['objectId']}})

hair=registry.dispatch('hair.create_curves',{'surface':{'objectId':surface['objectId']},'name':'ShortHair','radius':.015,
 'strands':[[[-.2,0,.7],[-.2,0,1.0],[-.15,0,1.25]],[[0,0,.8],[0,0,1.15],[.05,0,1.4]],[[.2,0,.7],[.2,0,1.0],[.25,0,1.25]]]})['result']
assert registry.dispatch('hair.inspect',{'objectId':hair['objectId']})['result']['strands']==3

floor=registry.dispatch('object.create_mesh',{'name':'PhysicsFloor','primitive':'cube','location':[1,0,-.1],'scale':[2,2,.1]})['result']
falling=registry.dispatch('object.create_mesh',{'name':'FallingRigid','primitive':'cube','location':[1,0,2.5],'scale':[.25,.25,.25]})['result']
registry.dispatch('simulation.rigid_body',{'objectId':floor['objectId'],'bodyType':'PASSIVE','collisionShape':'BOX'})
registry.dispatch('simulation.rigid_body',{'objectId':falling['objectId'],'bodyType':'ACTIVE','collisionShape':'BOX','mass':1})
bpy.context.scene.frame_start=1;bpy.context.scene.frame_end=30;bpy.context.scene.frame_set(1);z_start=bpy.data.objects['FallingRigid'].matrix_world.translation.z
for frame in range(2,31):bpy.context.scene.frame_set(frame)
z_end=bpy.data.objects['FallingRigid'].matrix_world.translation.z
assert z_end<z_start-1 and z_end>=.14,(z_start,z_end)

cloth=registry.dispatch('object.create_mesh',{'name':'Cloth','primitive':'plane','location':[0,0,2.5],'scale':[1,1,1]})['result']
info=registry.dispatch('mesh.inspect',{'objectId':cloth['objectId']})['result'];edges=list(range(info['counts']['edges']))
sel=registry.dispatch('mesh.select',{'objectId':cloth['objectId'],'method':'indices','edges':edges})['result']
registry.dispatch('mesh.edit',{'operation':'subdivide','selection':sel,'cuts':8})
collider=registry.dispatch('object.create_mesh',{'name':'ClothCollider','primitive':'sphere','location':[0,0,.7],'scale':[.7,.7,.7]})['result']
registry.dispatch('simulation.collision',{'objectId':collider['objectId'],'thickness':.02})
registry.dispatch('simulation.cloth',{'objectId':cloth['objectId'],'quality':5,'mass':.3,'frameStart':1,'frameEnd':30})
bpy.context.scene.frame_set(1);cloth_start=max((bpy.data.objects['Cloth'].matrix_world@vertex.co).z for vertex in bpy.data.objects['Cloth'].data.vertices)
for frame in range(2,31):bpy.context.scene.frame_set(frame)
evaluated_cloth=bpy.data.objects['Cloth'].evaluated_get(bpy.context.evaluated_depsgraph_get());cloth_end=min((evaluated_cloth.matrix_world@vertex.co).z for vertex in evaluated_cloth.data.vertices)
assert cloth_end<cloth_start-.5 and cloth_end>=-.002,(cloth_start,cloth_end)
soft=registry.dispatch('object.create_mesh',{'name':'SoftBody','primitive':'sphere','location':[2,0,2]})['result']
registry.dispatch('simulation.soft_body',{'objectId':soft['objectId'],'frameStart':1,'frameEnd':20})
flow=registry.dispatch('object.create_mesh',{'name':'SmokeFlow','primitive':'cube','location':[3,0,.5],'scale':[.25,.25,.25]})['result']
smoke=registry.dispatch('simulation.quick_smoke',{'flows':[{'objectId':flow['objectId']}],'resolution':16,'frameStart':1,'frameEnd':5})['result']
assert smoke['domain']['name'] and Path(smoke['cacheDirectory']).is_relative_to(output)
registry.dispatch('object.set_visibility',{'objectId':smoke['domain']['objectId'],'viewport':False,'render':False});registry.dispatch('object.set_visibility',{'objectId':flow['objectId'],'viewport':False,'render':False})
assert registry.dispatch('simulation.cache_status',{'objectId':cloth['objectId']})['result']['caches'][0]['frameEnd']==30
registry.dispatch('material.create_pbr',{'name':'P5Surface','baseColor':[.25,.38,.55,1],'roughness':.65})
for object_name in ('SculptSurface','VoxelSurface','MultiresSurface','Cloth','SoftBody','FallingRigid'):
    registry.dispatch('material.assign',{'object':object_name,'material':'P5Surface'})
registry.dispatch('light.set_world_color',{'color':[.04,.045,.06]});registry.dispatch('light.create',{'name':'P5Key','type':'AREA','location':[-4,-5,6],'energy':1500,'size':4})
registry.dispatch('camera.create',{'name':'P5Camera','location':[7,-11,5],'lens':55,'active':True});registry.dispatch('camera.aim_at',{'name':'P5Camera','target':[0,0,1]})
registry.dispatch('playback.set_frame',{'frame':30})
preview=registry.dispatch('preview.capture',{'snapshotId':'p5-surface-simulation','milestone':'surface_hair_simulation','width':640,'height':480})['result']['milestone']

job=registry.dispatch('job.submit',{'jobId':'job_p5_bake','kind':'BAKE_POINT_CACHES'})['result'];deadline=time.monotonic()+60
while time.monotonic()<deadline:
    status=registry.dispatch('job.status',{'jobId':job['jobId']})['result']
    if status['state'] in {'completed','failed','cancelled','interrupted'}:break
    time.sleep(.2)
assert status['state']=='completed',status
artifact=status['artifact'];bpy.ops.wm.open_mainfile(filepath=artifact['path'])
reopened=build_registry(bpy,approved_output_root=output)
cache_before=reopened.dispatch('simulation.cache_status',{'name':'Cloth'})['result']['caches'][0]
domain_cache=next(m.domain_settings.cache_directory for m in bpy.data.objects['Smoke Domain'].modifiers if m.type=='FLUID')
assert Path(domain_cache).is_relative_to(output/'jobs'/'job_p5_bake')
fluid_before=reopened.dispatch('simulation.cache_status',{'name':'Smoke Domain'})['result']['caches'][0]
assert fluid_before['isBaked'] and any(Path(domain_cache).rglob('*'))
freed=reopened.dispatch('simulation.free_cache',{'name':'Cloth'})['result']
cache_after=reopened.dispatch('simulation.cache_status',{'name':'Cloth'})['result']['caches'][0]
assert cache_before['isBaked'] and 'Cloth' in freed['freed'] and not cache_after['isBaked']
fluid_freed=reopened.dispatch('simulation.free_cache',{'name':'Smoke Domain'})['result']
fluid_after=reopened.dispatch('simulation.cache_status',{'name':'Smoke Domain'})['result']['caches'][0]
assert fluid_freed['freed'] and not fluid_after['isBaked']
report={'blender':bpy.app.version_string,'rigidDrop':[z_start,z_end],'clothDrop':[cloth_start,cloth_end],'hair':hair,'smoke':smoke,'preview':preview,
 'bakeArtifact':artifact,'cacheReusable':cache_before['isBaked'],'cacheInvalidated':not cache_after['isBaked'],
 'fluidCacheReusable':fluid_before['isBaked'],'fluidCacheInvalidated':not fluid_after['isBaked'],
 'technicalAcceptance':True,'visualAcceptance':'pending-model-review','productionAcceptance':False}
with (output/'acceptance.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
print('P5_ACCEPTANCE='+json.dumps(report))
