#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,re,argparse
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--out',type=Path);a=p.parse_args()
def need(v,m):
 if not v:raise ValueError(m)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
sel=read(H/'selected-manifest.json');orig=read(H/'original-export-manifest.json');need(len(sel)==21 and len({r['path']for r in sel})==21,'raw count differs')
for r in sel:
 need([s for s in orig if s['path']==r['path']]==[r],'original selection differs');p=H/'raw'/r['path'];need(p.stat().st_size==r['bytes']and sha(p)==r['sha256'],'raw bytes differ')
D=H/'raw/saif-power-task00-20261103-06';P=D/'power';e=read(P/'execution.json');prepared=read(P/'prepared.json');t=prepared['tasks'][0]
need(e['status']=='PARTIAL_EXECUTED_REVIEW_PENDING'and e['qualification']=='NOT_QUALIFIED'and e['requested_task_ids']==[0]and e['taskset_complete']is False,'power scope/status differs')
need(e['input_sha256_before']==e['input_sha256_after']and e['prepared']['sha256']==sha(P/'prepared.json')==e['prepared_sha256_after']and e['tool']['sha256']==e['tool_sha256_after'],'frozen before/after differ')
x=e['tasks'][0];need(x['task_id']==0 and x['execution']['returncode']==0 and len(x['reports'])==26,'actual PT execution/report set differs')
need((P/'task_00/pt.log').read_text().splitlines().count(t['completion_marker'])==1,'unique PT completion marker differs')
verified=[];missing=[]
for name,r in x['reports'].items():
 p=P/'task_00'/name
 if p.is_file():need(p.stat().st_size==r['bytes']and sha(p)==r['sha256'],'actual report hash differs');verified.append(name)
 else:missing.append(name)
need(sha(P/'task_00/pt.log')==x['execution']['log']['sha256'],'actual PT log differs')
r=read(H/'raw/power06-independent-report-review-20261103-02/result.json');need(r['status']=='REPORTS_RECHECKED_REVIEW_PENDING_NOT_QUALIFIED'and r['reports']==x['reports']and r['macro_count']==336 and r['pin_count']==22512,'independent marker/report receipt differs')
# This classifies tool provenance; marker coverage is not activity-value coverage.
text=(P/'task_00/read-saif.rpt').read_text();need('48551 (34.73%)'in text or '48551(34.73%)'in text,'read-SAIF file summary differs')
need('2046 (1.69%)'in text or '2046(1.69%)'in text,'fully annotated leaf summary differs')
result=dict(status='RECHECKED_PARTIAL_ACTUAL_PT_EXECUTION_NOT_QUALIFIED',actual_task_id=0,macro_markers=336,pin_markers=22512,complete_phase_marker_sets=True,activity_values_and_sources_compared=False,reported_file_nets=48551,total_nets=139779,reported_fully_annotated_leaf_cells=2046,total_leaf_cells=121078,retrieved_report_hashes_verified=verified,unretrieved_report_bytes=missing,raw_power_watts_rounded='0.0329',qualification='NOT_QUALIFIED',limitations=['Only task00; baseline12 activity/power campaign separate','No per-pin value/source audit in original checked_reports; marker presence alone is not annotation proof','Unknown SRAM states, Liberty when/internal_power joint control modes, propagated/default activity and inconsistent annotations remain unresolved','No full150MHz timing qualification; this is not scored task energy','Two original pin-attribute dumps ~806/804MB remain on server with SHA; local first-pin excerpts are derived, not whole-file coverage'])
if a.out:a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print('PASS actual task00 PT rc0, immutable inputs,26 report identities and full336/22512 marker receipts; NOT_QUALIFIED')
