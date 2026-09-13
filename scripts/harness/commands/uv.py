"""Topology-bound UV seams, unwrap, packing and diagnostics."""
from ..errors import HarnessError
from ..identity import ObjectResolver
from ..operation_context import OperationContext
from .mesh import TOPOLOGY_VERSION_KEY
from .validation import finite_number


class UVCommands:
    def __init__(self,bpy_module):
        self.bpy=bpy_module; self.objects=ObjectResolver(bpy_module); self.context=OperationContext(bpy_module)

    def _selection(self,arguments):
        selection=arguments.get('selection')
        if not isinstance(selection,dict): raise HarnessError('INVALID_ARGUMENT','selection receipt is required')
        obj=self.objects.resolve({'objectId':selection.get('objectId')},required_type={'MESH'})
        if selection.get('topologyVersion') != int(obj.data.get(TOPOLOGY_VERSION_KEY,0)):
            raise HarnessError('STALE_TOPOLOGY_SELECTION','selection topology version no longer matches the mesh')
        return obj,selection

    def mark_seams(self,arguments):
        obj,selection=self._selection(arguments); edges=selection.get('edges',[])
        if not isinstance(edges,list) or not edges or any(type(i) is not int or not 0<=i<len(obj.data.edges) for i in edges):
            raise HarnessError('INVALID_ARGUMENT','selection must contain valid edges')
        seam=arguments.get('seam',True)
        if type(seam) is not bool: raise HarnessError('INVALID_ARGUMENT','seam must be boolean')
        for index in edges: obj.data.edges[index].use_seam=seam
        obj.data.update()
        return {'changedObjects':[obj.name],'result':self.objects.receipt(obj)|{'edges':edges,'seam':seam}}

    def _select_faces(self,obj,selection):
        import bmesh
        faces=selection.get('faces',[])
        if not isinstance(faces,list) or not faces or any(type(i) is not int for i in faces):
            raise HarnessError('INVALID_ARGUMENT','selection must contain faces')
        bm=bmesh.from_edit_mesh(obj.data); bm.faces.ensure_lookup_table()
        if any(not 0<=i<len(bm.faces) for i in faces): raise HarnessError('INVALID_ARGUMENT','face index is outside mesh')
        for face in bm.faces: face.select=False
        for index in faces: bm.faces[index].select=True
        bmesh.update_edit_mesh(obj.data,loop_triangles=False,destructive=False)

    def unwrap(self,arguments):
        obj,selection=self._selection(arguments); method=str(arguments.get('method','ANGLE_BASED')).upper()
        if method not in {'ANGLE_BASED','CONFORMAL'}: raise HarnessError('INVALID_ARGUMENT','unsupported unwrap method')
        margin=finite_number(arguments.get('margin',.001),'margin',minimum=0)
        with self.context.active_object(obj,mode='EDIT'):
            self._select_faces(obj,selection)
            result=self.bpy.ops.uv.unwrap(method=method,margin=margin)
            if result != {'FINISHED'}: raise HarnessError('OPERATION_FAILED','UV unwrap did not finish')
        return {'changedObjects':[obj.name],'result':self.objects.receipt(obj)|{'method':method}}

    def pack(self,arguments):
        obj,selection=self._selection(arguments); margin=finite_number(arguments.get('margin',.001),'margin',minimum=0)
        with self.context.active_object(obj,mode='EDIT'):
            self._select_faces(obj,selection)
            result=self.bpy.ops.uv.pack_islands(margin=margin)
            if result != {'FINISHED'}: raise HarnessError('OPERATION_FAILED','UV pack did not finish')
        return {'changedObjects':[obj.name],'result':self.objects.receipt(obj)|{'margin':margin}}

    def inspect(self,arguments):
        obj=self.objects.resolve(arguments,required_type={'MESH'}); layer=obj.data.uv_layers.active
        if layer is None:
            return {'changedObjects':[],'result':self.objects.receipt(obj)|{'hasUV':False,'issues':[{'code':'UV_MISSING'}]}}
        outside=[]; degenerate=[]
        for polygon in obj.data.polygons:
            uvs=[layer.data[index].uv for index in polygon.loop_indices]
            if any(value<0 or value>1 for uv in uvs for value in uv): outside.append(polygon.index)
            area=abs(sum(uvs[i].x*uvs[(i+1)%len(uvs)].y-uvs[(i+1)%len(uvs)].x*uvs[i].y for i in range(len(uvs)))/2)
            if area<=1e-12: degenerate.append(polygon.index)
        issues=[]
        if outside: issues.append({'code':'UV_OUT_OF_BOUNDS','faces':outside})
        if degenerate: issues.append({'code':'UV_DEGENERATE','faces':degenerate})
        return {'changedObjects':[],'result':self.objects.receipt(obj)|{'hasUV':True,'layer':layer.name,
            'outOfBoundsFaces':outside,'degenerateFaces':degenerate,'issues':issues,
            'limitations':['UV island overlap is not yet detected']}}
