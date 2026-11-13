#!/usr/bin/env python3
"""Run complete12 and explicit waiting regressions after a functional base PASS.

No simulator rebuilds, no EDA, no acceptance relaxation. Every run is sealed by
run_cpu.py and retains its own output. At most two simulator processes run.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True);p.add_argument('--vectors',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();base=a.base.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    parent=json.loads((base/'result.json').read_text())
    if parent.get('status')!='PASS' or parent.get('schema')!='s3-compliant32-cpu-v1' or parent.get('outputs')!=25344:raise ValueError('functional task0 PASS required')
    runner=HERE/('run_cpu_xmacro.py' if parent.get('x_sram_configuration',{}).get('x_macros')==16 else 'run_cpu.py')
    receipt={'schema':'s3-compliant32-cpu-followups-v1','status':'RUNNING','started_at':datetime.now(timezone.utc).isoformat(),'base_result_sha256':digest(base/'result.json'),'runner_sha256':digest(runner),'commands':{},'results':{},'scope':'Local development vectors and SystemBus stimulus, no official SDK/audio/STA/PPA claim'}
    save=lambda:(out/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    save()
    cases=[('full12',12,0,0),('dma-first-wait31',1,31,0),('load-first-wait31',1,0,31)]
    commands={}
    for name,tasks,dma_wait,load_wait in cases:
        commands[name]=[sys.executable,'-u','-B',str(runner),'--out',str(out/name),'--vectors',str(a.vectors.resolve()),'--replay-from',str(base),'--tasks',str(tasks),'--warmup','--first-source-stall',str(dma_wait),'--first-load-stall',str(load_wait)]
    receipt['commands']=commands;save()
    def run(name):
        with (out/(name+'.driver.log')).open('w')as log:
            done=subprocess.run(commands[name],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=7200)
        d=json.loads((out/name/'result.json').read_text())
        return name,done.returncode,d
    try:
        with ThreadPoolExecutor(max_workers=2)as pool:
            for future in as_completed([pool.submit(run,case[0])for case in cases]):
                name,code,d=future.result();receipt['results'][name]={'returncode':code,'status':d.get('status'),'outputs':d.get('outputs'),'total_cycles':d.get('total_cycles'),'result_sha256':digest(out/name/'result.json')};save()
                print(name,receipt['results'][name],flush=True)
        if any(d['status']!='PASS' or d['returncode'] for d in receipt['results'].values()):raise ValueError('one or more complete followup regressions failed')
        baseline=parent['layers'][0]
        receipt['differential']={}
        for name in ['dma-first-wait31','load-first-wait31']:
            d=json.loads((out/name/'result.json').read_text());row=d['layers'][0]
            receipt['differential'][name]={'total_cycles_delta':row['total']-baseline['total'],'loading_cycles_delta':row['loading']-baseline['loading'],'dma_payload_cycles_delta':row['dma_payload']-baseline['dma_payload'],'injected_wait':31,'note':'Polling/fabric phase can change other overhead; exact equality to31 is not assumed. Exact endpoint offer/accept delay and full-window boundary are mandatory in each run.'}
        receipt['status']='PASS'
        return 0
    except Exception as exc:receipt.update(status='FAIL',error=str(exc));return 1
    finally:receipt['finished_at']=datetime.now(timezone.utc).isoformat();save()
if __name__=='__main__':sys.exit(main())
