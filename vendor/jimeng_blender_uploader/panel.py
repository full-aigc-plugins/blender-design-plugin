"""Blender UI panel for Jimeng/Dreamina uploader."""

from __future__ import annotations

import os

import bpy

from . import dcc_config, operators, state, variant


def _label_factor(context):
    base_factor = 0.31
    region_width = int(getattr(getattr(context, "region", None), "width", 0) or 0)
    if region_width <= 0:
        return base_factor
    min_label_factor = 148.0 / float(region_width)
    return min(0.40, max(base_factor, min_label_factor))


PANEL_TITLE_INDENT = "    "
ACTION_INDENT_FACTOR = 0.0


def _label_lines(text):
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    return [" ".join(lines)] if lines else [""]


def _contains_cjk(text):
    return any("\u4e00" <= char <= "\u9fff" for char in str(text or ""))


def _wrap_label_lines(text, context=None, label_factor=None):
    lines = _label_lines(text)
    if len(lines) != 1:
        return lines

    label = lines[0]
    region_width = int(getattr(getattr(context, "region", None), "width", 0) or 0)
    if not label or not region_width or not label_factor:
        return lines

    label_width = float(region_width) * float(label_factor)
    if _contains_cjk(label) and len(label) > 4 and label_width < 170:
        return [label[:4], label[4:]]

    words = label.split()
    if len(words) > 1 and label_width < 170:
        return words

    return lines


def _draw_form_label(layout, text, context=None, label_factor=None):
    lines = _wrap_label_lines(text, context=context, label_factor=label_factor)
    if len(lines) == 1:
        label_row = layout.row(align=True)
        label_row.alignment = "RIGHT"
        label_row.label(text=lines[0])
        return

    label_col = layout.column(align=True)
    for line in lines:
        line_row = label_col.row(align=True)
        line_row.alignment = "RIGHT"
        line_row.label(text=line)


def _hint_row(box, label_factor, text):
    split = box.split(factor=label_factor, align=True)
    split.separator()
    hint = split.row(align=True)
    # Blender's native UILayout label has no per-widget font-size API. Keep these
    # hint rows as visually quiet as the stock UI allows; true smaller text would
    # require custom drawing outside the standard add-on panel widgets.
    hint.scale_y = 0.55
    hint.enabled = False
    hint.label(text=text)


def _form_split(box, label_factor, text, context=None):
    split = box.split(factor=label_factor, align=True)
    _draw_form_label(split, text, context=context, label_factor=label_factor)
    return split


def _mode_row(box, scene, label_factor, context):
    split = _form_split(box, label_factor, variant.text("video_upload_method"), context=context)
    mode_row = split.row(align=True)
    mode_row.scale_y = 1.15
    op = mode_row.operator(
        "jimeng.set_uploader_mode",
        text=variant.text("mode_camera_display"),
        depress=scene.jimeng_uploader_mode == "VIEWPORT",
    )
    op.mode = "VIEWPORT"
    op = mode_row.operator(
        "jimeng.set_uploader_mode",
        text=variant.text("mode_local_display"),
        depress=scene.jimeng_uploader_mode == "EXISTING",
    )
    op.mode = "EXISTING"


def _action_row(box):
    if ACTION_INDENT_FACTOR <= 0:
        row = box.row(align=True)
        row.scale_y = 1.25
        return row
    split = box.split(factor=ACTION_INDENT_FACTOR, align=True)
    split.separator()
    row = split.row(align=True)
    row.scale_y = 1.25
    return row


def _error_row(box, text):
    if not text:
        return
    row = box.row(align=True)
    row.scale_y = 0.75
    row.alert = True
    row.label(text=text)


def _button_hint_row(box, text):
    if not text:
        return
    row = box.row(align=True)
    row.scale_y = 0.55
    row.enabled = False
    row.label(text=text)


def _link_display_text(text, context):
    value = str(text or "")
    if not value:
        return ""

    region_width = int(getattr(getattr(context, "region", None), "width", 0) or 0)
    if region_width <= 0:
        return value

    max_chars = max(16, int(region_width / 8) - 18)
    if len(value) <= max_chars:
        return value

    head = max(6, max_chars // 2)
    tail = max(6, max_chars - head - 3)
    return "{0}...{1}".format(value[:head], value[-tail:])


def _link_area(box, label_factor, scene, context):
    if not state.link_is_current(scene):
        return

    link_row = box.row(align=True)
    link_split = link_row.split(factor=0.08, align=True)
    link_label = link_split.row(align=True)
    link_label.alignment = "LEFT"
    link_label.label(text=variant.text("dreamina_link"))
    link_field = link_split.row(align=True)
    link_field.prop(scene, "jimeng_redirect_url_display", text="")

    open_row = box.row(align=True)
    open_row.scale_y = 1.15
    open_row.operator("jimeng.open_redirect_url", text=variant.text("open_link"))


class VIEW3D_PT_jimeng_uploader(bpy.types.Panel):
    bl_label = PANEL_TITLE_INDENT + variant.APP_NAME
    bl_idname = "VIEW3D_PT_jimeng_uploader"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = variant.SIDEBAR_CATEGORY
    bl_ui_units_x = 24

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.column()
        box.use_property_split = False
        label_factor = _label_factor(context)

        _mode_row(box, scene, label_factor, context)

        mode = scene.jimeng_uploader_mode
        if mode == "EXISTING":
            _hint_row(
                box,
                label_factor,
                variant.text("upload_limit", size=scene.jimeng_dcc_file_size_label),
            )

            video_split = _form_split(box, label_factor, variant.text("choose_video_file"), context=context)
            video_split.prop(scene, "jimeng_video_path", text="")
        else:
            _hint_row(
                box,
                label_factor,
                variant.text("upload_limit", size=scene.jimeng_dcc_file_size_label),
            )

            camera_split = _form_split(box, label_factor, variant.text("camera"), context=context)
            camera_split.prop(scene, "jimeng_camera", text="")

            resolution_split = _form_split(box, label_factor, variant.text("resolution"), context=context)
            resolution_split.prop(scene, "jimeng_resolution", text="")

            frame_split = _form_split(box, label_factor, variant.text("frame_range"), context=context)
            frame_row = frame_split.row(align=True)
            frame_row.prop(scene, "jimeng_frame_start", text="")
            frame_row.prop(scene, "jimeng_frame_end", text="")
            frame_row.operator("jimeng.use_scene_frame_range", text="", icon="FILE_REFRESH")

            _hint_row(box, label_factor, variant.text("max_frames", count=scene.jimeng_frame_limit_display))

            icon = "TRIA_DOWN" if scene.jimeng_default_params_expanded else "TRIA_RIGHT"
            params_row = box.row(align=True)
            params_row.alignment = "LEFT"
            params_title = " ".join(_label_lines(variant.text("default_params")))
            params_row.operator("jimeng.toggle_default_params", text=params_title, icon=icon, emboss=False)
            if scene.jimeng_default_params_expanded:
                protocol_split = box.split(factor=label_factor, align=True)
                protocol_split.separator()
                protocol_box = protocol_split.box()
                row = protocol_box.row()
                row.enabled = False
                row.label(text=variant.text("frame_rate"))
                row.label(text="{0}fps".format(scene.jimeng_dcc_fps))
                row = protocol_box.row()
                row.enabled = False
                row.label(text=variant.text("format"))
                row.label(text="{0} {1}".format(scene.jimeng_dcc_container_format, scene.jimeng_dcc_codec))
                row = protocol_box.row()
                row.enabled = False
                row.label(text=variant.text("preview_mode"))
                row.label(text=variant.text("preview_mode_auto"))

            output_split = _form_split(box, label_factor, variant.text("output_to"), context=context)
            output_split.prop(scene, "jimeng_output_dir", text="")

        task_state = getattr(scene, "jimeng_task_state", "IDLE")
        task_running = task_state == "RUNNING"
        preview_path = bpy.path.abspath(getattr(scene, "jimeng_video_path", "") or "")
        preview_ready = bool(preview_path and os.path.exists(preview_path))
        if mode != "EXISTING":
            preview_ready = preview_ready and state.link_is_current(scene)

        if mode == "EXISTING":
            row = _action_row(box)
            main_action = row.row(align=True)
            main_enabled = True
            main_action.enabled = main_enabled and not task_running
            main_action.operator(
                "jimeng.upload_existing",
                text=variant.text("open_link"),
                depress=main_enabled and not task_running,
            )
        else:
            row = _action_row(box)
            main_action = row.row(align=True)
            frame_too_short = operators.selected_ui_frame_range_too_short(scene)
            main_enabled = bool(scene.jimeng_camera) and not frame_too_short
            main_action.enabled = main_enabled and not task_running
            main_action.operator(
                "jimeng.render_upload",
                text=variant.text("render"),
                depress=main_enabled and not task_running,
            )

        preview_action = row.row(align=True)
        preview_action.enabled = bool(preview_ready and not task_running)
        preview_action.operator("jimeng.preview_video", text="", icon="PLAY")

        if mode != "EXISTING" and operators.selected_ui_frame_range_too_short(scene):
            _button_hint_row(
                box,
                variant.text(
                    "min_frames_hint",
                    count=operators.min_frame_limit(scene),
                    seconds=dcc_config.DEFAULT_MIN_DURATION_SECONDS,
                ),
            )

        if task_state == "FAILED":
            _error_row(box, getattr(scene, "jimeng_error_message", ""))

        if task_state != "RUNNING":
            _link_area(box, label_factor, scene, context)


CLASSES = (VIEW3D_PT_jimeng_uploader,)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
