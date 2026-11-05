#!/usr/bin/env python3
"""Verify145 payload bytes; no native tools or output directory creation."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent


def check():
    manifest=json.loads((HERE/'bundle-manifest145.json').read_text())
    assert manifest['schema']=='xu-profile-activity145-bundle-v1'
    assert manifest['status']=='READY_FOR_SERVER_NATIVE_PREFLIGHT_NOT_QUALIFIED'
    names=[]
    for record in manifest['files']:
        relative=Path(record['path'])
        assert not relative.is_absolute() and '..' not in relative.parts
        path=HERE/relative;assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size==record['bytes']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256'],str(relative)
        names.append(str(relative))
    assert len(names)==len(set(names)) and 'activity145.py' in names and 'macro145.py' in names
    actual={str(p.relative_to(HERE)) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    assert actual==set(names)|{'bundle-manifest145.json'},'unexpected/missing bundle files'
    return dict(status='BUNDLE145_PAYLOADS_VERIFIED_NOT_NATIVE_QUALIFIED',files=len(names),
                manifest_sha256=hashlib.sha256((HERE/'bundle-manifest145.json').read_bytes()).hexdigest())


if __name__=='__main__':
    try:print(json.dumps(check(),sort_keys=True))
    except (OSError,ValueError,AssertionError,KeyError) as exc:
        print('FAIL: '+str(exc),file=sys.stderr);sys.exit(1)
