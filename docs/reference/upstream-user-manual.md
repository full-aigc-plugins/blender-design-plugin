# Upstream user manual — Jimeng Seedance 2.5 white-model render uploader

> Transcribed from the official user-facing documentation supplied by the maintainer
> (2026-09-12). This is the behavioural authority for the Codex Skills in Task 4: the flows
> Codex exposes must be recognisably the same two flows described here. Screenshot markers in
> the original are omitted; the prose is verbatim in substance.

**Positioning.** The add-on targets Blender and Maya users of the "即梦 Seedance 2.5 白模渲染插件"
(Jimeng Seedance 2.5 white-model render uploader). Install it inside Blender or Maya, export a
white-model video with one click, and jump seamlessly to the Jimeng web app, where the exported
video is used as the reference-video input. That is the whole point of the product: it closes
the loop from "3D white-model authoring" to "AI render generation".

## Blender installation

1. Download the plugin zip from the Jimeng site — `https://jimeng.jianying.com/ai-tool/home`.
2. `Edit` > `Preferences` > `Add-ons` > `Install from Disk`, choose the zip, `Install from Disk`.
3. On success the list shows 即梦 Seedance 2.5 白模渲染上传器; leave it enabled.
4. Open the 3D View sidebar (`N`) and select the `Jimeng` tab.

## Blender: the two export flows

**Flow 1 — camera render (`相机渲染`).** Choose 相机渲染 as the video upload method, set the
camera parameters, resolution, and save location, then click 渲染 (render). When the render
finishes a Jimeng link appears; click 上传至即梦生成.

**Flow 2 — local upload (`本地上传`).** Choose 本地上传, pick the already-rendered white-model
video from disk, then click 上传至即梦生成.

Either flow navigates to the Jimeng page and injects the rendered white-model video as the
reference-video input.

## Maya installation

1. Download the same plugin zip from the Jimeng site.
2. Unpack and run the installer script — `install_maya_plugin.command` on Mac,
   `install_maya_plugin.bat` on Windows. On Mac, macOS may block it: use the question-mark in
   the dialog and allow it under 隐私与安全性 (`Privacy & Security`) via "仍要打开" (Open
   Anyway). Run the terminal command, press Return, wait for 进程已完成 (process completed),
   restart Maya, and allow access to the plugin location.
3. In Maya: open or create a project, then `窗口` (`Window`) > `设置/首选项` (Settings/
   Preferences) > `插件管理器` (Plug-in Manager).
4. In the Plug-in Manager click 浏览 (Browse), select the plugin location, open the `plug-ins`
   folder, choose `jimeng_maya_uploader_plugin.py`, and open it.
5. Search the Plug-in Manager for `jimeng_maya_uploader_plugin.py` and tick both 已加载
   (Loaded) and 自动加载 (Auto-load). On success the top bar shows
   即梦 Seedance 2.5 白模渲染上传器.

## Maya: the two export flows

**Flow 1 — camera render.** Choose 相机渲染, set the camera parameters, resolution, frame
range, and save location, then click 渲染. Then click 上传至即梦生成.

**Flow 2 — local upload.** Choose 本地上传, pick the local file, click 渲染, then click
上传至即梦生成.

Both flows jump to the Jimeng page and use the rendered white-model video as the
reference-video input.

## Scope notes for this repository

- The feature parity target for the Codex integration is the **Blender** surface. The Maya
  add-on is described here for context only; `codex-blender` is Blender-scoped and the plan
  claims no Maya support.
- Where the manual says "click 渲染 in the local-upload flow", the underlying behaviour is that
  a non-MP4 local file is converted before it can be uploaded; the render step in that flow is
  the conversion, not a Blender render.
- The manual documents the product's user-visible contract, not its internals. Numeric limits
  and encoding settings live in the integration plan's upstream-interop section.
