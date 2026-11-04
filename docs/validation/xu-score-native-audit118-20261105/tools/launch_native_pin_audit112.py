#!/usr/bin/env python3
"""Spawn one new read-only audit; a launch receipt is not audit completion."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

SCRIPT_SHA = 'b878d55ca38fb13a87853a46e69d5d221bb23d1af3a14b10020ec3eb7bbfa6ae'
desktop = Path.home() / 'Desktop'
base = desktop / 'xu-score-optimization-20261102'
script = desktop / 'xu_native_pin_audit112.py'
campaign = base / 's2c-full-soc-power12-20261104-57'
native = base / 's2c-native-pin-stream-20261104-93'
output = base / 's2c-native-pin-audit-20261104-112'
launch = base / 's2c-native-pin-audit-launch-20261104-112'
if hashlib.sha256(script.read_bytes()).hexdigest() != SCRIPT_SHA:
    raise SystemExit('audit112 script SHA differs; no process spawned')
if launch.exists() or output.exists():
    raise SystemExit('audit112 launch/output exists; observe it, do not restart')
if not campaign.is_dir() or not native.is_dir():
    raise SystemExit('original campaign or completed extractor directory absent')
source_state = json.loads((native / 'state.json').read_text())
if source_state.get('status') != 'EXTRACTED_24_ORIGINAL_REPORTS_NOT_QUALIFIED':
    raise SystemExit('extractor93 not terminal; no process spawned')
launch.mkdir()
state = dict(status='PREPARING_NOT_AUDIT_COMPLETION', qualification='NOT_QUALIFIED',
             script_sha256=SCRIPT_SHA, output=str(output))


def write():
    (launch / 'state.json').write_text(json.dumps(state, sort_keys=True, indent=2) + '\n')


write()
try:
    command = [sys.executable, '-u', str(script), '--campaign', str(campaign),
               '--native-root', str(native), '--output', str(output)]
    with (launch / 'driver.log').open('wb') as log:
        process = subprocess.Popen(command, cwd=str(desktop), stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    state.update(status='SPAWNED_NOT_AUDIT_COMPLETION', pid=process.pid, command=command)
except BaseException as error:
    state.update(status='LAUNCH_FAILED', error=type(error).__name__ + ': ' + str(error))
    write()
    raise
write()
print('XU_AUDIT112_SPAWNED pid=%d NOT_QUALIFIED; inspect output state for completion' % process.pid)
