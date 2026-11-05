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
    jobs=[('xu-native-query207','native_query207'),('xu-query-autopack209','two_candidate_finalpack209')]
    frozen=[];files={}
    for folder,job in jobs:
        raw=(BUILD/folder/(job+'.json')).read_bytes()
        (HERE/(job+'.json')).write_bytes(raw)
        frozen.append(record(job+'.json',raw))
        files['xu-native-query-control208/'+job+'.json']=raw
    ancestor=BUILD/'xu-score-resume-20261103/followup199/two-candidate-followup-registration-20261105-198.json'
    raw_ancestor=ancestor.read_bytes()
    ancestry=dict(path='/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/two-candidate-followup-registration-20261105-198.json',
                  bytes=len(raw_ancestor),sha256=hashlib.sha256(raw_ancestor).hexdigest())
    guard=encoded(dict(schema='xu-two-candidate-control208-v1',qualification='NOT_QUALIFIED',jobs=frozen,ancestry198=ancestry))
    (HERE/'frozen-jobs208.json').write_bytes(guard)
    files['xu-native-query-control208/frozen-jobs208.json']=guard
    files['xu-native-query-control208/register208.py']=(HERE/'register208.py').read_bytes()
    folder='xu-native-query207'
    m=json.loads((BUILD/folder/'manifest207.json').read_text())
    for row in m['runtime']:
        n=Path(row['name'])
        assert not n.is_absolute() and '..' not in n.parts and str(n)==row['name']
        raw=(BUILD/folder/n).read_bytes()
        assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
        files[folder+'/'+row['name']]=raw
    files[folder+'/manifest207.json']=(BUILD/folder/'manifest207.json').read_bytes()
    files['xu-query-autopack209/autopack209.py']=(BUILD/'xu-query-autopack209/autopack209.py').read_bytes()
    manifest=dict(schema='xu-runtime208-transport-v1',qualification='NOT_QUALIFIED',
                  files=[record(n,files[n])for n in sorted(files)])
    (HERE/'manifest208.json').write_bytes(encoded(manifest))
    target=HERE/'runtime208.tar.gz'
    with target.open('wb')as f:
        with gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0)as gz:
            with tarfile.open(fileobj=gz,mode='w')as t:
                for name in sorted(files):
                    info=tarfile.TarInfo(name);info.size=len(files[name]);info.mode=0o600;info.mtime=0
                    t.addfile(info,io.BytesIO(files[name]))
                raw=encoded(manifest);info=tarfile.TarInfo('manifest208.json');info.size=len(raw);info.mode=0o600;info.mtime=0
                t.addfile(info,io.BytesIO(raw))
    sha=hashlib.sha256(target.read_bytes()).hexdigest()
    remote='xu-followup-runtime208-'+sha[:12]+'.tar.gz'
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
manifest=json.loads(payload.pop('manifest208.json'))
assert manifest['schema']=='xu-runtime208-transport-v1' and len(payload)==len(manifest['files'])
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
receipt=D/'xu-score-optimization-20261102/followup208-install.json'
value=dict(schema='xu-runtime208-install-v1',status='INSTALLED_REVIEWED_RUNTIME_NOT_RUN_NOT_QUALIFIED',archive=dict(path=str(p),sha256=@SHA@,bytes=@BYTES@),manifest=manifest,new_native_runs=0)
if receipt.exists():assert json.loads(receipt.read_text())==value
else:
 with receipt.open('x')as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\\n')
print('XU208_INSTALLED',len(payload),@SHA@,flush=True)
'''.replace('@REMOTE@',repr(remote)).replace('@BYTES@',str(target.stat().st_size)).replace('@SHA@',repr(sha))
    (HERE/'install208.py').write_text(source)
    (HERE/'transport208.json').write_bytes(encoded(dict(schema='xu-transport208-identity-v1',
        archive=record(remote,target.read_bytes()),installer=record('install208.py',source.encode()),
        qualification='NOT_QUALIFIED',native_runs=0)))
    print(json.dumps(dict(files=len(files),bytes=target.stat().st_size,sha256=sha,remote=remote)))


if __name__=='__main__':main()
