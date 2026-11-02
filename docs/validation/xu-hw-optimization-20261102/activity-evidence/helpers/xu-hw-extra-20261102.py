#!/usr/bin/env python3
import hashlib
from pathlib import Path
import subprocess
import sys
import tarfile

desktop=Path.home()/'Desktop'
archive=desktop/'xu-hw-extra-interface-20261102.tar.xz'
if hashlib.sha256(archive.read_bytes()).hexdigest()!='a14d84c035d33b6e9d07afbae2e9ce3917544994583d9785c1d2814291490522':
    raise ValueError('extra interface archive hash mismatch')
base=desktop/'xu-hw-optimization-20261102'
source=base/'extra-interface-source'
source.mkdir(exist_ok=False)
with tarfile.open(str(archive),'r:xz') as tar:
    for member in tar:
        relative=Path(member.name)
        if not member.isfile() or relative.is_absolute() or '..' in relative.parts:
            raise ValueError('unexpected archive entry '+member.name)
        target=source/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(tar.extractfile(member).read())
output=base/'extra-interface-vcs-01'
with (base/'extra-interface-vcs-01-driver.log').open('x') as stream:
    process=subprocess.Popen([sys.executable,str(source/'xu-hw-extra-interface/run.py'),
        '--repo',str(base/'ChipContest'),'--sim','vcs','--out',str(output)],
        cwd=str(source),stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
print('STARTED extra-interface pid={} output={}'.format(process.pid,output),flush=True)
