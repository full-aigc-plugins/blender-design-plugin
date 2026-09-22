"""Optional Rigify adapter status; never installs or enables an extension."""
import json
import sys
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry

status=build_registry(bpy).dispatch('rig.rigify_status',{})['result']
assert status['blenderVersion']==bpy.app.version_string and status['operatorAvailable']==(status['installed'] and status['enabled'])
print('P7_RIGIFY='+json.dumps(status))
