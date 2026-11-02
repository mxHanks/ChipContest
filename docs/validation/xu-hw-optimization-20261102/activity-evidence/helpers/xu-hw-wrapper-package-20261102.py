import hashlib,io,json,tarfile
from pathlib import Path
B=Path.home()/'Desktop/xu-hw-optimization-20261102';C=B/'xu-vcs-hw-campaign-01';dest=B/'hw-wrapper-originals-01.tar.xz';files={p for p in (C/'acceptance/host-wrapper-vcs').rglob('*') if p.is_file() and p.suffix in ['.log','.json'] and p.stat().st_size<150000}
manifest={str(p.relative_to(C)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),server_path=str(p)) for p in sorted(files)}
with tarfile.open(str(dest),'x:xz',preset=9) as t:
 def add(n,b):
  i=tarfile.TarInfo(n);i.size=len(b);t.addfile(i,io.BytesIO(b))
 for p in sorted(files):add(str(p.relative_to(C)),p.read_bytes())
 add('supplemental-originals-manifest.json',(json.dumps(dict(schema='xu-hw-supplemental-originals-v1',files=manifest),indent=2,sort_keys=True)+'\n').encode('ascii'))
print('WRAPPER_ORIGINALS bytes={} sha256={} files={}'.format(dest.stat().st_size,hashlib.sha256(dest.read_bytes()).hexdigest(),len(files)),flush=True)
