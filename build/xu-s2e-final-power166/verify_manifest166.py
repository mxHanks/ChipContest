#!/usr/bin/env python3
"""Verify166 delivery bytes. This does not run EDA or imply qualification."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((HERE / 'manifest166.json').read_text())
    if manifest['schema'] != 'xu-s2e-final-power166-delivery-v1' or manifest['qualification'] != 'NOT_QUALIFIED':
        raise ValueError('166 manifest schema/qualification differs')
    names = set()
    for record in manifest['files']:
        name = record['path']
        path = Path(name)
        if path.is_absolute() or len(path.parts) != 1 or name in names or name in ['.', '..']:
            raise ValueError('unsafe/duplicate delivery name')
        names.add(name)
        file = HERE / name
        if not file.is_file() or file.is_symlink():
            raise ValueError('166 missing/nonregular delivery: ' + name)
        digest = hashlib.sha256()
        size = 0
        with file.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                size += len(block)
                digest.update(block)
        if digest.hexdigest() != record['sha256'] or size != record['bytes']:
            raise ValueError('166 delivery changed: ' + name)
    required = {'power166.py', 'frozen130.py', 'test_power166.py', 'README.md',
                'verify_manifest166.py', 'host-check166.json', 'host-check166.log'}
    if names != required:
        raise ValueError('166 delivery file set differs')
    if next(r['sha256'] for r in manifest['files'] if r['path'] == 'frozen130.py') != \
            '95caa5fab255c5126e5b51f6f0b06c9bf63283f9bbf89dd310202abc87515d46':
        raise ValueError('original130 changed')
    print('VERIFIED166_DELIVERY_7_FILES_NOT_QUALIFIED')


if __name__ == '__main__':
    main()
