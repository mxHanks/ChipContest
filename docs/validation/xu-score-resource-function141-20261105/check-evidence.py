#!/usr/bin/env python3
"""Independently inspect returned original141 bytes without remote state writes."""
from pathlib import Path, PurePosixPath
import hashlib
import importlib.util
import json
import re
import sys
import tarfile

HERE=Path(__file__).resolve().parent
ARCHIVE=HERE/'server141-original.tar.xz'
assert ARCHIVE.stat().st_size==75952
assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()=='7ae96540131c6aa45594eefb80f040f637aeadcf650192e45cc5ca129c59600d'
with tarfile.open(ARCHIVE,'r:xz') as t:
    members=t.getmembers()
    names=[m.name for m in members]
    assert len(names)==len(set(names))
    assert all(m.isfile() and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts for m in members)
    manifest=json.load(t.extractfile('manifest.json'))
    expected={r['path']:r for r in manifest}
    assert len(expected)==len(manifest)==39 and set(names)==set(expected)|{'manifest.json'}
    data={m.name:t.extractfile(m).read() for m in members}
for name,row in expected.items():
    assert len(data[name])==row['bytes'] and hashlib.sha256(data[name]).hexdigest()==row['sha256']
assert sum(r['bytes'] for r in manifest)==1534258
def load(name):return json.loads(data[name])
prefix='mapped-public-function-20261105-128/'
state=load(prefix+'state.json')
review=load(prefix+'public-function-review.json')
log=data[prefix+'functional-simulation.log'].decode()
assert state['status']==review['status']=='PUBLIC_FUNCTION128_COMPLETE_PRIVATE_GATE_PENDING_NOT_QUALIFIED'
assert len(state['inputs_before'])==len(state['inputs_after'])==636
assert state['inputs_before']==state['inputs_after'] and state['inputs_equal_before_after'] is True and state['identity_errors']==[]
assert state['private_pending_count']==60 and state['qualification']=='NOT_QUALIFIED'
assert state['runtime_mode']=='DOCUMENTED_NOTIMINGCHECK_PUBLIC_FUNCTION_ONLY'
assert len(state['steps'])==1
step=state['steps'][0]
assert step['status']=='EXITED' and step['returncode']==review['observed_returncode']==0
assert step['command'][-1]=='+notimingcheck' and '+nospecify' not in step['command']
assert hashlib.sha256(data[prefix+'functional-simulation.log']).hexdigest()==step['log']['sha256']=='3ed1bd2a292d14d49dee3ca15b5064734fb4c60fa3a85ab414dd6fbbb97d337d'
assert hashlib.sha256(data[prefix+'public-function-review.json']).hexdigest()==state['report']['sha256']
complete=re.findall(r'^XU_MAPPED111_PUBLIC_DIAGNOSTIC_COMPLETE (.+)$',log,re.M)
assert len(complete)==1
counters={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',complete[0])}
assert counters==dict(tasks=1,outputs=25344,writes=50688,w_pairs=8192,x_pairs=3168,rows=99,pops=3168,result_reads=50688,source_reads=23232,elapsed_cycles=990656)
assert len(re.findall(r'^XU_MAPPED111_REQUIRED_GATE_PENDING ',log,re.M))==review['required_gate_failure_count']==1
assert review['public_diagnostic_marker_count']==1
assert re.search(r'^Fatal: .*247: tb_xu_soc_ppa.public_scoreboard: at time 15964416666667 fs$',log,re.M)
assert all(review[k]=='NOT_QUALIFIED' for k in ['energy_qualification','full_function_qualification','functional_qualification','timing_qualification'])
sys.path.insert(0,str(HERE/'tools'))
import audit_actual133 as audit
inventory=load('private-target133-static-new/inventory133.json')
static=audit.inspect(inventory)
assert data['private-target133-static-new.returncode']==b'0\n'
assert load('private-target133-static-new.stdout.log')=={k:inventory[k] for k in ['status','design_modules','elaborated_scopes','classification_counts','original_private_gates_remaining']}
assert static['classification_counts']=={'1_RETAINED_NAMED_ENDPOINT':58,'2_PHYSICAL_RECONSTRUCTION_CANDIDATE':1,'3_NOT_LOCATED_OR_FORMAL_CORRESPONDENCE_NEEDED':1}
preflight=load('s2e-preflight-readonly-20261105-136/state.json')
assert preflight['status']=='READONLY_PREFLIGHT_PASS_NOT_QUALIFIED' and len(preflight['runs'])==2
for run in preflight['runs']:
    raw=data['s2e-preflight-readonly-20261105-136/'+run['label']+'.log']
    assert run['returncode']==0 and len(raw)==run['bytes'] and hashlib.sha256(raw).hexdigest()==run['sha256']
resource=load('resource-private-readonly-20261105-137/state.json')
assert resource['cpus']==96 and resource['license']['status']=='UNVERIFIED_NO_LMUTIL'
assert load('license-readonly-20261105-140/state.json')['status']=='LICENSE_UNKNOWN'
live=load('live141-observation.json')['observations'][0]
assert live['pid']==135097 and live['alive_now'] is True and live['current_task_id']==4 and live['status']=='RUNNING_REVIEW_PENDING'
print(json.dumps(dict(status='RETURNED141_EVIDENCE_CHECKED_NOT_QUALIFIED',payload_files=39,payload_bytes=1534258,public128=counters,private133_counts=static['classification_counts'],private_gates_remaining=60,resource_license='UNKNOWN_NO_NATIVE_CONCURRENCY_EXPANSION',s2e130_snapshot_task_id=4),sort_keys=True,indent=2))
