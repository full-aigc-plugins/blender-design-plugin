"""Composition root shared by managed and Connector modes."""

from __future__ import annotations

from .commands.animation import AnimationCommands
from .commands.camera import CameraCommands
from .commands.light import LightCommands
from .commands.material import MaterialCommands
from .commands.object import ObjectCommands
from .commands.scene import SceneCommands
from .commands.validation import closed_arguments
from pathlib import Path

from .advanced_python import AdvancedPythonExecutor
from .exporter import Exporter
from .preview import PreviewEngine
from .path_policy import PathPolicy
from .registry import CommandRegistry
from .session import HarnessSession


def build_registry(bpy_module, *, approved_output_root: Path | None = None, approved_asset_roots=(), revision_provider=lambda: 0) -> CommandRegistry:
    scene = SceneCommands(bpy_module)
    objects = ObjectCommands(bpy_module)
    materials = MaterialCommands(bpy_module, asset_policy=PathPolicy(approved_asset_roots) if approved_asset_roots else None)
    cameras = CameraCommands(bpy_module)
    lights = LightCommands(bpy_module)
    animation = AnimationCommands(bpy_module)
    advanced = AdvancedPythonExecutor(bpy_module)
    exporter = Exporter(bpy_module, approved_output_root=approved_output_root) if approved_output_root else None
    preview = PreviewEngine(bpy_module)

    registry = CommandRegistry()
    registry.register("scene.inspect", scene.inspect, validate=closed_arguments(), risk="read")
    registry.register("object.create_mesh", objects.create_mesh, validate=closed_arguments(required=("primitive", "name"), optional=("location", "rotation", "scale")))
    registry.register("object.create_curve", objects.create_curve, validate=closed_arguments(required=("name",), optional=("bevelDepth",)))
    registry.register("object.create_text", objects.create_text, validate=closed_arguments(required=("name", "text"), optional=("size", "extrude")))
    registry.register("object.transform", objects.transform, validate=closed_arguments(required=("name",), optional=("location", "rotation", "scale")))
    registry.register("object.rename", objects.rename, validate=closed_arguments(required=("name", "newName")))
    registry.register("object.parent", objects.parent, validate=closed_arguments(required=("child", "parent")))
    registry.register("object.delete", objects.delete, validate=closed_arguments(required=("name",)), risk="gated")
    registry.register("modifier.add", objects.add_modifier, validate=closed_arguments(required=("name", "modifier"), optional=("settings",)))
    registry.register("material.create_pbr", materials.create_pbr, validate=closed_arguments(required=("name",), optional=("baseColor", "metallic", "roughness", "alpha")))
    registry.register("material.assign", materials.assign, validate=closed_arguments(required=("object", "material")))
    registry.register("material.attach_image_texture", materials.attach_image_texture, validate=closed_arguments(required=("material", "path")))
    registry.register("camera.create", cameras.create, validate=closed_arguments(required=("name",), optional=("location", "rotation", "lens", "active")))
    registry.register("light.create", lights.create, validate=closed_arguments(required=("name",), optional=("type", "location", "energy", "color", "size")))
    registry.register("light.set_world_color", lights.set_world_color, validate=closed_arguments(required=("color",)))
    registry.register("animation.set_frame_range", animation.set_frame_range, validate=closed_arguments(required=("start", "end")))
    registry.register("animation.insert_keyframe", animation.insert_keyframe, validate=closed_arguments(required=("object", "dataPath", "frame")))
    registry.register("advanced.execute_python", advanced.execute, validate=closed_arguments(required=("script",)), risk="gated")
    def capture_preview(arguments):
        if approved_output_root is None:
            from .errors import HarnessError
            raise HarnessError("OUTPUT_NOT_AUTHORIZED", "preview output root is unavailable")
        snapshot_id = str(arguments.get("snapshotId", "uncommitted"))
        output_dir = Path(approved_output_root) / "milestones" / snapshot_id
        receipt = preview.capture_milestone(
            output_dir,
            milestone=str(arguments.get("milestone", "final_preview")),
            scene_revision=revision_provider(),
            snapshot_id=snapshot_id,
            width=int(arguments.get("width", 512)),
            height=int(arguments.get("height", 512)),
        )
        return {"changedObjects": [], "result": {"milestone": receipt}}

    registry.register(
        "preview.capture",
        capture_preview,
        validate=closed_arguments(required=("snapshotId",), optional=("milestone", "width", "height")),
        risk="read",
    )
    if exporter is not None:
        def export_file(arguments):
            receipt = exporter.export(
                Path(arguments["path"]),
                session_id=str(arguments.get("sessionId", "active")),
                scene_revision=revision_provider(),
                snapshot_id=str(arguments.get("snapshotId", "uncommitted")),
                overwrite=bool(arguments.get("overwrite", False)),
                parameters=dict(arguments.get("parameters", {})),
            )
            return {"changedObjects": [], "result": {"artifact": receipt}}

        registry.register(
            "export.file",
            export_file,
            validate=closed_arguments(required=("path", "snapshotId"), optional=("sessionId", "overwrite", "parameters")),
            risk="gated",
        )
    registry.register(
        "session.status",
        lambda _arguments: {"changedObjects": [], "result": {"sceneRevision": revision_provider()}},
        risk="read",
    )
    registry.register(
        "session.capabilities",
        lambda _arguments: {"changedObjects": [], "result": {"commands": registry.capabilities()}},
        risk="read",
    )
    return registry


def create_session(bpy_module, session_id: str, *, approved_output_root: Path | None = None, approved_asset_roots=(), transactions=None) -> HarnessSession:
    holder = {}
    registry = build_registry(
        bpy_module,
        approved_output_root=approved_output_root,
        approved_asset_roots=approved_asset_roots,
        revision_provider=lambda: holder["session"].scene_revision,
    )
    session = HarnessSession(session_id, dispatch=registry.dispatch, transactions=transactions)
    holder["session"] = session
    return session
