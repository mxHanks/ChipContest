#!/usr/bin/env python3
"""Seal validated CPU/DMA logs and measured comparisons without altering originals."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['baseline','task0','campaign','dma','out']:p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();campaign=read(a.campaign/'receipt.json');dma=read(a.dma/'receipt.json');base=read(a.baseline/'result.json');full=read(a.campaign/'full12/result.json');one=read(a.task0/'result.json')
 if campaign['status']!='PASS' or dma['status']!='PASS' or base['status']!='PASS' or full['status']!='PASS' or one['status']!='PASS':raise ValueError('all evidence must PASS')
 if base['outputs']!=304128 or full['outputs']!=304128:raise ValueError('complete twelve tasks required')
 if full['vectors_manifest_sha256']!=base['vectors_manifest_sha256']:raise ValueError('performance vector identity changed')
 if full['firmware']['image_sha256']!=base['firmware']['image_sha256']:raise ValueError('loaded CPU firmware image changed')
 for name in ['dma_day_main.c','firmware/start.S','firmware/link.ld']:
  if full['firmware']['source_sha256'][name]!=base['firmware']['source_sha256'][name]:raise ValueError('CPU firmware source changed: '+name)
 old_elf=(a.baseline/'firmware/dma_day_soc').read_bytes();new_elf=(a.task0/'firmware/dma_day_soc').read_bytes()
 normalize=lambda data:re.sub(rb'cc[A-Za-z0-9]{6}\.o\x00',b'ccTEMP00.o\x00',data)
 if normalize(old_elf)!=normalize(new_elf):raise ValueError('firmware ELF differs beyond temporary object symbols')
 if full['source_drift'] or one['source_drift']:raise ValueError('CPU source drift')
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 origins={}
 def copy(origin,name):
  origins[name]={'path':str(origin.resolve()),'sha256':sha(origin)};shutil.copy2(origin,out/name)
 for name,folder in [('baseline',a.baseline),('task0',a.task0),*[(name,a.campaign/name)for name in ['full12','dma-first-wait31','load-first-wait31','serialized-loader']]]:
  copy(folder/'result.json',name+'-result.json');copy(folder/'simulation.log',name+'-simulation.log')
 copy(a.task0/'source-manifest.json','cpu-source-manifest.json');copy(a.campaign/'receipt.json','cpu-campaign.json');copy(a.dma/'receipt.json','dma-receipt.json')
 for name in ['full12','reset-recovery','fault-staging','stall-task0','rows1-task0','last-y-hold-task0']:
  copy(a.dma/(name+'.json'),'dma-'+name+'.json');copy(a.dma/(name+'.log'),'dma-'+name+'.log')
 runs=a.task0.parent
 copy(runs/'endpoint-throttle-probe/tb.sv','endpoint-throttle-probe.sv')
 copy(runs/'endpoint-throttle-probe/result.log','endpoint-throttle-probe.log')
 for name in ['ingress-regression.log','source-invariants.json','checker-negative-cases.json','firmware-container-diff.txt']:copy(runs/name,name)
 gain=full['task_per_second_at_assumed_150mhz']/base['task_per_second_at_assumed_150mhz']
 summary=dict(status='LOCAL_FUNCTIONAL_PERFORMANCE_PASS_NOT_QUALIFIED',baseline_cycles=base['total_cycles'],optimized_cycles=full['total_cycles'],baseline_tasks_per_second=base['task_per_second_at_assumed_150mhz'],optimized_tasks_per_second=full['task_per_second_at_assumed_150mhz'],throughput_factor=gain,cycles_reduction_percent=100*(1-full['total_cycles']/base['total_cycles']),outputs=full['outputs'],frequency_assumption_hz=150000000,firmware_image_sha256=full['firmware']['image_sha256'],baseline_elf_sha256=base['firmware']['elf_sha256'],optimized_elf_sha256=full['firmware']['elf_sha256'],firmware_identity_note='Loaded image and start/C/linker source bytes match; ELF container differs only in compiler temporary object symbol',child_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT/'third-party/e203_hbirdv2',text=True).strip(),scope='Same 504-baseline original-SystemBus loading stimulus; noGPIO-production/STA/area/power qualification',origins=origins)
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 (out/'SHA256SUMS').write_text(''.join(sha(f)+'  '+f.name+'\n' for f in sorted(out.iterdir())if f.is_file()))
 print(json.dumps({k:v for k,v in summary.items()if k!='origins'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
