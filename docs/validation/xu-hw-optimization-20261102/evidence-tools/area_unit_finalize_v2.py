#!/usr/bin/env python3
"""Crosscheck LEF physical dimensions against exact mapped-library report areas."""
import hashlib,json,re
from pathlib import Path
D=Path.home()/'Desktop';B=D/'xu-hw-optimization-20261102';O=B/'area-units-01';P=B/'ppa'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ram=json.loads((O/'ram-physical-proof.json').read_text());std=json.loads((O/'stdcell-archive-progress.json').read_text())
if std['status']!='PASS' or len(std['selected'])!=1:raise ValueError('physical standard-cell proof incomplete')
ref=P/'baseline-ss-01/references.rpt';text=ref.read_text();checks=[]
for c in std['selected'][0]['cells']:
 values=re.findall(r'^'+re.escape(c['cell'])+r'\s+\S+\s*\n\s*([\d.]+)\s+\d+\s+[\d.]+',text,re.M)
 if not values:raise ValueError('cell absent from mapped-reference report: '+c['cell'])
 areas=set(map(float,values))
 if len(areas)!=1 or abs(next(iter(areas))-c['physical_area_um2'])>1e-5:raise ValueError('physical/reference unit mismatch '+c['cell'])
 checks.append(dict(c,library_report_cell_area=next(iter(areas)),difference=next(iter(areas))-c['physical_area_um2']))
libtext=Path(ram['lib_path']).read_text()
libtext=re.sub(r'/\*.*?\*/','',libtext,flags=re.S)
libtext=re.sub(r'//[^\n]*','',libtext)
cell=re.search(r'\bcell\s*\(\s*"?RAMSP1024X16"?\s*\)\s*\{',libtext)
if not cell:raise ValueError('target SRAM Liberty cell declaration missing')
m=re.search(r'\barea\s*:\s*([\d.eE+-]+)\s*;',libtext[cell.end():])
if not m:raise ValueError('target SRAM area attribute missing')
ram['lib_cell_area']=float(m[1]);ram['area_parser']='comments removed, area from exact cell(RAMSP1024X16) body; earlier generic first-area scan hit a comment'
rc=ram['cells'][0]
if abs(rc['physical_area_um2']-ram['lib_cell_area'])>1e-3:raise ValueError('SRAM LEF area differs from linked Liberty cell area')
paired=P/'paired-exact-audit-01/paired-summary.json';j=json.loads(paired.read_text());cases={}
for name,c in j['cases'].items():
 expected=16*ram['lib_cell_area']
 if abs(expected-c['macro_area'])>0.01:raise ValueError('linked macro area differs from physical library')
 cases[name]=dict(total_cell_area_um2=c['total_cell_area'],standard_cell_area_um2=c['stdcell_area'],sram_macro_area_um2=c['macro_area'],sram_macro_count=16,total_cell_area_mm2=c['total_cell_area']/1e6,limit_mm2=2.5,within_limit=c['total_cell_area']/1e6<=2.5,headroom_mm2=2.5-c['total_cell_area']/1e6,limit_fraction=c['total_cell_area']/1e6/2.5)
result=dict(schema='xu-server-process-library-area-compliance-v1',status='PASS',requirement=dict(source='user instruction 2026-11-02',accelerator_area_limit_mm2=2.5),
 scope='synthesized complete accelerator wrapper incl compute, bias cache, MMIO, X buffer and 16 weight SRAM macros; excludes CPU/interconnect/system shared RAM',
 unit='micrometres squared, established by matching mapped library area to physical LEF SIZE width x height',conversion='1 mm2 = 1000000 um2',
 physical_standard_cells=dict(archive_path=std['archive_path'],archive_bytes=std['archive_bytes'],archive_member=std['selected'][0]['archive_member'],member_sha256=std['selected'][0]['sha256'],checks=checks),
 physical_sram=ram,source_references_report=dict(path=str(ref),sha256=sha(ref)),paired_summary=dict(path=str(paired),sha256=sha(paired)),cases=cases,
 limitations=['Cell plus macro footprint sum from synthesis, not placed-and-routed core/die bounding-box area','No placement utilization, routing space, CTS/hold-fix/tap/filler insertion or final physical overhead included','Physical signoff remains incomplete due to hold violations, untested timing checks and unqualified experimental SRAM adapter'],
 provenance_files={str(p):sha(p) for p in [O/'ram-physical-proof.json',O/'stdcell-archive-progress.json',Path(__file__).resolve()]})
p=O/'area-compliance.json'
with p.open('x') as f:f.write(json.dumps(result,sort_keys=True,indent=2)+'\n')
print('AREA_COMPLIANCE',sha(p),json.dumps(cases,sort_keys=True))
