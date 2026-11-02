#!/usr/bin/env python3
"""Package preserved local outputs without re-running tests or copying caches/vectors."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile

sys.dont_write_bytecode = True
from xu_verify_local_evidence import CASES, checked_archive, require, sha256, verify_runtime_sources


ARCHIVES = {'xu-hw-local-evidence.tar.xz': 'baa54cb77e0b038d824a51c97f3f7227b56281a77445a9d8ad08209807e458ab',
            'xu-hw-extra-interface.tar.xz': 'a14d84c035d33b6e9d07afbae2e9ce3917544994583d9785c1d2814291490522'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--out', required=True, help='existing evidence directory containing evidence-tools')
    parser.add_argument('--runs', required=True, help='original local serial output directory')
    parser.add_argument('--stdout', required=True)
    parser.add_argument('--host-log', required=True)
    parser.add_argument('--numeric-log', required=True)
    parser.add_argument('--original-script', required=True)
    parser.add_argument('--chisel-archive', required=True)
    parser.add_argument('--interface-archive', required=True)
    args = parser.parse_args()
    repo, out, runs = Path(args.repo).resolve(), Path(args.out).resolve(), Path(args.runs).resolve()
    snapshot = json.loads((out/'evidence-tools/runtime-source-97b3542.json').read_text())
    verify_runtime_sources(repo, snapshot)
    artifacts = out/'local-artifacts'
    artifacts.mkdir(exist_ok=True)
    sources = {'xu-hw-local-evidence.tar.xz': Path(args.chisel_archive),
               'xu-hw-extra-interface.tar.xz': Path(args.interface_archive)}
    for filename, source in sources.items():
        require(sha256(source) == ARCHIVES[filename], 'previous archive identity differs: '+filename)
        shutil.copyfile(str(source), str(artifacts/filename))
    with tempfile.TemporaryDirectory(prefix='xu-package-local-') as temporary:
        staging = Path(temporary)
        for filename in ARCHIVES:
            checked_archive(artifacts/filename, staging, filename[:-7])
        chisel = staging/'xu-hw-local-evidence'
        for filename in ['xu-local-evidence-summary.json', 'xu-local-evidence-summary.md',
                         'xu-chisel-observation-receipt.json']:
            shutil.copyfile(str(chisel/filename), str(out/filename))
        raw = staging/'xu-hw-local-screening'
        raw.mkdir()
        def copy(source, relative):
            destination = raw/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(source), str(destination))
        copy(runs/'local-check.json', 'local-check.json')
        for path, name in [(args.stdout, 'local-check-stdout.log'), (args.host_log, 'host-tests.log'),
                           (args.numeric_log, 'numeric-tests.log'), (args.original_script, 'original-local-check.py')]:
            copy(Path(path), name)
        for label, schedule, mode, tasks in CASES:
            copy(runs/(label+'.log'), label+'.log')
            for path in sorted((runs/label).iterdir()):
                if path.is_file() and (path.name == 'accel_soc' or path.suffix in ['.json', '.log', '.dump', '.su'] or
                                       path.name == 'accel_soc.verilog'):
                    copy(path, Path(label)/path.name)
        references = dict(evidence_kind='derived source/vector reference manifest; vectors not duplicated in this archive',
                          frozen_runtime_commit=snapshot['commit'], e203_commit=snapshot['e203_commit'],
                          source_sha256=snapshot['source_sha256'],
                          real_archive_repository_path='tests/e203/vectors/kwt-silence-v1.tar.gz',
                          real_archive_sha256=sha256(repo/'tests/e203/vectors/kwt-silence-v1.tar.gz'),
                          real_archive_member_sha256={}, run_vector_sha256={})
        with tarfile.open(str(repo/references['real_archive_repository_path']), 'r:gz') as stream:
            for member in stream.getmembers():
                require(member.isfile() and member.name not in references['real_archive_member_sha256'],
                        'unexpected real vector archive entry')
                references['real_archive_member_sha256'][member.name] = hashlib.sha256(stream.extractfile(member).read()).hexdigest()
        for label, schedule, mode, tasks in CASES:
            result = json.loads((runs/label/'result.json').read_text())
            references['run_vector_sha256'][label] = result['vectors']
        (raw/'source-vector-references.json').write_text(json.dumps(references, indent=2)+'\n')
        paths = sorted(path for path in raw.rglob('*') if path.is_file())
        (raw/'SHA256SUMS').write_text(''.join(sha256(path)+'  '+path.relative_to(raw).as_posix()+'\n' for path in paths))
        with tarfile.open(str(artifacts/'xu-hw-local-screening.tar.xz'), 'w:xz', preset=9) as stream:
            for path in sorted(path for path in raw.rglob('*') if path.is_file()):
                info = stream.gettarinfo(str(path), arcname=path.relative_to(staging).as_posix())
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ''
                info.mode = 0o644
                with path.open('rb') as contents:
                    stream.addfile(info, contents)
    manifest = {path.name: dict(sha256=sha256(path), bytes=path.stat().st_size)
                for path in sorted(artifacts.glob('*.tar.xz'))}
    (artifacts/'archives-sha256.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
