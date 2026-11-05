#!/usr/bin/env python3
"""Migrate an already-stopped controller150 to153; never stop/retry workers."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

HERE=Path(__file__).resolve().parent
ORIGINAL150='d7813ac3745ff1aa5b5efc92eef298a6577abef774259f9285aae605c466db2f'

def control():
    spec=importlib.util.spec_from_file_location('xu153_migration_control',str(HERE/'xu_experiments.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def stable_identity(m,path):
    p=Path(path);before=p.stat();value=m.identity(p);after=p.stat()
    keys=['st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns']
    m.need(all(getattr(before,k)==getattr(after,k) for k in keys),'file changed during migration hash '+str(p))
    return value

def verify_bundle(m):
    manifest=m.read(HERE/'bundle-manifest153.json')
    m.need(manifest['schema']=='xu-experiment-control153-bundle-v1' and manifest['source150_sha256']==ORIGINAL150,'unexpected153 bundle manifest')
    m.need({r['name'] for r in manifest['runtime_files']}=={'xu_experiments.py','migration153.py'},'unexpected153 runtime list')
    for row in manifest['runtime_files']:
        actual=stable_identity(m,HERE/row['name'])
        m.need(actual['sha256']==row['sha256'] and actual['bytes']==row['bytes'],'153 bundle source changed '+row['name'])
    return stable_identity(m,HERE/'bundle-manifest153.json')

def controller_processes(m,out,sources):
    found=[]
    for p in m.processes():
        if p['uid']!=os.getuid():continue
        argv=p['argv']
        if 'run' not in argv or '--out' not in argv:continue
        at=argv.index('--out')
        if at+1>=len(argv):continue
        if Path(argv[at+1]).resolve()!=out:continue
        if any(Path(a).is_absolute() and Path(a).resolve() in sources for a in argv):found.append(p)
    return found

def verify_original(m,out):
    state=m.read(out/'state.json')
    m.need(state['schema']=='xu-experiment-control150-state-v1' and state['qualification']=='NOT_QUALIFIED','unexpected original controller state')
    worker=state['worker'];m.need(worker['sha256']==ORIGINAL150,'expected frozen original150; do not migrate twice')
    original=stable_identity(m,worker['path']);m.need(original==worker,'original150 script differs from frozen state')
    registration_rows={}
    for p in sorted((out/'registrations').glob('*.json')):
        job=m.validate_job(m.read(p));m.need(p.name==job['id']+'.json','registration name differs')
        registration_rows[job['id']]=stable_identity(m,p)
    for name,row in state['jobs'].items():
        m.need(name in registration_rows and row['registration']==registration_rows[name],'original registration changed '+name)
    sources={Path(worker['path']).resolve(),(HERE/'xu_experiments.py').resolve()}
    active=controller_processes(m,out,sources)
    m.need(not active,'original/new controller still running; stop only the controller before migration: '+json.dumps(active))
    old_pid=state.get('controller_pid')
    old_current=m.process_identity(old_pid) if isinstance(old_pid,int) else None
    return state,registration_rows,dict(original_worker=original,recorded_original_controller_pid=old_pid,
        recorded_pid_current_identity=old_current,matching_live_controllers=active,
        confirmed_original_controller_stopped=True)

def full_snapshot(m,out,destination):
    m.need(not destination.exists(),'fresh snapshot directory required')
    destination.mkdir(mode=0o700)
    names=sorted(out.rglob('*'));files=[]
    for p in names:
        m.need(not p.is_symlink(),'symlink in controller tree cannot be a full immutable snapshot '+str(p))
        relative=p.relative_to(out);target=destination/relative
        if p.is_dir():target.mkdir(exist_ok=True);continue
        m.need(p.is_file(),'nonregular controller file '+str(p))
        before=stable_identity(m,p);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(str(p),str(target));saved=stable_identity(m,target);after=stable_identity(m,p)
        m.need(before==after and saved['sha256']==before['sha256'] and saved['bytes']==before['bytes'],
               'live controller output changed during snapshot; no migration '+str(p))
        files.append(dict(relative=str(relative),bytes=before['bytes'],sha256=before['sha256']))
    m.need([str(p.relative_to(out)) for p in sorted(out.rglob('*'))]==[str(p.relative_to(out)) for p in names],
           'controller tree members changed during snapshot')
    m.save(destination/'SNAPSHOT153.json',dict(schema='xu-controller153-pre-migration-snapshot-v1',
        source=str(out),files=files,qualification='NOT_QUALIFIED',status='FULL_CONTROLLER_TREE_SNAPSHOT_VERIFIED'))
    return stable_identity(m,destination/'SNAPSHOT153.json')

def launch_controller(m,out,receipt,receipt_path,token):
    command=[sys.executable,'-B',str(HERE/'xu_experiments.py'),'run','--out',str(out)]
    log=out/('controller153-'+token+'.log')
    with log.open('xb') as stream:
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                                 start_new_session=True,shell=False)
    receipt.update(status='NEW_CONTROLLER_SPAWNED_CONFIRMATION_PENDING',spawn_pid=process.pid,
                   argv=command,controller_log=str(log))
    m.save(receipt_path,receipt)
    confirmed=None
    for _ in range(50):
        code=process.poll()
        if code is not None:
            receipt.update(status='NEW_CONTROLLER_EXITED_REVIEW_REQUIRED',spawn_returncode=code,
                           controller_log_identity=stable_identity(m,log));m.save(receipt_path,receipt)
            raise ValueError('new controller exited; inspect original launch receipt/log, never init or retry workers')
        observed=m.process_identity(process.pid)
        state=m.read(out/'state.json')
        if observed and observed['argv']==command and m.same_process(observed,state.get('controller_identity',{})):
            confirmed=observed;break
        time.sleep(0.1)
    m.need(confirmed is not None,'new controller handle not yet confirmed; inspect same PID before any resume')
    receipt.update(status='MIGRATED_SAME_OUT_CONTROLLER153_RUNNING_NOT_QUALIFIED',
                   confirmed_controller_identity=confirmed,finished_epoch=time.time())
    m.save(receipt_path,receipt)
    return receipt

def migrate(out):
    m=control();out=Path(out).resolve();m.need(out.is_dir(),'existing original controller directory required')
    manifest=verify_bundle(m);token=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:12]
    receipt_path=out/('migration153-'+token+'.json')
    # A separate migration lock remains held across old-lock release and new
    # spawn. The new controller independently takes the original controller.lock.
    with (out.parent/(out.name+'.migration153.lock')).open('a') as migration_lock:
        fcntl.flock(migration_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with (out/'controller.lock').open('a') as controller_lock:
            fcntl.flock(controller_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with (out/'register.lock').open('a') as registration_lock:
                fcntl.flock(registration_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                original,registrations,proof=verify_original(m,out)
                state_before=stable_identity(m,out/'state.json')
                snapshot=out.parent/(out.name+'.before153-'+token)
                snapshot_manifest=full_snapshot(m,out,snapshot)
                again,again_registrations,_=verify_original(m,out)
                m.need(again==original and registrations==again_registrations and
                       stable_identity(m,out/'state.json')==state_before,'original controller changed during migration')
                replacement=dict(original);replacement['worker']=stable_identity(m,HERE/'xu_experiments.py')
                # Preserve all jobs/runs. No worker signal, launch, retry or
                # status promotion occurs during the identity rebind itself.
                m.save(out/'state.json',replacement)
                m.need(m.read(out/'state.json')['jobs']==original['jobs'],'migration changed original jobs')
                receipt=dict(schema='xu-controller153-migration-v1',qualification='NOT_QUALIFIED',
                    status='STATE_REBOUND_ORIGINAL_JOBS_AND_RUNS_PRESERVED_NEW_CONTROLLER_NOT_YET_STARTED',
                    out=str(out),old_state_identity=state_before,new_worker=replacement['worker'],
                    original_controller_stop_proof=proof,bundle_manifest=manifest,
                    snapshot=str(snapshot),snapshot_manifest=snapshot_manifest,
                    registration_identities=registrations,workers_signalled=0,workers_restarted=0,
                    started_epoch=time.time())
                m.save(receipt_path,receipt)
        # The old controller lock is now released. A competing launch still
        # cannot produce two running controllers because run() uses LOCK_NB.
        return launch_controller(m,out,receipt,receipt_path,token)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',required=True)
    args=parser.parse_args()
    try:
        receipt=migrate(args.out)
    except Exception as error:
        print('XU153_MIGRATION_REVIEW_REQUIRED '+type(error).__name__+': '+str(error),file=sys.stderr,flush=True)
        return 1
    print('XU153_MIGRATION_COMPLETE '+json.dumps(receipt,sort_keys=True),flush=True)
    return 0

if __name__=='__main__':sys.exit(main())
