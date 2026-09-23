"""Foreground VIEW_3D sculpt brush acceptance."""
import json
import sys
import traceback
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)

def run():
 report={'blender':bpy.app.version_string,'background':bpy.app.background}
 try:
  registry=build_registry(bpy);sphere=registry.dispatch('object.create_mesh',{'name':'BrushSurface','primitive':'sphere'})['result']
  obj=bpy.data.objects['BrushSurface'];before=[v.co.copy() for v in obj.data.vertices]
  area=next(a for a in bpy.context.window.screen.areas if a.type=='VIEW_3D');region=next(r for r in area.regions if r.type=='WINDOW');mouse=[region.width/2,region.height/2]
  result=registry.dispatch('sculpt.brush_stroke',{'objectId':sphere['objectId'],'points':[{'location':[0,0,1],'mouse':mouse,'pressure':1,'size':120},
   {'location':[0.08,0,0.98],'mouse':[mouse[0]+8,mouse[1]],'pressure':1,'size':120}]})['result']
  delta=max((v.co-before[v.index]).length for v in obj.data.vertices);assert delta>1e-5,delta
  report|={'result':result,'maxVertexDelta':delta,'passed':True}
 except Exception as exc:  # noqa: BLE001
  report|={'passed':False,'error':{'type':type(exc).__name__,'message':str(exc)}};traceback.print_exc()
 with (output/'acceptance.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
 bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=1)
