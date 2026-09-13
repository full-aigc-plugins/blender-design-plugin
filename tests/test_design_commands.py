import unittest
from types import SimpleNamespace

from scripts.harness.commands.object import ObjectCommands
from scripts.harness.commands.scene import SceneCommands
from scripts.harness.errors import HarnessError


class FakeObject:
    def __init__(self, name, object_type="MESH"):
        self.name = name
        self.type = object_type
        self.location = [0.0, 0.0, 0.0]
        self.rotation_euler = [0.0, 0.0, 0.0]
        self.scale = [1.0, 1.0, 1.0]
        self.parent = None
        self.modifiers = FakeModifiers()

    def select_set(self, _value):
        return None


class FakeModifiers(list):
    def new(self, name, type):
        modifier = SimpleNamespace(name=name, type=type, width=0.0)
        self.append(modifier)
        return modifier


class FakeObjects(dict):
    def __iter__(self):
        return iter(self.values())

    def get(self, key, default=None):
        return super().get(key, default)

    def remove(self, obj, do_unlink=True):
        self.pop(obj.name)


class FakeMeshOps:
    def __init__(self, bpy):
        self.bpy = bpy

    def _add(self):
        obj = FakeObject("Primitive")
        self.bpy.data.objects[obj.name] = obj
        self.bpy.context.object = obj

    primitive_cube_add = lambda self: self._add()
    primitive_uv_sphere_add = lambda self: self._add()
    primitive_cylinder_add = lambda self: self._add()
    primitive_cone_add = lambda self: self._add()
    primitive_plane_add = lambda self: self._add()
    primitive_torus_add = lambda self: self._add()


class FakeCurveOps(FakeMeshOps):
    def _add(self):
        obj = FakeObject("Curve", "CURVE")
        obj.data = SimpleNamespace()
        self.bpy.data.objects[obj.name] = obj
        self.bpy.context.object = obj

    primitive_bezier_curve_add = lambda self: self._add()


class FakeObjectOps:
    def __init__(self, bpy):
        self.bpy = bpy

    def text_add(self):
        obj = FakeObject("Text", "FONT")
        obj.data = SimpleNamespace(body="Text")
        self.bpy.data.objects[obj.name] = obj
        self.bpy.context.object = obj


class FakeBpy:
    def __init__(self):
        self.data = type("Data", (), {})()
        self.data.objects = FakeObjects()
        self.data.materials = []
        self.context = type("Context", (), {})()
        self.context.object = None
        self.context.scene = type("Scene", (), {"camera": None, "frame_start": 1, "frame_end": 250})()
        self.ops = type("Ops", (), {})()
        self.ops.mesh = FakeMeshOps(self)
        self.ops.curve = FakeCurveOps(self)
        self.ops.object = FakeObjectOps(self)


class TestSceneCommands(unittest.TestCase):
    def test_inspect_returns_deterministic_summary(self):
        bpy = FakeBpy()
        bpy.data.objects["B"] = FakeObject("B")
        bpy.data.objects["A"] = FakeObject("A", "CAMERA")
        result = SceneCommands(bpy).inspect({})
        self.assertEqual(result["result"]["objects"], ["A", "B"])
        self.assertEqual(result["result"]["objectDetails"][0], {"name": "A", "type": "CAMERA"})
        self.assertEqual(result["result"]["summary"]["cameras"], 1)


class TestObjectCommands(unittest.TestCase):
    def setUp(self):
        self.bpy = FakeBpy()
        self.commands = ObjectCommands(self.bpy)

    def test_create_mesh(self):
        result = self.commands.create_mesh({"primitive": "cube", "name": "Body"})
        self.assertEqual(result["changedObjects"], ["Body"])
        self.assertIn("Body", self.bpy.data.objects)

    def test_create_mesh_rejects_unknown_primitive(self):
        with self.assertRaises(HarnessError) as caught:
            self.commands.create_mesh({"primitive": "dragon", "name": "Body"})
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")

    def test_transform_updates_requested_vectors(self):
        self.commands.create_mesh({"primitive": "cube", "name": "Body"})
        self.commands.transform({"name": "Body", "location": [1, 2, 3], "scale": [2, 2, 1]})
        body = self.bpy.data.objects["Body"]
        self.assertEqual(body.location, [1.0, 2.0, 3.0])
        self.assertEqual(body.scale, [2.0, 2.0, 1.0])

    def test_rename_rejects_collision(self):
        self.bpy.data.objects["A"] = FakeObject("A")
        self.bpy.data.objects["B"] = FakeObject("B")
        with self.assertRaises(HarnessError) as caught:
            self.commands.rename({"name": "A", "newName": "B"})
        self.assertEqual(caught.exception.code, "NAME_COLLISION")

    def test_delete_removes_object(self):
        self.bpy.data.objects["Body"] = FakeObject("Body")
        self.commands.delete({"name": "Body"})
        self.assertNotIn("Body", self.bpy.data.objects)

    def test_add_modifier(self):
        self.bpy.data.objects["Body"] = FakeObject("Body")
        result = self.commands.add_modifier({"name": "Body", "modifier": "BEVEL", "settings": {"width": 0.2}})
        modifier = self.bpy.data.objects["Body"].modifiers[0]
        self.assertEqual(modifier.type, "BEVEL")
        self.assertEqual(modifier.width, 0.2)
        self.assertEqual(result["changedObjects"], ["Body"])

    def test_create_curve_and_text(self):
        curve = self.commands.create_curve({"name": "Path"})
        text = self.commands.create_text({"name": "Label", "text": "Codex"})
        self.assertEqual(curve["changedObjects"], ["Path"])
        self.assertEqual(text["changedObjects"], ["Label"])
        self.assertEqual(self.bpy.data.objects["Label"].data.body, "Codex")


if __name__ == "__main__":
    unittest.main()
