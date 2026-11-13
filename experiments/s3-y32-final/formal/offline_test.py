#!/usr/bin/env python3
"""Synthetic rejection tests and real sealed-source review; no vendor tool/library access."""
import argparse,copy,importlib.util,json,re,shutil,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
from common import *
from review_native import REVIEWED,review_coverage
import prepare

def fixture(folder):
 (folder/'reports').mkdir()
 for role in REPORTS:(folder/'reports'/(role+'.rpt')).write_text('SYNTHETIC UNIT TEST ONLY - not native evidence '+role+'\n')
 assumptions=['synopsys_auto_setup','hdlin_unresolved_modules','verification_set_undriven_signals','verification_verify_directly_undriven_output','hdlin_ignore_parallel_case','hdlin_ignore_full_case','hdlin_error_on_mismatch_message']
 lists={k:[] for k in REVIEWED+['failing','aborted','unverified']}
 lists['assumptions']=[dict(id=k,actual_value='synthetic',evidence_reports=['assumptions']) for k in assumptions]
 macros=[]
 for group,count in GEOMETRY.items():
  for i in range(count):
   path=group+'/'+str(i);ports={}
   for name,(direction,width) in PORTS.items():
    ports[name]=dict(direction=direction,width=width,bits=[dict(reference_pin='r/'+path+'/'+name+str(b),implementation_pin='i/'+path+'/'+name+str(b),evidence_id=path+'/'+name+str(b),status='MATCHED_OPAQUE_OUTPUT' if direction=='output' else 'VERIFIED_COMPARE_POINT') for b in range(width)])
   macros.append(dict(canonical_path=path,group=group,cell_ref='RAMSP1024X16',disposition='PAIRED_OPAQUE',reference_path='r/'+path,implementation_path='i/'+path,ports=ports))
 c=dict(schema='final374-fm-native-coverage-v1',collector_complete=True,api_contract_sha256='synthetic-api',raw_reports={role:record(folder/'reports'/(role+'.rpt')) for role in REPORTS},
  report_provenance={role:dict(returncode=0,phase='verified',commands=['synthetic_documented_report']) for role in REPORTS},unresolved_modules=[],unexpected_black_boxes=[],
  compare_counts=dict(passing=123,failing=0,aborted=0,unverified=0,unread=0),point_lists=lists,physical_macro_boundaries=macros,resource_limit=dict(max_cores=2,native_report_role='resources'),guidance_counts=dict(accepted=2,rejected=0,unsupported=0,unprocessed=0,total=2))
 d=dict(schema='final374-fm-coverage-decisions-v1',coverage_sha256='',decisions=[dict(category='assumptions',id=k,decision='ACCEPTED_WITH_REASON',reason='Synthetic gate fixture checks exact exception matching only.',reviewer='offline-test',evidence_reports=['assumptions']) for k in assumptions])
 return c,d

def main():
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists(),'new test output required');a.out.parent.mkdir(parents=True,exist_ok=True)
 results=[]
 def result(name,ok,detail=''):need(ok,name+': '+detail);results.append(dict(case=name,status='PASS',detail=detail))
 with tempfile.TemporaryDirectory(prefix='final-formal-offline-') as td:
  folder=Path(td);c,d=fixture(folder)
  def check(cov,dec):
   dump(folder/'coverage.json',cov);dec['coverage_sha256']=sha(folder/'coverage.json');return review_coverage(cov,folder,dec,'synthetic-api',['synthetic_documented_report'])
  s=check(copy.deepcopy(c),copy.deepcopy(d));result('synthetic-complete-boundary-gate',s['paired_opaque_macros']==374 and s['accounted_boundary_bits']==25058,'Synthetic acceptance fixture only; no native equivalence claim')
  mutations={
   'reject-nonzero-failing':lambda x,y:x['compare_counts'].update(failing=1),
   'reject-nonzero-aborted':lambda x,y:x['compare_counts'].update(aborted=1),
   'reject-nonzero-unverified':lambda x,y:x['compare_counts'].update(unverified=1),
   'reject-zero-proof':lambda x,y:x['compare_counts'].update(passing=0),
   'reject-missing-report':lambda x,y:x['raw_reports'].pop('aborted'),
   'reject-missing-native-command-provenance':lambda x,y:x['report_provenance'].pop('black_boxes'),
   'reject-unsupported-report-api':lambda x,y:x['report_provenance']['aborted'].update(commands=['unknown_report']),
   'reject-unresolved-module':lambda x,y:x['unresolved_modules'].append('fake_dma'),
   'reject-extra-blackbox':lambda x,y:x['unexpected_black_boxes'].append('LinearTileDmaCore'),
   'reject-missing-physical-macro':lambda x,y:x['physical_macro_boundaries'].pop(),
   'reject-unreviewed-assumption':lambda x,y:y['decisions'].pop(),
   'reject-unreviewed-dont-verify':lambda x,y:x['point_lists']['dont_verify'].append(dict(id='unreviewed',evidence_reports=['dont_verify'])),
   'reject-opaque-input-bit-hole':lambda x,y:x['physical_macro_boundaries'][0]['ports']['D']['bits'].pop(),
   'reject-unverified-opaque-pin':lambda x,y:x['physical_macro_boundaries'][0]['ports']['D']['bits'][0].update(status='UNVERIFIED'),
   'reject-duplicate-opaque-pair':lambda x,y:x['physical_macro_boundaries'][1].update(reference_path=x['physical_macro_boundaries'][0]['reference_path']),
   'reject-unreviewed-opaque-constant':lambda x,y:x['physical_macro_boundaries'][0]['ports']['D']['bits'][0].update(status='VERIFIED_CONSTANT'),
   'reject-missing-guidance-rejection-list':lambda x,y:x['guidance_counts'].update(rejected=1,total=3),
   'reject-core-limit3':lambda x,y:x['resource_limit'].update(max_cores=3),
   'reject-unreviewed-optimized-macro':lambda x,y:x['physical_macro_boundaries'][0].update(disposition='PROVED_UNOBSERVABLE'),
  }
  for name,mutate in mutations.items():
   x,y=copy.deepcopy(c),copy.deepcopy(d);mutate(x,y)
   try:check(x,y)
   except ValueError as e:result(name,True,str(e))
   else:result(name,False,'incorrectly accepted')
  m,sm,_=package_check(a.package);result('real-final-sealed159-reference',len(sm['ordered_compile_sources'])==159 and m['defines']==DEFINES)
  for n in ['s2c-fm.log','s2e155-fm.log']:
   text=(ROOT/'docs/handoff-evidence'/n).read_text();result('reject-historical-marker-'+n,not re.findall(r'^XU_FINAL374_FM_VERIFY_SUCCEEDED_NOT_ACCEPTED$',text,re.M),'Historical proof cannot satisfy final native marker')
  # Direct emitter fixture tests Tcl syntax without satisfying actual readiness.
  emitdir=folder/'emitter';emitdir.mkdir()
  with patch.object(prepare,'package_check',return_value=(m,sm,None)):
   prepare.emit(a.package,folder/'fake-native',{},HERE/'adapter.template.tcl',emitdir)
  syntax='foreach p $argv {set h [open $p r];set s [read $h];close $h;if {![info complete $s]} {exit 1}}\n';(folder/'syntax.tcl').write_text(syntax)
  parsed=subprocess.run(['tclsh',str(folder/'syntax.tcl'),str(emitdir/'verify.tcl'),str(HERE/'api_probe.tcl'),str(HERE/'adapter.template.tcl')],capture_output=True,text=True);result('Tcl-parser-completeness',parsed.returncode==0,parsed.stderr)
  # A real initial source-only bundle must not emit/run native verification.
  reviewdir=folder/'source-review'
  done=subprocess.run([sys.executable,str(HERE/'prepare.py'),'--package',str(a.package.resolve()),'--out',str(reviewdir)],capture_output=True,text=True)
  result('source-only-preparation-cannot-verify',done.returncode==0 and not (reviewdir/'verify.tcl').exists(),done.stdout.strip())
  blocked=subprocess.run([sys.executable,str(HERE/'run_once.py'),'--preparation',str(reviewdir)],capture_output=True,text=True)
  result('unready-native-wrapper-rejected-before-tools',blocked.returncode!=0 and 'API/DC/source gates' in blocked.stderr,blocked.stderr.strip())
  # No vendor API is needed to demonstrate unsupported commands remain missing.
  probe=subprocess.run(['tclsh',str(HERE/'api_probe.tcl')],capture_output=True,text=True);sections=probe_sections(probe.stdout)
  result('unsupported-API-probe-not-empty-pass',probe.returncode==0 and any(not r['exists'] or r['returncode'] for r in sections.values()))
  (folder/'fake-probe.log').write_text(probe.stdout)
  try:api_check(HERE/'api-contract.template.json',HERE/'adapter.template.tcl',folder/'fake-probe.log')
  except ValueError as e:result('unapproved-API-template-rejected',True,str(e))
  else:result('unapproved-API-template-rejected',False)
 dump(a.out,dict(schema='final374-fm-offline-gate-tests-v1',status='PASS',tests=results,count=len(results),package_files_sha256=sha(a.package/'package-files.json'),native_eda_run=False,synthetic_native_fixtures=True,qualification='No native Formality result; fixture acceptance is solely a parser/gate test'))
 print('FINAL_FM_OFFLINE_GATE_TEST_PASS cases='+str(len(results)))
if __name__=='__main__':main()
