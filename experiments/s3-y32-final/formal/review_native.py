#!/usr/bin/env python3
"""Fail-closed review of actual final374 FM results. No EDA/remote access."""
import argparse,json,re,sys
from collections import Counter
from pathlib import Path
sys.dont_write_bytecode=True
from common import *

REVIEWED=['unmatched_reference','unmatched_implementation','unmatched_primary_reference','unmatched_primary_implementation','match_unread_reference','match_unread_implementation','unread','dont_verify','constants','cuts','hdlin_mismatches','guidance_not_accepted','assumptions','macro_omissions']

def review_coverage(c,folder,decisions,contract,documented_commands):
 need(c['schema']=='final374-fm-native-coverage-v1' and c['collector_complete'] is True,'native coverage collector missing/incomplete')
 need(c['api_contract_sha256']==contract,'coverage API identity differs')
 need(set(c['raw_reports'])==set(REPORTS),'missing raw native report role')
 need(set(c['report_provenance'])==set(REPORTS),'missing actual report-command provenance')
 for role,provenance in c['report_provenance'].items():
  need(provenance['returncode']==0 and provenance['phase'] in ['linked','matched','verified','setup'],'failed/unknown native report collection phase')
  names=provenance['commands'];need(names and set(names)<=set(documented_commands)|({'TCL_VARIABLE_INVENTORY'} if role=='assumptions' else set()),'report collected using unreviewed native API:'+role)
 for role,r in c['raw_reports'].items():
  path=folder/'reports'/(role+'.rpt');need(path.is_file() and path.stat().st_size>0 and record(path)==r,'empty/unbound raw report:'+role)
  need(not re.search(r'^(?:Error:|Fatal:|Unknown command)',path.read_text(errors='replace'),re.M),'native report API error:'+role)
 need(c['unresolved_modules']==[] and c['unexpected_black_boxes']==[],'unresolved or unexpected opaque logic')
 counts=c['compare_counts'];need(counts['passing']>0 and all(counts[k]==0 for k in ['failing','aborted','unverified']),'nonzero failure/abort/unverified or empty proof')
 lists=c['point_lists'];need(set(lists)==set(REVIEWED)|{'failing','aborted','unverified'},'incomplete point/assumption list roles')
 need(all(lists[k]==[] for k in ['failing','aborted','unverified']),'unverified points cannot be reviewed away')
 need(len(lists['unread'])==counts['unread'],'unread objects/count mismatch')
 needed={}
 for category in REVIEWED:
  ids=[r['id'] for r in lists[category]];need(len(set(ids))==len(ids),'duplicate native object:'+category)
  for row in lists[category]:
   need(row.get('evidence_reports') and set(row['evidence_reports'])<=set(REPORTS),'native object without raw evidence:'+row['id'])
   needed[category,row['id']]=row
 need(decisions['schema']=='final374-fm-coverage-decisions-v1' and decisions['coverage_sha256']==sha(folder/'coverage.json'),'review decisions not bound to actual coverage')
 observed={}
 for d in decisions['decisions']:
  key=d['category'],d['id'];need(key not in observed and key in needed,'duplicate/unknown exception decision')
  need(d['decision']=='ACCEPTED_WITH_REASON' and len(d['reason'].strip())>=30 and d.get('reviewer'),'unreviewed scope/assumption:'+str(key))
  need(set(d.get('evidence_reports',[]))>=set(needed[key]['evidence_reports']),'decision omits native evidence')
  observed[key]=d
 need(set(observed)==set(needed),'unreviewed native ignored/unread/unmatched/constant/assumption objects')
 macros=c['physical_macro_boundaries'];need(len(macros)==374,'physical macro inventory must account for all374')
 need(Counter(row['group'] for row in macros)==Counter(GEOMETRY),'physical macro group mismatch')
 need(len({r['canonical_path'] for r in macros})==374,'duplicate physical macro identity')
 refs=set();imps=set();boundary_bits=0
 for row in macros:
  need(row['cell_ref']=='RAMSP1024X16','opaque cell outside approved SRAM')
  if row['disposition']=='PROVED_UNOBSERVABLE':
   need(('macro_omissions',row['canonical_path']) in observed,'unreviewed optimized/omitted macro');continue
  need(row['disposition']=='PAIRED_OPAQUE' and row['reference_path'] and row['implementation_path'],'macro not paired')
  need(row['reference_path'] not in refs and row['implementation_path'] not in imps,'many-to-one opaque pairing')
  refs.add(row['reference_path']);imps.add(row['implementation_path'])
  need(set(row['ports'])==set(PORTS),'macro opaque port set differs')
  for name,(direction,width) in PORTS.items():
   port=row['ports'][name];need(port['direction']==direction and port['width']==width and len(port['bits'])==width,'macro pin direction/width/coverage hole')
   for bit in port['bits']:
    need(bit.get('reference_pin') and bit.get('implementation_pin') and bit.get('evidence_id'),'opaque bit lacks native pairing evidence')
    allowed=['MATCHED_OPAQUE_OUTPUT'] if direction=='output' else ['VERIFIED_COMPARE_POINT','VERIFIED_CONSTANT']
    need(bit['status'] in allowed,'opaque boundary bit was not proved/matched')
    if bit['status']=='VERIFIED_CONSTANT':need(('constants',bit['evidence_id']) in observed,'unreviewed boundary constant')
    boundary_bits+=1
 need(c['resource_limit']['max_cores']==2 and c['resource_limit']['native_report_role']=='resources','native max2core proof missing')
 need(lists['assumptions'],'actual HDL/undriven/auto-setup assumption inventory missing')
 required_assumptions={'synopsys_auto_setup','hdlin_unresolved_modules','verification_set_undriven_signals','verification_verify_directly_undriven_output','hdlin_ignore_parallel_case','hdlin_ignore_full_case','hdlin_error_on_mismatch_message'}
 need(required_assumptions<={r['id'] for r in lists['assumptions']},'actual HDL/undriven/auto-setup variables omitted')
 need(all('actual_value' in r for r in lists['assumptions']),'assumptions must include actual values')
 guidance=c['guidance_counts'];need(set(guidance)=={'accepted','rejected','unsupported','unprocessed','total'} and all(isinstance(v,int) and v>=0 for v in guidance.values()),'guidance inventory missing/invalid')
 need(guidance['accepted']>0 and guidance['total']==sum(guidance[k] for k in ['accepted','rejected','unsupported','unprocessed']) and len(lists['guidance_not_accepted'])==sum(guidance[k] for k in ['rejected','unsupported','unprocessed']),'SVF guidance count/list mismatch')
 return dict(paired_opaque_macros=len(refs),proved_unobservable_macros=374-len(refs),accounted_boundary_bits=boundary_bits,reviewed_exceptions=len(observed),compare_counts=counts)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--preparation',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--decisions',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists(),'new review output required')
 prep=a.preparation.resolve();run=a.run.resolve();b=json.loads((prep/'preparation.json').read_text())
 need(b['status']=='READY_FOR_NATIVE_FULL_TOP_FM_NOT_EXECUTED_NOT_ACCEPTED' and b['verification_tcl_emitted'] is True,'native run was not prepared through source/map/API gates')
 package=Path(b['package']);native=Path(b['native']['directory']);need(sha(package/'package-files.json')==b['package_files_sha256'],'sealed package changed')
 need(native_check(package,native)==b['native'],'own DC/map/SVF binding changed')
 api=api_check(prep/'api-contract.json',prep/'native-adapter.tcl',prep/'native-api-probe.log')
 e=json.loads((run/'execution.json').read_text());need(e['schema']=='final374-native-fm-execution-v1' and e['hardware_profile']==PROFILE and e['top']==TOP and e['defines']==DEFINES,'wrong native FM profile')
 need(e['preparation_sha256']==sha(prep/'preparation.json') and e['verify_tcl']==record(prep/'verify.tcl') and e['adapter']==record(prep/'native-adapter.tcl'),'native script identity differs')
 need(e['status']=='NATIVE_FM_COMPLETE_NOT_ACCEPTED' and e['returncode']==0 and e['tool_timed_out'] is False and e['source_drift']==[] and e['max_cores']==2,'native FM incomplete/timeout/drift/resource mismatch')
 need(e['tool']['sha256']==api['launcher']['sha256'] and e['tool']['path']==api['launcher']['path'],'native launcher identity/argv0 differs')
 need(e['native_tool_errors']==[],'native tool errors')
 for name in ['fm.log','coverage.json',*[f'reports/{n}.rpt' for n in REPORTS]]:
  need(name in e['outputs'] and record(run/name)==e['outputs'][name],'native output unbound:'+name)
 text=(run/'fm.log').read_text(errors='replace')
 need(re.findall(r'^Verification (?:SUCCEEDED|FAILED)[ \t]*$',text,re.M)==['Verification SUCCEEDED'],'unique native verification success required')
 need(re.findall(r'^XU_FINAL374_FM_VERIFY_SUCCEEDED_NOT_ACCEPTED[ \t]*$',text,re.M)==['XU_FINAL374_FM_VERIFY_SUCCEEDED_NOT_ACCEPTED'],'unique actual terminal marker required; Tcl echo is insufficient')
 need(not re.search(r'^(?:Error:|Fatal:|XU_FINAL374_FM_SCRIPT_ERROR|XU_FINAL374_FM_VERIFY_FAILED)',text,re.M),'native script/verify error')
 need('Version '+api['launcher']['native_version'] in text,'native FM version differs from API probe')
 for prefix in ['Reference design: r:/WORK/'+TOP,'Implementation design: i:/WORK/'+TOP]:
  need(len(re.findall(r'^\s*'+re.escape(prefix)+r'[ \t]*$',text,re.M))==1,'full verification top differs')
 c=json.loads((run/'coverage.json').read_text());s=review_coverage(c,run,json.loads(a.decisions.read_text()),sha(prep/'api-contract.json'),api['documented_commands'])
 passing=re.findall(r'^\s*(\d+) Passing compare points[ \t]*$',text,re.M);need(passing==[str(s['compare_counts']['passing'])],'native passing compare-point count differs')
 progress=re.findall(r'(\d+)F/(\d+)A/(\d+)P/(\d+)U \(100% Verification completed\)',text)
 need(progress and tuple(map(int,progress[-1]))==(0,0,s['compare_counts']['passing'],0),'terminal failure/abort/unverified progress differs')
 unread=re.findall(r'^  Unread[ \t]+([0-9 \t]+)$',text,re.M);need(len(unread)==1 and int(unread[0].split()[-1])==s['compare_counts']['unread'],'native final unread count differs')
 match=re.findall(r'^\s*(\d+)\((\d+)\) Unmatched reference\(implementation\) compare points[ \t]*$',text,re.M)
 need(match and set(match)=={(str(len(c['point_lists']['unmatched_reference'])),str(len(c['point_lists']['unmatched_implementation'])))},'native unmatched compare-point count differs')
 primary=re.findall(r'^\s*(\d+)\((\d+)\) Unmatched reference\(implementation\) primary inputs, black-box outputs[ \t]*$',text,re.M)
 need(primary and set(primary)=={(str(len(c['point_lists']['unmatched_primary_reference'])),str(len(c['point_lists']['unmatched_primary_implementation'])))},'native unmatched primary/opaque-output count differs')
 match_unread=re.findall(r'^\s*(\d+)\((\d+)\) Unmatched reference\(implementation\) unread points[ \t]*$',text,re.M)
 need(match_unread and set(match_unread)=={(str(len(c['point_lists']['match_unread_reference'])),str(len(c['point_lists']['match_unread_implementation'])))},'native matching unread list differs from final unread list')
 passing_table=re.findall(r'^Passing \(equivalent\)[ \t]+([0-9 \t]+)$',text,re.M)
 need(len(passing_table)==1 and len(passing_table[0].split())==8 and int(passing_table[0].split()[-1])==s['compare_counts']['passing'] and int(passing_table[0].split()[3])==len(c['point_lists']['cuts']),'native compare-point/cut table differs')
 failing_table=re.findall(r'^Failing \(not equivalent\)[ \t]+([0-9 \t]+)$',text,re.M)
 need(len(failing_table)==1 and len(failing_table[0].split())==8 and all(int(v)==0 for v in failing_table[0].split()),'native final failing table nonzero/missing')
 result=dict(schema='final374-native-fm-acceptance-review-v1',status='ACCEPTED_FULL_TOP_LOGIC_AT_REVIEWED_OPAQUE_SRAM_BOUNDARIES_NOT_QUALIFIED',hardware_profile=PROFILE,top=TOP,
  source_package_sha256=b['package_files_sha256'],dc_binding=b['native'],fm_execution=record(run/'execution.json'),coverage=record(run/'coverage.json'),decisions=record(a.decisions),summary=s,
  scope='RTL-to-mapped logic equivalence at reviewed opaque RAMSP boundaries; excludes SRAM internal circuits/timing, STA, PPA/power and official sample qualification',historical_S2_proof_inherited=False)
 dump(a.out,result);print(result['status'])
if __name__=='__main__':
 try:main()
 except (ValueError,KeyError,OSError) as e:print('FAIL: '+str(e),file=sys.stderr);sys.exit(1)
