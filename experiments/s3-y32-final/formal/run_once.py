#!/usr/bin/env python3
"""Review prepared FM bundle, or explicitly execute one later max2core native job."""
import argparse,json,os,re,signal,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
from common import *

def busy_jobs():
 jobs=[];names={'fm_shell','dc_shell','pt_shell','snps_shell','common_shell_ex','lc_shell','vcs','vcs1','simv','icc2_shell'}
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   if p.stat().st_uid!=os.getuid():continue
   comm=(p/'comm').read_text().strip();exe=Path(os.readlink(p/'exe')).name
   if comm in names or exe in names:jobs.append(dict(pid=int(p.name),comm=comm,exe=exe))
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
 return sorted(jobs,key=lambda r:r['pid'])
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--preparation',type=Path,required=True);p.add_argument('--out',type=Path);p.add_argument('--run',action='store_true');p.add_argument('--coordination-note');p.add_argument('--timeout-seconds',type=int,default=7200);a=p.parse_args()
 prep=a.preparation.resolve();b=json.loads((prep/'preparation.json').read_text());need(b['status']=='READY_FOR_NATIVE_FULL_TOP_FM_NOT_EXECUTED_NOT_ACCEPTED' and b['verification_tcl_emitted'],'API/DC/source gates are incomplete; only documentation probe is prepared')
 need(record(prep/'verify.tcl')==b['verification_tcl'],'generated native verification Tcl changed')
 c=api_check(prep/'api-contract.json',prep/'native-adapter.tcl',prep/'native-api-probe.log')
 need(record(prep/'api-contract.json')==b['api_contract']['identity'] and record(prep/'native-adapter.tcl')==b['api_contract']['adapter'] and record(prep/'native-api-probe.log')==b['api_contract']['probe'],'API contract/probe/adapter changed after preparation')
 package=Path(b['package']);need(sha(package/'package-files.json')==b['package_files_sha256'],'source package changed');need(native_check(package,Path(b['native']['directory']))==b['native'],'DC/map/final.svf identity changed')
 if not a.run:print('READY_INPUT_IDENTITIES_REVIEWED_NOT_EXECUTED');return 0
 need(a.out and not a.out.exists(),'new native output directory required');need(0<a.timeout_seconds<=14400,'bounded native lifetime required')
 jobs=busy_jobs()
 if jobs:need(a.coordination_note and len(a.coordination_note.strip())>=16,'existing same-account EDA jobs require concrete coordination note; they remain untouched')
 launcher=c['launcher'];need(Path(launcher['path']).is_file() and sha(launcher['path'])==launcher['sha256'],'actual FM launcher bytes differ')
 tc=json.loads((package/'toolchain.json').read_text());identities=[]
 for lib in tc['libraries']:need(Path(lib['path']).is_file() and sha(lib['path'])==lib['sha256'],'actual vendor library bytes differ');identities.append(dict(**lib,resolved_path=str(Path(lib['path']).resolve())))
 out=a.out.resolve();out.mkdir(parents=True);r=dict(schema='final374-native-fm-execution-v1',hardware_profile=PROFILE,top=TOP,defines=DEFINES,
  status='RUNNING',preparation_sha256=sha(prep/'preparation.json'),verify_tcl=record(prep/'verify.tcl'),adapter=record(prep/'native-adapter.tcl'),max_cores=2,
  tool=launcher,actual_launcher=dict(resolved_path=str(Path(launcher['path']).resolve()),is_symlink=Path(launcher['path']).is_symlink()),libraries=identities,
  observed_jobs=jobs,coordination_note=a.coordination_note,preexisting_jobs_policy='READ_ONLY_NEVER_STOP_OR_MODIFY',started_epoch=time.time(),timeout_seconds=a.timeout_seconds,
  command=[launcher['path'],'-f',str(prep/'verify.tcl')],tool_timed_out=False,source_drift=[],qualification='NOT_QUALIFIED')
 def save():dump(out/'execution.json',r)
 save()
 with (out/'fm.log').open('w') as log:
  process=subprocess.Popen(r['command'],cwd=out,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);r['pid']=process.pid;save()
  try:code=process.wait(timeout=a.timeout_seconds)
  except subprocess.TimeoutExpired:
   r['tool_timed_out']=True;os.killpg(process.pid,signal.SIGTERM)
   try:code=process.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);code=process.wait()
 try:
  need(sha(package/'package-files.json')==b['package_files_sha256'],'package manifest drift')
  need(native_check(package,Path(b['native']['directory']))==b['native'],'map/source/SVF drift')
  need(record(prep/'verify.tcl')==r['verify_tcl'] and record(prep/'native-adapter.tcl')==r['adapter'],'native script drift')
 except (ValueError,KeyError,OSError) as e:r['source_drift'].append(str(e))
 text=(out/'fm.log').read_text(errors='replace');r.update(returncode=code,finished_epoch=time.time(),native_tool_errors=re.findall(r'^(?:Error:|Fatal:|XU_FINAL374_FM_SCRIPT_ERROR).*$',text,re.M))
 required=['fm.log','coverage.json',*[f'reports/{n}.rpt' for n in REPORTS]]
 r['missing_required_outputs']=[n for n in required if not (out/n).is_file() or (out/n).stat().st_size==0]
 actual_marker=re.findall(r'^XU_FINAL374_FM_VERIFY_SUCCEEDED_NOT_ACCEPTED[ \t]*$',text,re.M)==['XU_FINAL374_FM_VERIFY_SUCCEEDED_NOT_ACCEPTED']
 r['status']='NATIVE_FM_COMPLETE_NOT_ACCEPTED' if code==0 and actual_marker and not r['tool_timed_out'] and not r['source_drift'] and not r['native_tool_errors'] and not r['missing_required_outputs'] else 'FAILED'
 r['outputs']={p.relative_to(out).as_posix():record(p) for p in sorted(out.rglob('*')) if p.is_file() and p!=out/'execution.json'};save();print(r['status']);return r['status']=='FAILED'
if __name__=='__main__':
 try:sys.exit(main())
 except (ValueError,KeyError,OSError) as e:print('FAIL: '+str(e),file=sys.stderr);sys.exit(1)
