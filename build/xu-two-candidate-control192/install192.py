#!/usr/bin/env python3
import hashlib,json,tarfile
from pathlib import Path,PurePosixPath
D=Path.home()/'Desktop'
p=D/'xu-followup-runtime192-a08459ff2b43.tar.gz'
assert p.is_file() and not p.is_symlink() and p.stat().st_size==110827
assert hashlib.sha256(p.read_bytes()).hexdigest()=='a08459ff2b43c94cb1dc8f06ede235b0e36e23ef304fe2d04e2da71503ce1ea2'
payload={}
with tarfile.open(str(p),'r:gz')as t:
 for m in t:
  n=PurePosixPath(m.name)
  assert m.isfile() and not m.issym() and not m.islnk() and not m.sparse
  assert not n.is_absolute() and '..' not in n.parts and str(n)==m.name and m.name not in payload and m.size<=4000000
  raw=t.extractfile(m).read();assert len(raw)==m.size;payload[m.name]=raw
manifest=json.loads(payload.pop('manifest192.json'))
assert manifest['schema']=='xu-runtime192-transport-v1' and len(payload)==len(manifest['files'])
assert set(payload)==set(r['name']for r in manifest['files'])
for r in manifest['files']:
 raw=payload[r['name']];assert len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256']
 dest=D/r['name']
 for parent in [dest]+list(dest.parents):
  if parent==D:break
  assert not parent.is_symlink()
 assert not dest.exists() or dest.is_file() and dest.read_bytes()==raw
# Only after every input and existing destination has passed do writes begin.
for n in sorted(payload):
 dest=D/n;dest.parent.mkdir(parents=True,exist_ok=True)
 if not dest.exists():
  with dest.open('xb')as f:f.write(payload[n])
 assert dest.read_bytes()==payload[n]
receipt=D/'xu-score-optimization-20261102/followup192-install.json'
value=dict(schema='xu-runtime192-install-v1',status='INSTALLED_REVIEWED_RUNTIME_NOT_RUN_NOT_QUALIFIED',archive=dict(path=str(p),sha256='a08459ff2b43c94cb1dc8f06ede235b0e36e23ef304fe2d04e2da71503ce1ea2',bytes=110827),manifest=manifest,new_native_runs=0)
if receipt.exists():assert json.loads(receipt.read_text())==value
else:
 with receipt.open('x')as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
print('XU192_INSTALLED',len(payload),'a08459ff2b43c94cb1dc8f06ede235b0e36e23ef304fe2d04e2da71503ce1ea2',flush=True)
