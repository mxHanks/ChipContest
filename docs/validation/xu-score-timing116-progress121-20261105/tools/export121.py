from pathlib import Path
import hashlib,json,tarfile,io,os,time
B=Path.home()/'Desktop/xu-score-optimization-20261102';O=B/'xu-server-progress-20261105-121.tar.xz';assert not O.exists();data={};obs=[];omitted=[]
def ident(p):
 h=hashlib.sha256();n=0
 with p.open('rb')as f:
  for d in iter(lambda:f.read(1048576),b''):h.update(d);n+=len(d)
 return dict(path=str(p.relative_to(B)),bytes=n,sha256=h.hexdigest())
for pre in ['full-soc-timing-combined-20261105-116','full-soc-timing-combined-launch-20261105-116','mapped-causal-native-20261105-117','mapped-causal-launch-20261105-117','s2e-formal-activity12-20261105-120']:
 root=B/pre
 if not root.exists():obs.append(dict(prefix=pre,exists=False));continue
 sp=root/'state.json'
 if not sp.exists():sp=root/'launch-state.json'
 if not sp.exists():sp=root/'result.json'
 state=json.loads(sp.read_text())if sp.exists()else{};pid=state.get('pid');proc=Path('/proc/'+str(pid));alive=proc.exists();command=(proc/'cmdline').read_bytes().decode(errors='replace').replace('\0',' ')if alive else'';obs.append(dict(prefix=pre,status=state.get('status'),pid=pid,pid_alive_now=alive,command=command))
 for directory,dirs,files in os.walk(str(root),followlinks=False):
  dirs[:]=[x for x in dirs if x not in ['csrc','obj_dir','DVEfiles','.git','__pycache__']and not x.endswith(('.daidir','.vdb'))]
  for name in sorted(files):
   p=Path(directory)/name
   if p.is_symlink()or not p.is_file()or p.suffix not in ['.json','.log','.sv','.svh','.c','.h','.txt','.rpt','.py','.jsonl']:continue
   if p.stat().st_size>8000000:omitted.append(dict(ident(p),reason='large_original_stays_server'));continue
   d=p.read_bytes();n=str(p.relative_to(B));assert n not in data;data[n]=d
for name in ['s2e-formal-activity12-20261105-120-driver.log']:
 p=B/name
 if p.exists():data[name]=p.read_bytes()
data['live121-observation.json']=(json.dumps(dict(epoch=time.time(),observed=obs,scope='Read-only snapshot; active process/log snapshots do not prove completion'),sort_keys=True,indent=2)+'\n').encode();data['omitted121-bodies.json']=(json.dumps(omitted,sort_keys=True,indent=2)+'\n').encode()
m=[dict(path=n,bytes=len(d),sha256=hashlib.sha256(d).hexdigest())for n,d in sorted(data.items())]
with tarfile.open(str(O),'x:xz')as t:
 for n,d in sorted(data.items()):
  x=tarfile.TarInfo(n);x.size=len(d);t.addfile(x,io.BytesIO(d))
 d=(json.dumps(m,sort_keys=True,indent=2)+'\n').encode();x=tarfile.TarInfo('manifest.json');x.size=len(d);t.addfile(x,io.BytesIO(d))
print('PROGRESS121_READY',O.stat().st_size,hashlib.sha256(O.read_bytes()).hexdigest(),len(m),sum(x['bytes']for x in m),flush=True)
