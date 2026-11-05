#!/usr/bin/env python3
"""Verify the frozen local188 bundle; never extract or mutate evidence."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def verify(root):
    root = root.resolve()
    manifest = json.loads((root / 'manifest188.json').read_text())
    if manifest['schema'] != 'xu-unknown188-bundle-v1':
        raise ValueError('wrong188 bundle schema')
    wanted = set()
    for row in manifest['files']:
        rel = PurePosixPath(row['path'])
        if rel.is_absolute() or '..' in rel.parts or row['path'] in wanted or rel.as_posix() != row['path']:
            raise ValueError('unsafe or duplicate188 path')
        wanted.add(row['path']); p = root / row['path']
        if any(q.is_symlink() for q in [p] + list(p.parents) if q != root.parent):
            raise ValueError('symlink188 member')
        if not p.is_file() or p.stat().st_size != row['bytes'] or digest(p) != row['sha256']:
            raise ValueError('188 bundle member mismatch: ' + row['path'])
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name != 'manifest188.json'}
    if actual != wanted:
        raise ValueError('188 member set mismatch')
    print('VERIFIED188_BUNDLE files=%d NOT_QUALIFIED' % len(wanted))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    verify(parser.parse_args().root)
