#!/usr/bin/env python3
"""One-time original-host deployment; daily entry remains xu_experiments.py."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
BASE=Path.home()/'Desktop/xu-score-optimization-20261102'
OUT=BASE/'unified-experiment-control-20261105-150'
EXPECTED='d7813ac3745ff1aa5b5efc92eef298a6577abef774259f9285aae605c466db2f'
assert not OUT.exists(),'Existing controller must be observed/resumed, never overwritten'
assert hashlib.sha256((HERE/'xu_experiments.py').read_bytes()).hexdigest()==EXPECTED
spec=importlib.util.spec_from_file_location('xu150',str(HERE/'xu_experiments.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
for p in sorted((HERE/'jobs').glob('*.json')):m.validate_job(m.read(p))
assert len(list((HERE/'jobs').glob('*.json')))==4
m.initialize(OUT)
for p in sorted((HERE/'jobs').glob('*.json')):m.register(OUT,p)
command=[sys.executable,'-B',str(HERE/'xu_experiments.py'),'run','--out',str(OUT)]
with (OUT/'controller.log').open('xb') as f:
    process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
m.save(OUT/'controller-launch.json',dict(pid=process.pid,argv=command,started_epoch=time.time(),qualification='NOT_QUALIFIED',status='SPAWNED_NOT_EXECUTION_COMPLETION'))
print('XU150_UNIFIED_CONTROLLER_STARTED',process.pid,flush=True)
