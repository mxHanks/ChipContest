#!/usr/bin/env python3
"""Verify original local116 bytes; optionally replay its original 14 host checks.

No server or native EDA tool is contacted. PASS is not server116 completion,
timing/electrical qualification, S2e validation, or a contest score.
"""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
TOOL = 'build/xu-timing-combined116/'
FINAL = TOOL + 'local-check116-final/'
ARCHIVE_SHA = '1afaa781fa6899b4aa7a988184c6e4bf780bb8c3330ebf2d267a0bc754cce7a2'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    value = {}
    for key, item in pairs:
        need(key not in value, 'duplicate JSON key: ' + str(key))
        value[key] = item
    return value


def load(data):
    return json.loads(data.decode('utf-8'), object_pairs_hook=unique)


def identity(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def expected(record):
    return {key: record[key] for key in ('bytes', 'sha256')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay', action='store_true',
                        help='run unchanged original14 host checks in an isolated temporary tree')
    args = parser.parse_args()
    manifest = load((HERE / 'manifest.json').read_bytes())
    need(manifest['schema'] == 'xu-score-timing116-local-offline-v1' and
         manifest['status'] == 'LOCAL116_PREPARATION_AND_14_CHECKS_ONLY_NOT_SERVER_EXECUTION' and
         manifest['qualification'] == 'NOT_QUALIFIED', 'archive scope differs')
    need(manifest['payload_files'] == len(manifest['files']) == 78, 'payload count differs')
    need(manifest['payload_bytes'] == 24908686, 'payload total differs')
    need(manifest['local_check_count'] == len(manifest['local_check_names']) == 14,
         'local check count differs')
    archive_path = HERE / manifest['archive']['file']
    need(archive_path.parent == HERE and archive_path.name ==
         'xu-timing116-local-original-bytes.tar.xz', 'archive path differs')
    archive_bytes = archive_path.read_bytes()
    need(identity(archive_bytes) == expected(manifest['archive']) and
         identity(archive_bytes)['sha256'] == ARCHIVE_SHA, 'compressed archive differs')
    payload = {}
    with tarfile.open(str(archive_path), 'r:xz') as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            need(member.isfile() and not name.is_absolute() and
                 all(part not in ('', '.', '..') for part in name.parts) and
                 member.name not in payload, 'unsafe/duplicate archive member')
            need(member.name in manifest['files'], 'unrecorded archive member')
            data = archive.extractfile(member).read()
            need(member.size == len(data) and identity(data) ==
                 expected(manifest['files'][member.name]), 'original bytes differ: ' + member.name)
            payload[member.name] = data
    need(set(payload) == set(manifest['files']) and
         sum(map(len, payload.values())) == manifest['payload_bytes'], 'payload set/total differs')
    original_root = Path(manifest['original_root'])

    def relative(absolute):
        return Path(absolute).relative_to(original_root).as_posix()

    def read_json(name):
        return load(payload[name])

    handoff = read_json(TOOL + 'handoff116.json')
    need(handoff['status'] == manifest['historical_handoff_status_preserved'] ==
         'READY_FOR_ONE_INDEPENDENT_SERVER_RUN_NOT_EXECUTED' and
         handoff['qualification'] == 'NOT_QUALIFIED' and handoff['local_checks'] == 14,
         'historical handoff scope differs')
    for name, record in handoff['files'].items():
        need(identity(payload[TOOL + name]) == expected(record), 'handoff file differs: ' + name)
    result = read_json(FINAL + 'results.json')
    need(result['status'] == 'LOCAL_RECEIPT_AND_GENERATOR_GUARDS_PASS_NOT_NATIVE_EDA' and
         result['qualification'] == 'NOT_QUALIFIED' and result['count'] == 14 and
         result['checks'] == manifest['local_check_names'], 'original14 scope/checks differ')
    for name, record in [('xu_timing_combined116.py', result['worker']),
                         ('check_local116.py', result['checker'])]:
        need(identity(payload[TOOL + name]) == expected(record), 'original14 tool binding differs')
    launcher = payload[TOOL + 'launch_timing_combined116.py'].decode('utf-8')
    worker_sha = re.search(r"WORKER_SHA = '([0-9a-f]{64})'", launcher).group(1)
    need(worker_sha == result['worker']['sha256'], 'launcher worker binding differs')
    for name in ('xu_timing_combined116.py', 'launch_timing_combined116.py', 'check_local116.py'):
        if sys.version_info >= (3, 8):
            ast.parse(payload[TOOL + name].decode('utf-8'), feature_version=(3, 6))
        else:
            ast.parse(payload[TOOL + name].decode('utf-8'))

    # Independently recheck the archived six native receipt/log/script bindings.
    ancestors = read_json(TOOL + 'ancestor-host-review116.json')
    need(len(ancestors['stages']) == 6 and ancestors['qualification'] == 'NOT_QUALIFIED',
         'ancestor scope differs')
    for stage in ancestors['stages']:
        name = relative(stage['state']['path'])
        need(identity(payload[name]) == expected(stage['state']), 'ancestor state differs')
        state = read_json(name)
        need(state['status'] == 'EXECUTED_NOT_QUALIFIED' and len(state['runs']) == 2 and
             state['mapped_netlist_sha256'] == stage['mapped_sha256_from_exact_state'],
             'ancestor mapped receipt/status differs')
        directory = str(PurePosixPath(name).parent) + '/'
        for label, record in zip(('dc', 'pt'), state['runs']):
            need(record['tool'] == label + '_shell' and record['returncode'] == 0 and
                 not record['errors'] and record['marker_count'] == 1, 'ancestor native run differs')
            need(identity(payload[directory + label + '.log'])['sha256'] == record['log_sha256'] and
                 identity(payload[directory + ('repair.tcl' if label == 'dc' else 'sta.tcl')])['sha256'] ==
                 record['script_sha256'], 'ancestor native log/script differs')
    fm49_name = relative(ancestors['FM49']['path'])
    need(identity(payload[fm49_name]) == expected(ancestors['FM49']), 'FM49 receipt differs')
    fm49 = read_json(fm49_name)
    need(fm49['status'] == 'VERIFIED_REVIEW_PENDING_NOT_QUALIFIED' and fm49['returncode'] == 0 and
         len(fm49['frozen_before']) == 169 and fm49['frozen_before'] == fm49['frozen_after'],
         'FM49 native/frozen scope differs')
    directory = str(PurePosixPath(fm49_name).parent) + '/'
    for name, record in [('fm.log', fm49['log']), ('verify.tcl', fm49['script'])]:
        need(identity(payload[directory + name]) == expected(record), 'FM49 native file differs')
    need('Verification SUCCEEDED' in [line.strip() for line in
         payload[directory + 'fm.log'].decode('utf-8').splitlines()], 'FM49 native success absent')

    review = read_json('build/xu-timing-next115/review115.json')
    need(review['status'] == 'READ_ONLY_LOCAL_REVIEW_NOT_NEW_SERVER_RUN' and
         review['qualification'] == 'NOT_QUALIFIED', 'review115 scope differs')
    for record in review['input_receipts']:
        need(identity(payload[relative(record['path'])]) == expected(record), 'review115 input differs')
    coverage_name = next(relative(row['path']) for row in review['input_receipts']
                         if row['path'].endswith('/analysis-coverage.rpt') and '-95/' in row['path'])
    blocks = re.split(r'\n(?=(?:u_soc|u_shared)/)', payload[coverage_name].decode('utf-8'))[1:]
    counts, roles, modes = Counter(), Counter(), Counter()
    types = set(('setup', 'hold', 'recovery', 'removal', 'min_period', 'min_pulse_width',
                 'clock_gating_setup', 'clock_gating_hold', 'out_setup', 'out_hold'))
    for block in blocks:
        block = re.sub(r'\n1\s*$', '', block)
        tokens = block.split()
        need(tokens[-2] == 'untested', 'coverage detail is not exact untested record')
        check = [token for token in tokens if token in types]
        need(len(check) == 1, 'coverage check type ambiguous')
        reason = tokens[-1]
        counts[check[0] + '|' + reason] += 1
        pin = tokens[0]
        if reason in ('no_clock', 'no_endpoint_clock', 'unknown'):
            roles[reason + '|' + pin.rsplit('/', 1)[-1].split('(', 1)[0]] += 1
        if check[0] == 'min_period' and reason == 'constant_disabled':
            modes[pin] += 1
    need(sum(counts.values()) == 27124 and dict(counts) ==
         review['95']['untested_check_reason_counts'], 'review115 coverage counts differ')
    need(dict(roles) == review['95']['untested_reason_pin_role_counts'] and
         len(modes) == 336 and set(modes.values()) == {31}, 'review115 coverage roles/modes differ')
    state94_name = next(relative(row['path']) for row in review['input_receipts']
                        if row['path'].endswith('/state.json') and '-94/' in row['path'])
    state94 = read_json(state94_name)
    need(state94['input_sha256_before'] == state94['input_sha256_after'], '94 input identity changed')

    replay_status = 'NOT_REQUESTED'
    if args.replay:
        with tempfile.TemporaryDirectory(prefix='.local116-replay-', dir=str(HERE)) as name:
            root = Path(name)
            # Original output bytes were verified above. Leave their location
            # absent so the unchanged original checker can create fresh output.
            for relative_name, data in payload.items():
                if relative_name.startswith(FINAL):
                    continue
                target = root / relative_name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            command = [sys.executable, str(root / (TOOL + 'check_local116.py'))]
            process = subprocess.run(command, cwd=str(root), stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, universal_newlines=True, timeout=120)
            need(process.returncode == 0, 'original14 host replay failed:\n' + process.stdout)
            replay = load((root / (FINAL + 'results.json')).read_bytes())
            need(replay['status'] == result['status'] and replay['qualification'] == 'NOT_QUALIFIED' and
                 replay['count'] == 14 and replay['checks'] == result['checks'] and
                 expected(replay['worker']) == expected(result['worker']) and
                 expected(replay['checker']) == expected(result['checker']), 'replayed14 scope differs')
            for generated in ('cleanup-generated.tcl', 'reset-generated.tcl'):
                need((root / (FINAL + generated)).read_bytes() == payload[FINAL + generated],
                     'replayed generated Tcl differs: ' + generated)
            replay_status = '14_ORIGINAL_HOST_CHECKS_REPLAYED_NOT_NATIVE_EDA'
    print(json.dumps(dict(status='OFFLINE_LOCAL116_EVIDENCE_PASS', qualification='NOT_QUALIFIED',
                          payload_files=len(payload), payload_bytes=manifest['payload_bytes'],
                          archive=manifest['archive'], local_checks=14,
                          review115_untested_rows=27124, replay=replay_status,
                          server116_execution='NOT_COVERED_BY_THIS_ARCHIVE'), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
