#!/usr/bin/env python3
"""Verify exact local104 artifact bytes without trusting tar member paths."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parent


def verify():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    archive=ROOT/'payload.tar.xz'
    data=archive.read_bytes()
    assert len(data)==manifest['archive']['bytes']
    assert hashlib.sha256(data).hexdigest()==manifest['archive']['sha256']
    names=set();total=0
    with tarfile.open(str(archive),'r:xz') as stream:
        for member in stream:
            path=PurePosixPath(member.name)
            assert member.isfile() and not path.is_absolute() and '..' not in path.parts
            assert str(path)==member.name and member.name not in names
            names.add(member.name)
            record=manifest['files'][member.name]
            assert member.size==record['bytes']
            content=stream.extractfile(member).read()
            assert len(content)==member.size and hashlib.sha256(content).hexdigest()==record['sha256']
            total+=len(content)
    assert names==set(manifest['files'])
    assert len(names)==manifest['file_count'] and total==manifest['payload_bytes']
    return dict(status='EXACT_LOCAL_ARTIFACT_HASHES_PASS_NOT_QUALIFICATION',files=len(names),bytes=total)


if __name__=='__main__':
    print(json.dumps(verify(),sort_keys=True))
