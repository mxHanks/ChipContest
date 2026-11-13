"""Review the third sealed gate without occupying the EDA slot."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

R=Path('/tmp/xu-b41-close-20261111-r1')
VARIANT='backoff_8_256_fast4-O2'
REVIEWER=R/'xu-review-gate-full12-r3.py'
REVIEWER_SHA='500221eb850b894f1d6ed5d58c51ebbd780bb8c2418c6e3b6dda709bcf8e79e8'
META=R/'xu-backoff-review-r3-queue.json'
BINDING=R/'xu-gate-20261112-r1'/(VARIANT+'-full12-r15')/'verified-binding.json'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def token():
    try:return Path('/proc/156004/stat').read_text().split()[21]
    except FileNotFoundError:return None
def sealed():
    try:
        b=json.loads(BINDING.read_text())
        return b['tasks']==12 and b['warmup']==1 and b['physical_clears']==13 and len(b['vcd_sha256'])==64
    except (OSError,ValueError,KeyError):return False

assert sha(REVIEWER)==REVIEWER_SHA
if '--launch' in sys.argv:
    start=token();assert start is not None
    assert not (R/'xu-gate-independent-20261113-r3'/(VARIANT+'.json')).exists()
    with META.open('x') as f:json.dump({'gate_pid':156004,'gate_start':start,'reviewer_sha256':REVIEWER_SHA,'wrapper_sha256':sha(Path(__file__))},f,indent=2)
    with (R/'xu-review-backoff-r3.log').open('x') as log:
        p=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve())],cwd=str(R),
                           stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    print('BACKOFF_R3_REVIEW_QUEUED',p.pid,flush=True)
    raise SystemExit(0)

meta=json.loads(META.read_text())
assert meta['wrapper_sha256']==sha(Path(__file__))
while not sealed():
    assert token()==meta['gate_start'],'Gate controller ended without a complete binding'
    print('WAIT_BACKOFF_SEALED_BINDING',time.strftime('%F %T'),flush=True)
    time.sleep(10)
assert sha(REVIEWER)==REVIEWER_SHA
p=subprocess.run([sys.executable,'-B',str(REVIEWER),VARIANT,'--publish-campaign-pointer'],cwd=str(R))
assert p.returncode==0,p.returncode
result=R/'xu-gate-independent-20261113-r3'/(VARIANT+'.json')
assert json.loads(result.read_text())['status']=='PASS_INDEPENDENT_GATE_FULL12_REVIEW'
print('BACKOFF_R3_REVIEW_COMPLETE',sha(result),flush=True)
