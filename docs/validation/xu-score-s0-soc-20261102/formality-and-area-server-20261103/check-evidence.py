#!/usr/bin/env python3
"""xu: read-only verification of archived original FM and hierarchical area bytes."""
from pathlib import Path
import hashlib,json,re
R=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def need(ok,why):
 if not ok:raise ValueError(why)
def read(p):return json.loads((R/p).read_text())
m=read('raw-manifest.json');need(len(m)==len({x['path']for x in m}),'duplicate archive path')
for item in m:
 p=R/item['path'];need(p.is_file()and p.stat().st_size==item['bytes']and sha(p)==item['sha256'],'raw byte identity: '+item['path'])
j=read('result.json');fm=read('raw/full-soc-formality-02/state.json');log=(R/'raw/full-soc-formality-02/fm.log').read_text();tcl=R/'raw/full-soc-formality-02/verify.tcl';unmatched=(R/'raw/full-soc-formality-02/unmatched.rpt').read_text()
need(fm['status']=='VERIFIED_REVIEW_PENDING'and fm['returncode']==0 and fm['errors']==[]and fm['pass_marker'],'actual FM state')
need(fm['log_sha256']==sha(R/'raw/full-soc-formality-02/fm.log')==j['formality']['log_sha256'],'FM log identity')
need(fm['script_sha256']==sha(tcl),'FM actual Tcl identity')
need('Verification SUCCEEDED' in log and '41462 Passing compare points' in log and 'XU_FULL_SOC_FORMALITY_PASS' in log,'FM actual success')
need(re.search(r'Passing \(equivalent\)\s+17136\s+0\s+0\s+0\s+144\s+24143\s+39\s+41462',log),'compare point breakdown')
need(re.search(r'Unread\s+0\s+0\s+0\s+0\s+0\s+511\s+0\s+511',log),'unread scope')
need(unmatched.count('valid_read_reg')==16 and unmatched.count('count_reg[15]')==1 and '17 Unmatched points' in unmatched,'unmatched scope')
need('set verification_set_undriven_signals synthesis' in log and 'set verification_verify_directly_undriven_output false' in log,'conditional undriven settings')
for n in ['netlist','svf']:
 filename='mapped.v'if n=='netlist'else'default.svf';items=[v for k,v in fm['input_sha256'].items()if k.endswith('/'+filename)]
 need(items==[j['formality'][n+'_sha256']],'FM declared '+n+' identity')
need(j['official_energy_or_score_computed']is False and j['area_limit_mm2']==2.25,'qualification/limit')
for item in j['area']:
 n=item['candidate'];base='raw/baseline/'if n=='baseline'else'raw/s1-ppa-campaign-01/'+n+'/ppa/';p=R/base/'area.rpt';text=p.read_text();lines=text.splitlines();rows=[i for i,l in enumerate(lines)if re.search(r'/u_accel_icb_slave\s*$',l)]
 need(len(rows)==1,'exact accelerator boundary '+n)
 area=float(lines[rows[0]+1].split()[0]);whole=float(re.search(r'Total cell area:\s*([0-9.]+)',text).group(1))
 need(item['source_report_sha256']==sha(p)and item['accelerator_area_um2']==area and item['accelerator_area_mm2']==area/1e6 and item['whole_soc_area_um2']==whole,'area raw parser '+n)
 need(item['under_area_limit']==(area<2250000)and item['full_soc_150mhz_timing_qualified']is False,'area qualification '+n)
 if n!='baseline':
  e=read(base+'execution.json');need(e['status']=='EXECUTED_NOT_QUALIFIED'and e['reports']['area.rpt']['sha256']==sha(p),'actual execution '+n)
  need(e['netlist_sha256']==item['mapped_netlist_sha256']and e['analysis_sdc_sha256']==item['analysis_sdc_sha256'],'declared execution identity '+n)
  need((R/base/'timing-slack.tsv').read_text()==item['timing_slack_tsv'],'actual timing '+n)
print('PASS xu raw byte identities, conditional full-SoC FM, hierarchical areas and explicit qualification limits; %d raw files'%len(m))
