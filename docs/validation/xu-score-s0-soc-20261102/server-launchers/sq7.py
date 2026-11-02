from pathlib import Path
import json,os
O=Path.home()/'Desktop/xu-score-optimization-20261102/full-soc-campaign-02'
for n in ['functional-state.json','ppa-state.json','ppa-ss-01/execution.json']:
 p=O/n
 if p.exists():print('STATE',n,json.dumps({k:v for k,v in json.loads(p.read_text()).items()if k in ['status','stage','error','completed','timing_review']},sort_keys=True))
for n in ['reference4ns-real1/reference/simulation.log','reference4ns-real1/harness/simulation.log','reference4ns-real1/macro/simulation.log','reference4ns-real12/reference/simulation.log','reference4ns-real12/macro/simulation.log','nominal150-real12/reference/simulation.log','nominal150-real12/macro/simulation.log','ppa-ss-01/dc.log','ppa-ss-01/pt-sta.log']:
 p=O/n
 if p.exists():
  lines=p.read_text(errors='replace').splitlines();issues=[x for x in lines if any(y in x for y in ['Error:','FAIL','FATAL','XU_FATAL'])]
  print('LOG',n,'\n'.join(issues[-3:]+lines[-3:]))
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if str(O)in cmd or 's0f.py'in cmd:print('LIVE_PID',p.name,cmd[:230])
 except OSError:pass
