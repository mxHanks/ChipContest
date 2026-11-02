#!/usr/bin/env python3
"""Transfer exact non-library reproducibility artifacts; mapped netlists remain server-side."""
from pathlib import Path
import hashlib,io,json,tarfile
D=Path.home()/'Desktop';B=D/'xu-hw-optimization-20261102';P=B/'ppa';dest=B/'ppa-artifacts-01.tar.xz'
files={p for p in P.rglob('*') if p.is_file() and p.suffix in ['.py','.rpt','.tcl','.sdc','.json','.txt','.log'] and not any(x in p.parts for x in ['work','WORK','alib-52','alib-52-1'])}
files.add(P/'frozen-fw-rtl/xu-sram-adapter.sv')
files.update(p for p in D.glob('xu-hw-*.py') if p.is_file())
def name(p):return 'ppa/'+str(p.relative_to(P)) if P in p.parents else 'helpers/'+p.name
def sha(b):return hashlib.sha256(b).hexdigest()
manifest={name(p):dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()),server_path=str(p)) for p in sorted(files)}
with tarfile.open(str(dest),'x:xz',preset=9) as t:
 def add(n,b):
  v=tarfile.TarInfo(n);v.size=len(b);t.addfile(v,io.BytesIO(b))
 for p in sorted(files):add(name(p),p.read_bytes())
 netlists={str(p):dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(P.rglob('mapped.v'))}
 add('ppa-transfer-manifest.json',(json.dumps(dict(schema='xu-original-ppa-artifacts-v1',scope='exact non-library reports/helper/Tcl/SDC/adapter; no vendor libraries/models, mapped netlists remain on server',files=manifest,mapped_netlists=netlists),indent=2,sort_keys=True)+'\n').encode('ascii'))
print('PPA_ARTIFACTS {} bytes={} sha256={} files={}'.format(dest,dest.stat().st_size,sha(dest.read_bytes()),len(files)),flush=True)
