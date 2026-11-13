#!/usr/bin/env python3
"""Detached one-shot supervisor for production-GPIO CPU evidence; never retries."""
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


def write(path, value):
    temp = path.with_suffix('.new')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temp.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--followups', action='store_true', help='Run the serial same-binary full12 and wait31 followups')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('runner_arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    args.state_dir = args.state_dir.resolve()
    target = args.state_dir / 'state.json'
    if args.worker:
        state = dict(status='RUNNING', supervisor_pid=os.getpid(), session_id=os.getsid(0), started_at=now())
        write(target, state)
        try:
            launch = json.loads((args.state_dir / 'launch.json').read_text())
            for name, expected in launch['pinned_tools'].items():
                if digest(Path(name)) != expected:
                    raise ValueError('supervisor input changed: ' + name)
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
        parser.error('state directory must be new; never restart an unverified live job')
    args.state_dir.mkdir(parents=True)
    forwarded = args.runner_arguments
    if forwarded and forwarded[0] == '--':
        forwarded = forwarded[1:]
    runner = HERE / ('run_followups.py' if args.followups else 'run_cpu.py')
    command = [sys.executable, '-u', '-B', str(runner), *forwarded]
    pinned = {str(path): digest(path) for path in sorted(HERE.iterdir()) if path.is_file()}
    launch = dict(status='PREPARED', created_at=now(), runner_command=command, pinned_tools=pinned,
                  policy='one new isolated session, maximum 1 local build CPU, no retries')
    write(args.state_dir / 'launch.json', launch)
    with (args.state_dir / 'supervisor.log').open('w') as stream:
        child = subprocess.Popen([sys.executable, '-u', '-B', str(HERE / 'launch.py'),
            '--state-dir', str(args.state_dir), '--worker'], stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    launch.update(status='LAUNCHED_NOT_COMPLETED', supervisor_pid=child.pid)
    write(args.state_dir / 'launch.json', launch)
    print(json.dumps(dict(supervisor_pid=child.pid, state_file=str(target))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
