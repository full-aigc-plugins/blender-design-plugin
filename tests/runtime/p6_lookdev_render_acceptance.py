"""P6 packed lookdev, Eevee/Cycles, compositor and extended delivery acceptance."""
import json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry
assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
registry=build_registry(bpy,approved_output_root=output,approved_asset_roots=(output,))
if bpy.data.objects.get('Cube'):registry.dispatch('object.set_visibility',{'name':'Cube','viewport':False,'render':False})
speaker=registry.dispatch('recipe.desktop_speaker',{'name':'RenderSpeaker','dimensions':[.42,.26,.68],'bevelWidth':.012,'wallThickness':.018})['result']
housing=speaker['parts']['Housing'];grille=speaker['parts']['Grille']
group=registry.dispatch('material.create_node_group',{'material':'RenderSpeaker_Housing_Mat','groupName':'Speaker Surface Controls',
 'baseColor':[.08,.16,.3,1],'roughness':.28})['result']
assert len(group['inputs'])==2
registry.dispatch('camera.create',{'name':'RenderCamera','location':[1.4,-2.2,1.15],'lens':62,'active':True});registry.dispatch('camera.aim_at',{'name':'RenderCamera','target':[0,0,.34]})
registry.dispatch('light.set_world_color',{'color':[.015,.02,.035]});registry.dispatch('light.create',{'name':'RenderKey','type':'AREA','location':[-2,-3,4],'energy':1100,'size':3})
registry.dispatch('light.create',{'name':'RenderRim','type':'AREA','location':[2,1,3],'energy':850,'size':2,'color':[.35,.55,1]})
cycles=registry.dispatch('render.configure',{'engine':'CYCLES','device':'CPU','width':320,'height':320,'samples':8,
 'transparent':True,'exposure':.3})['result'];assert cycles['device']=='CPU'
registry.dispatch('render.configure_passes',{'passes':['Z','NORMAL','DIFFUSE_COLOR','EMISSION']})
beauty=registry.dispatch('render.create_view_layer',{'name':'Beauty'})['result'];registry.dispatch('render.configure_passes',{'viewLayer':'Beauty','passes':['Z','NORMAL']})
assert bpy.context.scene.view_layers['Beauty'].use_pass_z and bpy.context.scene.view_layers['Beauty'].use_pass_normal
bake=registry.dispatch('material.bake',{'object':{'objectId':housing['objectId']},'relativePath':'bakes/housing_roughness.png',
 'bakeType':'ROUGHNESS','width':64,'height':64,'margin':4})['result']
registry.dispatch('material.connect_image_texture',{'material':'RenderSpeaker_Housing_Mat','path':bake['path'],'usage':'ROUGHNESS'})
draft=registry.dispatch('export.file',{'path':str(output/'lookdev_working.blend'),'snapshotId':'p6-draft','sessionId':'p6'})['result']['artifact']
registry.dispatch('asset.make_paths_relative',{});packed=registry.dispatch('asset.pack_resources',{})['result']
assert packed['count']>=1
registry.dispatch('render.configure',{'engine':'BLENDER_EEVEE_NEXT','width':320,'height':320,'samples':16,'transparent':False,'exposure':.2})
composite=registry.dispatch('compositor.configure',{'exposure':.15,'glare':True})['result'];assert composite['glare']
assert registry.dispatch('compositor.inspect',{})['result']['links']
preview=registry.dispatch('export.file',{'path':str(output/'lookdev.png'),'snapshotId':'p6','sessionId':'p6'})['result']['artifact']
exr=registry.dispatch('export.extended',{'path':str(output/'lookdev.exr'),'format':'exr'})['result']['artifact']
usd=registry.dispatch('export.extended',{'path':str(output/'speaker.usdc'),'format':'usdc'})['result']['artifact']
abc=registry.dispatch('export.extended',{'path':str(output/'speaker.abc'),'format':'abc'})['result']['artifact']
standalone=output/'standalone';standalone.mkdir()
blend=registry.dispatch('export.file',{'path':str(standalone/'packed_speaker.blend'),'snapshotId':'p6','sessionId':'p6'})['result']['artifact']
bpy.ops.wm.open_mainfile(filepath=blend['path'])
packed_after=[image.name for image in bpy.data.images if image.packed_file]
assert packed_after and bpy.data.node_groups.get('Speaker Surface Controls') and bpy.context.scene.use_nodes
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.wm.usd_import(filepath=usd['path']);usd_objects=len(bpy.data.objects);assert usd_objects>=5
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.wm.alembic_import(filepath=abc['path']);abc_objects=len(bpy.data.objects);assert abc_objects>=5
image=bpy.data.images.load(exr['path']);assert image.size[0]==320 and image.size[1]==320
report={'blender':bpy.app.version_string,'cycles':cycles,'passes':['Z','NORMAL','DIFFUSE_COLOR','EMISSION'],
 'bake':bake,'packedImages':packed_after,'compositor':composite,'artifacts':{'draft':draft,'png':preview,'exr':exr,'usd':usd,'abc':abc,'blend':blend},
 'reimport':{'usdObjects':usd_objects,'abcObjects':abc_objects,'exrSize':[320,320]},
 'technicalAcceptance':True,'visualAcceptance':'pending-model-review','productionAcceptance':False}
with (output/'acceptance.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
print('P6_ACCEPTANCE='+json.dumps(report))
