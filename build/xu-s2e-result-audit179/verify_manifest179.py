#!/usr/bin/env python3
"""Rehash every committed179 payload, without executing remote software."""
import hashlib
import json
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((HERE / 'manifest179.json').read_text())
    assert manifest['schema'] == 'xu-s2e-result-audit179-bundle-v1'
    paths = set()
    for row in manifest['files']:
        rel = PurePosixPath(row['path'])
        assert not rel.is_absolute() and '..' not in rel.parts and str(rel) == row['path'] and row['path'] not in paths
        paths.add(row['path']); p = HERE / row['path']
        assert p.is_file() and not p.is_symlink()
        assert p.stat().st_size == row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest() == row['sha256']
    print(json.dumps(dict(status='VERIFIED179_BUNDLE_NOT_QUALIFIED', files=len(paths)), sort_keys=True))


if __name__ == '__main__': main()
