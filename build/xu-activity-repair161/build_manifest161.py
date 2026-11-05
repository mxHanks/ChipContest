#!/usr/bin/env python3
"""Build the explicit release161 manifest, retaining the power146 filename."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PARENT_SHA='001c66b2e19cc6ec279e3ae3f24c859b0931ec2b5b850040f9207e7e97941358'
PROFILES=['baseline_h1_h2','s1_h2_only','s1_sram_bias','s2b','s2d','compact32_128']

def record(path):
    return dict(path=str(path.relative_to(HERE)),bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())

def build():
    parent=record(HERE/'parent145-manifest.json')
    assert parent['sha256']==PARENT_SHA,'original release154 manifest changed'
    payload=[record(p) for p in sorted(HERE.rglob('*')) if p.is_file() and
             '__pycache__' not in p.parts and p.name!='bundle-manifest145.json']
    result=dict(schema='xu-profile-activity145-bundle-v1',release='xu-activity-repair161',
        status='READY_FOR_SERVER_NATIVE_PREFLIGHT_NOT_QUALIFIED',qualification='NOT_QUALIFIED',
        parent145_manifest=parent,parent145_modified_payloads=['activity145.py'],
        profiles=PROFILES,excluded_profiles=['pe32','pe64'],
        compatibility='Original145 receipt/verification interfaces for unchanged power146; release identity is161',
        changes=['Pass original TB TESTCASE prefix, binding its single .verilog suffix to compiled image SHA',
                 'Fail before original readmemh if program image cannot be opened; no DUT assignment',
                 'Reject native file/readmem warnings and recheck per-task command on verification',
                 'Restrict new runs/verifications to six requested profiles'],files=payload)
    (HERE/'bundle-manifest145.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result

if __name__=='__main__':
    result=build();print(json.dumps(dict(release=result['release'],files=len(result['files'])),sort_keys=True))
