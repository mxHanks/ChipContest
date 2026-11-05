#!/usr/bin/env python3
"""Read-only verification of the complete frozen146 payload; no native tools."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common146 import identity, need, read


def check():
    manifest = read(HERE/'bundle-manifest146.json')
    need(manifest['schema'] == 'xu-candidate-power146-bundle-v1' and
         manifest['status'] == 'READY_FOR_SERVER_NATIVE_PREFLIGHT_NOT_QUALIFIED' and
         manifest['qualification'] == 'NOT_QUALIFIED', 'bundle schema/status differs')
    names = []
    for row in manifest['files']:
        relative = Path(row['path'])
        need(not relative.is_absolute() and '..' not in relative.parts, 'unsafe bundle member')
        actual = identity(HERE/relative)
        need(actual['bytes'] == row['bytes'] and actual['sha256'] == row['sha256'], 'bundle payload differs: '+str(relative))
        names.append(str(relative))
    actual = {str(p.relative_to(HERE)) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    need(len(names) == len(set(names)) and actual == set(names)|{'bundle-manifest146.json'}, 'bundle complete payload set differs')
    return dict(status='BUNDLE146_PAYLOADS_VERIFIED_NOT_NATIVE_QUALIFIED', files=len(names), manifest=identity(HERE/'bundle-manifest146.json'))


if __name__ == '__main__':
    try: print(json.dumps(check(), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('FAIL146: '+str(exc), file=sys.stderr); sys.exit(1)
