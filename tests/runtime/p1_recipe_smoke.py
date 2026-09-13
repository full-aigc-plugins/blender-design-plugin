"""P1 versioned recipes must use the same public registry and remain editable."""
import json, sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

registry=build_registry(bpy)
shell=registry.dispatch('recipe.hard_surface_shell',{'name':'Housing','dimensions':[1.2,.7,.5],
 'wallThickness':.025,'bevelWidth':.015})['result']
housing=bpy.data.objects[shell['shell']['name']]; helper=bpy.data.objects[shell['helper']['name']]
assert [m.type for m in housing.modifiers]==['BOOLEAN','BEVEL']
assert housing.modifiers[0].object is helper and helper.hide_render and not helper.hide_viewport
assert helper.display_type=='WIRE'
assert tuple(round(value,3) for value in housing.dimensions)==(1.2,.7,.5)

spear=registry.dispatch('recipe.spear',{'name':'SingleSpear','length':3.2,'shaftRadius':.025,
 'headLength':.32,'headRadius':.09})['result']
obj=bpy.data.objects['SingleSpear']
assert spear['singleObject'] and obj.type=='MESH'
assert bpy.data.objects.get('SingleSpear__Shaft') is None and bpy.data.objects.get('SingleSpear__Head') is None
assert abs(obj.dimensions.z-3.2)<1e-6 and [m.type for m in obj.modifiers]==['BEVEL']
assert shell['recipeVersion']=='1.0.0' and spear['recipeVersion']=='1.0.0'
print('P1_RECIPES='+json.dumps({'blender':bpy.app.version_string,'checks':['editable_shell','boolean_helper',
 'modifier_order','parameter_dimensions','single_spear_object','recipe_version'],'productionAcceptance':False}))
