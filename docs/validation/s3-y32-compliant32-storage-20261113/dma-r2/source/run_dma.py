#!/usr/bin/env python3
"""Reuse compliant32 protocol/numeric/fault/reset driver on scalar macro overlay."""
import argparse, hashlib, importlib.util, json, re, shutil, subprocess, time
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
UNIT=HERE.parent/'dma';PERIPS=ROOT/'third-party/e203_hbirdv2/rtl/e203/perips'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--vectors',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--jobs',type=int,choices=[1,2],default=1)
    p.add_argument('--smoke-only',action='store_true');a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);src=out/'source';src.mkdir();origins={}
    def cp(path):
        origins[str(path)]=sha(path);shutil.copy2(path,src/path.name);return src/path.name
    for f in sorted((a.candidate.resolve()/'rtl').glob('*.sv')):cp(f)
    for f in [PERIPS/'xu_dma_shared_arb.v',ROOT/'tools/ppa/xu_shared_icb_sram.sv',ROOT/'tools/ppa/xu_sirv_sram_adapter.sv']:cp(f)
    cpp=cp(UNIT/'dma32_test.cpp');cp(UNIT/'dma32_reset_recovery.cpp');top=cp(UNIT/'dma32_test_top.sv')
    t=cpp.read_text()
    if t.count('crwrites==17408')!=1:raise ValueError('original counter seam differs')
    cpp.write_text(t.replace('crwrites==17408','crwrites==35840'))
    spec=importlib.util.spec_from_file_location('storage_observer',HERE/'generate_observer.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.generate(src/'storage_observer.svh');t=top.read_text()
    if t.count('endmodule')!=1:raise ValueError('unit top seam differs')
    top.write_text(t.replace('endmodule',(src/'storage_observer.svh').read_text()+'\nendmodule'))
    cp(HERE/'generate_observer.py');cp(Path(__file__).resolve())
    rtl=sorted(f for f in src.iterdir() if f.suffix in ['.sv','.v']);identity={str(f):sha(f) for f in src.iterdir() if f.is_file()}
    vectors=a.vectors.resolve()
    for layer in range(12):
        for name in ['x.mem','w.mem','bias.mem','y32.mem']:
            f=vectors/f'layer_{layer:02d}'/name;identity[str(f)]=sha(f)
    rec=dict(schema='compliant32_storage_macro_unit_v1',status='RUNNING',started_at=datetime.now(timezone.utc).isoformat(),origins=origins,inputs=identity,commands=[],scope='Scalar result36 internal/292 generic macros including shared, no CPU/PPA qualification')
    def save():(out/'receipt.json').write_text(json.dumps(rec,indent=2)+'\n')
    def run(cmd,name):
        save();start=time.monotonic()
        with (out/(name+'.log')).open('w') as log:
            log.write(json.dumps(dict(command=[str(x) for x in cmd],cwd=str(ROOT)))+'\n');log.flush()
            done=subprocess.run([str(x) for x in cmd],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
        rec['commands'].append(dict(name=name,command=[str(x) for x in cmd],returncode=done.returncode,elapsed_seconds=time.monotonic()-start));save()
        if done.returncode:raise RuntimeError(name+' failed; preserved log')
    try:
        run(['verilator','--version'],'verilator-version')
        run(['verilator','--cc','--exe','--build','--assert','-Wno-fatal','-j',a.jobs,
          '-DXU_MATRIX_DMA_SYSBUS32','-DXU_MATRIX_X_SRAM','-DXU_MATRIX_STORAGE_SRAM','--top-module','dma32_test_top',
          '--Mdir',out/'obj','-CFLAGS','-std=c++17',*rtl,cpp],'compile')
        exe=out/'obj/Vdma32_test_top';rec['simulator_sha256']=sha(exe)
        cases=[('task0',1,8,0,0,0)] if a.smoke_only else [('task0',1,8,0,0,0),('full12',12,8,0,0,0),('faults-task0',1,8,1,0,0),('stall-task0',1,8,0,1,0),('rows1-task0',1,1,0,0,0),('last-y-hold-task0',1,8,0,0,1)]
        for name,tasks,rows,faults,stall,hold in cases:
            run([exe,vectors,tasks,rows,out/(name+'.json'),faults,stall,hold],name)
            result=json.loads((out/(name+'.json')).read_text());log=(out/(name+'.log')).read_text()
            if result.get('status')!='PASS' or result['exact_y32']!=25344*tasks:raise ValueError(name+' incomplete exact output')
            if log.count('S3_GENERIC_NON_PPA_MACRO_INSTANCE ')!=292:raise ValueError(name+' macro count mismatch')
            if 'total16bit_writes=36608' not in log:raise ValueError(name+' physical clear proof missing')
        if not a.smoke_only:
            v=subprocess.check_output(['verilator','-V'],text=True);inc=Path(re.search(r'^\s*VERILATOR_ROOT\s*=\s*(\S+)',v,re.M).group(1))/'include'
            exe2=out/'obj/dma32_reset_recovery'
            run(['g++','-std=c++17','-pthread','-I'+str(out/'obj'),'-I'+str(src),'-I'+str(inc),'-I'+str(inc/'vltstd'),
              src/'dma32_reset_recovery.cpp',out/'obj/Vdma32_test_top__ALL.a',out/'obj/verilated.o',out/'obj/verilated_threads.o','-o',exe2],'compile-reset-driver')
            run([exe2,vectors,out/'reset-recovery.json'],'reset-recovery')
            r=json.loads((out/'reset-recovery.json').read_text())
            if r.get('status')!='PASS' or r['exact_postreset_y32']!=76032:raise ValueError('incomplete reset outputs')
        drift=[s for s,h in identity.items() if sha(Path(s))!=h]
        if drift:raise ValueError('sealed source drift: '+repr(drift))
        rec.update(status='PASS',source_drift=drift);print('STORAGE_MACRO_DMA_UNIT_PASS')
    except Exception as e:rec.update(status='FAIL',error=str(e));raise
    finally:
        rec['finished_at']=datetime.now(timezone.utc).isoformat()
        rec['outputs']={f.name:dict(bytes=f.stat().st_size,sha256=sha(f)) for f in out.iterdir() if f.is_file() and f.name!='receipt.json'};save()
if __name__=='__main__':main()
