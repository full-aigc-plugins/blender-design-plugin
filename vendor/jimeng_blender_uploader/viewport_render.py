"""Viewport preview movie generation for Blender."""

from __future__ import annotations

import datetime
import os
import shutil

import bpy

from . import dcc_config, settings, upload_bridge


class ViewportRenderError(RuntimeError):
    pass


FALLBACK_ORIGINAL_WIDTH = 1280.0
FALLBACK_ORIGINAL_HEIGHT = 720.0
DEFAULT_MATERIAL_BASE_COLOR = (0.8, 0.8, 0.8, 1.0)
DEFAULT_MATERIAL_ROUGHNESS = 0.5
DEFAULT_MATERIAL_METALLIC = 0.0
TEXTURE_NODE_TYPES = {
    "TEX_BRICK",
    "TEX_CHECKER",
    "TEX_ENVIRONMENT",
    "TEX_GRADIENT",
    "TEX_IMAGE",
    "TEX_MAGIC",
    "TEX_MUSGRAVE",
    "TEX_NOISE",
    "TEX_VORONOI",
    "TEX_WAVE",
}
DEFAULT_NODE_TYPES = {"OUTPUT_MATERIAL", "BSDF_PRINCIPLED"}


def _positive_float(value, fallback):
    try:
        parsed = float(value)
    except Exception:
        return fallback
    return parsed if parsed > 0 else fallback


def _even_dimension(value):
    try:
        parsed = int(float(value))
    except Exception:
        parsed = 2
    if parsed % 2:
        parsed -= 1
    return max(2, parsed)


def _close_float(left, right, tolerance=0.025):
    try:
        return abs(float(left) - float(right)) <= tolerance
    except Exception:
        return False


def _close_color(left, right, tolerance=0.025):
    try:
        left_values = tuple(float(value) for value in left)
        right_values = tuple(float(value) for value in right)
    except Exception:
        return False
    count = min(len(left_values), len(right_values))
    return all(
        _close_float(left_values[index], right_values[index], tolerance)
        for index in range(count)
    )


def _input_default(node, name, fallback=None):
    socket = getattr(node, "inputs", {}).get(name) if node else None
    if socket is None:
        return fallback
    return getattr(socket, "default_value", fallback)


def _first_node_by_type(node_tree, node_type):
    for node in getattr(node_tree, "nodes", ()) or ():
        if getattr(node, "type", None) == node_type:
            return node
    return None


def material_preview_reason(material):
    """Return a reason when a material should be preserved in preview exports."""
    if material is None:
        return ""

    node_tree = getattr(material, "node_tree", None)
    if node_tree:
        for node in node_tree.nodes:
            node_type = getattr(node, "type", "")
            if node_type == "TEX_IMAGE" and getattr(node, "image", None):
                return "image texture node"
            if node_type in TEXTURE_NODE_TYPES and node_type != "TEX_IMAGE":
                return "procedural texture node"

        for node in node_tree.nodes:
            if getattr(node, "type", "") not in DEFAULT_NODE_TYPES:
                return "custom shader node"

        principled = _first_node_by_type(node_tree, "BSDF_PRINCIPLED")
        if principled:
            base_color = _input_default(principled, "Base Color", DEFAULT_MATERIAL_BASE_COLOR)
            metallic = _input_default(principled, "Metallic", DEFAULT_MATERIAL_METALLIC)
            roughness = _input_default(principled, "Roughness", DEFAULT_MATERIAL_ROUGHNESS)
            alpha = _input_default(principled, "Alpha", 1.0)
            emission_strength = _input_default(principled, "Emission Strength", 0.0)

            if not _close_color(base_color, DEFAULT_MATERIAL_BASE_COLOR):
                return "non-default base color"
            if not _close_float(metallic, DEFAULT_MATERIAL_METALLIC):
                return "non-default metallic"
            if not _close_float(roughness, DEFAULT_MATERIAL_ROUGHNESS):
                return "non-default roughness"
            if not _close_float(alpha, 1.0):
                return "non-default alpha"
            if not _close_float(emission_strength, 0.0):
                return "emission"

    if not _close_color(getattr(material, "diffuse_color", DEFAULT_MATERIAL_BASE_COLOR), DEFAULT_MATERIAL_BASE_COLOR):
        return "non-default diffuse color"

    return ""


def object_material_preview_reason(obj):
    if getattr(obj, "type", None) != "MESH" or getattr(obj, "hide_render", False):
        return ""
    try:
        if hasattr(obj, "visible_get") and not obj.visible_get():
            return ""
    except Exception:
        pass
    for slot in getattr(obj, "material_slots", ()) or ():
        reason = material_preview_reason(getattr(slot, "material", None))
        if reason:
            return reason
    return ""


def scene_has_material_preview(scene):
    return any(object_material_preview_reason(obj) for obj in getattr(scene, "objects", ()) or ())


def preview_mode_for_scene(scene):
    return "material" if scene_has_material_preview(scene) else "solid"


def original_resolution(scene):
    render = scene.render
    percentage = _positive_float(getattr(render, "resolution_percentage", 100), 100.0) / 100.0
    width = _positive_float(getattr(render, "resolution_x", 0), 0.0) * percentage
    height = _positive_float(getattr(render, "resolution_y", 0), 0.0) * percentage
    if width <= 0 or height <= 0:
        return FALLBACK_ORIGINAL_WIDTH, FALLBACK_ORIGINAL_HEIGHT
    return width, height


def _resolution_key(scene):
    return dcc_config.normalize_resolution_key(
        getattr(scene, "jimeng_resolution", "") or dcc_config.DEFAULT_RESOLUTION_KEY
    )


def _target_short_edge(scene):
    spec = dcc_config.export_resolution_spec(_resolution_key(scene))
    if spec.get("origin"):
        return 0.0
    short_edge = _positive_float(spec.get("short_edge"), 0.0)
    if short_edge > 0:
        return short_edge
    spec = dcc_config.export_resolution_spec(
        getattr(scene, "jimeng_resolution", "") or dcc_config.DEFAULT_RESOLUTION_KEY
    )
    width = _positive_float(spec.get("width"), FALLBACK_ORIGINAL_WIDTH)
    height = _positive_float(spec.get("height"), FALLBACK_ORIGINAL_HEIGHT)
    return max(2.0, min(width, height))


def scale_factor_for_scene(scene):
    width, height = original_resolution(scene)
    if width <= 0 or height <= 0:
        return 1.0
    target_short_edge = _target_short_edge(scene)
    if target_short_edge <= 0:
        return 1.0
    return min(1.0, target_short_edge / min(width, height))


def export_resolution(scene):
    original_width, original_height = original_resolution(scene)
    if _resolution_key(scene) == "origin":
        return _even_dimension(original_width), _even_dimension(original_height)
    scale = scale_factor_for_scene(scene)
    return (
        _even_dimension(original_width * scale),
        _even_dimension(original_height * scale),
    )


def _resolution(scene, _config):
    return export_resolution(scene)


def _camera(scene):
    camera = scene.jimeng_camera
    if camera and camera.type == "CAMERA":
        return camera
    raise ViewportRenderError("Choose a valid Blender camera before exporting to Dreamina.")


def _frame_range(scene):
    start = int(getattr(scene, "jimeng_frame_start", scene.frame_start))
    end = int(getattr(scene, "jimeng_frame_end", scene.frame_end))
    if start > end:
        raise ViewportRenderError("Frame Start must be less than or equal to Frame End.")
    return start, end


def _output_path(scene, camera, preview_mode):
    output_dir = bpy.path.abspath(scene.jimeng_output_dir or settings.default_output_dir())
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = camera.name.replace(os.sep, "_")
    prefix = "material_preview" if preview_mode == "material" else "white_model"
    return os.path.join(output_dir, "{0}_{1}_{2}.mp4".format(prefix, name, stamp))


def _frame_sequence_dir(output_path):
    root, _ext = os.path.splitext(output_path)
    frames_dir = root + "_frames"
    if os.path.isdir(frames_dir):
        shutil.rmtree(frames_dir)
    os.makedirs(frames_dir)
    return frames_dir


def _first_existing_frame(frames_dir):
    for name in sorted(os.listdir(frames_dir)):
        if name.lower().endswith(".png"):
            return os.path.join(frames_dir, name)
    return None


def _image_sequence_to_mp4(frames_dir, output_path, fps, start_frame):
    first_frame = _first_existing_frame(frames_dir)
    if not first_frame:
        raise ViewportRenderError("Blender did not create any PNG frames: {0}".format(frames_dir))

    input_pattern = os.path.join(frames_dir, "frame_%04d.png")
    arguments = [
        "-y",
        "-framerate",
        str(int(fps) or 24),
        "-start_number",
        str(int(start_frame)),
        "-i",
        input_pattern,
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2:out_range=tv,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-color_range",
        "tv",
        "-tag:v",
        "avc1",
        "-movflags",
        "+faststart",
        output_path,
    ]
    try:
        upload_bridge.run_ffmpeg(arguments, output_path=output_path)
    except upload_bridge.UploadError as exc:
        raise ViewportRenderError(str(exc))

    if not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
        raise ViewportRenderError("MP4 conversion did not create a valid file: {0}".format(output_path))
    return output_path


def _set_attr(obj, attr, value):
    if obj is not None and hasattr(obj, attr):
        try:
            setattr(obj, attr, value)
        except Exception:
            pass


def _set_first_supported_attr(obj, attr, values):
    if obj is None or not hasattr(obj, attr):
        return None
    for value in values:
        try:
            setattr(obj, attr, value)
            return value
        except Exception:
            pass
    return None


def render_preview_movie(scene, config=None):
    config = config or dcc_config.fallback_config()
    camera = _camera(scene)
    frame_start, frame_end = _frame_range(scene)
    width, height = _resolution(scene, config)
    fps = int(dcc_config.video_protocol(config).get("fps") or dcc_config.DEFAULT_FPS)
    preview_mode = preview_mode_for_scene(scene)
    output_path = _output_path(scene, camera, preview_mode)
    frames_dir = _frame_sequence_dir(output_path)

    render = scene.render
    image_settings = render.image_settings
    ffmpeg = getattr(render, "ffmpeg", None)
    display = scene.display
    shading = getattr(display, "shading", None)

    previous = {
        "camera": scene.camera,
        "frame_current": scene.frame_current,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "engine": render.engine,
        "filepath": render.filepath,
        "resolution_x": render.resolution_x,
        "resolution_y": render.resolution_y,
        "resolution_percentage": render.resolution_percentage,
        "file_format": image_settings.file_format,
        "shading_color_type": getattr(shading, "color_type", None),
        "shading_single_color": getattr(shading, "single_color", None),
        "shading_light": getattr(shading, "light", None),
        "shading_show_xray": getattr(shading, "show_xray", None),
    }
    if ffmpeg:
        previous.update(
            {
                "ffmpeg_format": getattr(ffmpeg, "format", None),
                "ffmpeg_codec": getattr(ffmpeg, "codec", None),
                "ffmpeg_crf": getattr(ffmpeg, "constant_rate_factor", None),
                "ffmpeg_audio_codec": getattr(ffmpeg, "audio_codec", None),
            }
        )

    try:
        scene.camera = camera
        scene.frame_start = frame_start
        scene.frame_end = frame_end
        scene.frame_set(frame_start)
        render.filepath = os.path.join(frames_dir, "frame_")
        render.resolution_x = width
        render.resolution_y = height
        render.resolution_percentage = 100

        try:
            render.engine = "BLENDER_WORKBENCH"
        except TypeError:
            pass

        image_settings.file_format = "PNG"

        if preview_mode == "material":
            _set_first_supported_attr(shading, "color_type", ("TEXTURE", "MATERIAL"))
        else:
            _set_attr(shading, "color_type", "SINGLE")
            _set_attr(shading, "single_color", (0.78, 0.78, 0.78))
        _set_attr(shading, "light", "STUDIO")
        _set_attr(shading, "show_xray", False)

        bpy.ops.render.opengl(animation=True, view_context=False)
    except Exception as exc:
        raise ViewportRenderError("Blender viewport render failed: {0}".format(exc))
    finally:
        scene.camera = previous["camera"]
        scene.frame_start = previous["frame_start"]
        scene.frame_end = previous["frame_end"]
        scene.frame_set(previous["frame_current"])
        render.engine = previous["engine"]
        render.filepath = previous["filepath"]
        render.resolution_x = previous["resolution_x"]
        render.resolution_y = previous["resolution_y"]
        render.resolution_percentage = previous["resolution_percentage"]
        image_settings.file_format = previous["file_format"]
        if ffmpeg:
            _set_attr(ffmpeg, "format", previous.get("ffmpeg_format"))
            _set_attr(ffmpeg, "codec", previous.get("ffmpeg_codec"))
            _set_attr(ffmpeg, "constant_rate_factor", previous.get("ffmpeg_crf"))
            _set_attr(ffmpeg, "audio_codec", previous.get("ffmpeg_audio_codec"))
        _set_attr(shading, "color_type", previous["shading_color_type"])
        _set_attr(shading, "single_color", previous["shading_single_color"])
        _set_attr(shading, "light", previous["shading_light"])
        _set_attr(shading, "show_xray", previous["shading_show_xray"])

    try:
        return _image_sequence_to_mp4(
            frames_dir,
            output_path,
            fps,
            frame_start,
        )
    finally:
        try:
            shutil.rmtree(frames_dir)
        except Exception:
            pass


def render_white_model_movie(scene, config=None):
    return render_preview_movie(scene, config)
