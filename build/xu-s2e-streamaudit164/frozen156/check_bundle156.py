#!/usr/bin/env python3
"""Read-only check of full156 local bundle; standard library only."""
import json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common156 import identity, need, read


def check_bundle():
    manifest = read(HERE/'manifest156.json'); names = []
    need(manifest['schema'] == 'xu-s2e-streamaudit156-bundle-v1' and manifest['qualification'] == 'NOT_QUALIFIED', 'bundle schema differs')
    for row in manifest['files']:
        relative = Path(row['path']); need(not relative.is_absolute() and '..' not in relative.parts, 'unsafe bundle member')
        actual = identity(HERE/relative)
        need(actual['sha256'] == row['sha256'] and actual['bytes'] == row['bytes'], 'bundle bytes differ: '+str(relative))
        names.append(str(relative))
    actual = {str(p.relative_to(HERE)) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    need(len(set(names)) == len(names) and actual == set(names)|{'manifest156.json'}, 'complete local bundle set differs')
    return dict(status='BUNDLE156_HOST_PAYLOADS_VERIFIED_NOT_NATIVE_QUALIFIED', files=len(names), manifest=identity(HERE/'manifest156.json'))


if __name__ == '__main__':
    try: print(json.dumps(check_bundle(), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('FAIL156: '+str(error), file=sys.stderr); sys.exit(1)
