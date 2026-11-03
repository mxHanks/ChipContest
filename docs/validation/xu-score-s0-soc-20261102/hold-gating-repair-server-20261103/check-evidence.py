#!/usr/bin/env python3
"""xu: verify lossless raw repair/STA/FM evidence; never qualify untested checks."""
from pathlib import Path
import collections,hashlib,json,lzma,re
HERE=Path(__file__).resolve().parent

def need(ok,why):
 if not ok:raise ValueError(why)
def sha(b):return hashlib.sha256(b).hexdigest()
def audit(root=HERE):
 entries=json.loads((root/'raw-manifest.json').read_text());seen=set();raw={}
 for e in entries:
  p=Path(e['path']);need(not p.is_absolute()and '..'not in p.parts and str(p)not in seen,'unsafe/duplicate archive path');seen.add(str(p));f=root/p;need(f.is_file()and not f.is_symlink(),'raw file missing/link');b=f.read_bytes();need(len(b)==e['stored_bytes']and sha(b)==e['stored_sha256'],'stored raw identity differs')
  need(e['compression']in ['none','xz'],'unexpected compression');b=lzma.decompress(b)if e['compression']=='xz'else b;x=e['original'];need(len(b)==x['bytes']and sha(b)==x['sha256'],'expanded original identity differs')
  exported=json.loads((root/(e['export']+'-manifest.json')).read_text());need(sum(z==x for z in exported)==1,'original manifest entry differs');need(x['path']not in raw,'duplicate original');raw[x['path']]=b
 def text(group,name):return raw[group+'/'+name].decode()
 old='full-soc-hold-repair-20261103-08';new='full-soc-gating-margin-repair-20261103-09';fm='full-soc-gating-formality-20261103-09';summaries={}
 for group,gating_hold_violations,total_violations in [(old,19,24),(new,0,5)]:
  state=json.loads(text(group,'state.json'));need(state['status']=='EXECUTED_NOT_QUALIFIED','repair execution not terminal')
  for r in state['runs']:
   label='dc'if r['tool']=='dc_shell'else 'pt';script='repair.tcl'if label=='dc'else 'sta.tcl';need(r['returncode']==0 and r['marker_count']==1 and not r['errors'],'repair EDA execution failed');need(sha(raw[group+'/'+label+'.log'])==r['log_sha256']and sha(raw[group+'/'+script])==r['script_sha256'],'repair execution hash differs')
  for name,r in state['reports'].items():need(len(raw[group+'/'+name])==r['bytes']and sha(raw[group+'/'+name])==r['sha256'],'reported raw identity differs')
  coverage=text(group,'analysis-coverage.rpt');table={}
  for line in coverage.splitlines():
   m=re.fullmatch(r'(setup|hold|recovery|removal|min_period|min_pulse_width|clock_gating_setup|clock_gating_hold|out_setup|out_hold)\s+(\d+)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)',line)
   if m:table[m[1]]=dict(zip(['total','met','violated','untested'],map(int,m.groups()[1:])))
  need(len(table)==10,'coverage summary incomplete');need(all(x['total']==x['met']+x['violated']+x['untested']for x in table.values()),'coverage does not conserve')
  need(table['setup']['violated']==table['hold']['violated']==0,'tested data timing differs');need(table['clock_gating_hold']['violated']==gating_hold_violations and table['removal']['violated']==5,'residual violations differ');need(sum(x['violated']for x in table.values())==total_violations,'total violations differ');need(sum(x['untested']for x in table.values())==27127,'untested checks changed')
  script=text(group,'sta.tcl');need('set_clock_gating_check'not in script and 'constraints.sdc' in script and 'xu-ts16.tcl'in script,'final PT clock/gating analysis changed')
  constraints=text(group,'constraints.rpt')
  electrical=collections.Counter()
  for block in constraints.split('    Pin: ')[1:]:
   kind=re.findall(r'^\s*(?:-\s*)?(max_capacitance|min_capacitance)\s+',block,re.M)
   need(len(kind)==1 and '(VIOLATED' in block,'electrical constraint block differs')
   electrical[kind[0]]+=1
  need(dict(electrical)==dict(max_capacitance=56,min_capacitance=1404),'electrical violations differ')
  reported_timing=len(re.findall(r'^  slack \(VIOLATED(?:: increase significant digits)?\)',constraints,re.M))
  need(reported_timing==5+(10 if group==old else 0),'constraint timing path report count differs')
  # report_constraint emits paths per constrained endpoint, while coverage
  # counts edge/check combinations: old gating hold has19 checks but10 paths.
  summaries[group]=dict(coverage=table,constraint_report_violated_timing_paths=reported_timing,electrical_violation_pin_blocks=dict(electrical),electrical_slack_scope='Original report uses low precision: 0.00 marked VIOLATED is not zero or a pass; precise diagnosis pending.',mapped_netlist_sha256=state['mapped_netlist_sha256'],timing=state['timing'])
 ns=json.loads(text(new,'state.json'));os=json.loads(text(old,'state.json'));need(ns['input_sha256'][next(k for k in ns['input_sha256']if k.endswith(old+'/mapped.v'))]==os['mapped_netlist_sha256'],'repair chain differs')
 need(ns['input_sha256'][next(k for k in ns['input_sha256']if k.endswith('/constraints.sdc'))]=='404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98','final analysis SDC differs')
 need('set_clock_gating_check -hold 0.12 [all_clocks]'in text(new,'repair.tcl'),'conservative synthesis margin differs')
 fs=json.loads(text(fm,'state.json'));need(fs['status']=='VERIFIED_REVIEW_PENDING_NOT_QUALIFIED'and fs['returncode']==0 and fs['frozen_before']==fs['frozen_after'],'FM execution/input stability differs');need(sha(raw[fm+'/fm.log'])==fs['log']['sha256']and sha(raw[fm+'/verify.tcl'])==fs['script']['sha256'],'FM raw identity differs');net=next(v for k,v in fs['frozen_before'].items()if k.endswith(new+'/mapped.v'));need(net['sha256']==ns['mapped_netlist_sha256'],'FM verified a different mapped implementation');log=text(fm,'fm.log');need(log.splitlines().count('XU_FULL_SOC_FORMALITY_PASS')==1 and '41462 Passing compare points'in log and 'Verification SUCCEEDED'in log,'FM completion differs')
 need('set synopsys_auto_setup true'in text(fm,'verify.tcl')and 'verification_verify_directly_undriven_output false'in log and '17(0) Unmatched reference(implementation) compare points'in log,'conditional FM limits omitted')
 passing=re.findall(r'^Passing \(equivalent\)\s+((?:\d+\s+){7}\d+)\s*$',log,re.M)
 unread=re.findall(r'^\s*Unread\s+((?:\d+\s+){7}\d+)\s*$',log,re.M)
 need(len(passing)==len(unread)==1 and list(map(int,passing[0].split()))==[17136,0,0,0,144,24143,39,41462] and list(map(int,unread[0].split()))==[0,0,0,0,0,511,0,511],'final FM passing/unread categories differ')
 coverage=text(new,'analysis-coverage.rpt');detail=coverage[coverage.index('\nu_soc/'):].lstrip('\n');records=[]
 for block in re.split(r'(?m)(?=^\S)',detail):
  if not block:continue
  if block=='1\n':continue
  need(block.startswith(('u_soc/','u_shared/')),'unknown coverage detail row');pin=block.splitlines()[0].strip();reason=re.search(r'untested\s+(\S+)',block);check=re.search(r'\b(setup|hold|recovery|removal|min_period|min_pulse_width|clock_gating_setup|clock_gating_hold|out_setup|out_hold)\b',block);need(reason is not None and check is not None,'coverage detail malformed');records.append((pin,check[0],reason[1]))
 need(len(records)==27127,'coverage detail count mismatch');counts=collections.Counter(reason for pin,check,reason in records);need(dict(counts)==dict(constant_disabled=17672,no_clock=9129,false_paths=276,no_endpoint_clock=48,unknown=2),'coverage reasons differ')
 roles=collections.Counter((reason,pin.rsplit('/',1)[-1].split('(')[0])for pin,check,reason in records if reason in ['no_clock','no_endpoint_clock','unknown'])
 need(roles==collections.Counter({('no_clock','RDN'):8676,('no_clock','SDN'):429,('no_clock','E'):24,('no_endpoint_clock','D'):48,('unknown','SDN'):2}),'unresolved pin roles differ')
 return dict(status='CONDITIONAL_MAPPED_CONSISTENCY_VERIFIED_TIMING_NOT_QUALIFIED',raw_files=len(entries),raw_bytes=sum(e['original']['bytes']for e in entries),repairs=summaries,fm=dict(passing=41462,unread=511,unmatched_reference=17,sram_internals='black_box_not_proven',direct_undriven_outputs_verified=False),untested_reasons=dict(counts),unresolved_pin_roles=[dict(reason=k[0],pin=k[1],checks=v)for k,v in sorted(roles.items())],classification_scope='Report reason/pin taxonomy only; no waiver or eligibility conclusion. Mapped/DB/SVF hashes are remote execution records; those large binaries are not locally rehashed.')
if __name__=='__main__':print(json.dumps(audit(),sort_keys=True,indent=2))
