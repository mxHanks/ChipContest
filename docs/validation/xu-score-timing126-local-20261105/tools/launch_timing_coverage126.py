#!/usr/bin/env python3
"""Launch one new read-only126; never overwrite/restart an existing run."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

B=Path.home()/'Desktop/xu-score-optimization-20261102'
WORKER=Path.home()/'Desktop/xu_timing_coverage126.py'
OUT=B/'full-soc-coverage-rdc-20261105-126'
LAUNCH=B/'full-soc-coverage-rdc-launch-20261105-126'
EXPECTED_WORKER='64de7a24a25e03a6c132f844747fa059618c4a8c85c1b84da95838a7e1c2438a'
EXPECTED_STATE='7da5adb892fcaa33b5876e4f8dcbd9467a09dd8b40687476de529d1f7bf3c84f'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def main():
    if OUT.exists() or LAUNCH.exists():raise ValueError('existing126 output/launcher; observe original PID/state, never restart')
    if sha(WORKER)!=EXPECTED_WORKER:raise ValueError('frozen126 worker differs')
    parent=B/'full-soc-timing-combined-20261105-116/state.json'
    if sha(parent)!=EXPECTED_STATE:raise ValueError('exact actual116 terminal state differs')
    if json.loads(parent.read_text()).get('status')!='EXECUTED_SAME_MAPPED_DC_PT_AND_FULL_FM_NOT_QUALIFIED':
        raise ValueError('actual116 own DC/PT/FM terminal required')
    LAUNCH.mkdir(exist_ok=False)
    state=dict(status='LAUNCHING_NOT_EXECUTION_COMPLETION',qualification='NOT_QUALIFIED',launcher_pid=os.getpid(),
               worker=str(WORKER),worker_sha256=EXPECTED_WORKER,parent_state_sha256=EXPECTED_STATE,
               output=str(OUT),started_epoch=time.time())
    def save():(LAUNCH/'state.json').write_text(json.dumps(state,sort_keys=True,indent=2)+'\n')
    save()
    try:
        with (LAUNCH/'driver.log').open('xb') as log:
            process=subprocess.Popen([sys.executable,'-u',str(WORKER)],stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        state.update(status='SPAWNED_NOT_EXECUTION_COMPLETION',worker_pid=process.pid,finished_epoch=time.time());save()
        print('XU_COVERAGE126_SPAWNED pid=%d NOT_QUALIFIED'%process.pid,flush=True)
    except BaseException as error:
        state.update(status='LAUNCH_FAILED_NOT_QUALIFIED',error=repr(error),finished_epoch=time.time());save();raise


if __name__=='__main__':main()
