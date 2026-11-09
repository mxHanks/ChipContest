#!/usr/bin/env python3
"""Replay a sealed DMA CPU run after relocation, without Git or old paths.

The default rebuilds the complete frozen RTL with Verilator. --reuse-binary is
an explicit Linux same-host convenience and does not establish a fresh build.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import traceback

DEFAULT_DEADLINE = '2026-11-09T23:59:00+08:00'


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def files(directory: Path):
    result={}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'sealed evidence must not contain symlinks: {path}')
        if path.is_file():
            result[path.relative_to(directory).as_posix()]=sha(path)
    return result


def checked_relative(directory: Path, name: str):
    relative=Path(name)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError(f'nonrelative evidence name: {name}')
    return directory/relative


def check_sealed(sealed: Path, record):
    if record.get('status')!='PASS':
        raise ValueError('sealed run is not a completed PASS')
    expected=record['source_sha256']
    actual=files(sealed/'source')
    if actual!=expected:
        raise ValueError('sealed source identity differs from result pins')
    manifest=json.loads((sealed/'source-manifest.json').read_text())
    if manifest['files']!=expected:
        raise ValueError('sealed source manifest differs from result pins')
    firmware=sealed/'firmware/dma_day_soc'
    image=sealed/'firmware/dma_day_soc.verilog'
    if firmware.is_symlink() or image.is_symlink() or sha(firmware)!=record['firmware']['elf_sha256'] or sha(image)!=record['firmware']['image_sha256']:
        raise ValueError('sealed firmware ELF/image identity mismatch')
    for layer in record['vectors']:
        for name,digest in layer['sha256'].items():
            path=checked_relative(sealed/'vectors'/f"layer_{layer['layer']:02d}",name)
            if path.is_symlink() or sha(path)!=digest:
                raise ValueError(f'sealed vector identity mismatch: {path}')
    for name,digest in record['vector_export'].items():
        if sha(checked_relative(sealed/'vectors',name))!=digest:
            raise ValueError('sealed vector export/profile identity mismatch')
    return actual


def run(command, cwd: Path, logfile: Path, timeout: float):
    command=[str(x) for x in command]
    with logfile.open('w') as log:
        log.write(json.dumps(dict(command=command,cwd=str(cwd)))+'\n')
        log.flush()
        result=subprocess.run(command,cwd=cwd,stdin=subprocess.DEVNULL,stdout=log,
                              stderr=subprocess.STDOUT,env=dict(os.environ,PWD=str(cwd)),timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'command exited {result.returncode}: {logfile}')
    return logfile.read_text(errors='replace').split('\n',1)[1]


def load_frozen_checker(path: Path):
    spec=importlib.util.spec_from_file_location('sealed_dma_cpu_checker',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not all(callable(getattr(module,name,None)) for name in ['check_log','check_physical_clear','check_vectors']):
        raise ValueError('sealed checker lacks required verification functions')
    return module


def reference_prefix(record,tasks):
    layers=record['layers'][:tasks]
    return {name:sum(layer[field] for layer in layers) for name,field in [
        ('principal_cycles','principal'),('payload_cycles','payload'),
        ('clear_cycles','clear'),('gap_cycles','gap'),('including_gap_cycles','including_gap')]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sealed-run','--run',dest='sealed_run',type=Path,required=True,
                        help='relocated completed run directory with source, firmware, vectors, and result.json')
    parser.add_argument('--out',type=Path,required=True,help='new directory outside the sealed tree')
    parser.add_argument('--tasks',type=int,help='optional first N sealed tasks; default all sealed tasks')
    parser.add_argument('--reuse-binary',action='store_true',help='Linux same-host only: copy and use pinned simulator instead of rebuilding')
    parser.add_argument('--jobs',type=int,default=2)
    parser.add_argument('--timeout',type=int,default=7200)
    parser.add_argument('--deadline',default=DEFAULT_DEADLINE,
                        help='last permitted experiment time, ISO8601 with timezone; override explicitly for a later authorized reproduction')
    args=parser.parse_args(argv)
    sealed=args.sealed_run.resolve();out=args.out.resolve()
    if out.exists():parser.error('--out must not already exist')
    if out==sealed or sealed in out.parents:parser.error('--out must be outside the sealed tree')
    if args.jobs<1 or args.timeout<1:parser.error('jobs and timeout must be positive')
    try:
        deadline=datetime.fromisoformat(args.deadline)
        if deadline.tzinfo is None:parser.error('deadline must include a timezone')
    except ValueError:parser.error('invalid ISO8601 deadline')
    if datetime.now(timezone.utc)>=deadline:parser.error('deadline reached; no new experiment')
    out.mkdir(parents=True)
    report=dict(schema='dma_day_portable_replay_v1',status='RUNNING',
                started_at=datetime.now(timezone.utc).isoformat(),
                runner_sha256=sha(Path(__file__)),sealed_run=str(sealed),
                arguments={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},
                scope='relocated frozen-source real CPU/peripheral-DMA simulation; no Git, no STA or official qualification',
                bytecode_writes_disabled=bool(sys.dont_write_bytecode))
    write_json(out/'result.json',report)
    def remaining():
        available=(deadline-datetime.now(timezone.utc)).total_seconds()
        if available<=0:raise RuntimeError('deadline reached; no new experiment')
        return min(args.timeout,available)
    try:
        original=json.loads((sealed/'result.json').read_text())
        report['sealed_result_sha256']=sha(sealed/'result.json')
        manifest=check_sealed(sealed,original)
        tasks=len(original['layers']) if args.tasks is None else args.tasks
        if not 1<=tasks<=len(original['layers']):raise ValueError('tasks must select a nonempty prefix of the sealed run')
        dual=int(original['arguments']['dual']);warmup=bool(original['arguments']['warmup'])
        throttle=int(original['arguments']['throttle']);first_stall=int(original['arguments']['first_source_stall'])
        max_cycles=int(original['arguments']['max_cycles'])
        for name in ['source','firmware','vectors']:
            shutil.copytree(sealed/name,out/name)
        shutil.copy2(sealed/'source-manifest.json',out/'source-manifest.json')
        report.update(source_sha256=manifest,firmware_elf_sha256=original['firmware']['elf_sha256'],
                      firmware_image_sha256=original['firmware']['image_sha256'],
                      requested_tasks=tasks,dual=dual,warmup=warmup,throttle=throttle,
                      full_sealed_task_scope=tasks==len(original['layers']),
                      expected_cycles=reference_prefix(original,tasks))
        checker=load_frozen_checker(out/'source/run_soc.py')
        vector_identity=checker.check_vectors(out/'vectors',tasks)
        if vector_identity!=original['vectors'][:tasks]:raise ValueError('relocated independent integer/vector verification differs')
        report['vectors']=vector_identity
        sim=out/'simulator';sim.mkdir()
        binary=sim/'dma_day_soc'
        report['tools']={}
        for tool in ['verilator','g++']:
            if shutil.which(tool):
                version=subprocess.run([tool,'--version'],capture_output=True,text=True)
                report['tools'][tool]=dict(path=shutil.which(tool),version=(version.stdout+version.stderr).splitlines()[:4])
        if args.reuse_binary:
            if not sys.platform.startswith('linux'):raise ValueError('--reuse-binary is only supported for Linux same-host replay')
            inherited=sealed/'simulator/dma_day_soc'
            if inherited.is_symlink() or sha(inherited)!=original['simulator_sha256']:
                raise ValueError('sealed simulator identity mismatch')
            shutil.copy2(inherited,binary)
            report['build_mode']='pinned Linux same-host simulator reuse; no fresh compilation'
        else:
            if not shutil.which('verilator') or not shutil.which('g++'):raise ValueError('Verilator and g++ are required to rebuild frozen RTL')
            rtl=out/'source/rtl'
            sources=sorted(p for p in rtl.rglob('*') if p.suffix in ['.v','.sv'])+[out/'source/tests/tb_dma_day_soc.sv']
            filelist=out/'rtl.f';filelist.write_text(''.join(str(p)+'\n' for p in sources))
            includes=[rtl/'core',rtl/'perips',rtl/'perips/apb_i2c',out/'source/tests']
            command=['verilator','--binary','--timing','--assert','-CFLAGS','-std=gnu++20',
                     '-j',str(args.jobs),'-Wno-fatal','--top-module','tb_dma_day_soc',
                     '-Mdir',sim,'-o','dma_day_soc','-DDISABLE_SV_ASSERTION=1','-DXU_MATRIX_DMA',
                     *['-I'+str(p) for p in includes],'-f',filelist]
            write_json(out/'result.json',report)
            run(command,out,out/'simulator-build.log',remaining())
            report['build_mode']='fresh Verilator --assert --timing build from relocated pinned RTL'
        report['simulator_sha256']=sha(binary)
        if datetime.now(timezone.utc)>=deadline:raise RuntimeError('deadline reached before simulation start')
        runtime=[binary,f'+TESTCASE={out}/firmware/dma_day_soc',f'+VECTORS={out}/vectors',
                 f'+TASKS={tasks}',f'+DUAL={dual}',f'+WARMUP={int(warmup)}',f'+THROTTLE={throttle}',
                 f'+FIRST_SOURCE_STALL={first_stall}',f'+MAX_CYCLES={max_cycles}','+DUMPWAVE=0']
        report['runtime_command']=[str(x) for x in runtime]
        write_json(out/'result.json',report)
        print(f'PORTABLE_DMA_RUNNING tasks={tasks} dual={dual} out={out}',flush=True)
        log=run(runtime,out,out/'simulation.log',remaining())
        observed=checker.check_log(log,tasks,dual,warmup)
        if (out/'source/tests/dma_physical_observer.svh').is_file():
            observed['physical_clear']=checker.check_physical_clear(log,tasks,warmup)
        else:raise ValueError('sealed run lacks the physical clear observer')
        for key,value in report['expected_cycles'].items():
            if observed[key]!=value:raise ValueError(f'relocated {key} differs: observed={observed[key]} sealed={value}')
        for got,want in zip(observed['layers'],original['layers'][:tasks]):
            for key in ['layer','dual','outputs','payload','clear','principal','gap','including_gap','start_to_done']:
                if got[key]!=want[key]:raise ValueError(f'relocated layer={got["layer"]} {key} differs from sealed run')
            if got['window']['first_accept']-got['window']['first_request']<first_stall:
                raise ValueError('relocated first-source VALID timing omitted forced wait')
        if files(out/'source')!=manifest:raise ValueError('replay source copy changed during execution')
        if check_sealed(sealed,original)!=manifest:raise ValueError('sealed tree changed during replay')
        report.update(observed,status='PASS',source_drift=[],sealed_source_drift=[],
                      reference_main_cycles_equal=True,
                      validation_scope='complete12' if tasks==12 else f'{tasks}-task prefix; not complete12 performance proof')
        print(f'PORTABLE_DMA_PASS tasks={tasks} principal={report["principal_cycles"]} outputs={report["outputs"]}',flush=True)
        return 0
    except Exception as exc:
        report.update(status='FAIL',error=str(exc),traceback=traceback.format_exc())
        print(f'PORTABLE_DMA_FAIL {exc}; evidence={out}',file=sys.stderr,flush=True)
        return 1
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        write_json(out/'result.json',report)


if __name__=='__main__':
    sys.exit(main())
