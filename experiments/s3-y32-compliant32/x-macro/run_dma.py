#!/usr/bin/env python3
"""Separate32-bit DMA regression over the opt-in X macro overlay; no install."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
UNIT=HERE.parent/'dma'
PERIPS=ROOT/'third-party/e203_hbirdv2/rtl/e203/perips'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--vectors',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--jobs',type=int,choices=[1,2],default=2)
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    src=out/'source';src.mkdir();candidate=args.candidate.resolve();vectors=args.vectors.resolve()
    origins={}
    def copy(path,name=None):
        target=src/(name or path.name);shutil.copy2(path,target);origins[str(path)]=sha(path);return target
    for path in sorted((candidate/'rtl').glob('*.sv')):copy(path)
    for name in ['xu_matrix_dma_sysbus32.sv','xu_dma_shared_arb.v']:copy(PERIPS/name)
    for name in ['xu_shared_icb_sram.sv','xu_sirv_sram_adapter.sv']:copy(ROOT/'tools/ppa'/name)
    cpp=copy(UNIT/'dma32_test.cpp');recovery=copy(UNIT/'dma32_reset_recovery.cpp')
    content=cpp.read_text()
    if content.count('crwrites==17408')!=1:raise ValueError('clear counter seam differs')
    cpp.write_text(content.replace('crwrites==17408','crwrites==32768'))
    top=copy(UNIT/'dma32_test_top.sv')
    spec=importlib.util.spec_from_file_location('xmacro_unit_observer',HERE/'generate_observer.py')
    observer=importlib.util.module_from_spec(spec);spec.loader.exec_module(observer)
    inst=src/'xmacro_unit_observer.svh'
    observer.generate(inst,mode='cpu',core='dma.u_core',clock='clk',
        owners_idle='!dma.pending && !dma.locked && !dma.core_active && !dma.core_out_valid',
        snapshot_zero='(dma.w_low === 0) && (dma.bias_low === 0) && (dma.y_payload === 0) && (dma.bias_data === 0)',
        warmup="1'b0")
    # Error/reset recovery can legally leave categories clean. Require a dirty
    # prior state after completed tasks; every clear still proves every address.
    mon=src/'tile_physical_observer.sv';text=mon.read_text()
    if text.count('strictDirty,ownersIdle')!=1 or text.count('if(clears>0)begin')!=1:
        raise ValueError('unit observer policy seam differs')
    mon.write_text(text.replace('strictDirty,ownersIdle','strictDirty,dirtyRequired,ownersIdle')
                  .replace('if(clears>0)begin','if(clears>0&&dirtyRequired)begin'))
    insertion=inst.read_text().replace(' .strictDirty(', ' .dirtyRequired(dma.done),\n .strictDirty(')
    text=top.read_text()
    if text.count('endmodule')!=1:raise ValueError('unit top seam differs')
    top.write_text(text.replace('endmodule',insertion+'\nendmodule'))
    copy(HERE/'generate_observer.py');copy(Path(__file__).resolve())
    rtl=sorted(p for p in src.iterdir() if p.suffix in ['.sv','.v'])
    identity={str(p):sha(p) for p in sorted(src.iterdir()) if p.is_file()}
    for layer in range(12):
        for name in ['x.mem','w.mem','bias.mem','y32.mem']:
            p=vectors/f'layer_{layer:02d}'/name;identity[str(p)]=sha(p)
    receipt=dict(schema='compliant32_xmacro_dma_unit_v1',status='RUNNING',
        started_at=datetime.now(timezone.utc).isoformat(),origins=origins,inputs=identity,commands=[],
        scope='Original32 DMA/arbiter/endpoint with256 shared+33 internal functional macros; noCPU/PPA.',
        observer_policy='All physical address/zero-write proof on every clear. Public dirty prestate required after completed task; aborted/reset task may leave categories clean.',
        counter_semantics=dict(mmio_W_plus_X=32768,observer_W_plus_bias_plus_X=33536))
    def save():(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    def run(cmd,name):
        save();begin=time.monotonic()
        with (out/(name+'.log')).open('w') as log:
            log.write(json.dumps(dict(command=[str(x) for x in cmd],cwd=str(ROOT)))+'\n');log.flush()
            done=subprocess.run([str(x) for x in cmd],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
        receipt['commands'].append(dict(name=name,command=[str(x) for x in cmd],returncode=done.returncode,elapsed_seconds=time.monotonic()-begin));save()
        if done.returncode:raise RuntimeError(name+' failed; see preserved log')
    try:
        run(['verilator','--version'],'verilator-version')
        run(['verilator','--cc','--exe','--build','--assert','-Wno-fatal','-j',args.jobs,
            '-DXU_MATRIX_DMA_SYSBUS32','-DXU_MATRIX_X_SRAM','--top-module','dma32_test_top',
            '--Mdir',out/'obj','-CFLAGS','-std=c++17',*rtl,cpp],'compile')
        exe=out/'obj/Vdma32_test_top';receipt['simulator_sha256']=sha(exe)
        for name,tasks,rows,faults,stall,hold in [('task0',1,8,0,0,0),('full12',12,8,0,0,0),
            ('faults-task0',1,8,1,0,0),('stall-task0',1,8,0,1,0),('rows1-task0',1,1,0,0,0),('last-y-hold-task0',1,8,0,0,1)]:
            run([exe,vectors,tasks,rows,out/(name+'.json'),faults,stall,hold],name)
            result=json.loads((out/(name+'.json')).read_text());log=(out/(name+'.log')).read_text()
            if result.get('status')!='PASS' or result['exact_y32']!=25344*tasks:raise ValueError(name+' incomplete numeric output')
            if log.count('S3_GENERIC_NON_PPA_MACRO_INSTANCE ')!=289:raise ValueError(name+' wrong physical macro count')
            if 'X=16384 total16bit_writes=33536' not in log:raise ValueError(name+' physical X clear proof missing')
        detail=subprocess.check_output(['verilator','-V'],text=True)
        found=re.search(r'^\s*VERILATOR_ROOT\s*=\s*(\S+)',detail,re.M);inc=Path(found.group(1))/'include'
        resetexe=out/'obj/dma32_reset_recovery'
        run(['g++','-std=c++17','-pthread','-I'+str(out/'obj'),'-I'+str(src),'-I'+str(inc),
            '-I'+str(inc/'vltstd'),recovery,out/'obj/Vdma32_test_top__ALL.a',out/'obj/verilated.o',
            out/'obj/verilated_threads.o','-o',resetexe],'compile-recovery-driver')
        run([resetexe,vectors,out/'reset-recovery.json'],'reset-recovery')
        reset=json.loads((out/'reset-recovery.json').read_text())
        if reset.get('status')!='PASS' or reset['exact_postreset_y32']!=76032:raise ValueError('postreset numeric output missing')
        drift=[p for p,h in identity.items() if sha(Path(p))!=h]
        if drift:raise ValueError('source/vector drift: '+repr(drift))
        receipt.update(status='PASS',source_drift=drift);print('XMACRO_DMA32_UNIT_PASS full12=304128 postreset=76032 macros=289',flush=True)
        return 0
    except Exception as error:
        receipt.update(status='FAIL',error=str(error));raise
    finally:
        receipt['finished_at']=datetime.now(timezone.utc).isoformat()
        receipt['outputs']={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))
            for p in sorted(out.iterdir()) if p.is_file() and p.name!='receipt.json'};save()


if __name__=='__main__':raise SystemExit(main())
