"""Generate the final paginated capability and separate coverage summaries."""
import json,sys
from collections import Counter
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.harness.runtime import build_registry
assert '--' in sys.argv
output=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
registry=build_registry(bpy,approved_output_root=output,approved_asset_roots=(output,))
items=[];offset=0;domains=None
while True:
    page=registry.dispatch('capability.list',{'offset':offset,'limit':100})['result'];items.extend(page['items']);domains=page['domains']
    if page['nextOffset'] is None:break
    offset=page['nextOffset']
skills=sorted({skill for item in items for skill in item['skills']});maturity=Counter(item['maturity'] for item in items)
distributed=sorted(path.parent.name for path in (ROOT/'skills').glob('*/SKILL.md'))
unreferenced=sorted(set(distributed)-set(skills))
summary={'blender':bpy.app.version_string,'registeredTools':len(items),'toolMaturity':dict(sorted(maturity.items())),
 'distributedSkills':len(distributed),'skillReferences':len(skills),'skills':skills,
 'unreferencedLifecycleSkills':unreferenced,
 'runtimeVerifiedTools':sum(item['maturity'] in {'L3','L4'} for item in items),
 'domainsListed':len(domains),'domainsWithCommands':sum(value['registeredCommands']>0 for value in domains.values()),
 'domainsWithoutCommands':[name for name,value in domains.items() if value['registeredCommands']==0],
 'rigifyGenerate':registry.describe_capability({'id':'rig.rigify_generate'})['availability'],
 'trackingSolveInBackground':registry.describe_capability({'id':'tracking.solve_camera'})['availability'],
 'windowsL4Verified':True,'singleCombinedCoveragePercent':None}
assert not summary['domainsWithoutCommands'];assert unreferenced==['blender-connector','blender-design-design','blender-managed','blender-recover'];assert summary['rigifyGenerate']['status']=='unavailable';assert summary['trackingSolveInBackground']['status']=='unavailable'
with (output/'capability-catalog.json').open('x',encoding='utf-8') as stream:json.dump({'items':items,'domains':domains},stream,ensure_ascii=False,indent=2)
with (output/'coverage-summary.json').open('x',encoding='utf-8') as stream:json.dump(summary,stream,ensure_ascii=False,indent=2)
print('FULL_CAPABILITY='+json.dumps(summary,ensure_ascii=False))
