#!/usr/bin/env python3
"""xu: read-only exact raw/high-precision electrical DRC census; no waiver."""
from pathlib import Path
import collections,hashlib,json,lzma,re
H=Path(__file__).resolve().parent

def need(v,m):
 if not v:raise ValueError(m)
def sha(b):return hashlib.sha256(b).hexdigest()
def audit():
 m=json.loads((H/'selected-manifest.json').read_text());orig=json.loads((H/'original-export-manifest.json').read_text());raw={}
 for x in m:
  p=H/x['path'];b=p.read_bytes();need(p.is_file()and not p.is_symlink()and len(b)==x['stored_bytes']and sha(b)==x['stored_sha256'],'stored identity differs');b=lzma.decompress(b)if x['compression']=='xz'else b;o=x['original'];need(o in orig and len(b)==o['bytes']and sha(b)==o['sha256'],'original bytes differ');need(o['path']not in raw,'duplicate raw');raw[o['path']]=b
 def text(n):return raw['full-soc-gating-drc-precision-20261103-14/'+n].decode()
 j=json.loads(text('state.json'));need(j['status']=='DIAGNOSTIC_EXECUTED_NOT_QUALIFIED'and j['returncode']==0 and j['errors']==[] and j['frozen_before']==j['frozen_after'],'actual PT execution differs');need(text('pt.log').splitlines().count('XU_FULL_SOC_HOLD_REPAIR_PT_DONE_NOT_QUALIFIED')==1,'actual PT marker differs');need('report_constraint -all_violators -verbose -significant_digits 8'in text('sta.tcl'),'precision command differs');need(j['env_setup']['SYNOPSYS_LC_ROOT']=='/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5','actual LC environment differs')
 for n,x in j['reports'].items():need(sha(raw['full-soc-gating-drc-precision-20261103-14/'+n])==x['sha256']and len(raw['full-soc-gating-drc-precision-20261103-14/'+n])==x['bytes'],'execution report hash differs')
 need(j['frozen_before'][next(k for k in j['frozen_before']if k.endswith('full-soc-gating-margin-repair-20261103-09/mapped.v'))]=='5610f32b23220c87d39b45f24133adbf867d7faeb7284eed5f75d84b77ef4fca','mapped configuration differs');need(j['frozen_before'][next(k for k in j['frozen_before']if k.endswith('/constraints.sdc'))]=='404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98','analysis SDC differs')
 rows=[]
 for block in text('constraints.rpt').split('    Pin: ')[1:]:
  kind=re.findall(r'^\s*(?:-\s*)?(max_capacitance|min_capacitance)\s+',block,re.M);s=re.search(r'^\s*Slack\s+(-?[\d.]+)\s*\(VIOLATED\)',block,re.M);need(len(kind)==1 and s is not None,'electrical DRC block differs');rows.append(dict(pin=block.splitlines()[0],kind=kind[0],slack_pf=s[1]))
 counts=collections.Counter(x['kind']for x in rows);need(counts==dict(max_capacitance=56,min_capacitance=1404),'electrical count differs');summary={k:dict(pin_blocks=counts[k],worst_slack_pf=min(float(x['slack_pf'])for x in rows if x['kind']==k),best_slack_pf=max(float(x['slack_pf'])for x in rows if x['kind']==k))for k in counts}
 need(summary['max_capacitance']['worst_slack_pf']==-.00129576 and summary['max_capacitance']['best_slack_pf']==-.00025722 and summary['min_capacitance']['worst_slack_pf']==summary['min_capacitance']['best_slack_pf']==-.0005,'precise slack range differs')
 need(len(re.findall(r'^  slack \(VIOLATED\)',text('constraints.rpt'),re.M))==5,'reset violation paths differ')
 return dict(status='ACTUAL_HIGH_PRECISION_DIAGNOSTIC_NOT_QUALIFIED',raw_files=len(m),electrical=summary,rows=rows,remaining_timing_violations=5,full_soc_150mhz_qualified=False,limitations=['Same09 netlist, original SDC and finite scope16; no thresholds or exceptions changed','Capacitance/voltage/clock/untested checks remain to review; electrical negatives are not rounded zero','Large remote DB/netlist/SVF not rehashed locally; execution records freeze their identity'])
if __name__=='__main__':print(json.dumps(audit(),sort_keys=True,indent=2))
