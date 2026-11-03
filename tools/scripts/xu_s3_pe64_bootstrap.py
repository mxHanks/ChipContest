#!/usr/bin/env python3
"""Verify one xu64 package and start a fresh detached server VCS campaign."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--bytes', type=int, required=True)
    parser.add_argument('--base', type=Path, default=Path.home() / 'Desktop/xu-score-optimization-20261102')
    parser.add_argument('--previous-source', type=Path)
    parser.add_argument('--cross-prefix')
    args = parser.parse_args()
    archive, base = args.archive.resolve(), args.base.resolve()
    require(re.fullmatch('[0-9a-f]{64}', args.sha256) is not None, 'invalid expected SHA256')
    require(args.bytes > 0 and archive.stat().st_size == args.bytes and sha(archive) == args.sha256, 'archive identity differs')
    deployment = base / 's3-pe64-deploy-20261103-02'
    source, out = base / 'ChipContest-s3-pe64-02', base / 's3-pe64-accept-02'
    require(not deployment.exists() and not source.exists() and not out.exists(), 'fresh deployment/source/output directories required')
    allowed = {'launch.py', 'main.bundle', 'child.bundle', 'source-files.json', 'source-identity.json', 'package-files.json', 'README.md'}
    with tarfile.open(str(archive), 'r:xz') as tar:
        members = tar.getmembers()
        require(len(members) == len(allowed) and {member.name for member in members} == allowed, 'package member inventory differs')
        require(all(member.isfile() and member.size < 20000000 for member in members), 'package links/devices/oversized member rejected')
        deployment.mkdir(parents=True, exist_ok=False)
        for member in members:
            with tar.extractfile(member) as stream:
                (deployment / member.name).write_bytes(stream.read())
    manifest = json.loads((deployment / 'package-files.json').read_text())
    require(set(manifest) == allowed - {'package-files.json'}, 'package SHA inventory differs')
    for name, record in manifest.items():
        path = deployment / name
        require(path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], 'package payload differs: ' + name)
    command = [sys.executable, str(deployment / 'launch.py'), '--source', str(source), '--out', str(out)]
    if args.previous_source:
        command += ['--previous-source', str(args.previous_source.resolve())]
    if args.cross_prefix:
        command += ['--cross-prefix', args.cross_prefix]
    log = deployment / 'driver.log'
    with log.open('wb') as stream:
        process = subprocess.Popen(command, cwd=str(deployment), env=dict(os.environ, PWD=str(deployment)),
                                   stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    record = dict(status='LAUNCHED_NOT_QUALIFIED', pid=process.pid, argv=command,
                  archive_sha256=args.sha256, archive_bytes=args.bytes, helper_sha256=sha(Path(__file__)),
                  source=str(source), out=str(out), log=str(log), identity=json.loads((deployment / 'source-identity.json').read_text()))
    (deployment / 'boot.json').write_text(json.dumps(record, indent=2) + '\n')
    print('XU_S3_PE64_BOOT ' + json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
