#!/usr/bin/env python3
"""Fetch original public V2 archive; extract untouched validation WAVs only.

Never creates an official600 claim, changes labels, alters audio, trains a model,
or extracts arbitrary tar paths. Archive transport identity is checked against
Google Storage's declared byte count and MD5 before any sample is used.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import traceback

URL='https://storage.googleapis.com/download.tensorflow.org/data/speech_commands_v0.02.tar.gz'
EXPECTED_BYTES=2428923189
EXPECTED_MD5='6b74f3901214cb2c2934e98196829835'
EXPECTED_SHA256='af14739ee7dc311471de98f5f9d2c9191b18aedfe957f4a6ff791c709868ff58'
CHECKSUM_SOURCE='https://raw.githubusercontent.com/tensorflow/datasets/master/tensorflow_datasets/datasets/speech_commands/checksums.tsv'
ROOT=Path(__file__).resolve().parents[4]
def hashes(path):
    sha=hashlib.sha256();md5=hashlib.md5()
    with path.open('rb')as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):sha.update(block);md5.update(block)
    return dict(sha256=sha.hexdigest(),md5=md5.hexdigest(),bytes=path.stat().st_size)
def split(name):
    key=re.sub(r'_nohash_.*$','',Path(name).name)
    maximum=2**27-1;p=(int(hashlib.sha1(key.encode()).hexdigest(),16)%(maximum+1))*(100.0/maximum)
    return 'validation'if p<10 else 'testing'if p<20 else 'training'
def save(path,data):path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='speech-commands-v2-public-validation-acquisition-v1',status='RUNNING',started_at=datetime.now(timezone.utc).isoformat(),url=URL,official_evaluation='NOT_OFFICIAL_SAMPLE_SELECTION',selection='original KWT speaker-hash validation split; training/testing audio excluded',source_url_in_pinned_kwt='kws_streaming/train/base_parser.py:39',expected_archive=dict(bytes=EXPECTED_BYTES,md5=EXPECTED_MD5,sha256=EXPECTED_SHA256,checksum_source=CHECKSUM_SOURCE),commands=[])
    dest=out/'speech_commands_v0.02.tar.gz';data=out/'data';data.mkdir()
    try:
        cmd=['curl','--fail','--location','--retry','3','--connect-timeout','20','--max-time','1800','--dump-header',str(out/'download-headers.txt'),'--output',str(dest),URL]
        receipt['commands'].append(cmd);save(out/'receipt.json',receipt)
        with(out/'download.log').open('w')as log:done=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1900)
        if done.returncode:raise RuntimeError('official archive download failed, retained partial bytes/log')
        record=hashes(dest);receipt['archive']=record
        if record['bytes']!=EXPECTED_BYTES or record['md5']!=EXPECTED_MD5 or record['sha256']!=EXPECTED_SHA256:raise ValueError('archive differs from official storage identity')
        inventory=[]
        with tarfile.open(dest,'r|gz')as archive:
            for member in archive:
                name=PurePosixPath(member.name)
                if name.is_absolute() or '..'in name.parts or member.issym() or member.islnk() or not(member.isfile()or member.isdir()):raise ValueError('unsafe archive member')
                parts=[x for x in name.parts if x!='.']
                selected=(member.isfile()and len(parts)==2 and parts[1].endswith('.wav')and not parts[0].startswith('_')and split(parts[1])=='validation')
                metadata=member.isfile()and len(parts)==1 and parts[0]in['LICENSE','README.md','validation_list.txt','testing_list.txt']
                if not(selected or metadata):continue
                if member.size>1024*1024:raise ValueError('unexpectedly large selected audio/metadata')
                target=data.joinpath(*parts);target.parent.mkdir(parents=True,exist_ok=True)
                if target.exists():raise ValueError('duplicate archive path')
                source=archive.extractfile(member)
                with target.open('xb')as stream:
                    remaining=member.size
                    while remaining:
                        block=source.read(min(65536,remaining))
                        if not block:raise ValueError('truncated tar member')
                        stream.write(block);remaining-=len(block)
                entry=dict(path=str(target.relative_to(data)),**hashes(target),split='validation'if selected else'metadata');inventory.append(entry)
        save(out/'selected-files.json',inventory)
        count=sum(x['split']=='validation'for x in inventory)
        if count<600:raise ValueError('insufficient validation WAVs')
        receipt.update(status='PASS_PUBLIC_VALIDATION_DATA_ONLY',validation_wavs=count,selected_inventory_sha256=hashes(out/'selected-files.json')['sha256'])
        print('PUBLIC_V2_VALIDATION_ACQUIRED',count,flush=True)
    except Exception as exc:receipt.update(status='FAIL',error=str(exc),traceback=traceback.format_exc());raise
    finally:receipt['finished_at']=datetime.now(timezone.utc).isoformat();save(out/'receipt.json',receipt)
if __name__=='__main__':main()
