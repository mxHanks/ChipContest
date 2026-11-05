#!/usr/bin/env python3
"""One-shot frozen xu134 launcher. No restart, overwrite, or remote operations."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
BASE=Path.home()/'Desktop/xu-score-optimization-20261102'
EXPECTED={'xu_s2e_timing134.py':'39eff5564db15f5fb2724ca9f1fb0e0b6141d5abb32fbdc74f7fd76a5eade621','reset134.tcl':'8e50f0559a0f443cc4359b28cf55d7e0e54e6778ca8490bce4aac91b157ac33c'}
OUTPUT=BASE/'s2e-own-timing-repair-20261105-134'
LAUNCH=BASE/'s2e-own-timing-repair-launch-20261105-134'
if len(sys.argv)!=1:raise SystemExit('No arguments accepted; no process spawned')
for name,digest in EXPECTED.items():
    path=HERE/name
    if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
        raise SystemExit('Frozen134 bundle differs: '+name+'; no process spawned')
if OUTPUT.exists() or LAUNCH.exists():raise SystemExit('134 output/launch exists; observe recorded job, never restart')
# Complete the read-only source/own89/109 freeze check before creating outputs.
check=subprocess.run([sys.executable,str(HERE/'xu_s2e_timing134.py'),'--preflight-only'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
if check.returncode:raise SystemExit('134 preflight rejected; no process spawned\n'+check.stderr)
LAUNCH.mkdir()
state=dict(status='PREPARING_NOT_QUALIFIED',qualification='NOT_QUALIFIED',started_epoch=time.time(),bundle=EXPECTED,output=str(OUTPUT),preflight=json.loads(check.stdout))
def save():
    temp=LAUNCH/'state.json.tmp';temp.write_text(json.dumps(state,sort_keys=True,indent=2)+'\n');os.replace(str(temp),str(LAUNCH/'state.json'))
save()
try:
    command=[sys.executable,'-u',str(HERE/'xu_s2e_timing134.py')]
    with (LAUNCH/'driver.log').open('xb') as log:
        process=subprocess.Popen(command,cwd=str(HERE),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    state.update(status='SPAWNED_NOT_EXECUTION_COMPLETION_NOT_QUALIFIED',pid=process.pid,command=command)
except BaseException as error:
    state.update(status='LAUNCH_FAILED_NOT_QUALIFIED',error=type(error).__name__+': '+str(error));save();raise
save()
print('XU_S2E_TIMING134_STARTED pid=%d NOT_QUALIFIED'%process.pid)
