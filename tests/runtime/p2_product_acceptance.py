"""P2-A desktop speaker, visual preview, reopen and GLB reimport acceptance."""
import json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
registry=build_registry(bpy,approved_output_root=output,approved_asset_roots=(output,))
if bpy.data.objects.get('Cube'): registry.dispatch('object.set_visibility',{'name':'Cube','viewport':False,'render':False})
registry.dispatch('scene.set_units',{'system':'METRIC','scaleLength':1})
speaker=registry.dispatch('recipe.desktop_speaker',{'name':'DesktopSpeaker','dimensions':[.42,.26,.68],
                                                    'bevelWidth':.012,'wallThickness':.018})['result']
assert set(speaker['parts'])=={'Housing','Grille','Knob','Interface','Base'}
for axis,want in enumerate((.42,.26,.68)):
    assert abs(bpy.data.objects['DesktopSpeaker_Housing'].dimensions[axis]-want)/want<=.005
assert [m.type for m in bpy.data.objects['DesktopSpeaker_Housing'].modifiers]==['BOOLEAN','BEVEL','SUBSURF']
assert speaker['wallThickness']==.018 and bpy.data.objects[speaker['helper']['name']].display_type=='WIRE'
assert speaker['uv']['Housing']['hasUV'] and speaker['uv']['Grille']['hasUV']

# Fixture texture created locally; command owns the image-node semantics.
texture=output/'roughness.png'; image=bpy.data.images.new('RoughnessFixture',width=4,height=4)
image.generated_color=(.45,.45,.45,1); image.save_render(str(texture)); bpy.data.images.remove(image)
connected=registry.dispatch('material.connect_image_texture',{'material':'DesktopSpeaker_Grille_Mat',
 'path':str(texture),'usage':'ROUGHNESS'})['result']
nodes=registry.dispatch('material.inspect_nodes',{'material':'DesktopSpeaker_Grille_Mat'})['result']
assert connected['colorSpace']=='Non-Color' and any(link['toSocket']=='Roughness' for link in nodes['links'])

ground=registry.dispatch('object.create_mesh',{'name':'ProductGround','primitive':'plane','scale':[.7,.7,1]})['result']
registry.dispatch('material.create_pbr',{'name':'ProductGroundMat','baseColor':[.025,.03,.04,1],'roughness':.7})
registry.dispatch('material.assign',{'object':'ProductGround','material':'ProductGroundMat'})
registry.dispatch('light.set_world_color',{'color':[.02,.025,.035]})
registry.dispatch('light.create',{'name':'ProductKey','type':'AREA','location':[-2,-3,4],'energy':1000,'size':3})
registry.dispatch('light.create',{'name':'ProductRim','type':'AREA','location':[2,1,3],'energy':700,'size':2,'color':[.4,.6,1]})
registry.dispatch('camera.create',{'name':'ProductCamera','location':[1.35,-2.1,1.15],'lens':62,'active':True})
registry.dispatch('camera.aim_at',{'name':'ProductCamera','target':[0,0,.34]})
preview=registry.dispatch('preview.capture',{'snapshotId':'p2-product','milestone':'desktop_speaker',
                                             'width':640,'height':640})['result']['milestone']
blend_path=output/'desktop_speaker.blend'; glb_path=output/'desktop_speaker.glb'
blend=registry.dispatch('export.file',{'path':str(blend_path),'snapshotId':'p2-product','sessionId':'p2a'})['result']['artifact']
glb=registry.dispatch('export.file',{'path':str(glb_path),'snapshotId':'p2-product','sessionId':'p2a','parameters':{'use_renderable':True}})['result']['artifact']
bpy.ops.wm.open_mainfile(filepath=str(blend_path))
assert set(speaker['parts'])=={'Housing','Grille','Knob','Interface','Base'}
assert bpy.data.objects.get('DesktopSpeaker_Housing') and bpy.data.materials.get('DesktopSpeaker_Grille_Mat')
reopen={'partsEditable':True,'modifierOrder':True,'uvLayers':True,'textureAvailable':bpy.data.images.get('roughness.png') is not None}
bpy.ops.wm.read_factory_settings(use_empty=True)
reimport=build_registry(bpy,approved_asset_roots=(output,)).dispatch('asset.import_file',{'path':str(glb_path)})['result']
assert len(reimport['objects'])>=5 and len(bpy.data.materials)>=5
report={'blender':bpy.app.version_string,'artifact':blend,'glb':glb,'preview':preview,
 'dimensions':speaker['dimensions'],'parts':sorted(speaker['parts']),'reopen':reopen,
 'reimport':{'objects':len(reimport['objects']),'materials':len(bpy.data.materials)},
 'technicalAcceptance':True,'visualAcceptance':'pending-model-review','productionAcceptance':False}
with (output/'acceptance.json').open('x',encoding='utf-8') as stream: json.dump(report,stream,ensure_ascii=False,indent=2)
print('P2_PRODUCT='+json.dumps(report,ensure_ascii=False))
