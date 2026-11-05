#!/usr/bin/env python3
"""Exercise process/resource/receipt dispatch decisions with temporary fixtures."""
import importlib.util
import json
from pathlib import Path
import tempfile
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('xu150',str(HERE/'xu_experiments.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
def ok(name,value):
    assert value,name
    checks.append(name)
res=dict(mem_available_bytes=32*1024**3,disk_available_bytes=200*1024**3,native_processes=[])
ok('single slot no spare-license claim',m.guard(res,{},dict(native=True)).startswith('ALLOW_EXCLUSIVE'))
ok('memory floor',m.guard(dict(res,mem_available_bytes=0),{},dict(native=True))=='WAIT_MEMORY')
ok('disk floor',m.guard(dict(res,disk_available_bytes=0),{},dict(native=True))=='WAIT_DISK')
ok('native existing process',m.guard(dict(res,native_processes=[dict(pid=1)]),{},dict(native=True))=='WAIT_EXCLUSIVE_NATIVE_SLOT')
ok('worker reservation between tool calls',m.guard(res,{'130':dict(status='RUNNING_ADOPTED',live_processes=[dict(pid=1)])},dict(native=True))=='WAIT_EXCLUSIVE_NATIVE_SLOT')
ok('durable start intent reserves slot',m.guard(res,{'134':dict(status='START_INTENT_REVIEW_IF_ORPHAN')},dict(native=True))=='WAIT_EXCLUSIVE_NATIVE_SLOT')
with tempfile.TemporaryDirectory(prefix='xu150-') as tmp:
    p=Path(tmp);state=p/'result.json';state.write_text(json.dumps(dict(status='COMPLETE')))
    job=dict(schema='xu-experiment-control150-job-v1',qualification='NOT_QUALIFIED',id='test',kind='adopt',dependencies=[],process_contains='frozen_worker.py',result_state=str(state),success_statuses=['COMPLETE'],failure_statuses=['FAIL'])
    m.validate_job(job)
    row=dict(status='QUEUED')
    m.observe(job,row,[dict(uid=m.os.getuid(),pid=123,argv=['python3','/tmp/frozen_worker.py'])])
    ok('terminal receipt while original worker lives waits',row['status']=='RUNNING_ADOPTED')
    m.observe(job,row,[])
    ok('terminal requires actual process exit',row['status']=='COMPLETED_DIAGNOSTIC_NOT_QUALIFIED')
    state.write_text(json.dumps(dict(status='RUNNING')));row=dict(status='QUEUED')
    m.observe(job,row,[])
    ok('nonterminal receipt no missing-handle restart',row['status']=='WAIT_EXISTING_JOB_OR_TERMINAL_RECEIPT')
    state.write_text(json.dumps(dict(status='FAIL')));m.observe(job,row,[])
    ok('failure preserved',row['status']=='FAILED_REVIEW_REQUIRED')
    inp=p/'input';inp.write_text('original')
    record=m.identity(inp)
    m.check_records([record]);inp.write_text('changed')
    try:m.check_records([record])
    except ValueError:checks.append('changed input rejected')
    else:raise AssertionError('changed input accepted')
    out=p/'control';m.initialize(out)
    jf=p/'job.json';jf.write_text(json.dumps(job));m.register(out,jf)
    m.register(out,jf)
    ok('same exact registration idempotent',len(list((out/'registrations').glob('*.json')))==1)
    changed=dict(job,process_contains='different.py');jf.write_text(json.dumps(changed))
    try:m.register(out,jf)
    except ValueError:checks.append('registration replacement rejected')
    else:raise AssertionError('replacement accepted')
    try:m.initialize(out)
    except ValueError:checks.append('existing controller init rejected')
    else:raise AssertionError('existing init accepted')
print(json.dumps(dict(status='HOST_CONTROL150_CHECKS_PASS_NO_EDA',checks=checks,count=len(checks)),sort_keys=True,indent=2))
