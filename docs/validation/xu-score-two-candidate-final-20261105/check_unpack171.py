#!/usr/bin/env python3
"""Verify every xu171 byte before safe optional extraction. No tar.extractall."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile

CHUNK=1024*1024
MAX_FILES=5000
MAX_MEMBER=512*1024*1024
MAX_TOTAL=2*1024*1024*1024
BLOCKED={'.git','__pycache__','private-manuals','private-docs'}


def need(ok,message):
    if not ok:raise ValueError(message)


def safe_name(name):
    need(isinstance(name,str)and name and '\0'not in name and '\\'not in name,'invalid member name')
    p=PurePosixPath(name)
    need(not p.is_absolute()and str(p)==name and not {'..','.'}&set(p.parts)and not BLOCKED&set(p.parts),'unsafe member: '+name)
    need(p.parts[0]not in ['checked171.json','EXTRACTION_FAILED171.json'],'reserved checker output path')
    return name


def unique_json(raw):
    def unique(pairs):
        out={}
        for k,v in pairs:
            need(k not in out,'duplicate JSON key: '+str(k));out[k]=v
        return out
    return json.loads(raw.decode('utf-8'),object_pairs_hook=unique)


def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as f:
        for block in iter(lambda:f.read(CHUNK),b''):h.update(block)
    return h.hexdigest()


def archive_identity(path):
    need(path.is_file()and not path.is_symlink(),'regular non-symlink archive required')
    return dict(bytes=path.stat().st_size,sha256=sha_file(path))


def inspect(path,expected_sha=None):
    path=Path(path).absolute();before=archive_identity(path)
    if expected_sha is not None:
        need(re.fullmatch('[0-9a-f]{64}',expected_sha)is not None and before['sha256']==expected_sha,'archive SHA256 differs')
    actual={};manifest=None;total=0
    with tarfile.open(str(path),'r:xz')as archive:
        for member in archive:
            name=safe_name(member.name)
            need(member.isfile()and not member.issym()and not member.islnk()and not member.sparse,'only regular nonsparse files allowed')
            need(name not in actual and 0<=member.size<=MAX_MEMBER,'duplicate/oversized archive member')
            need(len(actual)<MAX_FILES and total+member.size<=MAX_TOTAL,'archive resource limit exceeded')
            stream=archive.extractfile(member);need(stream is not None,'member body missing')
            h=hashlib.sha256();size=0;chunks=[]
            if name=='manifest.json':need(member.size<=16*CHUNK,'manifest too large')
            for block in iter(lambda:stream.read(CHUNK),b''):
                h.update(block);size+=len(block)
                if name=='manifest.json':chunks.append(block)
            need(size==member.size,'member body truncated');total+=size
            actual[name]=dict(path=name,bytes=size,sha256=h.hexdigest())
            if name=='manifest.json':manifest=unique_json(b''.join(chunks))
    need(isinstance(manifest,dict)and manifest.get('schema')=='xu-two-candidate-export171-v1'and
         manifest.get('qualification')=='NOT_QUALIFIED','missing/incorrect171 manifest')
    rows=manifest.get('files');need(isinstance(rows,list),'manifest files must be list');declared={}
    for row in rows:
        need(isinstance(row,dict)and set(row)=={'path','bytes','sha256'},'manifest identity shape differs')
        name=safe_name(row['path']);need(name!='manifest.json'and name not in declared,'duplicate/self manifest entry')
        need(type(row['bytes'])is int and row['bytes']>=0 and isinstance(row['sha256'],str)and
             re.fullmatch('[0-9a-f]{64}',row['sha256'])is not None,'invalid manifest bytes/SHA')
        declared[name]=row
    actual.pop('manifest.json',None)
    need(actual==declared,'manifest set/bytes/SHA differ from every actual payload byte')
    for name in declared:
        need(not any(str(p)in declared or str(p)=='manifest.json'for p in PurePosixPath(name).parents if str(p)!='.'),'file/directory prefix collision')
    need(manifest.get('payload_files')==len(actual)and manifest.get('payload_bytes')==sum(r['bytes']for r in actual.values()),'manifest totals differ')
    need('snapshot171.json'in actual,'explicit snapshot provenance missing')
    after=archive_identity(path);need(after==before,'archive changed during verification')
    return dict(schema='xu-checked-export171-v1',status='VERIFIED_ALL_PACKAGED_BYTES_NOT_QUALIFIED',qualification='NOT_QUALIFIED',
                archive=dict(path=str(path),**after),expected_archive_sha256_verified=expected_sha is not None,
                payload_files=len(actual),payload_bytes=sum(r['bytes']for r in actual.values())),declared


def unpack(path,out,expected_sha=None):
    path=Path(path).absolute();out=Path(out).absolute();need(not out.exists()and not out.is_symlink(),'fresh extraction directory required')
    report,declared=inspect(path,expected_sha)
    out.mkdir(parents=True,exist_ok=False)
    try:
        with tarfile.open(str(path),'r:xz')as archive:
            names=set()
            for member in archive:
                name=safe_name(member.name)
                need(member.isfile()and not member.issym()and not member.islnk()and not member.sparse,'member type changed')
                need(name not in names,'duplicate extraction member');names.add(name)
                need(name=='manifest.json'or name in declared,'unexpected extraction member')
                need(member.size==declared[name]['bytes']if name!='manifest.json'else member.size<=16*CHUNK,'extraction member size changed')
                destination=out/name;parent=out
                for piece in PurePosixPath(name).parts[:-1]:
                    parent=parent/piece
                    if not parent.exists():parent.mkdir()
                    need(parent.is_dir()and not parent.is_symlink(),'unsafe extraction parent')
                need(not destination.exists()and not destination.is_symlink(),'extraction path exists')
                stream=archive.extractfile(member);need(stream is not None,'member body missing')
                h=hashlib.sha256();size=0
                fd=os.open(str(destination),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(fd,'wb')as target:
                    for block in iter(lambda:stream.read(CHUNK),b''):
                        h.update(block);size+=len(block);target.write(block)
                need(size==member.size,'member truncated during extraction')
                if name!='manifest.json':need(dict(path=name,bytes=size,sha256=h.hexdigest())==declared[name],'payload changed during extraction')
            need(names==set(declared)|{'manifest.json'},'extraction inventory changed')
        need(archive_identity(path)=={k:report['archive'][k]for k in ['bytes','sha256']},'archive changed during extraction')
        report.update(extracted_to=str(out));(out/'checked171.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    except BaseException as error:
        failure=out/'EXTRACTION_FAILED171.json'
        if not failure.exists():failure.write_text(json.dumps(dict(status='FAILED_EXTRACTION_RETAINED_NOT_QUALIFIED',error=type(error).__name__+': '+str(error)),sort_keys=True,indent=2)+'\n')
        raise
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['check','unpack'])
    p.add_argument('--archive',type=Path,required=True);p.add_argument('--sha256');p.add_argument('--out',type=Path)
    a=p.parse_args()
    if a.action=='unpack':need(a.out is not None,'--out required for unpack');report=unpack(a.archive,a.out,a.sha256)
    else:need(a.out is None,'check does not create output');report,_=inspect(a.archive,a.sha256)
    print(json.dumps(report,sort_keys=True,indent=2))


if __name__=='__main__':main()
