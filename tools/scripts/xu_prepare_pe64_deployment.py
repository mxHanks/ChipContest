#!/usr/bin/env python3
"""Build a credential-free, byte/mode-frozen xu64 incremental server package."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

MAIN_BASE = '94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114'
CHILD_BASE = 'fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()


def require(value, message):
    if not value:
        raise ValueError(message)


def snapshot(repo):
    records = []
    for entry in subprocess.check_output(['git', 'ls-files', '-s', '-z'], cwd=repo).split(b'\0'):
        if not entry:
            continue
        meta, name = entry.split(b'\t', 1)
        mode, oid, stage = meta.decode().split()
        require(stage == '0', 'unmerged source')
        path = repo / os.fsdecode(name)
        record = dict(path=os.fsdecode(name), mode=mode, git_oid=oid)
        if mode != '160000':
            data = os.readlink(path).encode() if mode == '120000' else path.read_bytes()
            record.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        records.append(record)
    return dict(commit=git(repo, 'rev-parse', 'HEAD'), files=records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--out', required=True, type=Path, help='new package directory')
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    child = root / 'third-party/e203_hbirdv2'
    for repo in (root, child):
        require(not git(repo, 'status', '--porcelain'), 'clean committed checkout required: ' + str(repo))
    require(git(root, 'branch', '--show-current') == 'codex/xu-s3-pe64', 'independent64 branch required')
    require(git(root, 'ls-tree', 'HEAD', 'third-party/e203_hbirdv2').split()[2] == git(child, 'rev-parse', 'HEAD'), 'gitlink differs')
    out.mkdir(parents=True, exist_ok=False)
    frozen = {label: snapshot(repo) for label, repo in [('main', root), ('child', child)]}
    identity = dict(schema='xu-s3-pe64-deployment-v2', main_commit=frozen['main']['commit'],
                    e203_commit=frozen['child']['commit'], branch='codex/xu-s3-pe64',
                    main_base=MAIN_BASE, child_base=CHILD_BASE, qualification='NOT_QUALIFIED',
                    expected_full_soc_macros=384, logical_w_bytes=32768, physical_w_bytes=131072, padding_bytes=98304)
    (out / 'source-files.json').write_text(json.dumps(frozen, indent=2, sort_keys=True) + '\n')
    (out / 'source-identity.json').write_text(json.dumps(identity, indent=2, sort_keys=True) + '\n')
    shutil.copyfile(root / 'tools/scripts/xu_s3_pe64_server.py', out / 'launch.py')
    for label, repo, base in [('main', root, MAIN_BASE), ('child', child, CHILD_BASE)]:
        bundle = out / (label + '.bundle')
        subprocess.run(['git', 'merge-base', '--is-ancestor', base, 'HEAD'], cwd=repo, check=True)
        subprocess.run(['git', 'bundle', 'create', str(bundle), 'HEAD', '^' + base], cwd=repo, check=True)
        subprocess.run(['git', 'bundle', 'verify', str(bundle)], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    (out / 'README.md').write_text('''# xu independent64 VCS deployment

Requires the recorded32PE base commits available in the previous-source repository and child. This package contains no credentials. Extract into a new directory, verify its archive identity, and run:

```sh
python3 launch.py --source /absolute/new/ChipContest-s3-pe64-01 --out /absolute/new/s3-pe64-accept-01 --previous-source /absolute/server/ChipContest-s3-pe32-01
```

The default cross prefix is the previously measured server SiFive10.2 toolchain. Source, output and deployment directories must be new. The launcher checks exact GCC/VCS versions, full tracked file bytes and modes before/after, mandatory physical64 direct64/32/8 and boundary VCS, stock host/numeric/vector/doctor/legacy5/synthetic1/synthetic2/wide64-real12, plus four complete12 physical/schedule controls. Retention, full150MHz, mapping and fullSoC energy remain separate gates. Do not overwrite any32/default source or old raw capture.

For a local checkout-only validation use --prepare-only. That does not execute any EDA or establish server acceptance. Each invocation needs new source/output paths.
''')
    manifest = {p.name: dict(bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(out.iterdir()) if p.is_file()}
    (out / 'package-files.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    archive = out.with_suffix('.tar.xz')
    require(not archive.exists(), 'archive path must be new')
    with tarfile.open(archive, 'w:xz') as tar:
        for path in sorted(out.iterdir()):
            tar.add(path, arcname=path.name, recursive=False)
    receipt = dict(schema='xu-s3-pe64-package-receipt-v2', path=str(archive), bytes=archive.stat().st_size,
                   sha256=sha(archive), identity=identity, source_files=sum(len(value['files']) for value in frozen.values()),
                   package_payloads=len(manifest), qualified=False)
    out.with_suffix('.receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
