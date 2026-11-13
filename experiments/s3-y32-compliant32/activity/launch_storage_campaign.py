#!/usr/bin/env python3
"""Supervise existing local final374 jobs, audit activity, then replay full12.

No retries, source changes, transfer, EDA or power assertion. The two watched
supervisors must be live at launch. This worker uses CPU0 (or the chosen CPU),
while the independent functional CPU12 job keeps its separately assigned CPU.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def process(pid):
    p = Path('/proc') / str(pid)
    raw = (p / 'stat').read_text()
    # comm can contain spaces; fields after closing parenthesis start at state3.
    tail = raw[raw.rindex(')') + 2:].split()
    if tail[0] == 'Z':
        raise ValueError('watched process is a terminal zombie')
    return dict(pid=pid, start_ticks=tail[19], command=(p / 'cmdline').read_bytes().decode().replace('\0', ' '))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('state-dir', 'task0-run', 'task0-supervisor', 'cpu12-result', 'cpu12-supervisor',
                   'profile', 'vectors', 'native-reader', 'native-exporter', 'probe-result', 'ppa-base', 'storage-candidate'):
        parser.add_argument('--' + option, type=Path, required=True)
    parser.add_argument('--cpu', type=int, default=0)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    for name, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, name, value.resolve())
    statefile = args.state_dir / 'state.json'
    if not args.worker:
        if args.state_dir.exists():
            parser.error('new state directory required; never restart on observation timeout')
        watched = {}
        for label, directory in [('task0_activity', args.task0_supervisor), ('functional_cpu12', args.cpu12_supervisor)]:
            state = json.loads((directory / 'state.json').read_text())
            if state.get('status') != 'RUNNING':
                parser.error(label + ' supervisor must be live now')
            watched[label] = dict(state_path=str(directory / 'state.json'), process=process(state['supervisor_pid']))
        args.state_dir.mkdir(parents=True)
        tools = [Path(__file__).resolve(), HERE / 'run_gpio_activity.py', HERE / 'launch_gpio_full12.py',
            HERE / 'check_gpio_fst.py', HERE / 'activity_profile.py', HERE / 'convert_fst.py',
            HERE / 'gpio_monitor.svh', HERE / 'gpio_trace_main.cpp', args.profile,
            args.native_reader, args.native_exporter, args.probe_result]
        tools += sorted((HERE.parent / 'ppa/storage').glob('*.*'))
        launch = dict(schema='storage374-local-campaign-launch-v1', created_at=now(), watched=watched,
                      pinned_inputs={str(p): sha(p) for p in tools if p.is_file()})
        write(args.state_dir / 'launch.json', launch)
        command = [sys.executable, '-u', '-B', str(Path(__file__).resolve()), *sys.argv[1:], '--worker']
        with (args.state_dir / 'supervisor.log').open('w') as stream:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                     start_new_session=True, close_fds=True)
        launch.update(supervisor_pid=child.pid, status='LAUNCHED_NOT_COMPLETED')
        write(args.state_dir / 'launch.json', launch)
        print(json.dumps(dict(supervisor_pid=child.pid, state_file=str(statefile))))
        return 0
    os.sched_setaffinity(0, {args.cpu})
    launch = json.loads((args.state_dir / 'launch.json').read_text())
    state = dict(schema='storage374-local-activity-campaign-v1', status='RUNNING', started_at=now(),
                 supervisor_pid=os.getpid(), local_cpu_affinity=sorted(os.sched_getaffinity(0)), stages=[],
                 qualification='NO_POWER_PASS; no EDA, upload or native resource use')
    write(statefile, state)

    def pins():
        for name, expected in launch['pinned_inputs'].items():
            if sha(Path(name)) != expected:
                raise ValueError('campaign frozen tool/profile drift: ' + name)

    def wait_for(label, result_path, success):
        watch = launch['watched'][label]
        state.update(active_stage='WAIT_' + label, watched_process=watch['process'])
        write(statefile, state)
        deadline = time.monotonic() + 21600
        while True:
            pins()
            if result_path.is_file():
                value = json.loads(result_path.read_text())
                if value.get('status') == success:
                    return value
                if value.get('status', '').startswith(('FAIL', 'TIMEOUT')):
                    raise ValueError(label + ' terminal result: ' + str(value.get('error', value['status'])))
            observed = process(watch['process']['pid'])
            if observed['start_ticks'] != watch['process']['start_ticks']:
                raise ValueError(label + ' supervisor PID identity changed')
            if time.monotonic() >= deadline:
                raise TimeoutError('bounded wait expired; watched jobs were not stopped or restarted')
            time.sleep(15)

    def run(label, command):
        pins()
        stage = dict(stage=label, status='RUNNING', started_at=now(), command=[str(x) for x in command])
        state['stages'].append(stage)
        state.update(active_stage=label)
        with (args.state_dir / (label + '.log')).open('w') as stream:
            child = subprocess.Popen([str(x) for x in command], stdin=subprocess.DEVNULL,
                                     stdout=stream, stderr=subprocess.STDOUT)
            stage['pid'] = child.pid
            write(statefile, state)
            code = child.wait()
        stage.update(status='PASS' if code == 0 else 'FAIL', returncode=code, finished_at=now())
        write(statefile, state)
        if code:
            raise RuntimeError(label + ' failed: ' + str(code))
        return stage

    try:
        wait_for('task0_activity', args.task0_run / 'result.json', 'PASS_RTL_ACTIVITY_WINDOW_NOT_POWER_READY')
        audit0 = args.state_dir / 'task0-native-audit'
        run('task0_native_audit', [sys.executable, '-u', '-B', HERE / 'check_gpio_fst.py', '--run', args.task0_run,
            '--profile', args.profile, '--native-reader', args.native_reader, '--out', audit0])
        run('task0_saif', [sys.executable, '-u', '-B', HERE / 'convert_fst.py', 'convert', '--run', args.task0_run,
            '--audit', audit0, '--profile', args.profile, '--native-exporter', args.native_exporter,
            '--probe-result', args.probe_result, '--out', args.state_dir / 'task0-saif'])
        wait_for('functional_cpu12', args.cpu12_result, 'PASS')
        ppa = args.state_dir / 'final-ppa-inputs'
        run('final_ppa_seal', [sys.executable, '-B', HERE.parent / 'ppa/storage/prepare.py',
            '--base', args.ppa_base, '--storage-candidate', args.storage_candidate,
            '--cpu-full12', args.cpu12_result, '--out', ppa])
        run('final_ppa_review', [sys.executable, '-B', ppa / 'run_once.py'])
        fullstate, fullrun, fullaudit = [args.state_dir / name for name in ('full12-supervisor', 'full12-run', 'full12-native-audit')]
        run('full12_launch', [sys.executable, '-u', '-B', HERE / 'launch_gpio_full12.py',
            '--state-dir', fullstate, '--run-out', fullrun, '--audit-out', fullaudit,
            '--replay-from', args.task0_run, '--vectors', args.vectors, '--profile', args.profile,
            '--native-reader', args.native_reader, '--baseline-result', args.cpu12_result, '--cpu', args.cpu])
        childlaunch = json.loads((fullstate / 'launch.json').read_text())
        childprocess = process(childlaunch['supervisor_pid'])
        launch['watched']['full12_activity'] = dict(state_path=str(fullstate / 'state.json'), process=childprocess)
        write(args.state_dir / 'launch.json', launch)
        expected = 'PASS_FULL12_PRODUCTION_N2_SAME_CYCLES_ALL374_GENERIC_ACTIVITY_NOT_POWER_READY'
        wait_for('full12_activity', fullstate / 'state.json', expected)
        for layer in range(12):
            run('full12_saif_%02d' % layer, [sys.executable, '-u', '-B', HERE / 'convert_fst.py', 'convert', '--run', fullrun,
                '--audit', fullaudit, '--profile', args.profile, '--native-exporter', args.native_exporter,
                '--probe-result', args.probe_result, '--layer', layer, '--out', args.state_dir / ('full12-saif-%02d' % layer)])
        state.update(status='PASS_FINAL374_COMPLETE12_SAME_FREEZE_GENERIC_ACTIVITY_SAIF_AND_OFFLINE_PPA_INPUTS_NO_POWER_PASS',
                     cpu12_result_sha256=sha(args.cpu12_result), final_ppa_package_files_sha256=sha(ppa / 'package-files.json'),
                     full12_activity_state_sha256=sha(fullstate / 'state.json'))
        return 0
    except Exception as error:
        state.update(status='FAIL', error=str(error), traceback=traceback.format_exc())
        traceback.print_exc()
        return 1
    finally:
        state.update(finished_at=now(), active_stage=None)
        write(statefile, state)


if __name__ == '__main__':
    raise SystemExit(main())
