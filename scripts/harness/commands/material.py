"""PBR material creation and assignment."""

from __future__ import annotations

from .validation import require_name
from ..errors import HarnessError


def _unit(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
        raise HarnessError("INVALID_ARGUMENT", f"{field} must be between 0 and 1")
    return float(value)


class MaterialCommands:
    def __init__(self, bpy_module, *, asset_policy=None):
        self.bpy = bpy_module
        self.asset_policy = asset_policy

    def create_pbr(self, arguments: dict) -> dict:
        name = require_name(arguments.get("name"))
        if self.bpy.data.materials.get(name) is not None:
            raise HarnessError("NAME_COLLISION", f"material already exists: {name}")
        color = arguments.get("baseColor", [0.8, 0.8, 0.8, 1.0])
        if not isinstance(color, (list, tuple)) or len(color) != 4:
            raise HarnessError("INVALID_ARGUMENT", "baseColor must contain four numbers")
        color = tuple(_unit(item, "baseColor") for item in color)
        material = self.bpy.data.materials.new(name=name)
        material.use_nodes = True
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled is None:
            raise HarnessError("MATERIAL_NODE_MISSING", "Principled BSDF node is unavailable")
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Metallic"].default_value = _unit(arguments.get("metallic", 0.0), "metallic")
        principled.inputs["Roughness"].default_value = _unit(arguments.get("roughness", 0.5), "roughness")
        principled.inputs["Alpha"].default_value = _unit(arguments.get("alpha", 1.0), "alpha")
        return {"changedObjects": [], "result": {"name": name}}

    def assign(self, arguments: dict) -> dict:
        object_name = require_name(arguments.get("object"))
        material_name = require_name(arguments.get("material"))
        obj = self.bpy.data.objects.get(object_name)
        material = self.bpy.data.materials.get(material_name)
        if obj is None:
            raise HarnessError("OBJECT_NOT_FOUND", f"object not found: {object_name}")
        if material is None:
            raise HarnessError("MATERIAL_NOT_FOUND", f"material not found: {material_name}")
        slots = obj.data.materials
        if len(slots):
            slots[0] = material
        else:
            slots.append(material)
        return {"changedObjects": [object_name]}

    def attach_image_texture(self, arguments: dict) -> dict:
        material_name = require_name(arguments.get("material"))
        if self.asset_policy is None:
            raise HarnessError("ASSET_NOT_AUTHORIZED", "no asset root was approved")
        path = self.asset_policy.require_file(arguments.get("path"))
        material = self.bpy.data.materials.get(material_name)
        if material is None:
            raise HarnessError("MATERIAL_NOT_FOUND", f"material not found: {material_name}")
        material.use_nodes = True
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled is None:
            raise HarnessError("MATERIAL_NODE_MISSING", "Principled BSDF node is unavailable")
        image = self.bpy.data.images.load(str(path), check_existing=True)
        texture = material.node_tree.nodes.new("ShaderNodeTexImage")
        texture.image = image
        material.node_tree.links.new(texture.outputs["Color"], principled.inputs["Base Color"])
        return {"changedObjects": [], "result": {"material": material_name, "path": str(path)}}
