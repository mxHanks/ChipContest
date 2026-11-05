#!/usr/bin/env python3
"""One-shot xu administrative deferral of existing pe32/pe64 registrations.

Uses the existing controller153 DONE representation without fabricating worker
success. Existing workers, terminal rows, registrations and results are untouched.
Python 3.6+, no network, no process-group signals.
"""
import argparse
import copy
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

BASE = '/storage2/2026contest/server4/s4_23usr/Desktop'
OUT = BASE + '/xu-score-optimization-20261102/unified-experiment-control-20261105-150'
CONTROLLER = BASE + '/xu-campaign-batch154/control153/xu_experiments.py'
CONTROLLER_SHA = '877a1624d45bdae7dd5095809f69e3e9c95eafafac17f354fe52f9781c9ef025'
UID = 14023
TARGETS = {
    'activity145_pe32': '05146dd17c544595200a069a4f6a634fbd31d5abfc278033fcaf40a0c93cd71f',
    'activity145_pe64': 'a523ff19ee7e8345099251fbb25d3ab19884c9ed3669e1315ef0b11d6ece878a',
    'power146_pe32': '98de7f3626e39e9a3e9ec657470d46a4d91d97d0553d0017459dce2a7305ade1',
    'power146_pe64': '5cf5997f52068c1bd87b64b6ef033b2a70e75484e81cb8d22c8bb7d6900424d1',
}
DONE = {'COMPLETED_DIAGNOSTIC_NOT_QUALIFIED', 'FAILED_REVIEW_REQUIRED',
        'ADOPTED_TERMINAL_REVIEW_PENDING', 'ORPHAN_REVIEW_REQUIRED',
        'REJECTED_INPUT_REVIEW_REQUIRED', 'BLOCKED_DEPENDENCY_NOT_QUALIFIED'}
STARTED_KEYS = {'start_intent', 'started_epoch', 'pid', 'worker_identity',
                'run_dir', 'argv', 'launch_receipt', 'worker_log'}
ADMIN = 'DEFERRED_BY_USER_NOT_QUALIFIED'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    return value.hexdigest()


def identity(path):
    path = Path(path)
    need(path.is_absolute() and path.is_file() and not path.is_symlink(), 'absolute regular file required')
    before = path.stat()
    value = dict(path=str(path), bytes=before.st_size, sha256=sha(path))
    after = path.stat()
    need(all(getattr(before, key) == getattr(after, key) for key in
             ['st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns']), 'file changed while hashing')
    return value


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs)


def save(path, value):
    path = Path(path)
    temporary = path.with_name('.' + path.name + '.pending.' + uuid.uuid4().hex)
    with temporary.open('x') as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))
    fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def controller_argv(out):
    return ['/bin/python3', '-B', CONTROLLER, 'run', '--out', str(out)]


def exact_controller(expected, actual, out, uid):
    need(isinstance(expected, dict) and isinstance(actual, dict), 'controller process handle missing')
    need(expected.get('uid') == uid and expected.get('argv') == controller_argv(out), 'unexpected recorded controller uid/argv')
    need(isinstance(expected.get('pid'), int) and expected['pid'] > 1 and
         isinstance(expected.get('start_ticks'), int), 'invalid recorded controller handle')
    need(all(expected.get(key) == actual.get(key) for key in
             ['pid', 'uid', 'start_ticks', 'argv']), 'controller PID birth/uid/argv changed')
    return expected


def load_controller():
    need(os.getuid() == UID, 'this one-shot operation is restricted to the original server uid')
    need(identity(CONTROLLER)['sha256'] == CONTROLLER_SHA, 'frozen153 bytes changed')
    spec = importlib.util.spec_from_file_location('xu_frozen153_for_defer160', CONTROLLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    need(module.DONE == DONE, 'controller DONE representation changed')
    return module


def verify_state(module, out, require_live):
    state = read(out / 'state.json')
    need(state.get('schema') == 'xu-experiment-control150-state-v1' and
         state.get('qualification') == 'NOT_QUALIFIED', 'wrong controller schema')
    need(state.get('worker') == identity(CONTROLLER), 'controller frozen worker differs')
    registrations = {}
    jobs = {}
    for path in sorted((out / 'registrations').glob('*.json')):
        job = module.validate_job(read(path))
        need(path.name == job['id'] + '.json', 'registration id differs')
        registrations[job['id']] = identity(path)
        jobs[job['id']] = job
    need(set(state['jobs']) == set(registrations), 'unobserved/missing registration; inspect before defer')
    for name, row in state['jobs'].items():
        need(row['registration'] == registrations[name], 'frozen registration changed ' + name)
    for name, digest in TARGETS.items():
        need(name in jobs and registrations[name]['sha256'] == digest, 'target registration identity differs ' + name)
        need(jobs[name]['process_contains'] == jobs[name]['output_root'], 'target unique process marker differs')
    if require_live:
        token = exact_controller(state.get('controller_identity'),
                                 module.process_identity(state.get('controller_pid')), out, os.getuid())
        need(state['controller_pid'] == token['pid'], 'controller pid fields differ')
    return state, jobs, registrations


def stopped(module, token):
    current = module.process_identity(token['pid'])
    if current is None:
        return not Path('/proc', str(token['pid'])).exists()
    if current['uid'] != token['uid'] or current['start_ticks'] != token['start_ticks']:
        return True  # Original birth ended; never signal a reused PID.
    try:
        state = Path('/proc', str(token['pid']), 'stat').read_text().rsplit(')', 1)[1].split()[0]
    except OSError:
        return False
    return state == 'Z'


def stop_controller(module, token, out, on_signal=None):
    exact_controller(token, module.process_identity(token['pid']), out, os.getuid())
    os.kill(token['pid'], signal.SIGTERM)  # Deliberately one PID, never killpg.
    if on_signal:
        on_signal()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if stopped(module, token):
            return
        time.sleep(.1)
    raise ValueError('original controller has not exited; no state mutation or worker signal')


def snapshot(out, destination, state, registrations):
    destination.mkdir(mode=0o700)
    names = ['state.json', 'SUMMARY.md', 'events.jsonl']
    names += ['registrations/' + name + '.json' for name in sorted(registrations)]
    files = []
    for name in names:
        source = out / name
        if not source.exists() and name in ['SUMMARY.md', 'events.jsonl']:
            continue
        original = identity(source)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(source.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        need(identity(source) == original and identity(target)['sha256'] == original['sha256'], 'snapshot bytes changed')
        files.append(dict(relative=name, bytes=original['bytes'], sha256=original['sha256']))
    need(read(destination / 'state.json') == state, 'snapshot state differs')
    save(destination / 'manifest.json', dict(schema='xu-defer160-before-snapshot-v1',
         qualification='NOT_QUALIFIED', files=files, note='Full controller state, every registration, events and summary; worker results/logs untouched.'))
    return identity(destination / 'manifest.json')


def eligible(row, job, out, name, processes):
    if row['status'] in DONE:
        return False, 'ORIGINAL_TERMINAL_ROW_PRESERVED'
    if STARTED_KEYS.intersection(row) or row.get('live_processes') or row.get('unconfirmed_live_handle'):
        return False, 'ORIGINAL_STARTED_OR_LIVE_ROW_PRESERVED'
    if any(p.get('uid') == os.getuid() and any(job['process_contains'] in a for a in p.get('argv', [])) for p in processes):
        return False, 'ORIGINAL_LIVE_WORKER_PRESERVED'
    if Path(job['result_state']).exists() or Path(job['output_root']).exists() or (out / 'runs' / name).exists():
        return False, 'ORIGINAL_RESULT_OR_START_ARTIFACT_PRESERVED'
    return True, 'NEVER_STARTED_JOB_ADMINISTRATIVELY_DEFERRED'


def defer_rows(state, jobs, out, processes, receipt_identity):
    updated = copy.deepcopy(state)
    actions = {}
    for name in sorted(TARGETS):
        row = state['jobs'][name]
        allowed, reason = eligible(row, jobs[name], out, name, processes)
        actions[name] = dict(action=reason, original_status=row['status'], row_changed=allowed)
        if allowed:
            updated['jobs'][name].update(status='ADOPTED_TERMINAL_REVIEW_PENDING',
                administrative_status=ADMIN, administrative_receipt=receipt_identity,
                administrative_reason='User deferred only current pe32/pe64 follow-up experiments; no worker success asserted.')
    changed = {name for name in state['jobs'] if state['jobs'][name] != updated['jobs'][name]}
    need(changed <= set(TARGETS), 'non-target job changed')
    left, right = dict(state), dict(updated)
    left.pop('jobs'); right.pop('jobs')
    need(left == right, 'non-job controller state changed')
    for name in changed:
        need(state['jobs'][name]['status'] not in DONE and not STARTED_KEYS.intersection(state['jobs'][name]), 'started/terminal row mutation')
    return updated, actions


def restart(module, out, folder, receipt):
    need(read(out / 'state.json')['worker'] == identity(CONTROLLER), 'refuse resume: frozen worker binding differs')
    command = controller_argv(out)
    with (folder / 'controller-resume.log').open('xb') as stream:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True, shell=False)
    receipt.update(resume_spawn_pid=process.pid, resume_argv=command,
                   status='RESUME_SPAWNED_CONFIRMATION_PENDING_NOT_QUALIFIED')
    save(folder / 'receipt.json', receipt)
    for _ in range(100):
        need(process.poll() is None, 'resume controller exited; inspect resume log, never init/retry workers')
        actual = module.process_identity(process.pid)
        observed = read(out / 'state.json').get('controller_identity')
        if actual and actual == observed and actual.get('argv') == command and actual.get('uid') == os.getuid():
            receipt.update(resumed_controller_identity=actual, status='DEFERRED_ORIGINAL_WORKERS_PRESERVED_CONTROLLER_RESUMED_NOT_QUALIFIED')
            save(folder / 'receipt.json', receipt)
            return
        time.sleep(.1)
    raise ValueError('resume PID unconfirmed; inspect same process, do not start another controller')


def apply():
    module = load_controller()
    out = Path(OUT)
    token = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:12]
    folder = out.parent / (out.name + '.defer-pe160-' + token)
    folder.mkdir(mode=0o700)
    receipt = dict(schema='xu-defer-pe160-administrative-v1', qualification='NOT_QUALIFIED',
        status='VALIDATION_PENDING', out=str(out), requested_profiles=['pe32', 'pe64'],
        explicitly_preserved_profile='compact32_128', scope_provenance='User: 由于32pe和64pe带来的周期增益有限且占用面积增加较大，是否可以不考虑这两组',
        target_registration_sha256=TARGETS, controller_sha256=CONTROLLER_SHA,
        workers_signalled=0, workers_restarted=0, registrations_modified=0,
        worker_results_modified=0, started_epoch=time.time())
    save(folder / 'receipt.json', receipt)
    controller_stopped = False
    controller_lock = None
    error = None
    with (out / 'register.lock').open('a') as registration_lock:
        fcntl.flock(registration_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            original, jobs, registrations = verify_state(module, out, True)
            handle = original['controller_identity']
            receipt.update(original_controller_identity=handle, status='IDENTITY_VERIFIED_BEFORE_CONTROLLER_ONLY_STOP')
            save(folder / 'receipt.json', receipt)
            def mark_signal():
                receipt['controller_only_sigterm_sent'] = True
                save(folder / 'receipt.json', receipt)
            stop_controller(module, handle, out, mark_signal)
            controller_stopped = True
            controller_lock = (out / 'controller.lock').open('a')
            fcntl.flock(controller_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            original, jobs, registrations = verify_state(module, out, False)
            receipt['snapshot_manifest'] = snapshot(out, folder / 'before', original, registrations)
            # Immutable policy is referenced by changed rows; mutable lifecycle receipt is separate.
            policy_path = folder / 'policy.json'
            save(policy_path, dict(schema='xu-defer160-policy-v1', qualification='NOT_QUALIFIED',
                 status=ADMIN, profiles=['pe32', 'pe64'], targets=sorted(TARGETS),
                 reason=receipt['scope_provenance'], note='Administrative deferral only; no native worker was signalled and no success/result was fabricated.'))
            updated, actions = defer_rows(original, jobs, out, module.processes(), identity(policy_path))
            need(read(out / 'state.json') == original, 'state changed under controller lock')
            save(out / 'state.json', updated)
            need(read(out / 'state.json') == updated, 'committed state differs')
            receipt.update(actions=actions, changed_jobs=sorted(name for name, item in actions.items() if item['row_changed']),
                state_before=identity(folder / 'before' / 'state.json'), state_after=identity(out / 'state.json'),
                policy=identity(policy_path), status='ADMINISTRATIVE_DEFER_COMMITTED_CONTROLLER_PAUSED_NOT_QUALIFIED')
            save(folder / 'receipt.json', receipt)
        except Exception as failure:
            error = type(failure).__name__ + ': ' + str(failure)
            receipt.update(error=error, status='REVIEW_REQUIRED_NOT_QUALIFIED')
            save(folder / 'receipt.json', receipt)
        finally:
            if controller_lock is not None:
                controller_lock.close()
            # Keep registration lock across the seconds-long stop/change/resume.
            # Resume only after the old birth is authoritatively gone, never on timeout.
            if controller_stopped or (receipt.get('controller_only_sigterm_sent') and
                                      stopped(module, receipt['original_controller_identity'])):
                try:
                    need(stopped(module, receipt['original_controller_identity']), 'original controller birth still present')
                    restart(module, out, folder, receipt)
                except Exception as failure:
                    receipt.update(resume_error=type(failure).__name__ + ': ' + str(failure), status='RESUME_REVIEW_REQUIRED_NOT_QUALIFIED')
                    save(folder / 'receipt.json', receipt)
                    error = error or receipt['resume_error']
    print('XU160_RECEIPT ' + str(folder / 'receipt.json'), flush=True)
    print('XU160_STATUS ' + receipt['status'], flush=True)
    if error:
        raise ValueError(error)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['inspect', 'apply'])
    args = parser.parse_args()
    try:
        if args.mode == 'inspect':
            module = load_controller()
            state, jobs, registrations = verify_state(module, Path(OUT), True)
            print(json.dumps(dict(controller=state['controller_identity'], targets={name:dict(
                status=state['jobs'][name]['status'], registration=registrations[name],
                eligibility=eligible(state['jobs'][name], jobs[name], Path(OUT), name, module.processes())) for name in sorted(TARGETS)}), sort_keys=True))
        else:
            apply()
    except Exception as failure:
        print('XU160_REVIEW_REQUIRED ' + type(failure).__name__ + ': ' + str(failure), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
