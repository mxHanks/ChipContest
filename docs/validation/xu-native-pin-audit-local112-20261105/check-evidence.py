#!/usr/bin/env python3
"""Verify an offline LOCAL112 archive; optionally rerun its local fixture checks.

No server is contacted. A success here is not a server audit112 completion,
physical-state proof, timing qualification, power qualification or contest score.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
TOOL = 'build/xu-native-pin-audit112/'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON key: ' + str(key))
        result[key] = value
    return result


def load(data):
    return json.loads(data.decode('utf-8'), object_pairs_hook=unique_pairs)


def identity(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay', action='store_true',
                        help='rerun the original 16 local checks in an isolated temporary tree')
    args = parser.parse_args()
    manifest = load((HERE / 'manifest.json').read_bytes())
    need(manifest['schema'] == 'xu-native-pin-audit-local112-offline-v1', 'schema differs')
    need(manifest['qualification'] == 'NOT_QUALIFIED' and
         manifest['status'] == 'LOCAL_LAYOUT_AND_ARTIFICIAL_NEGATIVES_PASS_NOT_SERVER_CAMPAIGN',
         'local evidence scope differs')
    need(manifest['payload_files'] == len(manifest['files']) == 47, 'payload count differs')
    need(manifest['local_check_count'] == len(manifest['local_check_names']) == 16,
         'local check count differs')
    archive_path = HERE / manifest['archive']['file']
    need(archive_path.parent == HERE, 'archive path escapes evidence directory')
    archive_bytes = archive_path.read_bytes()
    need(identity(archive_bytes) == {k: manifest['archive'][k] for k in ('bytes', 'sha256')},
         'archive identity differs')
    payload = {}
    with tarfile.open(str(archive_path), 'r:xz') as source:
        for member in source:
            path = PurePosixPath(member.name)
            need(member.isfile() and not path.is_absolute() and
                 all(part not in ('', '.', '..') for part in path.parts) and
                 member.name not in payload, 'unsafe/duplicate archive member')
            need(member.name in manifest['files'], 'unrecorded archive member')
            data = source.extractfile(member).read()
            need(member.size == len(data), 'archive member size differs')
            need(identity(data) == {k: manifest['files'][member.name][k]
                                    for k in ('bytes', 'sha256')},
                 'payload identity differs: ' + member.name)
            payload[member.name] = data
    need(set(payload) == set(manifest['files']), 'missing archive member')
    need(sum(len(data) for data in payload.values()) == manifest['payload_bytes'],
         'total payload size differs')
    handoff = load(payload[TOOL + 'handoff112.json'])
    need(handoff['status'] == manifest['historical_handoff_status_preserved'] ==
         'READY_FOR_ONE_SERVER_RUN_NOT_EXECUTED', 'historical handoff scope differs')
    for name, receipt in handoff['files'].items():
        need(identity(payload[TOOL + name]) == receipt, 'handoff identity differs: ' + name)
    result = load(payload[TOOL + 'local-check112-v4/results.json'])
    need(result['qualification'] == 'NOT_QUALIFIED' and
         result['status'] == manifest['status'] and
         result['count'] == 16 and result['checks'] == manifest['local_check_names'],
         'original local result differs')
    for name in ('xu_native_pin_audit112.py', 'check_local112.py',
                 'launch_native_pin_audit112.py'):
        text = payload[TOOL + name].decode('utf-8')
        if sys.version_info >= (3, 8):
            ast.parse(text, feature_version=(3, 6))
        else:
            ast.parse(text)
    script_sha = re.search(r"SCRIPT_SHA = '([0-9a-f]{64})'",
                           payload[TOOL + 'launch_native_pin_audit112.py'].decode()).group(1)
    need(script_sha == identity(payload[TOOL + 'xu_native_pin_audit112.py'])['sha256'] ==
         result['audit_tool']['sha256'], 'frozen audit script binding differs')
    need(identity(payload[TOOL + 'check_local112.py'])['sha256'] ==
         result['test_tool']['sha256'], 'frozen check script binding differs')
    replay_status = 'NOT_REQUESTED'
    if args.replay:
        # Only temporary copies are adjusted. The archived scripts and input bytes
        # above remain unchanged. The original JSON stores local absolute paths;
        # its two sample.path values are relocated to the temporary copies.
        with tempfile.TemporaryDirectory(prefix='.local112-replay-', dir=str(HERE)) as name:
            root = Path(name)
            for relative, data in payload.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            sample_file = root / 'build/xu-pt-pin-extract74/sample-audit-93/sample-parsed.json'
            samples = load(sample_file.read_bytes())
            original_root = Path(manifest['original_root'])
            for row in samples:
                relative = Path(row['sample']['path']).relative_to(original_root).as_posix()
                need(relative in payload, 'relocated sample not archived')
                row['sample']['path'] = str(root / relative)
            sample_file.write_text(json.dumps(samples, sort_keys=True, indent=2) + '\n')
            output = root / 'replayed-local-results'
            command = [sys.executable, str(root / (TOOL + 'check_local112.py')),
                       '--output', str(output)]
            process = subprocess.run(command, cwd=str(root), stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, universal_newlines=True,
                                     timeout=120)
            need(process.returncode == 0, 'local replay failed:\n' + process.stdout)
            replayed = load((output / 'results.json').read_bytes())
            need(replayed['checks'] == manifest['local_check_names'] and
                 replayed['count'] == 16 and replayed['qualification'] == 'NOT_QUALIFIED' and
                 replayed['status'] == manifest['status'], 'local replay scope/checks differ')
            need(replayed['audit_tool']['sha256'] == result['audit_tool']['sha256'] and
                 replayed['test_tool']['sha256'] == result['test_tool']['sha256'],
                 'local replay script identity differs')
            replay_status = '16_ORIGINAL_LOCAL_CHECKS_REPLAYED_NOT_SERVER_CAMPAIGN'
    print(json.dumps(dict(status='OFFLINE_LOCAL112_EVIDENCE_PASS',
                          qualification='NOT_QUALIFIED', files=len(payload),
                          payload_bytes=manifest['payload_bytes'], archive=manifest['archive'],
                          local_check_count=16, replay=replay_status,
                          server112_execution='NOT_COVERED_BY_THIS_ARCHIVE'),
                     sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
