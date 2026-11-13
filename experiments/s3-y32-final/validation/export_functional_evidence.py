#!/usr/bin/env python3
"""Export compact, independently replayed final production GPIO evidence.

This GPIO374 independent evidence is separate from the historical1064 N3 candidate.
No simulation or EDA is repeated. A complete PASS, exact source/vector/binary
identity and frozen-checker raw-log replay are mandatory. Raw tensor vectors,
generated C++, libraries and credentials are never copied.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode=True

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def files(root):return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
def dump(path,data):path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--vectors',type=Path,required=True)
 a=p.parse_args();a.run=a.run.resolve();a.out=a.out.resolve();a.vectors=a.vectors.resolve()
 r=json.loads((a.run/'result.json').read_text())
 expected=['SYNTHESIS','DISABLE_SV_ASSERTION=1','XU_MATRIX_DMA','XU_MATRIX_DMA_SYSBUS32','XU_MATRIX_X_SRAM','XU_MATRIX_STORAGE_SRAM']
 if (r.get('status')!='PASS' or r.get('schema')!='s3-final-production-gpio-cpu-v1' or
     r.get('actual_generic_macro_instances')!=374 or r.get('definitions')!=expected or
     r.get('source_drift')!=[] or r.get('outputs')!=304128 or len(r.get('layers',[]))!=12):
  raise ValueError('actual final production GPIO complete12 PASS required')
 if files(a.run/'source')!=r['source_sha256'] or files(a.vectors)!=r['vector_byte_sha256']:
  raise ValueError('source/vector bytes drifted since actual simulation')
 for name,digest in r['ppa_binding']['production_rtl_files'].items():
  if sha(a.run/name)!=digest:raise ValueError('production source differs: '+name)
 if len(r['ppa_binding']['ordered_compile_sources'])!=159 or r['ppa_binding']['definitions_exact']!=expected:
  raise ValueError('final source SET/defines binding differs')
 origin=Path(r['replay']['path']);baseline=json.loads((origin/'result.json').read_text())
 binary=origin/'simulator/sysbus32_gpio_soc'
 if (sha(binary)!=r['simulator_sha256'] or baseline['ppa_binding']!=r['ppa_binding'] or
     baseline['source_sha256']!=r['source_sha256']):raise ValueError('replay binary/base source binding differs')
 for name,key in [('dma_day_soc','elf_sha256'),('dma_day_soc.verilog','image_sha256')]:
  if sha(a.run/'firmware'/name)!=r['firmware'][key]:raise ValueError('firmware drift')
 checker_path=a.run/'source/check_results.py'
 spec=importlib.util.spec_from_file_location('frozen_final_gpio_export_checker',checker_path)
 checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
 checked=checker.check_log((a.run/'simulation.log').read_text(),12,8,'warmup' in r,
  x_macros=True,storage_configuration=r['storage_binding'])
 for key,value in checked.items():
  if r.get(key)!=value:raise ValueError('raw checker replay differs: '+key)
 a.out.mkdir(parents=True,exist_ok=False)
 for origin_file,target in [(a.run/'result.json','result.json'),(a.run/'simulation.log','simulation.log'),
   (checker_path,'check_results.py'),
   (a.run/'firmware/dma_day_soc.verilog','firmware-image.verilog'),(origin/'result.json','base-task0-result.json')]:
  shutil.copy2(origin_file,a.out/target)
 dump(a.out/'source-manifest.json',r['source_sha256'])
 summary={key:r[key] for key in ['outputs','total_cycles','load_to_y_cycles','source_loading_cycles','clear_cycles','dma_payload_cycles',
  'inter_task_gap_cycles','inter_task_gap_total_cycles','campaign_clear_to_last_y_cycles','campaign_gpio_first_input_to_last_y_cycles',
  'task_per_second_at_assumed_150mhz','gpio_input_to_y_task_per_second_at_assumed_150mhz',
  'campaign_clear_to_last_y_task_per_second_at_assumed_150mhz','campaign_gpio_first_input_to_last_y_task_per_second_at_assumed_150mhz']}
 summary.update(configuration_identity='GPIO374_INDEPENDENT_NOT_1064_N3_CANDIDATE',
  schema='final374-production-gpio-complete12-evidence-v1',status='PASS_RAW_CHECKER_REPLAY_SAME_FROZEN_PRODUCTION12',
  exported_at=datetime.now(timezone.utc).isoformat(),run=str(a.run),result_sha256=sha(a.run/'result.json'),
  actual_macros=r['actual_generic_macro_instances'],source_count=159,definitions=expected,ppa_binding=r['ppa_binding'],
  layers=[dict(layer=item['layer'],outputs=item['outputs'],total=item['total'],load_to_y=item['load_to_y'],loading=item['loading'],
    clear=item['clear'],dma_payload=item['dma_payload'],last_y_retirement=item['last_y_retirement']) for item in r['layers']],
  timing_scope=dict(per_task='First GPIO data presentation through final Y write response retirement; conservative clear-through-finalY separately',
    continuous='First formal input through final formal Y across12, including every intertask gap',
    gaps='CPU verification readback, next-task poison, task control and handshake between adjacent per-task clear-toY windows',
    clock='150MHz assumed conversion only; not achieved STA frequency'),
  qualification='Complete functional GPIO/CPU12 evidence; no STA, area, mapped equivalence, power or official600 pass',
  exporter_sha256=sha(Path(__file__)),artifacts={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in a.out.iterdir() if p.is_file()})
 dump(a.out/'summary.json',summary)
 print(json.dumps({k:summary[k] for k in ['status','outputs','total_cycles','load_to_y_cycles','inter_task_gap_total_cycles','campaign_gpio_first_input_to_last_y_cycles']}))
if __name__=='__main__':main()
