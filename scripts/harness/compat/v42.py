"""Compatibility adapter for Blender 4.2.x.

Key API differences from later versions:
- Compositor uses scene.node_tree, CompositorNodeComposite.
- File output uses node.directory + node.file_name + node.file_output_items.
- Geometry Nodes modifier inputs use modifier[identifier] = value.
- Render engine EEVEE is BLENDER_EEVEE.
- Grease Pencil uses legacy GPencil data-blocks (not the 5.x rewrite).
- VSE effect strips use sequences.new_effect with seq1/seq2 kwargs.
"""

from .base import BlenderCompatibilityAdapter


class Blender42Adapter(BlenderCompatibilityAdapter):
    """Adapter for Blender 4.2.x."""

    def create_compositor_tree(self, scene):
        tree = getattr(scene, 'node_tree', None)
        if tree is None:
            tree = self.bpy.data.node_groups.new('Codex Scene Compositor', 'CompositorNodeTree')
            tree.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
            scene.node_tree = tree
            if hasattr(scene, 'use_nodes'):
                scene.use_nodes = True
        return tree

    def configure_file_output(self, node, directory, base_name):
        node.directory = str(directory)
        node.file_name = base_name + '_'
        if not any(getattr(s, 'name', '') == 'Image' for s in node.inputs):
            node.file_output_items.new('RGBA', 'Image')

    def configure_geometry_node_interface(self, modifier, socket_identifier, value):
        modifier[socket_identifier] = value
        return modifier[socket_identifier]

    def create_grease_pencil_data(self, bpy_module, name, layers):
        gp_data = bpy_module.data.grease_pencil.new(name)
        obj = bpy_module.data.objects.new(name, gp_data)
        bpy_module.context.scene.collection.objects.link(obj)
        for existing in list(gp_data.layers):
            gp_data.layers.remove(existing)
        for index, layer_name in enumerate(layers):
            gp_data.layers.new(layer_name, set_active=index == 0)
        return obj

    def configure_render_engine(self, scene, requested_engine, available_engines):
        if requested_engine in {'EEVEE', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'}:
            engine = next(
                (v for v in ('BLENDER_EEVEE',) if v in available_engines), None
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
