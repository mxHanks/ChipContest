#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,importlib.util
D=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('batch138',str(D/'batch138.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
manifest=json.loads((D/'bundle-manifest138.json').read_text())
for r in manifest['files']:
 p=D/r['path'];assert p.is_file() and not p.is_symlink();assert p.stat().st_size==r['bytes'] and m.sha(p)==r['sha256'],r['path']
p=m.validate_plan(m.read(D/'queue-plan138.json'));inv=m.read(D/'inventory137.snapshot.json')
assert m.sha(D/'inventory137.snapshot.json')==p['inventory137_sha256']
assert [r['id'] for r in p['candidates']]==[r['id'] for r in inv['candidates']]
for c,i in zip(p['candidates'],inv['candidates']):
 assert c['selected_mapped']['sha256']==i['formal']['mapped']['sha256']
 assert c['ordered_svf_inputs']==i['formal']['ordered_svf_inputs']
 records={r['path']:r['sha256'] for r in c['freeze_inputs']}
 for r in [c['selected_mapped'],c['original_mapped']]+c['ordered_svf_inputs']:assert records[r['path']]==r['sha256']
 assert c['formal_expected_passing'] is not None
 assert all(q.get('argv') is None for q in c['phases'])
assert p['guards']['unknown_license_policy']=='exclusive_single' and not p['guards']['license_known_required_for_native']
print(json.dumps({'status':'PASS_SELF_CONTAINED_BUNDLE_NO_EDA','files':len(manifest['files']),'candidates':8,'qualification':'NOT_QUALIFIED'}))
