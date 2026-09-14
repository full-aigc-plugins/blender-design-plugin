"""Compatibility adapter for Blender 5.0.x and 5.1.x.

Blender 5.0 introduced the Grease Pencil v3 rewrite (GreasePencil
data-block with layers/drawings replacing GPencil).  The compositor
still uses scene.node_tree and CompositorNodeComposite in 5.0–5.1.

Runtime-verified: NO.  Only Blender 5.2.1 is installed.  The adapter
here is based on changelog analysis, not live testing.
"""

from .base import BlenderCompatibilityAdapter


class Blender5051Adapter(BlenderCompatibilityAdapter):
    """Adapter for Blender 5.0.x and 5.1.x.

    Overrides create_grease_pencil_data for the GreasePencil v3 API.
    Other methods inherit the base class defaults where the 5.0/5.1
    behaviour matches 5.2; methods that differ from 5.2 but are
    unverifiable here are left as base-class defaults and will surface
    CAPABILITY_UNAVAILABLE if called.
    """

    def create_compositor_tree(self, scene):
        # In 5.0/5.1 the compositor still uses scene.node_tree.
        tree = getattr(scene, 'node_tree', None)
        if tree is None:
            tree = self.bpy.data.node_groups.new('Codex Scene Compositor', 'CompositorNodeTree')
            tree.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
            scene.node_tree = tree
            if hasattr(scene, 'use_nodes'):
                scene.use_nodes = True
        return tree

    def configure_file_output(self, node, directory, base_name):
        # In 5.0/5.1 the file output node uses base_path + file_slots.
        node.base_path = str(directory)
        slots = getattr(node, 'file_slots', None) or getattr(node, 'layer_slots', None)
        if slots and len(slots):
            slots[0].path = base_name + '_'

    def configure_geometry_node_interface(self, modifier, socket_identifier, value):
        # In 5.0/5.1 the properties.inputs interface may be available.
        # Try the new interface first, fall back to dict-style.
        interface_inputs = getattr(getattr(modifier, 'properties', None), 'inputs', None)
        if interface_inputs is not None and hasattr(interface_inputs, socket_identifier):
            property_socket = getattr(interface_inputs, socket_identifier)
            property_socket.value = value
            return property_socket.value
        modifier[socket_identifier] = value
        return modifier[socket_identifier]

    def create_grease_pencil_data(self, bpy_module, name, layers):
        """Create a GreasePencil v3 object (5.0+ API)."""
        bpy_module.ops.object.grease_pencil_add(type='EMPTY')
        obj = bpy_module.context.object
        obj.name = name
        for existing in list(obj.data.layers):
            obj.data.layers.remove(existing)
        obj.data.materials.clear()
        for index, layer_name in enumerate(layers):
            obj.data.layers.new(layer_name, set_active=index == 0)
        return obj

    def configure_render_engine(self, scene, requested_engine, available_engines):
        if requested_engine in {'EEVEE', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'}:
            engine = next(
                (v for v in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE') if v in available_engines),
                None,
            )
            if engine is None:
                from ..errors import HarnessError
                raise HarnessError('CAPABILITY_UNAVAILABLE', 'Eevee is unavailable')
            return engine
        if requested_engine == 'CYCLES':
            return 'CYCLES'
        from ..errors import HarnessError
        raise HarnessError('INVALID_ARGUMENT', 'unsupported render engine')

    def enable_rigify(self, bpy_module):
        try:
            import addon_utils
            bundled = any(m.__name__ == 'rigify' for m in addon_utils.modules())
        except (ImportError, AttributeError):
            bundled = False
        addons = bpy_module.context.preferences.addons
        modules = [item if isinstance(item, str) else str(getattr(item, 'module', '')) for item in addons]
        enabled = addons.get('rigify') is not None or any(
            m == 'rigify' or m.endswith('.rigify') for m in modules
        )
        operator = hasattr(bpy_module.ops.pose, 'rigify_generate')
        return {
            'installed': bundled or enabled,
            'bundledAvailable': bundled,
            'enabled': enabled,
            'operatorAvailable': operator and enabled,
            'blenderVersion': bpy_module.app.version_string,
        }
