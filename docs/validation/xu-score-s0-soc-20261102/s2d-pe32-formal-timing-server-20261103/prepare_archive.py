#!/usr/bin/env python3
"""xu: select immutable FM16/17 and timing19/21 bytes from export22."""
import argparse
import hashlib
import io
import json
import lzma
from pathlib import Path, PurePosixPath
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CAMPAIGNS = ['s2d-formality-campaign-20261103-16', 'pe32-formality-campaign-20261103-17',
             's2d-hold-gating-repair-20261103-19', 'pe32-hold-gating-repair-20261103-21']
EXPECTED_EXPORT_SHA = 'a6dd89390d2ba93c10f5d207e3111833d62bbab96772dee9787d6a7987401d7d'


def sha(data): return hashlib.sha256(data).hexdigest()


def store(data, relative):
    target = HERE / 'raw' / relative
    if len(data) >= 65536:
        target = target.with_name(target.name + '.xz')
        stored = lzma.compress(data)
    else:
        stored = data
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(stored)
    return dict(path=relative, bytes=len(data), sha256=sha(data),
                stored_path=str(target.relative_to(HERE)), stored_bytes=len(stored), stored_sha256=sha(stored))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--export', type=Path, required=True); args = ap.parse_args()
    if (HERE / 'selected-manifest.json').exists(): raise ValueError('refusing to overwrite an archive')
    data = args.export.read_bytes()
    if len(data) != 807588 or sha(data) != EXPECTED_EXPORT_SHA: raise ValueError('wrong export22 bytes')
    members = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:xz') as tar:
        for m in tar:
            path = PurePosixPath(m.name)
            if not m.isfile() or path.is_absolute() or '..' in path.parts or m.name in members:
                raise ValueError('unsafe/duplicate export member')
            members[m.name] = tar.extractfile(m).read()
    original_manifest = members.pop('manifest.json')
    manifest = json.loads(original_manifest)
    if len(manifest) != 142 or len(members) != 142: raise ValueError('unexpected payload count')
    seen = set()
    for entry in manifest:
        name = entry['path']
        if name in seen or name not in members: raise ValueError('bad source manifest')
        seen.add(name); content = members[name]
        if len(content) != entry['bytes'] or sha(content) != entry['sha256']: raise ValueError(name)
    if seen != set(members): raise ValueError('manifest incomplete')
    (HERE / 'source-export-manifest.json').write_bytes(original_manifest)
    selected = [store(content, name) for name, content in sorted(members.items()) if name.split('/')[0] in CAMPAIGNS]
    context = []
    base = ROOT / 'docs/validation/xu-score-s0-soc-20261102'
    for tag, folder in [
        ('s2d', base / 's2d-area-server-20261103/raw/export15/s2d-ppa-campaign-20261103-02/s2d'),
        ('pe32', base / 'pe32-area-server-20261103/raw/s3-pe32-ppa-campaign-20261103-01'),
    ]:
        for rel in ['ppa/prepared.json', 'ppa/execution.json', 'ppa/rtl.f', 'implementation/implementation.json']:
            src = folder / rel
            entry = store(src.read_bytes(), f'context/{tag}/{rel}')
            entry['source_local_path'] = str(src.relative_to(ROOT)); context.append(entry)
    src = base / 'hold-gating-repair-server-20261103/evidence-tools/xu-timing-scope-proposal-16.tcl'
    entry = store(src.read_bytes(), 'context/xu-timing-scope-proposal-16.tcl')
    entry['source_local_path'] = str(src.relative_to(ROOT)); context.append(entry)
    result = dict(schema='xu-selected-server-evidence-v1', source_export=dict(name=args.export.name, bytes=len(data), sha256=sha(data),
        manifest_sha256=sha(original_manifest), payload_count=142), selected_files=selected, context_files=context)
    (HERE / 'selected-manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(selected=len(selected), context=len(context), source_payloads_verified=len(members))))


if __name__ == '__main__': main()
