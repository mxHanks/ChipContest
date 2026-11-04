from pathlib import Path
import hashlib,json,tarfile,io,os,time
B=Path.home()/'Desktop/xu-score-optimization-20261102';O=B/'xu-mapped-probes-export-20261104-110.tar.xz';assert not O.exists();data={};obs=[]
def add(p,n=None):
 n=n or str(p.relative_to(B));assert n not in data;data[n]=p.read_bytes()
for pre in ['vpi-vendor-preload-primitive-20261104-105','mapped-udp-review-20261104-108']:
 root=B/pre;j=json.loads((root/'state.json').read_text());pid=j['pid'];proc=Path('/proc/'+str(pid));alive=proc.exists();cmd=(proc/'cmdline').read_bytes().decode(errors='replace').replace('\0',' ')if alive else''
 obs.append(dict(prefix=pre,status=j['status'],pid=pid,alive=alive,command=cmd));assert not j['status'].startswith(('RUNNING','LAUNCHED')),'original worker not terminal'
 assert not alive or str(root)not in cmd,'original worker still active'
 for directory,dirs,files in os.walk(str(root),followlinks=False):
  dirs[:]=[x for x in dirs if x not in ['csrc','obj_dir','DVEfiles','.git','__pycache__']and not x.endswith(('.daidir','.vdb'))]
  for name in sorted(files):
   q=Path(directory)/name
   if q.is_symlink()or not q.is_file()or q.suffix not in ['.json','.log','.sv','.c','.py','.txt']:continue
   assert q.stat().st_size<12000000;add(q)
for name in ['launch_vpi_primitive105.py','xu_vpi_preload105.c','tb_xu_vpi_preload105.sv','launch_udp_review108.py','xu_udp_review108.py']:
 add(Path.home()/'Desktop'/name,'tools/'+name)
data['live110-observation.json']=(json.dumps(dict(epoch=time.time(),observed=obs,vendor_fragments_exported=False),sort_keys=True,indent=2)+'\n').encode()
m=[dict(path=n,bytes=len(d),sha256=hashlib.sha256(d).hexdigest())for n,d in sorted(data.items())]
with tarfile.open(str(O),'x:xz')as t:
 for n,d in sorted(data.items()):
  x=tarfile.TarInfo(n);x.size=len(d);t.addfile(x,io.BytesIO(d))
 d=(json.dumps(m,sort_keys=True,indent=2)+'\n').encode();x=tarfile.TarInfo('manifest.json');x.size=len(d);t.addfile(x,io.BytesIO(d))
print('PROBES110_READY',O.stat().st_size,hashlib.sha256(O.read_bytes()).hexdigest(),len(m),sum(x['bytes']for x in m),flush=True)
