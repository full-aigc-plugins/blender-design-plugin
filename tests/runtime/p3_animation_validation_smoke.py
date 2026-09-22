"""Advanced animation APIs and reusable quality checks in Blender 5.2."""
import json
import sys
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True) if '--' in sys.argv else None
registry=build_registry(bpy,approved_output_root=output)
if bpy.data.objects.get('Cube'): registry.dispatch('object.set_visibility',{'name':'Cube','viewport':False,'render':False})
result=registry.dispatch('recipe.rigged_spear_character',{'name':'ValidationHero','height':2.2,
 'releaseFrame':61,'apexFrame':75,'catchFrame':90})['result']
arm=result['armature']; body=result['body']; spear=result['spear']
registry.dispatch('material.create_pbr',{'name':'P3Body','baseColor':[.32,.38,.48,1],'roughness':.65})
registry.dispatch('material.create_pbr',{'name':'P3Spear','baseColor':[.5,.16,.035,1],'metallic':.3,'roughness':.3})
registry.dispatch('material.assign',{'object':body['name'],'material':'P3Body'});registry.dispatch('material.assign',{'object':spear['name'],'material':'P3Spear'})
registry.dispatch('light.set_world_color',{'color':[.05,.055,.07]})
registry.dispatch('light.create',{'name':'P3Key','type':'AREA','location':[-3,-4,5],'energy':1500,'size':4})
registry.dispatch('animation.pose_keyframe',{'armature':arm['name'],'bone':'pelvis','dataPath':'location','frame':1,'value':[0,0,0]})
registry.dispatch('animation.pose_keyframe',{'armature':arm['name'],'bone':'pelvis','dataPath':'location','frame':30,'value':[.08,0,0]})
registry.dispatch('animation.pose_keyframe',{'armature':arm['name'],'bone':'pelvis','dataPath':'location','frame':45,'value':[0,0,0]})
actions=registry.dispatch('animation.action_list',{})['result']['actions']; assert actions and all(item['layered'] for item in actions)
edit=registry.dispatch('animation.fcurve_edit',{'objectId':spear['objectId'],'dataPath':'location','arrayIndex':0,
                                               'interpolation':'LINEAR'})['result']; assert edit['keyframes']==3
source_action=bpy.data.objects[spear['name']].animation_data.action.name
registry.dispatch('animation.nla_add_strip',{'objectId':spear['objectId'],'action':source_action,
 'track':'ThrowTrack','name':'ThrowClip','start':130,'scale':1.2,'repeat':1,'blendType':'REPLACE'})
shape=registry.dispatch('object.create_mesh',{'name':'FaceProxy','primitive':'cube'})['result']
registry.dispatch('animation.shape_key_add',{'objectId':shape['objectId'],'keyName':'Expression'})
registry.dispatch('animation.shape_key_keyframe',{'objectId':shape['objectId'],'keyName':'Expression','frame':1,'value':0})
registry.dispatch('animation.shape_key_keyframe',{'objectId':shape['objectId'],'keyName':'Expression','frame':20,'value':1})
registry.dispatch('object.set_visibility',{'objectId':shape['objectId'],'viewport':False,'render':False})
target=registry.dispatch('object.duplicate',{'objectId':arm['objectId'],'newName':'RetargetRig'})['result']
registry.dispatch('animation.retarget',{'source':{'objectId':arm['objectId']},'target':{'objectId':target['objectId']},
 'boneMap':{'pelvis':'pelvis','spine':'spine'},'frameStart':1,'frameEnd':45,'step':15})
path=registry.dispatch('curve.create',{'name':'CameraPath','points':[[-4,-6,2],[0,-7,2.5],[4,-5,2]],
 'splineType':'BEZIER','handleType':'AUTO'})['result']
camera=registry.dispatch('camera.create',{'name':'FollowCamera','location':[-4,-6,2],'active':True})
registry.dispatch('camera.follow_path',{'camera':{'name':'FollowCamera'},'path':{'objectId':path['objectId']},
 'name':'Fight Follow','frameStart':1,'frameEnd':120,'targetObjectId':body['objectId']})
handheld=registry.dispatch('camera.add_handheld',{'name':'FollowCamera','frameStart':1,'frameEnd':120,
 'translationStrength':.012,'rotationStrength':.008,'noiseScale':8,'seed':17})['result']
assert len(handheld['noiseCurves'])==6
clean_fixture=registry.dispatch('object.create_mesh',{'name':'CleanCurveFixture','primitive':'cube'})['result']
registry.dispatch('object.set_visibility',{'objectId':clean_fixture['objectId'],'viewport':False,'render':False})
for frame,x in ((1,0),(10,1),(19,2)):
    registry.dispatch('object.transform',{'objectId':clean_fixture['objectId'],'location':[x,0,0]})
    registry.dispatch('animation.insert_keyframe',{'object':'CleanCurveFixture','dataPath':'location','frame':frame})
cleaned=registry.dispatch('animation.fcurve_clean',{'objectId':clean_fixture['objectId'],'dataPath':'location','arrayIndex':0,'threshold':.0001})['result']
assert cleaned['removed']==1 and cleaned['remaining']==2

measurements={
 'handoff':registry.dispatch('validation.prop_handoff',{'object':{'objectId':spear['objectId']},'armature':{'objectId':arm['objectId']},
   'bone':'hand.R','constraintName':'Right Hand Grip','frameStart':61,'frameEnd':90,'catchFrame':90})['result'],
 'foot':registry.dispatch('validation.foot_drift',{'armature':{'objectId':arm['objectId']},'bone':'foot.L','frameStart':1,'frameEnd':45,'limit':.01})['result'],
 'limbs':registry.dispatch('validation.limb_length',{'armature':{'objectId':arm['objectId']},'bones':['upper_arm.R','lower_arm.R','upper_leg.L'],
   'frameStart':1,'frameEnd':90,'limit':.005})['result'],
 'floor':registry.dispatch('validation.floor_penetration',{'object':{'objectId':body['objectId']},'frameStart':1,'frameEnd':90,'floorZ':0,'limit':.002})['result'],
 'visibility':registry.dispatch('validation.camera_visibility',{'camera':{'name':'FollowCamera'},'objects':[{'objectId':body['objectId']}],
   'frameStart':75,'frameEnd':75})['result'],
 'motion':registry.dispatch('validation.motion_discontinuity',{'object':{'objectId':spear['objectId']},'frameStart':60,'frameEnd':91,
   'positionLimit':.01,'angleLimitDegrees':1})['result']}
assert all(measurements[key]['passed'] for key in ('handoff','foot','limbs','floor','visibility'))
assert not measurements['motion']['passed'] and measurements['motion']['issues']
report={'blender':bpy.app.version_string,'actions':len(actions),
 'checks':['layered_action','fcurve','fcurve_clean','nla','shape_keys','retarget','camera_path','handheld_noise','quality_commands'],
 'measurements':measurements,'productionAcceptance':False}
if output:
    registry.dispatch('playback.set_frame',{'frame':75})
    report['preview']=registry.dispatch('preview.capture',{'snapshotId':'p3-animation','milestone':'animation','width':640,'height':640})['result']['milestone']
    report['artifact']=registry.dispatch('export.file',{'path':str(output/'advanced_animation.blend'),'snapshotId':'p3-animation','sessionId':'p3'})['result']['artifact']
    with (output/'acceptance.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
print('P3_ANIMATION='+json.dumps(report))
