#!/usr/bin/env python3
"""Read-only audit of actual111 failure; never runs VCS or changes111 evidence."""
import argparse,hashlib,json,os,re,time,traceback
from pathlib import Path
EXPECTED={
 'state.json':'3f0ec494e0fa06efcd5617242c358b1e6242a9eea69b3acffdfcacbbe99ed414',
 'simulation.log':'c7d9933f20be539b11534ce9318f22dd9166747b0b096f169ff0c426514b3832',
 'tb_xu_mapped_task00111.sv':'30d7b1a454dd3ee5a33a05ea92656a16ab9c742d1fff6033e7559df5c9335a76',
 'vcs-build.log':'b774af6ef029e63c9c299e34660c6440e737d8a0e42d1097aa645afbb94fd64e',
 'vpi-build.log':'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
 'xu_mapped_task00_vpi111.c':'2403e25ee5ab453d017b6686da89df7553b79bcd89d70ca35be96281d5d8e7c7',
 'xu_mapped_expected111.h':'4e018f8d7e2a8030f2fc00c9c429afb1995f4b57780f8666861fbb411ad4c42a',
 'private-reference-adapter-plan.json':'6f3f337ddbd93cb103182d82ca4b821d9c99cdf3f7b594da1195c4ff98ccb486'}
FAILURE='XU_MAPPED111_PROTOCOL_REJECT unknown_shared_handshake'
TICK=9359423333333
STATUS='AUDITED_ACTUAL111_NATIVE_UNKNOWN_SHARED_HANDSHAKE_FAILURE_NOT_QUALIFIED'
def need(ok,message):
 if not ok:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def identity(path):
 p=Path(path);resolved=p.resolve(strict=True);before=resolved.stat();h=hashlib.sha256()
 with resolved.open('rb')as f:
  while True:
   body=f.read(1048576)
   if not body:break
   h.update(body)
 after=resolved.stat();fields=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
 need(fields(before)==fields(after),'input changed while hashing: '+str(p))
 return dict(input_path=str(p.absolute()),path=str(resolved),bytes=before.st_size,sha256=h.hexdigest(),device=before.st_dev,inode=before.st_ino,mtime_ns=before.st_mtime_ns,ctime_ns=before.st_ctime_ns)
def save(path,state):
 temporary=Path(path).with_name(Path(path).name+'.tmp');temporary.write_text(json.dumps(state,sort_keys=True,indent=2)+'\n');os.replace(str(temporary),str(path))
def parse_failure(log,tb,state):
 """Semantic parsing is independently exercised with real-log mutations."""
 need(state['status']=='FAIL_PUBLIC_DIAGNOSTIC_NOT_QUALIFIED'and state['qualification']=='NOT_QUALIFIED','original111 failure/scope was changed')
 need(state['inputs_equal_before_after']and state['inputs_before']==state['inputs_after']and not state['identity_errors'],'original111 input identity audit missing')
 need(len(state['inputs_before'])==628 and len({r['input_path']for r in state['inputs_before']})==628,'original111 full628 input records missing')
 need([r['name']for r in state['steps']]==['vpi-build','vcs-build','simulation'],'actual compiler/simulator steps missing')
 for step in state['steps']:need(step['status']=='EXITED'and step['returncode']==0,'actual native111 step outcome differs')
 tb_rows=[r for r in state['inputs_before']if Path(r['path']).name=='tb_xu_mapped_task00111.sv'];need(len(tb_rows)==1,'exact generated TB frozen identity missing');source=tb_rows[0]
 need(source['sha256']==sha(tb.encode())and source['sha256']==EXPECTED['tb_xu_mapped_task00111.sv'],'fatal source bytes differ from original freeze')
 expression='if((^{cmd_valid,cmd_ready,rsp_valid,rsp_ready})===1\'bx)$fatal(1,"'+FAILURE+'");'
 source_lines=tb.splitlines();locations=[i for i,line in enumerate(source_lines,1)if expression in line]
 need(locations==[216],'exact frozen unknown-handshake $fatal site differs')
 fatals=list(re.finditer(r'^Fatal: "([^"\n]+)", (\d+): ([^\n]+): at time (\d+) fs\n([^\n]+)\n\$finish called from file "([^"\n]+)", line (\d+)\.\n\$finish at simulation time\s+(\d+)\n',log,re.M))
 need(len(fatals)==1 and len(re.findall(r'^(?:Fatal|FATAL):',log,re.M))==1,'unique native complete fatal/finish block missing')
 f=fatals[0];path,line,scope,tick,message,finish_path,finish_line,finish_tick=f.groups()
 need(path==source['path']and finish_path==path,'native fatal/finish are not the frozen generated TB')
 need(int(line)==216 and int(finish_line)==216 and scope=='tb_xu_soc_ppa.public_scoreboard'and message==FAILURE,'native fatal site/scope/message differs')
 need(int(tick)==TICK and int(finish_tick)==TICK,'native fatal and finish times differ')
 need(len(re.findall(r'^Time: '+str(TICK)+r' fs$',log,re.M))==1,'native simulation footer time missing')
 need(state['steps'][-1]['log']['sha256']==sha(log.encode()),'actual original step raw simulation hash differs')
 need(state['error']['type']=='ValueError'and state['error']['message']=='required private gate unexpectedly returned zero','original parser error evidence differs')
 for forbidden in ['XU_MAPPED111_SOURCE_REQUEST','XU_MAPPED111_FINAL_Y_RETIRE','XU_MAPPED111_PUBLIC_DIAGNOSTIC_COMPLETE','XU_MAPPED111_REQUIRED_GATE_PENDING','SOC_PASS']:
  need(forbidden not in log,'actual111 unexpectedly claims later public/private completion: '+forbidden)
 need(log.count(FAILURE)==1 and len(re.findall(r'XU_MAPPED111_[A-Z_]*(?:REJECT|TIMEOUT)\b',log))==1,'actual111 has an extra observer rejection')
 need(re.search(r'^(?:Error|ERROR|FATAL|Fatal)(?:-|:|\[)',log[:f.start()],re.M)is None,'earlier native error/fatal present')
 geometry=list(re.finditer(r'^XU_MAPPED111_GEOMETRY tag=(\d+) role=([012]) status=PASS rows=256 row_bits=64 unique=256 memory_type=(29|116) reg_words=(\d+) memoryword_words=(\d+) parent_present=(\d+) scope_present=(\d+) index_present=(\d+) name=(\S+)$',log,re.M))
 need(len(geometry)==336 and sorted(int(r.group(1))for r in geometry)==list(range(336))and len({r.group(9)for r in geometry})==336,'complete native macro geometry not present')
 need(sum(r.group(2)=='1'for r in geometry)==32 and sum(r.group(2)=='2'for r in geometry)==256,'native geometry roles differ')
 for row in geometry:need(int(row.group(4))+int(row.group(5))==256,'native full-row type count differs')
 for marker in ['XU_MAPPED111_ADAPTER_READY macros=336 interface_bits_preserve_4state=1 preload_allowed=288 Q_WRITES=0 OTHER_DUT_FF_WRITES=0','XU_MAPPED111_PRELOAD_DONE itcm=32 shared=256 words_per_macro=256 bits_per_row=64 arbitrary_XZ_preserved=1 Q_WRITES=0','XU_MAPPED111_INITIAL_FIXED pads_original=1 HF150=1 LF32768=1 reset200ns=1 init_only_ITCM_SHARED=1 Q_init=0 OTHER_DUT_FF_init=0']:
  need(len(re.findall('^'+re.escape(marker)+'$',log,re.M))==1,'actual initial/preload marker absent or duplicated')
 timing=[]
 for match in re.finditer(r'^"([^"\n]+)", (\d+): Timing violation in ([^\n]+)\n[ \t]+(\$[^\n]+)\n',log,re.M):
  body=match.group(0).encode();timing.append(dict(offset_start=len(log[:match.start()].encode()),offset_end=len(log[:match.end()].encode()),raw_sha256=sha(body),source_file=match.group(1),source_line=int(match.group(2)),instance=match.group(3).strip(),native_check=match.group(4).strip()))
 need(len(timing)==25 and log.count('Timing violation in')==25 and all(r['native_check'].startswith('$hold(')for r in timing),'all actual native timing violations must remain explicit')
 recent=[r for r in timing if 'u_sirv_mem_fab.u_sirv_gnrl_icb_buffer.u_sirv_gnrl_rsp_fifo' in r['instance']]
 need(len(recent)==1 and 'qout_r_reg[0]'in recent[0]['instance']and '9359390050000'in recent[0]['native_check'],'recent actual response FIFO hold report missing')
 need(TICK<state['original_task00_window']['begin']['tick'],'failure is not before original source-request window')
 return dict(status=STATUS,qualification='NOT_QUALIFIED',public_task_complete=False,private_gate_pending_count=60,observed_simulation_returncode=0,observed_native_failure=dict(message=message,path=path,line=int(line),scope=scope,tick_fs=int(tick),finish_tick_fs=int(finish_tick),source_line=source_lines[215]),original_driver_parser_error=state['error'],before_original_source_request_fs=state['original_task00_window']['begin']['tick']-TICK,timing_violations=timing,native_timing_violation_count=25,causality='The response FIFO hold violation precedes the unknown-handshake rejection. No claim that it uniquely caused X without a dedicated trace/notifier analysis.',scope='Rehash and describe existing111 failure only; no VCS rerun, no pending gate removal, no timing-check disable')
def audit(root,out):
 root=Path(root).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
 result=dict(status='RUNNING_READONLY111_AUDIT_NOT_QUALIFIED',qualification='NOT_QUALIFIED',pid=os.getpid(),started_epoch=time.time(),root=str(root),source_inputs_before=[],current_frozen_inputs_before=[])
 save(out/'state.json',result)
 try:
  originals={}
  for name,expected in EXPECTED.items():
   row=identity(root/name);need(row['sha256']==expected,'actual111 original evidence body changed: '+name);originals[name]=(root/name).read_bytes();result['source_inputs_before'].append(row)
  original=json.loads(originals['state.json'].decode())
  for frozen in original['inputs_before']:
   row=identity(frozen['input_path']);need(row==frozen,'original111 frozen runtime/source identity changed: '+frozen['input_path']);result['current_frozen_inputs_before'].append(row)
  trees=[]
  for tree in original['runtime_trees']:
   now=sorted(str(p.absolute())for p in Path(tree['root']).rglob('*')if p.is_file());need(now==tree['files'],'original111 runtime tree members changed');trees.append(dict(root=tree['root'],files=now))
  result['runtime_trees_before']=trees;save(out/'state.json',result)
  report=parse_failure(originals['simulation.log'].decode('utf-8'),originals['tb_xu_mapped_task00111.sv'].decode('utf-8'),original)
  save(out/'failure-review.json',report);result['report']=identity(out/'failure-review.json');result.update(status=STATUS,public_task_complete=False,private_gate_pending_count=60)
 except BaseException as exc:
  result.update(status='FAIL_READONLY111_AUDIT_NOT_QUALIFIED',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc());raise
 finally:
  issues=[];after=[]
  for before in result['source_inputs_before']+result['current_frozen_inputs_before']:
   try:
    row=identity(before['input_path']);after.append(row)
    if row!=before:issues.append(dict(path=before['input_path'],error='INPUT_CHANGED_DURING_AUDIT'))
   except BaseException as exc:issues.append(dict(path=before['input_path'],error=type(exc).__name__+': '+str(exc)))
  result['current_and_source_inputs_after']=after
  for tree in result.get('runtime_trees_before',[]):
   current=sorted(str(p.absolute())for p in Path(tree['root']).rglob('*')if p.is_file())
   if current!=tree['files']:issues.append(dict(path=tree['root'],error='RUNTIME_TREE_MEMBERS_CHANGED'))
  result['identity_errors']=issues;result['inputs_equal_before_after']=not issues
  if issues:result['status']='FAIL_READONLY111_AUDIT_NOT_QUALIFIED'
  result['finished_epoch']=time.time();save(out/'state.json',result)
 need(result['status']==STATUS,'readonly111 audit did not finish cleanly')
 print(STATUS,flush=True)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();audit(a.root,a.out)
if __name__=='__main__':main()
