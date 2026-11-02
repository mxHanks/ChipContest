#!/usr/bin/env python3
"""Compact authorized activity-only progress, never credentials."""
import json,os,subprocess,time
from pathlib import Path
b=Path.home()/'Desktop/xu-hw-optimization-20261102'
print('ACTIVITY_STATUS epoch='+str(time.time()))
for folder in ['activity-01','activity-02','activity-power-01','activity-power-02']:
 p=b/folder/'job-state.json'
 if p.exists():
  j=json.loads(p.read_text());print(folder,json.dumps({k:j[k] for k in ['status','stage','error','summary_sha256'] if k in j},sort_keys=True))
  print('CASES',[(k,v.get('status'),v.get('cycles')) for k,v in j.get('cases',{}).items()])
for line in subprocess.check_output(['ps','-u',str(os.getuid()),'-o','pid,etime,time,pcpu,args']).decode().splitlines():
 if any(x in line for x in ['xu-hw-scale-vcd-20261102.py','xu-hw-scale-vcd-buffered-20261102.py','xu-hw-activity-job-v2-20261102.py execute','pt_shell -f power.tcl']):
  print('PROCESS',line)
  pid=line.split()[0]
  for n in [3,4]:
   p=Path('/proc')/pid/'fd'/str(n)
   try:
    dest=os.readlink(str(p))
    if 'activity-' in dest and '.vcd' in dest:print('FD',pid,n,dest,Path('/proc/'+pid+'/fdinfo/'+str(n)).read_text().splitlines()[0])
   except OSError:pass
