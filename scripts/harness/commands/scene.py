"""Read-only scene commands."""

from __future__ import annotations

from pathlib import Path

from ..artifact_validator import sha256_file
from ..errors import HarnessError

SUPPORTED_SCREENSHOT_FORMATS = {"png", "jpg"}
MIN_DIMENSION = 64
MAX_DIMENSION = 4096


class SceneCommands:
    def __init__(self, bpy_module, approved_output_root=None):
        self.bpy = bpy_module
        self.output_root = (
            Path(approved_output_root).resolve() if approved_output_root else None
        )

    def inspect(self, _arguments: dict) -> dict:
        objects = sorted(self.bpy.data.objects, key=lambda item: item.name)
        materials = list(getattr(self.bpy.data, "materials", ()))
        counts = {
            "objects": len(objects),
            "materials": len(materials),
            "lights": sum(obj.type == "LIGHT" for obj in objects),
            "cameras": sum(obj.type == "CAMERA" for obj in objects),
        }
        scene = self.bpy.context.scene
        collections = sorted(collection.name for collection in getattr(self.bpy.data, "collections", ()))
        material_names = sorted(material.name for material in materials)
        warnings = []
        missing_assets = []
        for image in getattr(self.bpy.data, "images", ()):
            filepath = getattr(image, "filepath", "")
            if not filepath or getattr(image, "source", "") != "FILE":
                continue
            try:
                resolved = Path(self.bpy.path.abspath(filepath)).resolve()
            except Exception:  # noqa: BLE001
                resolved = Path(filepath)
            if not resolved.is_file():
                missing_assets.append(str(resolved))
        if missing_assets:
            warnings.append("MISSING_ASSETS")
        return {
            "changedObjects": [],
            "result": {
                "objects": [obj.name for obj in objects],
                "objectDetails": [{"name": obj.name, "type": obj.type} for obj in objects],
                "collections": collections,
                "materials": material_names,
                "lights": [obj.name for obj in objects if obj.type == "LIGHT"],
                "cameras": [obj.name for obj in objects if obj.type == "CAMERA"],
                "summary": counts,
                "frameRange": {"start": int(scene.frame_start), "end": int(scene.frame_end)},
                "activeCamera": getattr(getattr(scene, "camera", None), "name", None),
                "currentFrame": int(getattr(scene, "frame_current", scene.frame_start)),
                "sceneName": getattr(scene, "name", "Scene"),
                "filepath": getattr(self.bpy.data, "filepath", ""),
                "missingAssets": missing_assets,
                "warnings": warnings,
            },
        }

    def screenshot(self, arguments: dict) -> dict:
        """Render a still PNG/JPG of the current scene state.

        The command does not mutate the .blend file; it only writes an
        external image under the approved output root. It is the missing
        "capture the live screenshot" step for closed-loop workflows
        (such as the dream-loop visual-quality loop) that need to compare
        the current scene against a target image.
        """
        if self.output_root is None:
            raise HarnessError(
                "OUTPUT_NOT_AUTHORIZED",
                "scene.screenshot requires an approved output root",
            )

        path = arguments.get("path")
        if not isinstance(path, str) or not path:
            raise HarnessError("INVALID_ARGUMENT", "path is required")

        target = Path(path)
        if target.is_symlink():
            raise HarnessError(
                "OUTPUT_NOT_AUTHORIZED", f"output must not be a symlink: {target}"
            )
        try:
            resolved = target.resolve()
        except OSError as exc:
            raise HarnessError("INVALID_ARGUMENT", f"path is not resolvable: {exc}") from exc
        try:
            resolved.relative_to(self.output_root)
        except ValueError:
            raise HarnessError(
                "OUTPUT_NOT_AUTHORIZED",
                f"output is outside approved root: {resolved}",
            )

        suffix = resolved.suffix.lower().lstrip(".")
        if suffix not in SUPPORTED_SCREENSHOT_FORMATS:
            raise HarnessError(
                "INVALID_ARGUMENT",
                f"screenshot format must be one of {sorted(SUPPORTED_SCREENSHOT_FORMATS)}; got path suffix: {suffix}",
            )
        requested_format = str(arguments.get("format", suffix)).lower()
        if requested_format != suffix:
            raise HarnessError(
                "INVALID_ARGUMENT",
                f"format argument '{requested_format}' does not match path suffix '{suffix}'",
            )

        if resolved.exists() and not bool(arguments.get("overwrite", False)):
            raise HarnessError(
                "OVERWRITE_AUTHORIZATION_REQUIRED",
                f"output already exists: {resolved}",
            )

        width = arguments.get("width", 1024)
        height = arguments.get("height", 1024)
        if not isinstance(width, int) or not isinstance(height, int):
            raise HarnessError(
                "INVALID_ARGUMENT", "width and height must be integers"
            )
        if not (MIN_DIMENSION <= width <= MAX_DIMENSION) or not (
            MIN_DIMENSION <= height <= MAX_DIMENSION
        ):
            raise HarnessError(
                "INVALID_ARGUMENT",
                f"width/height must be in [{MIN_DIMENSION}, {MAX_DIMENSION}]",
            )

        scene = self.bpy.context.scene

        camera_name = arguments.get("camera")
        if camera_name is not None:
            if not isinstance(camera_name, str) or not camera_name:
                raise HarnessError(
                    "INVALID_ARGUMENT", "camera must be a non-empty object name"
                )
            candidate = None
            scene_objects = getattr(scene, "objects", None)
            if scene_objects is not None and getattr(scene_objects, "get", None):
                candidate = scene_objects.get(camera_name)
            if candidate is None:
                data_objects = getattr(self.bpy.data, "objects", None)
                candidate = data_objects.get(camera_name) if data_objects is not None else None
            if candidate is None or getattr(candidate, "type", None) != "CAMERA":
                raise HarnessError(
                    "OBJECT_NOT_FOUND",
                    f"camera object not found or not a CAMERA: {camera_name}",
                )
            scene.camera = candidate

        if getattr(scene, "camera", None) is None:
            raise HarnessError(
                "CAMERA_REQUIRED", "create or select an active camera first"
            )

        frame = arguments.get("frame")
        if frame is not None:
            if not isinstance(frame, int):
                raise HarnessError(
                    "INVALID_ARGUMENT", "frame must be an integer"
                )
            if not (scene.frame_start <= frame <= scene.frame_end):
                raise HarnessError(
                    "INVALID_ARGUMENT",
                    "frame must be inside the scene frame range",
                )
            scene.frame_set(frame)

        render = getattr(scene, "render", None)
        if render is None:
            raise HarnessError(
                "MEDIA_INVALID", "scene.render is unavailable"
            )
        image_settings = getattr(render, "image_settings", None)
        if image_settings is None:
            raise HarnessError(
                "MEDIA_INVALID", "scene.render.image_settings is unavailable"
            )

        resolved.parent.mkdir(parents=True, exist_ok=True)

        original = {
            "filepath": render.filepath,
            "resolution_x": render.resolution_x,
            "resolution_y": render.resolution_y,
            "resolution_percentage": render.resolution_percentage,
            "file_format": image_settings.file_format,
        }
        try:
            render.resolution_x = int(width)
            render.resolution_y = int(height)
            render.resolution_percentage = 100
            image_settings.file_format = "PNG" if suffix == "png" else "JPEG"
            render.filepath = str(resolved)
            self.bpy.ops.render.render(write_still=True)
        finally:
            for key, value in original.items():
                target_attr = image_settings if key == "file_format" else render
                try:
                    setattr(target_attr, key, value)
                except Exception:  # noqa: S110, BLE001
                    pass

        if not resolved.is_file() or resolved.stat().st_size <= 0:
            raise HarnessError(
                "MEDIA_INVALID",
                f"screenshot was not produced or is empty: {resolved}",
            )

        return {
            "changedObjects": [],
            "result": {
                "artifact": {
                    "protocolVersion": "codex-blender/v1",
                    "path": str(resolved),
                    "sha256": sha256_file(resolved),
                    "bytes": resolved.stat().st_size,
                    "format": suffix,
                    "validation": {
                        "status": "passed",
                        "checks": ["exists", "non_empty", "sha256"],
                    },
                },
                "render": {
                    "engine": getattr(render, "engine", None),
                    "width": int(width),
                    "height": int(height),
                    "frame": int(getattr(scene, "frame_current", scene.frame_start)),
                    "camera": getattr(scene.camera, "name", None),
                },
            },
        }
