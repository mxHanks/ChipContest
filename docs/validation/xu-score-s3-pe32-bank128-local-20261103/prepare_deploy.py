#!/usr/bin/env python3
"""Create xu's protected-data-free incremental bank128 server handoff from a clean commit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile


def git(arguments, directory):
    return subprocess.check_output(['git'] + arguments, cwd=str(directory), text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    child = root / 'third-party/e203_hbirdv2'
    if git(['status', '--porcelain'], root) or git(['status', '--porcelain'], child):
        raise ValueError('both repositories must be clean, including untracked files')
    identity = dict(main_commit=git(['rev-parse', 'HEAD'], root), e203_commit=git(['rev-parse', 'HEAD'], child),
                    branch=git(['branch', '--show-current'], root),
                    main_prerequisite=git(['rev-parse', '94ce6f0'], root),
                    child_prerequisite=git(['rev-parse', 'fc3977d'], child))
    if identity['e203_commit'] != '52cfbea1f79f10e44f7d1696f54015797f886b96' or not identity['branch'].startswith('codex/xu-'):
        raise ValueError('unexpected candidate/branch identity')
    if git(['ls-tree', 'HEAD', 'third-party/e203_hbirdv2'], root).split()[2] != identity['e203_commit']:
        raise ValueError('gitlink differs')
    if git(['branch', '--show-current'], child) != identity['branch']:
        raise ValueError('main and child branch names must match this bundle handoff')
    archive = out.with_name(out.name + '.tar.gz')
    receipt = out.with_name(out.name + '-receipt.json')
    if out.exists() or archive.exists() or receipt.exists():
        raise ValueError('handoff paths must be new')
    out.mkdir(parents=True)
    for directory, suffix, prerequisite in [(root, 'main', identity['main_prerequisite']),
                                            (child, 'child', identity['child_prerequisite'])]:
        subprocess.run(['git', 'bundle', 'create', str(out / ('xu-bank128-' + suffix + '.bundle')),
                        identity['branch'], '^' + prerequisite], cwd=str(directory), check=True)
    source_files = {}
    for directory, prefix in [(root, ''), (child, 'third-party/e203_hbirdv2/')]:
        for line in git(['ls-files', '-s'], directory).splitlines():
            metadata, name = line.split('\t')
            mode = metadata.split()[0]
            if mode == '160000':
                continue
            path = directory / name
            record = dict(git_mode=mode)
            if mode == '120000':
                if not path.is_symlink():
                    raise ValueError('tracked symlink changed')
                record['link_target'] = os.readlink(path)
                data = record['link_target'].encode()
            else:
                if not path.is_file() or path.is_symlink():
                    raise ValueError('tracked source must be regular')
                data = path.read_bytes()
            expected = subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=str(directory))
            if data != expected:
                raise ValueError('source differs from committed blob: ' + prefix + name)
            record.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            source_files[prefix + name] = record
    (out / 'source-files.json').write_text(json.dumps(source_files, indent=2, sort_keys=True) + '\n')
    identity.update(source_files=len(source_files), logical_w_bytes=32768, physical_w_bytes=32768,
                    expected_full_soc_macros={'RAMSP128X16':128, 'RAMSP1024X16':320})
    (out / 'source-identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    shutil.copyfile(Path(__file__).with_name('server_launch.py'), out / 'launch.py')
    (out / 'README.md').write_text('''# xu compact128 W32 server handoff

Incremental prerequisites: original32 main94ce6f0 and childfc3977d objects, present in a clean original32 checkout.
No credential or vendor model body is included. All tracked source bytes/modes/link targets are frozen.
The launch requires a new source and output directory, actual regular RAMSP128X16.v, same SiFive GCC10.2/VCS2020.03.
It first runs mandatory VCS generated/designated single-bank and wide/compat checks, then eight-step development
acceptance and two full12 controls: original32 same wide and compact128 old auto. Actual model SHA is frozen before/after.
WholeSoC development cycles still use generated memories; do not label them a wholeSoC macro or timing qualification.

```bash
python3 launch.py --previous-source /absolute/ChipContest-s3-pe32-01 \\
  --source /absolute/new/ChipContest-pe32-bank128-01 --out /absolute/new/bank128-accept-01 \\
  --ramsp128-model /absolute/actual/RAMSP128X16.v \\
  --cross-prefix /absolute/sifive-rv32-c/bin/riscv64-unknown-elf-
```

`--prepare-only` checks actual clone, bundle prerequisites, commits, gitlink, complete tracked file set,
bytes/modes/link targets and clean state; it does not run or qualify EDA or the supplied model path.
No candidate retention, area, 150MHz, mapped-equivalence or fullSoC-energy claim is made by this package.
''')
    package_files = {p.name:dict(bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(out.iterdir()) if p.is_file()}
    (out / 'package-files.json').write_text(json.dumps(package_files, indent=2, sort_keys=True) + '\n')
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(out, arcname=out.name)
    result = dict(status='PREPARED_NOT_EXECUTED', archive=str(archive), archive_bytes=archive.stat().st_size,
                  archive_sha256=sha(archive), identity=identity, package_files=package_files)
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key:result[key] for key in ('status','archive','archive_bytes','archive_sha256')}))


if __name__ == '__main__':
    main()
