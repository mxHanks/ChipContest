#!/usr/bin/env python3
"""Detach one production N2 GPIO activity replay and its mandatory native audit.

Never retries or overwrites a run. One simulator is pinned to one local CPU.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

HERE = Path(__file__).resolve().parent


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def write(path, value):
    temp = path.with_suffix(path.suffix + '.new')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temp.replace(path)


def now():
    return datetime.now(timezone.utc).isoformat()


def worker(args):
    state = dict(schema='compliant32-production-gpio-full12-activity-supervisor-v1', status='RUNNING',
        supervisor_pid=os.getpid(), session_id=os.getsid(0), started_at=now(), stages=[],
        policy='one pinned single-thread simulator, exact proven GPIO binary, no retries')
    target = args.state_dir / 'state.json'
    write(target, state)
    try:
        launch = json.loads((args.state_dir / 'launch.json').read_text())
        for filename, expected in launch['pinned_inputs'].items():
            if sha(Path(filename)) != expected:
                raise ValueError('GPIO supervisor input drift: ' + filename)
        if args.cpu not in os.sched_getaffinity(0):
            raise ValueError('selected CPU is outside available affinity')
        os.sched_setaffinity(0, {args.cpu})
        state['local_cpu_affinity'] = sorted(os.sched_getaffinity(0))
        proven = json.loads((args.replay_from / 'result.json').read_text())
        if (proven.get('schema') != 'compliant32-production-gpio-fullsoc-rtl-activity-v1' or
                proven.get('status') != 'PASS_RTL_ACTIVITY_WINDOW_NOT_POWER_READY' or
                proven.get('macro_scope', {}).get('actual_ramsp_instances', 0) < 353 or
                any('XU_SYSBUS_TEST_LOADER' in name for name in proven.get('definitions', []))):
            raise ValueError('requires completed exact-profile production N2 GPIO activity task0')
        actual = proven['macro_scope']['actual_ramsp_instances']
        if proven.get('activity_profile'):
            if not args.profile or sha(args.profile) != proven['activity_profile']['sha256']:
                raise ValueError('full12 must reuse the same exact macro profile')
        elif actual != 353 or args.profile:
            raise ValueError('nonlegacy macro layout requires explicit profile')
        profile_args = ['--profile', str(args.profile)] if args.profile else []
        commands = [
            ('simulation', [sys.executable, '-u', '-B', str(HERE / 'run_gpio_activity.py'),
                '--out', str(args.run_out), '--vectors', str(args.vectors), '--tasks', '12', '--jobs', '1',
                '--replay-from', str(args.replay_from), *profile_args]),
            ('native_audit', [sys.executable, '-u', '-B', str(HERE / ('check_gpio_fst.py' if args.profile else 'check_fst.py')),
                '--run', str(args.run_out), '--native-reader', str(args.native_reader), '--out', str(args.audit_out), *profile_args]),
        ]
        for label, command in commands:
            for filename, expected in launch['pinned_inputs'].items():
                if sha(Path(filename)) != expected:
                    raise ValueError('GPIO supervisor input drift before ' + label)
            stage = dict(stage=label, command=command, status='RUNNING', started_at=now())
            state['stages'].append(stage)
            state['active_stage'] = label
            with (args.state_dir / (label + '.log')).open('w') as stream:
                child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
                stage['pid'] = child.pid
                write(target, state)
                code = child.wait()
            stage.update(returncode=code, status='PASS' if code == 0 else 'FAIL', finished_at=now())
            write(target, state)
            if code:
                raise RuntimeError('GPIO ' + label + ' exited ' + str(code))
        run = json.loads((args.run_out / 'result.json').read_text())
        baseline = json.loads(args.baseline_result.read_text())
        measured = run['functional']
        if (baseline.get('status') != 'PASS' or baseline.get('schema') != 's3-compliant32-production-gpio-cpu-v1' or
                measured['outputs'] != 304128 or len(measured['layers']) != 12 or len(baseline['layers']) != 12):
            raise ValueError('missing complete production GPIO full12 CPU evidence')
        if run['definitions'] != baseline['definitions'] or run['ppa_binding'] != baseline['ppa_binding']:
            raise ValueError('GPIO production hardware configuration differs from no-trace full12')
        if run.get('storage_binding') != baseline.get('storage_binding'):
            raise ValueError('GPIO storage overlay differs from no-trace full12')
        for key in ('elf_sha256', 'image_sha256'):
            if run['firmware'][key] != baseline['firmware'][key]:
                raise ValueError('GPIO firmware differs from no-trace full12')
        if run['vector_byte_sha256'] != baseline['vector_byte_sha256']:
            raise ValueError('GPIO vectors differ from no-trace full12')
        fields = ('layer', 'rows', 'outputs', 'total', 'load_to_y', 'loading', 'clear', 'dma_payload')
        compared = []
        for measured_layer, reference in zip(measured['layers'], baseline['layers']):
            if any(measured_layer[key] != reference[key] for key in fields):
                raise ValueError('GPIO full12 per-layer count/cycle differs: ' + str(measured_layer['layer']))
            compared.append({key: measured_layer[key] for key in fields})
        if measured['total_cycles'] != baseline['total_cycles']:
            raise ValueError('GPIO full12 total cycles differ')
        audit = json.loads((args.audit_out / 'result.json').read_text())
        if audit['status'] != f'PASS_NATIVE_RANGE_ALL_{actual}_MACRO_PORTS_INITIALIZED_NOT_POWER_READY' or len(audit['layers']) != 12:
            raise ValueError('GPIO complete-profile macro native time/initial-value audit missing')
        state.update(status=f'PASS_FULL12_PRODUCTION_N2_SAME_CYCLES_ALL{actual}_GENERIC_ACTIVITY_NOT_POWER_READY',
            outputs=measured['outputs'], total_cycles=measured['total_cycles'],
            baseline_result_sha256=sha(args.baseline_result),
            functional_result_sha256=sha(args.run_out / 'result.json'), native_audit_sha256=sha(args.audit_out / 'result.json'),
            per_layer_baseline_comparison=compared,
            qualification='Generic RTL activity only; mapped annotation, valid timing and characterized SRAM power remain unproven')
    except Exception as error:
        state.update(status='FAIL', error=str(error), traceback=traceback.format_exc())
        traceback.print_exc()
        return 1
    finally:
        state.update(finished_at=now(), active_stage=None)
        write(target, state)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('state-dir', 'run-out', 'audit-out', 'replay-from', 'vectors', 'native-reader', 'baseline-result'):
        parser.add_argument('--' + option, type=Path, required=True)
    parser.add_argument('--cpu', type=int, required=True)
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    for name in ('state_dir', 'run_out', 'audit_out', 'replay_from', 'vectors', 'native_reader', 'baseline_result'):
        setattr(args, name, getattr(args, name).resolve())
    if args.profile:
        args.profile = args.profile.resolve()
    if args.worker:
        return worker(args)
    if args.state_dir.exists() or args.run_out.exists() or args.audit_out.exists():
        parser.error('all output paths must be new; inspect live process before any retry')
    args.state_dir.mkdir(parents=True)
    command = [sys.executable, '-u', '-B', str(Path(__file__).resolve()), *sys.argv[1:], '--worker']
    inputs = [Path(__file__).resolve(), HERE / 'run_gpio_activity.py', HERE / 'gpio_monitor.svh',
              HERE / 'gpio_trace_main.cpp', HERE / 'check_fst.py', HERE / 'activity_profile.py',
              HERE / 'check_gpio_fst.py', args.native_reader,
              args.baseline_result, args.replay_from / 'result.json']
    if args.profile:
        inputs.append(args.profile)
    launch = dict(status='PREPARED', created_at=now(), command=command,
                  pinned_inputs={str(path): sha(path) for path in inputs})
    write(args.state_dir / 'launch.json', launch)
    with (args.state_dir / 'supervisor.log').open('w') as stream:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                 start_new_session=True, close_fds=True)
    launch.update(status='LAUNCHED_NOT_COMPLETED', supervisor_pid=child.pid, session_policy='start_new_session=True')
    write(args.state_dir / 'launch.json', launch)
    print(json.dumps(dict(supervisor_pid=child.pid, state_file=str(args.state_dir / 'state.json'))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
