#!/usr/bin/env python3
"""Seal only this task's final candidate outputs. No EDA or credential access."""
import argparse,hashlib,json,os,tarfile,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True);a=p.parse_args()
r=Path(a.root).resolve();out=Path(a.out).resolve()
assert r.name=='candidate' and r.parent.name=='xu-dma-synth-20261109-r3'
assert not out.exists();out.mkdir(mode=0o700)
j=json.loads((r/'execution.json').read_text());assert j['status']!='RUNNING','job still running'
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
inputs=json.loads((r/'package-files.json').read_text());assert all(sha(r/n)==v for n,v in inputs.items()),'source drift'
files=[]
for f in sorted(r.rglob('*')):
 rel=f.relative_to(r)
 if not f.is_file() or f.is_symlink():continue
 if len(rel.parts)>1 and rel.parts[0] not in ['source','dc-clock-reports'] and rel.as_posix() not in inputs:continue
 files.append(f)
assert set(inputs).issubset({f.relative_to(r).as_posix() for f in files}),'incomplete input evidence'
record=dict(schema='xu-server-final-artifact-seal-v1',sealed_epoch=time.time(),execution_status=j['status'],execution_sha256=sha(r/'execution.json'),input_manifest_sha256=sha(r/'package-files.json'),files={f.relative_to(r).as_posix():dict(bytes=f.stat().st_size,sha256=sha(f)) for f in files})
(out/'final-files.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
reports=[f for f in files if f.relative_to(r).parts[0]!='source' and f.name not in ['mapped.v','mapped.ddc','default.svf']]
for name,items in [('reports.tar.gz',reports),('full.tar.gz',files)]:
 with tarfile.open(out/name,'w:gz') as t:
  t.add(out/'final-files.json',arcname='final-files.json',recursive=False)
  for f in items:t.add(f,arcname='candidate/'+f.relative_to(r).as_posix(),recursive=False)
 print(json.dumps(dict(name=name,bytes=(out/name).stat().st_size,sha256=sha(out/name)),sort_keys=True))
print('SEALED_NOT_QUALIFIED')
