"""Enable bundled Rigify, persist preferences, and generate a real control rig."""

import json
import sys
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
registry=build_registry(bpy,approved_output_root=output)
before=registry.dispatch('rig.rigify_status',{})['result']
installed=registry.dispatch('rig.rigify_install',{'allowDownload':False,'savePreferences':True})['result']
assert installed['enabled'] and installed['operatorAvailable'] and installed['mode'] in {'bundled-enable','already-enabled'}
assert not installed.get('downloadAttempted',False)
bpy.ops.object.armature_human_metarig_add();metarig=bpy.context.object;metarig.name='L4 MetaRig'
generated=registry.dispatch('rig.rigify_generate',{'name':metarig.name})['result']
assert generated['created'],generated
blend=output/'rigify-generated.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend));bpy.ops.wm.open_mainfile(filepath=str(blend))
assert any(obj.type=='ARMATURE' and obj.name!='L4 MetaRig' for obj in bpy.data.objects)
report={'blender':bpy.app.version_string,'platform':sys.platform,'before':before,'install':installed,
        'generatedObjects':len(generated['created']),'blend':str(blend),'technicalAcceptance':True,
        'downloadAttempted':False,'license':'GPL (bundled Rigify)','productionAcceptance':sys.platform.startswith('win')}
(output/'p9-rigify-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('P9_RIGIFY='+json.dumps(report))
