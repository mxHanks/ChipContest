#!/usr/bin/env python3
"""Run the isolated33-functional-macro core campaign, with no installation."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--vectors',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--jobs',type=int,choices=[1,2],default=2)
    parser.add_argument('--smoke-only',action='store_true')
    parser.add_argument('--tasks',type=int,default=1)
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    candidate=args.candidate.resolve();vectors=args.vectors.resolve()
    if not 1<=args.tasks<=12:parser.error('tasks1..12 required')
    if (vectors/'x.mem').is_file():
        if args.tasks!=1:parser.error('multiple tasks require a layer_XX root')
        layers=[vectors]
    else:layers=[vectors/f'layer_{n:02d}' for n in range(args.tasks)]
    spec=importlib.util.spec_from_file_location('xmacro_observer',HERE/'generate_observer.py')
    observer=importlib.util.module_from_spec(spec);spec.loader.exec_module(observer)
    monitor=out/'tile_physical_observer.sv';observer.generate(monitor)
    rtl=sorted((candidate/'rtl').glob('*.sv'))
    if len(rtl)!=10:raise ValueError('candidate must contain exactly10 source modules/files')
    sources=rtl+[HERE/'tile_macro_driver.cpp',HERE/'generate_observer.py',
                 HERE/'prepare_candidate.py',Path(__file__).resolve(),monitor,observer.ORIGINAL]
    sources += [candidate/'manifest.json']
    inputs=[folder/name for folder in layers for name in ['x.mem','w.mem','bias.mem','y.mem','y32.mem']]
    identity={str(p):sha(p) for p in sources+inputs}
    report=dict(schema='compliant32_xmacro_core_campaign_v1',status='RUNNING',
        started_at=datetime.now(timezone.utc).isoformat(),inputs=identity,commands=[],
        scope='Isolated B41 core;33 real genericRAMSP1024X16 functional instances. NoCPU/PPA/official qualification.',
        storage=json.loads((candidate/'manifest.json').read_text())['storage'],cases=[])
    def save():
        (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(command,name):
        save();begin=time.monotonic()
        with (out/(name+'.log')).open('w') as log:
            log.write(json.dumps(dict(command=[str(x) for x in command],cwd=str(ROOT)))+'\n');log.flush()
            done=subprocess.run([str(x) for x in command],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL)
        report['commands'].append(dict(name=name,returncode=done.returncode,
            command=[str(x) for x in command],elapsed_seconds=time.monotonic()-begin));save()
        if done.returncode:raise RuntimeError(name+' failed; see preserved log')
    try:
        run(['verilator','--version'],'verilator-version')
        run(['verilator','--cc','--exe','--build','--assert','-Wno-fatal','-j',args.jobs,
            '-DXU_MATRIX_DMA_SYSBUS32','-DXU_MATRIX_X_SRAM',
            '--top-module','LinearTileDmaCore','--Mdir',out/'obj','-CFLAGS','-std=c++17',
            *rtl,monitor,HERE/'tile_macro_driver.cpp'],'compile')
        report['simulator_sha256']=sha(out/'obj/VLinearTileDmaCore')
        cases=[(8,0)] if args.smoke_only else [(8,0),(8,31),(8,255),(1,0),(3,0)]
        for index,folder in enumerate(layers):
          for rows,stall in cases:
            name=f'layer{index:02d}-rows{rows}-stall{stall}'
            run([out/'obj/VLinearTileDmaCore',folder,rows,stall,out/(name+'.json')],name)
            result=json.loads((out/(name+'.json')).read_text())
            if result['outputs_exact_raw48']!=25344 or result['outputs_exact_cpp_rne_y32']!=25344:
                raise ValueError('incomplete numerical output coverage')
            log=(out/(name+'.log')).read_text()
            if log.count('S3_GENERIC_NON_PPA_MACRO_INSTANCE ')!=33:
                raise ValueError('not exactly33 real functional macro instances')
            if log.count('XM_PHYSICAL_CLEAR_PASS ')!=2:
                raise ValueError('initial and dirty physical-clear proof missing')
            if 'X=16384 total16bit_writes=33536' not in log or 'X_MACROS=16 X_USED_WORDS=1024' not in log:
                raise ValueError('X all-physical-address coverage missing')
            report['cases'].append(dict(name=name,layer=index,rows=rows,stall=stall,result=result))
        drift=[str(p) for p in sources+inputs if sha(p)!=identity[str(p)]]
        if drift:raise ValueError('source/input drift: '+repr(drift))
        report.update(status='PASS',source_drift=drift)
        print(f'XMACRO_CORE_PASS cases={len(cases)*len(layers)} exact_outputs_per_case=25344 macros=33',flush=True)
        return 0
    except Exception as error:
        report.update(status='FAIL',error=str(error));raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        report['outputs']={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))
            for p in sorted(out.glob('*')) if p.is_file() and p.name!='receipt.json'}
        save()


if __name__=='__main__':
    raise SystemExit(main())
