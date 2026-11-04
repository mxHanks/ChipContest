from pathlib import Path
import hashlib,json,tarfile,io,os,time
B=Path.home()/'Desktop/xu-score-optimization-20261102';O=B/'xu-next-results-export-20261104-98.tar.xz';assert not O.exists();snapshot={};observed=[]
def add(p):
 n=str(p.relative_to(B));d=p.read_bytes();snapshot[n]=d
for pre in ['standard-cell-model-private-20261104-90','s2c-native-pin-failure-20261104-92','mapped-elaboration-probe-20261104-97','mapped-elaboration-launch-20261104-97']:
 root=B/pre
 if not root.exists():observed.append(dict(prefix=pre,status='ABSENT'));continue
 sp=root/'state.json';j=json.loads(sp.read_text())if sp.exists()else{};status=j.get('status','NO_STATE');alive=Path('/proc/'+str(j.get('pid',-1))).exists();observed.append(dict(prefix=pre,status=status,pid=j.get('pid'),pid_alive_now=alive))
 live=status.startswith(('RUNNING','LAUNCHED'))
 for p in sorted(root.rglob('*')):
  if p.name.startswith(('man-','man.','help-','help.')):continue
  if not p.is_file()or p.name in ['mapped.v','mapped.ddc','repair.svf']or p.name.endswith('.v')or p.name.endswith('.jsonl.xz'):continue
  if any(k in p.parts for k in ['csrc','obj_dir','DVEfiles']):continue
  if p.suffix not in ['.json','.log','.tsv','.tcl','.txt','.rpt','.py','.c','.h','.sv','.f']or p.stat().st_size>64000000:continue
  if live and p.name not in ['state.json','summary.json','driver.log']:continue
  add(p)
p=B/'xu-export87-state.json'
if p.exists():add(p)
p=B/'xu-export87-driver.log'
if p.exists():add(p)
snapshot['live98-observation.json']=(json.dumps(dict(epoch=time.time(),observed=observed,scope='Read-only terminal-or-live evidence snapshot; live files are not claimed final'),sort_keys=True,indent=2)+'\n').encode();m=[dict(path=n,bytes=len(d),sha256=hashlib.sha256(d).hexdigest())for n,d in sorted(snapshot.items())]
with tarfile.open(str(O),'x:xz')as t:
 for n,d in sorted(snapshot.items()):
  x=tarfile.TarInfo(n);x.size=len(d);t.addfile(x,io.BytesIO(d))
 d=(json.dumps(m,sort_keys=True,indent=2)+'\n').encode();x=tarfile.TarInfo('manifest.json');x.size=len(d);t.addfile(x,io.BytesIO(d))
r=dict(status='SNAPSHOT_COMPLETE',payload_count=len(m),payload_bytes=sum(x['bytes']for x in m),bytes=O.stat().st_size,sha256=hashlib.sha256(O.read_bytes()).hexdigest());(B/'xu-export98-state.json').write_text(json.dumps(r,sort_keys=True,indent=2)+'\n');print('NEXT_EXPORT98_READY',json.dumps(r,sort_keys=True),flush=True)
