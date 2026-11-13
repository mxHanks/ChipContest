#!/usr/bin/env python3
"""Run strengthened ordered-DMA drivers against an already built sealed RTL model."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',type=Path,required=True);p.add_argument('--vectors',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 model=a.model.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);src=out/'source';src.mkdir()
 for name in ['dma32_test.cpp','dma32_reset_recovery.cpp','dma32_fault_staging.cpp']:shutil.copy2(HERE/'dma'/name,src/name)
 obj=model/'obj';platform=ROOT/'third-party/e203_hbirdv2/rtl/e203'
 for name,path in [('xu_matrix_dma_sysbus32.sv',platform/'perips/xu_matrix_dma_sysbus32.sv'),('xu_systembus_ingress32.v',platform/'subsys/xu_systembus_ingress32.v'),('sirv_icb1to8_bus.v',platform/'fab/sirv_icb1to8_bus.v')]:
  if sha(model/'source'/name)!=sha(path):raise ValueError('model/production source differs: '+name)
 pinned={str(f):sha(f) for f in sorted((model/'source').iterdir()) if f.is_file()}
 pinned.update({str(f):sha(f) for f in sorted(obj.iterdir()) if f.is_file() and (f.suffix=='.h' or f.name in ['Vdma32_test_top__ALL.a','verilated.o','verilated_threads.o'])})
 pinned.update({str(f):sha(f) for f in sorted(src.iterdir())})
 pinned.update({str(f):sha(f) for f in sorted(a.vectors.resolve().rglob('*')) if f.is_file()})
 receipt=dict(status='RUNNING',model=str(model),scope='Local DMA4/ingress4/original-fabric functional model; noCPU, noSTA/PPA, no whole-task throughput',inputs=pinned,commands=[],results={})
 def save():(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 def run(cmd,name):
  with (out/(name+'.log')).open('w')as log:
   log.write(json.dumps([str(x) for x in cmd])+'\n');log.flush();d=subprocess.run(list(map(str,cmd)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
  receipt['commands'].append(dict(name=name,argv=list(map(str,cmd)),returncode=d.returncode));save()
  if d.returncode:raise RuntimeError(name+' failed; see retained log')
 save()
 try:
  detail=subprocess.check_output(['verilator','-V'],text=True);inc=Path(re.search(r'^\s*VERILATOR_ROOT\s*=\s*(\S+)',detail,re.M).group(1))/'include'
  for stem in ['dma32_test','dma32_reset_recovery','dma32_fault_staging']:
   run(['g++','-std=c++17','-pthread','-I'+str(obj),'-I'+str(src),'-I'+str(inc),'-I'+str(inc/'vltstd'),src/(stem+'.cpp'),obj/'Vdma32_test_top__ALL.a',obj/'verilated.o',obj/'verilated_threads.o','-o',out/stem],'compile-'+stem)
  for name,tasks,rows,faults,stall,hold in [('task0',1,8,0,0,0),('full12',12,8,0,0,0),('faults-task0',1,8,1,0,0),('stall-task0',1,8,0,1,0),('rows1-task0',1,1,0,0,0),('last-y-hold-task0',1,8,0,0,1)]:
   run([out/'dma32_test',a.vectors.resolve(),tasks,rows,out/(name+'.json'),faults,stall,hold],name)
   result=json.loads((out/(name+'.json')).read_text())
   if result['status']!='PASS' or result['exact_y32']!=tasks*25344:raise ValueError(name+' incomplete output')
   if hold and result['last_y_response_held_edges']!=97:raise ValueError('lastY response hold incomplete')
   receipt['results'][name]=result;save()
  for stem,name,key,count in [('dma32_reset_recovery','reset-recovery','exact_postreset_y32',76032),('dma32_fault_staging','fault-staging','exact_recovery_y32',177408)]:
   run([out/stem,a.vectors.resolve(),out/(name+'.json')],name)
   result=json.loads((out/(name+'.json')).read_text())
   if result['status']!='PASS' or result[key]!=count:raise ValueError(name+' recovery incomplete')
   if name=='reset-recovery' and any(c['cancelled_count']<2 for c in result['cases'] if c['phase']!=1):raise ValueError('multi-owner reset not exercised')
   receipt['results'][name]=result;save()
  if any(not Path(n).is_file() or sha(Path(n))!=h for n,h in pinned.items()):raise ValueError('frozen model/driver/vector drift')
  receipt.update(status='PASS',source_drift=[]);print('DMA4_REPLAY_PASS full12=304128 reset_recovery=76032 targeted_error_recovery=177408 lastY_valid_hold=97',flush=True)
 except Exception as error:receipt.update(status='FAIL',error=str(error));raise
 finally:save()
if __name__=='__main__':main()
