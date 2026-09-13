"""Camera creation and activation."""

from __future__ import annotations

from .validation import require_name, vector3
from ..errors import HarnessError


class CameraCommands:
    def __init__(self, bpy_module):
        self.bpy = bpy_module

    def create(self, arguments: dict) -> dict:
        name = require_name(arguments.get("name"))
        if self.bpy.data.objects.get(name) is not None:
            raise HarnessError("NAME_COLLISION", f"object already exists: {name}")
        location = vector3(arguments.get("location", [0, 0, 0]), "location")
        rotation = vector3(arguments.get("rotation", [0, 0, 0]), "rotation")
        self.bpy.ops.object.camera_add(location=location, rotation=rotation)
        camera = self.bpy.context.object
        old_name = camera.name
        camera.name = name
        if isinstance(self.bpy.data.objects, dict):
            self.bpy.data.objects.pop(old_name)
            self.bpy.data.objects[name] = camera
        lens = float(arguments.get("lens", 50.0))
        if lens <= 0:
            raise HarnessError("INVALID_ARGUMENT", "lens must be positive")
        camera.data.lens = lens
        if arguments.get("active", False):
            self.bpy.context.scene.camera = camera
        return {"changedObjects": [name], "result": {"name": name}}

