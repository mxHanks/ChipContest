#!/usr/bin/env python3
"""Restore only the exact frozen bias-pipeline patch; dry run unless --apply."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

here = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
root = args.repo.resolve()
manifest = json.loads((here.parent / 'bias8-logs/source-hashes.json').read_text())
originals = json.loads((here / 'original-hashes.json').read_text())
for name, expected in originals.items():
    source = here / 'before' / name
    if not source.is_file() or source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        raise SystemExit('Refusing rollback: packaged original SHA differs: ' + name)
# Check ALL destinations before any mutation. Refuse to remove an edited test.
for name, expected in manifest.items():
    path = root / name
    if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit('Refusing rollback: destination no longer matches frozen pipeline file: ' + name)
for name in manifest:
    source, destination = here / 'before' / name, root / name
    action = 'restore original' if source.is_file() else 'remove added test'
    print(action + ': ' + str(destination))
    if args.apply:
        if source.is_file():
            shutil.copyfile(source, destination)
        else:
            destination.unlink()
print('Rollback applied.' if args.apply else 'Dry run only; append --apply to restore these four exact files.')
