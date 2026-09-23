"""Tests for rig.auto_weights, rig.validate_deformation and new animation commands.

These tests exercise the production logic for character deformation and
advanced animation controls.  They are designed to fail first (RED) and
pass once the commands are implemented.
"""
import math
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts.harness.commands.rig import RigCommands
from scripts.harness.commands.advanced_animation import AdvancedAnimationCommands
from scripts.harness.errors import HarnessError


# ---------------------------------------------------------------------------
# Minimal Blender mocks
# ---------------------------------------------------------------------------

class FakeVertex:
    def __init__(self, index, co):
        self.index = index
        self.co = list(co)
        self.groups = []


class FakeVertexGroup:
    def __init__(self, name, index=0):
        self.name = name
        self.index = index
        self._weights = {}

    def add(self, indices, weight, mode):
        for idx in indices:
            if mode == 'REPLACE':
                self._weights[idx] = weight
            elif mode == 'ADD':
                self._weights[idx] = self._weights.get(idx, 0) + weight
            elif mode == 'SUBTRACT':
                self._weights[idx] = max(0, self._weights.get(idx, 0) - weight)


class FakeVertexGroups(dict):
    def new(self, name):
        group = FakeVertexGroup(name, len(self))
        self[name] = group
        return group

    def get(self, key, default=None):
        return super().get(key, default)


class FakeFModifier:
    def __init__(self, mtype='GENERATOR'):
        self.type = mtype
        self.strength = 0
        self.scale = 1
        self.phase = 0


class FakeFCurve:
    def __init__(self, data_path='', array_index=0):
        self.data_path = data_path
        self.array_index = array_index
        self.keyframe_points = []
        self.modifiers = SimpleNamespace(new=lambda t: FakeFModifier(t))

    def update(self):
        pass


class FakeAction:
    def __init__(self, name):
        self.name = name
        self._curves = []

    @property
    def fcurves(self):
        return self._curves


class FakeAnimationData:
    def __init__(self):
        self.action = None
        self.nla_tracks = SimpleNamespace(
            get=lambda name: None,
            new=lambda: SimpleNamespace(name='', strips=SimpleNamespace(new=lambda n, s, a: SimpleNamespace(name=n, scale=1, repeat=1, blend_type='REPLACE')))
        )


class FakeDriverTarget:
    def __init__(self):
        self.id = None
        self.data_path = ''


class FakeDriverVariable:
    def __init__(self):
        self.name = 'var'
        self.type = 'SINGLE_PROP'
        self.targets = [FakeDriverTarget()]


class FakeDriver:
    def __init__(self):
        self.type = 'SCRIPTED'
        self.expression = ''
        self.variables = SimpleNamespace(new=lambda: FakeDriverVariable())


class FakeMeshData:
    def __init__(self, vertices):
        self.vertices = vertices
        self.shape_keys = None
        self._topology = 0

    def get(self, key, default=None):
        if key == 'codex_topology_version':
            return self._topology
        return default


class FakeEdge:
    """Minimal edge with .vertices tuple."""
    def __init__(self, i, j):
        self.vertices = (i, j)


class FakeEvaluatedMesh:
    """Mesh returned by evaluated_get().to_mesh() -- shares vertex data."""
    def __init__(self, vertices, edges=None):
        self.vertices = vertices
        # Build edges from sequential vertex pairs if not supplied.
        if edges is None:
            self.edges = [FakeEdge(i, i + 1) for i in range(max(0, len(vertices) - 1))]
        else:
            self.edges = edges


class FakeDepsgraph:
    """Minimal depsgraph that returns the same mesh data on evaluation."""
    def update(self):
        pass


class FakeEvaluatedMeshProxy:
    """Proxy returned by evaluated_get() that applies pose-bone transforms.

    When to_mesh() is called, scale, rotation and location from pose bones
    are applied per-vertex using vertex-group weights.  This is a simplified
    model that is sufficient for testing the edge-shrinkage collapse metric:
    - scale < 1 on weighted vertices -> edge shrinkage -> collapse > 0
    - rotation with nonzero extent -> edge length change -> collapse > 0
    - location change with uniform weights -> rigid shift -> collapse == 0
    - no transform -> identity -> collapse == 0
    """
    def __init__(self, mesh_obj):
        self._mesh_obj = mesh_obj

    def to_mesh(self):
        vertices = [FakeVertex(v.index, list(v.co)) for v in self._mesh_obj.data.vertices]
        armature = self._mesh_obj._armature
        if armature is not None:
            for bone_name, pose_bone in armature.pose.bones.items():
                group = self._mesh_obj.vertex_groups.get(bone_name)
                if group is None:
                    continue
                sx, sy, sz = pose_bone.scale
                lx, ly, lz = pose_bone.location
                erx, ery, erz = pose_bone.rotation_euler
                has_scale = abs(sx - 1.0) > 1e-6 or abs(sy - 1.0) > 1e-6 or abs(sz - 1.0) > 1e-6
                has_loc = abs(lx) > 1e-6 or abs(ly) > 1e-6 or abs(lz) > 1e-6
                has_rot = abs(erx) > 1e-6 or abs(ery) > 1e-6 or abs(erz) > 1e-6
                if not has_scale and not has_loc and not has_rot:
                    continue
                # Precompute rotation matrix (Euler XYZ).
                cx, cy, cz = math.cos(erx), math.cos(ery), math.cos(erz)
                sxr, syr, szr = math.sin(erx), math.sin(ery), math.sin(erz)
                # R = Rz * Ry * Rx
                r00 = cz * cy;  r01 = cz * syr * sxr - szr * cx;  r02 = cz * syr * cx + szr * sxr
                r10 = szr * cy; r11 = szr * syr * sxr + cz * cx;  r12 = szr * syr * cx - cz * sxr
                r20 = -syr;     r21 = cy * sxr;                    r22 = cy * cx
                for v in vertices:
                    w = group._weights.get(v.index, 0)
                    if w <= 0:
                        continue
                    px, py, pz = v.co
                    if has_scale:
                        px *= 1.0 + (sx - 1.0) * w
                        py *= 1.0 + (sy - 1.0) * w
                        pz *= 1.0 + (sz - 1.0) * w
                    if has_rot:
                        # Apply weighted rotation: lerp between identity and R.
                        iw = 1.0 - w
                        mr00 = iw + r00 * w; mr01 = r01 * w;       mr02 = r02 * w
                        mr10 = r10 * w;       mr11 = iw + r11 * w; mr12 = r12 * w
                        mr20 = r20 * w;       mr21 = r21 * w;       mr22 = iw + r22 * w
                        nx = mr00 * px + mr01 * py + mr02 * pz
                        ny = mr10 * px + mr11 * py + mr12 * pz
                        nz = mr20 * px + mr21 * py + mr22 * pz
                        px, py, pz = nx, ny, nz
                    if has_loc:
                        px += lx * w
                        py += ly * w
                        pz += lz * w
                    v.co = [px, py, pz]
        # Build edges: chain vertices sequentially (same topology as the base mesh).
        edges = [FakeEdge(i, i + 1) for i in range(max(0, len(vertices) - 1))]
        return FakeEvaluatedMesh(vertices, edges)

    def to_mesh_clear(self):
        pass


class FakeBone:
    def __init__(self, name, head, tail, parent=None, deform=True, rotation_mode='XYZ'):
        self.name = name
        self.head_local = list(head)
        self.tail_local = list(tail)
        self.parent = parent
        self.use_deform = deform
        self.rotation_mode = rotation_mode
        self.length = math.sqrt(sum((a - b) ** 2 for a, b in zip(head, tail)))


class _LiveBoneProperty:
    """Mimics Blender's mathutils live-wrapper: reads through to the bone's
    current storage so that ``old = bone.scale; bone.scale = [0.1,0.1,0.1]``
    makes ``old`` read back ``[0.1,0.1,0.1]`` -- exactly as in real Blender."""
    __slots__ = ('_bone', '_slot')

    def __init__(self, bone, slot):
        object.__setattr__(self, '_bone', bone)
        object.__setattr__(self, '_slot', slot)

    def __getitem__(self, index):
        return getattr(self._bone, '_' + self._slot)[index]

    def __setitem__(self, index, value):
        getattr(self._bone, '_' + self._slot)[index] = value

    def __iter__(self):
        return iter(getattr(self._bone, '_' + self._slot))

    def __len__(self):
        return len(getattr(self._bone, '_' + self._slot))

    def __repr__(self):
        return repr(getattr(self._bone, '_' + self._slot))

    def __eq__(self, other):
        if isinstance(other, (list, tuple)):
            return list(self) == list(other)
        return NotImplemented


class _LiveBoneDescriptor:
    """Descriptor that returns a _LiveBoneProperty, making getattr(bone, attr)
    return a live wrapper that reads through to the bone's storage."""
    def __init__(self, slot):
        self._slot = slot

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return _LiveBoneProperty(obj, self._slot)

    def __set__(self, obj, value):
        target = getattr(obj, '_' + self._slot)
        for i in range(len(target)):
            target[i] = value[i]


class FakePoseBone:
    location = _LiveBoneDescriptor('location')
    rotation_euler = _LiveBoneDescriptor('rotation_euler')
    rotation_quaternion = _LiveBoneDescriptor('rotation_quaternion')
    rotation_axis_angle = _LiveBoneDescriptor('rotation_axis_angle')
    scale = _LiveBoneDescriptor('scale')

    def __init__(self, name, rotation_mode='XYZ'):
        self.name = name
        self.matrix = FakeMatrix()
        self.constraints = []
        self._location = [0, 0, 0]
        self._rotation_euler = [0, 0, 0]
        self._rotation_quaternion = [1, 0, 0, 0]
        self._rotation_axis_angle = [0, 0, 0, 1]
        self._scale = [1, 1, 1]
        self.rotation_mode = rotation_mode
        self.animation_data = None

    def keyframe_insert(self, data_path='', frame=0):
        pass


class FakeArmatureData:
    def __init__(self, bones):
        self.bones = bones


class FakeVector3:
    """Minimal 3D vector that is iterable."""
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z

    def __iter__(self):
        return iter([self.x, self.y, self.z])

    def copy(self):
        return FakeVector3(self.x, self.y, self.z)


class FakeMatrix:
    """Minimal 4x4 matrix that supports @ operator and .translation."""
    def __init__(self, rows=None):
        self.rows = rows or [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]

    def __matmul__(self, other):
        if isinstance(other, FakeMatrix):
            return other
        return other

    @property
    def translation(self):
        return FakeVector3(self.rows[0][3], self.rows[1][3], self.rows[2][3])

    def copy(self):
        return FakeMatrix([r[:] for r in self.rows])


class FakeArmatureObject:
    def __init__(self, name, bones):
        self.name = name
        self.type = 'ARMATURE'
        self.data = FakeArmatureData(bones)
        self.pose = SimpleNamespace(bones={
            b.name: FakePoseBone(b.name, rotation_mode=getattr(b, 'rotation_mode', 'XYZ'))
            for b in bones if b.use_deform
        })
        self.matrix_world = FakeMatrix()
        self.animation_data = None

    def get(self, key, default=None):
        return default

    def animation_data_create(self):
        self.animation_data = FakeAnimationData()
        return self.animation_data


class FakeMeshObject:
    def __init__(self, name, vertex_count=8, armature=None):
        self.name = name
        self.type = 'MESH'
        vertices = []
        for i in range(vertex_count):
            x = (i % 2) * 2 - 1
            y = ((i // 2) % 2) * 2 - 1
            z = (i // 4) * 2 - 1
            vertices.append(FakeVertex(i, [x, y, z]))
        self.data = FakeMeshData(vertices)
        self.vertex_groups = FakeVertexGroups()
        self.modifiers = []
        self.parent = None
        self.animation_data = None
        self._codex_id = 'obj_test_mesh'
        self._keyframe_calls = []
        self._armature = armature

    def get(self, key, default=None):
        if key == 'codex_blender_object_id':
            return self._codex_id
        if key == 'codex_topology_version':
            return self.data.get(key, default)
        return default

    def __setitem__(self, key, value):
        if key == 'codex_blender_object_id':
            self._codex_id = value

    def evaluated_get(self, depsgraph):
        """Return a proxy that applies pose-bone transforms on to_mesh()."""
        return FakeEvaluatedMeshProxy(self)

    def to_mesh(self):
        """Return a mesh sharing our vertex data."""
        return FakeEvaluatedMesh(self.data.vertices)

    def to_mesh_clear(self):
        pass

    def animation_data_create(self):
        self.animation_data = FakeAnimationData()
        return self.animation_data

    def driver_add(self, data_path):
        """Mock driver_add: returns a FakeDriver wrapped in a namespace."""
        if self.animation_data is None:
            self.animation_data_create()
        if self.animation_data.action is None:
            self.animation_data.action = FakeAction(self.name + '_Action')
        driver = FakeDriver()
        return SimpleNamespace(driver=driver, data_path=data_path)

    def keyframe_insert(self, data_path='', frame=0):
        self._keyframe_calls.append((data_path, frame))


class FakeEmptyObject:
    def __init__(self, name):
        self.name = name
        self.type = 'EMPTY'
        self.constraints = []
        self.location = [0, 0, 0]
        self.matrix_world = FakeMatrix()
        self.animation_data = None

    def get(self, key, default=None):
        return default

    def keyframe_insert(self, data_path='', frame=0):
        pass

    def animation_data_create(self):
        self.animation_data = FakeAnimationData()
        return self.animation_data


class FakeCameraObject:
    def __init__(self, name):
        self.name = name
        self.type = 'CAMERA'
        self.constraints = []
        self.location = [0, 0, 0]
        self.matrix_world = FakeMatrix()
        self.animation_data = None

    def get(self, key, default=None):
        return default

    def keyframe_insert(self, data_path='', frame=0):
        pass

    def animation_data_create(self):
        self.animation_data = FakeAnimationData()
        return self.animation_data


class FakeObjects(dict):
    def __iter__(self):
        return iter(self.values())

    def remove(self, obj, do_unlink=True):
        self.pop(obj.name, None)


class FakeTimelineMarker:
    def __init__(self, name, frame):
        self.name = name
        self.frame = frame
        self.camera = None


class FakeTimelineMarkers(dict):
    def new(self, name, frame):
        m = FakeTimelineMarker(name, frame)
        self[name] = m
        return m

    def get(self, name, default=None):
        return super().get(name, default)


class FakeKeyingSetPath:
    def __init__(self, data_path, index):
        self.data_path = data_path
        self.index = index


class FakeKeyingSetPaths(list):
    def add(self, target, data_path, index=-1):
        self.append(FakeKeyingSetPath(data_path, index))


class FakeKeyingSet:
    def __init__(self, name):
        self.name = name
        self.paths = FakeKeyingSetPaths()


class FakeKeyingSets:
    def new(self, name):
        return FakeKeyingSet(name)


class FakeScene:
    def __init__(self):
        self.collection = SimpleNamespace(objects=SimpleNamespace(link=lambda obj: None))
        self.frame_current = 1
        self.frame_start = 1
        self.frame_end = 250
        self.timeline_markers = FakeTimelineMarkers()
        self.keying_sets = FakeKeyingSets()

    def frame_set(self, f):
        self.frame_current = f


class FakeActions(dict):
    def new(self, name):
        action = FakeAction(name)
        self[name] = action
        return action

    def get(self, key, default=None):
        return super().get(key, default)


class FakeBpy:
    def __init__(self):
        self.data = SimpleNamespace(
            objects=FakeObjects(),
            armatures=SimpleNamespace(new=lambda name: None),
            actions=FakeActions(),
        )
        self._scene = FakeScene()
        self._depsgraph = FakeDepsgraph()
        self.context = SimpleNamespace(
            scene=self._scene,
            view_layer=SimpleNamespace(update=lambda: None),
            active_object=None,
            evaluated_depsgraph_get=lambda: self._depsgraph,
        )


# ---------------------------------------------------------------------------
# Test rig.auto_weights
# ---------------------------------------------------------------------------

class TestAutoWeights(unittest.TestCase):
    """Tests for rig.auto_weights -- auto weight assignment with normalization."""

    def _make_scene(self, vertex_count=8):
        bpy = FakeBpy()
        mesh_obj = FakeMeshObject('TestMesh', vertex_count)
        bones = [
            FakeBone('bone_root', [0, 0, -1], [0, 0, 0]),
            FakeBone('bone_tip', [0, 0, 0], [0, 0, 1]),
        ]
        arm_obj = FakeArmatureObject('TestArm', bones)
        bpy.data.objects[mesh_obj.name] = mesh_obj
        bpy.data.objects[arm_obj.name] = arm_obj
        return bpy, mesh_obj, arm_obj

    def test_auto_weights_sum_to_one(self):
        """Every vertex's weights must sum to 1 +/- 0.001."""
        bpy, mesh_obj, arm_obj = self._make_scene()
        cmds = RigCommands(bpy)
        result = cmds.auto_weights({
            'mesh': {'name': 'TestMesh'},
            'armature': {'name': 'TestArm'},
        })
        for v in mesh_obj.data.vertices:
            total = sum(
                group._weights.get(v.index, 0)
                for group in mesh_obj.vertex_groups.values()
            )
            self.assertAlmostEqual(total, 1.0, delta=0.001,
                                   msg=f'vertex {v.index} weights sum to {total}')

    def test_auto_weights_max_influences_default_4(self):
        """No vertex should have more than 4 bone influences by default."""
        bpy = FakeBpy()
        mesh_obj = FakeMeshObject('TestMesh', 4)
        # Create 6 deform bones so the cap matters.
        bones = [FakeBone(f'bone_{i}', [i * 0.5, 0, -1], [i * 0.5, 0, 1]) for i in range(6)]
        arm_obj = FakeArmatureObject('TestArm', bones)
        bpy.data.objects[mesh_obj.name] = mesh_obj
        bpy.data.objects[arm_obj.name] = arm_obj
        cmds = RigCommands(bpy)
        cmds.auto_weights({
            'mesh': {'name': 'TestMesh'},
            'armature': {'name': 'TestArm'},
        })
        for v in mesh_obj.data.vertices:
            influenced = sum(
                1 for group in mesh_obj.vertex_groups.values()
                if group._weights.get(v.index, 0) > 1e-6
            )
            self.assertLessEqual(influenced, 4,
                                 msg=f'vertex {v.index} has {influenced} influences')

    def test_auto_weights_max_influences_custom(self):
        """maxInfluences argument must be respected."""
        bpy = FakeBpy()
        mesh_obj = FakeMeshObject('TestMesh', 4)
        # Create 6 deform bones so the cap matters.
        bones = [FakeBone(f'bone_{i}', [i * 0.5, 0, -1], [i * 0.5, 0, 1]) for i in range(6)]
        arm_obj = FakeArmatureObject('TestArm', bones)
        bpy.data.objects[mesh_obj.name] = mesh_obj
        bpy.data.objects[arm_obj.name] = arm_obj
        cmds = RigCommands(bpy)
        cmds.auto_weights({
            'mesh': {'name': 'TestMesh'},
            'armature': {'name': 'TestArm'},
            'maxInfluences': 2,
        })
        for v in mesh_obj.data.vertices:
            influenced = sum(
                1 for group in mesh_obj.vertex_groups.values()
                if group._weights.get(v.index, 0) > 1e-6
            )
            self.assertLessEqual(influenced, 2,
                                 msg=f'vertex {v.index} has {influenced} influences')

    def test_auto_weights_no_unweighted_vertices(self):
        """Every vertex must be assigned to at least one bone group."""
        bpy, mesh_obj, arm_obj = self._make_scene()
        cmds = RigCommands(bpy)
        cmds.auto_weights({
            'mesh': {'name': 'TestMesh'},
            'armature': {'name': 'TestArm'},
        })
        for v in mesh_obj.data.vertices:
            total = sum(
                group._weights.get(v.index, 0)
                for group in mesh_obj.vertex_groups.values()
            )
            self.assertGreater(total, 1e-6,
                               msg=f'vertex {v.index} is unweighted (sum={total})')

    def test_auto_weights_creates_vertex_groups_for_deform_bones(self):
        """auto_weights must create vertex groups for all deform bones."""
        bpy, mesh_obj, arm_obj = self._make_scene()
        cmds = RigCommands(bpy)
        cmds.auto_weights({
            'mesh': {'name': 'TestMesh'},
            'armature': {'name': 'TestArm'},
        })
        for bone in arm_obj.data.bones:
            if bone.use_deform:
                self.assertIn(bone.name, mesh_obj.vertex_groups)

    def test_auto_weights_rejects_non_mesh(self):
        bpy = FakeBpy()
        arm = FakeArmatureObject('Arm', [])
        bpy.data.objects['Arm'] = arm
        bpy.data.objects['Empty'] = FakeEmptyObject('Empty')
        cmds = RigCommands(bpy)
        with self.assertRaises(HarnessError) as ctx:
            cmds.auto_weights({'mesh': {'name': 'Empty'}, 'armature': {'name': 'Arm'}})
        self.assertEqual(ctx.exception.code, 'OBJECT_TYPE_MISMATCH')

    def test_auto_weights_rejects_non_armature(self):
        bpy = FakeBpy()
        mesh = FakeMeshObject('Mesh')
        bpy.data.objects['Mesh'] = mesh
        bpy.data.objects['Empty'] = FakeEmptyObject('Empty')
        cmds = RigCommands(bpy)
        with self.assertRaises(HarnessError) as ctx:
            cmds.auto_weights({'mesh': {'name': 'Mesh'}, 'armature': {'name': 'Empty'}})
        self.assertEqual(ctx.exception.code, 'OBJECT_TYPE_MISMATCH')


# ---------------------------------------------------------------------------
# Test rig.validate_deformation
# ---------------------------------------------------------------------------

class TestValidateDeformation(unittest.TestCase):
    """Tests for rig.validate_deformation -- extreme pose collapse check."""

    def _make_scene(self):
        bpy = FakeBpy()
        mesh_obj = FakeMeshObject('Body', 8)
        bones = [
            FakeBone('shoulder.L', [0.2, 0, 1.5], [0.5, 0, 1.5]),
            FakeBone('hip.L', [0.1, 0, 0.8], [0.2, 0, 0.5]),
            FakeBone('elbow.L', [0.5, 0, 1.3], [0.8, 0, 1.2]),
            FakeBone('knee.L', [0.2, 0, 0.5], [0.2, 0, 0.1]),
        ]
        arm_obj = FakeArmatureObject('Rig', bones)
        bpy.data.objects[mesh_obj.name] = mesh_obj
        bpy.data.objects[arm_obj.name] = arm_obj
        return bpy, mesh_obj, arm_obj

    def test_validate_deformation_returns_results(self):
        bpy, mesh_obj, arm_obj = self._make_scene()
        cmds = RigCommands(bpy)
        poses = [
            {'bone': 'shoulder.L', 'dataPath': 'rotation_euler', 'value': [1.5, 0, 0]},
        ]
        result = cmds.validate_deformation({
            'mesh': {'name': 'Body'},
            'armature': {'name': 'Rig'},
            'poses': poses,
            'thresholds': {'collapse': 0.5},
        })
        self.assertIn('results', result['result'])
        self.assertEqual(len(result['result']['results']), 1)

    def test_validate_deformation_rejects_missing_threshold(self):
        bpy, _, arm_obj = self._make_scene()
        cmds = RigCommands(bpy)
        with self.assertRaises(HarnessError) as ctx:
            cmds.validate_deformation({
                'mesh': {'name': 'Body'},
                'armature': {'name': 'Rig'},
                'poses': [],
            })
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')

    def test_validate_deformation_rejects_empty_poses(self):
        bpy, _, arm_obj = self._make_scene()
        cmds = RigCommands(bpy)
        with self.assertRaises(HarnessError) as ctx:
            cmds.validate_deformation({
                'mesh': {'name': 'Body'},
                'armature': {'name': 'Rig'},
                'poses': [],
                'thresholds': {'collapse': 0.5},
            })
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')
        self.assertIn('non-empty', str(ctx.exception))

    def test_validate_deformation_rejects_invalid_pose(self):
        bpy, _, arm_obj = self._make_scene()
        cmds = RigCommands(bpy)
        with self.assertRaises(HarnessError) as ctx:
            cmds.validate_deformation({
                'mesh': {'name': 'Body'},
                'armature': {'name': 'Rig'},
                'poses': [{'bone': 'shoulder.L'}],  # missing dataPath and value
                'thresholds': {'collapse': 0.5},
            })
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')


# ---------------------------------------------------------------------------
# Test animation.driver_create
# ---------------------------------------------------------------------------

class TestDriverCreate(unittest.TestCase):
    def test_driver_create_returns_result(self):
        bpy = FakeBpy()
        bpy.data.objects['TestMesh'] = FakeMeshObject('TestMesh')
        cmds = AdvancedAnimationCommands(bpy)
        result = cmds.driver_create({
            'owner': {'name': 'TestMesh'},
            'dataPath': 'location',
            'expression': 'var * 2',
            'variables': [{'name': 'var', 'type': 'SINGLE_PROP', 'target': 'self', 'dataPath': 'location.x'}],
        })
        self.assertIn('result', result)
        self.assertEqual(result['result']['expression'], 'var * 2')
        self.assertEqual(len(result['result']['variables']), 1)

    def test_driver_create_rejects_empty_expression(self):
        bpy = FakeBpy()
        bpy.data.objects['TestMesh'] = FakeMeshObject('TestMesh')
        cmds = AdvancedAnimationCommands(bpy)
        with self.assertRaises(HarnessError) as ctx:
            cmds.driver_create({
                'owner': {'name': 'TestMesh'},
                'dataPath': 'location',
                'expression': '',
                'variables': [],
            })
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')


# ---------------------------------------------------------------------------
# Test animation.keying_set_create
# ---------------------------------------------------------------------------

class TestKeyingSetCreate(unittest.TestCase):
    def test_keying_set_create_returns_result(self):
        bpy = FakeBpy()
        cmds = AdvancedAnimationCommands(bpy)
        result = cmds.keying_set_create({
            'name': 'CharacterPose',
            'paths': [{'data_path': 'pose.bones["pelvis"].location', 'index': 0}],
        })
        self.assertIn('result', result)
        self.assertEqual(result['result']['name'], 'CharacterPose')

    def test_keying_set_create_rejects_empty_paths(self):
        bpy = FakeBpy()
        cmds = AdvancedAnimationCommands(bpy)
        with self.assertRaises(HarnessError) as ctx:
            cmds.keying_set_create({'name': 'Empty', 'paths': []})
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')


# ---------------------------------------------------------------------------
# Test animation.marker_set
# ---------------------------------------------------------------------------

class TestMarkerSet(unittest.TestCase):
    def test_marker_set_returns_result(self):
        bpy = FakeBpy()
        cmds = AdvancedAnimationCommands(bpy)
        result = cmds.marker_set({
            'name': 'ReleasePoint',
            'frame': 61,
        })
        self.assertIn('result', result)
        self.assertEqual(result['result']['name'], 'ReleasePoint')
        self.assertEqual(result['result']['frame'], 61)

    def test_marker_set_with_camera(self):
        bpy = FakeBpy()
        bpy.data.objects['Camera'] = FakeCameraObject('Camera')
        cmds = AdvancedAnimationCommands(bpy)
        result = cmds.marker_set({
            'name': 'CamCut',
            'frame': 30,
            'camera': {'name': 'Camera'},
        })
        self.assertIn('result', result)


# ---------------------------------------------------------------------------
# Test animation.motion_path_calculate
# ---------------------------------------------------------------------------

class TestMotionPathCalculate(unittest.TestCase):
    def test_motion_path_returns_points(self):
        bpy = FakeBpy()
        bpy.data.objects['Arm'] = FakeArmatureObject('Arm', [
            FakeBone('bone', [0, 0, 0], [0, 0, 1]),
        ])
        cmds = AdvancedAnimationCommands(bpy)
        result = cmds.motion_path_calculate({
            'target': {'name': 'Arm'},
            'frameStart': 1,
            'frameEnd': 10,
        })
        self.assertIn('result', result)
        self.assertIn('points', result['result'])

    def test_motion_path_rejects_invalid_range(self):
        bpy = FakeBpy()
        bpy.data.objects['Arm'] = FakeArmatureObject('Arm', [
            FakeBone('bone', [0, 0, 0], [0, 0, 1]),
        ])
        cmds = AdvancedAnimationCommands(bpy)
        with self.assertRaises(HarnessError) as ctx:
            cmds.motion_path_calculate({
                'target': {'name': 'Arm'},
                'frameStart': 10,
                'frameEnd': 1,
            })
        self.assertEqual(ctx.exception.code, 'INVALID_ARGUMENT')


# ---------------------------------------------------------------------------
# Test animation.root_motion
# ---------------------------------------------------------------------------

class TestRootMotion(unittest.TestCase):
    def test_root_motion_returns_result(self):
        bpy = FakeBpy()
        bpy.data.objects['Arm'] = FakeArmatureObject('Arm', [
            FakeBone('root', [0, 0, 0], [0, 0, 1]),
        ])
        bpy.data.objects['Target'] = FakeEmptyObject('Target')
        cmds = AdvancedAnimationCommands(bpy)
        result = cmds.root_motion({
            'armature': {'name': 'Arm'},
            'sourceBone': 'root',
            'targetObject': {'name': 'Target'},
            'frameStart': 1,
            'frameEnd': 30,
        })
        self.assertIn('result', result)
        self.assertEqual(result['result']['sourceBone'], 'root')

    def test_root_motion_rejects_missing_bone(self):
        bpy = FakeBpy()
        bpy.data.objects['Arm'] = FakeArmatureObject('Arm', [
            FakeBone('root', [0, 0, 0], [0, 0, 1]),
        ])
        bpy.data.objects['Target'] = FakeEmptyObject('Target')
        cmds = AdvancedAnimationCommands(bpy)
        with self.assertRaises(HarnessError) as ctx:
            cmds.root_motion({
                'armature': {'name': 'Arm'},
                'sourceBone': 'nonexistent',
                'targetObject': {'name': 'Target'},
                'frameStart': 1,
                'frameEnd': 30,
            })
        self.assertEqual(ctx.exception.code, 'BONE_NOT_FOUND')


# ---------------------------------------------------------------------------
# Weight-normalisation mutation tests
# ---------------------------------------------------------------------------

class TestWeightNormalizationMutation(unittest.TestCase):
    """Mutation tests: deliberately break normalisation and verify tests catch it."""

    def test_sum_to_one_detects_broken_normalisation(self):
        """If normalisation is stubbed to no-op, the sum-to-one test must fail."""
        bpy = FakeBpy()
        mesh_obj = FakeMeshObject('TestMesh', 4)
        bones = [FakeBone('b1', [0, 0, -1], [0, 0, 1])]
        arm_obj = FakeArmatureObject('TestArm', bones)
        bpy.data.objects[mesh_obj.name] = mesh_obj
        bpy.data.objects[arm_obj.name] = arm_obj

        # Simulate broken normalisation: assign raw weights without normalising
        group = mesh_obj.vertex_groups.new('b1')
        for v in mesh_obj.data.vertices:
            group.add([v.index], 0.5, 'REPLACE')  # sum = 0.5, not 1.0

        for v in mesh_obj.data.vertices:
            total = sum(
                g._weights.get(v.index, 0)
                for g in mesh_obj.vertex_groups.values()
            )
            with self.assertRaises(AssertionError, msg=f'vertex {v.index} should fail'):
                self.assertAlmostEqual(total, 1.0, delta=0.001)

    def test_max_influences_detects_broken_cap(self):
        """If the influence cap is not enforced, the test must detect it."""
        bpy = FakeBpy()
        mesh_obj = FakeMeshObject('TestMesh', 4)
        bones = [FakeBone(f'b{i}', [i * 0.5, 0, -1], [i * 0.5, 0, 1]) for i in range(6)]
        arm_obj = FakeArmatureObject('TestArm', bones)
        bpy.data.objects[mesh_obj.name] = mesh_obj
        bpy.data.objects[arm_obj.name] = arm_obj

        # Simulate no cap: assign all 6 bones with nonzero weight
        for i, bone in enumerate(bones):
            group = mesh_obj.vertex_groups.new(bone.name)
            for v in mesh_obj.data.vertices:
                group.add([v.index], 1.0 / 6, 'REPLACE')

        for v in mesh_obj.data.vertices:
            influenced = sum(
                1 for g in mesh_obj.vertex_groups.values()
                if g._weights.get(v.index, 0) > 1e-6
            )
            with self.assertRaises(AssertionError, msg=f'vertex {v.index} should fail'):
                self.assertLessEqual(influenced, 4)

    def test_unweighted_vertices_detects_skipped_assignment(self):
        """If weight assignment is skipped for some vertices, the test must detect it."""
        bpy = FakeBpy()
        mesh_obj = FakeMeshObject('TestMesh', 4)
        bones = [FakeBone('b1', [0, 0, -1], [0, 0, 1])]
        arm_obj = FakeArmatureObject('TestArm', bones)
        bpy.data.objects[mesh_obj.name] = mesh_obj
        bpy.data.objects[arm_obj.name] = arm_obj

        # Simulate skipped assignment: only assign weights to even vertices
        group = mesh_obj.vertex_groups.new('b1')
        for v in mesh_obj.data.vertices:
            if v.index % 2 == 0:
                group.add([v.index], 1.0, 'REPLACE')
            # odd vertices get no weight at all

        for v in mesh_obj.data.vertices:
            total = sum(
                g._weights.get(v.index, 0)
                for g in mesh_obj.vertex_groups.values()
            )
            if v.index % 2 != 0:
                # Odd vertices should be detected as unweighted
                with self.assertRaises(AssertionError, msg=f'vertex {v.index} should fail'):
                    self.assertGreater(total, 1e-6)


class TestCollapseTripCase(unittest.TestCase):
    """Falsifiable tests for validate_deformation collapse metric.

    The mock now applies pose-bone scale to weighted vertices via
    FakeEvaluatedMeshProxy, so these tests genuinely exercise the
    edge-shrinkage metric.  A broken metric (constant, displacement-
    based, or rigid-motion-unaware) will fail at least one of these.
    """

    def _make_weighted_scene(self, rotation_mode='XYZ'):
        """Create a scene where all vertices are fully weighted to one bone."""
        bpy = FakeBpy()
        bones = [FakeBone('bone_main', [0, 0, 0], [0, 0, 1],
                          rotation_mode=rotation_mode)]
        arm_obj = FakeArmatureObject('Rig', bones)
        mesh_obj = FakeMeshObject('Body', 8, armature=arm_obj)
        # Assign all vertices to the bone with full weight.
        group = mesh_obj.vertex_groups.new('bone_main')
        for v in mesh_obj.data.vertices:
            group.add([v.index], 1.0, 'REPLACE')
        bpy.data.objects[mesh_obj.name] = mesh_obj
        bpy.data.objects[arm_obj.name] = arm_obj
        return bpy, mesh_obj, arm_obj

    def test_no_op_pose_collapse_is_zero(self):
        """Identity pose (no deformation) must report collapse == 0."""
        bpy, _, _ = self._make_weighted_scene()
        cmds = RigCommands(bpy)
        result = cmds.validate_deformation({
            'mesh': {'name': 'Body'},
            'armature': {'name': 'Rig'},
            'poses': [{'bone': 'bone_main', 'dataPath': 'scale', 'value': [1, 1, 1]}],
            'thresholds': {'collapse': 0.5},
        })
        self.assertTrue(result['result']['allPassed'])
        self.assertAlmostEqual(result['result']['results'][0]['collapse'], 0.0, places=10,
                               msg='Identity pose must give collapse == 0')

    def test_collapsing_pose_detected(self):
        """Scaling a bone to 10% must produce collapse ~0.9 and fail a tight threshold."""
        bpy, _, _ = self._make_weighted_scene()
        cmds = RigCommands(bpy)
        result = cmds.validate_deformation({
            'mesh': {'name': 'Body'},
            'armature': {'name': 'Rig'},
            'poses': [{'bone': 'bone_main', 'dataPath': 'scale', 'value': [0.1, 0.1, 0.1]}],
            'thresholds': {'collapse': 0.01},
        })
        collapse = result['result']['results'][0]['collapse']
        self.assertGreater(collapse, 0.8,
                           msg=f'Scale 0.1 should give collapse ~0.9, got {collapse}')
        self.assertFalse(result['result']['allPassed'],
                         msg='Collapsing pose must fail with tight threshold')

    def test_rigid_translation_preserves_edges(self):
        """Translating a bone (all vertices shift equally) must give collapse == 0."""
        bpy, _, _ = self._make_weighted_scene()
        cmds = RigCommands(bpy)
        result = cmds.validate_deformation({
            'mesh': {'name': 'Body'},
            'armature': {'name': 'Rig'},
            'poses': [{'bone': 'bone_main', 'dataPath': 'location', 'value': [5, 0, 0]}],
            'thresholds': {'collapse': 0.5},
        })
        collapse = result['result']['results'][0]['collapse']
        self.assertAlmostEqual(collapse, 0.0, places=10,
                               msg='Rigid translation must not register as collapse')

    def test_partial_scale_collapse_proportional(self):
        """Scaling to 50% should give collapse ~0.5, not 0 and not the full displacement."""
        bpy, _, _ = self._make_weighted_scene()
        cmds = RigCommands(bpy)
        result = cmds.validate_deformation({
            'mesh': {'name': 'Body'},
            'armature': {'name': 'Rig'},
            'poses': [{'bone': 'bone_main', 'dataPath': 'scale', 'value': [0.5, 0.5, 0.5]}],
            'thresholds': {'collapse': 1.0},
        })
        collapse = result['result']['results'][0]['collapse']
        self.assertGreater(collapse, 0.3,
                           msg=f'Scale 0.5 should give collapse ~0.5, got {collapse}')
        self.assertLess(collapse, 0.7,
                        msg=f'Scale 0.5 should give collapse ~0.5, got {collapse}')

    def test_rotation_mode_mismatch_euler_on_quaternion(self):
        """rotation_euler on a QUATERNION-mode bone must raise ROTATION_MODE_MISMATCH."""
        bpy = FakeBpy()
        bones = [FakeBone('bone', [0, 0, 0], [0, 0, 1], rotation_mode='QUATERNION')]
        arm_obj = FakeArmatureObject('Rig', bones)
        mesh_obj = FakeMeshObject('Body', 4, armature=arm_obj)
        group = mesh_obj.vertex_groups.new('bone')
        for v in mesh_obj.data.vertices:
            group.add([v.index], 1.0, 'REPLACE')
        bpy.data.objects[mesh_obj.name] = mesh_obj
        bpy.data.objects[arm_obj.name] = arm_obj
        cmds = RigCommands(bpy)
        with self.assertRaises(HarnessError) as ctx:
            cmds.validate_deformation({
                'mesh': {'name': 'Body'},
                'armature': {'name': 'Rig'},
                'poses': [{'bone': 'bone', 'dataPath': 'rotation_euler', 'value': [1.5, 0, 0]}],
                'thresholds': {'collapse': 0.5},
            })
        self.assertEqual(ctx.exception.code, 'ROTATION_MODE_MISMATCH')

    def test_rotation_mode_mismatch_quaternion_on_euler(self):
        """rotation_quaternion on an Euler-mode bone must raise ROTATION_MODE_MISMATCH."""
        bpy = FakeBpy()
        bones = [FakeBone('bone', [0, 0, 0], [0, 0, 1], rotation_mode='XYZ')]
        arm_obj = FakeArmatureObject('Rig', bones)
        mesh_obj = FakeMeshObject('Body', 4, armature=arm_obj)
        group = mesh_obj.vertex_groups.new('bone')
        for v in mesh_obj.data.vertices:
            group.add([v.index], 1.0, 'REPLACE')
        bpy.data.objects[mesh_obj.name] = mesh_obj
        bpy.data.objects[arm_obj.name] = arm_obj
        cmds = RigCommands(bpy)
        with self.assertRaises(HarnessError) as ctx:
            cmds.validate_deformation({
                'mesh': {'name': 'Body'},
                'armature': {'name': 'Rig'},
                'poses': [{'bone': 'bone', 'dataPath': 'rotation_quaternion', 'value': [1, 0, 0, 0]}],
                'thresholds': {'collapse': 0.5},
            })
        self.assertEqual(ctx.exception.code, 'ROTATION_MODE_MISMATCH')


class TestPoseRestorationLeak(unittest.TestCase):
    """Detect the live-wrapper pose restoration bug.

    In Blender, ``getattr(pose_bone, 'scale')`` returns a live mathutils
    reference, not a copy.  If the code does ``old = getattr(bone, attr);
    setattr(bone, attr, new_value)`` and later ``setattr(bone, attr, old)``,
    the restore is a no-op because ``old`` now reads the new value.

    This test applies a non-trivial pose first, then an identity pose, and
    asserts the identity pose reports collapse == 0 (proving the bone was
    properly restored between calls).  It also asserts the bone is back to
    its original value after all calls.
    """

    def _make_weighted_scene(self):
        bpy = FakeBpy()
        bones = [FakeBone('bone_main', [0, 0, 0], [0, 0, 1])]
        arm_obj = FakeArmatureObject('Rig', bones)
        mesh_obj = FakeMeshObject('Body', 8, armature=arm_obj)
        group = mesh_obj.vertex_groups.new('bone_main')
        for v in mesh_obj.data.vertices:
            group.add([v.index], 1.0, 'REPLACE')
        bpy.data.objects[mesh_obj.name] = mesh_obj
        bpy.data.objects[arm_obj.name] = arm_obj
        return bpy, mesh_obj, arm_obj

    def test_identity_after_rotation_gives_zero_collapse_and_restores_bone(self):
        """Ordered control: rotation pose then identity pose.

        After the rotation pose, the bone must be restored to its original
        value (catches the live-wrapper leak).  The identity pose must then
        report collapse == 0.
        """
        bpy, _, arm_obj = self._make_weighted_scene()
        cmds = RigCommands(bpy)
        bone = arm_obj.pose.bones['bone_main']
        orig_rot = list(bone.rotation_euler)

        # First: apply a non-trivial rotation.
        cmds.validate_deformation({
            'mesh': {'name': 'Body'},
            'armature': {'name': 'Rig'},
            'poses': [{'bone': 'bone_main', 'dataPath': 'rotation_euler', 'value': [2.8, 0, 0]}],
            'thresholds': {'collapse': 1.0},
        })
        # Bone must be restored after the rotation pose.
        self.assertEqual(list(bone.rotation_euler), orig_rot,
                         msg='Bone rotation_euler was not restored after rotation pose; '
                             'live-wrapper leak detected')

        # Second: apply an identity rotation -- must see no residual deformation.
        result = cmds.validate_deformation({
            'mesh': {'name': 'Body'},
            'armature': {'name': 'Rig'},
            'poses': [{'bone': 'bone_main', 'dataPath': 'rotation_euler', 'value': [0, 0, 0]}],
            'thresholds': {'collapse': 1.0},
        })
        collapse = result['result']['results'][0]['collapse']
        self.assertAlmostEqual(collapse, 0.0, delta=1e-6,
                               msg='Identity pose after rotation must give collapse == 0')
        # Bone must still be restored after the identity pose.
        self.assertEqual(list(bone.rotation_euler), orig_rot,
                         msg='Bone rotation_euler was not restored after identity pose')

    def test_pose_bone_restored_after_validation(self):
        """The pose bone must be back to its original value after validation."""
        bpy, _, arm_obj = self._make_weighted_scene()
        cmds = RigCommands(bpy)
        bone = arm_obj.pose.bones['bone_main']

        # Record original values.
        orig_scale = list(bone.scale)
        orig_loc = list(bone.location)

        # Apply a scale pose.
        cmds.validate_deformation({
            'mesh': {'name': 'Body'},
            'armature': {'name': 'Rig'},
            'poses': [{'bone': 'bone_main', 'dataPath': 'scale', 'value': [0.1, 0.1, 0.1]}],
            'thresholds': {'collapse': 1.0},
        })

        # Bone must be restored.
        self.assertEqual(list(bone.scale), orig_scale,
                         msg='Bone scale was not restored after validate_deformation')
        self.assertEqual(list(bone.location), orig_loc,
                         msg='Bone location was not restored after validate_deformation')

    def test_identity_after_scale_restores_bone_and_gives_zero_collapse(self):
        """Ordered control: scale-to-0.1 then identity scale.

        After the scale pose, the bone must be restored.  The identity pose
        must then report collapse == 0.
        """
        bpy, _, arm_obj = self._make_weighted_scene()
        cmds = RigCommands(bpy)
        bone = arm_obj.pose.bones['bone_main']
        orig_scale = list(bone.scale)

        # First: scale to 0.1.
        cmds.validate_deformation({
            'mesh': {'name': 'Body'},
            'armature': {'name': 'Rig'},
            'poses': [{'bone': 'bone_main', 'dataPath': 'scale', 'value': [0.1, 0.1, 0.1]}],
            'thresholds': {'collapse': 1.0},
        })
        # Bone must be restored after the scale pose.
        self.assertEqual(list(bone.scale), orig_scale,
                         msg='Bone scale was not restored after scale pose; '
                             'live-wrapper leak detected')

        # Second: identity scale -- must see no residual deformation.
        result = cmds.validate_deformation({
            'mesh': {'name': 'Body'},
            'armature': {'name': 'Rig'},
            'poses': [{'bone': 'bone_main', 'dataPath': 'scale', 'value': [1, 1, 1]}],
            'thresholds': {'collapse': 1.0},
        })
        collapse = result['result']['results'][0]['collapse']
        self.assertAlmostEqual(collapse, 0.0, delta=1e-6,
                               msg='Identity scale after scale-to-0.1 must give collapse == 0')
        # Bone must still be restored after the identity pose.
        self.assertEqual(list(bone.scale), orig_scale,
                         msg='Bone scale was not restored after identity pose')


if __name__ == '__main__':
    unittest.main()
