#!/usr/bin/env python3
"""Self-contained, local-only freeze/adopt queue; native stages fail closed.

Python3 standard library. No network, remapping, historic writes, automatic
restarts, license checkout probe, or promotion to contest qualification.
"""
import argparse,fcntl,hashlib,json,os,re,shutil,subprocess,sys,time,uuid
from pathlib import Path
SCHEMA='xu-batch-scheduler138-plan-v1'
BAD=re.compile(r'^\s*(?:Error:|Error-|Fatal:|XU_FATAL:)',re.I)
TERMINAL_EXTERNAL={'EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING','NATIVE_TIMING_COMPLETE_REVIEW_PENDING_NOT_QUALIFIED','PASS_REVIEW_PENDING_NOT_QUALIFIED'}
EDA_NAMES={'pt_shell','dc_shell','fm_shell','vcs','simv','lc_shell'}
def need(ok,msg):
 if not ok:raise ValueError(msg)
def read(path):
 def unique(pairs):
  d={}
  for k,v in pairs:need(k not in d,'duplicate JSON key '+k);d[k]=v
  return d
 return json.loads(Path(path).read_text(),object_pairs_hook=unique)
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(path,value):
 p=Path(path);tmp=p.with_name(p.name+'.tmp.'+uuid.uuid4().hex)
 tmp.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n');os.replace(str(tmp),str(p))
def ident(path):
 p=Path(path);need(p.is_absolute() and p.is_file(),'absolute readable file required: '+str(p))
 return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p),'symlink_target':os.readlink(str(p)) if p.is_symlink() else None}
def checked(records):
 actual=[];errors=[]
 for r in records:
  try:
   a=ident(r['path']);need(a['sha256']==r['sha256'],'SHA_MISMATCH')
   need('bytes' not in r or a['bytes']==r['bytes'],'BYTE_COUNT_MISMATCH');actual.append(a)
  except (OSError,ValueError) as e:errors.append({'path':r.get('path'),'error':str(e)})
 return actual,errors
def git_identity(source):
 root=source['server_root']
 def git(*a):return subprocess.check_output(['git','-C',root,*a],stderr=subprocess.STDOUT,timeout=30).decode().strip()
 head=git('rev-parse','HEAD');child=subprocess.check_output(['git','-C',str(Path(root)/'third-party/e203_hbirdv2'),'rev-parse','HEAD'],stderr=subprocess.STDOUT,timeout=30).decode().strip()
 need(head==source['main_commit'],'source main HEAD differs');need(child==source['child_commit'],'source child HEAD differs')
 dirty=git('status','--porcelain','--untracked-files=no');need(not dirty,'tracked source/index dirty: '+dirty[:1000])
 cd=subprocess.check_output(['git','-C',str(Path(root)/'third-party/e203_hbirdv2'),'status','--porcelain','--untracked-files=no'],stderr=subprocess.STDOUT,timeout=30).decode().strip();need(not cd,'tracked child/index dirty')
 return {'root':root,'main_commit':head,'main_tree':git('rev-parse','HEAD^{tree}'),'child_commit':child,'tracked_clean':True,'original_ppa_main_commit':source.get('original_ppa_main_commit'),'binding':'ACTUAL_CHECKOUT_HEAD_AND_ALL_DECLARED_INPUT_BODIES; original PPA main null remains null'}
def tool_git_identity(tool):
 root=tool['assets_root']
 def git(*a):return subprocess.check_output(['git','-C',root,*a],stderr=subprocess.STDOUT,timeout=30).decode().strip()
 head=git('rev-parse','HEAD');expected=tool.get('main_commit')
 if expected:need(head==expected,'PPA tool HEAD differs from archive producer')
 need(not git('status','--porcelain','--untracked-files=no'),'tracked PPA tool checkout dirty')
 return {'root':root,'main_commit':head,'main_tree':git('rev-parse','HEAD^{tree}'),'declared_producer_main_commit':expected,'tracked_clean':True,'binding':'Declared actual producer files rehashed; unknown historical tool commit remains explicit'}
def proc_snapshot():
 result=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   raw=(p/'cmdline').read_bytes();argv=[x.decode(errors='replace') for x in raw.split(b'\0') if x]
   if argv:result.append({'pid':int(p.name),'argv':argv})
  except (OSError,PermissionError):pass
 return result
def resource_snapshot(out,processes=None):
 mem={}
 for line in Path('/proc/meminfo').read_text().splitlines():
  k,v=line.split(':',1);mem[k]=int(v.strip().split()[0])*1024
 ps=proc_snapshot() if processes is None else processes
 return {'epoch':time.time(),'cpu_count':os.cpu_count(),'mem_available_bytes':mem['MemAvailable'],'disk_available_bytes':shutil.disk_usage(str(out)).free,'native_processes':[p for p in ps if any(Path(a).name in EDA_NAMES for a in p['argv'][:2])]}
def external_snapshot(plan,processes=None):
 ps=proc_snapshot() if processes is None else processes;rows=[]
 for x in plan.get('external_adoptions',[]):
  r={'id':x['id'],'action':x['action'],'processes':[p for p in ps if any(x['command_contains'] in a for a in p['argv'])]}
  p=Path(x['state_path'])
  if p.is_file():
   try:
    d=read(p);r.update(state_file=ident(p),reported_status=d.get('status'),taskset_complete=d.get('taskset_complete'),current_task_id=d.get('current_task_id'),tasks_recorded=len(d.get('tasks',[])))
   except (OSError,ValueError) as e:r['read_error']=str(e)
  else:r['reported_status']='NOT_PRESENT_NO_RESTART'
  r['live_process_present']=bool(r['processes']);rows.append(r)
 return rows
def parse_license(text,features):
 rows={}
 for m in re.finditer(r'Users of ([^:\s]+):\s*\(Total of (\d+) licenses? issued;\s*Total of (\d+) licenses? in use\)',text):
  name,total,used=m.groups();need(name not in rows,'duplicate license feature '+name);rows[name]={'total':int(total),'used':int(used),'free':int(total)-int(used)}
 if not features or any(f not in rows for f in features):return {'status':'UNKNOWN','reason':'NO_VERIFIED_TOTAL_AND_USED_FOR_ALL_REQUIRED_FEATURES','features':rows}
 if any(rows[f]['free']<1 for f in features):return {'status':'NO_FREE_LICENSE','features':rows}
 return {'status':'KNOWN_FREE','features':rows}
def license_snapshot(guards,features):
 command=guards.get('license_command')
 if not command:return {'status':'UNKNOWN','reason':'NO_READ_ONLY_LMSTAT_COMMAND_CONFIGURED'}
 need(isinstance(command,list) and command and all(isinstance(a,str) and a for a in command),'license command must be argv')
 need(Path(command[0]).name in ['lmutil','lmstat'] and (Path(command[0]).name=='lmstat' or 'lmstat' in command) and not any('get_license' in a for a in command),'only explicit read-only lmutil lmstat argv supported; list_licenses is checkout count, not free seats')
 try:
  r=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=guards.get('license_timeout_seconds',15))
  output=r.stdout.decode(errors='replace');v=parse_license(output,features) if r.returncode==0 else {'status':'UNKNOWN','reason':'LICENSE_QUERY_NONZERO'}
  v.update(command=command,returncode=r.returncode,stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stdout=output);return v
 except (OSError,subprocess.TimeoutExpired,ValueError) as e:return {'status':'UNKNOWN','reason':str(e),'command':command}
def native_guard(guards,res,ext,lic):
 if res['mem_available_bytes']<guards['min_mem_available_bytes']:return 'WAIT_MEMORY'
 if res['disk_available_bytes']<guards['min_disk_available_bytes']:return 'WAIT_DISK'
 if len(res['native_processes'])>=guards['max_native_jobs'] or any(x['live_process_present'] for x in ext):return 'WAIT_EXISTING_NATIVE_OR_ADOPTED_JOB'
 if lic['status']=='NO_FREE_LICENSE':return 'WAIT_LICENSE_FREE'
 if lic['status']!='KNOWN_FREE':
  if guards.get('unknown_license_policy','wait')!='exclusive_single':return 'WAIT_LICENSE_KNOWN'
  if guards['max_native_jobs']!=1:return 'WAIT_LICENSE_KNOWN'
  return 'ALLOW_UNKNOWN_LICENSE_EXCLUSIVE_SINGLE_DIAGNOSTIC_ONLY'
 return 'ALLOW_KNOWN_LICENSE'
def validate_plan(p):
 need(p.get('schema')==SCHEMA and p.get('qualification')=='NOT_QUALIFIED','plan schema/qualification')
 need(p.get('candidate_count')==len(p.get('candidates',[]))==8,'exact eight candidates required')
 ids=set()
 for c in p['candidates']:
  need(c['id'] not in ids,'duplicate candidate');ids.add(c['id']);phases=set()
  for r in c['freeze_inputs']:need(Path(r['path']).is_absolute() and re.fullmatch('[0-9a-f]{64}',r['sha256']),'invalid frozen record')
  for q in c['phases']:
   need(q['id'] not in phases and all(d in phases for d in q['depends']),'phase ordering/cycle');phases.add(q['id'])
   if q.get('argv') is not None:
    need(q['kind']=='command' and isinstance(q['argv'],list) and q['argv'] and all(type(a)==str and a for a in q['argv']),'exact argv required')
    need(q.get('input_records') and q.get('completion_marker'),'runnable command needs frozen phase inputs and unique completion marker')
 g=p['guards'];need(g['max_native_jobs']==1,'138 conservative global native cap is one')
 need(g.get('unknown_license_policy','wait') in ['wait','exclusive_single'],'invalid unknown-license policy')
 return p
def initialize(planpath,out):
 plan=validate_plan(read(planpath));out=Path(out).resolve();need(not out.exists(),'new output directory required');out.mkdir(parents=True)
 (out/'plan.json').write_bytes(Path(planpath).read_bytes())
 st={'schema':'xu-batch-scheduler138-state-v1','plan_sha256':sha(out/'plan.json'),'worker_sha256':sha(Path(__file__).resolve()),'qualification':'NOT_QUALIFIED','created_epoch':time.time(),'status':'QUEUED_INPUT_PREFLIGHT_PENDING','candidates':{c['id']:{q['id']:{'status':'QUEUED'} for q in c['phases']} for c in plan['candidates']}}
 write(out/'state.json',st);return st

def freeze_candidate(c,out):
 before,errors=checked(c['freeze_inputs']);source=None;tool=None
 try:source=git_identity(c['source'])
 except (OSError,ValueError,subprocess.SubprocessError) as e:errors.append({'source':c['source']['server_root'],'error':str(e)})
 try:tool=tool_git_identity(c['tool'])
 except (OSError,ValueError,subprocess.SubprocessError) as e:errors.append({'tool':c['tool']['assets_root'],'error':str(e)})
 # Compare every body again and recheck checkout after full read. This binds a
 # manifest at the current known source identity without inventing old commits.
 after,posterrors=checked(c['freeze_inputs']);errors.extend(posterrors)
 if source:
  try:need(git_identity(c['source'])==source,'checkout changed during freeze')
  except (OSError,ValueError,subprocess.SubprocessError) as e:errors.append({'source':c['source']['server_root'],'error':str(e)})
 if tool:
  try:need(tool_git_identity(c['tool'])==tool,'PPA tool checkout changed during freeze')
  except (OSError,ValueError,subprocess.SubprocessError) as e:errors.append({'tool':c['tool']['assets_root'],'error':str(e)})
 if before!=after:errors.append({'error':'INPUTS_CHANGED_DURING_FREEZE'})
 r={'status':'FROZEN_REVIEW_PENDING_NOT_QUALIFIED' if not errors else 'PENDING_INPUT_OR_SOURCE_VERIFY','qualification':'NOT_QUALIFIED','candidate':c['id'],'source':source,'tool':tool,'selected_mapped':c['selected_mapped'],'ordered_svf_inputs':c['ordered_svf_inputs'],'before':before,'after':after,'errors':errors,'completed_epoch':time.time()}
 write(out/('freeze-attempt-'+uuid.uuid4().hex+'.json'),r);write(out/'freeze.json',r);return r

def adopt_fm(c,out):
 frozen=read(out/'freeze.json');need(frozen['status']=='FROZEN_REVIEW_PENDING_NOT_QUALIFIED','own freeze must pass before adoption')
 actual,errors=checked(c['freeze_inputs']);need(not errors,'frozen inputs changed before FM adoption')
 need(actual==frozen['after'],'frozen identity or symlink changed')
 need(git_identity(c['source'])==frozen['source'],'source checkout changed before adoption')
 need(tool_git_identity(c['tool'])==frozen['tool'],'tool checkout changed before adoption')
 log=Path(c['formal_log']['path']).read_text(errors='replace');lines=log.splitlines();success=sum(line.strip()=='Verification SUCCEEDED' for line in lines)
 need(success==1,'own native FM success must appear exactly once')
 passing=c.get('formal_expected_passing');counts=[int(m.group(1)) for m in re.finditer(r'^\s*(\d+) Passing compare points\s*$',log,re.M)]
 if passing is not None:need(counts and all(n==passing for n in counts),'own FM native passing count differs')
 r={'status':'OWN_FM_ADOPTED_CONDITIONAL_REVIEW_PENDING','qualification':'NOT_QUALIFIED','selected_mapped':c['selected_mapped'],'original_mapped':c['original_mapped'],'same_original_area_mapping':c['selected_mapped']['sha256']==c['original_mapped']['sha256'],'ordered_svf_inputs':c['ordered_svf_inputs'],'log':ident(c['formal_log']['path']),'native_verification_succeeded_count':success,'native_passing_counts':counts,'sram_internal':'BLACK_BOX_NOT_PROVED','adopted_epoch':time.time()}
 actual2,errors=checked(c['freeze_inputs']);need(not errors and actual2==actual,'inputs changed during adoption')
 need(git_identity(c['source'])==frozen['source'] and tool_git_identity(c['tool'])==frozen['tool'],'checkout changed during adoption')
 write(out/'adopt-own-fm.json',r);return r

def run_command(planpath,cid,qid,out,token):
 plan=validate_plan(read(planpath));c=next(c for c in plan['candidates'] if c['id']==cid);q=next(q for q in c['phases'] if q['id']==qid)
 out=Path(out);native_lock=None;receipt={'status':'FAIL_REVIEW_REQUIRED','candidate':cid,'phase':qid,'token':token,'started_epoch':time.time(),'qualification':'NOT_QUALIFIED'}
 try:
  if q['native']:
   native_lock=(out.parent.parent/'native.lock').open('a');fcntl.flock(native_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  records=c['freeze_inputs']+q['input_records'];before,errors=checked(records);need(not errors,'phase input preflight failed: '+str(errors[:3]))
  guards=plan['guards'];res=resource_snapshot(out);ext=external_snapshot(plan);lic=license_snapshot(guards,q.get('license_features',guards['native_license_features']))
  # Runner is itself now visible; external patterns never name this runner.
  decision=native_guard(guards,res,ext,lic) if q['native'] else 'ALLOW_NON_NATIVE'
  receipt.update(resources_before=res,external_before=ext,license=lic,guard_decision=decision)
  need(decision.startswith('ALLOW'),'native pre-spawn guard: '+decision)
  with (out/'command.log').open('x') as f:
   r=subprocess.run(q['argv'],cwd=str(out),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=guards['native_timeout_seconds'],shell=False)
  after,errors=checked(records);need(not errors and before==after,'phase inputs changed')
  log=(out/'command.log').read_text(errors='replace');need(r.returncode==0,'command returned '+str(r.returncode))
  need(log.splitlines().count(q['completion_marker'])==1,'exact unique completion marker absent')
  need(not any(BAD.search(line) for line in log.splitlines()),'native error/fatal output')
  receipt.update(status='EXECUTED_DIAGNOSTIC_REVIEW_PENDING_NOT_QUALIFIED',returncode=r.returncode,before=before,after=after,log=ident(out/'command.log'))
 except Exception as e:receipt['error']=str(e)
 finally:
  receipt['finished_epoch']=time.time();write(out/'result.json',receipt)
  if native_lock:native_lock.close()
 return receipt

def tick(out,execute=False,retry=False):
 out=Path(out).resolve()
 with (out/'scheduler.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  st=read(out/'state.json');need(sha(out/'plan.json')==st['plan_sha256'],'plan changed; initialize a new independent queue')
  need(sha(Path(__file__).resolve())==st['worker_sha256'],'scheduler worker changed')
  plan=validate_plan(read(out/'plan.json'));ps=proc_snapshot();st['external_adoptions']=external_snapshot(plan,ps);st['resources']=resource_snapshot(out,ps)
  for c in plan['candidates']:
   cdir=out/c['id'];cdir.mkdir(exist_ok=True)
   for q in c['phases']:
    cur=st['candidates'][c['id']][q['id']]
    if cur['status']=='RUNNING':
     rpath=Path(cur['run_dir'])/'result.json'
     if rpath.is_file():
      r=read(rpath);need(r['token']==cur['token'],'result token differs');cur.update(status=r['status'],result=ident(rpath));continue
     live=any(p['pid']==cur['pid'] and cur['token'] in p['argv'] for p in ps)
     if not live:cur.update(status='ORPHAN_REVIEW_REQUIRED_NO_RESTART')
     continue
    if cur['status'] in ['FROZEN_REVIEW_PENDING_NOT_QUALIFIED','OWN_FM_ADOPTED_CONDITIONAL_REVIEW_PENDING','EXECUTED_DIAGNOSTIC_REVIEW_PENDING_NOT_QUALIFIED']:
     continue
    if cur['status'].startswith(('PENDING_INPUT','FAIL_','ORPHAN_')) and not retry:continue
    done={'FROZEN_REVIEW_PENDING_NOT_QUALIFIED','OWN_FM_ADOPTED_CONDITIONAL_REVIEW_PENDING','EXECUTED_DIAGNOSTIC_REVIEW_PENDING_NOT_QUALIFIED'}
    if any(st['candidates'][c['id']][d]['status'] not in done for d in q['depends']):cur['status']='WAIT_DEPENDENCY';continue
    if q['kind']=='freeze':
     if not execute:cur['status']='READY_FREEZE_NO_LICENSE_REQUIRED';continue
     r=freeze_candidate(c,cdir);cur.update(status=r['status'],receipt=ident(cdir/'freeze.json'),error_count=len(r['errors']));continue
    if q['kind']=='adopt_fm':
     if not execute:cur['status']='READY_ADOPT_OWN_FM';continue
     try:cur.update(adopt_fm(c,cdir))
     except Exception as e:cur.update(status='FAIL_OWN_FM_ADOPTION_REVIEW_REQUIRED',error=str(e))
     continue
    if q.get('argv') is None:cur.update(status='PENDING_IMPLEMENTATION',reason=q['blocked_reason']);continue
    if not execute:cur['status']='READY_COMMAND_EXPLICIT_EXECUTE_REQUIRED';continue
    if q['native'] and any(row['status']=='RUNNING' for phases in st['candidates'].values() for row in phases.values()):
     cur['status']='WAIT_EXISTING_NATIVE_OR_ADOPTED_JOB';continue
    res=resource_snapshot(out);ext=external_snapshot(plan);lic=license_snapshot(plan['guards'],q.get('license_features',plan['guards']['native_license_features']))
    decision=native_guard(plan['guards'],res,ext,lic) if q['native'] else 'ALLOW_NON_NATIVE'
    cur.update(guard_decision=decision,license=lic)
    if not decision.startswith('ALLOW'):cur['status']=decision;continue
    token=uuid.uuid4().hex;run=cdir/(q['id']+'-'+token);run.mkdir()
    argv=[sys.executable,str(Path(__file__).resolve()),'_phase','--plan',str(out/'plan.json'),'--candidate',c['id'],'--phase',q['id'],'--out',str(run),'--token',token]
    # Persist intent before spawning; a crash between intent/Popen requires review.
    cur.update(status='ORPHAN_REVIEW_REQUIRED_NO_RESTART',token=token,run_dir=str(run),argv=argv);write(out/'state.json',st)
    with (run/'runner.log').open('x') as f:p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    cur.update(status='RUNNING',pid=p.pid,started_epoch=time.time());write(out/'state.json',st)
    # Native cap1: a tick dispatches at most one command; subsequent phases wait.
    st['status']='RUNNING_OR_PENDING_NOT_QUALIFIED';st['updated_epoch']=time.time();write(out/'state.json',st);return st
  st['status']='INPUTS_AND_ADOPTIONS_COMPLETE_REMAINING_PHASES_PENDING_NOT_QUALIFIED' if all(st['candidates'][c['id']]['adopt_own_fm']['status']=='OWN_FM_ADOPTED_CONDITIONAL_REVIEW_PENDING' for c in plan['candidates']) else 'PREFLIGHT_OR_DEPENDENCY_PENDING_NOT_QUALIFIED'
  st['updated_epoch']=time.time();write(out/'state.json',st);return st

def main():
 a=argparse.ArgumentParser();sub=a.add_subparsers(dest='mode');v=sub.add_parser('validate');v.add_argument('--plan',required=True)
 i=sub.add_parser('init');i.add_argument('--plan',required=True);i.add_argument('--out',required=True)
 t=sub.add_parser('tick');t.add_argument('--out',required=True);t.add_argument('--execute',action='store_true');t.add_argument('--retry-pending',action='store_true')
 p=sub.add_parser('_phase');p.add_argument('--plan',required=True);p.add_argument('--candidate',required=True);p.add_argument('--phase',required=True);p.add_argument('--out',required=True);p.add_argument('--token',required=True)
 n=a.parse_args()
 if n.mode=='validate':d=validate_plan(read(n.plan));r={'status':'PLAN_VALID_MISSING_ADAPTERS_STAY_PENDING','candidates':len(d['candidates']),'frozen_input_counts':{c['id']:len(c['freeze_inputs']) for c in d['candidates']}}
 elif n.mode=='init':r=initialize(n.plan,n.out)
 elif n.mode=='tick':r=tick(n.out,n.execute,n.retry_pending)
 elif n.mode=='_phase':r=run_command(n.plan,n.candidate,n.phase,n.out,n.token)
 else:a.error('mode required')
 if n.mode in ['init','tick']:
  r={'status':r['status'],'qualification':r['qualification'],'state_path':str(Path(n.out).resolve()/'state.json'),'candidates':{cid:{qid:row['status'] for qid,row in phases.items()} for cid,phases in r['candidates'].items()}}
 print(json.dumps(r,sort_keys=True,indent=2))
if __name__=='__main__':main()
