"""Typed priority modifier lifecycle in a factory Blender scene."""
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from scripts.harness.runtime import build_registry

registry = build_registry(bpy)
body = registry.dispatch('object.create_mesh', {'name':'Body','primitive':'cube'})['result']
target = registry.dispatch('object.create_mesh', {'name':'Cutter','primitive':'cylinder','location':[0,0,0]})['result']
specs = [
 ('MIRROR', {'use_axis':[True,False,False], 'use_clip':True}),
 ('ARRAY', {'count':2, 'relative_offset_displace':[1.2,0,0]}),
 ('BEVEL', {'width':.05, 'segments':2}),
 ('SUBDIVISION', {'levels':1, 'render_levels':1}),
 ('SOLIDIFY', {'thickness':.1, 'offset':0}),
 ('BOOLEAN', {'operation':'DIFFERENCE', 'solver':'EXACT', 'object':{'objectId':target['objectId']}}),
 ('DECIMATE', {'ratio':.9, 'decimate_type':'COLLAPSE'}),
]
names=[]
for index,(kind,settings) in enumerate(specs):
    result=registry.dispatch('modifier.add', {'objectId':body['objectId'],'modifier':kind,
        'modifierName':f'M{index}_{kind}','settings':settings})['result']; names.append(result['modifierName'])
listed=registry.dispatch('modifier.list', {'objectId':body['objectId']})['result']['modifiers']
assert [m['name'] for m in listed] == names
registry.dispatch('modifier.configure', {'objectId':body['objectId'],'modifierName':names[2],
                                         'settings':{'width':.08,'segments':3}})
registry.dispatch('modifier.move', {'objectId':body['objectId'],'modifierName':names[-1],'targetIndex':0})
registry.dispatch('modifier.set_enabled', {'objectId':body['objectId'],'modifierName':names[1],
                                           'viewport':False,'render':True})
registry.dispatch('modifier.remove', {'objectId':body['objectId'],'modifierName':names[0]})
apply_obj=registry.dispatch('object.create_mesh', {'name':'Apply','primitive':'cube'})['result']
registry.dispatch('modifier.add', {'objectId':apply_obj['objectId'],'modifier':'BEVEL',
                                  'modifierName':'ApplyBevel','settings':{'width':.05,'segments':2}})
before=len(bpy.data.objects['Apply'].data.vertices)
registry.dispatch('modifier.apply', {'objectId':apply_obj['objectId'],'modifierName':'ApplyBevel'})
assert len(bpy.data.objects['Apply'].modifiers)==0 and len(bpy.data.objects['Apply'].data.vertices)>before
print('P1_MODIFIERS='+json.dumps({'blender':bpy.app.version_string,'types':[s[0] for s in specs],
 'checks':['create','list','configure','move','enable','remove','apply'],'productionAcceptance':False}))
