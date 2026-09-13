"""P7 Grease Pencil and VSE local-delivery acceptance."""
import json,math,struct,subprocess,sys,wave
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry
assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)

# Approved local fixture media.
for name,color in [('warm',(0.8,.12,.04,1)),('cool',(.03,.2,.8,1))]:
    image=bpy.data.images.new(name,width=320,height=240);image.generated_color=color;image.save_render(str(output/f'{name}.png'));bpy.data.images.remove(image)
with wave.open(str(output/'tone.wav'),'wb') as audio:
    audio.setparams((1,2,24000,48000,'NONE','not compressed'))
    audio.writeframes(b''.join(struct.pack('<h',int(1800*math.sin(2*math.pi*220*i/24000))) for i in range(48000)))

registry=build_registry(bpy,approved_output_root=output,approved_asset_roots=(output,))
if bpy.data.objects.get('Cube'):registry.dispatch('object.set_visibility',{'name':'Cube','viewport':False,'render':False})
gp=registry.dispatch('grease_pencil.create',{'name':'StoryboardLines','layers':['Action','Notes'],'inFront':True})['result']
material=registry.dispatch('grease_pencil.add_material',{'objectId':gp['objectId'],'material':'Ink','color':[.9,.15,.04,1]})['result']
for frame,offset in [(1,0),(12,.25)]:
    registry.dispatch('grease_pencil.add_stroke',{'objectId':gp['objectId'],'layer':'Action','frame':frame,'materialIndex':material['index'],
      'points':[{'position':[-.8+offset,0,0],'radius':.08},{'position':[0+offset,0,.8],'radius':.12},{'position':[.8+offset,0,0],'radius':.08}]})
gp_info=registry.dispatch('grease_pencil.inspect',{'objectId':gp['objectId']})['result'];assert [layer['name'] for layer in gp_info['layers']]==['Action','Notes'];assert gp_info['materials']==['Ink'];assert len(next(layer for layer in gp_info['layers'] if layer['name']=='Action')['frames'])==2
registry.dispatch('camera.create',{'name':'GP Camera','location':[0,-6,.3],'lens':55,'active':True});registry.dispatch('camera.aim_at',{'name':'GP Camera','target':[0,0,.3]})
preview=registry.dispatch('preview.capture',{'snapshotId':'p7-gp','milestone':'grease_pencil','width':640,'height':480})['result']['milestone']

registry.dispatch('sequence.add',{'type':'IMAGE','name':'Warm','path':str(output/'warm.png'),'channel':1,'frameStart':1,'duration':30})
registry.dispatch('sequence.add',{'type':'IMAGE','name':'Cool','path':str(output/'cool.png'),'channel':2,'frameStart':21,'duration':30})
registry.dispatch('sequence.trim',{'name':'Warm','frameStart':1,'frameEnd':31});registry.dispatch('sequence.move',{'name':'Cool','frameStart':21,'channel':2})
registry.dispatch('sequence.transition',{'name':'WarmToCool','first':'Warm','second':'Cool','channel':3})
registry.dispatch('sequence.add',{'type':'SOUND','name':'Tone','path':str(output/'tone.wav'),'channel':4,'frameStart':1})
registry.dispatch('sequence.set_volume',{'name':'Tone','volume':.35})
registry.dispatch('sequence.configure_output',{'frameStart':1,'frameEnd':50,'width':320,'height':240,'fps':24})
timeline=registry.dispatch('sequence.inspect',{})['result'];assert len(timeline['strips'])==4
video=registry.dispatch('export.file',{'path':str(output/'timeline.mp4'),'snapshotId':'p7','sessionId':'p7'})['result']['artifact']
audio_streams=subprocess.run(['ffprobe','-v','error','-select_streams','a','-show_entries','stream=codec_name','-of','json',video['path']],capture_output=True,text=True,check=True)
assert json.loads(audio_streams.stdout)['streams'][0]['codec_name']=='aac'
blend=registry.dispatch('export.file',{'path':str(output/'gp_vse.blend'),'snapshotId':'p7','sessionId':'p7'})['result']['artifact']
bpy.ops.wm.open_mainfile(filepath=blend['path']);reopened=build_registry(bpy).dispatch('sequence.inspect',{})['result']
assert len(reopened['strips'])==4 and len(bpy.data.objects['StoryboardLines'].data.layers['Action'].frames)==2
report={'blender':bpy.app.version_string,'greasePencil':gp_info,'timeline':timeline,'video':video,'blend':blend,'preview':preview,
 'technicalAcceptance':True,'visualAcceptance':'pending-model-review','productionAcceptance':False}
with (output/'acceptance.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
print('P7_GP_VSE='+json.dumps(report))
