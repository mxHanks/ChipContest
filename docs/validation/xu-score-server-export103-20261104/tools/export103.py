from pathlib import Path
import hashlib,json,tarfile,io,os,time,sys,subprocess
B=Path.home()/'Desktop/xu-score-optimization-20261102';O=B/'xu-next-results-export-20261104-103.tar.xz';L=B/'xu-export103-driver.log'
if len(sys.argv)==1:
 assert not O.exists()and not L.exists()
 with L.open('xb')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('EXPORT103_STARTED',p.pid,flush=True);sys.exit(0)
assert not O.exists();snapshot={};observed=[];omitted=[]
def add(p):
 n=str(p.relative_to(B));d=p.read_bytes();assert n not in snapshot;snapshot[n]=d
def ident(p):
 h=hashlib.sha256();n=0
 with p.open('rb')as f:
  for d in iter(lambda:f.read(1024*1024),b''):h.update(d);n+=len(d)
 return dict(path=str(p.relative_to(B)),bytes=n,sha256=h.hexdigest())
def obs(pre):
 root=B/pre;sp=root/'state.json';j=json.loads(sp.read_text())if sp.exists()else{};pid=j.get('pid',j.get('campaign_pid'));proc=Path('/proc/'+str(pid));status=j.get('status','ABSENT_OR_NO_STATE');live=proc.exists();cmd=(proc/'cmdline').read_bytes().decode(errors='replace').replace('\0',' ')if live else'';observed.append(dict(prefix=pre,status=status,pid=pid,pid_alive_now=live,process_command=cmd));return root,j,status
specs=['s2c-native-pin-stream-20261104-93','s2c-native-pin-launch-20261104-93','pmu-reset-unconstrained-paths-20261104-94','full-soc-unloaded-cell-cleanup-20261104-95','vpi-vendor-preload-primitive-20261104-100','mapped-warning-audit-20261104-101','mapped-warning-audit-deploy-20261104-101','s2e-ppa-campaign-20261104-89','s2e-ppa-deploy-20261104-89']
for pre in specs:
 root,j,status=obs(pre)
 if not root.exists():continue
 live=status.startswith(('RUNNING','PREPARING','LAUNCHED','CAMPAIGN_LAUNCHED'))
 for directory,dirs,files in os.walk(str(root),followlinks=False):
  dirs[:]=[x for x in dirs if x not in ['csrc','obj_dir','DVEfiles','.git','__pycache__']and not x.endswith(('.daidir','.vdb'))]
  for name in sorted(files):
   p=Path(directory)/name
   if p.is_symlink()or not p.is_file():continue
   if name.startswith(('man-','help-')):omitted.append(dict(ident(p),reason='installed_manual_body_identity_only'));continue
   if name in ['mapped.v','mapped.ddc','repair.svf','default.svf']or p.suffix in ['.o','.so','.vvp','.elf','.db','.v']:continue
   if p.suffix not in ['.json','.jsonl','.log','.rpt','.tsv','.csv','.tcl','.txt','.py','.c','.h','.sv','.f','.xz']:continue
   if p.stat().st_size>64000000:omitted.append(dict(ident(p),reason='large_body_identity_only'));continue
   if live and name not in ['state.json','summary.json','driver.log','campaign.log']:continue
   add(p)
# The stream output state intentionally has no PID; tie the launcher worker to /proc.
l=B/'s2c-native-pin-launch-20261104-93/state.json'
if l.exists():
 j=json.loads(l.read_text());pid=j.get('pid');p=Path('/proc/'+str(pid));observed.append(dict(prefix='actual93_worker_from_launcher',pid=pid,pid_alive_now=p.exists(),process_command=(p/'cmdline').read_bytes().decode(errors='replace').replace('\0',' ')if p.exists()else''))
snapshot['live103-observation.json']=(json.dumps(dict(epoch=time.time(),observed=observed,scope='Terminal/raw or explicitly live snapshot; no new qualification inferred'),sort_keys=True,indent=2)+'\n').encode();snapshot['omitted103-bodies.json']=(json.dumps(omitted,sort_keys=True,indent=2)+'\n').encode();m=[dict(path=n,bytes=len(d),sha256=hashlib.sha256(d).hexdigest())for n,d in sorted(snapshot.items())]
with tarfile.open(str(O),'x:xz')as t:
 for n,d in sorted(snapshot.items()):
  x=tarfile.TarInfo(n);x.size=len(d);t.addfile(x,io.BytesIO(d))
 d=(json.dumps(m,sort_keys=True,indent=2)+'\n').encode();x=tarfile.TarInfo('manifest.json');x.size=len(d);t.addfile(x,io.BytesIO(d))
r=dict(status='SNAPSHOT_COMPLETE',payload_count=len(m),payload_bytes=sum(x['bytes']for x in m),bytes=O.stat().st_size,sha256=hashlib.sha256(O.read_bytes()).hexdigest());(B/'xu-export103-state.json').write_text(json.dumps(r,sort_keys=True,indent=2)+'\n');print('NEXT_EXPORT103_READY',json.dumps(r,sort_keys=True),flush=True)
