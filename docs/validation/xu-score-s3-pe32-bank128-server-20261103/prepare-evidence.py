#!/usr/bin/env python3
"""xu: preserve immutable actual compact-W32 actual server bytes and pinned Git sources."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

H = Path(__file__).resolve().parent
ROOT = H.parents[2]
REPO = ROOT.parent / 'ChipContest-xu-pe32-bank128'
SUB = 'third-party/e203_hbirdv2'
MAIN = 'f75880d4f06ccb7f1c16115bee501f53d9a2abb7'
CHILD = '52cfbea1f79f10e44f7d1696f54015797f886b96'


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '--no-replace-objects', *args], cwd=repo)


def write(name, value):
    (H / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def tree(repo, commit):
    result = {}
    for entry in git(repo, 'ls-tree', '-rz', commit).split(b'\0'):
        if not entry:
            continue
        meta, name = entry.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        result[name.decode()] = dict(mode=mode, kind=kind, oid=oid)
    return result


def blobs(repo, records):
    entries = [(n, r) for n, r in records.items() if r['kind'] == 'blob']
    stream = subprocess.run(['git', '--no-replace-objects', 'cat-file', '--batch'], cwd=repo,
        input=''.join(r['oid'] + '\n' for n, r in entries).encode(), stdout=subprocess.PIPE, check=True).stdout
    result, at = {}, 0
    for name, record in entries:
        end = stream.index(b'\n', at)
        oid, kind, size = stream[at:end].decode().split()
        at = end + 1
        size = int(size)
        need(oid == record['oid'] and kind == 'blob', 'Git object differs')
        result[name] = stream[at:at + size]
        at += size
        need(stream[at:at + 1] == b'\n', 'Git object separator differs')
        at += 1
    need(at == len(stream), 'Git object stream trailing bytes')
    return result

def main():
    need(not (H/'frozen-git-sources.tar.xz').exists(),'refuse existing completed source archive')
    folder=ROOT/'build/xu-score-resume-20261103/next-results-export-46'
    archive=folder.with_suffix('.tar.xz').read_bytes()
    need(len(archive)==117416 and sha(archive)=='d9c4470ef190ef40ebce4a5d21dfd5fd37e6f83ca0b4aa8f15735cd824cb5e79','actual export46 archive differs')
    manifest=json.loads((folder/'manifest.json').read_text());need(len(manifest)==len({x['path']for x in manifest})==167,'export path/count differs');selected=[]
    for record in manifest:
        relative=Path(record['path']);path=folder/relative
        need(not relative.is_absolute() and '..'not in relative.parts and path.is_file() and not path.is_symlink(),'unsafe raw path')
        data=path.read_bytes();need(len(data)==record['bytes'] and sha(data)==record['sha256'],'export byte differs')
        if relative.parts[0] in ['s3-pe32-bank128-accept-02','bank128-deploy-20261103-38']:
            target=H/'raw'/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():need(not target.is_symlink() and target.read_bytes()==data,'existing raw differs; preserve and stop')
            else:target.write_bytes(data)
            selected.append(record)
    need(len(selected)==150,'150 acceptance/bootstrap raw records expected')
    (H/'original-export-manifest.json').write_bytes((folder/'manifest.json').read_bytes());write('selected-manifest.json',selected)
    write('transport.json',dict(bytes=len(archive),sha256=sha(archive),export_payloads=167,selected_acceptance_payloads=147,selected_bootstrap_payloads=3,manifest_sha256=sha((folder/'manifest.json').read_bytes())))
    deployment=REPO/'build/xu-pe32-bank128-server-deploy-20261103-02'
    receipt=(deployment.parent/(deployment.name+'-receipt.json')).read_bytes();need(sha(receipt)=='eaff5cad26794fcbdd491f0a319190b4d192696de3780000d6a3e0ee73440880','original local packaging receipt differs')
    package=json.loads((deployment/'package-files.json').read_text());dest=H/'deployment';dest.mkdir()
    for name in ['launch.py','README.md','source-files.json','source-identity.json','package-files.json']:
        data=(deployment/name).read_bytes()
        if name in package:need(len(data)==package[name]['bytes']and sha(data)==package[name]['sha256'],'package file differs')
        (dest/name).write_bytes(data)
    (dest/'packaging-receipt.json').write_bytes(receipt)
    listed=json.loads((dest/'source-files.json').read_text());need(len(listed)==2637,'complete source manifest count differs')
    original={};modes={};full={}
    for label,repo,commit,prefix in [('main',REPO,MAIN,''),('child',REPO/SUB,CHILD,SUB+'/')]:
        records=tree(repo,commit);data=blobs(repo,records)
        full[label]=dict(commit=commit,tree=git(repo,'rev-parse',commit+'^{tree}').decode().strip(),entries=records)
        for name,record in records.items():
            if record['kind']=='commit':need(name==SUB and record['mode']=='160000'and record['oid']==CHILD,'wrong gitlink');continue
            key=prefix+name;need(key in listed,'missing frozen source path');entry=listed[key]
            need(entry['git_mode']==record['mode']and entry['bytes']==len(data[name])and entry['sha256']==sha(data[name]),'actual package/original Git bytes or mode differ')
            if record['mode']=='120000':need(entry['link_target'].encode()==data[name],'source symlink target differs')
            original[key]=data[name];modes[key]=record['mode']
    need(set(original)==set(listed),'package full tracked path set differs')
    snapshot={};accept=H/'raw/s3-pe32-bank128-accept-02/acceptance'
    for path in accept.rglob('result.json'):
        for name,expected in json.loads(path.read_text()).get('source_sha256',{}).items():
            n=name.replace(SUB+'/vsim/install/rtl/',SUB+'/rtl/e203/');need(sha(original[n])==expected,'measured source differs');snapshot[name]=original[n]
    for name,data in original.items():
        if name.startswith(('tools/scripts/','tools/ppa/','tests/e203/firmware/','tests/e203/test_','tests/numeric/','src/main/scala/','src/test/scala/linear/','tests/e203/tb_')) or name in ['tests/e203/vectors/kwt-silence-v1.json','tests/e203/vectors/kwt-silence-v1.tar.gz',SUB+'/vsim/bin/run.makefile','docs/validation/xu-score-s3-pe32-bank128-local-20261103/server_launch.py'] or (name.startswith('tests/e203/') and name.endswith('.S')):
            snapshot[name]=data
    with tarfile.open(H/'frozen-git-sources.tar.xz','x:xz')as tar:
        for name,data in sorted(snapshot.items()):
            item=tarfile.TarInfo(name);item.size=len(data);item.mode=0o644;item.mtime=0;tar.addfile(item,io.BytesIO(data))
    write('full-git-objects.json',full)
    write('git-source-audit.json',dict(main_commit=MAIN,e203_commit=CHILD,main_entries=len(full['main']['entries']),child_entries=len(full['child']['entries']),full_manifest_blobs=len(original),source_sha256={n:sha(b)for n,b in snapshot.items()},archived_source_count=len(snapshot),source_manifest_sha256=sha((dest/'source-files.json').read_bytes()),note='Every package-tracked path compared to original immutable Git blobs, modes, symlink targets and child gitlink; selected measured/reproduction source blobs archived. Actual server filesystem stability remains the launch verification receipt assertion.'))
    print('FROZEN150 actual raw /2637 source blobs/',len(snapshot),'archived sources')


if __name__=='__main__':main()
