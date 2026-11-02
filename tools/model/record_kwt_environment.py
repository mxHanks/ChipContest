#!/usr/bin/env python3
"""Record and verify the installed legacy environment against its pinned lock.

Run with the isolated Python used for inference. Hashed installed RECORD entries
are checked against actual files. Bytecode and RECORD's own unhashed entries are
explicitly excluded from that check, while each RECORD's complete SHA is stored.
"""
import argparse
import base64
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            value.update(block)
    return value.hexdigest()


def normalize(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def snapshot(lock):
    require(sys.version_info[:3] == (3, 8, 20), 'use the actual isolated Python 3.8.20 runtime')
    expected = {}
    for line in lock.read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        name, version = line.split('==')
        require(normalize(name) not in expected, 'duplicate locked dependency')
        expected[normalize(name)] = version
    actual = {}
    records = []
    for distribution in metadata.distributions():
        name = normalize(distribution.metadata['Name'])
        require(name not in actual, 'duplicate installed dependency')
        actual[name] = distribution.version
        checked = []
        unhashed = []
        record_sha = None
        for entry in sorted(distribution.files or [], key=str):
            path = Path(distribution.locate_file(entry)).resolve()
            require(path.is_file(), 'installed distribution entry is missing: ' + str(entry))
            require(path == Path(sys.prefix).resolve() or Path(sys.prefix).resolve() in path.parents,
                    'dependency entry escapes isolated environment: ' + str(entry))
            if str(entry).endswith('.dist-info/RECORD'):
                record_sha = digest(path)
            if entry.hash is None:
                unhashed.append(str(entry))
                continue
            require(entry.hash.mode == 'sha256', 'unexpected installed dependency hash algorithm')
            actual_sha = digest(path)
            encoded = base64.urlsafe_b64encode(bytes.fromhex(actual_sha)).decode().rstrip('=')
            require(encoded == entry.hash.value, 'installed dependency RECORD/hash mismatch: ' + str(entry))
            checked.append(dict(path=str(entry), bytes=path.stat().st_size, sha256=actual_sha))
        require(record_sha is not None and checked, 'distribution lacks a verifiable RECORD: ' + name)
        identity = hashlib.sha256(json.dumps(checked, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        records.append(dict(name=name, version=distribution.version, record_sha256=record_sha,
            hashed_installed_files_verified=len(checked), hashed_installed_bytes_verified=sum(row['bytes'] for row in checked),
            verified_file_inventory_sha256=identity, unhashed_entries_not_checked=unhashed))
    require(actual == expected, 'installed package/version set differs from pinned lock')
    records.sort(key=lambda row: row['name'])
    identity = hashlib.sha256(json.dumps(records, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return dict(schema='xu-legacy-inference-environment-v1', status='PASS', python=platform.python_version(),
        executable=str(Path(sys.executable)), executable_resolved=str(Path(sys.executable).resolve()),
        executable_sha256=digest(Path(sys.executable).resolve()), prefix=sys.prefix,
        lock_sha256=digest(lock), packages=records, package_count=len(records),
        installed_package_inventory_sha256=identity,
        scope='actual installed file hashes checked against wheel/build RECORD entries; unhashed bytecode/RECORD entries explicitly excluded',
        fallback='TensorFlow CPU 2.4.0 release is an explicit fallback from requested upstream 2.4.0rc1')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = snapshot(args.lock)
    result['recorder_sha256'] = digest(Path(__file__))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print('PASS: {} locked distributions; installed package inventory {}'.format(
        result['package_count'], result['installed_package_inventory_sha256']))


if __name__ == '__main__':
    main()
