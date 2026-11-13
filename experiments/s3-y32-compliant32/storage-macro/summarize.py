#!/usr/bin/env python3
"""Recheck finished evidence and report honest unit-only candidate comparison."""
import argparse,hashlib,json,re
from pathlib import Path
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify_receipt(folder):
    p=folder/'receipt.json';r=json.loads(p.read_text())
    if r.get('status')!='PASS':raise ValueError('not PASS: '+str(p))
    for s,h in r['inputs'].items():
        if sha(Path(s))!=h:raise ValueError('input drift: '+s)
    if any(x['returncode'] for x in r['commands']):raise ValueError('failed command')
    for name,expected in r.get('outputs',{}).items():
        f=folder/name
        if f.stat().st_size!=expected['bytes'] or sha(f)!=expected['sha256']:raise ValueError('output drift '+str(f))
    return r
def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--require-wide',action='store_true');a=p.parse_args();root=a.build.resolve()
    results=[]
    for name,candidate,dma,core in [('three','candidate-r2','dma-r2','core-r2'),('wide','wide-candidate-r2','wide-dma-r2','wide-core-r2')]:
      if not (root/core/'receipt.json').exists():
        if name=='wide' and not a.require_wide:continue
        raise ValueError('missing final core receipt')
      m=json.loads((root/candidate/'manifest.json').read_text())
      for n,h in m['files'].items():
        if sha(root/candidate/'rtl'/n)!=h:raise ValueError('candidate drift')
      dr=verify_receipt(root/dma);cr=verify_receipt(root/core)
      full=json.loads((root/dma/'full12.json').read_text());reset=json.loads((root/dma/'reset-recovery.json').read_text())
      if full['exact_y32']!=304128 or reset['exact_postreset_y32']!=76032 or len(cr['cases'])!=60:raise ValueError('coverage gap')
      if sum(x['result']['outputs_exact_raw48'] for x in cr['cases'])!=1520640:raise ValueError('raw coverage gap')
      hold=json.loads((root/dma/'last-y-hold-task0.json').read_text())
      if hold['last_y_response_held_edges']!=97:raise ValueError('last Y response hold missing')
      port=[dict(zip(['store','read','held','producer_blocked','scalar_retired'],map(int,x))) for x in re.findall(r'SM_RESULT_PORT_MEASURE store_edges=(\d+) read_edges=(\d+) hold_edges=(\d+) producer_blocked_by_read=(\d+) scalar_rsp_retired_pops=(\d+)',(root/dma/'full12.log').read_text())]
      if len(port)!=12 or any(x['scalar_retired']!=25344 for x in port):raise ValueError('port counts missing')
      if (root/dma/'full12.log').read_text().count('SM_PHYSICAL_CLEAR_PASS ')!=12:raise ValueError('physical clear call coverage')
      results.append(dict(name=name,candidate=str(root/candidate),manifest_sha256=sha(root/candidate/'manifest.json'),
        dma_receipt_sha256=sha(root/dma/'receipt.json'),core_receipt_sha256=sha(root/core/'receipt.json'),
        storage=m['storage'],clear=m['clear'],full12=full,raw_cases=60,raw_regular_outputs=1520640,
        legal_endpoint_raw48=sum(x['result']['legal_endpoint_raw48_outputs'] for x in cr['cases']),
        reset_recovery_exact_y32=reset['exact_postreset_y32'],final_y_hold_edges=97,port_per_task=port))
    r=dict(status='PASS_UNIT_ONLY',candidates=results,
      scope='Functional generic SRAM module and32bit arbiter/endpoint, no CPU/System Bus whole-task/PPA claim',
      missing=['Selected-candidate CPU full12 and official timing window','Official-area-unit/macro-price and mapped STA','Mapped functional consistency and all-SoC power','Organizer official600 selection'])
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2)+'\n');print('STORAGE_MACRO_EVIDENCE_RECHECK_PASS candidates='+str(len(results)))
if __name__=='__main__':main()
