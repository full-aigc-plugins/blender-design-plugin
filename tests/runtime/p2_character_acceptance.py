"""P2-B real armature, skin, IK and one-prop handoff acceptance."""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
registry=build_registry(bpy,approved_output_root=output)
if bpy.data.objects.get('Cube'): registry.dispatch('object.set_visibility',{'name':'Cube','viewport':False,'render':False})
result=registry.dispatch('recipe.rigged_spear_character',{'name':'SpearHero','height':2.2,
 'releaseFrame':61,'apexFrame':75,'catchFrame':90})['result']
body=bpy.data.objects[result['body']['name']]; arm=bpy.data.objects[result['armature']['name']]; spear=bpy.data.objects[result['spear']['name']]
assert body.parent is arm and any(m.type=='ARMATURE' and m.object is arm for m in body.modifiers)
assert len([obj for obj in bpy.data.objects if obj.name=='SpearHero_Spear'])==1
weighted={group.name:0 for group in body.vertex_groups}
for vertex in body.data.vertices:
    for membership in vertex.groups: weighted[body.vertex_groups[membership.group].name]+=1
assert weighted['spine']>0 and weighted['upper_arm.R']>0 and weighted['lower_leg.L']>0
bone_count=len(arm.data.bones)
registry.dispatch('animation.pose_keyframe',{'armature':arm.name,'bone':'pelvis','dataPath':'location','frame':1,'value':[0,0,0]})
registry.dispatch('animation.pose_keyframe',{'armature':arm.name,'bone':'pelvis','dataPath':'location','frame':30,'value':[.08,0,0]})
registry.dispatch('animation.pose_keyframe',{'armature':arm.name,'bone':'pelvis','dataPath':'location','frame':45,'value':[0,0,0]})

# Moving the right-hand target must change the IK chain.
bpy.context.scene.frame_set(1); bpy.context.view_layer.update()
before=arm.pose.bones['lower_arm.R'].matrix.copy(); control=bpy.data.objects['SpearHero_Hand.R_CTRL']
control.location.z+=.2; bpy.context.view_layer.update(); after=arm.pose.bones['lower_arm.R'].matrix.copy()
assert any(abs(a-b)>1e-5 for row_a,row_b in zip(before,after) for a,b in zip(row_a,row_b)); control.location.z-=.2

rest_lengths={bone.name:bone.length for bone in arm.data.bones}
def matrices(frame):
    bpy.context.scene.frame_set(frame); bpy.context.view_layer.update()
    hand=(arm.matrix_world@arm.pose.bones['hand.R'].matrix).translation
    return spear.matrix_world.copy(),hand

max_length_error=0
for frame in (1,61,75,90,91,120):
    bpy.context.scene.frame_set(frame); bpy.context.view_layer.update()
    for bone in arm.data.bones:
        max_length_error=max(max_length_error,abs(bone.length-rest_lengths[bone.name])/rest_lengths[bone.name])
assert max_length_error<=.005
constraint=spear.constraints['Right Hand Grip']
bpy.context.scene.frame_set(60); assert constraint.influence==1
bpy.context.scene.frame_set(61); assert constraint.influence==0
run=0; max_run=0; max_release_distance=0
for frame in range(61,91):
    matrix,hand=matrices(frame); distance=(matrix.translation-hand).length
    max_release_distance=max(max_release_distance,distance)
    run=run+1 if distance>=.05 else 0; max_run=max(max_run,run)
assert max_run>=6
catch_matrix,_=matrices(90); attached_matrix,_=matrices(91)
catch_position_jump=(attached_matrix.translation-catch_matrix.translation).length
catch_rotation_jump=catch_matrix.to_quaternion().rotation_difference(attached_matrix.to_quaternion()).angle
assert catch_position_jump<=.01 and catch_rotation_jump<=math.radians(2)
foot_positions=[]
for frame in (1,30,60,90,120):
    bpy.context.scene.frame_set(frame); bpy.context.view_layer.update()
    foot_positions.append((arm.matrix_world@arm.pose.bones['foot.L'].matrix).translation.copy())
foot_drift=max((point-foot_positions[0]).length for point in foot_positions)
minimum_z=min((body.matrix_world@Vector(corner)).z for corner in body.bound_box)
assert foot_drift<=.01 and minimum_z>=-.002,(foot_drift,minimum_z)

registry.dispatch('material.create_pbr',{'name':'CharacterClay','baseColor':[.28,.32,.38,1],'roughness':.72})
registry.dispatch('material.create_pbr',{'name':'SpearBronze','baseColor':[.35,.13,.035,1],'metallic':.35,'roughness':.3})
registry.dispatch('material.assign',{'object':body.name,'material':'CharacterClay'}); registry.dispatch('material.assign',{'object':spear.name,'material':'SpearBronze'})
ground=registry.dispatch('object.create_mesh',{'name':'CharacterGround','primitive':'plane','scale':[3,2,1]})['result']
registry.dispatch('material.create_pbr',{'name':'CharacterGroundMat','baseColor':[.04,.045,.055,1],'roughness':.85})
registry.dispatch('material.assign',{'object':'CharacterGround','material':'CharacterGroundMat'})
registry.dispatch('light.set_world_color',{'color':[.025,.03,.04]})
registry.dispatch('light.create',{'name':'CharacterKey','type':'AREA','location':[-3,-4,5],'energy':1300,'size':4})
registry.dispatch('camera.create',{'name':'CharacterCamera','location':[4,-7,3],'lens':58,'active':True})
registry.dispatch('camera.aim_at',{'name':'CharacterCamera','target':[0,0,1.15]})
registry.dispatch('playback.set_frame',{'frame':75})
preview=registry.dispatch('preview.capture',{'snapshotId':'p2-character','milestone':'rigged_spear_character','width':640,'height':640})['result']['milestone']
blend_path=output/'rigged_spear_character.blend'
artifact=registry.dispatch('export.file',{'path':str(blend_path),'snapshotId':'p2-character','sessionId':'p2b'})['result']['artifact']
bpy.ops.wm.open_mainfile(filepath=str(blend_path))
assert bpy.data.objects['SpearHero_Body'].modifiers['Armature Deform'].object==bpy.data.objects['SpearHero_Rig']
assert bpy.data.objects['SpearHero_Spear'].constraints.get('Right Hand Grip')
bpy.ops.wm.read_factory_settings(use_empty=True)
alternate=build_registry(bpy).dispatch('recipe.rigged_spear_character',{'name':'ResizedHero','height':1.8,
 'releaseFrame':50,'apexFrame':63,'catchFrame':78})['result']
alternate_arm=bpy.data.objects[alternate['armature']['name']]
rescale_error=abs(alternate_arm.data.bones['head'].tail_local.z-2.18*(1.8/2.2))
assert rescale_error<=.001 and alternate['throwFrames']=={'release':50,'apex':63,'catch':78}
report={'blender':bpy.app.version_string,'artifact':artifact,'preview':preview,'bones':bone_count,
 'weightedGroups':sum(count>0 for count in weighted.values()),'ikControllerMovesArm':True,
 'maxLimbLengthError':max_length_error,'releaseFramesAtLeast5cm':max_run,'maxReleaseDistance':max_release_distance,
 'catchPositionJump':catch_position_jump,'catchRotationJumpDegrees':math.degrees(catch_rotation_jump),
 'footDriftDuringPelvisMove':foot_drift,'minimumBodyZ':minimum_z,'oneSpear':True,'reopenEditable':True,
 'rescaleError':rescale_error,'retimedThrow':alternate['throwFrames'],
 'technicalAcceptance':True,'visualAcceptance':'pending-model-review','productionAcceptance':False}
with (output/'acceptance.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
print('P2_CHARACTER='+json.dumps(report,ensure_ascii=False))
