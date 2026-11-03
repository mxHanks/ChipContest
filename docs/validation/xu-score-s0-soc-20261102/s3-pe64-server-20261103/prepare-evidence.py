#!/usr/bin/env python3
"""xu: preserve immutable actual PE64 server01/02 bytes and pinned Git sources."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

H = Path(__file__).resolve().parent
ROOT = H.parents[3]
REPO = ROOT.parent / 'ChipContest-xu-s3-pe64'
SUB = 'third-party/e203_hbirdv2'
MAIN = '3443fad8945577626d226b1cd53eadec89331a20'
CHILD = '7aae96776e116d5e95d6ebb49d29a5fccce04ab9'


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
    need(not (H / 'selected-manifest.json').exists(), 'refusing to overwrite evidence')
    selected = []
    transports = []
    for name, count, size, expected_sha, groups in [
        ('next-results-export-28', 188, 265524, 'b5f00d48912278915a8236e3bcc7b1080e0b3eaa02126539984a8e04b51ea1d7',
         ['s3-pe64-accept-02', 's3-pe64-deploy-20261103-02']),
        ('terminal-results-export-22', 142, 807588, 'a6dd89390d2ba93c10f5d207e3111833d62bbab96772dee9787d6a7987401d7d',
         ['s3-pe64-accept-01', 's3-pe64-deploy-20261103-01'])]:
        folder = ROOT / 'build/xu-score-resume-20261103' / name
        transport = folder.with_suffix('.tar.xz').read_bytes()
        need(len(transport) == size and sha(transport) == expected_sha, 'transport differs')
        raw_manifest = (folder / 'manifest.json').read_bytes()
        manifest = json.loads(raw_manifest)
        need(len(manifest) == count and len({e['path'] for e in manifest}) == count, 'manifest duplicate/count')
        for entry in manifest:
            path = Path(entry['path'])
            need(not path.is_absolute() and '..' not in path.parts and (folder / path).is_file()
                 and not (folder / path).is_symlink(), 'unsafe exported path')
            b = (folder / path).read_bytes()
            need(len(b) == entry['bytes'] and sha(b) == entry['sha256'], 'exported payload differs')
            if path.parts[0] in groups:
                target = H / 'raw' / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b)
                selected.append(dict(entry, export=name))
        (H / (name + '-manifest.json')).write_bytes(raw_manifest)
        transports.append(dict(name=name, bytes=size, sha256=expected_sha,
                               manifest_sha256=sha(raw_manifest), payload_count=count))
    need(len(selected) == 206, 'PE64 raw selection count')
    write('selected-manifest.json', selected)
    write('transports.json', transports)
    source_manifest = json.loads((H / 'raw/s3-pe64-deploy-20261103-02/source-files.json').read_text())
    sources, modes = {}, {}
    for label, repo, commit, prefix in [('main', REPO, MAIN, ''), ('child', REPO / SUB, CHILD, SUB + '/')]:
        records = tree(repo, commit)
        payload = blobs(repo, records)
        listed = source_manifest[label]
        need(listed['commit'] == commit and len(listed['files']) == len(records), 'full source count/pin differs')
        need(len({r['path'] for r in listed['files']}) == len(records), 'duplicate source path')
        for record in listed['files']:
            n = record['path']
            original = records[n]
            need(record['mode'] == original['mode'] and record['git_oid'] == original['oid'], 'Git identity/mode differs')
            if original['kind'] == 'blob':
                b = payload[n]
                need(len(b) == record['bytes'] and sha(b) == record['sha256'], 'full source bytes differ')
                sources[prefix + n] = b
                modes[prefix + n] = original['mode']
            else:
                need(n == SUB and original['kind'] == 'commit' and original['oid'] == CHILD, 'unexpected gitlink')
    snapshot = {}
    accept = H / 'raw/s3-pe64-accept-02/acceptance'
    for path in accept.rglob('result.json'):
        for name, expected_sha in json.loads(path.read_text()).get('source_sha256', {}).items():
            n = name.replace(SUB + '/vsim/install/rtl/', SUB + '/rtl/e203/')
            need(sha(sources[n]) == expected_sha, 'actual measured RTL/TB differs')
            snapshot[name] = sources[n]
    for name, b in sources.items():
        if name.startswith(('tools/scripts/', 'tests/e203/firmware/', 'tests/e203/test_', 'tests/numeric/',
                            'src/main/scala/', 'src/test/scala/linear/', 'tests/e203/tb_')) or (name.startswith('tests/e203/') and name.endswith('.S')) or name in [
            'tests/e203/tb_accel_soc.sv', 'tests/e203/tb_xu_pe64_wrapper.sv',
            'tests/e203/tb_xu_pe64_boundary.sv', 'tests/e203/tb_xu_pe64_compat_wrapper.sv',
            'tests/e203/tb_xu_cached_wrapper.sv', 'tests/e203/vectors/kwt-silence-v1.json',
            'tests/e203/vectors/kwt-silence-v1.tar.gz', SUB + '/vsim/bin/run.makefile']:
            snapshot[name] = b
    with tarfile.open(H / 'frozen-git-sources.tar.xz', 'x:xz') as tar:
        for name, b in sorted(snapshot.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(b), 0, 0o644
            tar.addfile(info, io.BytesIO(b))
    old = '6f47746a916e14d0bbdcbb799c6338acd5c979a7'
    diff = git(REPO, 'diff', '--binary', old, MAIN)
    (H / 'server01-to-02.patch').write_bytes(diff)
    old_sources = {name: git(REPO, 'show', old + ':' + name) for name in [
        'tests/e203/test_pe64_contract.py', 'tools/scripts/xu_prepare_pe64_deployment.py',
        'tools/scripts/xu_s3_pe64_bootstrap.py']}
    with tarfile.open(H / 'server01-compatibility-sources.tar.xz', 'x:xz') as tar:
        for name, b in sorted(old_sources.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(b), 0, 0o644
            tar.addfile(info, io.BytesIO(b))
    deployment = REPO / 'build/xu-pe64-deployment-20261103-02'
    need(json.loads((deployment / 'source-identity.json').read_text())['main_commit'] == MAIN, 'deployment differs')
    package = json.loads((deployment / 'package-files.json').read_text())
    (H / 'deployment').mkdir()
    for name in ['launch.py', 'README.md', 'source-files.json', 'source-identity.json', 'package-files.json']:
        b = (deployment / name).read_bytes()
        if name in package:
            need(len(b) == package[name]['bytes'] and sha(b) == package[name]['sha256'], 'deployment bytes differ')
        (H / 'deployment' / name).write_bytes(b)
    shutil.copyfile(deployment.parent / (deployment.name + '.receipt.json'), H / 'deployment/packaging-receipt.json')
    write('git-source-audit.json', dict(main_commit=MAIN, e203_commit=CHILD, full_manifest_entries=2713,
        full_blob_entries=len(sources), source_sha256={n: sha(b) for n, b in sorted(snapshot.items())},
        full_source_manifest_sha256=sha((deployment / 'source-files.json').read_bytes()),
        archived_source_count=len(snapshot), full_git_modes=modes,
        old_main_commit=old, unchanged_child=True,
        server01_to_02_paths=git(REPO, 'diff', '--name-only', old, MAIN).decode().splitlines(),
        server01_to_02_patch_sha256=sha(diff), old_source_sha256={n: sha(b) for n, b in old_sources.items()},
        child_delta_from_pe32=git(REPO / SUB, 'diff', '--name-only', 'fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5', CHILD).decode().splitlines(),
        note='All 2713 manifest entries checked against immutable Git: 2712 blobs (four literal symlink target strings), plus exact child gitlink. Selected measured/reproduction blobs are bundled; no server binaries rehashed locally.'))
    print('FROZEN206 raw;2713 manifest entries;2712 blobs;', len(snapshot), 'snapshot blobs')


if __name__ == '__main__':
    main()
