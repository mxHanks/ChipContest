#!/usr/bin/env python3
"""Detached same-timing117 cause probe; original111 evidence stays immutable."""
from pathlib import Path
import hashlib,json,subprocess,sys,time,os,traceback,signal
B=Path.home()/'Desktop/xu-score-optimization-20261102';D=Path.home()/'Desktop';L=B/'mapped-causal-launch-20261105-117';O=B/'mapped-causal-native-20261105-117';EXPECTED={'xu_mapped_causal117.py': '53250772d0d1fd102aa7a8f26abba19df2c607195b77b4ae03aec6c5f90e6886', 'xu_mapped_causal117.c': 'c12e150fe15304aab10929f876343764a451a6979243f587256a992e0d9e0ac6'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(s):
 p=L/'state.tmp';p.write_text(json.dumps(s,sort_keys=True,indent=2)+'\n');os.replace(str(p),str(L/'state.json'))
if len(sys.argv)==1:
 if O.exists():raise ValueError('117 output exists; inspect current native child, never restart on observation timeout')
 L.mkdir(exist_ok=False)
 with(L/'driver.log').open('xb')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('XU_CAUSAL117_STARTED launcher_pid=%d output=%s'%(p.pid,O),flush=True);sys.exit(0)
s=dict(status='RUNNING_NATIVE117_DIAGNOSTIC_NOT_QUALIFIED',qualification='NOT_QUALIFIED',pid=os.getpid(),started_epoch=time.time());save(s);child=None
try:
 helpers=[D/n for n in sorted(EXPECTED)]+[Path(__file__).resolve()];s['helpers_before']={str(p):sha(p)for p in helpers};save(s)
 for name,digest in EXPECTED.items():
  if sha(D/name)!=digest:raise ValueError('117 helper changed: '+name)
 command=[sys.executable,str(D/'xu_mapped_causal117.py'),'--root',str(B/'mapped-task00-public-diagnostic-20261104-111'),'--source',str(D/'xu_mapped_causal117.c'),'--out',str(O)]
 s['command']=command;child=subprocess.Popen(command,stdin=subprocess.DEVNULL,start_new_session=True);s['child_pid']=child.pid;save(s);s['child_returncode']=child.wait()
 if s['child_returncode']:raise ValueError('117 diagnostic failed; original111/raw native117 failure preserved')
 native=json.loads((O/'state.json').read_text());s['native_status']=native['status']
 if native['status']!='NATIVE117_PASSIVE_EVENTS_COLLECTED_NOT_FUNCTIONAL_OR_TIMING_OR_ENERGY_QUALIFIED':raise ValueError('unexpected native117 terminal scope')
 s['status']=native['status']
except BaseException as exc:
 s.update(status='FAIL_NATIVE117_DIAGNOSTIC_NOT_QUALIFIED',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
 if child is not None and child.poll()is None:
  try:os.kill(child.pid,signal.SIGINT);child.wait(timeout=15)
  except BaseException as cleanup:s['cleanup_error']=type(cleanup).__name__+': '+str(cleanup)
 raise
finally:
 try:
  s['helpers_after']={str(p):sha(p)for p in helpers};s['helpers_equal']=s.get('helpers_before')==s['helpers_after']
  if not s['helpers_equal']:s.update(status='FAIL_NATIVE117_DIAGNOSTIC_NOT_QUALIFIED',helper_identity_error='HELPER_CHANGED')
 except BaseException as exc:s.update(status='FAIL_NATIVE117_DIAGNOSTIC_NOT_QUALIFIED',helper_identity_error=type(exc).__name__+': '+str(exc))
 s['finished_epoch']=time.time();save(s)
print('XU_CAUSAL117_TERMINAL',s['status'],flush=True)
