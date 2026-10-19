#!/usr/bin/env python3
"""Verify the official archive, safely extract it and inventory source WAVs.

This records raw source partitions, not KWT's unknown/silence sampling list.
Use the pinned upstream AudioProcessor to construct evaluation examples.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_BYTES = 2428923189
EXPECTED_SHA = 'af14739ee7dc311471de98f5f9d2c9191b18aedfe957f4a6ff791c709868ff58'
SOURCE_URL = 'https://storage.googleapis.com/download.tensorflow.org/data/speech_commands_v0.02.tar.gz'
CHECKSUM_URL = 'https://raw.githubusercontent.com/tensorflow/datasets/master/tensorflow_datasets/datasets/speech_commands/checksums.tsv'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def safe_name(member):
    path = PurePosixPath(member.name)
    if path.is_absolute() or '..' in path.parts or '\\' in member.name:
        raise ValueError('unsafe archive member: ' + member.name)
    if not (member.isfile() or member.isdir()):
        raise ValueError('link/device/unsupported member: ' + member.name)
    if not path.parts:
        if member.isdir():
            return None
        raise ValueError('empty filename')
    return Path(*path.parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New directory only')
    args = parser.parse_args()
    archive, output = args.archive.resolve(), args.output.resolve()
    if output.exists():
        parser.error('output already exists; never overwrite an existing dataset')
    report = {'schema': 'speech-commands-v2-inventory-v1', 'status': 'FAIL',
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'command': [sys.executable, *sys.argv], 'archive': str(archive),
              'source_url': SOURCE_URL, 'checksum_source': CHECKSUM_URL,
              'scope': 'archive integrity and source file inventory; not model/RTL precision',
              'evaluation_manifest': 'NOT_RUN: construct using pinned KWT AudioProcessor',
              'implementation_sha256': digest(__file__)}
    output.mkdir(parents=True, exist_ok=False)
    try:
        if archive.stat().st_size != EXPECTED_BYTES or digest(archive) != EXPECTED_SHA:
            raise ValueError('archive length/SHA256 differs from official checksum')
        report['archive_sha256'] = EXPECTED_SHA
        records, seen = [], set()
        with tarfile.open(archive, 'r:gz') as tar:
            members = tar.getmembers()
            if len(members) > 200000 or sum(m.size for m in members) > 12 * (1 << 30):
                raise ValueError('unexpected archive count/expanded size')
            for member in members:
                relative = safe_name(member)
                if relative is None:
                    continue
                if relative in seen:
                    raise ValueError('duplicate archive path')
                seen.add(relative)
            for member in members:
                relative = safe_name(member)
                if relative is None:
                    continue
                target = output / relative
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src, target.open('xb') as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
                if target.stat().st_size != member.size:
                    raise ValueError('truncated member: ' + member.name)
                records.append({'path': relative.as_posix(), 'bytes': member.size,
                                'sha256': digest(target)})
        manifest = output / 'source-files.json'
        manifest.write_text(json.dumps(records, indent=2) + '\n')
        counts = Counter(Path(r['path']).parts[0] for r in records if r['path'].endswith('.wav'))
        if not counts or '_background_noise_' not in counts:
            raise ValueError('missing expected audio/background folders')
        report.update(status='PASS', files=len(records), wav_by_directory=dict(sorted(counts.items())),
                      expanded_bytes=sum(r['bytes'] for r in records),
                      inventory={'path': str(manifest), 'sha256': digest(manifest)},
                      end_marker='SPEECH_COMMANDS_PREPARED')
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
    (output / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('status', 'scope')}, ensure_ascii=False))
    if report['status'] == 'PASS':
        print('SPEECH_COMMANDS_PREPARED ' + str(output / 'preparation.json'))
    else:
        print(report['error'], file=sys.stderr)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
