#!/usr/bin/env python3
"""DMA4/storage21 integration regression over installed RTL and the original32 fabric."""
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
UNIT=ROOT/'experiments/s3-y32-ingress-perf/dma'
PERIPS=ROOT/'third-party/e203_hbirdv2/rtl/e203/perips'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vectors',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--jobs',type=int,choices=[1],default=1)
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    src=out/'source';src.mkdir();vectors=args.vectors.resolve()
    origins={}
    def copy(path,name=None):
        target=src/(name or path.name);shutil.copy2(path,target);origins[str(path)]=sha(path);return target
    for name in ['DmaBiasSramPrefetch.sv','LinearTileDmaCore.sv','MacController.sv','Sram1024x16.sv','TileWeightBank.sv','TileWeightBankArray.sv','TileXMacroRowBuffer.sv','TileXRowBuffer.sv','mem_1024x16.sv','xu_matrix_dma_sysbus32.sv']:copy(PERIPS/name)
    copy(ROOT/'tools/ppa/generic_ramsp_non_ppa.sv')
    platform=ROOT/'third-party/e203_hbirdv2/rtl/e203'
    for name in ['subsys/xu_systembus_ingress32.v','fab/sirv_icb1to8_bus.v','general/sirv_gnrl_icbs.v','general/sirv_gnrl_bufs.v','general/sirv_gnrl_dffs.v']:copy(platform/name)
    for name in ['xu_shared_icb_sram.sv','xu_sirv_sram_adapter.sv']:copy(ROOT/'tools/ppa'/name)
    cpp=copy(UNIT/'dma32_test.cpp');recovery=copy(UNIT/'dma32_reset_recovery.cpp');staging=copy(HERE/'dma32_fault_multi.cpp')
    top=copy(UNIT/'dma32_test_top.sv')
    text=cpp.read_text();assert text.count('crwrites==32768')==1
    cpp.write_text(text.replace('crwrites==32768','crwrites==54272'))
    spec=importlib.util.spec_from_file_location('storage_observer',ROOT/'experiments/s3-y32-compliant32/storage-macro/generate_observer.py')
    observer=importlib.util.module_from_spec(spec);spec.loader.exec_module(observer)
    inst=src/'storage_observer.svh';observer.generate(inst,result_macros=21)
    rowcheck=r"""
 reg previousHeld=0,previousLastPop=0;
 reg [335:0] previousRowQ;
 reg [3:0] previousRowOwner;
 always @(posedge clk)begin
   if(!rst_n||dma.aborting)begin previousHeld<=0;previousLastPop<=0;end
   else begin
     if(previousHeld&&!previousLastPop&&dma.u_core.readHeld)begin
       assert(dma.u_core.resultRowQ===previousRowQ)else $fatal(1,"macro Q row changed before last Y response");
       assert({dma.u_core.head,dma.u_core.outRow}==previousRowOwner)else $fatal(1,"macro slot/row released before last Y response");
     end
     previousHeld<=dma.u_core.readHeld;
     previousLastPop<=dma.core_pop&&dma.core_out_column==7;
     previousRowQ<=dma.u_core.resultRowQ;
     previousRowOwner<={dma.u_core.head,dma.u_core.outRow};
   end
 end
"""
    text=top.read_text();assert text.count('endmodule')==1
    top.write_text(text.replace('endmodule',inst.read_text()+rowcheck+'\nendmodule'))
    copy(ROOT/'experiments/s3-y32-compliant32/storage-macro/generate_observer.py');copy(Path(__file__).resolve())
    rtl=sorted(p for p in src.iterdir() if p.suffix in ['.sv','.v'])
    identity={str(p):sha(p) for p in sorted(src.iterdir()) if p.is_file()}
    for layer in range(12):
        for name in ['x.mem','w.mem','bias.mem','y32.mem']:
            p=vectors/f'layer_{layer:02d}'/name;identity[str(p)]=sha(p)
    receipt=dict(schema='s3_y32_final_dma4_storage21_unit_v1',status='RUNNING',
        started_at=datetime.now(timezone.utc).isoformat(),origins=origins,inputs=identity,commands=[],
        scope='DMA4 plus ingress4 and unchanged original32 fabric/endpoint with256 shared+54 internal macros; local diagnostic noCPU/PPA.',
        observer_policy='All physical address/zero-write proof on every clear. Public dirty prestate required after completed task; aborted/reset task may leave categories clean.',
        counter_semantics=dict(mmio_W_X_result=54272,physical_W_bias_X_result=55040))
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
        run(['verilator','--cc','--exe','--build','--assert','--no-timing','-DDISABLE_SV_ASSERTION=1','-Wno-fatal','-j',args.jobs,
            '-DXU_MATRIX_DMA_SYSBUS32','-DXU_MATRIX_X_SRAM','-DXU_MATRIX_STORAGE_SRAM','--top-module','dma32_test_top',
            '--Mdir',out/'obj','-CFLAGS','-std=c++17',*rtl,cpp],'compile')
        exe=out/'obj/Vdma32_test_top';receipt['simulator_sha256']=sha(exe)
        for name,tasks,rows,faults,stall,hold in [('task0',1,8,0,0,0),('full12',12,8,0,0,0),
            ('faults-task0',1,8,1,0,0),('stall-task0',1,8,0,1,0),('rows1-task0',1,1,0,0,0),('last-y-hold-task0',1,8,0,0,1)]:
            run([exe,vectors,tasks,rows,out/(name+'.json'),faults,stall,hold],name)
            result=json.loads((out/(name+'.json')).read_text());log=(out/(name+'.log')).read_text()
            if result.get('status')!='PASS' or result['exact_y32']!=25344*tasks:raise ValueError(name+' incomplete numeric output')
            if log.count('S3_GENERIC_NON_PPA_MACRO_INSTANCE ')!=310:raise ValueError(name+' wrong physical macro count')
            if 'X=16384 RESULT=21504 total16bit_writes=55040' not in log:raise ValueError(name+' physical X clear proof missing')
        detail=subprocess.check_output(['verilator','-V'],text=True)
        found=re.search(r'^\s*VERILATOR_ROOT\s*=\s*(\S+)',detail,re.M);inc=Path(found.group(1))/'include'
        resetexe=out/'obj/dma32_reset_recovery'
        run(['g++','-std=c++17','-pthread','-I'+str(out/'obj'),'-I'+str(src),'-I'+str(inc),
            '-I'+str(inc/'vltstd'),recovery,out/'obj/Vdma32_test_top__ALL.a',out/'obj/verilated.o',
            out/'obj/verilated_threads.o','-o',resetexe],'compile-recovery-driver')
        run([resetexe,vectors,out/'reset-recovery.json'],'reset-recovery')
        reset=json.loads((out/'reset-recovery.json').read_text())
        if reset.get('status')!='PASS' or reset['exact_postreset_y32']!=76032:raise ValueError('postreset numeric output missing')
        stagingexe=out/'obj/dma32_fault_staging'
        run(['g++','-std=c++17','-pthread','-I'+str(out/'obj'),'-I'+str(src),'-I'+str(inc),
            '-I'+str(inc/'vltstd'),staging,out/'obj/Vdma32_test_top__ALL.a',out/'obj/verilated.o',
            out/'obj/verilated_threads.o','-o',stagingexe],'compile-staging-driver')
        run([stagingexe,vectors,out/'fault-staging.json'],'fault-staging')
        staging_result=json.loads((out/'fault-staging.json').read_text())
        if staging_result.get('status')!='PASS' or staging_result['exact_recovery_y32']!=177408:raise ValueError('targeted error recovery missing')
        drift=[p for p,h in identity.items() if sha(Path(p))!=h]
        if drift:raise ValueError('source/vector drift: '+repr(drift))
        receipt.update(status='PASS',source_drift=drift);print('FINAL_DMA4_STORAGE21_UNIT_PASS full12=304128 postreset=76032 macros=310',flush=True)
        return 0
    except Exception as error:
        receipt.update(status='FAIL',error=str(error));raise
    finally:
        receipt['finished_at']=datetime.now(timezone.utc).isoformat()
        receipt['outputs']={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))
            for p in sorted(out.iterdir()) if p.is_file() and p.name!='receipt.json'};save()


if __name__=='__main__':raise SystemExit(main())
