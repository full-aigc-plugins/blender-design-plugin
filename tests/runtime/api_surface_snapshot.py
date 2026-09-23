#!/usr/bin/env python3
"""Capture the Blender API surface for version-compatibility analysis.

Run inside Blender:
    blender --background --factory-startup --python-exit-code 1 \
        --python tests/runtime/api_surface_snapshot.py -- <evidence-dir>

Writes <evidence-dir>/api_surface_<version>.json with the probed surface.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import bpy
except ImportError:
    print("ERROR: this script must run inside Blender (import bpy failed)", file=sys.stderr)
    sys.exit(1)


def _probe_compositor(bpy_module):
    """Probe compositor tree API."""
    scene = bpy_module.context.scene
    result = {
        'has_node_tree': hasattr(scene, 'node_tree') and scene.node_tree is not None,
        'has_compositing_node_group': hasattr(scene, 'compositing_node_group'),
        'scene_use_nodes': hasattr(scene, 'use_nodes'),
        'CompositorNodeComposite_available': hasattr(bpy_module.types, 'CompositorNodeComposite'),
    }
    # Try creating a compositor tree to see which API works.
    try:
        tree = bpy_module.data.node_groups.new('_probe_compositor', 'CompositorNodeTree')
        result['CompositorNodeTree_creatable'] = True
        result['interface_new_socket_available'] = hasattr(tree.interface, 'new_socket')
        bpy_module.data.node_groups.remove(tree)
    except Exception as exc:  # noqa: BLE001
        result['CompositorNodeTree_creatable'] = False
        result['CompositorNodeTree_error'] = str(exc)
    return result


def _probe_file_output(bpy_module):
    """Probe file output node attributes."""
    try:
        tree = bpy_module.data.node_groups.new('_probe_fileout', 'CompositorNodeTree')
        node = tree.nodes.new('CompositorNodeOutputFile')
        result = {
            'has_directory': hasattr(node, 'directory'),
            'has_base_path': hasattr(node, 'base_path'),
            'has_file_name': hasattr(node, 'file_name'),
            'has_file_output_items': hasattr(node, 'file_output_items'),
            'has_file_slots': hasattr(node, 'file_slots'),
            'has_layer_slots': hasattr(node, 'layer_slots'),
        }
        bpy_module.data.node_groups.remove(tree)
    except Exception as exc:  # noqa: BLE001
        result = {'error': str(exc)}
    return result


def _probe_geometry_nodes(bpy_module):
    """Probe geometry nodes modifier interface API."""
    result = {
        'GeometryNodeTree_available': hasattr(bpy_module.types, 'GeometryNodeTree'),
        'NODES_modifier_type': 'NODES' in {item.identifier for item in bpy_module.types.Modifier.bl_rna.properties['type'].enum_items} if hasattr(bpy_module.types, 'Modifier') else False,
    }
    # Try creating a mesh + geometry nodes modifier to probe properties.inputs.
    try:
        mesh = bpy_module.data.meshes.new('_probe_mesh')
        obj = bpy_module.data.objects.new('_probe_obj', mesh)
        bpy_module.context.scene.collection.objects.link(obj)
        group = bpy_module.data.node_groups.new('_probe_gn', 'GeometryNodeTree')
        group.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        modifier = obj.modifiers.new(name='GN', type='NODES')
        modifier.node_group = group
        result['properties_inputs_available'] = hasattr(getattr(modifier, 'properties', None), 'inputs')
        result['modifier_dict_access'] = hasattr(modifier, '__getitem__')
        # Cleanup
        obj.modifiers.remove(modifier)
        bpy_module.data.node_groups.remove(group)
        bpy_module.data.objects.remove(obj, do_unlink=True)
        bpy_module.data.meshes.remove(mesh)
    except Exception as exc:  # noqa: BLE001
        result['probe_error'] = str(exc)
    return result


def _probe_grease_pencil(bpy_module):
    """Probe Grease Pencil API."""
    result = {
        'GPencil_available': hasattr(bpy_module.types, 'GPencil') or hasattr(bpy_module.data, 'grease_pencil'),
        'GreasePencil_available': hasattr(bpy_module.types, 'GreasePencil'),
        'grease_pencil_add_operator': callable(getattr(bpy_module.ops.object, 'grease_pencil_add', None)),
    }
    # Try creating a GP object to see which API works.
    try:
        bpy_module.ops.object.grease_pencil_add(type='EMPTY')
        obj = bpy_module.context.object
        if obj is not None:
            result['gp_created_type'] = obj.type
            result['gp_has_layers'] = hasattr(obj.data, 'layers')
            result['gp_has_drawing'] = hasattr(obj.data, 'drawing') if hasattr(obj.data, 'drawing') else False
            bpy_module.data.objects.remove(obj, do_unlink=True)
    except Exception as exc:  # noqa: BLE001
        result['gp_create_error'] = str(exc)
    return result


def _probe_render_engine(bpy_module):
    """Probe render engine identifiers."""
    scene = bpy_module.context.scene
    available = {item.identifier for item in scene.render.bl_rna.properties['engine'].enum_items}
    return {
        'available_engines': sorted(available),
        'has_BLENDER_EEVEE': 'BLENDER_EEVEE' in available,
        'has_BLENDER_EEVEE_NEXT': 'BLENDER_EEVEE_NEXT' in available,
        'has_CYCLES': 'CYCLES' in available,
    }


def _probe_rigify(bpy_module):
    """Probe Rigify operator availability."""
    return {
        'pose_rigify_generate': hasattr(bpy_module.ops.pose, 'rigify_generate'),
    }


def _probe_vse(bpy_module):
    """Probe VSE API."""
    scene = bpy_module.context.scene
    editor = scene.sequence_editor_create()
    # Blender 4.2 calls the strip collection `sequences`; 4.5+ renamed it `strips`.
    strips_attr = 'strips' if hasattr(editor, 'strips') else 'sequences'
    strips_rna = getattr(editor, strips_attr).bl_rna
    new_effect_params = {p.identifier for p in strips_rna.functions.get('new_effect', type('F', (), {'parameters': []})).parameters} if 'new_effect' in {f.identifier for f in strips_rna.functions} else set()
    return {
        'strips_collection_attr': strips_attr,
        'strips_new_effect_has_length': 'length' in new_effect_params,
        'strips_new_effect_has_seq1': 'seq1' in new_effect_params,
        'has_sequences_attr': hasattr(editor, 'sequences'),
    }


def _version_string(bpy_module):
    v = bpy_module.app.version
    return f'{v[0]}.{v[1]}.{v[2]}'


def main():
    if len(sys.argv) < 2:
        evidence_dir = Path('.')
    else:
        # argv[0] is the script path; args after '--' start at argv[1].
        evidence_dir = Path(sys.argv[-1]) if sys.argv[-1] != sys.argv[0] else Path('.')

    evidence_dir.mkdir(parents=True, exist_ok=True)
    version = _version_string(bpy)
    surface = {
        'blender_version': version,
        'version_tuple': list(bpy.app.version),
        'platform': sys.platform,
        'compositor': _probe_compositor(bpy),
        'file_output': _probe_file_output(bpy),
        'geometry_nodes': _probe_geometry_nodes(bpy),
        'grease_pencil': _probe_grease_pencil(bpy),
        'render_engine': _probe_render_engine(bpy),
        'rigify': _probe_rigify(bpy),
        'vse': _probe_vse(bpy),
    }
    out_path = evidence_dir / f'api_surface_{version}.json'
    out_path.write_text(json.dumps(surface, indent=2, sort_keys=True))
    print(f'API surface snapshot written to {out_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
