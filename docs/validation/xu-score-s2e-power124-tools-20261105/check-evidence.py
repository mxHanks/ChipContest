#!/usr/bin/env python3
"""Verify frozen124 tools and original early failure; no EDA/energy claim."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
DRIVER = '2349b11ec32e63c71ff70497c8d6d124ec99024bec73b75239944993bd58bc58'
LAUNCHER = '282b56f60cbbca2e1b94578b664f9245e73af7feb4e25e287460095edff81f20'
ARCHIVE = 'c4f7186a2cbdc7bbfd16d9af9ee7fb23621901a05193d1c55261f5b3db2de339'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify():
    manifest = json.loads((HERE / 'payload-manifest.json').read_text())
    body = (HERE / 'payload.tar.xz').read_bytes()
    need(digest(body) == ARCHIVE == manifest['archive']['sha256'] and len(body) == manifest['archive']['bytes'], 'archive identity differs')
    expected = {row['path']: row for row in manifest['files']}
    need(len(expected) == manifest['payload_files'] == len(manifest['files']) == 17, 'complete manifest file set differs')
    files = {}
    with tarfile.open(fileobj=io.BytesIO(body), mode='r:xz') as tar:
        for member in tar:
            path = Path(member.name)
            need(member.isfile() and not path.is_absolute() and '..' not in path.parts and
                 member.name in expected and member.name not in files, 'unsafe/duplicate/unexpected archive member')
            data = tar.extractfile(member).read()
            row = expected[member.name]
            need(len(data) == row['bytes'] and digest(data) == row['sha256'], 'member identity differs: ' + member.name)
            files[member.name] = data
    need(set(files) == set(expected) and sum(len(v) for v in files.values()) == manifest['payload_bytes'], 'missing payload/body count differs')
    need(digest(files['delivery/xu_s2e_full_soc_power124.py']) == DRIVER and
         files['server124/xu_s2e_full_soc_power124.py'] == files['delivery/xu_s2e_full_soc_power124.py'] and
         digest(files['delivery/launch_s2e_power124.py']) == LAUNCHER, 'frozen tools/server executed copy differ')
    for name, data in files.items():
        if name.endswith('.py'):
            ast.parse(data.decode(), feature_version=(3, 6))
    handoff = json.loads(files['delivery/handoff124-manifest.json'])
    for name, row in handoff['files'].items():
        data = files['delivery/' + name]
        need(digest(data) == row['sha256'] and len(data) == row['bytes'], 'original handoff file differs')
    host = json.loads(files['delivery/host-check124.json'])
    need(host['producer']['sha256'] == DRIVER and host['total'] == len(host['checks']) == 23 and
         all(row['status'] == 'PASS' for row in host['checks']) and
         files['delivery/host-check124.log'].decode().splitlines() == ['PASS ' + row['name'] for row in host['checks']],
         'host receipt/log differ')
    native = files['server124/driver.log'].decode().splitlines()
    need(native[-1] == 'FAIL: ValueError: normalization raw/output identity differs' and len(native) == 2, 'original early failure log differs')
    header = json.loads(native[0])
    launch = json.loads(files['server124/launch-state.json'])
    need(launch['pid'] == 133531 and launch['status'] == 'STARTED_NOT_QUALIFIED' and
         launch['producer_sha256'] == header['producer_sha256'] == DRIVER and
         launch['command'] == header['command'] and launch['qualification'] == 'NOT_QUALIFIED', 'original launch/log producer/command differs')
    observation = json.loads(files['server124/source129-live-observation.json'])
    found = [row for row in observation['observed'] if row['prefix'] == 's2e-full-soc-power-launch-20261105-124']
    need(len(found) == 1 and found[0]['pid'] == 133531 and found[0]['pid_alive_now'] is False and found[0]['command'] == '',
         'actual129 original process observation differs')
    source129 = json.loads(files['server124/source129-manifest.json'])
    for name in ('driver.log', 'launch-state.json', 'xu_s2e_full_soc_power124.py'):
        original_name = 's2e-full-soc-power-launch-20261105-124/' + name
        rows = [row for row in source129 if row['path'] == original_name]
        data = files['server124/' + name]
        need(len(rows) == 1 and rows[0]['bytes'] == len(data) and rows[0]['sha256'] == digest(data), 'source129 original identity differs')
    task = json.loads(files['actual120/task00-result.json'])
    raw, normalized_raw = task['raw_saif'], task['normalization']['raw_saif']
    need(set(raw) == {'path', 'sha256'} and set(normalized_raw) == {'path', 'sha256', 'bytes'} and
         raw['path'] == normalized_raw['path'] and raw['sha256'] == normalized_raw['sha256'] and
         normalized_raw['bytes'] == 25568880 and raw != normalized_raw, 'actual120 receipt-shape cause differs')
    review = json.loads(files['independent/review.json'])
    need(review['qualification'] == 'NOT_QUALIFIED' and review['producer_sha256'] == DRIVER and
         review['status'] == 'TOOLS_ARCHIVED_ACTUAL_EARLY_FAILURE_NOT_PPA_OR_ENERGY_QUALIFIED', 'review scope/status differs')
    return files


def extract(files, destination):
    need(not destination.exists(), 'fresh extraction directory required')
    destination.mkdir(parents=True)
    for name, data in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def rerun_host(files, workspace, frozen_tools):
    # Recreate the original relative host-check layout in a fresh temporary
    # directory. Only the fixture directory is linked; no frozen source/tool
    # guard is patched. The original readonly input checkout remains external.
    need((workspace / 'build/xu-score-resume-20261103/activity125').is_dir(), 'actual120 local fixtures are required')
    with tempfile.TemporaryDirectory(prefix='xu-power124-replay-') as temporary:
        base = Path(temporary)
        tools = base / 'build/xu-s2e-power124'
        tools.mkdir(parents=True)
        for name in ('xu_s2e_full_soc_power124.py', 'check_power124.py'):
            (tools / name).write_bytes(files['delivery/' + name])
        (base / 'build/xu-score-resume-20261103').symlink_to(workspace / 'build/xu-score-resume-20261103', target_is_directory=True)
        command = [sys.executable, str(tools / 'check_power124.py'), '--frozen-tools', str(frozen_tools), '--out', str(base / 'rerun.json')]
        subprocess.run(command, check=True)
        receipt = json.loads((base / 'rerun.json').read_text())
        need(receipt['total'] == 23 and all(row['status'] == 'PASS' for row in receipt['checks']), 'host replay did not pass23 scoped checks')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', type=Path)
    parser.add_argument('--rerun-host', action='store_true')
    parser.add_argument('--workspace-root', type=Path, default=HERE.parents[2])
    parser.add_argument('--frozen-tools', type=Path)
    args = parser.parse_args()
    files = verify()
    if args.extract:
        extract(files, args.extract.resolve())
    if args.rerun_host:
        need(args.frozen_tools is not None, 'explicit clean original109 --frozen-tools required')
        rerun_host(files, args.workspace_root.resolve(), args.frozen_tools.resolve())
    print('PASS: frozen12417 payloads,23 prior scoped host checks and original early-failure chain; NOT_QUALIFIED; no PT/energy claim')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        sys.exit(1)
