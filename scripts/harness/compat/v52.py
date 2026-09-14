"""Compatibility adapter for Blender 5.2.x.

Blender 5.2 changed the compositor tree API: scenes use
compositing_node_group instead of node_tree, and the composite output
node is NodeGroupOutput (CompositorNodeComposite was removed).

Runtime-verified: YES against Blender 5.2.1 (arm64, macOS).
"""

from .base import BlenderCompatibilityAdapter


class Blender52Adapter(BlenderCompatibilityAdapter):
    """Adapter for Blender 5.2.x (verified against 5.2.1)."""

    def create_compositor_tree(self, scene):
        tree = getattr(scene, 'compositing_node_group', None)
        if tree is None:
            tree = self.bpy.data.node_groups.new('Codex Scene Compositor', 'CompositorNodeTree')
            tree.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
            scene.compositing_node_group = tree
            if hasattr(scene, 'use_nodes'):
                scene.use_nodes = True
        return tree

    def configure_file_output(self, node, directory, base_name):
        # Evidence from 5.2.1 snapshot: has_directory=True, has_base_path=False,
        # has_file_name=True, has_file_output_items=True.  The 5.2 file output
        # node still uses the directory+file_name API, not base_path+file_slots.
        node.directory = str(directory)
        node.file_name = base_name + '_'
        if not any(getattr(s, 'name', '') == 'Image' for s in node.inputs):
            node.file_output_items.new('RGBA', 'Image')

    def configure_geometry_node_interface(self, modifier, socket_identifier, value):
        # Evidence from 5.2.1 snapshot: properties_inputs_available=True,
        # modifier_dict_access=False.  Use properties.inputs exclusively.
        interface_inputs = getattr(getattr(modifier, 'properties', None), 'inputs', None)
        if interface_inputs is not None and hasattr(interface_inputs, socket_identifier):
            property_socket = getattr(interface_inputs, socket_identifier)
            property_socket.value = value
            return property_socket.value
        # Fallback: should not happen in 5.2 but kept for robustness.
        modifier[socket_identifier] = value
        return modifier[socket_identifier]

    def create_grease_pencil_data(self, bpy_module, name, layers):
        """Create a GreasePencil v3 object (same as 5.0/5.1)."""
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
        # Evidence from 5.2.1 snapshot: available=['BLENDER_EEVEE'],
        # has_BLENDER_EEVEE_NEXT=False.  Prefer BLENDER_EEVEE in 5.2.
        if requested_engine in {'EEVEE', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'}:
            engine = next(
                (v for v in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT') if v in available_engines),
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
