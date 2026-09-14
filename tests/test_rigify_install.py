import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.harness.commands.rig import RigCommands


class RigifyInstallTests(unittest.TestCase):
    def test_install_command_is_gated_and_closed(self):
        from scripts.harness.runtime import build_registry
        from tests.test_design_commands import FakeBpy
        capability=build_registry(FakeBpy()).describe_capability({'id':'rig.rigify_install'})
        self.assertEqual(capability['risk'],'gated')
        self.assertEqual(set(capability['input']['properties']),{'allowDownload','savePreferences'})

    def test_bundled_rigify_is_enabled_without_network_and_preferences_are_saved(self):
        class Addons(dict):
            def __iter__(self):return iter(self.values())
        addons=Addons();events=[]
        preferences=SimpleNamespace(addons=addons,system=SimpleNamespace(use_online_access=False),
                                    extensions=SimpleNamespace(repos=[]))
        def enable(**kwargs):addons['rigify']=SimpleNamespace(module='rigify');events.append(('enable',kwargs));return {'FINISHED'}
        bpy=SimpleNamespace(context=SimpleNamespace(preferences=preferences),app=SimpleNamespace(version_string='5.2.1'),
          ops=SimpleNamespace(preferences=SimpleNamespace(addon_enable=enable),wm=SimpleNamespace(save_userpref=lambda:events.append(('save',{})) or {'FINISHED'}),
                              pose=SimpleNamespace(rigify_generate=lambda:{'FINISHED'})))
        addon_utils=SimpleNamespace(modules=lambda:[SimpleNamespace(__name__='rigify')])
        with patch.dict(sys.modules,{'addon_utils':addon_utils}):
            result=RigCommands(bpy).rigify_install({'allowDownload':False,'savePreferences':True})['result']
        self.assertEqual(result['mode'],'bundled-enable');self.assertTrue(result['enabled'])
        self.assertEqual([event[0] for event in events],['enable','save'])

    def test_status_accepts_blender_addon_collection_objects(self):
        class AddonCollection:
            def get(self,_name):return None
            def __iter__(self):return iter([SimpleNamespace(module='bl_ext.blender_org.rigify')])
        bpy=SimpleNamespace(context=SimpleNamespace(preferences=SimpleNamespace(addons=AddonCollection())),
          app=SimpleNamespace(version_string='5.2.1'),ops=SimpleNamespace(pose=SimpleNamespace(rigify_generate=lambda:{'FINISHED'})))
        with patch.dict(sys.modules,{'addon_utils':SimpleNamespace(modules=lambda:[])}):
            status=RigCommands(bpy).rigify_status({})['result']
        self.assertTrue(status['enabled']);self.assertTrue(status['operatorAvailable'])


if __name__=='__main__':unittest.main()
