"""Vendored subset of jimeng_blender_uploader for headless use.

This package contains the headless core of the official
jimeng_blender_uploader Blender add-on (version 1.0.0, macOS/CN build).
Only the modules required for the render/encode/upload pipeline are
included.  The upstream UI registration (__init__.py, operators.py,
panel.py, state.py) is deliberately excluded because it imports bpy at
module level and registers Blender operators and panels, which cannot
run outside Blender.
"""
