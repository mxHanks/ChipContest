#!/usr/bin/env python3
"""Launch isolated mapped task00 public diagnosis; expected final private-gate fatal."""
from pathlib import Path
import hashlib,json,subprocess,sys,os,time,traceback,signal
B=Path.home()/'Desktop/xu-score-optimization-20261102'
D=Path.home()/'Desktop'
L=B/'mapped-task00-public-launch-20261104-111'
O=B/'mapped-task00-public-diagnostic-20261104-111'
HELPERS={'xu_build_mapped_task00111.py': '2a740fb35d8f6db7da3295031f4e7e66f1505d30c9ccf030a5cb1862cb8caa6d', 'xu_mapped_task00_vpi111.c': '2403e25ee5ab453d017b6686da89df7553b79bcd89d70ca35be96281d5d8e7c7', 'xu_public_observer111.svh': 'f8dbc36126bc2773c23141bfa85b7cee67403421fcf2a7385343ff3af8b0a4f3'}
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb')as f:
  while True:
   chunk=f.read(1048576)
   if not chunk:break
   h.update(chunk)
 return h.hexdigest()
def save(state):
 p=L/'launch-state.tmp';p.write_text(json.dumps(state,sort_keys=True,indent=2)+'\n');os.replace(str(p),str(L/'launch-state.json'))
if len(sys.argv)==1:
 if O.exists():raise ValueError('111 output already exists; inspect its real state and never restart on observation timeout')
 L.mkdir(exist_ok=False)
 with(L/'driver.log').open('xb')as f:
  process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('XU_MAPPED111_LAUNCHED launcher_pid=%d output=%s'%(process.pid,O),flush=True)
 sys.exit(0)
s=dict(status='RUNNING_LAUNCH_VALIDATION_NOT_QUALIFIED',pid=os.getpid(),started_epoch=time.time(),qualification='NOT_QUALIFIED')
save(s);child=None
try:
 helpers=[D/n for n in sorted(HELPERS)]+[Path(__file__).resolve()]
 s['helpers_before']={str(p):sha(p)for p in helpers};save(s)
 for name,expected in HELPERS.items():
  if sha(D/name)!=expected:raise ValueError('111 helper changed: '+name)
 command=[sys.executable,str(D/'xu_build_mapped_task00111.py'),'--capture',str(B/'s2c-formal-activity12-20261103-23'),'--inventory',str(B/'s2c-pt-macro-pin-inventory-20261103-20/inventory.json'),'--out',str(O),'--run-vcs','/eda/synopsys/vcs/vcs_2020.03-SP2-6/bin/vcs','--mapped',str(B/'s2c-ppa-campaign-20261103-01/s2c/ppa/mapped.v'),'--vendor','/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/verilog/RAMSP1024X16.v','--standard',str(B/'standard-cell-model-private-20261104-90/scc40nll_vhsc40_rvt.v'),'--vpi-include','/eda/synopsys/vcs/vcs_2020.03-SP2-6/include','--preload-proof',str(B/'vpi-vendor-preload-primitive-20261104-105')]
 s.update(status='RUNNING_BUILDER_NOT_QUALIFIED',command=command);save(s)
 child=subprocess.Popen(command,stdin=subprocess.DEVNULL,start_new_session=True)
 s['builder_pid']=child.pid;save(s)
 code=child.wait();s['builder_returncode']=code
 if code:raise ValueError('111 builder failed; original failure/raw child logs are retained')
 actual=json.loads((O/'state.json').read_text());s['builder_terminal_status']=actual['status']
 if actual['status']!='PUBLIC_TASK00_DIAGNOSTIC_COMPLETE_REQUIRED_PRIVATE_GATE_FAILED':raise ValueError('111 unexpected terminal classification')
 s['status']='PUBLIC_TASK00_DIAGNOSTIC_COMPLETE_REQUIRED_PRIVATE_GATE_FAILED'
except BaseException as exc:
 s.update(status='FAIL_PUBLIC_DIAGNOSTIC_NOT_QUALIFIED',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
 if child is not None and child.poll()is None:
  # The builder's SIGINT handler is Python's ordinary KeyboardInterrupt; its
  # EvidenceRun will stop its dedicated native child group and save failure.
  try:os.kill(child.pid,signal.SIGINT);child.wait(timeout=15)
  except BaseException as cleanup:s['builder_cleanup_error']=type(cleanup).__name__+': '+str(cleanup)
 raise
finally:
 try:
  s['helpers_after']={str(p):sha(p)for p in helpers};s['helpers_equal']=s.get('helpers_before')==s['helpers_after']
  if not s['helpers_equal']:s['status']='FAIL_PUBLIC_DIAGNOSTIC_NOT_QUALIFIED';s['helper_identity_error']='HELPER_CHANGED'
 except BaseException as exc:s.update(status='FAIL_PUBLIC_DIAGNOSTIC_NOT_QUALIFIED',helper_identity_error=type(exc).__name__+': '+str(exc))
 s['finished_epoch']=time.time();save(s)
print('XU_MAPPED111_TERMINAL',s['status'],flush=True)
