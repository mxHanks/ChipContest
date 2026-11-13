#!/usr/bin/env python3
"""Launch one independent local full12 activity supervisor, with no retries.

The separate session protects the job from a tool handle closing. It is not a
claim about the unexplained exit143 of the earlier attached 289-macro run.
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
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def now():
    return datetime.now(timezone.utc).isoformat()


def worker(args):
    state = dict(schema='compliant32-local-full12-activity-supervisor-v1', status='RUNNING',
                 supervisor_pid=os.getpid(), session_id=os.getsid(0), started_at=now(),
                 policy='one single-thread simulator, exact proven binary, no retries or overlapping output reuse', stages=[])
    target = args.state_dir / 'state.json'
    write(target, state)
    try:
        launch = json.loads((args.state_dir / 'launch.json').read_text())
        for path, digest in launch['pinned_tools'].items():
            if sha(Path(path)) != digest:
                raise ValueError('supervisor tool drift: ' + path)
        if args.cpu not in os.sched_getaffinity(0):
            raise ValueError('chosen CPU is outside available affinity')
        os.sched_setaffinity(0, {args.cpu})
        state['affinity'] = sorted(os.sched_getaffinity(0))
        previous = json.loads((args.replay_from / 'result.json').read_text())
        if (previous.get('status') != 'PASS_RTL_ACTIVITY_WINDOW_NOT_POWER_READY' or
                previous.get('macro_scope', {}).get('actual_ramsp_instances') != 353):
            raise ValueError('only a completed actual353 macro task0 may launch final full12')
        commands = [
            ('simulation', [sys.executable, '-u', '-B', str(HERE / 'run_activity.py'),
                '--out', str(args.run_out), '--vectors', str(args.vectors), '--tasks', '12',
                '--jobs', '1', '--replay-from', str(args.replay_from)]),
            ('native_audit', [sys.executable, '-u', '-B', str(HERE / 'check_fst.py'),
                '--run', str(args.run_out), '--native-reader', str(args.native_reader), '--out', str(args.audit_out)]),
        ]
        for label, command in commands:
            for path, digest in launch['pinned_tools'].items():
                if sha(Path(path)) != digest:
                    raise ValueError('supervisor tool drift before ' + label)
            record = dict(stage=label, command=command, started_at=now(), status='RUNNING')
            state['stages'].append(record)
            state['active_stage'] = label
            with (args.state_dir / (label + '.log')).open('w') as stream:
                child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
                record['pid'] = child.pid
                write(target, state)
                code = child.wait()
            record.update(returncode=code, finished_at=now(), status='PASS' if code == 0 else 'FAIL')
            write(target, state)
            if code:
                raise RuntimeError(label + ' terminated with ' + str(code))
        run = json.loads((args.run_out / 'result.json').read_text())
        baseline = json.loads(args.baseline_result.read_text())
        measured = run['functional']
        if baseline.get('status') != 'PASS' or measured['outputs'] != 304128 or len(measured['layers']) != 12:
            raise ValueError('missing complete12 CPU outputs')
        for key in ('elf_sha256', 'image_sha256'):
            if run['firmware'][key] != baseline['firmware'][key]:
                raise ValueError('CPU firmware differs from full12 no-trace baseline')
        if run['vector_byte_sha256'] != baseline['vector_byte_sha256']:
            raise ValueError('vector identity differs from full12 no-trace baseline')
        fields = ('layer', 'rows', 'outputs', 'total', 'load_to_y', 'loading', 'clear', 'dma_payload')
        compared = []
        for actual, reference in zip(measured['layers'], baseline['layers']):
            if any(actual[key] != reference[key] for key in fields):
                raise ValueError('per-layer cycle/count differs from no-trace baseline: ' + str(actual['layer']))
            compared.append({key: actual[key] for key in fields})
        if measured['total_cycles'] != baseline['total_cycles']:
            raise ValueError('complete12 cycle count differs')
        audit = json.loads((args.audit_out / 'result.json').read_text())
        if audit['status'] != 'PASS_NATIVE_RANGE_ALL_353_MACRO_PORTS_INITIALIZED_NOT_POWER_READY' or len(audit['layers']) != 12:
            raise ValueError('missing complete12 native all353 port audit')
        state.update(status='PASS_FULL12_SAME_CYCLES_ALL353_GENERIC_PORT_ACTIVITY_NOT_POWER_READY',
            outputs=measured['outputs'], total_cycles=measured['total_cycles'],
            baseline_result_sha256=sha(args.baseline_result), functional_result_sha256=sha(args.run_out / 'result.json'),
            native_audit_sha256=sha(args.audit_out / 'result.json'), per_layer_baseline_comparison=compared,
            qualification='Generic RTL activity and functional cycles only; mapped annotations, vendor SRAM power and qualification remain pending')
    except Exception as error:
        state.update(status='FAIL', error=str(error), traceback=traceback.format_exc())
        traceback.print_exc()
        return 1
    finally:
        state['finished_at'] = now()
        state['active_stage'] = None
        write(target, state)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('state-dir', 'run-out', 'audit-out', 'replay-from', 'vectors', 'native-reader', 'baseline-result'):
        parser.add_argument('--' + option, type=Path, required=True)
    parser.add_argument('--cpu', type=int, default=1)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    for key in ('state_dir', 'run_out', 'audit_out', 'replay_from', 'vectors', 'native_reader', 'baseline_result'):
        setattr(args, key, getattr(args, key).resolve())
    if args.worker:
        return worker(args)
    if args.state_dir.exists() or args.run_out.exists() or args.audit_out.exists():
        parser.error('supervisor, run and audit output paths must all be new')
    args.state_dir.mkdir(parents=True)
    command = [sys.executable, '-u', '-B', str(Path(__file__).resolve()), *sys.argv[1:], '--worker']
    pinned = [Path(__file__).resolve(), HERE / 'run_activity.py', HERE / 'check_fst.py', args.native_reader,
              args.baseline_result, args.replay_from / 'result.json']
    launch = dict(status='PREPARED', created_at=now(), command=command,
                  pinned_tools={str(path): sha(path) for path in pinned})
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
