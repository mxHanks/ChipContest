from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
records=json.loads((root/'manifest.json').read_text())['files']
seen=set()
for r in records:
 p=root/r['path']
 assert r['path'] not in seen and not Path(r['path']).is_absolute() and '..' not in Path(r['path']).parts
 seen.add(r['path'])
 assert p.is_file() and not p.is_symlink() and p.stat().st_size==r['bytes']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],r['path']
actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts}
assert actual==seen
print('XU_JOINT_MICRO_ARCHIVE_EXACT_SHA256_PASS files=%d; NOT_ACTIVITY_OR_ENERGY_QUALIFIED'%len(seen))
