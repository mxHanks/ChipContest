#!/usr/bin/env python3
"""Stream-verify all 58 immutable actual69 payloads, optionally extract."""
import argparse,hashlib,json,tarfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parent
ARCHIVE_SHA='d115ae49c1b0949653ee14222343dbcf745a1a3680d86efaca2c6e374fc72733'
def need(ok,message):
    if not ok:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def verify(selected=(),extract=None):
    archive=ROOT/'payload.tar.xz';need(archive.stat().st_size==264268 and sha(archive.read_bytes())==ARCHIVE_SHA,'immutable archive SHA differs')
    manifest=json.loads((ROOT/'original-manifest.json').read_text());expected={r['path']:r for r in manifest}
    need(len(manifest)==len(expected)==58 and sum(r['bytes']for r in manifest)==16423789,'actual source manifest dimensions differ')
    if extract:
        extract=Path(extract);extract.mkdir(exist_ok=False)
    selected=set(selected);found={};observed={};seen=set();inside=None
    with tarfile.open(archive,mode='r|xz')as tar:
        for member in tar:
            path=PurePosixPath(member.name)
            need(member.isfile()and not path.is_absolute()and '..'not in path.parts and member.name not in seen,'unsafe or duplicate native archive member')
            need(member.size<64000000,'unexpected oversized member');seen.add(member.name)
            keep=member.name in selected or member.name=='manifest.json'
            content=bytearray()if keep else None;h=hashlib.sha256();size=0;writer=None
            if extract:
                out=extract/member.name;out.parent.mkdir(parents=True,exist_ok=True);writer=out.open('xb')
            try:
                with tar.extractfile(member)as source:
                    while True:
                        data=source.read(1024*1024)
                        if not data:break
                        size+=len(data);h.update(data)
                        if keep:content.extend(data)
                        if writer:writer.write(data)
            finally:
                if writer:writer.close()
            need(size==member.size,'native member size differs')
            if member.name=='manifest.json':inside=json.loads(content)
            else:
                observed[member.name]=dict(path=member.name,bytes=size,sha256=h.hexdigest())
                if keep:found[member.name]=bytes(content)
    need(inside==manifest and observed==expected,'all 58 native payload SHA/size comparisons must match')
    need(set(found)==selected,'selected native evidence missing')
    return found
def main():
    p=argparse.ArgumentParser();p.add_argument('--extract',type=Path);args=p.parse_args()
    verify(extract=args.extract)
    print(json.dumps(dict(status='PASS',qualification='NOT_QUALIFIED',archive_bytes=264268,archive_sha256=ARCHIVE_SHA,payload_count=58,payload_bytes=16423789),sort_keys=True,indent=2))
if __name__=='__main__':main()
