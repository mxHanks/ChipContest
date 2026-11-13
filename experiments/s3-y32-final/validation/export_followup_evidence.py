#!/usr/bin/env python3
"""Replay and export GPIO374 wait31 evidence after both same-binary cases PASS."""
import argparse
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode=True
from export_functional_evidence import sha,files,dump

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--followups',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 a=p.parse_args();a.followups=a.followups.resolve();a.out=a.out.resolve()
 receipt=json.loads((a.followups/'receipt.json').read_text())
 if receipt.get('status')!='PASS' or receipt.get('schema')!='s3-final-production-gpio-followups-v1':raise ValueError('complete same-binary followups PASS required')
 base=Path(receipt['base']);baseline=json.loads((base/'result.json').read_text());binary=base/'simulator/sysbus32_gpio_soc'
 if baseline['status']!='PASS' or baseline['schema']!='s3-final-production-gpio-cpu-v1' or sha(binary)!=baseline['simulator_sha256']:raise ValueError('base binary binding differs')
 results={};copies=[]
 for name,expected in [('dma-first-wait31',(31,0)),('load-first-wait31',(0,31))]:
  folder=a.followups/name;r=json.loads((folder/'result.json').read_text())
  if (r.get('status')!='PASS' or r.get('outputs')!=25344 or r.get('actual_generic_macro_instances')!=374 or
      r['ppa_binding']!=baseline['ppa_binding'] or r['source_sha256']!=baseline['source_sha256'] or
      r['vector_byte_sha256']!=baseline['vector_byte_sha256'] or r['simulator_sha256']!=baseline['simulator_sha256'] or
      r['firmware']!=baseline['firmware'] or files(folder/'source')!=r['source_sha256']):raise ValueError('wait31 source/vector/binary/firmware binding differs')
  for file,key in [('dma_day_soc','elf_sha256'),('dma_day_soc.verilog','image_sha256')]:
   if sha(folder/'firmware'/file)!=baseline['firmware'][key]:raise ValueError('wait31 firmware bytes differ')
  if sha(folder/'result.json')!=receipt['results'][name]['result_sha256']:raise ValueError('followup terminal receipt differs')
  cp=folder/'source/check_results.py';spec=importlib.util.spec_from_file_location('frozen_wait_checker',cp);checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
  checked=checker.check_log((folder/'simulation.log').read_text(),1,8,'warmup' in r,x_macros=True,storage_configuration=r['storage_binding'])
  if any(r.get(k)!=v for k,v in checked.items()):raise ValueError('raw wait31 checker replay differs')
  row=r['layers'][0];channel=row['channel']
  if (channel['forced_wait'],channel['forced_load_wait'])!=expected:raise ValueError('different forced endpoint waits')
  results[name]=dict(status='PASS_RAW_CHECKER_REPLAY_SAME_BINARY',result_sha256=sha(folder/'result.json'),total_cycles=r['total_cycles'],
   gpio_input_to_y_cycles=r['load_to_y_cycles'],loading_cycles=r['source_loading_cycles'],dma_payload_cycles=r['dma_payload_cycles'],
   total_delta_from_base=r['total_cycles']-baseline['total_cycles'],input_window_delta_from_base=r['load_to_y_cycles']-baseline['load_to_y_cycles'],
   actual_dma_endpoint_wait=channel['endpoint_first_accept']-channel['endpoint_first_offer'],
   actual_load_endpoint_wait=channel['load_endpoint_accept']-channel['load_endpoint_offer'],forced_dma_wait=expected[0],forced_load_wait=expected[1])
  copies.extend([(folder/'result.json',name+'/result.json'),(folder/'simulation.log',name+'/simulation.log')])
 a.out.mkdir(parents=True,exist_ok=False)
 for origin,target in copies:
  dest=a.out/target;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(origin,dest)
 shutil.copy2(a.followups/'receipt.json',a.out/'receipt.json')
 dump(a.out/'summary.json',dict(schema='gpio374-independent-wait31-evidence-v1',status='PASS_BOTH_SAME_BINARY_WAIT31_RAW_REPLAYS',
  configuration='GPIO374 independent, not1064 N3 candidate; no EDA',exported_at=datetime.now(timezone.utc).isoformat(),
  simulator_sha256=baseline['simulator_sha256'],base_result_sha256=sha(base/'result.json'),
  tests=results,exporter_sha256=sha(Path(__file__)),scope='Real GPIO/CPU loading, physical clear, full Y writes/readbacks, endpoint waits and all intervening delays preserved. Overall cycle deltas need not equal31 because of CPU/bus phase.'))
 print(json.dumps(results))
if __name__=='__main__':main()
