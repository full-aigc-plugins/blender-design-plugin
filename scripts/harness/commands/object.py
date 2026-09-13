"""Object creation, transform, hierarchy, deletion, and modifier commands."""

from __future__ import annotations

from .validation import require_name, vector3
from ..errors import HarnessError


PRIMITIVE_OPERATORS = {
    "cube": "primitive_cube_add",
    "sphere": "primitive_uv_sphere_add",
    "cylinder": "primitive_cylinder_add",
    "cone": "primitive_cone_add",
    "plane": "primitive_plane_add",
    "torus": "primitive_torus_add",
}


class ObjectCommands:
    def __init__(self, bpy_module):
        self.bpy = bpy_module

    def _object(self, name: str):
        obj = self.bpy.data.objects.get(name)
        if obj is None:
            raise HarnessError("OBJECT_NOT_FOUND", f"object not found: {name}")
        return obj

    def create_mesh(self, arguments: dict) -> dict:
        name = require_name(arguments.get("name"))
        primitive = str(arguments.get("primitive", "")).lower()
        operator_name = PRIMITIVE_OPERATORS.get(primitive)
        if operator_name is None:
            raise HarnessError("INVALID_ARGUMENT", f"unsupported primitive: {primitive}")
        if self.bpy.data.objects.get(name) is not None:
            raise HarnessError("NAME_COLLISION", f"object already exists: {name}")
        getattr(self.bpy.ops.mesh, operator_name)()
        obj = self.bpy.context.object
        old_name = obj.name
        obj.name = name
        if isinstance(self.bpy.data.objects, dict) and old_name in self.bpy.data.objects:
            self.bpy.data.objects.pop(old_name)
            self.bpy.data.objects[name] = obj
        for field, attr, fallback in (
            ("location", "location", [0, 0, 0]),
            ("rotation", "rotation_euler", [0, 0, 0]),
            ("scale", "scale", [1, 1, 1]),
        ):
            if field in arguments:
                setattr(obj, attr, vector3(arguments[field], field))
        return {"changedObjects": [name], "result": {"name": name, "type": "MESH"}}

    def create_curve(self, arguments: dict) -> dict:
        name = require_name(arguments.get("name"))
        if self.bpy.data.objects.get(name) is not None:
            raise HarnessError("NAME_COLLISION", f"object already exists: {name}")
        self.bpy.ops.curve.primitive_bezier_curve_add()
        curve = self._rename_active(name)
        if "bevelDepth" in arguments:
            curve.data.bevel_depth = float(arguments["bevelDepth"])
        return {"changedObjects": [name], "result": {"name": name, "type": "CURVE"}}

    def create_text(self, arguments: dict) -> dict:
        name = require_name(arguments.get("name"))
        text = str(arguments.get("text", ""))
        if self.bpy.data.objects.get(name) is not None:
            raise HarnessError("NAME_COLLISION", f"object already exists: {name}")
        self.bpy.ops.object.text_add()
        obj = self._rename_active(name)
        obj.data.body = text
        if "size" in arguments:
            obj.data.size = float(arguments["size"])
        if "extrude" in arguments:
            obj.data.extrude = float(arguments["extrude"])
        return {"changedObjects": [name], "result": {"name": name, "type": "FONT"}}

    def _rename_active(self, name: str):
        obj = self.bpy.context.object
        old_name = obj.name
        obj.name = name
        if isinstance(self.bpy.data.objects, dict):
            self.bpy.data.objects.pop(old_name)
            self.bpy.data.objects[name] = obj
        return obj

    def transform(self, arguments: dict) -> dict:
        name = require_name(arguments.get("name"))
        obj = self._object(name)
        changed = False
        for field, attr in (("location", "location"), ("rotation", "rotation_euler"), ("scale", "scale")):
            if field in arguments:
                setattr(obj, attr, vector3(arguments[field], field))
                changed = True
        if not changed:
            raise HarnessError("INVALID_ARGUMENT", "transform requires location, rotation, or scale")
        return {"changedObjects": [name]}

    def rename(self, arguments: dict) -> dict:
        name = require_name(arguments.get("name"))
        new_name = require_name(arguments.get("newName"))
        obj = self._object(name)
        if self.bpy.data.objects.get(new_name) is not None:
            raise HarnessError("NAME_COLLISION", f"object already exists: {new_name}")
        obj.name = new_name
        if isinstance(self.bpy.data.objects, dict):
            self.bpy.data.objects.pop(name)
            self.bpy.data.objects[new_name] = obj
        return {"changedObjects": [new_name]}

    def delete(self, arguments: dict) -> dict:
        name = require_name(arguments.get("name"))
        obj = self._object(name)
        self.bpy.data.objects.remove(obj, do_unlink=True)
        return {"changedObjects": [name]}

    def parent(self, arguments: dict) -> dict:
        child_name = require_name(arguments.get("child"))
        parent_name = require_name(arguments.get("parent"))
        self._object(child_name).parent = self._object(parent_name)
        return {"changedObjects": [child_name]}

    def add_modifier(self, arguments: dict) -> dict:
        name = require_name(arguments.get("name"))
        modifier_type = str(arguments.get("modifier", "")).upper()
        if not modifier_type:
            raise HarnessError("INVALID_ARGUMENT", "modifier is required")
        obj = self._object(name)
        modifier = obj.modifiers.new(name=f"Codex {modifier_type.title()}", type=modifier_type)
        for key, value in dict(arguments.get("settings", {})).items():
            if key.startswith("_") or not hasattr(modifier, key):
                raise HarnessError("INVALID_ARGUMENT", f"unsupported modifier setting: {key}")
            setattr(modifier, key, value)
        return {"changedObjects": [name], "result": {"modifier": modifier.name}}
