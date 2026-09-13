"""Light and world commands."""

from __future__ import annotations

from .validation import require_name, vector3
from ..errors import HarnessError


LIGHT_TYPES = {"POINT", "SUN", "SPOT", "AREA"}


class LightCommands:
    def __init__(self, bpy_module):
        self.bpy = bpy_module

    def create(self, arguments: dict) -> dict:
        name = require_name(arguments.get("name"))
        light_type = str(arguments.get("type", "AREA")).upper()
        if light_type not in LIGHT_TYPES:
            raise HarnessError("INVALID_ARGUMENT", f"unsupported light type: {light_type}")
        if self.bpy.data.objects.get(name) is not None:
            raise HarnessError("NAME_COLLISION", f"object already exists: {name}")
        location = vector3(arguments.get("location", [0, 0, 0]), "location")
        self.bpy.ops.object.light_add(type=light_type, location=location)
        light = self.bpy.context.object
        old_name = light.name
        light.name = name
        if isinstance(self.bpy.data.objects, dict):
            self.bpy.data.objects.pop(old_name)
            self.bpy.data.objects[name] = light
        energy = float(arguments.get("energy", 1000.0))
        if energy < 0:
            raise HarnessError("INVALID_ARGUMENT", "energy must not be negative")
        color = arguments.get("color", [1, 1, 1])
        light.data.energy = energy
        light.data.color = tuple(vector3(color, "color"))
        if hasattr(light.data, "size") and "size" in arguments:
            light.data.size = float(arguments["size"])
        return {"changedObjects": [name], "result": {"name": name, "type": light_type}}

    def set_world_color(self, arguments: dict) -> dict:
        color = tuple(vector3(arguments.get("color"), "color"))
        self.bpy.context.scene.world.color = color
        return {"changedObjects": []}

