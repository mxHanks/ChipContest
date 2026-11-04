#!/usr/bin/env python3
"""Same native timing, frozen111 TB, additional read-only VPI trace; no signoff claim."""
import argparse,hashlib,json,os,re,signal,subprocess,time,traceback
from pathlib import Path
SOURCE111='3f0ec494e0fa06efcd5617242c358b1e6242a9eea69b3acffdfcacbbe99ed414'
HEADER='/eda/synopsys/vcs/vcs_2020.03-SP2-6/include'
EXPECTED_C='c12e150fe15304aab10929f876343764a451a6979243f587256a992e0d9e0ac6'
def need(ok,message):
 if not ok:raise ValueError(message)
def identity(path):
 p=Path(os.path.abspath(str(path)));q=p.resolve(strict=True);before=q.stat();h=hashlib.sha256()
 with q.open('rb')as f:
  while True:
   b=f.read(1048576)
   if not b:break
   h.update(b)
 after=q.stat();key=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
 need(key(before)==key(after),'input changed while hashing: '+str(p))
 return dict(input_path=str(p),path=str(q),bytes=before.st_size,sha256=h.hexdigest(),device=before.st_dev,inode=before.st_ino,mtime_ns=before.st_mtime_ns,ctime_ns=before.st_ctime_ns)
def save(path,value):
 t=Path(path).with_name(Path(path).name+'.tmp');t.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n');os.replace(str(t),str(path))
def help_spans(raw):
 text=raw.decode('utf-8',errors='replace');lines=text.splitlines();selected=set()
 for i,line in enumerate(lines):
  if re.search(r'timing|notifier|specify|sdf|delay|\-load|\+vpi',line,re.I):selected.update(range(max(0,i-2),min(len(lines),i+3)))
 return dict(total_lines=len(lines),matched_lines=[dict(line=i+1,text=lines[i])for i in sorted(selected)],scope='Native help text only; no timing/notifier/delay option is selected or applied')
class Run:
 def __init__(self,out):
  self.out=Path(out).resolve();self.out.mkdir(parents=True,exist_ok=False);self.rows={};self.state=dict(status='RUNNING_CAUSAL_NATIVE117_NOT_QUALIFIED',qualification='NOT_QUALIFIED',pid=os.getpid(),started_epoch=time.time(),inputs_before=[],steps=[]);self.save()
 def save(self):save(self.out/'state.json',self.state)
 def freeze(self,path,expected=None):
  row=identity(path);name=row['input_path']
  if expected is not None:need(row==expected,'original111 input identity changed: '+name)
  if name in self.rows:need(self.rows[name]==row,'already frozen input changed: '+name)
  else:self.rows[name]=row;self.state['inputs_before']=list(self.rows.values());self.save()
  return row
 def run(self,name,args,timeout,zero=True):
  row=dict(name=name,command=list(args),started_epoch=time.time(),timeout_seconds=timeout,status='STARTING');self.state['steps'].append(row);self.save();p=None;log=self.out/(name+'.log')
  try:
   with log.open('xb')as f:
    try:
     p=subprocess.Popen(args,cwd=str(self.out),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);row.update(status='RUNNING',pid=p.pid,process_group=p.pid);self.save();row['returncode']=p.wait(timeout=timeout);row['status']='EXITED'
    except BaseException as exc:
     row['status']='EXCEPTION';row['error']=type(exc).__name__+': '+str(exc)
     if p is not None:
      for sig in [signal.SIGTERM,signal.SIGKILL]:
       try:os.killpg(p.pid,sig)
       except ProcessLookupError:pass
       try:p.wait(timeout=5)
       except subprocess.TimeoutExpired:continue
      p.wait(timeout=5)
     raise
  finally:
   row['finished_epoch']=time.time()
   if log.exists():row['log']=identity(log)
   self.save()
  if zero:need(row['returncode']==0,'native command failed: '+name)
  return row['returncode'],log.read_bytes()
 def close(self,error=None):
  after=[];issues=[]
  for key,before in self.rows.items():
   try:
    row=identity(key);after.append(row)
    if row!=before:issues.append(dict(path=key,error='INPUT_CHANGED'))
   except BaseException as exc:issues.append(dict(path=key,error=type(exc).__name__+': '+str(exc)))
  self.state.update(inputs_after=after,identity_errors=issues,inputs_equal_before_after=not issues,finished_epoch=time.time())
  if error is not None or issues:self.state.update(status='FAIL_NATIVE117_DIAGNOSTIC_NOT_QUALIFIED',error=error or'Frozen input identity changed')
  self.save();need(error is None and not issues,'native117 diagnostic failed; state/raw logs preserved')
def execute(root,source,out,help_only):
 run=Run(out);error=None
 try:
  state_row=run.freeze(root/'state.json');need(state_row['sha256']==SOURCE111,'original111 terminal state changed');original=json.loads((root/'state.json').read_text())
  need(original['status']=='FAIL_PUBLIC_DIAGNOSTIC_NOT_QUALIFIED'and original['inputs_equal_before_after']and original['inputs_before']==original['inputs_after']and len(original['inputs_before'])==628,'complete original111 failure identity proof missing')
  for row in original['inputs_before']:run.freeze(row['input_path'],row)
  for step in original['steps']:need(run.freeze(step['log']['input_path'])==step['log'],'actual111 raw child log changed')
  for tree in original['runtime_trees']:need(sorted(str(p.absolute())for p in Path(tree['root']).rglob('*')if p.is_file())==tree['files'],'original111 runtime tree members changed')
  native=original['steps'][1]['command'];simulator=Path(original['steps'][2]['command'][0]);vcs=Path(native[0]);run.freeze(vcs);run.freeze(simulator)
  run.freeze(__file__);c=run.freeze(source);need(c['sha256']==EXPECTED_C,'read-only117 source differs')
  text=Path(source).read_text();need('vpi_put_value'not in text and'vpiForceFlag'not in text and'vpi_control'not in text,'causal trace must not write/control simulator')
  rc,raw=run.run('actual111-runtime-help',[str(simulator),'-help'],60,zero=False);save(run.out/'runtime-help-timing-excerpts.json',dict(returncode=rc,**help_spans(raw)))
  rc,raw=run.run('native-vcs-help',[str(vcs),'-help'],60,zero=False);save(run.out/'vcs-help-timing-excerpts.json',dict(returncode=rc,**help_spans(raw)))
  # No native help option is inferred into a simulation command. The original
  # timing/model/defines remain exact; no SDF, no notifier suppression.
  if help_only:run.state['status']='NATIVE117_HELP_CAPTURED_ONLY_NOT_QUALIFIED'
  else:
   cc=original['steps'][0]['command'][0];run.freeze(cc);run.freeze(Path(HEADER)/'vpi_user.h');library=run.out/'causal117.so'
   run.run('causal-vpi-build',[cc,'-std=gnu99','-Wall','-Wextra','-Werror','-fPIC','-shared','-isystem',HEADER,str(Path(source).resolve()),'-o',str(library)],1800);run.freeze(library)
   command=list(native);newbinary=run.out/'task00'
   for i,arg in enumerate(command):
    if arg.startswith('-Mdir='):command[i]='-Mdir='+str(run.out/'csrc')
    if i>0 and command[i-1]=='-o':command[i]=str(newbinary)
   command+=['-load',str(library)+':xu_causal117_register']
   old_without=[v for i,v in enumerate(native)if not v.startswith('-Mdir=')and v!='-o'and not(i and native[i-1]=='-o')]
   new_without=[v for i,v in enumerate(command[:-2])if not v.startswith('-Mdir=')and v!='-o'and not(i and command[i-1]=='-o')]
   need(old_without==new_without,'compile inputs/options beyond output paths were changed')
   need(not any(re.search(r'notiming|no_tchk|no_notifier|nospecify|sdf',v,re.I)for v in command),'timing or SDF mode change forbidden')
   run.state['original_compilation_preserved_except_outputs_and_passive_vpi']=True;run.save();run.run('causal-vcs-build',command,1800);run.freeze(newbinary)
   args=list(original['steps'][2]['command']);args[0]=str(newbinary);code,raw=run.run('causal-simulation',args,21600,zero=False);log=raw.decode('utf-8',errors='replace')
   ready=re.findall(r'^XU_CAUSAL117_READY target_cells=1 fifo_modules=1 shared_modules=1 accel_modules=1 observed_nodes=(\d+) failed=0 start_fs=9359300000000 stop_fs=9359500000000 writes=0 forces=0 timing_controls_changed=0 NOT_FUNCTIONAL_OR_150MHZ_OR_ENERGY_QUALIFIED$',log,re.M)
   ends=re.findall(r'^XU_CAUSAL117_END events_in_slice=(\d+) observed_nodes=(\d+) failed=0 final_tick_fs=(\d+) writes=0 forces=0 NOT_FUNCTIONAL_OR_150MHZ_OR_ENERGY_QUALIFIED$',log,re.M)
   need(len(ready)==1 and len(ends)==1 and int(ready[0])>14 and int(ends[0][0])>0,'native passive trace target/bindings/events missing or rejected')
   events=[]
   for row in re.finditer(r'^XU_CAUSAL117_EVENT serial=(\d+) tick_fs=(\d+) reason=(\S+) role=(\S+) bits=(\d+) aval=([0-9a-f]+) bval=([0-9a-f]+) name=(\S+)$',log,re.M):events.append(dict(serial=int(row.group(1)),tick_fs=int(row.group(2)),reason=row.group(3),role=row.group(4),bits=int(row.group(5)),aval=row.group(6),bval=row.group(7),name=row.group(8)))
   need(events and [r['serial']for r in events]==list(range(1,len(events)+1)),'passive event sequence incomplete')
   fatal=list(re.finditer(r'^Fatal: "([^"\n]+)", (\d+): ([^\n]+): at time (\d+) fs\n([^\n]+)',log,re.M))
   report=dict(status='NATIVE117_PASSIVE_EVENTS_COLLECTED_NOT_FUNCTIONAL_OR_TIMING_OR_ENERGY_QUALIFIED',qualification='NOT_QUALIFIED',native_returncode=code,event_count=len(events),events=events,notifier_like_names=sorted({r['name']for r in events if re.search('notifier|notify',r['name'],re.I)}),native_fatals=[dict(source=f.group(1),line=int(f.group(2)),scope=f.group(3),tick_fs=int(f.group(4)),message=f.group(5))for f in fatal],native_timing_violations=log.count('Timing violation in'),scope='Read-only native node observations. Timing checks unchanged. A notifier->Q->handshake causal conclusion requires reading event order/connectivity, not this completion marker.')
   need('SOC_PASS'not in log,'unexpected full-pass claim requires separate audit; do not promote')
   save(run.out/'passive-event-review.json',report);run.state.update(status=report['status'],report=identity(run.out/'passive-event-review.json'),native_simulation_returncode=code)
 except BaseException as exc:error=type(exc).__name__+': '+str(exc);run.state['traceback']=traceback.format_exc();raise
 finally:run.close(error)
 print(run.state['status'],flush=True)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);p.add_argument('--source',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--help-only',action='store_true');a=p.parse_args();execute(a.root,a.source,a.out,a.help_only)
if __name__=='__main__':main()
