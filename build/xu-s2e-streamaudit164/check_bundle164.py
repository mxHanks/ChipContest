#!/usr/bin/env python3
"""Read-only check of full164 local bundle; standard library only."""
import json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common164 import identity, need, read


def check_bundle():
    manifest = read(HERE/'manifest164.json'); names = []
    need(manifest['schema'] == 'xu-s2e-streamaudit164-bundle-v1' and manifest['qualification'] == 'NOT_QUALIFIED', 'bundle schema differs')
    for row in manifest['files']:
        relative = Path(row['path']); need(not relative.is_absolute() and '..' not in relative.parts, 'unsafe bundle member')
        actual = identity(HERE/relative)
        need(actual['sha256'] == row['sha256'] and actual['bytes'] == row['bytes'], 'bundle bytes differ: '+str(relative))
        names.append(str(relative))
    actual = {str(p.relative_to(HERE)) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    need(len(set(names)) == len(names) and actual == set(names)|{'manifest164.json'}, 'complete local bundle set differs')
    return dict(status='BUNDLE164_HOST_PAYLOADS_VERIFIED_NOT_NATIVE_QUALIFIED', files=len(names), manifest=identity(HERE/'manifest164.json'))


if __name__ == '__main__':
    try: print(json.dumps(check_bundle(), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('FAIL164: '+str(error), file=sys.stderr); sys.exit(1)
