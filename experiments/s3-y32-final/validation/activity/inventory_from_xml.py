#!/usr/bin/env python3
"""Generate exact final374 activity paths from independent production PPA XML."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--preflight',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();r=json.loads((a.preflight/'result.json').read_text());xml=a.preflight/'elaborated.xml'
if r['status']!='PASS_EXACT374_N2_XML_NOT_PPA' or sha(xml)!=r['xml_sha256']:
 raise ValueError('completed exact final PPA XML preflight required')
paths=[c.attrib['hier'] for c in ET.parse(xml).getroot().findall('.//cell') if c.attrib.get('submodname')=='RAMSP1024X16']
if len(paths)!=374 or len(set(paths))!=374 or sorted(paths)!=sorted(r['macro_paths']):
 raise ValueError('actual XML macro leaf SET differs from preflight')
macros={}
for item in paths:
 path=item.replace('__BRA__','[').replace('__KET__',']')
 for branch,repl in [('u_soc','dut'),('u_shared','endpoint')]:
  prefix='xu_soc_sysbus32_ppa_top.'+branch+'.'
  if path.startswith(prefix):path='TOP.tb_sysbus32_soc.'+repl+'.'+path[len(prefix):];break
 else:raise ValueError('macro outside actual SoC/shared scopes')
 groups=[g for g,pat in [('itcm','.u_e203_itcm_ram.'),('dtcm','.u_e203_dtcm_ram.'),('shared','.endpoint.'),
  ('weights','.u_core.weights.'),('bias','.u_core.biasMemory.'),('x','.u_core.xSets['),('result','.u_core.resultSlices[')] if pat in path]
 if len(groups)!=1:raise ValueError('unknown/ambiguous physical macro owner: '+path)
 macros[path]=groups[0]
counts=dict(Counter(macros.values()))
if counts!=dict(itcm=32,dtcm=32,shared=256,weights=16,bias=1,x=16,result=21):raise ValueError('physical grouping differs')
result=dict(name='final-dma4-storage374-production-n2',macros=dict(sorted(macros.items())),group_counts=counts,
 source_review=dict(method='Actual independently elaborated final production PPA XML, not observed FST',
  preflight=str(a.preflight.resolve()),preflight_result_sha256=sha(a.preflight/'result.json'),xml_sha256=sha(xml),
  package_files_sha256=r['package_files_sha256'],mapping={'u_soc':'dut','u_shared':'endpoint'},
  decoding='Verilator __BRA__/__KET__ decoded to literal brackets; no wildcard/numeric-only inventory'))
with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps(dict(status='EXACT_XML374_INVENTORY',macros=len(macros),groups=counts)))
