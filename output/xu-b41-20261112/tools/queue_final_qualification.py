"""Run the already prepared timing scope check after gate and power drain."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

R=Path('/tmp/xu-b41-close-20261111-r1')
META=R/'xu-final-qualification-queue.json'
QUAL=R/'xu-workload-qualification-r1.py'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def token(pid):
    try:return (Path('/proc')/str(pid)/'stat').read_text().split()[21]
    except FileNotFoundError:return None

if '--launch' in sys.argv:
    dependencies={str(pid):token(pid) for pid in [156004,160819]}
    assert all(dependencies.values())
    assert not (R/'xu-workload-qualification-20261113-r1').exists()
    meta={'dependencies':dependencies,'qualification_sha256':sha(QUAL),'wrapper_sha256':sha(Path(__file__))}
    with META.open('x') as f:json.dump(meta,f,indent=2)
    with (R/'xu-workload-qualification-r1.log').open('x') as log:
        p=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve())],cwd=str(R),
                           stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    with (R/'xu-final-qualification-controller.json').open('x') as f:json.dump({'pid':p.pid,'metadata_sha256':sha(META)},f,indent=2)
    print('FINAL_TIMING_SCOPE_QUEUED',p.pid,flush=True)
    raise SystemExit(0)

meta=json.loads(META.read_text())
assert sha(QUAL)==meta['qualification_sha256'] and sha(Path(__file__))==meta['wrapper_sha256']
while any(token(pid)==start for pid,start in meta['dependencies'].items()):
    print('WAIT_GATE_AND_POWER_NATURAL_TERMINAL',time.strftime('%F %T'),flush=True)
    time.sleep(15)
assert 'GATE_REMAINING_TWO_FULL12_PASS' in (R/'xu-run-gate-reset-r16.log').read_text()
while True:
    rows=subprocess.check_output(['ps','-u','s4_23usr','-o','pid,comm','--no-headers'],universal_newlines=True).splitlines()
    heavy=[s for s in rows if len(s.split())>1 and s.split()[1].startswith(('simv','fm_shell','pt_shell','dc_shell','common_shell','vcs','vcd2saif'))]
    if not heavy:break
    print('WAIT_ACTUAL_EDA_DRAIN',heavy,flush=True);time.sleep(15)
assert sha(QUAL)==meta['qualification_sha256']
p=subprocess.run([sys.executable,'-B',str(QUAL)],cwd=str(R))
assert p.returncode==0,p.returncode
result=R/'xu-workload-qualification-20261113-r1/result.json'
data=json.loads(result.read_text())
assert data['status']=='PASS_NATIVE_FIXED_BENCHMARK_WORKLOAD_FOUR_SCENARIOS' and len(data['scenarios'])==4
print('FINAL_TIMING_SCOPE_NATIVE_COMPLETE',sha(result),flush=True)
