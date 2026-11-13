#!/usr/bin/env python3
"""Complete twelve-task and endpoint-wait regressions using one sealed CPU binary."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse,hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--vectors',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 base=a.base.resolve();parent=json.loads((base/'result.json').read_text());out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 if parent.get('schema')!='s3-ingress-perf-cpu-v1' or parent.get('status')!='PASS' or parent.get('outputs')!=25344:raise ValueError('validated single task base required')
 receipt=dict(status='RUNNING',base_result_sha256=sha(base/'result.json'),runner_sha256=sha(HERE/'run_cpu.py'),commands={},results={},scope='Same binary/firmware/RTL and public audio vectors; local original32 stimulus timing, no official qualification')
 def save():(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 cases=[('full12',12,0,0,1),('dma-first-wait31',1,31,0,1),('load-first-wait31',1,0,31,1),('serialized-loader',1,0,0,0)]
 for name,tasks,dmawait,loadwait,pipe in cases:
  receipt['commands'][name]=[sys.executable,'-u','-B',str(HERE/'run_cpu.py'),'--out',str(out/name),'--vectors',str(a.vectors.resolve()),'--replay-from',str(base),'--tasks',str(tasks),'--warmup','--first-source-stall',str(dmawait),'--first-load-stall',str(loadwait),'--load-pipeline',str(pipe)]
 save()
 def run(case):
  name,tasks,dmawait,loadwait,pipe=case
  with (out/(name+'.driver.log')).open('w')as log:d=subprocess.run(receipt['commands'][name],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=3600)
  result=json.loads((out/name/'result.json').read_text())
  if d.returncode or result['status']!='PASS':raise RuntimeError(name+' failed')
  if result['simulator_sha256']!=parent['simulator_sha256'] or result['firmware']['elf_sha256']!=parent['firmware']['elf_sha256'] or result['source_sha256']!=parent['source_sha256']:raise ValueError('same-binary identity differs')
  for row in result['layers']:
   if not 2<=row['channel']['max_outstanding']<=4:raise ValueError('DMA pipeline not exercised')
   loader=row['loader_pipeline']
   if pipe and not 2<=loader['max_outstanding']<=4:raise ValueError('loader pipeline not exercised')
  return name,dict(status='PASS',outputs=result['outputs'],total_cycles=result['total_cycles'],loading_cycles=result['source_loading_cycles'],dma_cycles=result['dma_payload_cycles'],tasks_per_second=result['task_per_second_at_assumed_150mhz'],result_sha256=sha(out/name/'result.json'))
 try:
  with ThreadPoolExecutor(max_workers=2)as pool:
   for f in as_completed([pool.submit(run,case)for case in cases]):
    name,result=f.result();receipt['results'][name]=result;save();print(name,result,flush=True)
  receipt.update(status='PASS');return 0
 except Exception as error:receipt.update(status='FAIL',error=str(error));raise
 finally:save()
if __name__=='__main__':raise SystemExit(main())
