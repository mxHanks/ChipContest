#!/usr/bin/env python3
"""Check release161 and every unchanged payload of the frozen original145."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from build_manifest161 import PARENT_SHA,PROFILES
import check_bundle145

def check():
    result=check_bundle145.check()
    manifest=json.loads((HERE/'bundle-manifest145.json').read_text())
    assert manifest['release']=='xu-activity-repair161'
    assert manifest['profiles']==PROFILES and manifest['excluded_profiles']==['pe32','pe64']
    assert manifest['parent145_modified_payloads']==['activity145.py']
    parent_path=HERE/'parent145-manifest.json'
    assert hashlib.sha256(parent_path.read_bytes()).hexdigest()==PARENT_SHA
    parent=json.loads(parent_path.read_text())
    unchanged=0
    for record in parent['files']:
        if record['path']=='activity145.py':continue
        path=HERE/record['path']
        assert path.stat().st_size==record['bytes']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256'],record['path']
        unchanged+=1
    result.update(release=manifest['release'],unchanged_parent_payloads=unchanged,
                  status='BUNDLE161_VERIFIED_NOT_NATIVE_QUALIFIED')
    return result

if __name__=='__main__':
    try:print(json.dumps(check(),sort_keys=True))
    except (OSError,ValueError,AssertionError,KeyError) as exc:
        print('FAIL: '+str(exc),file=sys.stderr);sys.exit(1)
