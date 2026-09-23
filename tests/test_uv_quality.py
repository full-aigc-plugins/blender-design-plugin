"""Tests for uv.detect_overlap and uv.measure_texel_density."""
import math
import unittest
from types import SimpleNamespace

from scripts.harness.commands.uv import UVCommands
from scripts.harness.errors import HarnessError
from scripts.harness.identity import ObjectResolver
from tests.test_design_commands import FakeBpy

# -- Lightweight fakes with UV data -------------------------------------------

class FakeUVCoord:
    """Mimics mathutils.Vector(2) -- supports .x/.y and iteration."""
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __iter__(self):
        return iter((self.x, self.y))

    def __repr__(self):
        return f'<FakeUVCoord ({self.x}, {self.y})>'


class FakeUVLayerData:
    """Mimics bpy.types.MeshUVLoopLayer.data (indexed by loop index).

    Each entry has a .uv attribute (a SimpleNamespace with .x and .y),
    matching how Blender's UV layer data actually works: data[i].uv.x/y.
    """
    def __init__(self):
        self._entries = {}

    def __getitem__(self, index):
        return self._entries[index]

    def __setitem__(self, index, uv):
        self._entries[index] = uv


class FakeUVLayer:
    def __init__(self, name='UVMap'):
        self.name = name
        self.data = FakeUVLayerData()


class FakePolygon:
    def __init__(self, index, loop_indices, vertex_indices):
        self.index = index
        self.loop_indices = loop_indices
        self.vertices = vertex_indices


class FakeVertex:
    def __init__(self, co):
        self.co = co


class FakeMeshWithUV:
    """Minimal mesh that carries UV layers, polygons and vertices."""
    def __init__(self):
        self.uv_layers = FakeUVLayers()
        self.polygons = []
        self.vertices = []

    def add_polygon(self, loop_indices, uvs, positions):
        """Add a polygon: loop_indices are auto-assigned, uvs are (x,y) pairs."""
        idx = len(self.polygons)
        base = len(self.uv_layers.active.data._entries) if self.uv_layers.active else 0
        vert_base = len(self.vertices)
        self.polygons.append(FakePolygon(idx, list(range(base, base + len(uvs))),
                                         list(range(vert_base, vert_base + len(positions)))))
        if self.uv_layers.active:
            for i, (u, v) in enumerate(uvs):
                self.uv_layers.active.data[base + i] = SimpleNamespace(
                    uv=FakeUVCoord(u, v))
        for pos in positions:
            self.vertices.append(FakeVertex(pos))


class FakeUVLayers:
    def __init__(self):
        self._active = None
        self._layers = {}

    @property
    def active(self):
        return self._active

    def new(self, name='UVMap'):
        layer = FakeUVLayer(name)
        self._active = layer
        self._layers[name] = layer
        return layer

    def get(self, name):
        return self._layers.get(name)


class FakeObjectWithUV:
    def __init__(self, name, mesh):
        self.name = name
        self.type = 'MESH'
        self.data = mesh
        self._props = {}

    def get(self, key, default=None):
        return self._props.get(key, default)

    def __setitem__(self, key, value):
        self._props[key] = value


# -- Shared test helpers -------------------------------------------------------

def _make_unit_square_mesh(uv_offset=(0, 0)):
    """Two triangles forming a unit square at UV positions offset by uv_offset.

    Face 0: triangle (0,0)-(1,0)-(1,1) in UV, same in 3D
    Face 1: triangle (0,0)-(1,1)-(0,1) in UV, same in 3D
    Total 3D area = 1.0.  Total UV area = 1.0.
    """
    ox, oy = uv_offset
    mesh = FakeMeshWithUV()
    mesh.uv_layers.new('UVMap')
    # Face 0: triangle
    mesh.add_polygon(
        loop_indices=[0, 1, 2],
        uvs=[(0 + ox, 0 + oy), (1 + ox, 0 + oy), (1 + ox, 1 + oy)],
        positions=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
    )
    # Face 1: triangle
    mesh.add_polygon(
        loop_indices=[3, 4, 5],
        uvs=[(0 + ox, 0 + oy), (1 + ox, 1 + oy), (0 + ox, 1 + oy)],
        positions=[(0.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)],
    )
    return mesh


def _make_overlapping_mesh():
    """Two identical triangles occupying the same UV region.

    Face 0 and Face 1 both map to the triangle (0,0)-(0.5,0)-(0.5,0.5).
    Overlap area = 0.125 (half of 0.5 * 0.5).
    """
    mesh = FakeMeshWithUV()
    mesh.uv_layers.new('UVMap')
    uv_tri = [(0.0, 0.0), (0.5, 0.0), (0.5, 0.5)]
    mesh.add_polygon([0, 1, 2], uv_tri, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)])
    mesh.add_polygon([3, 4, 5], uv_tri, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)])
    return mesh


def _make_degenerate_mesh():
    """One normal triangle and one zero-area (degenerate) triangle in UV."""
    mesh = FakeMeshWithUV()
    mesh.uv_layers.new('UVMap')
    # Face 0: normal triangle
    mesh.add_polygon(
        [0, 1, 2],
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
    )
    # Face 1: degenerate (collinear UVs)
    mesh.add_polygon(
        [3, 4, 5],
        [(0.0, 0.0), (0.5, 0.0), (1.0, 0.0)],
        [(0.0, 0.0, 0.0), (0.5, 0.0, 0.0), (1.0, 0.0, 0.0)],
    )
    return mesh


def _make_udim_mesh():
    """Two triangles at identical local UV positions but on different UDIM tiles.

    Face 0: UV tile (0,0), local coords (0,0)-(0.5,0)-(0.5,0.5)
    Face 1: UV tile (1,0), local coords (0,0)-(0.5,0)-(0.5,0.5) (global: 1.0,0.0)-(1.5,0.0)-(1.5,0.5)
    These must NOT be reported as overlapping.
    """
    mesh = FakeMeshWithUV()
    mesh.uv_layers.new('UVMap')
    mesh.add_polygon(
        [0, 1, 2],
        [(0.0, 0.0), (0.5, 0.0), (0.5, 0.5)],
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
    )
    mesh.add_polygon(
        [3, 4, 5],
        [(1.0, 0.0), (1.5, 0.0), (1.5, 0.5)],
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
    )
    return mesh


def _register_object(bpy, obj):
    bpy.data.objects[obj.name] = obj
    resolver = ObjectResolver(bpy)
    resolver.ensure_id(obj)
    return obj


# -- Test cases ---------------------------------------------------------------

class TestDetectOverlapRegistered(unittest.TestCase):
    """Verify uv.detect_overlap exists in the registry."""
    def _all_ids(self, registry):
        ids = set()
        offset = 0
        while True:
            page = registry.list_capabilities({'offset': offset, 'limit': 100})
            for item in page.get('items', []):
                ids.add(item['id'])
            offset = page.get('nextOffset')
            if offset is None:
                break
        return ids

    def test_registered(self):
        from scripts.harness.runtime import build_registry
        bpy = FakeBpy()
        registry = build_registry(bpy)
        ids = self._all_ids(registry)
        self.assertIn('uv.detect_overlap', ids)

    def test_registered_texel_density(self):
        from scripts.harness.runtime import build_registry
        bpy = FakeBpy()
        registry = build_registry(bpy)
        ids = self._all_ids(registry)
        self.assertIn('uv.measure_texel_density', ids)


class TestDetectOverlapBasic(unittest.TestCase):
    def setUp(self):
        self.bpy = FakeBpy()
        self.uvs = UVCommands(self.bpy)

    def test_overlapping_faces_detected(self):
        mesh = _make_overlapping_mesh()
        obj = _register_object(self.bpy, FakeObjectWithUV('OverlapObj', mesh))
        result = self.uvs.detect_overlap({'objectId': obj.get('codex_blender_object_id')})
        res = result['result']
        self.assertEqual(result['changedObjects'], [])
        self.assertTrue(res['hasOverlaps'])
        overlaps = res['overlaps']
        self.assertEqual(len(overlaps), 1)
        pair = overlaps[0]
        self.assertIn('faceA', pair)
        self.assertIn('faceB', pair)
        self.assertIn('area', pair)
        self.assertIn('ratio', pair)
        # Both faces index 0 and 1
        self.assertEqual({pair['faceA'], pair['faceB']}, {0, 1})
        # Overlap area should be 0.125
        self.assertAlmostEqual(pair['area'], 0.125, places=6)

    def test_no_overlap_returns_empty(self):
        mesh = _make_unit_square_mesh()
        obj = _register_object(self.bpy, FakeObjectWithUV('NoOverlapObj', mesh))
        result = self.uvs.detect_overlap({'objectId': obj.get('codex_blender_object_id')})
        res = result['result']
        self.assertFalse(res['hasOverlaps'])
        self.assertEqual(res['overlaps'], [])

    def test_degenerate_faces_reported_separately(self):
        mesh = _make_degenerate_mesh()
        obj = _register_object(self.bpy, FakeObjectWithUV('DegenerateObj', mesh))
        result = self.uvs.detect_overlap({'objectId': obj.get('codex_blender_object_id')})
        res = result['result']
        # Face 1 is degenerate
        self.assertIn(1, res['degenerateFaces'])
        # Degenerate face must not appear in overlaps
        overlap_indices = set()
        for o in res['overlaps']:
            overlap_indices.add(o['faceA'])
            overlap_indices.add(o['faceB'])
        self.assertNotIn(1, overlap_indices)


class TestDetectOverlapUDIM(unittest.TestCase):
    def test_different_tiles_not_overlapping(self):
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = _make_udim_mesh()
        obj = _register_object(bpy, FakeObjectWithUV('UDIMObj', mesh))
        result = uvs.detect_overlap({'objectId': obj.get('codex_blender_object_id')})
        res = result['result']
        self.assertFalse(res['hasOverlaps'])
        self.assertEqual(res['overlaps'], [])

    def test_same_tile_overlap_detected(self):
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = FakeMeshWithUV()
        mesh.uv_layers.new('UVMap')
        # Both faces on tile (1,0) with overlapping UVs
        mesh.add_polygon(
            [0, 1, 2],
            [(1.0, 0.0), (1.5, 0.0), (1.5, 0.5)],
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
        )
        mesh.add_polygon(
            [3, 4, 5],
            [(1.1, 0.1), (1.5, 0.1), (1.5, 0.5)],
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
        )
        obj = _register_object(bpy, FakeObjectWithUV('SameTileObj', mesh))
        result = uvs.detect_overlap({'objectId': obj.get('codex_blender_object_id')})
        res = result['result']
        self.assertTrue(res['hasOverlaps'])


class TestDetectOverlapTolerance(unittest.TestCase):
    def test_tolerance_suppresses_tiny_overlap(self):
        """An overlap area smaller than tolerance must be suppressed."""
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = FakeMeshWithUV()
        mesh.uv_layers.new('UVMap')
        # Two large faces with a tiny sliver of overlap
        mesh.add_polygon(
            [0, 1, 2, 3],
            [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)],
        )
        mesh.add_polygon(
            [4, 5, 6, 7],
            [(0.9999, 0.0), (2.0, 0.0), (2.0, 1.0), (0.9999, 1.0)],
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)],
        )
        obj = _register_object(bpy, FakeObjectWithUV('ToleranceObj', mesh))
        # With tolerance > tiny overlap area, should suppress
        result = uvs.detect_overlap({
            'objectId': obj.get('codex_blender_object_id'),
            'tolerance': 0.01,
        })
        res = result['result']
        self.assertFalse(res['hasOverlaps'])

    def test_tolerance_passes_larger_overlap(self):
        """An overlap area larger than tolerance must be reported."""
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = _make_overlapping_mesh()
        obj = _register_object(bpy, FakeObjectWithUV('TolPassObj', mesh))
        # Overlap area is 0.125; tolerance 0.01 should not suppress it
        result = uvs.detect_overlap({
            'objectId': obj.get('codex_blender_object_id'),
            'tolerance': 0.01,
        })
        res = result['result']
        self.assertTrue(res['hasOverlaps'])
        self.assertEqual(len(res['overlaps']), 1)


class TestDetectOverlapReadOnly(unittest.TestCase):
    def test_detect_overlap_does_not_modify_mesh(self):
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = _make_overlapping_mesh()
        obj = _register_object(bpy, FakeObjectWithUV('ReadOnlyObj', mesh))
        # Snapshot polygon count and UV values
        poly_count_before = len(mesh.polygons)
        uvs_before = [(d.uv.x, d.uv.y) for d in mesh.uv_layers.active.data._entries.values()]
        uvs.detect_overlap({'objectId': obj.get('codex_blender_object_id')})
        poly_count_after = len(mesh.polygons)
        uvs_after = [(d.uv.x, d.uv.y) for d in mesh.uv_layers.active.data._entries.values()]
        self.assertEqual(poly_count_before, poly_count_after)
        self.assertEqual(uvs_before, uvs_after)


class TestMeasureTexelDensity(unittest.TestCase):
    def setUp(self):
        self.bpy = FakeBpy()
        self.uvs = UVCommands(self.bpy)

    def test_texel_density_unit_square(self):
        """A 1x1 meter plane with UVs covering [0,1]x[0,1] at 1024x1024.

        Expected density = 1024 px/m  (texels per meter).
        """
        mesh = _make_unit_square_mesh()
        obj = _register_object(self.bpy, FakeObjectWithUV('DensityObj', mesh))
        result = self.uvs.measure_texel_density({
            'objectId': obj.get('codex_blender_object_id'),
            'textureWidth': 1024,
            'textureHeight': 1024,
        })
        res = result['result']
        self.assertEqual(result['changedObjects'], [])
        self.assertEqual(res['textureWidth'], 1024)
        self.assertEqual(res['textureHeight'], 1024)
        faces = res['faces']
        self.assertEqual(len(faces), 2)
        for face_data in faces:
            self.assertIn('face', face_data)
            self.assertIn('texelDensity', face_data)
            self.assertIn('uvArea', face_data)
            self.assertIn('threeDArea', face_data)
            # Each triangle has area 0.5 in both UV and3D
            self.assertAlmostEqual(face_data['uvArea'], 0.5, places=6)
            self.assertAlmostEqual(face_data['threeDArea'], 0.5, places=6)
            # texelDensity = sqrt(1024*1024 * 0.5/0.5) = 1024
            self.assertAlmostEqual(face_data['texelDensity'], 1024.0, places=1)

    def test_texel_density_non_square_uv(self):
        """UV area = 0.5, 3D area = 1.0 => density = sqrt(W*H * 0.5)."""
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = FakeMeshWithUV()
        mesh.uv_layers.new('UVMap')
        # Single triangle: UV area 0.5, 3D area 1.0
        mesh.add_polygon(
            [0, 1, 2],
            [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],  # UV area = 0.5
            [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)],  # 3D area = 1.0
        )
        obj = _register_object(bpy, FakeObjectWithUV('NonSquareObj', mesh))
        result = uvs.measure_texel_density({
            'objectId': obj.get('codex_blender_object_id'),
            'textureWidth': 1024,
            'textureHeight': 1024,
        })
        face_data = result['result']['faces'][0]
        expected = math.sqrt(1024 * 1024 * 0.5 / 1.0)  # ~724.1
        self.assertAlmostEqual(face_data['texelDensity'], expected, places=0)

    def test_texel_density_zero_three_d_area(self):
        """A face with zero3D area should report density as null."""
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = FakeMeshWithUV()
        mesh.uv_layers.new('UVMap')
        # Collinear3D vertices => zero area
        mesh.add_polygon(
            [0, 1, 2],
            [(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)],
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        )
        obj = _register_object(bpy, FakeObjectWithUV('Zero3DObj', mesh))
        result = uvs.measure_texel_density({
            'objectId': obj.get('codex_blender_object_id'),
            'textureWidth': 512,
            'textureHeight': 512,
        })
        face_data = result['result']['faces'][0]
        self.assertIsNone(face_data['texelDensity'])


class TestDetectOverlapMissingUV(unittest.TestCase):
    def test_no_uv_layer_returns_error(self):
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = FakeMeshWithUV()
        # No UV layer created
        obj = _register_object(bpy, FakeObjectWithUV('NoUVObj', mesh))
        result = uvs.detect_overlap({'objectId': obj.get('codex_blender_object_id')})
        res = result['result']
        self.assertFalse(res['hasUV'])
        self.assertIn({'code': 'UV_MISSING'}, res['issues'])


class TestUVLayerParameter(unittest.TestCase):
    """F1: uvLayer parameter must be accepted and resolved correctly."""

    def test_absent_uv_layer_uses_active(self):
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = _make_overlapping_mesh()
        obj = _register_object(bpy, FakeObjectWithUV('ActiveLayerObj', mesh))
        result = uvs.detect_overlap({'objectId': obj.get('codex_blender_object_id')})
        self.assertTrue(result['result']['hasUV'])
        self.assertEqual(result['result']['layer'], 'UVMap')

    def test_named_uv_layer_resolves(self):
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = FakeMeshWithUV()
        mesh.uv_layers.new('UVMap')
        mesh.uv_layers.new('SecondUV')
        # Set overlapping UVs on the second layer
        mesh.add_polygon(
            [0, 1, 2],
            [(0.0, 0.0), (0.5, 0.0), (0.5, 0.5)],
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
        )
        mesh.add_polygon(
            [3, 4, 5],
            [(0.0, 0.0), (0.5, 0.0), (0.5, 0.5)],
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
        )
        obj = _register_object(bpy, FakeObjectWithUV('NamedLayerObj', mesh))
        result = uvs.detect_overlap({
            'objectId': obj.get('codex_blender_object_id'),
            'uvLayer': 'SecondUV',
        })
        self.assertTrue(result['result']['hasUV'])
        self.assertEqual(result['result']['layer'], 'SecondUV')
        self.assertTrue(result['result']['hasOverlaps'])

    def test_missing_uv_layer_raises(self):
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = _make_overlapping_mesh()
        obj = _register_object(bpy, FakeObjectWithUV('MissingLayerObj', mesh))
        with self.assertRaises(HarnessError) as ctx:
            uvs.detect_overlap({
                'objectId': obj.get('codex_blender_object_id'),
                'uvLayer': 'NonExistent',
            })
        self.assertEqual(ctx.exception.code, 'UV_LAYER_NOT_FOUND')

    def test_missing_uv_layer_raises_on_density(self):
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = _make_unit_square_mesh()
        obj = _register_object(bpy, FakeObjectWithUV('MissingDensityObj', mesh))
        with self.assertRaises(HarnessError) as ctx:
            uvs.measure_texel_density({
                'objectId': obj.get('codex_blender_object_id'),
                'uvLayer': 'Ghost',
                'textureWidth': 512,
                'textureHeight': 512,
            })
        self.assertEqual(ctx.exception.code, 'UV_LAYER_NOT_FOUND')


class TestToleranceBoundary(unittest.TestCase):
    """F2: tolerance must be probed at the boundary, not just far from it."""

    def _make_overlap_with_width(self, overlap_width):
        """Two unit-height quads overlapping by overlap_width in U.
        Both quads stay within tile (0,0) so the tile filter does not
        interfere with the tolerance test."""
        mesh = FakeMeshWithUV()
        mesh.uv_layers.new('UVMap')
        # Quad A: (0,0)-(1,0)-(1,1)-(0,1)
        # Quad B: (1-overlap_width,0)-(0.9999,0)-(0.9999,1)-(1-overlap_width,1)
        # Overlap width = 0.9999 - (1-overlap_width) = overlap_width - 0.0001
        # We want the actual overlap with A to be overlap_width, so B's right
        # edge must be >= 1.0.  But that puts the centroid past 1.0, landing
        # on tile (1,0).  Instead, make B a narrow band entirely inside tile 0:
        #   B left  = 1 - overlap_width - 0.0001
        #   B right = 1 - 0.0001
        # Overlap with A = B right - max(A left, B left) = (1-0.0001) - (1-overlap_width-0.0001) = overlap_width
        left = 1.0 - overlap_width - 0.0001
        right = 1.0 - 0.0001
        mesh.add_polygon(
            [0, 1, 2, 3],
            [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)],
        )
        mesh.add_polygon(
            [4, 5, 6, 7],
            [(left, 0.0), (right, 0.0), (right, 1.0), (left, 1.0)],
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)],
        )
        return mesh

    def test_just_below_tolerance_suppressed(self):
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = self._make_overlap_with_width(0.0099)
        obj = _register_object(bpy, FakeObjectWithUV('BelowTolObj', mesh))
        result = uvs.detect_overlap({
            'objectId': obj.get('codex_blender_object_id'),
            'tolerance': 0.01,
        })
        self.assertFalse(result['result']['hasOverlaps'],
                         'Overlap area 0.0099 must be suppressed at tolerance 0.01')

    def test_just_above_tolerance_reported(self):
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = self._make_overlap_with_width(0.0101)
        obj = _register_object(bpy, FakeObjectWithUV('AboveTolObj', mesh))
        result = uvs.detect_overlap({
            'objectId': obj.get('codex_blender_object_id'),
            'tolerance': 0.01,
        })
        self.assertTrue(result['result']['hasOverlaps'],
                        'Overlap area 0.0101 must be reported at tolerance 0.01')
        self.assertAlmostEqual(result['result']['overlaps'][0]['area'], 0.0101, places=4)


class TestInspectLimitationsUpdated(unittest.TestCase):
    def test_limitations_no_longer_claims_overlap_undetected(self):
        """After this task, uv.inspect must not claim overlap is undetected."""
        bpy = FakeBpy()
        uvs = UVCommands(bpy)
        mesh = _make_unit_square_mesh()
        obj = _register_object(bpy, FakeObjectWithUV('LimObj', mesh))
        result = uvs.inspect({'objectId': obj.get('codex_blender_object_id')})
        limitations = result['result'].get('limitations', [])
        for lim in limitations:
            self.assertNotIn('overlap is not yet detected', lim.lower(),
                             'limitations must not claim overlap detection is missing')


if __name__ == '__main__':
    unittest.main()
