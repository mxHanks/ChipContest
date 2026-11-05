#!/usr/bin/env python3
"""Persistent single-entry experiment controller, Python3.6+, no network.

Exact frozen jobs, dependency order, durable start intent, existing-job adoption,
one native slot, and append-only observations. No result is contest qualified.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

NATIVE={'pt_shell','pt_shell_exec','dc_shell','dc_shell_exec','fm_shell','fm_shell_exec','vcs','vcs1','simv','lc_shell','lc_shell_exec'}
DONE={'COMPLETED_DIAGNOSTIC_NOT_QUALIFIED','FAILED_REVIEW_REQUIRED','ADOPTED_TERMINAL_REVIEW_PENDING','ORPHAN_REVIEW_REQUIRED','REJECTED_INPUT_REVIEW_REQUIRED'}

def need(ok,message):
    if not ok:raise ValueError(message)

def read(path):
    def pairs(xs):
        d={}
        for k,v in xs:need(k not in d,'duplicate key '+k);d[k]=v
        return d
    return json.loads(Path(path).read_text(),object_pairs_hook=pairs)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()

def identity(path):
    p=Path(path)
    need(p.is_absolute() and p.is_file() and not p.is_symlink(),'absolute non-symlink file required '+str(p))
    return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))

def save(path,value):
    p=Path(path);temp=p.with_name(p.name+'.tmp.'+uuid.uuid4().hex)
    with temp.open('x') as f:
        f.write(json.dumps(value,sort_keys=True,indent=2)+'\n');f.flush();os.fsync(f.fileno())
    os.replace(str(temp),str(p))

def processes():
    result=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            uid=p.stat().st_uid
            argv=[x.decode(errors='replace') for x in (p/'cmdline').read_bytes().split(b'\0') if x]
            if argv:result.append(dict(pid=int(p.name),uid=uid,argv=argv))
        except OSError:pass
    return result

def resources(out,ps):
    values={k:int(v.split()[0])*1024 for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())}
    native=[p for p in ps if p['uid']==os.getuid() and any(Path(a).name in NATIVE for a in p['argv'][:2])]
    return dict(epoch=time.time(),mem_available_bytes=values['MemAvailable'],disk_available_bytes=shutil.disk_usage(str(out)).free,cpu_count=os.cpu_count(),native_processes=native,license_capacity='UNKNOWN_NO_SPARE_SEATS_CLAIMED',native_policy='EXCLUSIVE_SINGLE_EXISTING_JOB_OR_ONE_NEW_JOB')

def check_records(records):
    actual=[]
    for r in records:
        value=identity(r['path'])
        need(value['sha256']==r['sha256'] and ('bytes' not in r or r['bytes']==value['bytes']),'frozen input changed '+r['path'])
        actual.append(value)
    return actual

def validate_job(job):
    need(job['schema']=='xu-experiment-control150-job-v1' and job['qualification']=='NOT_QUALIFIED','job schema/qualification')
    need(job['id'] and all(c.isalnum() or c in '_-' for c in job['id']),'unsafe job id')
    need(job['kind'] in ['adopt','launch'],'job kind')
    need(isinstance(job['dependencies'],list),'dependencies')
    for dep in job['dependencies']:need(set(dep)=={'id','policy'} and dep['policy'] in ['terminal','success'],'dependency policy')
    need(job.get('process_contains') and Path(job['result_state']).is_absolute(),'process/result identity required')
    need(job['success_statuses'] and isinstance(job['failure_statuses'],list),'explicit terminal statuses required')
    if job['kind']=='launch':
        need(job['argv'] and all(isinstance(x,str) and x for x in job['argv']) and job['frozen_inputs'],'frozen argv/inputs required')
        need(job.get('output_root'),'unique output required')
        need(job.get('launch_mode','launcher') in ['launcher','direct'],'launch mode')
        if job.get('launch_mode','launcher')=='launcher':
            need(job.get('launch_receipt') and job.get('pid_keys'),'launcher receipts required')
    return job

def add_event(out,value):
    with (out/'events.jsonl').open('a') as f:
        f.write(json.dumps(dict(epoch=time.time(),**value),sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())

def summarize(out,state):
    rows=['# xu实验总控150','', '所有状态均为NOT_QUALIFIED；诊断完成不代表比赛资格。','', '|实验|状态|原始状态|PID|','|---|---|---|---|']
    for name,row in sorted(state['jobs'].items()):
        rows.append('|{}|{}|{}|{}|'.format(name,row['status'],row.get('reported_status',''),row.get('pid','')))
    rows+=['','资源及许可证：'+json.dumps(state.get('resources',{}),sort_keys=True,ensure_ascii=False),'','已完成/失败的原结果和日志保持在各自目录；总控不删除、覆盖或自动重启。']
    (out/'SUMMARY.md').write_text('\n'.join(rows)+'\n')

def initialize(out):
    out=Path(out).resolve();need(not out.exists(),'existing controller: use run/status, never init again')
    out.mkdir(parents=True);(out/'registrations').mkdir();(out/'runs').mkdir()
    state=dict(schema='xu-experiment-control150-state-v1',qualification='NOT_QUALIFIED',worker=identity(Path(__file__).resolve()),created_epoch=time.time(),jobs={},status='WAIT_REGISTERED_JOBS')
    save(out/'state.json',state);summarize(out,state)
    return state

def register(out,jobpath):
    out=Path(out).resolve();job=validate_job(read(jobpath));target=out/'registrations'/(job['id']+'.json')
    with (out/'register.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if target.exists():need(target.read_bytes()==Path(jobpath).read_bytes(),'same id cannot be replaced');return
        with target.open('xb') as f:f.write(Path(jobpath).read_bytes());f.flush();os.fsync(f.fileno())
    print('REGISTERED',job['id'],sha(target),flush=True)

def terminal_status(job,reported):
    if reported in job['success_statuses']:return 'COMPLETED_DIAGNOSTIC_NOT_QUALIFIED'
    if reported in job['failure_statuses']:return 'FAILED_REVIEW_REQUIRED'
    return None

def observe(job,row,ps):
    matches=[p for p in ps if p['uid']==os.getuid() and any(job['process_contains'] in a for a in p['argv'])]
    row['live_processes']=matches
    if matches:row['pid']=matches[0]['pid']
    p=Path(job['result_state'])
    if p.is_file():
        value=read(p);row.update(reported_status=value.get('status'),result_state_snapshot=dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)))
        # A terminal receipt while the worker is still alive is a verified wait.
        if not matches:
            terminal=terminal_status(job,value.get('status'))
            if terminal:row['status']=terminal;row['terminal_receipt']=identity(p);return
    if matches:row['status']='RUNNING_ADOPTED' if job['kind']=='adopt' else 'RUNNING';return
    if job['kind']=='adopt':row['status']='WAIT_EXISTING_JOB_OR_TERMINAL_RECEIPT';return
    if row['status'] in ['START_INTENT_REVIEW_IF_ORPHAN','RUNNING']:
        # A missing handle is reviewed, never silently relaunched. Allow the
        # child initial receipt grace without classifying a transient as exit.
        if time.time()-row.get('started_epoch',0)>120:row['status']='ORPHAN_REVIEW_REQUIRED'

def guard(res,rows,job):
    if res['mem_available_bytes']<16*1024**3:return 'WAIT_MEMORY'
    if res['disk_available_bytes']<150*1024**3:return 'WAIT_DISK'
    if job.get('native',True) and (res['native_processes'] or any(r.get('live_processes') or r['status'] in ['START_INTENT_REVIEW_IF_ORPHAN','RUNNING'] for r in rows.values())):return 'WAIT_EXCLUSIVE_NATIVE_SLOT'
    return 'ALLOW_EXCLUSIVE_SINGLE_DIAGNOSTIC_NO_SPARE_LICENSE_CLAIM'

def start(out,job,row,state):
    records=check_records(job['frozen_inputs'])
    need(not Path(job['output_root']).exists(),'output exists; adopt/inspect original instead of restart')
    if job.get('launch_mode','launcher')=='launcher':
        need(not Path(job['launch_receipt']).parent.exists(),'launcher exists; adopt/inspect original instead of restart')
    run=out/'runs'/job['id'];run.mkdir()
    row.update(status='START_INTENT_REVIEW_IF_ORPHAN',started_epoch=time.time(),frozen_before=records,argv=job['argv'],run_dir=str(run))
    save(out/'state.json',state);add_event(out,dict(job=job['id'],event='START_INTENT',argv=job['argv']))
    if job.get('launch_mode','launcher')=='direct':
        with (run/'worker.log').open('xb') as f:
            process=subprocess.Popen(job['argv'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,shell=False)
        row.update(pid=process.pid,status='RUNNING',worker_log=str(run/'worker.log'))
        save(run/'spawn.json',dict(pid=process.pid,argv=job['argv'],epoch=time.time(),qualification='NOT_QUALIFIED'))
        add_event(out,dict(job=job['id'],event='SPAWNED',pid=process.pid))
        return
    with (run/'launcher.log').open('xb') as f:
        result=subprocess.run(job['argv'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=300,shell=False)
    row.update(launcher_returncode=result.returncode,launcher_log=identity(run/'launcher.log'))
    row['frozen_after_launch']=check_records(job['frozen_inputs'])
    need(row['frozen_after_launch']==records,'launcher frozen inputs changed')
    if result.returncode:
        row['status']='FAILED_REVIEW_REQUIRED';row['error']='launcher returned '+str(result.returncode);return
    receipt=read(job['launch_receipt']);row['launch_receipt']=identity(job['launch_receipt'])
    pids=[receipt[k] for k in job['pid_keys'] if isinstance(receipt.get(k),int)]
    need(len(pids)==1,'one original worker PID required');row['pid']=pids[0];row['status']='RUNNING'
    add_event(out,dict(job=job['id'],event='SPAWNED',pid=pids[0]))

def tick(out,state):
    out=Path(out)
    need(identity(Path(__file__).resolve())==state['worker'],'controller bytes changed; use frozen original worker')
    jobs={}
    for p in sorted((out/'registrations').glob('*.json')):
        job=validate_job(read(p));need(p.name==job['id']+'.json','registration name mismatch');jobs[job['id']]=job
        if job['id'] not in state['jobs']:
            state['jobs'][job['id']]=dict(status='QUEUED',registration=identity(p))
            add_event(out,dict(job=job['id'],event='QUEUED',registration=identity(p)))
        else:need(identity(p)==state['jobs'][job['id']]['registration'],'frozen registration changed')
    ps=processes();state['resources']=resources(out,ps)
    for name,job in jobs.items():
        row=state['jobs'][name]
        if row.get('pid') and job.get('launch_mode')=='direct':
            try:
                pid,status=os.waitpid(row['pid'],os.WNOHANG)
                if pid:row.update(observed_wait_status=status,observed_exit_code=os.WEXITSTATUS(status) if os.WIFEXITED(status) else None)
            except ChildProcessError:pass
        if row['status'] not in DONE:observe(job,row,ps)
    for name,job in jobs.items():
        row=state['jobs'][name]
        if job['kind']!='launch' or row['status'] in DONE or row.get('live_processes') or row['status'] in ['RUNNING','START_INTENT_REVIEW_IF_ORPHAN']:continue
        waiting=[]
        for d in job['dependencies']:
            dr=state['jobs'].get(d['id'],{})
            if dr.get('status') not in DONE or (d['policy']=='success' and dr.get('status')!='COMPLETED_DIAGNOSTIC_NOT_QUALIFIED'):waiting.append(d)
        if waiting:row.update(status='WAIT_DEPENDENCY',waiting=waiting);continue
        decision=guard(state['resources'],state['jobs'],job);row['guard']=decision
        if not decision.startswith('ALLOW'):row['status']=decision;continue
        try:start(out,job,row,state)
        except Exception as e:row.update(status='REJECTED_INPUT_REVIEW_REQUIRED',error=type(e).__name__+': '+str(e))
        break  # One global dispatch per iteration; resource/adoption recheck.
    state.update(updated_epoch=time.time(),controller_pid=os.getpid(),status='ACTIVE_NOT_QUALIFIED' if jobs else 'WAIT_REGISTERED_JOBS')
    save(out/'state.json',state);summarize(out,state)
    return state

def run(out,once=False):
    out=Path(out).resolve()
    with (out/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state=read(out/'state.json');add_event(out,dict(event='CONTROLLER_RUNNING',pid=os.getpid()))
        while True:
            tick(out,state)
            if once:return state
            time.sleep(15)

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='mode')
    p=sub.add_parser('init');p.add_argument('--out',required=True)
    p=sub.add_parser('register');p.add_argument('--out',required=True);p.add_argument('--job',required=True)
    p=sub.add_parser('run');p.add_argument('--out',required=True);p.add_argument('--once',action='store_true')
    p=sub.add_parser('status');p.add_argument('--out',required=True)
    a=ap.parse_args()
    if a.mode=='init':initialize(a.out)
    elif a.mode=='register':register(a.out,a.job)
    elif a.mode=='run':run(a.out,a.once)
    elif a.mode=='status':print((Path(a.out)/'SUMMARY.md').read_text())
    else:ap.error('command required')

if __name__=='__main__':main()
