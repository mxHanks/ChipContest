#!/usr/bin/env python3
"""xu verify exact local tool-validation payload and current producer bytes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
manifest = json.loads((HERE/'manifest.json').read_text())
for relative,record in manifest['files'].items():
    path = HERE/relative
    assert not path.is_symlink() and path.is_file(),relative
    data=path.read_bytes()
    assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256'],relative
for relative,digest in manifest['source_sha256'].items():
    path=ROOT/relative
    assert path.is_file() and not path.is_symlink(),relative
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,relative
assert manifest['status']=='HOST_VALIDATED_NOT_EDA' and manifest['host_tests']==63
assert manifest['cli_generated_macros']=={'RAMSP1024X16':320,'RAMSP128X16':128}
print('XU_BANK128_PPA_HOST_RECHECK_PASS payloads=%d sources=%d NOT_EDA'%(len(manifest['files']),len(manifest['source_sha256'])))
