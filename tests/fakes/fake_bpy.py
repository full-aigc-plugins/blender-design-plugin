"""Fake bpy module for hermetic testing of blender_bridge.

Provides a minimal Blender API surface so that inspect_scene() and
export_preview() can be driven without a real Blender installation.
Every class carries a ``snapshot()`` method that returns a JSON-serializable
dict of all observable state, enabling read-only assertions.

No real Blender is required; standard library only.
"""

import os


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


class FakeImageSettings:
    """Mimics render.image_settings."""
    def __init__(self, file_format="PNG"):
        self.file_format = file_format

    def snapshot(self):
        return {"file_format": self.file_format}


class FakeRenderSettings:
    """Mimics scene.render settings."""
    def __init__(self, resolution_x=1920, resolution_y=1080,
                 resolution_percentage=100, engine="BLENDER_EEVEE",
                 filepath="", file_format="PNG"):
        self.resolution_x = resolution_x
        self.resolution_y = resolution_y
        self.resolution_percentage = resolution_percentage
        self.engine = engine
        self.filepath = filepath
        self.image_settings = FakeImageSettings(file_format)

    def snapshot(self):
        return {
            "resolution_x": self.resolution_x,
            "resolution_y": self.resolution_y,
            "resolution_percentage": self.resolution_percentage,
            "engine": self.engine,
            "filepath": self.filepath,
            "file_format": self.image_settings.file_format,
        }


class FakeShading:
    """Mimics scene.display.shading."""
    def __init__(self, color_type="SINGLE", single_color=(0.8, 0.8, 0.8),
                 light="STUDIO", show_xray=False):
        self.color_type = color_type
        self.single_color = single_color
        self.light = light
        self.show_xray = show_xray

    def snapshot(self):
        return {
            "color_type": self.color_type,
            "single_color": list(self.single_color),
            "light": self.light,
            "show_xray": self.show_xray,
        }


class FakeDisplay:
    """Mimics scene.display."""
    def __init__(self, shading=None):
        self.shading = shading or FakeShading()

    def snapshot(self):
        return {"shading": self.shading.snapshot()}


class FakeOpsRender:
    """Mimics bpy.ops.render.opengl — writes frame PNGs to the output dir."""
    def __init__(self):
        self.last_call = None  # records kwargs for test assertions

    def __call__(self, **kwargs):
        self.last_call = kwargs
        # In the fake, we do nothing — the test adapter or mock handles file creation.


class FakeOps:
    """Mimics bpy.ops."""
    def __init__(self):
        self.render = type("Render", (), {"opengl": FakeOpsRender()})()


class FakeScene:
    """Mimics a Blender scene with jimeng_* properties for the export adapter."""
    def __init__(self, frame_start=1, frame_end=250, render=None,
                 camera=None, frame_current=None, display=None):
        self.frame_start = frame_start
        self.frame_end = frame_end
        self.render = render or FakeRenderSettings()
        self.camera = camera
        self.frame_current = frame_current if frame_current is not None else frame_start
        self.display = display or FakeDisplay()

        # jimeng_* properties — set by the adapter, read by the vendored core
        self.jimeng_camera = None
        self.jimeng_resolution = "origin"
        self.jimeng_frame_start = frame_start
        self.jimeng_frame_end = frame_end
        self.jimeng_output_dir = ""

    def frame_set(self, frame):
        """Mimics scene.frame_set — sets the current frame."""
        self.frame_current = frame

    def snapshot(self):
        return {
            "frame_start": self.frame_start,
            "frame_end": self.frame_end,
            "frame_current": self.frame_current,
            "camera_name": self.camera.name if self.camera else None,
            "render": self.render.snapshot(),
            "display": self.display.snapshot(),
            "jimeng_camera_name": self.jimeng_camera.name if self.jimeng_camera else None,
            "jimeng_resolution": self.jimeng_resolution,
            "jimeng_frame_start": self.jimeng_frame_start,
            "jimeng_frame_end": self.jimeng_frame_end,
            "jimeng_output_dir": self.jimeng_output_dir,
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


class FakePathModule:
    """Mimics bpy.path — provides abspath() for the vendored core."""
    @staticmethod
    def abspath(path):
        """Resolve a Blender-relative path to absolute (here: just expand ~ and make absolute)."""
        if not path:
            return ""
        expanded = os.path.expanduser(str(path))
        if os.path.isabs(expanded):
            return expanded
        return os.path.abspath(expanded)


class FakeBpy:
    """Complete fake bpy module for testing.

    Accepts an optional ops= argument for injecting a FakeOps so the
    export tests can observe render.opengl calls without touching disk
    through the fake itself.
    """
    def __init__(self, data=None, context=None, app=None, ops=None):
        self.data = data or FakeData()
        self.context = context or FakeContext()
        self.app = app or FakeApp()
        self.ops = ops or FakeOps()
        self.path = FakePathModule()

    def snapshot(self):
        return {
            "data": self.data.snapshot(),
            "context": self.context.snapshot(),
            "app": self.app.snapshot(),
        }
