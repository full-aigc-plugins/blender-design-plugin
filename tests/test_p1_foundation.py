import unittest

from scripts.harness.errors import HarnessError
from scripts.harness.identity import ObjectResolver, OBJECT_ID_KEY
from scripts.harness.runtime import build_registry
from tests.test_design_commands import FakeBpy, FakeObject


class PropertyObject(FakeObject):
    def __init__(self, name):
        super().__init__(name)
        self.properties = {}

    def get(self, key, default=None):
        return self.properties.get(key, default)

    def __setitem__(self, key, value):
        self.properties[key] = value


class P1FoundationTests(unittest.TestCase):
    def test_stable_id_survives_rename_and_resolves(self):
        bpy = FakeBpy()
        obj = PropertyObject('Before')
        bpy.data.objects[obj.name] = obj
        resolver = ObjectResolver(bpy)
        stable_id = resolver.ensure_id(obj)
        self.assertTrue(stable_id.startswith('obj_'))
        obj.name = 'After'
        bpy.data.objects.pop('Before')
        bpy.data.objects['After'] = obj
        self.assertIs(resolver.resolve({'objectId': stable_id}), obj)
        self.assertEqual(obj.get(OBJECT_ID_KEY), stable_id)

    def test_duplicate_stable_ids_are_repaired_deterministically(self):
        bpy = FakeBpy()
        first, second = PropertyObject('A'), PropertyObject('B')
        first[OBJECT_ID_KEY] = 'obj_same'
        second[OBJECT_ID_KEY] = 'obj_same'
        bpy.data.objects['A'], bpy.data.objects['B'] = first, second
        resolver = ObjectResolver(bpy)
        self.assertIs(resolver.resolve({'objectId': 'obj_same'}), first)
        self.assertNotEqual(resolver.ensure_id(second), 'obj_same')

    def test_explicit_new_id_never_steals_source_identity(self):
        bpy=FakeBpy(); source=PropertyObject('ZSource'); copied=PropertyObject('ACopy')
        bpy.data.objects[source.name]=source; resolver=ObjectResolver(bpy); source_id=resolver.ensure_id(source)
        copied[OBJECT_ID_KEY]=source_id; bpy.data.objects[copied.name]=copied
        copied_id=resolver.assign_new_id(copied)
        self.assertNotEqual(copied_id,source_id)
        self.assertEqual(source.get(OBJECT_ID_KEY),source_id)

    def test_name_and_id_must_identify_same_object(self):
        bpy = FakeBpy()
        a, b = PropertyObject('A'), PropertyObject('B')
        bpy.data.objects['A'], bpy.data.objects['B'] = a, b
        resolver = ObjectResolver(bpy)
        with self.assertRaises(HarnessError):
            resolver.resolve({'name': 'A', 'objectId': resolver.ensure_id(b)})

    def test_p1_commands_are_registered_without_placeholders(self):
        registry = build_registry(FakeBpy())
        expected = {
            'scene.set_units', 'collection.create', 'collection.move_object',
            'object.describe', 'object.duplicate', 'object.instance',
            'object.set_visibility', 'object.apply_transform', 'object.set_origin',
            'object.set_display',
            'mesh.inspect', 'mesh.select', 'mesh.edit',
            'modifier.list', 'modifier.configure', 'modifier.move',
            'modifier.set_enabled', 'modifier.apply', 'modifier.remove',
            'collection.set_visibility', 'object.join', 'object.separate',
            'curve.create', 'curve.configure', 'curve.to_mesh',
            'asset.import_file', 'asset.library',
            'recipe.hard_surface_shell', 'recipe.spear',
            'uv.mark_seams', 'uv.unwrap', 'uv.pack', 'uv.inspect',
            'material.connect_image_texture', 'material.inspect_nodes',
            'recipe.desktop_speaker',
            'camera.aim_at',
            'rig.create_armature','rig.bind','rig.assign_weights','rig.inspect','rig.create_control',
            'constraint.add_bone','constraint.add_object','constraint.keyframe_influence',
            'animation.pose_keyframe','recipe.rigged_spear_character',
            'animation.action_list','animation.fcurve_edit','animation.nla_add_strip',
            'animation.shape_key_add','animation.shape_key_keyframe','animation.retarget',
            'camera.follow_path','validation.prop_handoff','validation.foot_drift',
            'validation.limb_length','validation.floor_penetration','validation.camera_visibility',
            'validation.motion_discontinuity','job.submit','job.status','job.cancel','job.recover',
            'geometry_nodes.create_group','geometry_nodes.add_node','geometry_nodes.connect',
            'geometry_nodes.set_node_input','geometry_nodes.set_modifier_input','geometry_nodes.inspect',
            'recipe.procedural_courtyard','recipe.update_procedural_courtyard',
            'sculpt.set_mask','sculpt.displace','sculpt.voxel_remesh','sculpt.multires','sculpt.cleanup',
            'hair.create_curves','hair.inspect','simulation.rigid_body','simulation.collision',
            'simulation.cloth','simulation.soft_body','simulation.quick_smoke','simulation.cache_status',
            'simulation.free_cache',
            'material.create_node_group','material.bake','asset.pack_resources','asset.make_paths_relative',
            'render.configure','render.configure_passes','render.inspect','compositor.configure','compositor.inspect',
            'export.extended',
            'grease_pencil.create','grease_pencil.add_material','grease_pencil.add_stroke','grease_pencil.inspect',
            'sequence.add','sequence.trim','sequence.move','sequence.transition','sequence.set_volume','sequence.inspect','sequence.configure_output',
            'tracking.load_clip','tracking.add_track','tracking.solve_camera','tracking.setup_scene','tracking.inspect',
            'rig.rigify_status','rig.rigify_generate',
            'compositor.add_tracking_mask',
            'animation.fcurve_clean','camera.add_handheld','render.create_view_layer',
            'sculpt.brush_stroke',
        }
        registered = {item['command'] for item in registry.capabilities()}
        self.assertTrue(expected <= registered)

    def test_mesh_edit_schema_requires_versioned_selection(self):
        description = build_registry(FakeBpy()).describe_capability({'id': 'mesh.edit'})
        self.assertIn('selection', description['input']['required'])
        self.assertIn('operation', description['input']['required'])
        self.assertEqual(description['domain'], 'mesh')

    def test_legacy_object_commands_accept_stable_id_locators(self):
        registry = build_registry(FakeBpy())
        for name in ('object.transform', 'object.rename', 'object.delete'):
            schema = registry.describe_capability({'id': name})['input']
            self.assertIn('objectId', schema['properties'], name)
        parent = registry.describe_capability({'id': 'object.parent'})['input']['properties']
        self.assertIn('childObjectId', parent)
        self.assertIn('parentObjectId', parent)
