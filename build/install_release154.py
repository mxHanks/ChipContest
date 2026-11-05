#!/usr/bin/env python3
"""Install only the exact frozen154 archive, without starting experiments."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import uuid

ARCHIVE_SHA='8de2a0f7181cd7e52b1ac92ada842cbd8d8003e75fbd68c2ed93d967118c6003'
ARCHIVE_BYTES=201028
MANIFEST_SHA='29a3a238ca27182b814035203a2e5cae3f651066f599bf859596546c4f752590'


def need(value,message):
    if not value:raise ValueError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=Path.home()/'Desktop/xu-campaign-batch154.tar.xz')
    parser.add_argument('--destination',type=Path,default=Path.home()/'Desktop/xu-campaign-batch154')
    args=parser.parse_args();archive=args.archive.resolve();target=args.destination.absolute()
    need(archive.is_file() and not archive.is_symlink() and archive.stat().st_size==ARCHIVE_BYTES,'archive size/type differs')
    need(hashlib.sha256(archive.read_bytes()).hexdigest()==ARCHIVE_SHA,'archive SHA differs')
    with tarfile.open(str(archive),'r:xz') as tar:
        members=tar.getmembers();names=[m.name for m in members]
        need(len(names)==len(set(names)) and len(names)==87,'release member set size differs')
        need(all(m.isfile() and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts and m.size<16000000 for m in members),'unsafe member')
        data={m.name:tar.extractfile(m).read() for m in members}
    need(hashlib.sha256(data['release154.json']).hexdigest()==MANIFEST_SHA,'release manifest SHA differs')
    manifest=json.loads(data['release154.json'].decode('utf-8'))
    need(manifest['job_count']==20 and manifest['qualification']=='NOT_QUALIFIED','release schema differs')
    need(set(data)=={r['path'] for r in manifest['files']}|{'release154.json'},'manifest membership differs')
    for row in manifest['files']:
        raw=data[row['path']]
        need(len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],'payload differs: '+row['path'])
    need(target.parent.is_dir(),'destination parent missing')
    with (target.parent/(target.name+'.install154.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        need(not target.exists() and not target.is_symlink(),'existing deployment must not be overwritten')
        temporary=target.with_name('.'+target.name+'.installing-'+uuid.uuid4().hex)
        temporary.mkdir(mode=0o700)
        for name,raw in sorted(data.items()):
            path=temporary/name;path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
        need(not target.exists(),'destination appeared during install')
        os.rename(str(temporary),str(target))
    receipt=dict(status='INSTALLED_FROZEN_RELEASE154_NOT_STARTED_NOT_QUALIFIED',archive_sha256=ARCHIVE_SHA,
                 manifest_sha256=MANIFEST_SHA,files=86,jobs=20,target=str(target))
    receipt_path=target.parent/(target.name+'-install.json')
    with receipt_path.open('x') as stream:stream.write(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print(json.dumps(receipt,sort_keys=True),flush=True)


if __name__=='__main__':main()
