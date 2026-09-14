"""Unit tests for retopo commands: argument validation and production logic."""
import math
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts.harness.errors import HarnessError
from scripts.harness.runtime import build_registry
from tests.test_design_commands import FakeBpy, FakeObject, FakeObjects


# ---------------------------------------------------------------------------
# Argument-validation tests (unchanged from original)
# ---------------------------------------------------------------------------

class PropertyObject(FakeObject):
    def __init__(self, name, object_type='MESH'):
        super().__init__(name, object_type)
        self.properties = {}

    def get(self, key, default=None):
        return self.properties.get(key, default)

    def __setitem__(self, key, value):
        self.properties[key] = value


class RetopoRegistrationTests(unittest.TestCase):
    def test_retopo_commands_are_registered(self):
        registry = build_registry(FakeBpy())
        for cmd in ('retopo.setup_surface', 'retopo.project',
                    'retopo.transfer_layers', 'retopo.validate'):
            result = registry.dispatch('capability.describe', {'id': cmd})
            self.assertEqual(result['result']['id'], cmd)

    def test_retopo_domain_is_known(self):
        registry = build_registry(FakeBpy())
        result = registry.dispatch('capability.list', {'domain': 'retopo'})
        names = [item['id'] for item in result['result']['items']]
        self.assertIn('retopo.setup_surface', names)
        self.assertIn('retopo.project', names)
        self.assertIn('retopo.transfer_layers', names)
        self.assertIn('retopo.validate', names)


class SetupSurfaceArgumentTests(unittest.TestCase):
    def test_requires_sourceObjectId(self):
        registry = build_registry(FakeBpy())
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.setup_surface', {'targetName': 'T'})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_requires_targetName(self):
        bpy = FakeBpy()
        obj = PropertyObject('Source')
        bpy.data.objects['Source'] = obj
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.setup_surface', {'sourceObjectId': {'name': 'Source'}})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_rejects_invalid_symmetry(self):
        bpy = FakeBpy()
        obj = PropertyObject('Source')
        bpy.data.objects['Source'] = obj
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.setup_surface', {
                'sourceObjectId': {'name': 'Source'}, 'targetName': 'T', 'symmetry': 'w'})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')


class ProjectArgumentTests(unittest.TestCase):
    def test_requires_objectId(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        bpy.data.objects['Source'] = src
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.project', {'sourceObjectId': {'name': 'Source'}})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_requires_sourceObjectId(self):
        bpy = FakeBpy()
        tgt = PropertyObject('Target')
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.project', {'objectId': {'name': 'Target'}})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_rejects_invalid_method(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        tgt = PropertyObject('Target')
        bpy.data.objects['Source'] = src
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.project', {
                'objectId': {'name': 'Target'}, 'sourceObjectId': {'name': 'Source'},
                'method': 'invalid'})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')


class TransferLayersArgumentTests(unittest.TestCase):
    def test_requires_layers(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        tgt = PropertyObject('Target')
        bpy.data.objects['Source'] = src
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.transfer_layers', {
                'sourceObjectId': {'name': 'Source'},
                'targetObjectId': {'name': 'Target'}})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_rejects_empty_layers(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        tgt = PropertyObject('Target')
        bpy.data.objects['Source'] = src
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.transfer_layers', {
                'sourceObjectId': {'name': 'Source'},
                'targetObjectId': {'name': 'Target'}, 'layers': []})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_rejects_non_string_layers(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        tgt = PropertyObject('Target')
        bpy.data.objects['Source'] = src
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.transfer_layers', {
                'sourceObjectId': {'name': 'Source'},
                'targetObjectId': {'name': 'Target'}, 'layers': [123]})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')


class ValidateArgumentTests(unittest.TestCase):
    def test_requires_objectId(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        bpy.data.objects['Source'] = src
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.validate', {'sourceObjectId': {'name': 'Source'}})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_requires_sourceObjectId(self):
        bpy = FakeBpy()
        tgt = PropertyObject('Target')
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.validate', {'objectId': {'name': 'Target'}})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_rejects_invalid_maxPoleValence(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        tgt = PropertyObject('Target')
        bpy.data.objects['Source'] = src
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.validate', {
                'objectId': {'name': 'Target'},
                'sourceObjectId': {'name': 'Source'}, 'maxPoleValence': 2})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_rejects_non_integer_maxPoleValence(self):
        bpy = FakeBpy()
        src = PropertyObject('Source')
        tgt = PropertyObject('Target')
        bpy.data.objects['Source'] = src
        bpy.data.objects['Target'] = tgt
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.validate', {
                'objectId': {'name': 'Target'},
                'sourceObjectId': {'name': 'Source'}, 'maxPoleValence': 4.5})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_risk_is_read(self):
        registry = build_registry(FakeBpy())
        caps = registry.capabilities()
        validate_cap = next(c for c in caps if c['command'] == 'retopo.validate')
        self.assertEqual(validate_cap['risk'], 'read')

    def test_source_type_mismatch_rejected(self):
        bpy = FakeBpy()
        src = PropertyObject('Source', 'CAMERA')
        bpy.data.objects['Source'] = src
        registry = build_registry(bpy)
        with self.assertRaises(HarnessError) as ctx:
            registry.dispatch('retopo.validate', {
                'objectId': {'name': 'Source'},
                'sourceObjectId': {'name': 'Source'}})
        self.assertEqual(ctx.exception.code, 'OBJECT_TYPE_MISMATCH')


# ---------------------------------------------------------------------------
# Production-logic tests: fakes with enough structure for RetopoCommands
# ---------------------------------------------------------------------------

class FakeCo:
    """Minimal 3-vector supporting the operations retopo.py uses."""
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def copy(self):
        return FakeCo(self.x, self.y, self.z)

    def __add__(self, other):
        if isinstance(other, (list, tuple)):
            return FakeCo(self.x + other[0], self.y + other[1], self.z + other[2])
        return FakeCo(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return FakeCo(self.x - other.x, self.y - other.y, self.z - other.z)

    def __truediv__(self, scalar):
        return FakeCo(self.x / scalar, self.y / scalar, self.z / scalar)

    def __iadd__(self, vec):
        self.x += vec[0]; self.y += vec[1]; self.z += vec[2]
        return self

    def __getitem__(self, index):
        return (self.x, self.y, self.z)[index]

    def __setitem__(self, index, value):
        if index == 0: self.x = float(value)
        elif index == 1: self.y = float(value)
        elif index == 2: self.z = float(value)

    def __iter__(self):
        yield self.x; yield self.y; yield self.z

    def __repr__(self):
        return f'FakeCo({self.x:.3f}, {self.y:.3f}, {self.z:.3f})'

    @property
    def length(self):
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalize(self):
        L = self.length
        if L > 1e-15:
            self.x /= L; self.y /= L; self.z /= L
        return self

    def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z


class FakeMeshVertex:
    def __init__(self, x, y, z, index=0):
        self.co = FakeCo(x, y, z)
        self.index = index


class FakeMeshPolygon:
    def __init__(self, vertices, index=0):
        self.vertices = vertices
        self.index = index
        self.loop_indices = list(range(len(vertices)))


class FakeMeshData:
    """Mimics bpy.types.Mesh for retopo tests."""
    def __init__(self, vertices=None, polygons=None):
        self._verts = [FakeMeshVertex(*v, index=i) for i, v in enumerate(vertices or [])]
        self._polys = [FakeMeshPolygon(p, index=i) for i, p in enumerate(polygons or [])]
        self.properties = {}
        self.uv_layers = SimpleNamespace(active=None)
        self.color_attributes = FakeColorAttributes()

    @property
    def vertices(self):
        return self._verts

    @property
    def polygons(self):
        return self._polys

    @property
    def edges(self):
        return []

    def get(self, key, default=None):
        return self.properties.get(key, default)

    def __setitem__(self, key, value):
        self.properties[key] = value

    def update(self):
        pass


class FakeColorAttr:
    def __init__(self, name, data_type, domain):
        self.name = name
        self.data_type = data_type
        self.domain = domain
        self.data = [SimpleNamespace(color=[0, 0, 0, 1]) for _ in range(256)]

class FakeColorAttributes(dict):
    def get(self, key, default=None):
        return super().get(key, default)

    def new(self, name, type, domain):
        attr = FakeColorAttr(name, type, domain)
        self[name] = attr
        return attr


class FakeWeightGroup:
    def __init__(self, name, weights=None):
        self.name = name
        self._weights = weights or {}

    def weight(self, index):
        if index not in self._weights:
            raise RuntimeError('no weight')
        return self._weights[index]

    def add(self, indices, weight, mode):
        for i in indices:
            self._weights[i] = weight


class FakeVertexGroups(dict):
    def get(self, key, default=None):
        return super().get(key, default)

    def new(self, name):
        vg = FakeWeightGroup(name)
        self[name] = vg
        return vg


class RetopoObject(FakeObject):
    """Object with mesh data, vertex groups, and color attributes."""
    def __init__(self, name, vertices=None, polygons=None):
        super().__init__(name, 'MESH')
        self.data = FakeMeshData(vertices, polygons)
        self.vertex_groups = FakeVertexGroups()
        self.properties = {}

    def get(self, key, default=None):
        return self.properties.get(key, default)

    def __setitem__(self, key, value):
        self.properties[key] = value


class FakeCollection:
    def __init__(self):
        self.objects_list = []

    def objects(self):
        return self.objects_list

    class _Objects:
        def __init__(self, parent):
            self._parent = parent
        def link(self, obj):
            self._parent.objects_list.append(obj)

    @property
    def objects(self):
        return self._Objects(self)


class _MeshFactory:
    def new(self, name):
        m = FakeMeshData()
        m.name = name
        return m

class _ObjectFactory(FakeObjects):
    def new(self, name, data):
        obj = RetopoObject(name)
        obj.data = data
        self[obj.name] = obj
        return obj

class _RetopoData:
    def __init__(self):
        self.objects = _ObjectFactory()
        self.materials = []
        self.meshes = _MeshFactory()
        self.color_attributes = FakeColorAttributes()

class RetopoFakeBpy:
    """Standalone FakeBpy for retopo production tests (no property conflict)."""
    def __init__(self):
        self.data = _RetopoData()
        self.context = SimpleNamespace(
            object=None,
            scene=SimpleNamespace(
                camera=None, frame_start=1, frame_end=250,
                collection=FakeCollection()
            )
        )
        self.ops = SimpleNamespace()


def _make_fake_bmesh(verts=None, edges=None, faces=None):
    """Build a minimal fake bmesh.new() return value.

    from_mesh populates verts from data.vertices; to_mesh writes back.
    """
    class _EL(list):
        def ensure_lookup_table(self): pass
    bm = SimpleNamespace()
    bm.verts = _EL(verts or [])
    bm.edges = _EL(edges or [])
    bm.faces = _EL(faces or [])
    _pre_set = bool(verts)
    def _from_mesh(data):
        if _pre_set:
            return  # keep pre-set verts (e.g. custom link_edges for pole tests)
        bm.verts.clear()
        for i, v in enumerate(getattr(data, 'vertices', [])):
            bmv = SimpleNamespace(co=FakeCo(v.co.x, v.co.y, v.co.z), index=i,
                                  link_edges=[])
            bm.verts.append(bmv)
    def _to_mesh(data):
        data._verts = [FakeMeshVertex(v.co.x, v.co.y, v.co.z, i)
                       for i, v in enumerate(bm.verts)]
        data._polys = []
    bm.from_mesh = _from_mesh
    bm.to_mesh = _to_mesh
    bm.normal_update = lambda: None
    bm.free = lambda: None
    return bm

def _inject_fake_bmesh(grid_verts=None):
    """Create a fake bmesh module that records create_grid calls."""
    created_verts = []

    class FakeBMVert:
        def __init__(self, x, y, z):
            self.co = FakeCo(x, y, z)
            self.index = len(created_verts)
            created_verts.append(self)

    class _ElementList(list):
        """List subclass with ensure_lookup_table for bmesh compat."""
        def ensure_lookup_table(self):
            pass

    class FakeBMesh:
        def __init__(self):
            self.verts = _ElementList()
            self.edges = _ElementList()
            self.faces = _ElementList()

        def from_mesh(self, mesh_data):
            self.verts.clear()
            for i, v in enumerate(getattr(mesh_data, 'vertices', [])):
                bmv = SimpleNamespace(co=FakeCo(v.co.x, v.co.y, v.co.z), index=i)
                self.verts.append(bmv)

        def to_mesh(self, mesh_data):
            mesh_data._verts = [FakeMeshVertex(v.co.x, v.co.y, v.co.z, i)
                                for i, v in enumerate(self.verts)]
            mesh_data._polys = []

        def normal_update(self):
            pass

        def free(self):
            pass

    def fake_create_grid(bm, x_segments=1, y_segments=1, size=1.0):
        created_verts.clear()
        bm.verts.clear()
        nx, ny = x_segments + 1, y_segments + 1
        for j in range(ny):
            for i in range(nx):
                x = -size + 2 * size * i / x_segments
                y = -size + 2 * size * j / y_segments
                v = FakeBMVert(x, y, 0.0)
                bm.verts.append(v)

    fake_bmesh = SimpleNamespace(
        new=FakeBMesh,
        ops=SimpleNamespace(
            create_grid=fake_create_grid,
            remove_doubles=lambda bm, verts=None, dist=1e-4: None,
        ),
    )
    return fake_bmesh, created_verts


def _inject_fake_mathutils(source_verts):
    """Create a fake mathutils module with a brute-force KDTree."""
    class FakeKDTree:
        def __init__(self, n):
            self._points = []

        def insert(self, co, index):
            self._points.append((list(co), index))

        def balance(self):
            pass

        def find(self, co):
            best_dist = float('inf')
            best_loc = None
            best_idx = None
            for pt, idx in self._points:
                d = math.sqrt(sum((a - b)**2 for a, b in zip(co, pt)))
                if d < best_dist:
                    best_dist = d
                    best_loc = pt
                    best_idx = idx
            return FakeCo(*best_loc) if best_loc is not None else None, best_idx, best_dist

    fake_mathutils = SimpleNamespace(
        kdtree=SimpleNamespace(KDTree=FakeKDTree),
        Vector=lambda args: FakeCo(*args),
    )
    return fake_mathutils


class SetupSurfaceProductionTests(unittest.TestCase):
    """setup_surface must produce real mesh data, not just return a receipt."""

    def test_produces_mesh_object_with_vertices(self):
        bpy = RetopoFakeBpy()
        source = RetopoObject('Source', vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)])
        bpy.data.objects['Source'] = source

        from scripts.harness.commands.retopo import RetopoCommands
        cmds = RetopoCommands(bpy)
        fake_bmesh, created_verts = _inject_fake_bmesh()
        with patch.dict(sys.modules, {'bmesh': fake_bmesh, 'mathutils': SimpleNamespace(
                Vector=lambda args: FakeCo(*args))}):
            result = cmds.setup_surface({
                'sourceObjectId': {'name': 'Source'},
                'targetName': 'RetopoGrid', 'symmetry': 'none', 'offset': 0.05
            })

        obj = bpy.data.objects['RetopoGrid']
        self.assertIsNotNone(obj, 'setup_surface must create a new object')
        self.assertEqual(obj.type, 'MESH')
        self.assertGreater(len(obj.data.vertices), 0, 'mesh must have vertices')
        self.assertIn('limitations', result['result'])
        self.assertTrue(any('starting point' in l.lower() for l in result['result']['limitations']))

    def test_symmetry_x_mirrors_vertices(self):
        """symmetry='x' must actually mirror vertices, not just echo the parameter.

        If _apply_mirror were a no-op the vertex set would remain one-sided
        and the min/max X distances from center.x would differ — this test
        would fail.
        """
        bpy = RetopoFakeBpy()
        # Asymmetric source: center.x = (-2 + 1) / 2 = -0.5
        source = RetopoObject('Source', vertices=[(-2, 0, 0), (1, 0, 0)])
        bpy.data.objects['Source'] = source

        from scripts.harness.commands.retopo import RetopoCommands
        cmds = RetopoCommands(bpy)
        fake_bmesh, created_verts = _inject_fake_bmesh()
        with patch.dict(sys.modules, {'bmesh': fake_bmesh, 'mathutils': SimpleNamespace(
                Vector=lambda args: FakeCo(*args))}):
            result = cmds.setup_surface({
                'sourceObjectId': {'name': 'Source'},
                'targetName': 'MirrorGrid', 'symmetry': 'x', 'offset': 0.1
            })
        self.assertEqual(result['result']['symmetry'], 'x')

        obj = bpy.data.objects['MirrorGrid']
        xs = [v.co.x for v in obj.data.vertices]
        center_x = -0.5  # (-2 + 1) / 2
        # After mirroring about center_x the vertex set must be symmetric:
        # for every x there must be a corresponding 2*center_x - x.
        rounded = sorted(round(x - center_x, 4) for x in xs)
        negated = sorted(round(-(x - center_x), 4) for x in xs)
        self.assertEqual(rounded, negated,
                        'vertex X offsets from center must be symmetric after mirror')


class ProjectProductionTests(unittest.TestCase):
    """project must move target vertices toward the source."""

    def test_project_moves_vertices_closer_to_source(self):
        bpy = RetopoFakeBpy()
        source = RetopoObject('Source', vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)])
        target = RetopoObject('Target', vertices=[(0.5, 0.5, 2.0), (0.2, 0.3, 2.0)])
        bpy.data.objects['Source'] = source
        bpy.data.objects['Target'] = target

        # Record original Z
        original_z = [v.co.z for v in target.data.vertices]

        from scripts.harness.commands.retopo import RetopoCommands
        cmds = RetopoCommands(bpy)
        # source data needs faces for the bmesh face check
        source.data._polys = [FakeMeshPolygon([0, 1, 2]), FakeMeshPolygon([1, 2, 3])]
        fake_mathutils = _inject_fake_mathutils(source.data.vertices)
        fake_bmesh = SimpleNamespace(new=lambda: _make_fake_bmesh(
            faces=[SimpleNamespace() for _ in source.data._polys]))
        # Patch at the module level where retopo.py imports them
        with patch.dict(sys.modules, {'bmesh': fake_bmesh, 'mathutils': fake_mathutils}):
            result = cmds.project({
                'objectId': {'name': 'Target'},
                'sourceObjectId': {'name': 'Source'},
                'method': 'nearest', 'maxDistance': 5.0
            })

        # Vertices should have moved: Z should be closer to 0 (source plane)
        for i, v in enumerate(target.data.vertices):
            self.assertLess(abs(v.co.z), abs(original_z[i]),
                            f'vertex {i} Z should be closer to source plane')

    def test_project_includes_limitations(self):
        bpy = RetopoFakeBpy()
        source = RetopoObject('Source', vertices=[(0, 0, 0)])
        target = RetopoObject('Target', vertices=[(0, 0, 1)])
        bpy.data.objects['Source'] = source
        bpy.data.objects['Target'] = target

        from scripts.harness.commands.retopo import RetopoCommands
        cmds = RetopoCommands(bpy)
        source.data._polys = [FakeMeshPolygon([0])]
        fake_mathutils = _inject_fake_mathutils(source.data.vertices)
        fake_bmesh = SimpleNamespace(new=lambda: _make_fake_bmesh(faces=[SimpleNamespace()]))
        with patch.dict(sys.modules, {'bmesh': fake_bmesh, 'mathutils': fake_mathutils}):
            result = cmds.project({
                'objectId': {'name': 'Target'},
                'sourceObjectId': {'name': 'Source'},
                'method': 'nearest', 'maxDistance': 5.0
            })
        self.assertIn('limitations', result['result'])
        self.assertTrue(any('automatic' in l.lower() for l in result['result']['limitations']))


class TransferLayersProductionTests(unittest.TestCase):
    """transfer_layers must copy a vertex group from source to target."""

    def test_copies_vertex_group_weights(self):
        bpy = RetopoFakeBpy()
        source = RetopoObject('Source', vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)])
        vg = source.vertex_groups.new('WeightA')
        vg.add([0], 0.0, 'REPLACE')
        vg.add([1], 0.5, 'REPLACE')
        vg.add([2], 1.0, 'REPLACE')
        target = RetopoObject('Target', vertices=[(0.01, 0.01, 0), (0.99, 0.01, 0), (0.01, 0.99, 0)])
        bpy.data.objects['Source'] = source
        bpy.data.objects['Target'] = target

        from scripts.harness.commands.retopo import RetopoCommands
        cmds = RetopoCommands(bpy)
        fake_mathutils = _inject_fake_mathutils(source.data.vertices)
        
        with patch.dict(sys.modules, {'mathutils': fake_mathutils}):
            result = cmds.transfer_layers({
                'sourceObjectId': {'name': 'Source'},
                'targetObjectId': {'name': 'Target'},
                'layers': ['WeightA']
            })

        self.assertEqual(len(result['result']['transferred']), 1)
        self.assertEqual(result['result']['transferred'][0]['name'], 'WeightA')
        self.assertEqual(result['result']['transferred'][0]['type'], 'vertex_group')
        self.assertIn('transferMethod', result['result'])
        self.assertEqual(result['result']['transferMethod'], 'nearest_vertex')
        self.assertIn('limitations', result['result'])
        # Verify actual weights were copied
        target_vg = target.vertex_groups.get('WeightA')
        self.assertIsNotNone(target_vg)
        self.assertAlmostEqual(target_vg.weight(0), 0.0, places=2)
        self.assertAlmostEqual(target_vg.weight(1), 0.5, places=2)
        self.assertAlmostEqual(target_vg.weight(2), 1.0, places=2)

    def test_copies_color_attribute(self):
        bpy = RetopoFakeBpy()
        source = RetopoObject('Source', vertices=[(0, 0, 0), (1, 0, 0)])
        ca = source.data.color_attributes.new('MyColor', 'FLOAT_COLOR', 'POINT')
        ca.data[0].color = [1.0, 0.0, 0.0, 1.0]
        ca.data[1].color = [0.0, 1.0, 0.0, 1.0]
        target = RetopoObject('Target', vertices=[(0.01, 0, 0), (0.99, 0, 0)])
        bpy.data.objects['Source'] = source
        bpy.data.objects['Target'] = target

        from scripts.harness.commands.retopo import RetopoCommands
        cmds = RetopoCommands(bpy)
        fake_mathutils = _inject_fake_mathutils(source.data.vertices)
        
        with patch.dict(sys.modules, {'mathutils': fake_mathutils}):
            result = cmds.transfer_layers({
                'sourceObjectId': {'name': 'Source'},
                'targetObjectId': {'name': 'Target'},
                'layers': ['MyColor']
            })

        self.assertEqual(result['result']['transferred'][0]['type'], 'color_attribute')
        target_ca = target.data.color_attributes.get('MyColor')
        self.assertIsNotNone(target_ca)
        self.assertAlmostEqual(target_ca.data[0].color[0], 1.0, places=2)
        self.assertAlmostEqual(target_ca.data[1].color[1], 1.0, places=2)


class ValidateProductionTests(unittest.TestCase):
    """validate must compute deviation and flip to handover past threshold."""

    def test_pass_when_within_thresholds(self):
        bpy = RetopoFakeBpy()
        source = RetopoObject('Source', vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)])
        target = RetopoObject('Target', vertices=[(0.01, 0, 0), (0.99, 0, 0), (0, 1.01, 0)])
        bpy.data.objects['Source'] = source
        bpy.data.objects['Target'] = target

        from scripts.harness.commands.retopo import RetopoCommands
        cmds = RetopoCommands(bpy)
        fake_mathutils = _inject_fake_mathutils(source.data.vertices)
        # Fake bmesh for pole analysis: 3 verts with 2 edges each (valence 2 < 5)
        fake_bm_verts = [SimpleNamespace(link_edges=[1, 2], index=i) for i in range(3)]
        fake_bmesh = SimpleNamespace(new=lambda: _make_fake_bmesh(verts=fake_bm_verts))
        
        with patch.dict(sys.modules, { 'mathutils': fake_mathutils, 'bmesh': fake_bmesh }):
            result = cmds.validate({
                'objectId': {'name': 'Target'},
                'sourceObjectId': {'name': 'Source'},
                'maxDeviation': 1.0, 'maxPoleValence': 5
            })

        self.assertEqual(result['result']['status'], 'pass')
        self.assertFalse(result['result']['handover'])
        self.assertEqual(result['result']['issues'], [])

    def test_handover_when_deviation_exceeded(self):
        bpy = RetopoFakeBpy()
        source = RetopoObject('Source', vertices=[(0, 0, 0)])
        # Target vertex is far from source
        target = RetopoObject('Target', vertices=[(5.0, 5.0, 5.0)])
        bpy.data.objects['Source'] = source
        bpy.data.objects['Target'] = target

        from scripts.harness.commands.retopo import RetopoCommands
        cmds = RetopoCommands(bpy)
        fake_mathutils = _inject_fake_mathutils(source.data.vertices)
        fake_bmesh = SimpleNamespace(new=lambda: _make_fake_bmesh())
        
        with patch.dict(sys.modules, { 'mathutils': fake_mathutils, 'bmesh': fake_bmesh }):
            result = cmds.validate({
                'objectId': {'name': 'Target'},
                'sourceObjectId': {'name': 'Source'},
                'maxDeviation': 0.01, 'maxPoleValence': 100
            })

        self.assertEqual(result['result']['status'], 'handover')
        self.assertTrue(result['result']['handover'])
        self.assertTrue(any(i['code'] == 'DEVIATION_EXCEEDED' for i in result['result']['issues']))
        self.assertIn('handoverReason', result['result'])

    def test_handover_when_pole_valence_exceeded(self):
        bpy = RetopoFakeBpy()
        source = RetopoObject('Source', vertices=[(0, 0, 0)])
        target = RetopoObject('Target', vertices=[(0, 0, 0)])  # same pos, deviation=0
        bpy.data.objects['Source'] = source
        bpy.data.objects['Target'] = target

        from scripts.harness.commands.retopo import RetopoCommands
        cmds = RetopoCommands(bpy)
        fake_mathutils = _inject_fake_mathutils(source.data.vertices)
        # Vertex with valence 6 (> maxPoleValence=4)
        fake_bm_verts = [SimpleNamespace(link_edges=[1, 2, 3, 4, 5, 6], index=0)]
        fake_bmesh = SimpleNamespace(new=lambda: _make_fake_bmesh(verts=fake_bm_verts))
        
        with patch.dict(sys.modules, { 'mathutils': fake_mathutils, 'bmesh': fake_bmesh }):
            result = cmds.validate({
                'objectId': {'name': 'Target'},
                'sourceObjectId': {'name': 'Source'},
                'maxDeviation': 100.0, 'maxPoleValence': 4
            })

        self.assertEqual(result['result']['status'], 'handover')
        self.assertTrue(result['result']['handover'])
        self.assertTrue(any(i['code'] == 'POLE_VALENCE_EXCEEDED' for i in result['result']['issues']))
        self.assertEqual(result['result']['poleCount'], 1)


if __name__ == '__main__':
    unittest.main()
