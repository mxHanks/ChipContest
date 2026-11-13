#!/usr/bin/env python3
"""Prepare final374 FM inputs/probe; emit native verification ONLY after API/DC gates. Never runs EDA."""
import argparse,json,shutil,sys
from pathlib import Path
sys.dont_write_bytecode=True
from common import *

def emit(package,native,contract,adapter,out):
 p,n=Path(package).resolve(),Path(native).resolve();m,sm,_=package_check(p,cpu=True)
 defines=' '.join(DEFINES);includes=sorted({str((p/r['path']).parent) for r in sm['ordered_compile_sources']})
 need(not any(c.isspace() for c in str(p)),'known native -vcs syntax requires package path without whitespace')
 vcs=' '.join('+incdir+'+value for value in includes)+' -f '+str(p/'rtl.f');safe(vcs)
 libs=json.loads((p/'toolchain.json').read_text())['libraries']
 text='''# Generated after same-map/source/API preflight. Verification success is not acceptance.
if {[catch {
  file mkdir reports
  foreach final_fm_command {read_db read_sverilog read_verilog set_top set_svf match verify report_unmatched_points report_failing_points} {
    if {[llength [info commands $final_fm_command]] != 1} {error "Missing native FM API: $final_fm_command"}
  }
  source [file join [file dirname [info script]] native-adapter.tcl]
  final_fm_configure_resources 2 reports
  final_fm_configure_assumptions reports
'''
 text+='  set_svf '+safe(n/'final.svf')+'\n'
 for lib in libs:text+='  read_db -technology_library '+safe(lib['path'])+'\n'
 text+='  read_sverilog -r -define {'+defines+'} -vcs '+safe(vcs)+'\n'
 text+='  set_top r:/WORK/'+TOP+'\n  read_verilog -i '+safe(n/'mapped.v')+'\n  set_top i:/WORK/'+TOP+'\n'
 text+='''  final_fm_collect linked reports
  match
  report_unmatched_points > reports/unmatched.rpt
  final_fm_collect matched reports
  # Must enumerate actual opaque macro instances/ports in BOTH containers.
  # Never blackbox a whole DMA/core/CPU/fabric or tolerate unresolved modules.
  final_fm_assert_boundaries reports 374 RAMSP1024X16
  set final_fm_verified [verify]
  report_failing_points > reports/failing.rpt
  final_fm_collect verified reports
'''
 for name in REPORTS:
  text+='  if {![file isfile reports/'+name+'.rpt] || [file size reports/'+name+'.rpt] == 0} {error {Missing native '+name+' report}}\n'
 text+='  if {![file isfile coverage-native.tsv] || [file size coverage-native.tsv] == 0} {error {Missing complete native coverage collector}}\n'
 text+='''  if {$final_fm_verified} {
    puts {XU_FINAL374_FM_VERIFY_SUCCEEDED_NOT_ACCEPTED}
    exit 0
  } else {
    puts {XU_FINAL374_FM_VERIFY_FAILED}
    exit 1
  }
} final_fm_error]} {
  puts stderr "XU_FINAL374_FM_SCRIPT_ERROR $final_fm_error"
  exit 1
}
'''
 (out/'verify.tcl').write_text(text);shutil.copy2(adapter,out/'native-adapter.tcl')
 return record(out/'verify.tcl')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--native',type=Path);p.add_argument('--api-contract',type=Path);p.add_argument('--adapter',type=Path);p.add_argument('--probe-log',type=Path)
 a=p.parse_args();out=a.out.resolve();need(not out.exists(),'new output directory required');out.mkdir(parents=True)
 m,sm,cpu=package_check(a.package);package=a.package.resolve()
 bundle=dict(schema='final374-formal-preparation-v1',status='OFFLINE_SOURCE_REVIEWED_NOT_FORMALITY_EXECUTED',hardware_profile=PROFILE,top=TOP,defines=DEFINES,
  package=str(package),package_files_sha256=sha(package/'package-files.json'),source_manifest_sha256=sha(package/'source-manifest.json'),ordered_sources=sm['ordered_compile_sources'],
  own_svf_required='final.svf',expected_physical_macros=GEOMETRY,opaque_cell='RAMSP1024X16',opaque_ports=PORTS,
  native=None,api_contract=None,verification_tcl_emitted=False,eda_executed=False,
  required_native_reports=REPORTS,missing=['Same-package completed DC mapped.v/mapped.ddc/final.svf and DC receipt','Current native FM launcher identity and max2core/report API documentation','Reviewed native API adapter and signatures','Actual full-top FM match/verify plus coverage/assumption review'],
  inherited_old_proof=False,prohibited=['old353/S2 SVF or map','general unresolved blackboxing','whole DMA/core/fabric blackboxing','unreviewed dont_verify/unread/unmatched/constant/cut','hardcoded42338 passing points'])
 shutil.copy2(HERE/'api_probe.tcl',out/'api_probe.tcl');shutil.copy2(HERE/'adapter.template.tcl',out/'adapter.template.tcl')
 if a.native:bundle['native']=native_check(package,a.native);bundle['missing']=bundle['missing'][1:]
 apis=[bool(a.api_contract),bool(a.adapter),bool(a.probe_log)];need(not any(apis) or all(apis),'API contract/adapter/probe log must be supplied together')
 if all(apis):
  c=api_check(a.api_contract,a.adapter,a.probe_log);bundle['api_contract']=dict(path=str(a.api_contract.resolve()),identity=record(a.api_contract),adapter=record(a.adapter),probe=record(a.probe_log),launcher=c['launcher'])
  need(a.native,'native map required before emitting executable verification Tcl')
  bundle['verification_tcl']=emit(package,a.native,c,a.adapter,out);bundle['verification_tcl_emitted']=True
  for src,name in [(a.api_contract,'api-contract.json'),(a.probe_log,'native-api-probe.log')]:shutil.copy2(src,out/name)
  bundle['status']='READY_FOR_NATIVE_FULL_TOP_FM_NOT_EXECUTED_NOT_ACCEPTED';bundle['missing']=['Actual native full-top FM match/verify and every coverage/assumption review']
 bundle['historical_native_syntax_sources']={}
 for log,want in [('s2c-fm.log','c4214d589302ef3e7a147304b5de86dffc13c03d6e60ccb7c1cf241abfebf76c'),('s2e155-fm.log','d88c3a5e3e8842d501efb13d70a1eb33aa9547d35eb1cecca9434dce68a2b0e4')]:
  path=ROOT/'docs/handoff-evidence'/log
  if path.is_file():need(sha(path)==want,'old syntax provenance drift')
  bundle['historical_native_syntax_sources'][log]=dict(expected_sha256=want,locally_present=path.is_file(),actual_identity=record(path) if path.is_file() else None,used_as_current_equivalence_evidence=False)
 bundle['control_tools']={name:sha(HERE/name) for name in ['common.py','prepare.py','run_once.py','review_native.py','normalize.py']}
 bundle['tool_sha256']=sha(Path(__file__).resolve());dump(out/'preparation.json',bundle)
 print(json.dumps({k:bundle[k] for k in ['status','verification_tcl_emitted','eda_executed','missing']}))
if __name__=='__main__':
 try:main()
 except (ValueError,KeyError,OSError) as e:print('FAIL: '+str(e),file=sys.stderr);sys.exit(1)
