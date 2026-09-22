"""Opt-in foreground Connector lifecycle test; no installation or preference writes."""
import argparse
import sys
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from connector.codex_blender_connector import runtime
from scripts.harness.execution_policy import ExecutionPolicy

parser=argparse.ArgumentParser()
parser.add_argument('--output-root',required=True)
parser.add_argument('--runtime-dir',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
runtime.start(bpy,session_id='connector-policy-smoke',runtime_dir=Path(args.runtime_dir),
              approved_output_root=Path(args.output_root),
              execution_policy=ExecutionPolicy.auto_with_budget(args.output_root,False,None))
bpy.app.handlers.quit_pre.append(lambda _:runtime.stop())
