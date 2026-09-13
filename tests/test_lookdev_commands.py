import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace

from scripts.harness.commands.animation import AnimationCommands
from scripts.harness.commands.camera import CameraCommands
from scripts.harness.commands.light import LightCommands
from scripts.harness.commands.material import MaterialCommands
from scripts.harness.errors import HarnessError
from scripts.harness.path_policy import PathPolicy


class Socket:
    def __init__(self, value=None):
        self.default_value = value


class Node:
    def __init__(self):
        self.inputs = {
            "Base Color": Socket(), "Metallic": Socket(), "Roughness": Socket(), "Alpha": Socket()
        }


class Materials(dict):
    def new(self, name):
        material = SimpleNamespace(
            name=name,
            use_nodes=False,
            node_tree=SimpleNamespace(nodes=SimpleNamespace(get=lambda _name: Node())),
        )
        self[name] = material
        return material


class Objects(dict):
    def __iter__(self):
        return iter(self.values())


class Ops:
    def __init__(self, bpy):
        self.bpy = bpy
        self.object = SimpleNamespace(camera_add=self.camera_add, light_add=self.light_add)

    def camera_add(self, location=None, rotation=None):
        obj = SimpleNamespace(name="Camera", type="CAMERA", location=location, rotation_euler=rotation, data=SimpleNamespace(lens=50.0))
        self.bpy.data.objects[obj.name] = obj
        self.bpy.context.object = obj

    def light_add(self, type="AREA", location=None):
        obj = SimpleNamespace(name="Light", type="LIGHT", location=location, data=SimpleNamespace(type=type, energy=10.0, color=(1, 1, 1), shape="DISK", size=1.0))
        self.bpy.data.objects[obj.name] = obj
        self.bpy.context.object = obj


class Bpy:
    def __init__(self):
        self.data = SimpleNamespace(objects=Objects(), materials=Materials())
        self.context = SimpleNamespace(object=None, scene=SimpleNamespace(camera=None, frame_start=1, frame_end=250, world=SimpleNamespace(color=(0, 0, 0))))
        self.ops = Ops(self)


class MeshObject:
    def __init__(self, name):
        self.name = name
        self.type = "MESH"
        self.data = SimpleNamespace(materials=[])
        self.keyframes = []

    def keyframe_insert(self, data_path, frame):
        self.keyframes.append((data_path, frame))


class TestLookdevCommands(unittest.TestCase):
    def setUp(self):
        self.bpy = Bpy()
        self.bpy.data.objects["Body"] = MeshObject("Body")

    def test_create_and_assign_pbr_material(self):
        commands = MaterialCommands(self.bpy)
        result = commands.create_pbr({"name": "Blue", "baseColor": [0.1, 0.2, 0.8, 1.0], "metallic": 0.4, "roughness": 0.25})
        commands.assign({"object": "Body", "material": "Blue"})
        self.assertEqual(result["result"]["name"], "Blue")
        self.assertEqual(self.bpy.data.objects["Body"].data.materials[0].name, "Blue")

    def test_invalid_camera_properties_do_not_leave_objects(self):
        for lens in (-1, float('nan'), float('inf'), True):
            with self.subTest(lens=lens):
                self.setUp()
                before = set(self.bpy.data.objects.keys())
                with self.assertRaises(HarnessError):
                    CameraCommands(self.bpy).create({'name': 'InvalidCamera', 'lens': lens})
                self.assertEqual(set(self.bpy.data.objects.keys()), before)

    def test_invalid_light_properties_do_not_leave_objects(self):
        for params in ({'energy': -1}, {'energy': float('nan')}, {'color': [1]}, {'size': -2}):
            with self.subTest(params=params):
                self.setUp()
                before = set(self.bpy.data.objects.keys())
                with self.assertRaises(HarnessError):
                    LightCommands(self.bpy).create({'name': 'InvalidLight', **params})
                self.assertEqual(set(self.bpy.data.objects.keys()), before)

    def test_invalid_material_properties_do_not_leave_datablocks(self):
        for params in ({'roughness': 2}, {'metallic': float('nan')}, {'alpha': True}):
            with self.subTest(params=params):
                self.setUp()
                before = set(self.bpy.data.materials)
                with self.assertRaises(HarnessError):
                    MaterialCommands(self.bpy).create_pbr({'name': 'InvalidMaterial', **params})
                self.assertEqual(set(self.bpy.data.materials), before)

    def test_create_camera_and_make_active(self):
        result = CameraCommands(self.bpy).create({"name": "HeroCamera", "location": [4, -4, 3], "rotation": [1, 0, 0], "lens": 55, "active": True})
        self.assertEqual(result["changedObjects"], ["HeroCamera"])
        self.assertEqual(self.bpy.context.scene.camera.name, "HeroCamera")

    def test_create_area_light(self):
        result = LightCommands(self.bpy).create({"name": "Key", "type": "AREA", "location": [2, -2, 4], "energy": 900, "color": [1, 0.8, 0.6], "size": 3})
        self.assertEqual(result["changedObjects"], ["Key"])
        self.assertEqual(self.bpy.data.objects["Key"].data.energy, 900.0)

    def test_set_frame_range_and_keyframe(self):
        commands = AnimationCommands(self.bpy)
        commands.set_frame_range({"start": 1, "end": 48})
        commands.insert_keyframe({"object": "Body", "dataPath": "location", "frame": 24})
        self.assertEqual((self.bpy.context.scene.frame_start, self.bpy.context.scene.frame_end), (1, 48))
        self.assertEqual(self.bpy.data.objects["Body"].keyframes, [("location", 24)])

    def test_invalid_frame_range_fails(self):
        with self.assertRaises(HarnessError):
            AnimationCommands(self.bpy).set_frame_range({"start": 50, "end": 10})

    def test_attach_approved_image_texture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_path = root / "texture.png"
            image_path.write_bytes(b"png")
            principled = Node()
            texture = SimpleNamespace(image=None, outputs={"Color": Socket()})
            linked = []
            material = self.bpy.data.materials.new("Blue")
            material.node_tree = SimpleNamespace(
                nodes=SimpleNamespace(get=lambda _name: principled, new=lambda _kind: texture),
                links=SimpleNamespace(new=lambda source, target: linked.append((source, target))),
            )
            self.bpy.data.images = SimpleNamespace(load=lambda path, check_existing: SimpleNamespace(filepath=path))
            result = MaterialCommands(self.bpy, asset_policy=PathPolicy([root])).attach_image_texture({"material": "Blue", "path": str(image_path)})
            self.assertEqual(result["result"]["path"], str(image_path.resolve()))
            self.assertEqual(len(linked), 1)

    def test_create_pbr_finds_principled_by_stable_node_type(self):
        principled = Node()
        principled.type = "BSDF_PRINCIPLED"
        nodes = [principled]
        nodes_get = lambda _name: None
        nodes_collection = SimpleNamespace(get=nodes_get)
        nodes_collection.__iter__ = lambda _self: iter(nodes)

        class IterableNodes:
            def get(self, _name):
                return None
            def __iter__(self):
                return iter(nodes)

        class LocalizedMaterials(dict):
            def new(self, name):
                material = SimpleNamespace(name=name, use_nodes=False, node_tree=SimpleNamespace(nodes=IterableNodes()))
                self[name] = material
                return material

        self.bpy.data.materials = LocalizedMaterials()
        result = MaterialCommands(self.bpy).create_pbr({"name": "Localized"})
        self.assertEqual(result["result"]["name"], "Localized")


if __name__ == "__main__":
    unittest.main()
