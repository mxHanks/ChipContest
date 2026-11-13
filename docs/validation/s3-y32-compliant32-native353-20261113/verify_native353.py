#!/usr/bin/env python3
"""SHA-check, safely extract and independently replay native353 evidence.

Uses Python and the bundled read-only reviewer only. No EDA, remote access,
characterized library, cached library data or credential file is required.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def forbidden(name):
    parts = PurePosixPath(name).parts
    base = parts[-1].lower() if parts else ''
    return (any(p == 'WORK' or p.lower().startswith('alib-') or p.lower() in {'credentials', '.ssh'} for p in parts)
            or base.endswith(('.db', '.lib', '.alib', '.db.gz', '.lib.gz'))
            or base in {'access.json', 'credentials.json', 'id_rsa', 'id_ed25519'})


def summary(record):
    keys = ['status', 'timing_verdict', 'coverage', 'all_violator_rows_by_section',
            'leaf_counts', 'macro_groups', 'area_library_units',
            'charged_named_area_library_units',
            'conservative_all_soc_standard_plus33internal_library_units',
            'internal33_area_library_units', 'setup', 'hold', 'official_mm2_verdict']
    return {key: record[key] for key in keys}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--extract-to', type=Path, required=True)
    args = parser.parse_args()
    bundle, out = args.bundle.resolve(), args.extract_to.resolve()
    if out.exists():
        raise ValueError('fresh extraction directory required; no overwrite')
    manifest = json.loads((bundle / 'package-manifest.json').read_text())
    archive_name = manifest['archive']['name']
    if archive_name != 'native353-evidence.tar.xz':
        raise ValueError('unexpected archive name or path')
    archive = bundle / archive_name
    if sha(archive) != manifest['archive']['sha256'] or archive.stat().st_size != manifest['archive']['bytes']:
        raise ValueError('archive identity differs')
    expected = manifest['payload_files']
    if len(expected) > 10000 or sum(x['bytes'] for x in expected.values()) > 1024 * 1024 * 1024:
        raise ValueError('unreasonable evidence archive size')
    out.mkdir(parents=True)
    seen = set()
    with tarfile.open(archive, 'r:xz') as tar:
        for member in tar:
            name = member.name
            path = PurePosixPath(name)
            if (not member.isfile() or member.issym() or member.islnk() or path.is_absolute()
                    or '..' in path.parts or '\\' in name or name in seen or name not in expected
                    or path.as_posix() != name or forbidden(name)):
                raise ValueError('unsafe, duplicate, unindexed or forbidden archive member: ' + name)
            target = out.joinpath(*path.parts)
            if member.size != expected[name]['bytes']:
                raise ValueError('archive member size differs: ' + name)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            if source is None:
                raise ValueError('archive member has no bytes')
            with target.open('xb') as destination:
                shutil.copyfileobj(source, destination)
            if sha(target) != expected[name]['sha256']:
                raise ValueError('archive member identity differs: ' + name)
            seen.add(name)
    if seen != set(expected):
        raise ValueError('archive member set differs')
    reviewed = out / 'independent-review.json'
    command = [sys.executable, '-B', str(out / 'tools/review_native.py'),
               '--native', str(out / 'native/candidate'), '--inputs', str(out / 'inputs/candidate'),
               '--allow-omitted-alib-cache', '--out', str(reviewed)]
    done = subprocess.run(command, capture_output=True, text=True)
    (out / 'independent-review.stdout.txt').write_text(done.stdout + done.stderr)
    if done.returncode:
        raise ValueError('independent native replay failed; see retained stdout')
    result = json.loads(reviewed.read_text())
    wanted = json.loads((out / 'expected-summary.json').read_text())
    if summary(result) != wanted:
        raise ValueError('replayed native measurements differ from sealed reference')
    if result['coverage']['All Checks']['violated'] != 595 or result['timing_verdict'] != 'NOT_CLOSED':
        raise ValueError('this historical red353 evidence must not become a qualification PASS')
    output = {'status': 'PASS_SAFE_EXTRACTION_AND_NATIVE_REPORT_REPLAY_NOT_QUALIFIED',
              'archive_sha256': sha(archive), 'verified_payload_files': len(seen),
              'violated_checks': 595, 'timing_verdict': 'NOT_CLOSED',
              'charged_named_area_library_units': result['charged_named_area_library_units'],
              'conservative_all_soc_standard_plus33internal_library_units': result['conservative_all_soc_standard_plus33internal_library_units'],
              'independent_review_sha256': sha(reviewed), 'command': command,
              'omitted_vendor_cache_identities_retained_in_original_receipt': True,
              'no_eda_or_remote_access': True}
    (out / 'verification.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({key: output[key] for key in ['status', 'verified_payload_files', 'violated_checks',
                                                 'timing_verdict', 'charged_named_area_library_units',
                                                 'conservative_all_soc_standard_plus33internal_library_units']}))


if __name__ == '__main__':
    main()
