#!/usr/bin/env python3
"""Transfer complete small original supplemental logs/activity/PPA files with raw waveform identities."""
from pathlib import Path
import hashlib,io,json,tarfile
D=Path.home()/'Desktop';B=D/'xu-hw-optimization-20261102';C=B/'xu-vcs-hw-campaign-01';dest=B/'hw-final-artifacts-01.tar.xz'
state=json.loads((B/'activity-power-02/job-state.json').read_text())
if state.get('status')!='PASS':raise ValueError('final paired activity power is not complete PASS')
files=set()
for p in (C/'acceptance/host-wrapper-vcs').rglob('*'):
 if p.is_file() and p.suffix in ['.log','.json','.f','.v','.sv'] and p.stat().st_size<150000:files.add(p)
for folder in ['activity-01','activity-02','activity-power-01','activity-power-02']:
 base=B/folder
 for p in base.rglob('*'):
  if any(x in p.parts for x in ['old-RTL-clone','build','vectors','csrc','simv.daidir']):continue
  if p.is_file() and p.suffix in ['.json','.log','.tcl','.sdc','.rpt','.txt','.patch'] and p.stat().st_size<600000 and not p.name.startswith(('man-','pt-man-','help-','pt-help-')):files.add(p)
for p in (B/'extra-interface-source').rglob('*'):
 if p.is_file() and p.suffix in ['.py','.sv','.md','.v']:files.add(p)
files.update(p for p in D.glob('xu-hw-*.py') if p.is_file())
files.update(p for p in D.glob('xu-hw-*-selftest-*.json') if p.is_file())
def name(p):return str(p.relative_to(C)) if C in p.parents else str(p.relative_to(B)) if B in p.parents else 'helpers/'+p.name
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while True:
   b=f.read(1024*1024)
   if not b:break
   h.update(b)
 return h.hexdigest()
data={p:p.read_bytes() for p in sorted(files)}
manifest={name(p):dict(bytes=len(data[p]),sha256=hashlib.sha256(data[p]).hexdigest(),server_path=str(p)) for p in sorted(files)}
raw={str(p):dict(bytes=p.stat().st_size,sha256=sha(p)) for folder in ['activity-01','activity-02','activity-power-01','activity-power-02'] for p in (B/folder).rglob('*') if p.is_file() and (p.suffix=='.vcd' or p.name.endswith('.vcd.gz'))}
with tarfile.open(str(dest),'x:xz',preset=9) as t:
 def add(n,b):
  v=tarfile.TarInfo(n);v.size=len(b);t.addfile(v,io.BytesIO(b))
 for p in sorted(files):add(name(p),data[p])
 add('supplemental-originals-manifest.json',(json.dumps(dict(schema='xu-hw-final-original-artifacts-v1',evidence_kind='original small files; raw waveform bytes remain on server',files=manifest,waveforms=raw),indent=2,sort_keys=True)+'\n').encode('ascii'))
print('HW_FINAL_ARTIFACTS {} bytes={} sha256={} files={}'.format(dest,dest.stat().st_size,sha(dest),len(files)),flush=True)
