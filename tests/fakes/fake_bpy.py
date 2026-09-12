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
    """Mimics bpy.ops, including the add-on's jimeng.* operator namespace."""
    def __init__(self, bpy=None):
        self.render = type("Render", (), {"opengl": FakeOpsRender()})()
        self.jimeng = FakeJimengOps(bpy) if bpy is not None else None


class FakeScene:
    """Mimics a Blender scene, including the add-on's full jimeng_* property surface.

    The property names and defaults mirror what the vendored add-on's
    ``register()`` installs on ``bpy.types.Scene``, because the add-on's
    operators read and write them directly.
    """
    def __init__(self, frame_start=1, frame_end=250, render=None,
                 camera=None, frame_current=None, display=None):
        self.frame_start = frame_start
        self.frame_end = frame_end
        self.render = render or FakeRenderSettings()
        self.camera = camera
        self.frame_current = frame_current if frame_current is not None else frame_start
        self.display = display or FakeDisplay()

        # --- add-on inputs ---
        self.jimeng_uploader_mode = "VIEWPORT"
        self.jimeng_video_path = ""
        self.jimeng_output_dir = ""
        self.jimeng_camera = None
        self.jimeng_resolution = "origin"
        self.jimeng_frame_start = frame_start
        self.jimeng_frame_end = frame_end
        self.jimeng_frame_range_initialized = False
        self.jimeng_frame_range_manual = False
        self.jimeng_default_params_expanded = False
        self.jimeng_prompt = ""

        # --- add-on outputs / status ---
        self.jimeng_redirect_url = ""
        self.jimeng_redirect_url_display = ""
        self.jimeng_link_ready = False
        self.jimeng_link_signature = ""
        self.jimeng_camera_cache_json = ""
        self.jimeng_active_camera_key = ""
        self.jimeng_status = ""
        self.jimeng_status_detail = ""
        self.jimeng_task_state = "IDLE"
        self.jimeng_task_message = ""
        self.jimeng_error_message = ""

        # --- DCC protocol properties ---
        self.jimeng_dcc_fps = 24
        self.jimeng_dcc_container_format = "mp4"
        self.jimeng_dcc_codec = "h264"
        self.jimeng_dcc_file_size_label = ""
        self.jimeng_dcc_min_frame_num = 44
        self.jimeng_dcc_max_frame_num = 720
        self.jimeng_frame_limit_display = ""

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
    """Mimics bpy.app, including the handlers and timers the add-on registers."""
    def __init__(self, version_string="4.2.0"):
        self.version_string = version_string
        self.handlers = FakeHandlers()
        self.timers = FakeTimers()

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

    Emulates enough of Blender for the vendored add-on's ``register()`` to run
    and for its operators to be dispatched through ``bpy.ops.jimeng.*``.
    """
    def __init__(self, data=None, context=None, app=None, ops=None):
        self.data = data or FakeData()
        self.context = context or FakeContext()
        self.app = app or FakeApp()
        self.path = FakePathModule()
        self.props = FakeProps()
        self.types = FakeTypes()
        self.utils = FakeUtils()
        self.ops = ops or FakeOps(bpy=self)

    def snapshot(self):
        return {
            "data": self.data.snapshot(),
            "context": self.context.snapshot(),
            "app": self.app.snapshot(),
        }


# ---------------------------------------------------------------------------
# Blender registration surface (props / types / utils / ops dispatch)
# ---------------------------------------------------------------------------

class _PropStub:
    """Stands in for bpy.props.XProperty(...) — records kwargs, holds no state."""
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeProps:
    """Mimics bpy.props property constructors."""
    EnumProperty = StringProperty = PointerProperty = IntProperty = BoolProperty = _PropStub


class FakeOperatorBase:
    """Mimics bpy.types.Operator — provides the report() the add-on calls."""
    def __init__(self):
        self.reported = []

    def report(self, level, message):
        self.reported.append((level, message))


class FakePanelBase:
    """Mimics bpy.types.Panel (registration only; never drawn)."""


class FakeTypes:
    """Mimics bpy.types — the classes add-ons subclass or reference in props.

    Unknown attributes are auto-created as empty classes so a property
    constructor's ``type=`` argument (e.g. ``bpy.types.Object``) resolves
    without having to enumerate Blender's whole type registry here.
    """
    def __init__(self):
        self.Scene = type("FakeSceneType", (), {})
        self.Operator = FakeOperatorBase
        self.Panel = FakePanelBase
        self.Object = type("FakeObjectType", (), {})

    def __getattr__(self, name):
        # Only reached when the attribute is genuinely missing.
        created = type(f"Fake{name}Type", (), {})
        setattr(self, name, created)
        return created


class FakeUtils:
    """Mimics bpy.utils class registration, keyed by bl_idname."""
    def __init__(self):
        self.classes = {}
        self.registered = []

    def register_class(self, cls):
        idname = getattr(cls, "bl_idname", None) or getattr(cls, "__name__", str(cls))
        if idname in self.classes:
            raise ValueError(f"{idname} is already registered")
        self.classes[idname] = cls
        self.registered.append(cls)

    def unregister_class(self, cls):
        idname = getattr(cls, "bl_idname", None) or getattr(cls, "__name__", str(cls))
        self.classes.pop(idname, None)
        if cls in self.registered:
            self.registered.remove(cls)


class FakeJimengOps:
    """Dispatches bpy.ops.jimeng.* to the classes register_class recorded.

    This runs the REAL vendored operator code, not a stand-in.
    """
    def __init__(self, bpy):
        self._bpy = bpy

    def _invoke(self, idname):
        cls = self._bpy.utils.classes.get(idname)
        if cls is None:
            raise RuntimeError(f"{idname} is not registered")
        operator = cls()
        context = FakeOperatorContext(self._bpy)
        result = operator.execute(context)
        self._bpy.last_operator = (idname, operator)
        return result

    def render_upload(self):
        return self._invoke("jimeng.render_upload")

    def upload_existing(self):
        return self._invoke("jimeng.upload_existing")


class FakeOperatorContext:
    """Mimics the operator context passed to execute()."""
    def __init__(self, bpy):
        self.scene = bpy.context.scene
        self.preferences = bpy.context.preferences


class FakeHandlers:
    """Mimics bpy.app.handlers."""
    def __init__(self):
        self.load_post = []


class FakeTimers:
    """Mimics bpy.app.timers — registration is a no-op that reports unregistered."""
    def __init__(self):
        self.registered = []

    def is_registered(self, callback):
        return callback in self.registered

    def register(self, callback, **kwargs):
        self.registered.append(callback)

    def unregister(self, callback):
        if callback in self.registered:
            self.registered.remove(callback)
