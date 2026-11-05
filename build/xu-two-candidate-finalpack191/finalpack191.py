#!/usr/bin/env python3
"""xu191: final S2e/S2c diagnostic snapshot, no new EDA or experiment writes."""
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
OUT=B/'two-candidate-finalpack-20261105-191'
ARCHIVE=B/'xu-server-two-candidate-final-20261105-191.tar.xz'
EXPORTER=D/'exporter171.py'
EXPORTER_SHA='9c72cfa8ef45b0b2cfba865af1914728077e63a4fb62c940ad7dacaa81300263'
SUCCESS='EXPORTED_TWO_CANDIDATE_FINAL191_NOT_QUALIFIED'
FAIL='FAIL_FINALPACK191_NOT_QUALIFIED'
JOBS=['s2c_readonly177','s2e_coverage186','s2c_common_preflight190','s2c_common_full12_190']
ROOTS=['s2c-own9c16-readonly-20261105-177',
       's2e-own155-coverage-readonly-20261105-186',
       's2c-common-scope-preflight-20261105-190',
       's2c-common-scope-power12-20261105-190']


def select191(s):
    """Fixed relation/diagnostic reports only; no model/library/RTL body paths."""
    control=s.base/'unified-experiment-control-20261105-150'
    s.names(control,control.name,['state.json','events.jsonl','SUMMARY.md','config.json'])
    for job in JOBS:
        s.add(control/'registrations'/(job+'.json'),control.name+'/registrations/'+job+'.json')
        s.tree(control/'runs'/job,control.name+'/runs/'+job,{'.json','.jsonl','.log','.txt'})
    for root in ROOTS:
        directory=s.base/root
        if not directory.exists():
            s.missing.append(dict(path=str(directory),archive_path=root,kind='optional_directory'))
            continue
        # Preserve Snapshot's source symlink/path guards for directories and files.
        s.checked_source(directory,s.base)
        need(not directory.is_symlink(),'source root symlink rejected')
        for folder,dirs,files in os.walk(str(directory),followlinks=False):
            clean=[]
            for name in sorted(dirs):
                p=Path(folder)/name
                if name in {'.git','__pycache__'}:continue
                if p.is_symlink():
                    s.rejected.append(dict(source_path=str(p),error='source directory symlink'))
                else:clean.append(name)
            dirs[:]=clean
            for name in sorted(files):
                p=Path(folder)/name
                if p.suffix not in {'.json','.jsonl','.log','.txt','.tsv','.csv','.tcl','.rpt'}:continue
                s.add(p,root+'/'+str(p.relative_to(directory)),
                      omit=name in ['sram-pins-before.rpt','sram-pins-after.rpt'])
    s.add(Path(__file__).resolve(),'desktop/xu-two-candidate-finalpack191/finalpack191.py',s.desktop)
    s.generated('selection191.json',dict(schema='xu-final191-selection-v1',qualification='NOT_QUALIFIED',
        jobs=JOBS,roots=ROOTS,selector=identity(Path(__file__).resolve()),
        note='Only diagnostic relation reports; missing/failed stages retained, no qualification inferred.'))
    if s.rejected:
        save(OUT/'source-rejections191.json',dict(schema='xu-final191-source-rejections-v1',
            qualification='NOT_QUALIFIED',rejected_sources=s.rejected,
            note='No archive published; diagnostic source paths retained for review.'))
        raise ValueError('rejected diagnostic source; inspect source-rejections191.json')


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
    spec=importlib.util.spec_from_file_location('xu191_frozen_exporter171',str(EXPORTER))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.select=select191;module.JOBS=list(JOBS)
    return module


def run(out):
    out=Path(out).absolute();need(out==OUT,'only the fixed191 output root is supported')
    need(not out.exists()and not out.is_symlink(),'fresh191 output required; never overwrite or restart')
    need(B.is_dir()and not B.is_symlink(),'original campaign directory required')
    out.mkdir()
    state=dict(schema='xu-two-candidate-finalpack191-state-v1',status='RUNNING_FINALPACK191_NOT_QUALIFIED',
        qualification='NOT_QUALIFIED',pid=os.getpid(),started_epoch=time.time(),command=list(sys.argv),
        archive_path=str(ARCHIVE),same_python_process=True,new_experiments_launched=0,
        source_semantics='171 live evidence snapshots only; no terminal freeze or qualification inferred')
    save(out/'state.json',state)
    try:
        inputs=[identity(Path(__file__).resolve()),identity(EXPORTER)]
        need(inputs[1]['sha256']==EXPORTER_SHA,'frozen exporter171 SHA differs')
        state['inputs_before']=inputs;save(out/'state.json',state)
        need(not ARCHIVE.exists()and not ARCHIVE.is_symlink(),'fresh191 archive required; original package preserved')
        module=load_exporter()
        result=module.export(B,D,ARCHIVE,16*1024*1024)
        after=[identity(Path(row['path']))for row in inputs]
        actual=identity(ARCHIVE)
        state.update(inputs_after=after,inputs_equal_before_after=after==inputs,
            exporter_result=result,archive=actual,exporter_returned_epoch=time.time())
        need(after==inputs,'frozen191/171 input changed during export')
        need(all(result.get(k)==actual[k]for k in ['path','bytes','sha256']),'exporter result differs from actual final package bytes')
        need(state['pid']==os.getpid(),'same Python process required')
        state.update(status=SUCCESS,finished_epoch=time.time());save(out/'state.json',state)
        print('XU191_TERMINAL '+SUCCESS+' '+json.dumps(actual,sort_keys=True),flush=True);return 0
    except BaseException as error:
        state.update(status=FAIL,error=type(error).__name__+': '+str(error),traceback=traceback.format_exc(),finished_epoch=time.time())
        if 'inputs_before'in state:
            try:
                state['inputs_after']=[identity(Path(row['path']))for row in state['inputs_before']]
                state['inputs_equal_before_after']=state['inputs_after']==state['inputs_before']
            except BaseException as followup:state['identity_recheck_error']=type(followup).__name__+': '+str(followup)
        save(out/'state.json',state)
        print('XU191_TERMINAL '+FAIL+' '+state['error'],file=sys.stderr,flush=True);return 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();return run(args.out)


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError)as error:
        print('XU191_TERMINAL '+FAIL+' '+type(error).__name__+': '+str(error),file=sys.stderr,flush=True);sys.exit(1)
