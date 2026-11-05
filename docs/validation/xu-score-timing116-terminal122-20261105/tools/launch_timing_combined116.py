#!/usr/bin/env python3
"""Launch the frozen independent116 worker once; inspect its own terminal state."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

WORKER_SHA = '8b6a464d94377a5df8bc1fac78b61eae1e5852c801ff453be2b8d4937d29d860'
desktop = Path.home() / 'Desktop'
base = desktop / 'xu-score-optimization-20261102'
worker = desktop / 'xu_timing_combined116.py'
output = base / 'full-soc-timing-combined-20261105-116'
launch = base / 'full-soc-timing-combined-launch-20261105-116'
if len(sys.argv) != 1:
    raise SystemExit('no arguments accepted; no process spawned')
if hashlib.sha256(worker.read_bytes()).hexdigest() != WORKER_SHA:
    raise SystemExit('116 worker SHA differs; no process spawned')
if output.exists() or launch.exists():
    raise SystemExit('116 output/launch exists; observe the recorded job, do not restart')
parent = base / 'full-soc-unloaded-cell-cleanup-20261104-95'
if hashlib.sha256((parent / 'state.json').read_bytes()).hexdigest() != '3d65d7a3c4753961a331bd9a69121c93cd504639cd409c6dfca5784e44779aca':
    raise SystemExit('actual95 state differs; no process spawned')
launch.mkdir()
state = dict(status='PREPARING_NOT_EXECUTION_COMPLETION', qualification='NOT_QUALIFIED',
             worker_sha256=WORKER_SHA, output=str(output))


def write():
    (launch / 'state.json').write_text(json.dumps(state, sort_keys=True, indent=2) + '\n')


write()
try:
    command = [sys.executable, '-u', str(worker)]
    with (launch / 'driver.log').open('xb') as log:
        process = subprocess.Popen(command, cwd=str(desktop), stdout=log,
                                   stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                   start_new_session=True)
    state.update(status='SPAWNED_NOT_EXECUTION_COMPLETION', pid=process.pid, command=command)
except BaseException as error:
    state.update(status='LAUNCH_FAILED_NOT_QUALIFIED', error=type(error).__name__ + ': ' + str(error))
    write()
    raise
write()
print('XU_COMBINED116_STARTED pid=%d NOT_QUALIFIED; inspect output state' % process.pid)
