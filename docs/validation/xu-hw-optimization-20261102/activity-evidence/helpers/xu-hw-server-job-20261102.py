#!/usr/bin/env python3
"""Restore pinned xu hardware source into an independent server copy and run campaign."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

desktop=Path.home()/'Desktop'
base=desktop/'xu-hw-optimization-20261102'
old=desktop/'xu-fw-optimization-20261102/ChipContest'
repo=base/'ChipContest'
out=base/'xu-vcs-hw-campaign-01'
main_sha='97b35421dfbbfa8f4d495b6927a7c66610ff8206'
sub_sha='f49a5fc914971426bd4530db39e270a84b41139f'
bundles=[('xu-hw-main-97b3542.bundle','ce1fa1cb5c12708b788a146d02844f6047737bbb862a62a05252807ecaeb53d6'),
         ('xu-hw-e203-f49a5fc.bundle','e8fe26006aec48c11e91caf368d940723b176bafee17e3c3f7134e55feb64dd4')]


def run(arguments,cwd=None):
    subprocess.check_call(arguments,cwd=str(cwd) if cwd else None)


def query(arguments,cwd):
    return subprocess.check_output(arguments,cwd=str(cwd)).decode().strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


action=sys.argv[1]
if action=='setup':
    for name,expected in bundles:
        if sha(desktop/name)!=expected:raise ValueError('bundle hash mismatch: '+name)
    base.mkdir(exist_ok=True)
    if repo.exists():raise ValueError('new hardware repository already exists')
    run(['git','clone','--no-hardlinks','--no-checkout',str(old),str(repo)])
    run(['git','fetch',str(desktop/bundles[0][0]),'codex/xu-optimize-hw:refs/heads/codex/xu-optimize-hw'],repo)
    run(['git','checkout','codex/xu-optimize-hw'],repo)
    sub=repo/'third-party/e203_hbirdv2'
    if sub.exists():sub.rmdir()
    run(['git','clone','--no-hardlinks','--no-checkout',str(old/'third-party/e203_hbirdv2'),str(sub)])
    run(['git','fetch',str(desktop/bundles[1][0]),'codex/xu-optimize-hw:refs/heads/codex/xu-optimize-hw'],sub)
    run(['git','checkout','codex/xu-optimize-hw'],sub)
    run(['git','submodule','init'],repo)
    if query(['git','rev-parse','HEAD'],repo)!=main_sha or query(['git','rev-parse','HEAD'],sub)!=sub_sha:
        raise ValueError('pinned checkout mismatch')
    if query(['git','ls-tree','HEAD','third-party/e203_hbirdv2'],repo).split()[2]!=sub_sha:
        raise ValueError('gitlink mismatch')
    for directory in [repo,sub]:
        if query(['git','status','--porcelain'],directory):raise ValueError('new checkout is not clean')
    print('SETUP_PASS main='+main_sha+' e203='+sub_sha+' clean=true no_hardlinks=true',flush=True)
elif action=='start':
    state=base/'hw-job-state.json'
    log=base/'hw-job.log'
    if state.exists() or log.exists() or out.exists():raise ValueError('refusing to reuse hardware job output')
    with log.open('x') as stream:
        p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'execute'],stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    print('STARTED hardware campaign pid='+str(p.pid),flush=True)
elif action=='execute':
    prefix=str(desktop/'xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-')
    command=[sys.executable,'tools/scripts/xu_hw_experiments.py','--sim','vcs','--cross-prefix',prefix,'--out',str(out),'--accept']
    state=dict(status='RUNNING',command=command,started_epoch=time.time(),main_commit=main_sha,e203_commit=sub_sha)
    target=base/'hw-job-state.json'
    target.write_text(json.dumps(state,indent=2)+'\n')
    try:
        p=subprocess.run(command,cwd=str(repo),timeout=172800)
        state.update(status='PASS' if p.returncode==0 else 'FAIL',returncode=p.returncode)
    except Exception as error:state.update(status='FAIL',error=str(error))
    state['finished_epoch']=time.time()
    target.write_text(json.dumps(state,indent=2)+'\n')
    print('HARDWARE_JOB_'+state['status'],flush=True)
elif action=='status':
    path=base/'hw-job-state.json'
    if path.exists():print(path.read_text())
    path=base/'hw-job.log'
    if path.exists():print(path.read_text(errors='replace')[-2000:])
else:raise ValueError('unknown action')
