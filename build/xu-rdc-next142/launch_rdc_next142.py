#!/usr/bin/env python3
"""Launch one new read-only142; never overwrite/restart an existing run."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

B=Path.home()/'Desktop/xu-score-optimization-20261102'
WORKER=Path.home()/'Desktop/xu_rdc_next142.py'
OUT=B/'full-soc-rdc-next-20261105-142'
LAUNCH=B/'full-soc-rdc-next-launch-20261105-142'
EXPECTED_WORKER='b004c17af3370f5a872c91cd71dfd93fbefeb772e17139e51ac35a642c39a4e7'
EXPECTED_STATE='7da5adb892fcaa33b5876e4f8dcbd9467a09dd8b40687476de529d1f7bf3c84f'
EXPECTED_132_STATE='2f6b6147e384851f194c1f46cb21dfb8c574d1ea3abab136f80d32bd2a21a5b5'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def main():
    if OUT.exists() or LAUNCH.exists():raise ValueError('existing142 output/launcher; observe original PID/state, never restart')
    if sha(WORKER)!=EXPECTED_WORKER:raise ValueError('frozen142 worker differs')
    parent=B/'full-soc-timing-combined-20261105-116/state.json'
    if sha(parent)!=EXPECTED_STATE:raise ValueError('exact actual116 terminal state differs')
    if json.loads(parent.read_text()).get('status')!='EXECUTED_SAME_MAPPED_DC_PT_AND_FULL_FM_NOT_QUALIFIED':
        raise ValueError('actual116 own DC/PT/FM terminal required')
    actual132=B/'full-soc-coverage-rdc-20261105-132/state.json'
    if sha(actual132)!=EXPECTED_132_STATE:raise ValueError('exact actual132 terminal state differs')
    LAUNCH.mkdir(exist_ok=False)
    state=dict(status='LAUNCHING_NOT_EXECUTION_COMPLETION',qualification='NOT_QUALIFIED',launcher_pid=os.getpid(),
               worker=str(WORKER),worker_sha256=EXPECTED_WORKER,parent_state_sha256=EXPECTED_STATE,actual132_state_sha256=EXPECTED_132_STATE,
               output=str(OUT),started_epoch=time.time())
    def save():(LAUNCH/'state.json').write_text(json.dumps(state,sort_keys=True,indent=2)+'\n')
    save()
    try:
        with (LAUNCH/'driver.log').open('xb') as log:
            process=subprocess.Popen([sys.executable,'-u',str(WORKER)],stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        state.update(status='SPAWNED_NOT_EXECUTION_COMPLETION',worker_pid=process.pid,finished_epoch=time.time());save()
        print('XU_RDC142_SPAWNED pid=%d NOT_QUALIFIED'%process.pid,flush=True)
    except BaseException as error:
        state.update(status='LAUNCH_FAILED_NOT_QUALIFIED',error=repr(error),finished_epoch=time.time());save();raise


if __name__=='__main__':main()
