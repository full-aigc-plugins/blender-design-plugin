"""Curve, join/separate and authorized asset paths in Blender."""
import json, sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
asset_root=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)

def reset(): bpy.ops.wm.read_factory_settings(use_empty=True)
def selected_cube(name):
    bpy.ops.mesh.primitive_cube_add(); obj=bpy.context.object; obj.name=name
    for other in bpy.context.selected_objects: other.select_set(False)
    obj.select_set(True); bpy.context.view_layer.objects.active=obj
    return obj

# Generate deterministic local fixtures with Blender's own exporters.
reset(); selected_cube('ObjFixture'); bpy.ops.wm.obj_export(filepath=str(asset_root/'fixture.obj'),export_selected_objects=True)
reset(); selected_cube('GlbFixture'); bpy.ops.export_scene.gltf(filepath=str(asset_root/'fixture.glb'),export_format='GLB',use_selection=True)
reset(); selected_cube('FbxFixture'); bpy.ops.export_scene.fbx(filepath=str(asset_root/'fixture.fbx'),use_selection=True)
reset(); library_object=selected_cube('LibraryFixture')
bpy.data.libraries.write(str(asset_root/'fixture.blend'),{library_object,library_object.data})

reset(); registry=build_registry(bpy,approved_asset_roots=(asset_root,))
curve=registry.dispatch('curve.create',{'name':'SpearPath','splineType':'BEZIER',
 'points':[[0,0,0],[0,0,2],[1,0,3]],'handleType':'AUTO','bevelDepth':.03,'bevelResolution':2,'resolution':16})['result']
assert len(bpy.data.objects['SpearPath'].data.splines[0].bezier_points)==3
registry.dispatch('curve.configure',{'objectId':curve['objectId'],'bevelDepth':.05})
registry.dispatch('curve.to_mesh',{'objectId':curve['objectId']}); assert bpy.data.objects['SpearPath'].type=='MESH'

for name,x in [('JoinA',0),('JoinB',3)]: selected_cube(name); bpy.context.object.location.x=x
joined=registry.dispatch('object.join',{'objects':[{'name':'JoinA'},{'name':'JoinB'}],'newName':'Joined'})['result']
parts=registry.dispatch('object.separate',{'objectId':joined['objectId'],'method':'LOOSE'})['result']
assert len(parts['created'])==1

formats={}
for filename in ('fixture.obj','fixture.glb','fixture.fbx'):
    result=registry.dispatch('asset.import_file',{'path':str(asset_root/filename)})['result']
    assert result['objects']; formats[Path(filename).suffix]=len(result['objects'])
appended=registry.dispatch('asset.library',{'path':str(asset_root/'fixture.blend'),'dataType':'OBJECT',
                                            'names':['LibraryFixture'],'link':False})['result']
linked=registry.dispatch('asset.library',{'path':str(asset_root/'fixture.blend'),'dataType':'OBJECT',
                                          'names':['LibraryFixture'],'link':True})['result']
assert appended['items'] and linked['items'] and not appended['linked'] and linked['linked']
print('P1_CURVE_ASSET='+json.dumps({'blender':bpy.app.version_string,'formats':formats,
 'checks':['curve_points','handles','profile','to_mesh','join','separate','append','link'],
 'productionAcceptance':False}))
