#!/usr/bin/env python3
"""Reuse an identity-checked PASS model for bounded source-assembly fault tests."""
import argparse,hashlib,json,pathlib,re,shutil,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--model',type=pathlib.Path,required=True);ap.add_argument('--vectors',type=pathlib.Path,required=True);ap.add_argument('--out',type=pathlib.Path,required=True);a=ap.parse_args()
 model=a.model.resolve();previous=json.loads((model/'receipt.json').read_text());assert previous['status']=='PASS' and previous['source_drift']==[]
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);src=out/'source';src.mkdir()
 for file in (model/'source').glob('*'):
  if file.suffix in ['.v','.sv']:
   old=[p for p in previous['inputs'] if pathlib.Path(p).name==file.name];assert len(old)==1 and sha(file)==previous['inputs'][old[0]]
   assert sha(pathlib.Path(old[0]))==sha(file),'RTL changed since compiled model'
 inputs={str(model/'receipt.json'):sha(model/'receipt.json')}
 for name in ['dma32_test.cpp','dma32_fault_staging.cpp','run_fault_staging.py']:
  p=HERE/name;shutil.copy2(p,src/name);inputs[str(p)]=sha(p)
 for layer in range(8):
  for name in ['x.mem','w.mem','bias.mem','y32.mem']:
   p=a.vectors.resolve()/f'layer_{layer:02d}'/name;assert previous['inputs'][str(p)]==sha(p);inputs[str(p)]=sha(p)
 objects=[model/'obj/Vdma32_test_top__ALL.a',model/'obj/verilated.o',model/'obj/verilated_threads.o']
 objects+=sorted((model/'obj').glob('*.h'))
 receipt=dict(schema='compliant32-targeted-assembly-faults-v1',status='RUNNING',scope='Same frozen32bit peripheral/64PE model, new driver tests address-targeted source halves/errors; no CPU, new RTL compilation or PPA',base_receipt_sha256=sha(model/'receipt.json'),inputs=inputs,model_link_inputs={str(p):sha(p) for p in objects},commands=[])
 save=lambda:(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 def run(cmd,name):
  save();begin=time.monotonic()
  with (out/(name+'.log')).open('w')as log:r=subprocess.run([str(x)for x in cmd],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
  receipt['commands'].append(dict(command=[str(x)for x in cmd],returncode=r.returncode,elapsed_seconds=time.monotonic()-begin));save()
  if r.returncode:raise RuntimeError(name+' failed')
 try:
  info=subprocess.check_output(['verilator','-V'],text=True);inc=pathlib.Path(re.search(r'^\s*VERILATOR_ROOT\s*=\s*(\S+)',info,re.M)[1])/'include';exe=out/'dma32_fault_staging'
  run(['g++','-std=c++17','-pthread','-I'+str(model/'obj'),'-I'+str(src),'-I'+str(inc),'-I'+str(inc/'vltstd'),src/'dma32_fault_staging.cpp',*objects[:3],'-o',exe],'compile-driver')
  receipt['executable_sha256']=sha(exe)
  run([exe,a.vectors.resolve(),out/'fault-staging.json'],'fault-staging');d=json.loads((out/'fault-staging.json').read_text());assert d['status']=='PASS'and d['exact_recovery_y32']==177408
  assert all(sha(pathlib.Path(p))==h for p,h in {**inputs,**receipt['model_link_inputs']}.items())
  receipt['status']='PASS';receipt['source_drift']=[];print('DMA32_STAGING_FAULTS_PASS cases=7 exact_recovery_y32=177408',flush=True)
 except Exception as e:receipt.update(status='FAILED',error=str(e));raise
 finally:receipt['outputs']={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))for p in out.iterdir()if p.is_file()and p.name!='receipt.json'};save()
if __name__=='__main__':main()
