#!/usr/bin/env python3
"""Exact HW campaign JSON, small raw logs, and derived full-log identities/selected lines."""
import hashlib,io,json,sys,tarfile
from pathlib import Path
C=Path(sys.argv[1]).resolve();dest=Path(sys.argv[2]);B=C.parent
j=json.loads((C/'experiments.json').read_text());a=json.loads((C/'acceptance/acceptance.json').read_text())
if j['status']!='PASS' or j['acceptance']['status']!='PASS' or a['status']!='PASS':raise ValueError('complete acceptance required')
files=set(C.rglob('result.json'))|{C/'experiments.json',C/'acceptance/acceptance.json',C/'acceptance/xu-performance.json'}
# Original build receipts accompany every source compilation.
files.update(C.rglob('firmware-build.json'))
for p in [C/'acceptance/host.log',C/'acceptance/numeric.log',C/'acceptance/host-wrapper-vcs.log',B/'extra-interface-vcs-01-driver.log']:
 if p.is_file():files.add(p)
E=B/'extra-interface-vcs-01'
if E.exists():
 files.update(E.rglob('*.json'))
 files.update(p for p in E.rglob('*.log') if p.stat().st_size<150000)
def rel(p):
 try:return str(p.relative_to(C))
 except ValueError:return '../'+str(p.relative_to(B))
# No parent paths in tar: sibling extra evidence has a clear independent prefix.
def name(p):return rel(p).replace('../','extra-evidence/',1)
def sha(b):return hashlib.sha256(b).hexdigest()
manifest={name(p):dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()),server_path=str(p)) for p in sorted(files)}
with tarfile.open(str(dest),'x:xz',preset=9) as t:
 def add(n,b):
  i=tarfile.TarInfo(n);i.size=len(b);t.addfile(i,io.BytesIO(b))
 def addjson(n,v):add(n,(json.dumps(v,sort_keys=True,indent=2)+'\n').encode('ascii'))
 for p in sorted(files):add(name(p),p.read_bytes())
 addjson('xu-transfer-manifest.json',dict(schema='xu-exact-hw-result-file-bundle-v1',evidence_kind='original result JSON and specified full small logs; manifest derived',campaign=str(C),files=manifest))
 simulations={}
 for p in sorted(C.rglob('simulation.log')):
  b=p.read_bytes();simulations[str(p.relative_to(C))]=dict(bytes=len(b),sha256=sha(b),selected_exact_lines=[l for l in b.decode('utf-8',errors='replace').splitlines() if l.startswith(('TASK_PASS ','PERF_TASK ','SOC_PASS '))])
 addjson('xu-simulation-pass-lines-derived.json',dict(schema='xu-simulation-pass-lines-derived-v1',evidence_kind='selected exact lines only; full original logs remain on server',logs=simulations))
 selected={}
 for p in sorted(set(C.rglob('*.log'))|set(E.rglob('*.log'))|{B/'extra-interface-vcs-01-driver.log'}):
  if not p.is_file():continue
  b=p.read_bytes();selected[name(p)]=dict(bytes=len(b),sha256=sha(b),selected_exact_lines=[l for l in b.decode('utf-8',errors='replace').splitlines() if ('PASS' in l or 'Ran ' in l or l=='OK' or 'FAILED' in l or l.startswith(('TEST_PASS','TASK_PASS ','PERF_TASK ','SOC_PASS ')))])
 addjson('xu-selected-validation-log-lines.json',dict(schema='xu-selected-log-lines-derived-v1',evidence_kind='selected exact lines only; full-log bytes transferred only if in manifest',logs=selected))
print('HW_PACKAGE {} bytes={} sha256={} original_files={}'.format(dest,dest.stat().st_size,sha(dest.read_bytes()),len(files)),flush=True)
print('EXPERIMENTS '+json.dumps([(e['name'],e.get('comparison',{}),e.get('aggregate',{})) for e in j['experiments']]),flush=True)
print('SELECTED '+json.dumps(j['selected']),flush=True)
