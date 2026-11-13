#!/usr/bin/env python3
"""Frozen-source64PE/32-bit DMA development regression; no CPU/PPA claim."""
import argparse
from datetime import datetime,timezone
import hashlib,json,pathlib,re,shutil,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[3]
HERE=pathlib.Path(__file__).resolve().parent

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--vectors',type=pathlib.Path,required=True)
 ap.add_argument('--out',type=pathlib.Path,required=True)
 ap.add_argument('--deadline',help='Optional timezone-qualified experiment deadline')
 args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
 deadline=datetime.fromisoformat(args.deadline) if args.deadline else None
 if deadline and deadline.tzinfo is None:raise ValueError('deadline must include timezone')
 perips=ROOT/'third-party/e203_hbirdv2/rtl/e203/perips'
 names=['LinearTileDmaCore.sv','Sram1024x16.sv','TileWeightBank.sv','mem_1024x16.sv','DmaBiasSramPrefetch.sv','TileXRowBuffer.sv','MacController.sv','TileWeightBankArray.sv','xu_matrix_dma_sysbus32.sv','xu_dma_shared_arb.v']
 rtl=[perips/x for x in names]+[ROOT/'tools/ppa/xu_shared_icb_sram.sv',ROOT/'tools/ppa/xu_sirv_sram_adapter.sv',ROOT/'tools/ppa/generic_ramsp_non_ppa.sv',HERE/'dma32_test_top.sv']
 cpp=HERE/'dma32_test.cpp';recovery=HERE/'dma32_reset_recovery.cpp'
 src=out/'source';src.mkdir();inputs={}
 for p in rtl+[cpp,recovery,pathlib.Path(__file__).resolve()]:
  inputs[str(p)]=sha(p);shutil.copy2(p,src/p.name)
 if sha(perips/'LinearTileDmaCore.sv')!='710b8e180652f49751769e152a3b3a9e6a35ba622fb4c3e2385dc5ffab241fcb':raise ValueError('requires frozen64PE B41 core')
 vectors=args.vectors.resolve()
 for layer in range(12):
  for n in ['x.mem','w.mem','bias.mem','y32.mem']:inputs[str(vectors/f'layer_{layer:02d}'/n)]=sha(vectors/f'layer_{layer:02d}'/n)
 receipt=dict(schema='compliant32_dma_unit_v1',status='RUNNING',scope='64PE B41 DMA + original32 endpoint/arbiter +256 functional RAMSP macros; development unit only, not CPU/SystemBus official timing or PPA',inputs=inputs,commands=[],deadline=args.deadline)
 save=lambda:(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 def run(cmd,name):
  if deadline and datetime.now(timezone.utc)>=deadline:raise RuntimeError('deadline reached before '+name)
  save();begin=time.monotonic()
  with (out/(name+'.log')).open('w') as log:
   done=subprocess.run([str(x)for x in cmd],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  receipt['commands'].append(dict(name=name,command=[str(x)for x in cmd],returncode=done.returncode,elapsed_seconds=time.monotonic()-begin));save()
  if done.returncode:raise RuntimeError(name+' failed; preserved raw log')
 try:
  run(['verilator','--version'],'verilator-version')
  cmd=['verilator','--cc','--exe','--build','-j','2','--assert','-Wno-fatal','--top-module','dma32_test_top','--Mdir',out/'obj','-CFLAGS','-std=c++17']+[src/p.name for p in rtl+[cpp]]
  run(cmd,'compile');exe=out/'obj/Vdma32_test_top';receipt['executable_sha256']=sha(exe)
  for name,tasks,rows,faults,stall,hold in [('task0',1,8,0,0,0),('full12',12,8,0,0,0),('faults-task0',1,8,1,0,0),('stall-task0',1,8,0,1,0),('rows1-task0',1,1,0,0,0),('last-y-hold-task0',1,8,0,0,1)]:
   run([exe,vectors,tasks,rows,out/(name+'.json'),faults,stall,hold],name)
   d=json.loads((out/(name+'.json')).read_text())
   if d.get('status')!='PASS' or d['exact_y32']!=25344*tasks:raise RuntimeError(name+' numeric coverage')
   print(name,'PASS','exact_y32',d['exact_y32'],flush=True)
  root_text=subprocess.check_output(['verilator','-V'],text=True)
  found=re.search(r'^\s*VERILATOR_ROOT\s*=\s*(\S+)',root_text,re.M)
  inc=pathlib.Path(found.group(1))/'include'
  resetexe=out/'obj/dma32_reset_recovery'
  run(['g++','-std=c++17','-pthread','-I'+str(out/'obj'),'-I'+str(src),'-I'+str(inc),'-I'+str(inc/'vltstd'),src/recovery.name,out/'obj/Vdma32_test_top__ALL.a',out/'obj/verilated.o',out/'obj/verilated_threads.o','-o',resetexe],'compile-recovery-driver')
  run([resetexe,vectors,out/'reset-recovery.json'],'reset-recovery')
  d=json.loads((out/'reset-recovery.json').read_text())
  if d.get('status')!='PASS' or d['exact_postreset_y32']!=76032:raise RuntimeError('postreset numeric coverage')
  receipt['source_drift']=[p for p,h in inputs.items()if sha(pathlib.Path(p))!=h]
  if receipt['source_drift']:raise RuntimeError('source drift')
  receipt['status']='PASS';print('DMA32_UNIT_CAMPAIGN_PASS',flush=True)
 except Exception as e:
  receipt.update(status='FAILED',error=str(e));raise
 finally:
  receipt['outputs']={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))for p in sorted(out.iterdir())if p.is_file()and p.name!='receipt.json'};save()
if __name__=='__main__':main()
