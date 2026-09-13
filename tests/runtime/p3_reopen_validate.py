"""Validate persisted P3 structures after Blender opens the delivered file."""
import json,sys
from pathlib import Path
import bpy
assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
spear=bpy.data.objects['ValidationHero_Spear']; face=bpy.data.objects['FaceProxy']; camera=bpy.data.objects['FollowCamera']
checks={
 'layeredActions':all(len(action.layers)>0 and len(action.slots)>0 for action in bpy.data.actions),
 'nla':any(track.name=='ThrowTrack' and any(strip.name=='ThrowClip' for strip in track.strips) for track in spear.animation_data.nla_tracks),
 'shapeKey':face.data.shape_keys.key_blocks.get('Expression') is not None,
 'cameraPath':camera.constraints.get('Fight Follow') is not None and camera.constraints.get('Fight Follow Aim') is not None,
 'retargetAction':bpy.data.objects['RetargetRig'].animation_data.action is not None,
 'handheldNoise':sum(len(curve.modifiers) for layer in bpy.data.objects['FollowCamera'].animation_data.action.layers for strip in layer.strips for bag in strip.channelbags for curve in bag.fcurves)>=6,
 'cleanedCurve':sum(len(curve.keyframe_points) for layer in bpy.data.objects['CleanCurveFixture'].animation_data.action.layers for strip in layer.strips for bag in strip.channelbags for curve in bag.fcurves if curve.data_path=='location' and curve.array_index==0)==2,
}
assert all(checks.values()),checks
with (output/'reopen.json').open('x',encoding='utf-8') as stream:json.dump({'blender':bpy.app.version_string,'checks':checks,'passed':True},stream,indent=2)
print('P3_REOPEN='+json.dumps(checks))
