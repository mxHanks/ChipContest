#!/usr/bin/env python3
"""Read-only actual hierarchical DC area and conditional FM evidence audit."""
from pathlib import Path
import argparse,hashlib,json,re
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path);a=p.parse_args()
def need(v,m):
 if not v:raise ValueError(m)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sel=read(H/'selected-manifest.json');orig=read(H/'original-export-manifest.json');need(len(sel)==41 and len({r['path']for r in sel})==41,'unique raw set differs')
for r in sel:
 need([x for x in orig if x['path']==r['path']]==[r],'raw selection differs');q=H/'raw'/r['path'];need(q.stat().st_size==r['bytes']and sha(q)==r['sha256'],'raw bytes differ')
B=H/'raw';campaign=read(B/'candidate-formality-campaign-20261103-01/state.json');rows=[]
for name,main,child,expected_area,points,dff in [('s2b','a2a1f076060c43fcefb1148edaa83c89bb1d4320','d5faa5e8c857fa35df62a68de667bdb8a6e954f7','286936.4304',41550,24231),('s2c','d276b55ffecbe8d620f9a361bf5d0859299ba7b5','49a9436e01ea8ceeead94242e4a99c16e31a0865','294801.8380',42338,25019)]:
 D=B/(name+'-ppa-campaign-20261103-01')/name;P=D/'ppa';impl=read(D/'implementation/implementation.json');prep=read(P/'prepared.json');e=read(P/'execution.json')
 need(impl['source_freeze']['main_commit']==main and impl['source_freeze']['e203_commit']==child,'candidate source differs')
 need(e['status']=='EXECUTED_NOT_QUALIFIED'and e['dc']['returncode']==e['pt']['returncode']==0,'DC/PT execution differs')
 need(e['dc']['log_sha256']==sha(P/'dc.log'),'actual DC log differs')
 for n,r in e['reports'].items():
  if(P/n).is_file():need(sha(P/n)==r['sha256']and(P/n).stat().st_size==r['bytes'],'report identity differs')
 area=(P/'area.rpt').read_text();lines=area.splitlines();ix=[i for i,l in enumerate(lines)if l.endswith('/u_accel_icb_slave')];need(len(ix)==1,'accelerator boundary differs');parts=lines[ix[0]+1].split();need(parts[0]==expected_area,'actual accelerator area differs')
 whole=float(re.search(r'^Total cell area:\s*([0-9.]+)',area,re.M).group(1));accel=float(parts[0]);clock=(P/'clock-reports/review_status.txt').read_text();need('NO_CLOCK_ENDPOINTS=696'in clock and 'REPORT_COMMAND_FAILURES={exceptions.rpt yes'in clock,'unresolved clock/report review lost')
 f=next(x for x in campaign['runs']if x['candidate']==name);F=B/'candidate-formality-campaign-20261103-01'/name;log=(F/'fm.log').read_text()
 need(f['status']=='VERIFIED_REVIEW_PENDING_NOT_QUALIFIED'and f['returncode']==0 and f['frozen_before']==f['frozen_after'],'conditional actual FM receipt differs')
 need(f['log']['sha256']==sha(F/'fm.log')and log.splitlines().count('XU_FULL_SOC_FORMALITY_PASS')==1 and 'Verification SUCCEEDED'in log,'actual FM log differs')
 need(re.search(r'Passing \(equivalent\)\s+17136\s+0\s+0\s+0\s+144\s+'+str(dff)+r'\s+39\s+'+str(points),log),'FM compare breakdown differs')
 need('set verification_set_undriven_signals synthesis'in log and 'set verification_verify_directly_undriven_output false'in log,'FM conditional undriven handling lost')
 need(re.search(r'Unread\s+0\s+0\s+0\s+0\s+0\s+511\s+0\s+511',log),'FM unread scope differs')
 net=[v for k,v in f['frozen_before'].items()if k.endswith('/mapped.v')];svf=[v for k,v in f['frozen_before'].items()if k.endswith('/default.svf')];need(len(net)==len(svf)==1 and net[0]['sha256']==e['netlist_sha256'],'FM netlist does not match measured PPA')
 unmatched=(F/'unmatched.rpt').read_text();need(unmatched.count('valid_read_reg')==16 and unmatched.count('count_reg[15]')==1 and '17 Unmatched points'in unmatched,'FM unmatched scope differs')
 rows.append(dict(candidate=name,main_commit=main,e203_commit=child,accelerator_area_um2=accel,accelerator_area_mm2=accel/1e6,whole_soc_area_um2=whole,area_limit_mm2=2.25,under_limit=accel<=2250000,area_report_sha256=sha(P/'area.rpt'),mapped_netlist_sha256=e['netlist_sha256'],analysis_sdc_sha256=e['analysis_sdc_sha256'],actual_passing_compare_points=points,actual_passing_blackbox_pins=17136,actual_passing_ports=144,actual_passing_dff=dff,actual_passing_latches=39,unread_dff=511,unmatched_reference_compare_points=17,formality_log_sha256=sha(F/'fm.log'),svf=svf[0],raw_timing_slack=(P/'timing-slack.tsv').read_text(),full_soc_150mhz_qualified=False))
j=dict(status='RECHECKED_SAME_LIBRARY_AREAS_AND_CONDITIONAL_SOC_EQUIVALENCE_NOT_QUALIFIED',candidates=rows,official_energy_or_score_computed=False,qualification_gaps=['ActualPT all-propagated clocks are an unbuffered pre-CTS diagnostic, not closed timing','Collector report_exceptions -verbose failed; raw failure retained','696 unclocked pin entries need library/control/24UART role review','FM SRAM internals are black boxes; synthesis-style undriven and unread/unmatched scope remains explicit','No local rehash of unreturned mapped.v/SVF/library binaries; identity recorded in actual receipts'])
if a.out:a.out.write_text(json.dumps(j,sort_keys=True,indent=2)+'\n')
print('PASS41 immutable raw files; same-library accelerator areas; S2b41550/S2c42338 conditional FM compare points; NOT_QUALIFIED')
