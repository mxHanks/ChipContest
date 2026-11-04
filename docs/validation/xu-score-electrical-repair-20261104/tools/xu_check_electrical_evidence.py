#!/usr/bin/env python3
"""Verify exact collected bytes and rederive electrical evidence counts.
Uses only the Python standard library. Does not run EDA or modify any RTL.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,ast,csv,hashlib,io,json,lzma,re
ROOT=Path(__file__).resolve().parents[1]
ACTUAL49='5df0b568d1751d19388edb33d244f8b19051a9fa7c77b24a2e023bf1e2ee4b4c'
ORIGINAL09='5610f32b23220c87d39b45f24133adbf867d7faeb7284eed5f75d84b77ef4fca'
def sha(data):return hashlib.sha256(data).hexdigest()
def require(condition,message):
 if not condition:raise AssertionError(message)
def rows(data):return list(csv.DictReader(io.StringIO(data.decode()),delimiter='\t'))
def read_evidence():
 binding=json.loads((ROOT/'source-bindings.json').read_text());data={};count=0
 for export,entry in binding['source_manifests'].items():
  raw=(ROOT/entry['stored_path']).read_bytes();require(len(raw)==entry['bytes']and sha(raw)==entry['sha256'],'source manifest identity: '+export)
 for key,group in binding['groups'].items():
  mp=binding['source_manifests'][group['source_export']]['stored_path'];manifest={e['path']:e for e in json.loads((ROOT/mp).read_text())}
  require(len(group['files'])==group['raw_file_count'],'raw file count: '+key)
  data[key]={}
  for record in group['files']:
   stored=(ROOT/record['stored_path']).read_bytes();require(len(stored)==record['stored_bytes']and sha(stored)==record['stored_sha256'],'stored bytes: '+record['stored_path'])
   raw=lzma.decompress(stored)if record['storage']=='xz'else stored
   require(len(raw)==record['original_bytes']and sha(raw)==record['original_sha256'],'original bytes: '+record['stored_path'])
   e=manifest[record['source_manifest_entry']];require(e['bytes']==len(raw)and e['sha256']==sha(raw),'collected manifest mismatch: '+record['stored_path'])
   require(record['original_filename']not in data[key],'duplicate original name');data[key][record['original_filename']]=raw;count+=1
 for name,e in binding['additional_sources'].items():
  raw=(ROOT/name).read_bytes();require(len(raw)==e['bytes']and sha(raw)==e['sha256'],'helper/host evidence source changed: '+name)
 catalog=json.loads((ROOT/'provenance/installed-command-bindings40.json').read_text());manifest={e['path']:e for e in json.loads((ROOT/catalog['source_export_manifest']).read_text())}
 for command,e in catalog['commands'].items():
  original=manifest[e['source_manifest_entry']];require(original['sha256']==e['original_sha256']and original['bytes']==e['original_bytes'],'installed manual identity: '+command)
 require(not any(p.name in {'insert_buffer.txt','remove_cell.txt','size_cell.txt','get_alternative_lib_cells.txt'}for p in ROOT.rglob('*')),'installed manual full text must stay private')
 return binding,data,count

def caps(data):
 result={}
 for block in data.decode().split('    Pin: ')[1:]:
  pin=block.splitlines()[0];require(pin not in result,'duplicate capacitance pin')
  maximum=re.search(r'^\s*max_capacitance\s+([\d.Ee+-]+)\s*\n\s*-\s+Capacitance\s+([\d.Ee+-]+)',block,re.M)
  minimum=re.search(r'^\s*Capacitance\s+([\d.Ee+-]+)\s*\n\s*-\s+min_capacitance\s+([\d.Ee+-]+)',block,re.M)
  require(bool(maximum)!=bool(minimum),'unrecognized capacitance block: '+pin)
  result[pin]={'kind':'max_capacitance'if maximum else 'min_capacitance','limit':float(maximum[1]if maximum else minimum[2]),'load':float(maximum[2]if maximum else minimum[1])}
 return result

def coverage(data):
 result={};pattern=r'^([a-z_]+|All Checks)\s+(\d+)\s+(\d+)\s+\(\s*\d+%\)\s+(\d+)\s+\(\s*\d+%\)\s+(\d+)\s+\(\s*\d+%\)'
 for match in re.finditer(pattern,data.decode(),re.M):result[match[1]]=dict(zip(('total','met','violated','untested'),map(int,match.groups()[1:])))
 require(len(result)==11,'all ten check classes and aggregate required')
 require(result['All Checks']=={'total':294512,'met':267380,'violated':5,'untested':27127},'coverage aggregate differs')
 return result

def reset_failures(data):
 result={}
 for block in data.decode().split('  Startpoint: ')[1:]:
  require(block.splitlines()[0].strip()=='io_pads_aon_erst_n_i_ival','reset raw startpoint differs')
  require('removal check against rising-edge clock xu_lfextclk'in block,'reset check type differs')
  endpoint=re.search(r'^  Endpoint: (\S+)',block,re.M);slack=re.search(r'^  slack \(VIOLATED\)\s+([-\d.]+)',block,re.M)
  pins=re.findall(r'^  (\S+/(?:RDN|SDN)) \((\S+)\)',block,re.M)
  require(endpoint is not None and slack is not None and len(pins)==1,'reset endpoint parse')
  require(endpoint[1]not in result,'duplicate reset endpoint')
  result[endpoint[1]]={'pin':pins[0][0],'ref':pins[0][1],'slack_ns':float(slack[1])}
 require(len(result)==5,'exact five reset failures required')
 require(sorted(e['slack_ns']for e in result.values())==[-0.12148283,-0.11847966,-0.04010564,-0.04010564,-0.04010564],'actual five reset slacks differ')
 return result

def state_reports(group,state):
 for name,e in state['reports'].items():require(len(group[name])==e['bytes']and sha(group[name])==e['sha256'],'state report identity: '+name)

def audit():
 binding,data,raw_count=read_evidence();a=data['actual49'];b=data['baseline14'];s49=json.loads(a['state.json']);s14=json.loads(b['state.json']);s42=json.loads(data['actual42']['state.json'])
 require(s49['status']=='EXECUTED_NOT_QUALIFIED'and s49['mapped_netlist_sha256']==ACTUAL49,'actual49 terminal identity')
 require(len(a)==27 and len(data['actual42'])==3,'27 actual49 and3 actual42 originals required')
 require(s42['status']=='FAIL'and s42['error']=='actual library proposal generation failed','actual42 did not fail at proposal generation')
 require('AssertionError:'in data['actual42']['proposal.log'].decode()and 'min_capacitance'in data['actual42']['proposal.log'].decode(),'actual42 parser failure origin')
 require(len(s49['runs'])==2,'49 DC/PT runs required')
 for label,run,marker in zip(('dc','pt'),s49['runs'],('XU_FULL_SOC_CAP_SIZE_REPAIR_DC_DONE_NOT_QUALIFIED','XU_FULL_SOC_CAP_SIZE_REPAIR_PT_DONE_NOT_QUALIFIED')):
  require(run['returncode']==0 and not run['errors']and run['marker_count']==1,'49 run did not execute cleanly')
  require(sha(a[label+'.log'])==run['log_sha256'],'49 log identity')
  require(sha(a['repair.tcl'if label=='dc'else 'sta.tcl'])==run['script_sha256'],'49 script identity')
  require(a[label+'.log'].decode().splitlines().count(marker)==1,'49 independent completion marker')
 state_reports(a,s49);state_reports(b,s14)
 require(s14['status']=='DIAGNOSTIC_EXECUTED_NOT_QUALIFIED'and s14['returncode']==0 and not s14['errors']and s14['frozen_before']==s14['frozen_after'],'baseline14 execution identity')
 original49={n:v for n,v in s49['input_sha256'].items()if n.endswith('/full-soc-gating-margin-repair-20261103-09/mapped.v')};require(list(original49.values())==[ORIGINAL09],'49 ancestry changed')
 for suffix,expected in [('/full-soc-pt-compatible-05/constraints.sdc','404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'),('/xu-ts16.tcl','45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e')]:
  require([v for n,v in s49['input_sha256'].items()if n.endswith(suffix)]==[expected],'original constraint identity')
 c14=caps(b['constraints.rpt']);c49=caps(a['constraints.rpt']);counts14=Counter(v['kind']for v in c14.values());counts49=Counter(v['kind']for v in c49.values());require(counts14=={'max_capacitance':56,'min_capacitance':1404}and counts49=={'min_capacitance':1404},'actual max56to0/min1404 counts')
 min14={p:v for p,v in c14.items()if v['kind']=='min_capacitance'};require(min14==c49 and all(v['load']==0 for v in c49.values()),'mincap pins, limits, or loads changed')
 cv14=coverage(b['analysis-coverage.rpt']);cv49=coverage(a['analysis-coverage.rpt']);require(cv14==cv49,'coverage check-class counts changed')
 rf14=reset_failures(b['hold.rpt']);rf49=reset_failures(a['hold.rpt']);require(rf14==rf49,'reset identities/slacks changed')
 require('No paths with slack less than 0.00000000.'in a['setup.rpt'].decode(),'49 setup violator report changed')
 source=rows(data['palette41']['source-pins.tsv']);palette=rows(data['palette41']['library-palette.tsv']);topology=rows(data['topology35']['topology.tsv']);require(len(source)==1460 and len({r['pin']for r in source})==1460,'41 source pins')
 require(Counter(r['kind']for r in source)==counts14 and {r['pin']for r in source}==set(c14),'41 original pins binding')
 for name,status in [('topology35','TOPOLOGY_EXPORTED_REVIEW_PENDING_NOT_QUALIFIED'),('palette41','CELL_PALETTE_EXPORTED_REVIEW_PENDING_NOT_QUALIFIED')]:
  state=json.loads(data[name]['state.json']);require(state['status']==status and state['returncode']==0 and not state['errors']and state['frozen_before']==state['frozen_after'],'35/41 query state')
  require([v for n,v in state['frozen_before'].items()if n.endswith('/full-soc-gating-drc-precision-20261103-14/constraints.rpt')]==[sha(b['constraints.rpt'])],'35/41 original constraints binding')
  require([v for n,v in state['frozen_before'].items()if n.endswith('/full-soc-gating-margin-repair-20261103-09/mapped.v')]==[ORIGINAL09],'35/41 original netlist binding')
  for n,e in state['outputs'].items():require(len(data[name][n])==e['bytes']and sha(data[name][n])==e['sha256'],'35/41 output identity: '+n)
 require(json.loads(data['topology35']['state.json'])['frozen_before']==json.loads(data['palette41']['state.json'])['frozen_before'],'35/41 must have identical frozen original inputs')
 lib=defaultdict(dict);byref=defaultdict(set)
 for r in palette:lib[r['libcell']][r['libpin'].rsplit('/',1)[1]]=r;byref[r['libcell'].rsplit('/',1)[1]].add(r['libcell'])
 sized=rows(a['sized-cells.tsv']);plan=json.loads(a['size-plan.json']);proposals={r['cell']:r for r in plan['max_cap_size_proposals']}
 require(len(sized)==56 and len({r['cell']for r in sized})==56 and set(proposals)=={r['cell']for r in sized}and not plan['max_cap_no_legal_candidate'],'56 actual sizing records/proposals')
 require({r['cell']for r in source if r['kind']=='max_capacitance'}==set(proposals),'sizing original drivers differ')
 for r in sized:
  before=byref[r['before_ref']];after=byref[r['after_ref']];require(len(before)==1 and len(after)==1 and before!=after,'actual sizing library references')
  before=next(iter(before));after=next(iter(after));require({v['family']for v in lib[before].values()}=={v['family']for v in lib[after].values()},'sizing family changed')
  require(proposals[r['cell']]['selected']['libcell']==after and proposals[r['cell']]['current_libcell']==before,'actual sizing selection differs')
 grouped=defaultdict(list)
 for r in topology:grouped[r['source_pin']].append(r)
 require(set(grouped)==set(c14),'35 topology coverage of exact original pins')
 dead=set()
 for pin in min14:
  rs=grouped[pin];require(len(rs)==1 and rs[0]['object']==pin and rs[0]['object_class']=='pin'and rs[0]['direction']=='out','35 mincap leaf receiver exists');dead.add(pin)
 owners={r['cell']:r['ref']for r in source if r['kind']=='min_capacitance'};require(len(owners)==1404,'whole-cell candidate count')
 for owner,ref in owners.items():
  choices=byref[ref];require(len(choices)==1,'candidate actual library reference ambiguous');lc=next(iter(choices));outputs={owner+'/'+p for p,r in lib[lc].items()if r['direction']=='out'};require(outputs and outputs.issubset(dead),'whole-cell actual output set not proven')
 plic=[owner for owner,ref in owners.items()if ref=='DRNQV0_12TR40'];require(len(plic)==3 and all(re.search(r'/flop_o_irq\.plic_irq_prio_dffr/qout_r_reg\[[012]\]$',p)for p in plic),'only exact3 unused priority flop candidates')
 prior=json.loads(data['successful09']['state.json']);require(prior['status']=='VERIFIED_REVIEW_PENDING_NOT_QUALIFIED'and prior['returncode']==0 and prior['frozen_before']==prior['frozen_after'],'prior09 FM state')
 require(sha(data['successful09']['fm.log'])==prior['log']['sha256']and data['successful09']['fm.log'].decode().splitlines().count('XU_FULL_SOC_FORMALITY_PASS')==1,'prior09 full FM log')
 require(sha(data['successful09']['verify.tcl'])==prior['script']['sha256'],'prior09 FM script')
 for p in (ROOT/'tools').glob('*.py'):ast.parse(p.read_text())
 h50=json.loads((ROOT/'host-checks/min-cleanup50-host-check.json').read_text());h55=json.loads((ROOT/'host-checks/reset-host-check55.json').read_text())
 require(h50['helper_sha256']==sha((ROOT/'tools/launch_min_cell_cleanup50.py').read_bytes()),'50 host test helper binding')
 require(h55['helper_sha256']==sha((ROOT/'tools/launch_reset_buffer55.py').read_bytes()),'55 host test helper binding')
 return {'status':'RAW_HASH_AND_COUNT_AUDIT_PASS_NOT_NEW_EDA_NOT_QUALIFIED','raw_files_verified':raw_count,'raw_groups':{k:v['raw_file_count']for k,v in binding['groups'].items()},'actual42':{'status':'FAIL','phase':'proposal parser, before DC/PT','execution_evidence':'only3 raw driver/proposal/state files; no sizing result'},'actual49':{'status':s49['status'],'mapped_netlist_sha256_declared_by_server_state':ACTUAL49,'actual_sized_cells':len(sized),'capacitance_before':dict(counts14),'capacitance_after':{'max_capacitance':0,'min_capacitance':counts49['min_capacitance']},'mincap_pin_set_limits_and_zero_loads_unchanged':True,'reset_failures_unchanged':rf49,'coverage':cv49,'max_setup_report':'No negative paths reported under original SDC','full_formal_equivalence':'NOT_RUN_AFTER49'},'cleanup_candidates':{'status':'ORIGINAL09_TOPOLOGY_CANDIDATES_ONLY_NOT_REMOVED','whole_cells_all_outputs_source_only':len(owners),'exact_unused_plic_priority_flops':len(plic),'mandatory_next_gate':'50 rechecks every candidate against exact actual49 inside DC before any removal, audits upstream afterward, then full PT/FM'},'host_only_helpers':{'50':'5 existing host Tcl control modes; no DC/PT execution','54':'Python syntax and frozen-chain source prepared; no new full FM execution','55':'actual49 reset/actual41 palette binding and generated Tcl completeness; no insertion/PT/FM execution'},'scope':['Original SDC, original library hashes and original mapped RTL are unchanged by this evidence checker.','Actual49 mapped.v and SVFs were not in the27 returned raw files; this host audit verifies the collected state/report/script bytes, not absent server netlist/SVF bytes. Runtime helpers rehash those files.','35/41 prove original09 connectivity/library-output candidates only; actual49 topology must be checked again before removal.','Delay insertion plus full FM can test the existing HF-referenced0-input-delay/LF-check SDC scenario, not every asynchronous reset-release phase, protocol, or MTBF.','All50/54/55 artifacts remain HOST_ONLY and NOT_QUALIFIED.']}

def check_content_manifest():
 p=ROOT/'manifest.json'
 if p.exists():
  m=json.loads(p.read_text())
  for name,e in m['files'].items():
   raw=(ROOT/name).read_bytes();require(len(raw)==e['bytes']and sha(raw)==e['sha256'],'bundle content identity: '+name)
  actual={str(p.relative_to(ROOT))for p in ROOT.rglob('*')if p.is_file()and '__pycache__'not in p.parts and p.name!='manifest.json'};require(actual==set(m['files']),'bundle inventory mismatch')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--write-audit',action='store_true');args=ap.parse_args();result=audit()
 if args.write_audit:(ROOT/'audit.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
 else:
  check_content_manifest();require(json.loads((ROOT/'audit.json').read_text())==result,'recorded audit differs from freshly derived facts')
 print(json.dumps({'status':result['status'],'raw_files_verified':result['raw_files_verified'],'actual49_sized_cells':result['actual49']['actual_sized_cells'],'maxcap':'56->0','mincap':1404,'reset_failures':5,'untested':27127,'50_54_55':'HOST_ONLY_NOT_EDA_NOT_QUALIFIED'},sort_keys=True))
if __name__=='__main__':main()
