#!/usr/bin/env python3
"""Detached one-shot production GPIO activity runner; no retries or EDA."""
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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('runner_arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    args.state_dir = args.state_dir.resolve()
    target = args.state_dir / 'state.json'
    if args.worker:
        state = dict(status='RUNNING', started_at=now(), supervisor_pid=os.getpid(), session_id=os.getsid(0))
        write(target, state)
        try:
            launch = json.loads((args.state_dir / 'launch.json').read_text())
            for name, digest in launch['pinned_tools'].items():
                if sha(Path(name)) != digest:
                    raise ValueError('GPIO activity tool changed: ' + name)
            with (args.state_dir / 'runner.log').open('w') as stream:
                child = subprocess.Popen(launch['runner_command'], stdin=subprocess.DEVNULL,
                                         stdout=stream, stderr=subprocess.STDOUT)
                state['runner_pid'] = child.pid
                write(target, state)
                code = child.wait()
            state.update(status='PASS' if code == 0 else 'FAIL', returncode=code)
            return code
        except Exception as error:
            state.update(status='FAIL', error=str(error), traceback=traceback.format_exc())
            traceback.print_exc()
            return 1
        finally:
            state['finished_at'] = now()
            write(target, state)
    if args.state_dir.exists():
        parser.error('state directory must be new; never restart a job on an observation timeout')
    args.state_dir.mkdir(parents=True)
    forwarded = args.runner_arguments
    if forwarded and forwarded[0] == '--':
        forwarded = forwarded[1:]
    command = [sys.executable, '-u', '-B', str(HERE / 'run_gpio_activity.py'), *forwarded]
    tools = [Path(__file__), HERE / 'run_gpio_activity.py', HERE / 'gpio_monitor.svh',
             HERE / 'gpio_trace_main.cpp', HERE / 'activity_profile.py']
    launch = dict(status='PREPARED', created_at=now(), runner_command=command,
                  pinned_tools={str(path.resolve()): sha(path) for path in tools},
                  policy='one independent session; max1 build job, one pinned simulator, no retries')
    write(args.state_dir / 'launch.json', launch)
    with (args.state_dir / 'supervisor.log').open('w') as stream:
        child = subprocess.Popen([sys.executable, '-u', '-B', str(Path(__file__).resolve()),
            '--state-dir', str(args.state_dir), '--worker'], stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    launch.update(status='LAUNCHED_NOT_COMPLETED', supervisor_pid=child.pid)
    write(args.state_dir / 'launch.json', launch)
    print(json.dumps(dict(supervisor_pid=child.pid, state_file=str(target))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
