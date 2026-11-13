#!/usr/bin/env python3
"""Serial final GPIO evidence campaign; no retries, EDA, or foreign process changes."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OLD=Path('/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/compliant32-20261113')
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
 q=p.with_suffix('.new');q.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n');q.replace(p)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--base',type=Path,required=True);p.add_argument('--vectors',type=Path,required=True)
 p.add_argument('--out',type=Path,required=True);p.add_argument('--cpu',type=int,required=True)
 a=p.parse_args();a.base=a.base.resolve();a.vectors=a.vectors.resolve();a.out=a.out.resolve()
 a.out.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{a.cpu})
 r=dict(schema='final-production-gpio-serial-campaign-v1',status='RUNNING',stage='WAIT_BASE',started_at=now(),
  supervisor_pid=os.getpid(),cpu_affinity=sorted(os.sched_getaffinity(0)),base=str(a.base),commands={},completed={},
  policy='One pinned CPU; exact base binary replay; no retry/restart; final independent dual-window activity only after functional followups')
 def save():write(a.out/'state.json',r)
 def execute(name,command):
  command=list(map(str,command));r.update(stage=name,active_command=command);r['commands'][name]=command;save()
  with (a.out/(name+'.log')).open('w') as stream:
   child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
   r['active_pid']=child.pid;save();code=child.wait()
  r['completed'][name]=dict(returncode=code,finished_at=now());r['active_pid']=None;save()
  if code:raise RuntimeError(name+' exit '+str(code))
 try:
  save();deadline=time.monotonic()+6*3600
  while True:
   b=json.loads((a.base/'result.json').read_text())
   if b['status']=='PASS':break
   if b['status']=='FAIL':raise ValueError('base functional run failed: '+b.get('error',''))
   if time.monotonic()>deadline:raise TimeoutError('base wait exceeded6h; no process killed')
   time.sleep(5)
  r['base_result_sha256']=sha(a.base/'result.json');save()
  follow=a.out.parents[1]/'gpio-followups-r1'
  execute('FUNCTIONAL_FOLLOWUPS',[sys.executable,'-u','-B',HERE.parent/'run_followups.py','--base',a.base,'--vectors',a.vectors,'--out',follow])
  full=follow/'full12/result.json';fullrun=json.loads(full.read_text())
  if fullrun.get('status')!='PASS' or fullrun.get('outputs')!=304128:raise ValueError('complete12 missing')
  r['cpu_full12']=dict(path=str(full),sha256=sha(full),total_cycles=fullrun['total_cycles'],campaign_cycles=fullrun['campaign_gpio_first_input_to_last_y_cycles']);save()
  profile_dir=a.out/'profile';profile_dir.mkdir()
  execute('XML_INVENTORY',[sys.executable,'-B',HERE/'inventory_from_xml.py','--preflight',ROOT/'build/s3-y32-final/ppa/preflight-r1','--out',profile_dir/'inventory.json'])
  profile=profile_dir/'profile.json'
  execute('SEAL_PROFILE',[sys.executable,'-B',HERE/'activity_profile.py','--baseline-result',a.base/'result.json','--inventory',profile_dir/'inventory.json','--out',profile])
  activity=a.out/'task0-r1'
  execute('ACTIVITY_TASK0',[sys.executable,'-u','-B',HERE/'run_gpio_activity.py','--base',a.base,'--out',activity,'--vectors',a.vectors,'--profile',profile,'--tasks','1','--jobs','1'])
  # Reuse only byte-bound native digital parsers; no old waveform/activity is used.
  native=a.out/'native-tools';native.mkdir()
  rid=json.loads((OLD/'activity-native-reader-r1/identity.json').read_text())
  reader_old=OLD/'activity-native-reader-r1/fst_inventory'
  if sha(reader_old)!=rid['binary_sha256'] or sha(HERE/'fst_inventory.cpp') not in rid['inputs'].values():raise ValueError('native reader drift')
  exporter_old=OLD/'activity-saif-native-build-r2/fst_to_saif';eid=json.loads((OLD/'activity-saif-native-build-r2/result.json').read_text())
  if sha(exporter_old)!=eid['binary_sha256'] or sha(HERE/'fst_to_saif.cpp')!=eid['source_sha256']:raise ValueError('native exporter drift')
  probe_old=OLD/'activity-saif-native-probe-r2/result.json';probe=json.loads(probe_old.read_text())
  if probe['status']!='PASS_NATIVE_FST_SAIF_DIGITAL_PROBE_NOT_POWER_READY' or probe['native_exporter_sha256']!=sha(exporter_old):raise ValueError('native semantic probe drift')
  for origin,name in [(reader_old,'fst_inventory'),(exporter_old,'fst_to_saif'),(OLD/'activity-native-reader-r1/identity.json','reader-identity.json'),(OLD/'activity-saif-native-build-r2/result.json','exporter-build.json'),(probe_old,'exporter-semantic-probe.json')]:shutil.copy2(origin,native/name)
  write(native/'binding.json',dict(reader_source_sha256=sha(HERE/'fst_inventory.cpp'),exporter_source_sha256=sha(HERE/'fst_to_saif.cpp'),files={p.name:sha(p) for p in native.iterdir() if p.is_file()},scope='Tool reuse only; every final waveform independently captured'))
  audit=a.out/'task0-native-audit-r1'
  execute('NATIVE_FST_AUDIT',[sys.executable,'-B',HERE/'check_gpio_fst.py','--run',activity,'--profile',profile,'--native-reader',native/'fst_inventory','--out',audit])
  execute('SAIF_CLEAR',[sys.executable,'-B',HERE/'convert_fst.py','convert','--run',activity,'--audit',audit,'--profile',profile,'--native-exporter',native/'fst_to_saif','--probe-result',native/'exporter-semantic-probe.json','--out',a.out/'task0-saif-clear-r1'])
  gpio_activity=a.out/'task0-gpio-r1'
  execute('ACTIVITY_TASK0_GPIO',[sys.executable,'-u','-B',HERE/'run_gpio_activity.py','--replay-from',activity,'--out',gpio_activity,'--vectors',a.vectors,'--profile',profile,'--tasks','1','--jobs','1','--window','gpio'])
  gpio_audit=a.out/'task0-gpio-native-audit-r1'
  execute('NATIVE_GPIO_FST_AUDIT',[sys.executable,'-B',HERE/'check_gpio_fst.py','--run',gpio_activity,'--profile',profile,'--native-reader',native/'fst_inventory','--out',gpio_audit])
  execute('SAIF_GPIO',[sys.executable,'-B',HERE/'convert_fst.py','convert','--run',gpio_activity,'--audit',gpio_audit,'--profile',profile,'--native-exporter',native/'fst_to_saif','--probe-result',native/'exporter-semantic-probe.json','--out',a.out/'task0-saif-gpio-r1'])
  activity_result=json.loads((activity/'result.json').read_text())
  sample_bytes=sum(item['bytes'] for name,item in activity_result['activity_files'].items() if name.endswith('.fst'))
  available=shutil.disk_usage(a.out).free;projected=int(sample_bytes*12*1.25)
  r['activity_full12_resource_check']=dict(single_task_fst_bytes=sample_bytes,projected_full12_fst_bytes_with25percent_margin=projected,available_bytes=available,minimum_free_reserve_bytes=2*1024**3);save()
  if available>=projected+2*1024**3 and projected<=12*1024**3:
   activity12=a.out/'full12-r1'
   execute('ACTIVITY_FULL12',[sys.executable,'-u','-B',HERE/'run_gpio_activity.py','--replay-from',activity,'--out',activity12,'--vectors',a.vectors,'--profile',profile,'--tasks','12','--jobs','1'])
   observed=json.loads((activity12/'result.json').read_text())['functional']
   for key in ('total_cycles','load_to_y_cycles','campaign_clear_to_last_y_cycles','campaign_gpio_first_input_to_last_y_cycles'):
    if observed[key]!=fullrun[key]:raise ValueError('full12 activity/no-trace cycle identity differs: '+key)
   if observed['layers']!=fullrun['layers']:raise ValueError('full12 activity/no-trace layer evidence differs')
   audit12=a.out/'full12-native-audit-r1'
   execute('NATIVE_FULL12_FST_AUDIT',[sys.executable,'-B',HERE/'check_gpio_fst.py','--run',activity12,'--profile',profile,'--native-reader',native/'fst_inventory','--out',audit12])
   r['activity_full12']=dict(path=str(activity12),result_sha256=sha(activity12/'result.json'),native_audit_sha256=sha(audit12/'result.json'),outputs=observed['outputs'],same_full12_cycles=True);save()
  else:r['activity_full12_resource_check']['skipped']='Projected raw FST exceeds disk policy/reserve; task0 retained'
  r.update(status='PASS_FUNCTIONAL12_AND_DUAL_WINDOW_RTL_ACTIVITY_NOT_POWER_READY',stage='COMPLETE',active_pid=None)
  return 0
 except Exception as e:
  r.update(status='FAIL',error=str(e),traceback=traceback.format_exc());traceback.print_exc();return 1
 finally:r['finished_at']=now();save()
if __name__=='__main__':raise SystemExit(main())
