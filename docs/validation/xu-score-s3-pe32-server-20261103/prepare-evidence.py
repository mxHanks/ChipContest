#!/usr/bin/env python3
"""Freeze selected original S3 server evidence and independently read pinned Git blobs.

This copies no remote files and runs no RTL/EDA job. Each output must be fresh.
"""
import argparse
import hashlib
import io
import json
import posixpath
from pathlib import Path
import shutil
import subprocess
import tarfile

MAIN='94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114'
CHILD='fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5'
TRANSPORT_SHA='5330f5c8b03d9a8f8077f1dbc51908881bb9d472ebad3c3b4fd73d81aa180336'
TRANSPORT_BYTES=279572
SUB='third-party/e203_hbirdv2'

def need(v,m):
    if not v:raise ValueError(m)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,j):p.write_text(json.dumps(j,indent=2,sort_keys=True)+'\n')
def git(root,*args):return subprocess.check_output(['git','--no-replace-objects',*args],cwd=root)
def tree(root,commit):
    result={}
    for entry in git(root,'ls-tree','-rz',commit).split(b'\0'):
        if not entry:continue
        meta,name=entry.split(b'\t',1);mode,kind,oid=meta.decode().split()
        result[name.decode()]=dict(mode=mode,kind=kind,oid=oid)
    return result
def blobs(root,records):
    entries=[(n,r)for n,r in records.items()if r['kind']=='blob']
    stream=subprocess.run(['git','--no-replace-objects','cat-file','--batch'],cwd=root,
        input=''.join(r['oid']+'\n'for n,r in entries).encode(),stdout=subprocess.PIPE,check=True).stdout
    result={};at=0
    for name,record in entries:
        end=stream.index(b'\n',at);oid,kind,size=stream[at:end].decode().split();at=end+1;size=int(size)
        need(oid==record['oid']and kind=='blob','Git batch object differs')
        result[name]=stream[at:at+size];at+=size;need(stream[at:at+1]==b'\n','Git batch separator differs');at+=1
    need(at==len(stream),'Git batch trailing bytes')
    return result

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--export',type=Path,required=True)
p.add_argument('--candidate',type=Path,required=True)
p.add_argument('--deployment',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();b=a.export.resolve();out=a.out.resolve();repo=a.candidate.resolve();deployment=a.deployment.resolve()
need(out.is_dir(),'archive directory required')
archive=b.with_suffix('.tar.xz');need(archive.stat().st_size==TRANSPORT_BYTES and sha(archive.read_bytes())==TRANSPORT_SHA,'original transport differs')
manifest=read(b/'manifest.json');need(len(manifest)==174 and len({r['path']for r in manifest})==174,'export manifest uniqueness differs')
for r in manifest:
    path=Path(r['path']);need(not path.is_absolute()and '..'not in path.parts,'unsafe original path')
    raw=(b/path).read_bytes();need(len(raw)==r['bytes']and sha(raw)==r['sha256'],'original payload differs: '+str(path))
selected=[r for r in manifest if r['path'].startswith(('s3-pe32-accept-01/','s3-pe32-deploy-20261103-01/'))]
need(len(selected)==129,'selected S3 raw set differs')
for r in selected:
    dest=out/'raw'/r['path'];dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():need(dest.read_bytes()==(b/r['path']).read_bytes(),'existing raw payload differs; never overwrite')
    else:shutil.copyfile(b/r['path'],dest)
write(out/'original-export-manifest.json',manifest);write(out/'selected-manifest.json',selected)
ident=read(deployment/'source-identity.json');need(ident['main_commit']==MAIN and ident['e203_commit']==CHILD,'deployment pin differs')
for name,record in read(deployment/'package-files.json').items():
    raw=(deployment/name).read_bytes();need(len(raw)==record['bytes']and sha(raw)==record['sha256'],'deployment package payload differs: '+name)
sources={};modes={}
for location,commit,prefix in [(repo,MAIN,''),(repo/SUB,CHILD,SUB+'/')]:
    records=tree(location,commit)
    for name,raw in blobs(location,records).items():sources[prefix+name]=raw;modes[prefix+name]=records[name]['mode']
main_tree=tree(repo,MAIN);need(main_tree[SUB]['kind']=='commit'and main_tree[SUB]['oid']==CHILD,'main child gitlink differs')
frozen=read(deployment/'source-files.json')
resolved=dict(sources);symlinks={}
for name,mode in modes.items():
    if mode!='120000':continue
    target=sources[name].decode();need(not target.startswith('/'),'absolute Git symlink target')
    destination=posixpath.normpath(posixpath.join(posixpath.dirname(name),target))
    need(destination in sources and modes[destination]!='120000','Git symlink target absent/recursive')
    resolved[name]=sources[destination]
    symlinks[name]=dict(target=target,git_blob_sha256=sha(sources[name]),resolved_path=destination,resolved_sha256=sha(resolved[name]))
need({n:sha(v)for n,v in resolved.items()}==frozen and len(frozen)==2510,'full2510 deployment source SHA differs from immutable Git sources')
copied=['source-identity.json','source-files.json','package-files.json','launch.py','README.md']
for name in copied:
    dest=out/'deployment'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(deployment/name,dest)
receipt=deployment.parent/(deployment.name+'-receipt.json');shutil.copyfile(receipt,out/'deployment/packaging-receipt.json')
snapshot={}
accept=b/'s3-pe32-accept-01/acceptance'
for path in accept.rglob('result.json'):
    snapshot.update({name:sources[name.replace(SUB+'/vsim/install/rtl/',SUB+'/rtl/e203/')]
                     for name in read(path).get('source_sha256',{})})
for name in sources:
    if name.startswith(('tools/scripts/','tests/e203/firmware/','tests/e203/test_','tests/numeric/'))or name in [
        'src/main/scala/GenerateRTL.scala','src/main/scala/linear/XuParallelCore.scala',
        'src/test/scala/linear/XuParallelAutoGroupCoreTest.scala',
        'tests/e203/tb_xu_pe32_wrapper.sv','tests/e203/tb_xu_pe32_compat_wrapper.sv',
        'tests/e203/tb_xu_cached_wrapper.sv',SUB+'/vsim/bin/run.makefile']:
        snapshot[name]=sources[name]
with tarfile.open(out/'frozen-git-sources.tar.xz','x:xz')as t:
    for name,raw in sorted(snapshot.items()):
        member=tarfile.TarInfo(name);member.size=len(raw);member.mtime=0;member.mode=0o644;t.addfile(member,io.BytesIO(raw))
write(out/'git-source-audit.json',dict(main_commit=MAIN,e203_commit=CHILD,
    source_sha256={n:sha(v)for n,v in sorted(snapshot.items())},full_tracked_source_paths_verified=len(frozen),
    full_tracked_source_manifest_sha256=sha((deployment/'source-files.json').read_bytes()),
    full_tracked_git_modes=modes,git_symlinks=symlinks,
    child_changed_from_f49=git(repo/SUB,'diff','--name-only','f49a5fc914971426bd4530db39e270a84b41139f',CHILD).decode().splitlines(),
    transport=dict(bytes=TRANSPORT_BYTES,sha256=TRANSPORT_SHA),
    note='All2510 deployment path hashes rechecked against immutable Git sources; four tracked symlinks use Git-resolved target bytes, as the deployment manifest did. Only selected measured/reproduction blobs copied in the source tar; installed RTL evidence-key aliases retained.'))
print('FROZEN',len(selected),'raw payloads;',len(frozen),'tracked source hashes;',len(snapshot),'archived source blobs')
