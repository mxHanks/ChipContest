#!/usr/bin/env python3
"""xu173: one foreground, same-PID call to the SHA-frozen readonly exporter171."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback

D=Path.home()/'Desktop'
B=D/'xu-score-optimization-20261102'
OUT=B/'two-candidate-autopack-20261105-173'
ARCHIVE=B/'xu-server-two-candidate-20261105-171.tar.xz'
EXPORTER=D/'exporter171.py'
EXPORTER_SHA='9c72cfa8ef45b0b2cfba865af1914728077e63a4fb62c940ad7dacaa81300263'
SUCCESS='EXPORTED_TWO_CANDIDATE_PACKAGE_NOT_QUALIFIED'
FAIL='FAIL_AUTOPACK173_NOT_QUALIFIED'


def need(ok,message):
    if not ok:raise ValueError(message)


def identity(path):
    p=Path(path).absolute();need(p.is_file()and not p.is_symlink(),'regular non-symlink file required: '+str(p))
    h=hashlib.sha256()
    with p.open('rb')as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def save(path,value):
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('x')as f:
        f.write(json.dumps(value,sort_keys=True,indent=2)+'\n');f.flush();os.fsync(f.fileno())
    os.replace(str(temporary),str(path))
    fd=os.open(str(path.parent),os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def load_exporter():
    row=identity(EXPORTER);need(row['sha256']==EXPORTER_SHA,'frozen exporter171 SHA differs')
    spec=importlib.util.spec_from_file_location('xu173_frozen_exporter171',str(EXPORTER))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def run(out):
    out=Path(out).absolute();need(out==OUT,'only the fixed173 output root is supported')
    need(not out.exists()and not out.is_symlink(),'fresh173 output required; never overwrite or restart')
    need(B.is_dir()and not B.is_symlink(),'original campaign directory required')
    out.mkdir()
    state=dict(schema='xu-two-candidate-autopack173-state-v1',status='RUNNING_AUTOPACK173_NOT_QUALIFIED',
        qualification='NOT_QUALIFIED',pid=os.getpid(),started_epoch=time.time(),command=list(sys.argv),
        archive_path=str(ARCHIVE),same_python_process=True,new_experiments_launched=0,
        source_semantics='171 live evidence snapshots only; no terminal freeze or qualification inferred')
    save(out/'state.json',state)
    try:
        inputs=[identity(Path(__file__).resolve()),identity(EXPORTER)]
        need(inputs[1]['sha256']==EXPORTER_SHA,'frozen exporter171 SHA differs')
        state['inputs_before']=inputs;save(out/'state.json',state)
        need(not ARCHIVE.exists()and not ARCHIVE.is_symlink(),'fresh171 archive required; original package preserved')
        module=load_exporter()
        result=module.export(B,D,ARCHIVE,16*1024*1024)
        after=[identity(Path(row['path']))for row in inputs]
        actual=identity(ARCHIVE)
        state.update(inputs_after=after,inputs_equal_before_after=after==inputs,
            exporter_result=result,archive=actual,exporter_returned_epoch=time.time())
        need(after==inputs,'frozen173/171 input changed during export')
        need(all(result.get(k)==actual[k]for k in ['path','bytes','sha256']),'exporter result differs from actual final package bytes')
        need(state['pid']==os.getpid(),'same Python process required')
        state.update(status=SUCCESS,finished_epoch=time.time());save(out/'state.json',state)
        print('XU173_TERMINAL '+SUCCESS+' '+json.dumps(actual,sort_keys=True),flush=True);return 0
    except BaseException as error:
        state.update(status=FAIL,error=type(error).__name__+': '+str(error),traceback=traceback.format_exc(),finished_epoch=time.time())
        if 'inputs_before'in state:
            try:
                state['inputs_after']=[identity(Path(row['path']))for row in state['inputs_before']]
                state['inputs_equal_before_after']=state['inputs_after']==state['inputs_before']
            except BaseException as followup:state['identity_recheck_error']=type(followup).__name__+': '+str(followup)
        save(out/'state.json',state)
        print('XU173_TERMINAL '+FAIL+' '+state['error'],file=sys.stderr,flush=True);return 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();return run(args.out)


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError)as error:
        print('XU173_TERMINAL '+FAIL+' '+type(error).__name__+': '+str(error),file=sys.stderr,flush=True);sys.exit(1)
