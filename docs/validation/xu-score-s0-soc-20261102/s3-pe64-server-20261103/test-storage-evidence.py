#!/usr/bin/env python3
"""xu: actual archive byte/path corruption tests; preserve every original byte."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

H = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('xu_pe64_check', H / 'check-evidence.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def main():
    rejected = []

    def reject(label, root, reason):
        try:
            check.audit(root)
        except ValueError as error:
            assert reason in str(error), (label, str(error))
            rejected.append(label)
        else:
            raise AssertionError('corrupt evidence accepted: ' + label)

    selected = check.read(H / 'selected-manifest.json')
    with tempfile.TemporaryDirectory(prefix='xu-pe64-storage-') as directory:
        root = Path(directory) / 'copy'
        shutil.copytree(H, root, ignore=shutil.ignore_patterns('__pycache__'))
        for entry in selected:
            path = root / 'raw' / entry['path']
            original = path.read_bytes()
            path.write_bytes(original + b'\n')
            reject('payload_bytes/' + entry['path'], root, 'raw bytes differ')
            path.write_bytes(original)
        manifest = root / 'selected-manifest.json'
        original = manifest.read_bytes()
        manifest.write_text(json.dumps(selected + [selected[0]]))
        reject('duplicate_selection', root, 'raw uniqueness/count differs')
        manifest.write_bytes(original)
        path = root / 'raw' / selected[0]['path']
        original = path.read_bytes()
        path.unlink()
        path.symlink_to(H / 'raw' / selected[0]['path'])
        reject('symlink_payload', root, 'raw bytes differ')
        path.unlink()
        path.write_bytes(original)
        path = root / 'raw/unlisted.log'
        path.write_text('unlisted')
        reject('unlisted_payload', root, 'extra/missing raw')
        path.unlink()
        source = root / 'git-source-audit.json'
        original = source.read_bytes()
        j = json.loads(original)
        j['source_sha256'][next(iter(j['source_sha256']))] = '0' * 64
        source.write_text(json.dumps(j))
        reject('wrong_frozen_source_hash', root, 'frozen source bytes differ')
        source.write_bytes(original)
    print(json.dumps(dict(status='PASS', rejected=len(rejected), cases=rejected), indent=2))


if __name__ == '__main__':
    main()
