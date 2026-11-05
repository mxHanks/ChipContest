#!/usr/bin/env python3
"""Launch the new read-only123 extraction once; never restart an existing run."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

EXPECTED = '688aa9aa49b85c08d493e9cf50b150376f311acfa07bfa0245d80c14c100b4e9'
base = Path.home() / 'Desktop/xu-score-optimization-20261102'
source = Path.home() / 'Desktop/xu_mapped_connectivity123.py'
out = base / 'mapped-connectivity-20261105-123'
launch = base / 'mapped-connectivity-launch-20261105-123'
if out.exists() or launch.exists():
    raise ValueError('existing123 output/launch: observe it; do not restart')
if hashlib.sha256(source.read_bytes()).hexdigest() != EXPECTED:
    raise ValueError('connectivity123 uploaded source differs')
launch.mkdir(parents=True, exist_ok=False)
command = [sys.executable, '-u', str(source), '--out', str(out)]
with (launch / 'driver.log').open('xb') as log:
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                               stderr=subprocess.STDOUT, start_new_session=True)
receipt = dict(status='LAUNCHED_READ_ONLY123_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
               pid=process.pid, launcher_pid=os.getpid(), started_epoch=time.time(),
               command=command, source_sha256=EXPECTED, output=str(out))
(launch / 'state.json').write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
print('XU_CONNECTIVITY123_LAUNCHED pid=' + str(process.pid) + ' NOT_QUALIFIED', flush=True)
