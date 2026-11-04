#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,subprocess,sys,time,os,traceback
B=Path.home()/'Desktop/xu-score-optimization-20261102';T=Path.home()/'Desktop/xu_audit_mapped111_failure115.py';L=B/'mapped-task00-audit-launch-20261105-115';O=B/'mapped-task00-readonly-audit-20261105-115';EXPECTED='ae88d67e1938c3cc7d2b3be5f3c0dff78b4afb6122a9d2b8a1462cc4a9028b21'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(s):
 p=L/'state.tmp';p.write_text(json.dumps(s,sort_keys=True,indent=2)+'\n');os.replace(str(p),str(L/'state.json'))
if len(sys.argv)==1:
 if O.exists():raise ValueError('115 audit output exists; inspect state; do not restart')
 L.mkdir(exist_ok=False)
 with(L/'driver.log').open('xb')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('XU_AUDIT115_STARTED',p.pid,flush=True);sys.exit(0)
s=dict(status='RUNNING_READONLY_AUDIT_NOT_QUALIFIED',pid=os.getpid(),started_epoch=time.time(),qualification='NOT_QUALIFIED');save(s)
try:
 s['helpers_before']={str(p):sha(p)for p in [T,Path(__file__).resolve()]};save(s)
 if sha(T)!=EXPECTED:raise ValueError('115 helper changed')
 command=[sys.executable,str(T),'--root',str(B/'mapped-task00-public-diagnostic-20261104-111'),'--out',str(O)];s['command']=command
 child=subprocess.Popen(command,stdin=subprocess.DEVNULL);s['child_pid']=child.pid;save(s);s['child_returncode']=child.wait()
 if s['child_returncode']:raise ValueError('actual115 read-only audit failed; original111 untouched')
 native=json.loads((O/'state.json').read_text());s['audit_status']=native['status']
 if native['status']!='AUDITED_ACTUAL111_NATIVE_UNKNOWN_SHARED_HANDSHAKE_FAILURE_NOT_QUALIFIED':raise ValueError('unexpected read-only classification')
 s['status']=native['status']
except BaseException as exc:s.update(status='FAIL_READONLY_AUDIT_NOT_QUALIFIED',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc());raise
finally:
 try:
  s['helpers_after']={str(p):sha(p)for p in [T,Path(__file__).resolve()]};s['helpers_equal']=s['helpers_before']==s['helpers_after']
  if not s['helpers_equal']:s.update(status='FAIL_READONLY_AUDIT_NOT_QUALIFIED',helper_identity_error='HELPER_CHANGED')
 except BaseException as exc:s.update(status='FAIL_READONLY_AUDIT_NOT_QUALIFIED',helper_identity_error=type(exc).__name__+': '+str(exc))
 s['finished_epoch']=time.time();save(s)
print('XU_AUDIT115_TERMINAL',s['status'],flush=True)
