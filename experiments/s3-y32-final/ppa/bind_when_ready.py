#!/usr/bin/env python3
"""Wait for actual production CPU12 PASS, seal/replay and package inputs locally.

Single bounded preparation job only: no EDA, transport, credentials or services.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temp.replace(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-package', type=Path, required=True)
    p.add_argument('--cpu-full12', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--timeout-seconds', type=int, default=14400)
    a = p.parse_args()
    source, cpu, out, receipt = [x.resolve() for x in
        [a.source_package, a.cpu_full12, a.out, a.receipt]]
    if receipt.exists() or out.exists() or out.with_suffix('.tar.gz').exists():
        raise ValueError('new receipt, package and archive required')
    receipt.parent.mkdir(parents=True, exist_ok=True)
    record = dict(schema='final374-cpu12-local-bind-job-v1', status='WAITING_FOR_ACTUAL_CPU12_PASS',
        started_epoch=time.time(), deadline_epoch=time.time() + a.timeout_seconds,
        cpu_full12_path=str(cpu), source_package_path=str(source), out=str(out),
        source_package_files_sha256=sha(source / 'package-files.json'), native_eda_started=False)
    write(receipt, record)
    while time.time() < record['deadline_epoch']:
        if cpu.is_file():
            try:
                result = json.loads(cpu.read_text())
            except json.JSONDecodeError:
                result = {}
            if result.get('status') == 'PASS':
                break
            if result.get('status') == 'FAIL':
                record.update(status='CPU12_FAILED_NO_PACKAGE_NO_EDA', finished_epoch=time.time())
                write(receipt, record)
                return 1
        time.sleep(10)
    else:
        record.update(status='TIMEOUT_NO_PACKAGE_NO_EDA', finished_epoch=time.time())
        write(receipt, record)
        return 1
    record.update(status='BINDING_AND_RAW_REPLAY', cpu_full12_sha256=sha(cpu))
    write(receipt, record)
    command = ['python3', '-B', str(Path(__file__).resolve().parent / 'prepare.py'),
        '--source-package', str(source), '--cpu-full12', str(cpu), '--out', str(out)]
    process = subprocess.run(command, capture_output=True, text=True)
    record.update(command=command, returncode=process.returncode, stdout=process.stdout, stderr=process.stderr)
    if process.returncode:
        record.update(status='BIND_OR_RAW_REPLAY_FAILED_NO_EDA', finished_epoch=time.time())
        write(receipt, record)
        return 1
    pinned = json.loads((out / 'package-files.json').read_text())
    names = sorted(pinned) + ['package-files.json']
    files = {}
    for name in names:
        path = Path(name)
        actual = out / path
        if path.is_absolute() or '..' in path.parts or actual.is_symlink() or not actual.is_file():
            raise ValueError('unsafe package transfer path: ' + name)
        if path.suffix.lower() in {'.db', '.lib', '.alib', '.env'} or path.name.lower() in {'access.json', 'credentials.json'}:
            raise ValueError('private vendor/credential file forbidden: ' + name)
        digest = sha(actual)
        if name in pinned and pinned[name] != digest:
            raise ValueError('sealed source drift before transfer archive: ' + name)
        files[name] = dict(sha256=digest, bytes=actual.stat().st_size)
    archive = out.with_suffix('.tar.gz')
    with tarfile.open(archive, 'w:gz', compresslevel=9) as bundle:
        for name in names:
            bundle.add(out / name, arcname='candidate/' + name, recursive=False)
    manifest = out.with_suffix('.transfer.json')
    transfer = dict(schema='final374-input-transfer-v1', status='SEALED_CPU12_REPLAYED_INPUTS_ONLY_NO_EDA',
        archive_path=str(archive), archive_sha256=sha(archive), archive_bytes=archive.stat().st_size,
        package_files_sha256=sha(out / 'package-files.json'), cpu_full12_result_sha256=sha(cpu),
        files=files, native_outputs_included=False, vendor_libraries_or_credentials_included=False)
    write(manifest, transfer)
    record.update(status='CPU12_BOUND_RAW_REPLAY_AND_TRANSFER_SEAL_PASS_NO_EDA', finished_epoch=time.time(),
        package_files_sha256=sha(out / 'package-files.json'), transfer_manifest_path=str(manifest),
        transfer_manifest_sha256=sha(manifest), archive_path=str(archive), archive_sha256=sha(archive),
        archive_bytes=archive.stat().st_size)
    write(receipt, record)
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
