"""Real Blender acceptance for extended VSE sources, transitions, speed and audio automation."""

import json
import math
import struct
import sys
import wave
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)

images=[]
for index,color in enumerate(((.8,.1,.1,1),(.1,.8,.1,1),(.1,.1,.8,1))):
    path=output/f'frame-{index}.png';image=bpy.data.images.new(f'Frame{index}',width=160,height=90)
    image.generated_color=color;image.save_render(str(path));bpy.data.images.remove(image);images.append(str(path))
for index,frequency in enumerate((220,330)):
    with wave.open(str(output/f'tone-{index}.wav'),'wb') as audio:
        audio.setparams((1,2,24000,24000,'NONE','not compressed'))
        audio.writeframes(b''.join(struct.pack('<h',int(1200*math.sin(2*math.pi*frequency*i/24000))) for i in range(24000)))

shot=bpy.data.scenes.new('ShotScene');shot.frame_start=1;shot.frame_end=20
shot.render.resolution_x=160;shot.render.resolution_y=90;shot.render.resolution_percentage=100
bpy.context.window.scene=shot
bpy.ops.object.camera_add(location=(0,-4,2));shot.camera=bpy.context.object
bpy.context.window.scene=bpy.data.scenes['Scene']
registry=build_registry(bpy,approved_output_root=output,approved_asset_roots=(output,))
registry.dispatch('sequence.add',{'type':'SCENE','name':'SceneSource','scene':'ShotScene','channel':1,'frameStart':1,'duration':20})
registry.dispatch('sequence.add',{'type':'IMAGE_SEQUENCE','name':'Frames','paths':images,'channel':2,'frameStart':10})
registry.dispatch('sequence.add',{'type':'TEXT','name':'Caption','text':'Codex Video','duration':24,'channel':3,'frameStart':1,'fontSize':32})
registry.dispatch('sequence.transition',{'name':'SceneWipe','first':'SceneSource','second':'Frames','channel':4,'transitionType':'WIPE'})
registry.dispatch('sequence.set_speed',{'name':'FramesSpeed','source':'Frames','channel':5,'factor':1.5,'interpolate':True})
for index,start in ((0,1),(1,10)):
    registry.dispatch('sequence.add',{'type':'SOUND','name':f'Tone{index}','path':str(output/f'tone-{index}.wav'),'channel':6+index,'frameStart':start,'duration':20})
audio_crossfade=registry.dispatch('sequence.transition',{'name':'AudioCrossfade','first':'Tone0','second':'Tone1','channel':8,'transitionType':'SOUND_CROSSFADE'})['result']
registry.dispatch('sequence.keyframe_volume',{'name':'Tone0','frame':10,'volume':.25})
timeline=registry.dispatch('sequence.inspect',{})['result']
types={item['name']:item['type'] for item in timeline['strips']}
assert types['SceneSource']=='SCENE' and types['Frames']=='IMAGE' and types['Caption']=='TEXT'
assert types['SceneWipe']=='WIPE' and types['FramesSpeed']=='SPEED' and audio_crossfade['type']=='SOUND_CROSSFADE'
blend=output/'vse-extended.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend));bpy.ops.wm.open_mainfile(filepath=str(blend))
reopened=build_registry(bpy).dispatch('sequence.inspect',{})['result'];assert len(reopened['strips'])==7,reopened
report={'blender':bpy.app.version_string,'timeline':timeline,'audioCrossfade':audio_crossfade,'blend':str(blend),'technicalAcceptance':True,
        'visualAcceptance':'editor-structure-only','productionAcceptance':False}
(output/'p8-vse-extended-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('P8_VSE_EXTENDED='+json.dumps(report))
