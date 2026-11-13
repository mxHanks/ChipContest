#!/usr/bin/env python3
"""Negative report-replay checks on a disposable verified extraction only.

Temporarily hides files in that derived extraction and restores exact bytes in
finally blocks. Never point this at returned native originals or source inputs.
No EDA or remote commands are executed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--extracted', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    root = args.extracted.resolve()
    if args.out.exists() or not (root / 'verification.json').is_file() or not (root / 'independent-review.json').is_file():
        raise ValueError('fresh output and disposable independently verified extraction required')
    native, inputs = root / 'native/candidate', root / 'inputs/candidate'
    manifest = json.loads((Path(__file__).resolve().parent / 'package-manifest.json').read_text())
    before = {name: sha(root / name) for name in manifest['payload_files']}
    cases = []

    def run(name, expected, allow=True):
        result = root / ('negative-' + name + '.json')
        if result.exists():
            raise ValueError('refuse repeated negative output')
        command = [sys.executable, '-B', str(root / 'tools/review_native.py'),
                   '--native', str(native), '--inputs', str(inputs), '--out', str(result)]
        if allow:
            command += ['--allow-omitted-alib-cache']
        done = subprocess.run(command, capture_output=True, text=True)
        text = done.stdout + done.stderr
        if done.returncode == 0 or expected not in text or result.exists():
            raise ValueError('negative check did not fail at expected evidence guard: ' + name)
        cases.append({'case': name, 'returncode': done.returncode,
                      'expected_failure': expected, 'observed_failure': text.splitlines()[-1]})

    run('cache-needs-explicit-selector', 'missing returned evidence:dc:alib-52/', allow=False)
    for name, file, expected in [
        ('missing-hold-report', native / 'pt/reports/hold.rpt', 'missing returned evidence:pt:reports/hold.rpt'),
        ('missing-mapped-netlist', native / 'mapped.v', 'missing returned evidence:dc:mapped.v')]:
        backup = file.with_name(file.name + '.negative-backup')
        if backup.exists():
            raise ValueError('preexisting negative backup')
        file.rename(backup)
        try:
            run(name, expected)
        finally:
            backup.rename(file)
    receipt = native / 'execution.json'
    original = receipt.read_bytes()
    changed = json.loads(original)
    changed['outputs']['alib-52/important-report.rpt'] = {'bytes': 1, 'sha256': '0' * 64}
    receipt.write_text(json.dumps(changed) + '\n')
    try:
        run('alib-prefix-cannot-hide-report', 'missing returned evidence:dc:alib-52/important-report.rpt')
    finally:
        receipt.write_bytes(original)
    after = {name: sha(root / name) for name in manifest['payload_files']}
    if before != after:
        raise ValueError('derived extraction did not restore exactly')
    record = {'status': 'PASS_NEGATIVE_OMISSION_GUARDS_NO_EVIDENCE_DRIFT', 'cases': cases,
              'all_payload_files_restored_byte_exact': True, 'no_eda_or_remote_access': True}
    args.out.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'status': record['status'], 'cases': len(cases)}))


if __name__ == '__main__':
    main()
