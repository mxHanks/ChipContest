#!/usr/bin/env python3
"""Single daily entry for the frozen server campaign: start, status, run, report.

Uses the existing persistent controller state. Does not initialize a new queue,
restart experiments, remove failed evidence, or infer contest qualification.
"""
import argparse
import csv
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
BASE = Path.home()/'Desktop/xu-score-optimization-20261102'
CONTROL = BASE/'unified-experiment-control-20261105-150'
PROFILES = ['baseline_h1_h2', 's1_h2_only', 's1_sram_bias', 's2b', 's2d', 'pe32', 'pe64', 'compact32_128']
ORIGINAL150_SHA='d7813ac3745ff1aa5b5efc92eef298a6577abef774259f9285aae605c466db2f'


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):
            result.update(block)
    return result.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')


def identity(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def verify_release():
    manifest = read(HERE/'release154.json')
    need(manifest['qualification'] == 'NOT_QUALIFIED' and manifest['schema'] == 'xu-campaign-release154-v1', 'release schema differs')
    seen = set()
    for row in manifest['files']:
        path = Path(row['path'])
        need(not path.is_absolute() and '..' not in path.parts and row['path'] not in seen, 'unsafe/duplicate release member')
        seen.add(row['path'])
        actual = HERE/path
        need(actual.is_file() and not actual.is_symlink() and actual.stat().st_size == row['bytes'] and sha(actual) == row['sha256'], 'release bytes changed: '+row['path'])
    actual_files={str(p.relative_to(HERE)) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name != 'release154.json'}
    need(actual_files == seen, 'release file set differs')
    return manifest


def start(manifest):
    worker = HERE/'control153/xu_experiments.py'
    state = read(CONTROL/'state.json')
    need(state['worker'] == identity(worker), 'perform controlled153 migration before start')
    registrar = load('xu_enroll152_for154', HERE/'enroll152.py')
    receipts = BASE/'campaign-enrollment-20261105-154'
    receipts.mkdir(exist_ok=True)
    receipt = receipts/('enroll-%d-%s.json' % (int(time.time()), uuid.uuid4().hex))
    registrar.enroll(worker, CONTROL, sorted((HERE/'jobs').glob('*.json')), receipt, manifest['controller_sha256'])
    # A locked controller is already active. The controller itself takes the
    # same lock before any dispatch, so a concurrent start cannot duplicate it.
    with (CONTROL/'controller.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print('CONTROLLER_ALREADY_RUNNING; BATCH_REGISTERED_NOT_QUALIFIED', flush=True)
            return
    command = [sys.executable, '-B', str(worker), 'run', '--out', str(CONTROL)]
    log = receipts/('controller-%d-%s.log' % (int(time.time()), uuid.uuid4().hex))
    with log.open('xb') as stream:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    write(receipts/('spawn-'+uuid.uuid4().hex+'.json'), dict(pid=process.pid, argv=command, log=str(log), qualification='NOT_QUALIFIED'))
    print('CONTROLLER_SPAWNED', process.pid, 'BATCH_REGISTERED_NOT_QUALIFIED', flush=True)


def upgrade(manifest):
    state=read(CONTROL/'state.json')
    if state['worker']['sha256']==manifest['controller_sha256']:
        start(manifest)
        return
    with (CONTROL/'register.lock').open('a') as registration_lock:
        fcntl.flock(registration_lock,fcntl.LOCK_EX)
        state=read(CONTROL/'state.json')
        need(state['worker']['sha256']==ORIGINAL150_SHA and identity(state['worker']['path'])==state['worker'], 'unexpected original controller; no signal sent')
        need(set(state['jobs'])=={'s2e_power130','eight_freeze138','s2e_timing134','baseline_rdc142'}, 'unexpected original queue; inspect before upgrade')
        need(all(r['status'] in ('COMPLETED_DIAGNOSTIC_NOT_QUALIFIED','FAILED_REVIEW_REQUIRED') for r in state['jobs'].values()), 'original queue not terminal; no signal sent')
        next_control=load('xu153_for_quiesce154',HERE/'control153/xu_experiments.py')
        for path in sorted((CONTROL/'registrations').glob('*.json')):
            job=read(path)
            need(identity(path)==state['jobs'][job['id']]['registration'],'original registration changed; no signal sent')
            matches=[p for p in next_control.processes() if p['uid']==os.getuid() and any(job['process_contains'] in a for a in p['argv'])]
            need(not matches,'original experiment still alive; no signal sent')
        pid=state['controller_pid'];before=next_control.process_identity(pid)
        expected=['-B',state['worker']['path'],'run','--out',str(CONTROL)]
        receipt_dir=BASE/'campaign-enrollment-20261105-154';receipt_dir.mkdir(exist_ok=True)
        receipt_path=receipt_dir/('quiesce150-'+uuid.uuid4().hex+'.json')
        receipt=dict(schema='xu-controller150-quiesce154-v1',qualification='NOT_QUALIFIED',status='VALIDATING_ONLY_CONTROLLER_STOP',
                     controller_state=identity(CONTROL/'state.json'),old_controller_identity=before,workers_signalled=0,epoch=time.time())
        if before:
            need(before['uid']==os.getuid() and before['argv'][1:]==expected,'recorded PID no longer the exact original controller; no signal sent')
            need(next_control.same_process(before,next_control.process_identity(pid)),'controller process identity changed; no signal sent')
            write(receipt_path,receipt)
            os.kill(pid,signal.SIGTERM)  # Exact controller only; never a process group.
            for _ in range(100):
                current=next_control.process_identity(pid)
                if not current or not next_control.same_process(before,current):break
                time.sleep(0.1)
            else:raise ValueError('same original controller still alive; inspect it before migration')
        receipt.update(status='ORIGINAL_CONTROLLER_STOPPED_EXPERIMENTS_UNTOUCHED',finished_epoch=time.time())
        write(receipt_path,receipt)
    migration=load('xu_migration153_for154',HERE/'control153/migration153.py')
    migration.migrate(CONTROL)
    start(manifest)


def report(out):
    out = Path(out).resolve()
    need(not out.exists(), 'fresh report output required; existing reports are preserved')
    out.mkdir(parents=True)
    snapshots=out/'snapshots';snapshots.mkdir()
    def capture(path,name):
        # Parse and hash the same original byte string, even if a live worker
        # atomically publishes the next receipt while this report is running.
        raw=Path(path).read_bytes();value=json.loads(raw.decode('utf-8'))
        saved=snapshots/name
        with saved.open('xb') as stream:stream.write(raw)
        return value,dict(source_path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),snapshot=str(saved))
    control,controller_receipt=capture(CONTROL/'state.json','controller-state.json')
    state = dict(schema='xu-campaign-report154-v1', status='RUNNING_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
                 created_epoch=time.time(), controller_state=controller_receipt,
                 candidates=[], continuations=[], input_receipts=[], source='Frozen task results; diagnostic energy/area are not eligibility or scores.')
    write(out/'state.json', state)
    overview, layers = [], []
    try:
        for jobid,jobstate in sorted(control['jobs'].items()):
            if jobid.startswith(('activity145_','power146_')) or jobid=='zz_campaign_report154':continue
            registration=CONTROL/'registrations'/(jobid+'.json')
            if not registration.is_file():continue
            job,reg_receipt=capture(registration,jobid+'-registration.json')
            state['input_receipts'].append(reg_receipt)
            continuation=dict(job_id=jobid,queue_status=jobstate['status'],qualification='NOT_QUALIFIED',result_path=job['result_state'])
            result_path=Path(job['result_state'])
            if result_path.is_file():
                value,receipt=capture(result_path,jobid+'-result.json')
                state['input_receipts'].append(receipt)
                continuation.update(reported_status=value.get('status'),result_snapshot=receipt)
                if jobid=='s2e_power130':continuation['diagnostic_summary']=value.get('diagnostic_summary')
            state['continuations'].append(continuation)
        for profile in PROFILES:
            activity_root = BASE/'eight-formal-activity12-20261105-145'/profile
            power_root = BASE/'eight-full-soc-power12-20261105-146'/profile
            ap, ep, sp = activity_root/'result.json', power_root/'execution.json', power_root/'summary.json'
            activity, execution, summary = {}, {}, {}
            for path, key in [(ap,'activity'), (ep,'execution'), (sp,'summary')]:
                if path.is_file():
                    value,receipt=capture(path,profile+'-'+key+'.json')
                    state['input_receipts'].append(receipt)
                    if key == 'activity': activity=value
                    elif key == 'execution': execution=value
                    else: summary=value
            for jobid in ['activity145_'+profile, 'power146_'+profile]:
                path=CONTROL/'registrations'/(jobid+'.json')
                if path.is_file():
                    _,receipt=capture(path,jobid+'-registration.json')
                    state['input_receipts'].append(receipt)
            area=summary.get('area',{}).get('accelerator',{})
            row=dict(profile=profile, qualification='NOT_QUALIFIED',
                activity_status=activity.get('status',control['jobs'].get('activity145_'+profile,{}).get('status','ABSENT')),
                power_status=execution.get('status',control['jobs'].get('power146_'+profile,{}).get('status','ABSENT')),
                elapsed_cycles12=summary.get('elapsed_cycles12'),
                accelerator_area_mm2_diagnostic=area.get('area_mm2_diagnostic'),
                diagnostic_energy12_j=summary.get('sum_diagnostic_energy_j'),
                mean_reported_power_w=summary.get('time_weighted_mean_reported_power_w'),
                area_limit_mm2='2.25', diagnostic_within_area_limit=area.get('diagnostic_within_limit'),
                activity_result=str(ap), power_result=str(ep), power_summary=str(sp),
                selected_mapped=summary.get('selected_mapped'), analysis_sdc=summary.get('analysis_sdc'))
            if row['elapsed_cycles12'] is None and activity.get('taskset_complete'):
                row['elapsed_cycles12']=sum(t['activity_window']['formal_elapsed_cycles'] for t in activity['tasks'])
            overview.append(row);state['candidates'].append(row)
            power_layers={t['task_id']:t for t in summary.get('layers',[])}
            activity_layers={t['task_id']:t for t in activity.get('tasks',[])}
            for number in range(12):
                a,p=activity_layers.get(number,{}),power_layers.get(number,{})
                log=a.get('boundary_log',{})
                layers.append(dict(profile=profile,task_id=number,qualification='NOT_QUALIFIED',
                    elapsed_cycles=a.get('activity_window',{}).get('formal_elapsed_cycles'),
                    duration_ticks=a.get('activity_window',{}).get('duration_ticks'),
                    power_w=p.get('power_components',{}).get('total_power_w'),
                    diagnostic_energy_j=p.get('diagnostic_energy_j'),
                    vcs_log_sha256=log.get('sha256'),pt_log_sha256=p.get('log_sha256')))
        for rows,name in [(overview,'candidate-comparison.csv'),(layers,'layer-comparison.csv')]:
            simple=[{k:v for k,v in r.items() if k not in ('selected_mapped','analysis_sdc')} for r in rows]
            fields=list(simple[0])
            with (out/name).open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(simple)
        state.update(status='COLLECTED_CAMPAIGN_DIAGNOSTICS_NOT_QUALIFIED',finished_epoch=time.time(),
                     artifacts=[identity(out/'candidate-comparison.csv'),identity(out/'layer-comparison.csv')])
        write(out/'state.json',state)
        print('COLLECTED_CAMPAIGN_DIAGNOSTICS_NOT_QUALIFIED',str(out),flush=True)
        return state
    except BaseException as exc:
        state.update(status='FAILED_REPORT_NOT_QUALIFIED',error=type(exc).__name__+': '+str(exc))
        write(out/'state.json',state)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['upgrade','start','status','run','report','verify'])
    parser.add_argument('--report-out',type=Path)
    args=parser.parse_args()
    manifest=verify_release()
    if args.mode=='verify':
        print('VERIFIED_FROZEN_RELEASE154_NOT_QUALIFIED',len(manifest['files']));return
    if args.mode=='upgrade': upgrade(manifest)
    elif args.mode=='start': start(manifest)
    elif args.mode=='status': print((CONTROL/'SUMMARY.md').read_text())
    elif args.mode=='run':
        os.execv(sys.executable,[sys.executable,'-B',str(HERE/'control153/xu_experiments.py'),'run','--out',str(CONTROL)])
    elif args.mode=='report':
        need(args.report_out is not None,'--report-out required')
        report(args.report_out)


if __name__=='__main__':
    main()
