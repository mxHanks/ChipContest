#!/usr/bin/env python3
"""Make a publishable native353 report/source archive, excluding vendor caches."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def identity(path):
    return {'bytes': path.stat().st_size, 'sha256': sha(path)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native', type=Path, required=True)
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--reviewer', type=Path, required=True)
    p.add_argument('--reference-review', type=Path, required=True)
    p.add_argument('--stage', type=Path, required=True)
    a = p.parse_args()
    source, native, stage = a.inputs.resolve(), a.native.resolve(), a.stage.resolve()
    archive, manifest = HERE / 'native353-evidence.tar.xz', HERE / 'package-manifest.json'
    if stage.exists() or archive.exists() or manifest.exists():
        raise ValueError('fresh stage and delivery outputs required')
    spec = importlib.util.spec_from_file_location('native353_verify', HERE / 'verify_native353.py')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    stage.mkdir(parents=True)
    excluded_present = {}
    for path in sorted(native.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(native)
        if path.is_symlink():
            raise ValueError('native symbolic link forbidden: ' + str(rel))
        if verifier.forbidden(str(rel)):
            excluded_present[str(rel)] = identity(path)
            continue
        target = stage / 'native/candidate' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    pinned = json.loads((source / 'package-files.json').read_text())
    for name in list(pinned) + ['package-files.json']:
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts or '\\' in name or verifier.forbidden(name):
            raise ValueError('forbidden/unsafe input source file: ' + name)
        path = source / rel
        if path.is_symlink() or (name in pinned and sha(path) != pinned[name]):
            raise ValueError('sealed source drift: ' + name)
        target = stage / 'inputs/candidate' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    (stage / 'tools').mkdir()
    shutil.copy2(a.reviewer, stage / 'tools/review_native.py')
    expected = verifier.summary(json.loads(a.reference_review.read_text()))
    (stage / 'expected-summary.json').write_text(json.dumps(expected, indent=2, sort_keys=True) + '\n')
    policy = {'status': 'EXPLICIT_PUBLISHING_OMISSIONS_NOT_TIMING_EVIDENCE_OMISSIONS',
              'excluded_present_vendor_caches': excluded_present,
              'original_dc_receipt_preserved_sha256': sha(native / 'execution.json'),
              'original_pt_receipt_preserved_sha256': sha(native / 'pt/execution.json'),
              'source_package_files_sha256': sha(source / 'package-files.json'),
              'reviewer_sha256': sha(a.reviewer),
              'reference_review_sha256': sha(a.reference_review),
              'excluded_types': ['WORK compiler intermediate output', 'alib-52/*.db.alib vendor-derived cache',
                                 'all .db/.lib/.alib library files', 'credential/key files'],
              'required_evidence_not_omitted': ['original native receipts', 'all returned original reports',
                                              'mapped.v', 'mapped.ddc', 'default.svf', 'leaf-inventory.tsv'],
              'note': 'Original receipts keep SHA256/byte identities for omitted WORK and alib cache outputs. Source inputs are provided independently under inputs/candidate. No receipt bytes were rewritten.'}
    (stage / 'publication-omissions.json').write_text(json.dumps(policy, indent=2, sort_keys=True) + '\n')
    command = [sys.executable, '-B', str(stage / 'tools/review_native.py'), '--native', str(stage / 'native/candidate'),
               '--inputs', str(stage / 'inputs/candidate'), '--allow-omitted-alib-cache',
               '--out', str(stage / 'review-native353.json')]
    done = subprocess.run(command, capture_output=True, text=True)
    (stage / 'review-native353.stdout.txt').write_text(done.stdout + done.stderr)
    if done.returncode:
        raise ValueError('staged native replay failed; stage/log retained')
    reviewed = json.loads((stage / 'review-native353.json').read_text())
    if verifier.summary(reviewed) != expected:
        raise ValueError('new staged replay differs from original raw353 measurements')
    files = {str(path.relative_to(stage)): identity(path) for path in sorted(stage.rglob('*')) if path.is_file()}
    with tarfile.open(archive, 'w:xz', preset=6) as tar:
        for name in files:
            path = stage / name
            if verifier.forbidden(name):
                raise ValueError('forbidden payload file: ' + name)
            info = tar.gettarinfo(str(path), arcname=name)
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            info.mode = 0o644
            with path.open('rb') as stream:
                tar.addfile(info, stream)
    record = {'schema': 'compliant32-native353-publishable-archive-v1',
              'status': 'SEALED_NATIVE353_RED_EVIDENCE_NOT_QUALIFIED',
              'archive': {'name': archive.name, **identity(archive)},
              'payload_files': files, 'payload_bytes': sum(v['bytes'] for v in files.values()),
              'native_dc_receipt': identity(native / 'execution.json'),
              'native_pt_receipt': identity(native / 'pt/execution.json'),
              'pure_source_package_files_sha256': sha(source / 'package-files.json'),
              'excluded_present_vendor_caches': excluded_present,
              'no_eda_or_remote_access': True, 'timing_verdict': 'NOT_CLOSED',
              'official_area_mm2_verdict': 'NOT_VERIFIED', 'configuration': 'historical353; not final374'}
    manifest.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    (HERE / 'summary.json').write_text(json.dumps(expected, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': record['status'], 'archive': record['archive'],
                      'payload_files': len(files), 'excluded_vendor_cache_files': len(excluded_present)}))


if __name__ == '__main__':
    main()
