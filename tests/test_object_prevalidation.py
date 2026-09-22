import unittest

from scripts.harness.commands.curve import CurveCommands
from scripts.harness.commands.object import ObjectCommands
from scripts.harness.errors import HarnessError
from tests.test_design_commands import FakeBpy


class ObjectPrevalidationTests(unittest.TestCase):
    def test_failed_modifier_configuration_does_not_leave_modifier(self):
        bpy = FakeBpy()
        commands = ObjectCommands(bpy)
        commands.create_mesh({'name': 'Body', 'primitive': 'cube'})
        with self.assertRaises(HarnessError):
            commands.add_modifier({'name': 'Body', 'modifier': 'BEVEL',
                                   'settings': {'width': .1, 'not_a_property': 1}})
        self.assertEqual(len(bpy.data.objects['Body'].modifiers), 0)

    def test_modifier_settings_must_be_an_object(self):
        bpy = FakeBpy()
        commands = ObjectCommands(bpy)
        commands.create_mesh({'name': 'Body', 'primitive': 'cube'})
        with self.assertRaises(HarnessError):
            commands.add_modifier({'name': 'Body', 'modifier': 'BEVEL', 'settings': []})
        self.assertEqual(len(bpy.data.objects['Body'].modifiers), 0)

    def test_invalid_curve_and_text_parameters_do_not_create(self):
        for method, args in [('create_curve', {'bevelDepth': -1}),
                             ('create_text', {'text': 'A', 'size': float('nan')}),
                             ('create_text', {'text': 'A', 'extrude': -1})]:
            with self.subTest(method=method, args=args):
                bpy = FakeBpy()
                with self.assertRaises(HarnessError):
                    getattr(ObjectCommands(bpy), method)({'name': 'Invalid', **args})
                self.assertEqual(len(bpy.data.objects), 0)

    def test_explicit_curve_settings_are_validated_before_data_creation(self):
        for args in ({'resolution':0},{'bevelResolution':-1}):
            bpy=FakeBpy()
            with self.assertRaises(HarnessError):CurveCommands(bpy).create({'name':'Invalid','points':[[0,0,0],[1,0,0]],**args})
            self.assertEqual(len(bpy.data.objects),0)

    def test_join_name_collision_is_rejected_before_operator_context(self):
        bpy=FakeBpy();commands=ObjectCommands(bpy)
        for name in ('A','B','Existing'):commands.create_mesh({'name':name,'primitive':'cube'})
        before=set(bpy.data.objects)
        with self.assertRaises(HarnessError):commands.join({'objects':[{'name':'A'},{'name':'B'}],'newName':'Existing'})
        self.assertEqual(set(bpy.data.objects),before)

    def test_parent_rejects_cycle_without_changing_existing_hierarchy(self):
        bpy = FakeBpy()
        commands = ObjectCommands(bpy)
        for name in ['A', 'B']:
            commands.create_mesh({'name': name, 'primitive': 'cube'})
        commands.parent({'child': 'B', 'parent': 'A'})
        with self.assertRaises(HarnessError):
            commands.parent({'child': 'A', 'parent': 'B'})
        self.assertIsNone(bpy.data.objects['A'].parent)

    def test_invalid_transform_does_not_create_object(self):
        for vector in ([0, 0], [0, float('nan'), 0], [0, float('inf'), 0]):
            bpy = FakeBpy()
            with self.assertRaises(HarnessError):
                ObjectCommands(bpy).create_mesh({'name': 'Invalid', 'primitive': 'cube', 'scale': vector})
            self.assertEqual(len(bpy.data.objects), 0)

    def test_invalid_late_field_does_not_apply_earlier_field(self):
        bpy = FakeBpy()
        commands = ObjectCommands(bpy)
        commands.create_mesh({'name': 'Body', 'primitive': 'cube'})
        with self.assertRaises(HarnessError):
            commands.transform({'name': 'Body', 'location': [3, 2, 1], 'scale': [0, 0]})
        self.assertEqual(bpy.data.objects['Body'].location, [0, 0, 0])
