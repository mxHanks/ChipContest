#!/usr/bin/env python3
"""Mutate disposable evidence copies and require precise integrity failures."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path)
args = parser.parse_args()
records = []


def change_json(directory, name, modify):
    path = directory / name
    value = json.loads(path.read_text())
    modify(value)
    path.write_text(json.dumps(value) + '\n')


def corrupt_raw(directory):
    row = json.loads((directory / 'selected-manifest.json').read_text())[0]
    path = directory / 'raw' / row['path']
    path.write_bytes(path.read_bytes() + b'\n')


def corrupt_selected(directory):
    change_json(directory, 'selected-manifest.json', lambda rows: rows[0].update(sha256='0' * 64))


def corrupt_source(directory):
    change_json(directory, 'git-source-audit.json',
                lambda audit: audit['source_sha256'].update({next(iter(audit['source_sha256'])): '0' * 64}))


cases = [
    ('changed_raw_bytes', corrupt_raw, 'original raw bytes differ:'),
    ('extra_raw_file', lambda d: (d / 'raw/unexpected-file').write_bytes(b'xu'),
     'extra or missing raw file'),
    ('changed_selected_digest', corrupt_selected, 'selected manifest differs'),
    ('changed_frozen_source_digest', corrupt_source, 'frozen source digest differs'),
    ('duplicate_export_path', lambda d: change_json(d, 'original-export-manifest.json',
                                                 lambda rows: rows.append(rows[0])),
     'original manifest is not unique'),
    ('wrong_candidate_commit', lambda d: change_json(d, 'git-source-audit.json',
                                                   lambda audit: audit.update(main_commit='0' * 40)),
     'frozen commit differs')]

# Keep the temporary directory beneath this archive so the unchanged checker
# still locates the repository's fixed fixture through its normal parent walk.
with tempfile.TemporaryDirectory(prefix='.xu-integrity-negative-', dir=HERE) as temporary:
    for number, (name, modify, expected) in enumerate(cases):
        directory = Path(temporary) / str(number)
        directory.mkdir()
        for item in ['check-evidence.py', 'original-export-manifest.json',
                     'selected-manifest.json', 'git-source-audit.json', 'frozen-git-sources.tar.xz']:
            shutil.copyfile(HERE / item, directory / item)
        shutil.copytree(HERE / 'raw', directory / 'raw')
        modify(directory)
        result = subprocess.run([sys.executable, str(directory / 'check-evidence.py')],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode == 0 or expected not in result.stdout:
            raise ValueError('corruption not rejected for its intended reason: ' + name + '\n' + result.stdout)
        records.append(dict(case=name, returncode=result.returncode,
                            expected_rejection=expected, actual_rejection=result.stdout.splitlines()[-1]))
report = dict(status='PASS', mutated_copies_only=True, unchanged_raw=True,
              integrity_corruptions_rejected=len(records), cases=records)
if args.out:
    args.out.write_text(json.dumps(report, indent=2) + '\n')
print('PASS: ' + str(len(records)) + ' independent archive-integrity corruptions rejected; original bytes unchanged')
