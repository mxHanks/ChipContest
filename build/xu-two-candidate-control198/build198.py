#!/usr/bin/env python3
"""Reproducible runtime tar and byte-checking no-clobber Desktop installer."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

HERE=Path(__file__).resolve().parent
BUILD=HERE.parent


def encoded(v):return (json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def record(name,raw):return dict(name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def main():
    jobs=[('xu-s2e-coverage186','s2e_coverage186'),('xu-s2c-common-power190','s2c_common_preflight190'),
          ('xu-s2c-common-power190','s2c_common_full12_190'),('xu-two-candidate-finalpack191','two_candidate_finalpack191')]
    frozen=[];files={}
    for folder,job in jobs:
        raw=(BUILD/folder/(job+'.json')).read_bytes()
        (HERE/(job+'.json')).write_bytes(raw)
        frozen.append(record(job+'.json',raw))
        files['xu-two-candidate-control198/'+job+'.json']=raw
    guard=encoded(dict(schema='xu-two-candidate-control198-v1',qualification='NOT_QUALIFIED',jobs=frozen))
    (HERE/'frozen-jobs198.json').write_bytes(guard)
    files['xu-two-candidate-control198/frozen-jobs198.json']=guard
    files['xu-two-candidate-control198/register198.py']=(HERE/'register198.py').read_bytes()
    for folder,number in [('xu-s2e-coverage186',186),('xu-s2c-common-power190',190)]:
        m=json.loads((BUILD/folder/('manifest%d.json'%number)).read_text())
        for row in m['runtime']:
            raw=(BUILD/folder/row['name']).read_bytes()
            assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
            remote_folder='xu-s2c-common-power198' if number==190 else folder
            files[remote_folder+'/'+row['name']]=raw
        remote_folder='xu-s2c-common-power198' if number==190 else folder
        files[remote_folder+'/manifest%d.json'%number]=(BUILD/folder/('manifest%d.json'%number)).read_bytes()
    files['xu-two-candidate-finalpack191/finalpack191.py']=(BUILD/'xu-two-candidate-finalpack191/finalpack191.py').read_bytes()
    manifest=dict(schema='xu-runtime198-transport-v1',qualification='NOT_QUALIFIED',
                  files=[record(n,files[n])for n in sorted(files)])
    (HERE/'manifest198.json').write_bytes(encoded(manifest))
    target=HERE/'runtime198.tar.gz'
    with target.open('wb')as f:
        with gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0)as gz:
            with tarfile.open(fileobj=gz,mode='w')as t:
                for name in sorted(files):
                    info=tarfile.TarInfo(name);info.size=len(files[name]);info.mode=0o600;info.mtime=0
                    t.addfile(info,io.BytesIO(files[name]))
                raw=encoded(manifest);info=tarfile.TarInfo('manifest198.json');info.size=len(raw);info.mode=0o600;info.mtime=0
                t.addfile(info,io.BytesIO(raw))
    sha=hashlib.sha256(target.read_bytes()).hexdigest()
    remote='xu-followup-runtime198-'+sha[:12]+'.tar.gz'
    source='''#!/usr/bin/env python3
import hashlib,json,tarfile
from pathlib import Path,PurePosixPath
D=Path.home()/'Desktop'
p=D/@REMOTE@
assert p.is_file() and not p.is_symlink() and p.stat().st_size==@BYTES@
assert hashlib.sha256(p.read_bytes()).hexdigest()==@SHA@
payload={}
with tarfile.open(str(p),'r:gz')as t:
 for m in t:
  n=PurePosixPath(m.name)
  assert m.isfile() and not m.issym() and not m.islnk() and not m.sparse
  assert not n.is_absolute() and '..' not in n.parts and str(n)==m.name and m.name not in payload and m.size<=4000000
  raw=t.extractfile(m).read();assert len(raw)==m.size;payload[m.name]=raw
manifest=json.loads(payload.pop('manifest198.json'))
assert manifest['schema']=='xu-runtime198-transport-v1' and len(payload)==len(manifest['files'])
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
receipt=D/'xu-score-optimization-20261102/followup198-install.json'
value=dict(schema='xu-runtime198-install-v1',status='INSTALLED_REVIEWED_RUNTIME_NOT_RUN_NOT_QUALIFIED',archive=dict(path=str(p),sha256=@SHA@,bytes=@BYTES@),manifest=manifest,new_native_runs=0)
if receipt.exists():assert json.loads(receipt.read_text())==value
else:
 with receipt.open('x')as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\\n')
print('XU198_INSTALLED',len(payload),@SHA@,flush=True)
'''.replace('@REMOTE@',repr(remote)).replace('@BYTES@',str(target.stat().st_size)).replace('@SHA@',repr(sha))
    (HERE/'install198.py').write_text(source)
    (HERE/'transport198.json').write_bytes(encoded(dict(schema='xu-transport198-identity-v1',
        archive=record(remote,target.read_bytes()),installer=record('install198.py',source.encode()),
        qualification='NOT_QUALIFIED',native_runs=0)))
    print(json.dumps(dict(files=len(files),bytes=target.stat().st_size,sha256=sha,remote=remote)))


if __name__=='__main__':main()
