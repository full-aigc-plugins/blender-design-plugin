"""Generate known footage, solve it in foreground CLIP_EDITOR, and record error."""
import json
import sys
import traceback
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True);frames_dir=output/'frames';frames_dir.mkdir()

def run():
  report={'blender':bpy.app.version_string,'background':bpy.app.background}
  try:
    for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
    scene=bpy.context.scene
    scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=320;scene.render.resolution_y=240;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    points=[(-2,-1,.2),(-1,0,.5),(0,1,.3),(1.5,-.5,.8),(2,1,1.2),(-1.8,1,1.5),(-.8,-1,2),(.5,.5,2.2),(1.8,-1,2.5),(-2,.5,2.8),(0,-.8,3),(2,.8,3.2)]
    for index,point in enumerate(points):
      bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.1,location=point);bpy.context.active_object.name=f'TrackPoint{index:02d}'
    camera_data=bpy.data.cameras.new('FixtureCamera');camera_data.lens=35;camera_data.sensor_width=36
    camera=bpy.data.objects.new('FixtureCamera',camera_data);scene.collection.objects.link(camera);scene.camera=camera
    for frame,location in [(1,(-1.5,-8,3)),(20,(1.5,-7,2.5))]:
      camera.location=location;camera.rotation_euler=(Vector((0,0,1.4))-camera.location).to_track_quat('-Z','Y').to_euler();camera.keyframe_insert('location',frame=frame);camera.keyframe_insert('rotation_euler',frame=frame)
    for curve in camera.animation_data.action.layers[0].strips[0].channelbags[0].fcurves:
      for key in curve.keyframe_points:key.interpolation='LINEAR'
    marker_data={index:[] for index in range(len(points))}
    for frame in range(1,21):
      scene.frame_set(frame);scene.render.filepath=str(frames_dir/f'frame_{frame:04d}.png');bpy.ops.render.render(write_still=True)
      for index,point in enumerate(points):
        co=world_to_camera_view(scene,camera,Vector(point));assert 0<co.x<1 and 0<co.y<1 and co.z>0
        marker_data[index].append({'frame':frame,'co':[co.x,co.y]})
    # Turn a real foreground area into the required editor before calling the structured commands.
    window=bpy.context.window;area=next(area for area in window.screen.areas if area.type=='VIEW_3D');area.type='CLIP_EDITOR'
    registry=build_registry(bpy,approved_output_root=output,approved_asset_roots=(output,))
    focal=35/36*320
    clip=registry.dispatch('tracking.load_clip',{'name':'KnownTrackingClip','path':str(frames_dir/'frame_0001.png'),'focalLengthPixels':focal})['result']
    assert clip['duration']>=20,clip
    for index,markers in marker_data.items():registry.dispatch('tracking.add_track',{'clip':'KnownTrackingClip','name':f'Point{index:02d}','markers':markers})
    solved=registry.dispatch('tracking.solve_camera',{'clip':'KnownTrackingClip','keyframeA':1,'keyframeB':20})['result']
    setup=registry.dispatch('tracking.setup_scene',{'clip':'KnownTrackingClip'})['result']
    inspected=registry.dispatch('tracking.inspect',{'clip':'KnownTrackingClip'})['result']
    assert solved['reprojectionError']<1 and sum(track['hasBundle'] for track in inspected['tracks'])>=8
    path=output/'tracking_solution.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
    report|={'clip':clip,'solve':solved,'setup':setup,'tracks':len(inspected['tracks']),'bundles':sum(t['hasBundle'] for t in inspected['tracks']),
             'artifact':str(path),'passed':True,'productionAcceptance':True}
  except Exception as exc:  # noqa: BLE001
    report|={'passed':False,'productionAcceptance':False,'error':{'type':type(exc).__name__,'message':str(exc)}};traceback.print_exc()
  with (output/'acceptance.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
  bpy.ops.wm.quit_blender()

bpy.app.timers.register(run,first_interval=1)
