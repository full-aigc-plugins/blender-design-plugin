"""Optional Connector Add-on for attaching Codex to an open Blender session."""

bl_info = {
    "name": "Blender Design Connector",
    "author": "PartMe.AI",
    "version": (0, 3, 0),
    "blender": (4, 2, 0),
    "location": "3D View > Sidebar > Codex > Start MCP Server",
    "description": "Expose the guarded Blender Design Harness through the plugin-owned MCP adapter",
    "category": "Interface",
}


def register():
    import bpy

    from . import runtime
    from .panel import register as register_panel
    register_panel()
    if runtime.on_file_loaded not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(runtime.on_file_loaded)


def unregister():
    import bpy

    from . import runtime
    from .panel import unregister as unregister_panel
    from .runtime import stop
    stop()
    if runtime.on_file_loaded in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(runtime.on_file_loaded)
    unregister_panel()
