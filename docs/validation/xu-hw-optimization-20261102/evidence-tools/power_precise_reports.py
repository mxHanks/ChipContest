#!/usr/bin/env python3
"""Repeat the same validated activity/netlists with explicit verbose power units."""
from pathlib import Path
import hashlib,json,os,re,subprocess,time
D=Path.home()/'Desktop';B=D/'xu-hw-optimization-20261102';O=B/'activity-power-exact-01';O.mkdir(exist_ok=False)
lc='/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5';env=dict(os.environ,SYNOPSYS_LC_ROOT=lc);env['PATH']=lc+'/bin:'+env['PATH']
state=dict(status='RUNNING',cases={})
def save():(O/'state.json').write_text(json.dumps(state,sort_keys=True,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
save()
try:
 for name in ['baseline','candidate']:
  here=O/name;here.mkdir();t=(B/'activity-power-02'/name/'power.tcl').read_text()
  t=t.replace('man report_switching_activity > man-report-switching-activity.txt\n','')
  t=t.replace('report_power > power.rpt','report_power -verbose -significant_digits 8 > power-exact.rpt')
  (here/'power.tcl').write_text(t)
  with (here/'pt.log').open('x') as f:r=subprocess.run(['pt_shell','-f','power.tcl'],cwd=str(here),env=env,stdout=f,stderr=subprocess.STDOUT,timeout=600)
  log=(here/'pt.log').read_text(errors='replace');errors=re.findall(r'^Error:.*$',log,re.M)
  if r.returncode or errors or 'XU_ACTIVITY_POWER_PASS' not in log.splitlines():raise ValueError(name+' precise report failed '+str(errors))
  state['cases'][name]=dict(status='PASS',reports={p.name:dict(sha256=sha(p),text=p.read_text(errors='replace')) for p in here.glob('*.rpt')},tcl=dict(sha256=sha(here/'power.tcl'),text=t),log=dict(sha256=sha(here/'pt.log'),text=log));save()
 state['status']='PASS'
except Exception as e:state.update(status='FAIL',error=str(e));raise
finally:save()
print('PRECISE_POWER',sha(O/'state.json'))
