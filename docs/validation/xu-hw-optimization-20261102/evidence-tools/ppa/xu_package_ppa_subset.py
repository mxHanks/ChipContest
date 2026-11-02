#!/usr/bin/env python3
"""Verify the original PPA transfer, then archive exact selected original bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

SOURCE_ARCHIVE_SHA256 = '8fc6a127069934bb21227b865918c45aeb74f4f7739b7c24b34b32ee5a4c31f3'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_original(source, archive):
    require(sha256(archive) == SOURCE_ARCHIVE_SHA256, 'source transfer archive SHA differs')
    manifest = json.loads((source/'ppa-transfer-manifest.json').read_text())
    require(manifest['schema'] == 'xu-original-ppa-artifacts-v1' and len(manifest['files']) == 113,
            'source transfer file inventory differs')
    actual = {path.relative_to(source).as_posix() for path in source.rglob('*') if path.is_file()}
    require(actual == set(manifest['files']) | {'ppa-transfer-manifest.json'},
            'unpacked source file set differs from transfer manifest')
    with tarfile.open(str(archive), 'r:xz') as stream:
        members = stream.getmembers()
        require(len(members) == len({member.name for member in members}), 'duplicate source archive entry')
        archived = {}
        for member in members:
            name = Path(member.name)
            require(not name.is_absolute() and '..' not in name.parts and member.isfile(),
                    'unsafe/non-file source archive entry')
            archived[member.name] = stream.extractfile(member).read()
        require(set(archived) == actual, 'source archive member set differs')
        for name, payload in archived.items():
            require((source/name).read_bytes() == payload, 'source archive/unpacked bytes differ: '+name)
    for name, record in manifest['files'].items():
        require(sha256(source/name) == record['sha256'] and (source/name).stat().st_size == record['bytes'],
                'source original byte/hash differs: '+name)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--source-archive', required=True)
    parser.add_argument('--out', required=True, help='new .tar.xz archive path')
    args = parser.parse_args()
    source, archive, out = Path(args.source).resolve(), Path(args.source_archive).resolve(), Path(args.out).resolve()
    manifest = verify_original(source, archive)
    require(not out.exists(), 'refusing to replace subset archive')
    included, omitted = {}, {}
    for name, record in manifest['files'].items():
        reason = None
        if name.endswith('.txt'):
            require('/pt-help-' in name or '/pt-man-' in name, 'unexpected .txt exclusion')
            reason = 'vendor full help/manual payload; unnecessary for source/log/metric reproducibility'
        elif Path(name).name in ['summary.json', 'baseline-summary.json', 'paired-summary.json']:
            reason = 'duplicate summary JSON, some containing embedded vendor manual payload; exact raw reports/metadata retained'
        if reason:
            omitted[name] = dict(record, reason=reason, preserved_at='original server_path and source transfer archive')
        else:
            require(not name.endswith(('.db', '.lib', '.ddc')) and Path(name).name not in ['mapped.v', 'mem_1024x16.sv'],
                    'unexpected library, mapped-netlist or vendor-model payload')
            included[name] = dict(record)
    with tempfile.TemporaryDirectory(prefix='xu-ppa-subset-') as temporary:
        staging = Path(temporary)/'xu-ppa-reproducibility'
        staging.mkdir()
        for name in list(included)+['ppa-transfer-manifest.json']:
            destination = staging/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(source/name), str(destination))
        derived = dict(schema='xu-derived-ppa-reproducibility-subset-v1', evidence_kind='derived selection; included originals are byte-identical',
                       source_archive=dict(name=archive.name, sha256=sha256(archive), bytes=archive.stat().st_size,
                                           source_original_files_verified=113),
                       original_transfer_manifest=dict(path='ppa-transfer-manifest.json', sha256=sha256(source/'ppa-transfer-manifest.json'),
                                                       copied_without_modification=True),
                       included_originals=included, omitted_originals=omitted,
                       excluded_before_original_transfer=manifest['mapped_netlists'],
                       limits=['No library DB/Liberty, vendor model, mapped-netlist or vendor full manual payload included.',
                               'Original failure and unset-Library-Compiler attempts remain original records; replay uses corrected environment.',
                               'This selection does not add a synthesis, timing or power run.'])
        (staging/'derived-subset-manifest.json').write_text(json.dumps(derived, indent=2, sort_keys=True)+'\n')
        paths = sorted(path for path in staging.rglob('*') if path.is_file())
        (staging/'SHA256SUMS').write_text(''.join(sha256(path)+'  '+path.relative_to(staging).as_posix()+'\n' for path in paths))
        out.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(str(out), 'w:xz', preset=9) as stream:
            for path in sorted(path for path in staging.rglob('*') if path.is_file()):
                info = stream.gettarinfo(str(path), arcname=path.relative_to(staging.parent).as_posix())
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ''
                info.mode = 0o644
                with path.open('rb') as payload:
                    stream.addfile(info, payload)
    print(json.dumps(dict(status='PASS', original_files_verified=113, included_originals=len(included),
                          omitted_originals=len(omitted), archive_sha256=sha256(out), archive_bytes=out.stat().st_size,
                          ordinary_files_including_manifest=len(included)+3), indent=2))


if __name__ == '__main__':
    main()
