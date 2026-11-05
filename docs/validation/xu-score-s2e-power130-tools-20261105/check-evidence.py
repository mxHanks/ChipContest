#!/usr/bin/env python3
"""Verify frozen130 tools/43 host checks and original131 live snapshot only."""
import argparse
import ast
import difflib
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
DRIVER = '95caa5fab255c5126e5b51f6f0b06c9bf63283f9bbf89dd310202abc87515d46'
LAUNCHER = '82ed8f7db2bf88643d320ea9016b0435c2c6dc11363825d5a024efb4c2f2a3b2'
ARCHIVE = '86bd9a31a747d5b77a301816cbda48e695aa7448dd02b515d5ad18124b49ff1b'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def payload():
    manifest = json.loads((HERE / 'payload-manifest.json').read_text())
    data = (HERE / 'payload.tar.xz').read_bytes()
    need(sha(data) == ARCHIVE == manifest['archive']['sha256'] and len(data) == manifest['archive']['bytes'], 'payload archive differs')
    expected = {row['path']:row for row in manifest['files']}
    need(len(expected) == len(manifest['files']) == manifest['payload_files'] == 14, 'complete payload member count differs')
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:xz') as tar:
        for member in tar:
            name = member.name
            need(member.isfile() and not Path(name).is_absolute() and '..' not in Path(name).parts and name in expected and name not in files,
                 'unsafe/unexpected/duplicate member')
            body = tar.extractfile(member).read()
            need(sha(body) == expected[name]['sha256'] and len(body) == expected[name]['bytes'], 'member differs: ' + name)
            files[name] = body
    need(set(files) == set(expected) and sum(map(len, files.values())) == manifest['payload_bytes'], 'payload incomplete')
    return files


def constants(source):
    values = {}
    for node in ast.parse(source, feature_version=(3, 6)).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('CAPTURE_COMMIT','MAIN','NETLIST','SDC','LIBRARIES','FROZEN','PRODUCER_SHA'):
                    values[target.id] = ast.literal_eval(node.value)
    return values


def verify(files):
    need(sha(files['delivery/xu_s2e_full_soc_power130.py']) == DRIVER and
         sha(files['delivery/launch_s2e_power130.py']) == LAUNCHER and
         files['server131/xu_s2e_full_soc_power130.py'] == files['delivery/xu_s2e_full_soc_power130.py'], 'frozen local/remote producer or launcher differs')
    handoff = json.loads(files['delivery/handoff130-manifest.json'])
    for name, row in handoff['files'].items():
        need(len(files['delivery/'+name]) == row['bytes'] and sha(files['delivery/'+name]) == row['sha256'], 'handoff identity differs')
    for name, body in files.items():
        if name.endswith('.py'):
            ast.parse(body.decode(), feature_version=(3,6))
    need(constants(files['delivery/launch_s2e_power130.py'].decode())['PRODUCER_SHA'] == DRIVER, 'launcher producer pin differs')
    host = json.loads(files['delivery/host-check130.json'])
    need(host['total'] == len(host['checks']) == 43 and host['producer']['sha256'] == DRIVER and
         all(row['status'] == 'PASS' for row in host['checks']) and
         files['delivery/host-check130.log'].decode().splitlines() == ['PASS '+row['name'] for row in host['checks']], 'focused43 host receipt/log differs')
    names = [row['name'] for row in host['checks']]
    need(sum(name.startswith('actual120 task') and 'raw and normalized receipt shapes' in name for name in names) == 12 and
         sum(name.startswith('reject Tcl ') or name.startswith('reject invented zero switching') for name in names) == 3,
         'full12 receipt-shape or coordinated Tcl/hash negative coverage missing')
    launch = json.loads(files['server131/launch-state.json'])
    lines = files['server131/driver.log'].decode().splitlines()
    header = json.loads(lines[0])
    need(launch['pid'] == 135097 and launch['status'] == 'STARTED_NOT_QUALIFIED' and launch['qualification'] == 'NOT_QUALIFIED' and
         launch['producer_sha256'] == header['producer_sha256'] == DRIVER and launch['command'] == header['command'], 'actual launch/log differs')
    replay = [re.fullmatch(r'REPLAYED_S2E130_ACTIVITY task=(\d+) elapsed=868343 unknown_bit_ticks=26076600970238528 NOT_QUALIFIED',line)for line in lines[1:]]
    need(len(replay) == 3 and all(replay) and [int(row.group(1)) for row in replay] == [0,1,2], 'actual131 raw-replay snapshot differs')
    observation = json.loads(files['server131/source131-live-observation.json'])
    rows = [row for row in observation['observed'] if row['prefix'] == 's2e-full-soc-power-launch-20261105-130']
    need(len(rows) == 1 and rows[0]['pid'] == 135097 and rows[0]['pid_alive_now'] is True and
         rows[0]['command'].startswith('/bin/python3 -u '+launch['frozen_producer']+' campaign '), 'actual131 matching live process observation differs')
    source = json.loads(files['server131/source131-manifest.json'])
    for name in ('driver.log','launch-state.json','xu_s2e_full_soc_power130.py'):
        candidates = [row for row in source if row['path'] == 's2e-full-soc-power-launch-20261105-130/'+name]
        need(len(candidates) == 1 and len(files['server131/'+name]) == candidates[0]['bytes'] and
             sha(files['server131/'+name]) == candidates[0]['sha256'], 'source131 original identity differs')
    # Check fixed commits/library/common hashes against actual frozen124 bytes;
    # only the separately reviewed coordinator and schema changed in130.
    old_archive = HERE.parent / 'xu-score-s2e-power124-tools-20261105/payload.tar.xz'
    need(sha(old_archive.read_bytes()) == 'c4f7186a2cbdc7bbfd16d9af9ee7fb23621901a05193d1c55261f5b3db2de339', 'original124 shared archive differs')
    with tarfile.open(old_archive) as tar:
        old = tar.extractfile('delivery/xu_s2e_full_soc_power124.py').read().decode()
    new = files['delivery/xu_s2e_full_soc_power130.py'].decode()
    need(constants(old) == constants(new), 'fixed source/netlist/SDC/library/common hash constants changed')
    difference = ''.join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),
        fromfile='frozen124/xu_s2e_full_soc_power124.py',tofile='frozen130/xu_s2e_full_soc_power130.py'))
    need(difference.encode() == files['review/124-to-130.diff'], 'reviewed coordinator diff differs')


def extract(files, destination):
    need(not destination.exists(), 'fresh extraction directory required')
    destination.mkdir(parents=True)
    for name, body in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)


def rerun_host(files, workspace, frozen_tools):
    need((workspace / 'build/xu-score-resume-20261103/activity125').is_dir(), 'actual125 local activity bodies required')
    with tempfile.TemporaryDirectory(prefix='xu-power130-replay-') as temporary:
        base = Path(temporary)
        tools = base / 'build/xu-s2e-power130'
        tools.mkdir(parents=True)
        for name in ('xu_s2e_full_soc_power130.py','check_power130.py'):
            (tools/name).write_bytes(files['delivery/'+name])
        (base / 'build/xu-score-resume-20261103').symlink_to(workspace / 'build/xu-score-resume-20261103',target_is_directory=True)
        subprocess.run([sys.executable,str(tools/'check_power130.py'),'--frozen-tools',str(frozen_tools),'--out',str(base/'result.json')],check=True)
        result = json.loads((base/'result.json').read_text())
        need(result['total'] == 43 and all(row['status']=='PASS'for row in result['checks']), '43 scoped host checks did not pass')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract',type=Path)
    parser.add_argument('--rerun-host',action='store_true')
    parser.add_argument('--workspace-root',type=Path,default=HERE.parents[2])
    parser.add_argument('--frozen-tools',type=Path)
    args = parser.parse_args()
    files = payload()
    verify(files)
    if args.extract:
        extract(files,args.extract.resolve())
    if args.rerun_host:
        need(args.frozen_tools is not None, 'explicit clean original109 --frozen-tools required')
        rerun_host(files,args.workspace_root.resolve(),args.frozen_tools.resolve())
    print('PASS: frozen13014 payloads,43 scoped host checks and original131 live/preparing snapshot; NOT_QUALIFIED; no terminal PT/energy claim')


if __name__ == '__main__':
    try:
        main()
    except (ValueError,OSError,KeyError) as error:
        print('FAIL: '+str(error),file=sys.stderr)
        sys.exit(1)
