"""Fake bpy module for hermetic testing of blender_bridge.

Provides a minimal Blender API surface so that inspect_scene() can be
driven without a real Blender installation.  Every class carries a
``snapshot()`` method that returns a JSON-serializable dict of all
observable state, enabling read-only assertions.

No real Blender is required; standard library only.
"""


# ---------------------------------------------------------------------------
# Blender data-model stubs
# ---------------------------------------------------------------------------

class FakeLibrary:
    """Represents an external .blend library link."""
    def __init__(self, filepath):
        self.filepath = filepath

    def snapshot(self):
        return {"filepath": self.filepath}


class FakeNodeInput:
    """Mimics a node input socket."""
    def __init__(self, default_value=None):
        self.default_value = default_value

    def snapshot(self):
        return {"default_value": self.default_value}


class FakeNode:
    """Mimics a shader node."""
    SHADER = "SHADER"
    TEX_IMAGE = "TEX_IMAGE"
    GROUP = "GROUP"

    def __init__(self, name, node_type, inputs=None):
        self.name = name
        self.type = node_type
        self.inputs = list(inputs or [])

    def snapshot(self):
        return {
            "name": self.name,
            "type": self.type,
            "inputs": [i.snapshot() for i in self.inputs],
        }


class FakeNodeTree:
    """Mimics a material node tree (shader graph)."""
    def __init__(self, nodes=None):
        self.nodes = list(nodes or [])

    def snapshot(self):
        return {"nodes": [n.snapshot() for n in self.nodes]}


class FakeMaterial:
    """Mimics a Blender material datablock."""
    def __init__(self, name, use_nodes=False, node_tree=None):
        self.name = name
        self.use_nodes = use_nodes
        self.node_tree = node_tree

    def snapshot(self):
        return {
            "name": self.name,
            "use_nodes": self.use_nodes,
            "node_tree": self.node_tree.snapshot() if self.node_tree else None,
        }


class FakeCamera:
    """Mimics camera data block."""
    def __init__(self, name):
        self.name = name

    def snapshot(self):
        return {"name": self.name}


class FakeMaterialSlot:
    """Mimics an object's material slot."""
    def __init__(self, material):
        self.material = material

    def snapshot(self):
        return {"material_name": self.material.name if self.material else None}


class FakeObject:
    """Mimics a Blender object."""
    MESH = "MESH"
    CAMERA = "CAMERA"

    def __init__(self, name, obj_type="MESH", data=None, materials=None,
                 library=None):
        self.name = name
        self.type = obj_type
        self.data = data
        self.material_slots = [FakeMaterialSlot(m) for m in (materials or [])]
        self.library = library

    def snapshot(self):
        return {
            "name": self.name,
            "type": self.type,
            "materials": [s.snapshot() for s in self.material_slots],
            "library": self.library.snapshot() if self.library else None,
        }


class FakeRenderSettings:
    """Mimics scene.render settings."""
    def __init__(self, resolution_x=1920, resolution_y=1080,
                 resolution_percentage=100, engine="BLENDER_EEVEE"):
        self.resolution_x = resolution_x
        self.resolution_y = resolution_y
        self.resolution_percentage = resolution_percentage
        self.engine = engine

    def snapshot(self):
        return {
            "resolution_x": self.resolution_x,
            "resolution_y": self.resolution_y,
            "resolution_percentage": self.resolution_percentage,
            "engine": self.engine,
        }


class FakeScene:
    """Mimics a Blender scene."""
    def __init__(self, frame_start=1, frame_end=250, render=None):
        self.frame_start = frame_start
        self.frame_end = frame_end
        self.render = render or FakeRenderSettings()

    def snapshot(self):
        return {
            "frame_start": self.frame_start,
            "frame_end": self.frame_end,
            "render": self.render.snapshot(),
        }


class FakeCollection:
    """Mimics bpy.types.bpy_prop_collection with iteration and lookup."""
    def __init__(self, items=None):
        self._items = list(items or [])

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._items[key]
        for item in self._items:
            if getattr(item, "name", None) == key:
                return item
        raise KeyError(key)

    def snapshot(self):
        return [
            item.snapshot() if hasattr(item, "snapshot") else str(item)
            for item in self._items
        ]


class FakeData:
    """Mimics bpy.data."""
    def __init__(self, objects=None, materials=None, scenes=None):
        self.objects = FakeCollection(objects or [])
        self.materials = FakeCollection(materials or [])
        self.scenes = FakeCollection(scenes or [])

    def snapshot(self):
        return {
            "objects": self.objects.snapshot(),
            "materials": self.materials.snapshot(),
            "scenes": self.scenes.snapshot(),
        }


class FakePreferencesFilepaths:
    """Mimics bpy.context.preferences.filepaths."""
    def __init__(self):
        self.use_scripts_auto_execute = False

    def snapshot(self):
        return {"use_scripts_auto_execute": self.use_scripts_auto_execute}


class FakePreferences:
    """Mimics bpy.context.preferences."""
    def __init__(self):
        self.filepaths = FakePreferencesFilepaths()

    def snapshot(self):
        return {"filepaths": self.filepaths.snapshot()}


class FakeContext:
    """Mimics bpy.context."""
    def __init__(self, scene=None, preferences=None):
        self.scene = scene
        self.preferences = preferences or FakePreferences()

    def snapshot(self):
        return {
            "scene": self.scene.snapshot() if self.scene else None,
            "preferences": self.preferences.snapshot(),
        }


class FakeApp:
    """Mimics bpy.app."""
    def __init__(self, version_string="4.2.0"):
        self.version_string = version_string

    def snapshot(self):
        return {"version_string": self.version_string}


class FakeBpy:
    """Complete fake bpy module for testing."""
    def __init__(self, data=None, context=None, app=None):
        self.data = data or FakeData()
        self.context = context or FakeContext()
        self.app = app or FakeApp()

    def snapshot(self):
        return {
            "data": self.data.snapshot(),
            "context": self.context.snapshot(),
            "app": self.app.snapshot(),
        }
