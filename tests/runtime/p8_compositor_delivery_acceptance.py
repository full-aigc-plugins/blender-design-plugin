"""Real Blender acceptance for compositor file output and VSE compositor modifier."""

import json
import sys
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
image=bpy.data.images.new('CompositorInput',width=160,height=90);image.generated_color=(.2,.4,.8,1)
image_path=output/'input.png';image.save_render(str(image_path));bpy.data.images.remove(image)
registry=build_registry(bpy,approved_output_root=output,approved_asset_roots=(output,))
registry.dispatch('compositor.configure',{'exposure':.25,'glare':False})
file_output=registry.dispatch('compositor.add_file_output',{'name':'Delivery Output','outputDir':str(output/'compositor-frames'),
  'baseName':'shot','format':'OPEN_EXR_MULTILAYER','colorDepth':'16'})['result']
group=registry.dispatch('compositor.create_strip_group',{'name':'Strip Look','exposure':.5})['result']
registry.dispatch('sequence.add',{'type':'IMAGE','name':'Input','path':str(image_path),'channel':1,'frameStart':1,'duration':10})
modifier=registry.dispatch('sequence.add_compositor_modifier',{'strip':'Input','name':'Look','groupName':'Strip Look'})['result']
assert file_output['format']=='OPEN_EXR_MULTILAYER' and group['name']=='Strip Look' and modifier['type']=='COMPOSITOR'
blend=output/'compositor-delivery.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend));bpy.ops.wm.open_mainfile(filepath=str(blend))
strip=bpy.context.scene.sequence_editor.strips['Input'];assert strip.modifiers['Look'].node_group.name=='Strip Look'
node=bpy.context.scene.compositing_node_group.nodes['Delivery Output'];assert getattr(node,'directory',getattr(node,'base_path',None))==str((output/'compositor-frames').resolve())
report={'blender':bpy.app.version_string,'fileOutput':file_output,'stripGroup':group,'modifier':modifier,
        'blend':str(blend),'technicalAcceptance':True,'visualAcceptance':'node-structure-only','productionAcceptance':False}
(output/'p8-compositor-delivery-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('P8_COMPOSITOR_DELIVERY='+json.dumps(report))
