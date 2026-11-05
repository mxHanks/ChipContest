#!/usr/bin/env python3
"""xu independent local raw-byte review of diagnostic175; no EDA or remote IO."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / 'build/xu-s2c-observation175'
RAW = ROOT / 'build/xu-score-resume-20261103/progress174'
NATIVE = RAW / 's2c-passive-unknown-20261105-167'
ARCHIVE = ROOT / 'build/xu-score-resume-20261103/xu-server-two-candidate-progress-20261105-174.tar.xz'
EXPECTED_ARCHIVE = 'df0166018b47d6ad78917928f23fc77c5a32213b8f386b56610f4e67fa64dfd4'
EIGHT = [('w_commit', '048', 1), ('x_commit', '051', 1),
         ('bias_commit', '043', 1), ('row_active', '016', 1),
         ('row_count', '017', 2), ('row_running', '023', 1),
         ('row_produced', '020', 6), ('row_retired', '022', 6)]


def need(test, message):
    if not test:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1048576), b''):
            digest.update(part)
    return digest.hexdigest()


def identity(path):
    return dict(bytes=path.stat().st_size, sha256=sha(path))


def read(path):
    return json.loads(path.read_text())


def main():
    # Check every package member without extracting or trusting the analysis.
    need(identity(ARCHIVE) == dict(bytes=188212, sha256=EXPECTED_ARCHIVE), '174 archive identity')
    manifest = read(RAW / 'manifest.json')
    declared = {row['path']: row for row in manifest['files']}
    need(len(declared) == len(manifest['files']) == 74, '174 inventory')
    with tarfile.open(str(ARCHIVE), 'r:xz') as stream:
        members = stream.getmembers()
        need(len(members) == 75 and len({m.name for m in members}) == 75, '174 unique members')
        for member in members:
            name = Path(member.name)
            need(member.isfile() and not member.issym() and not member.islnk() and
                 not name.is_absolute() and '..' not in name.parts, '174 safe regular member')
            body = stream.extractfile(member).read()
            need(body == (RAW / member.name).read_bytes(), '174 archive/extracted bytes')
            if member.name != 'manifest.json':
                row = declared[member.name]
                need(len(body) == row['bytes'] and hashlib.sha256(body).hexdigest() == row['sha256'], '174 payload SHA')
    for row in read(SRC / 'manifest175.json')['files']:
        need(identity(SRC / row['path']) == {key: row[key] for key in ['bytes', 'sha256']}, '175 manifest SHA')
    # Replay the reviewed program in a fresh directory, never its original out.
    with tempfile.TemporaryDirectory(prefix='xu-review175-') as tmp:
        replay = subprocess.run([sys.executable, '-B', str(SRC / 'analyze175.py'), '--out', tmp],
                                cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True)
        need(replay.returncode == 0, '175 replay: ' + replay.stdout)
        for name in ['analysis175.json', 'events175.json']:
            need((Path(tmp) / name).read_bytes() == (SRC / name).read_bytes(), '175 reproducible output')
    state = read(NATIVE / 'state.json')
    analysis = read(SRC / 'analysis175.json')
    lines = (NATIVE / 'simulation.log').read_text().splitlines()
    # Independent raw field parser and per-bit four-state decoding.
    events = []
    for line in lines:
        if line.startswith('XU_UNKNOWN167_EVENT '):
            fields = dict(item.split('=', 1) for item in line.split()[1:])
            a, b, bits = int(fields['aval'], 16), int(fields['bval'], 16), int(fields['bits'])
            fields['value'] = ''.join('x' if b & (1 << i) and a & (1 << i) else
                                      'z' if b & (1 << i) else '1' if a & (1 << i) else '0'
                                      for i in range(bits - 1, -1, -1))
            fields['time'] = int(fields['tick_fs'])
            events.append(fields)
    need(len(events) == 566, '566 raw events')
    initial = [event for event in events if event['reason'] == 'first_observed_window_event']
    final = [event for event in events if event['reason'] == 'before_original_unknown_fatal']
    changes = [event for event in events if event['reason'] == 'value_change']
    need(len(initial) == len(final) == 131 and len(changes) == 304, 'snapshot/change counts')
    trigger = [line for line in lines if line.startswith('XU_UNKNOWN167_TRIGGER ')]
    need(len(trigger) == 1, 'unique task-local trigger')
    tasklocal = dict(item.split('=', 1) for item in trigger[0].split()[2:])
    native = {name: next(e['value'] for e in final if e['role'] == name) for name, _, _ in EIGHT}
    sampled = {name: next(e['value'] for e in final if e['name'] == 'tb_xu_soc_ppa.xu147_o_' + suffix)
               for name, suffix, _ in EIGHT}
    need(native == sampled == tasklocal == state['original_unknown_values'], 'fatal eight values agree')
    need([name for name, value in native.items() if re.search('[xz]', value)] == ['bias_commit'], 'only bias unknown')
    need(all(value == '0' * width for name, _, width in EIGHT if name != 'bias_commit'
             for value in [native[name]]), 'other seven operands zero')
    def by_role(rows, role):
        return [event for event in rows if event['role'] == role]
    initial_target = {role: by_role(initial, role)[0]['value']
                      for role in ['fifo_CK', 'fifo_D', 'fifo_Q', 'fifo_NOTIFIER']}
    need(initial_target == dict(fifo_CK='1', fifo_D='0', fifo_Q='0', fifo_NOTIFIER='x'), 'window initial target')
    first_x = {role: next(event['time'] for event in by_role(changes, role) if 'x' in event['value'])
               for role in ['fifo_D', 'fifo_Q', 'bias_commit']}
    need(first_x == dict(fifo_D=9359383443333, fifo_Q=9359390060000, bias_commit=9359416896667), 'earlier D transient retained')
    hold = [lines[i + 1] for i, line in enumerate(lines) if 'Timing violation in ' in line]
    need(len(hold) == 25 and sum('9359390050000' in line for line in hold) == 1, '25 native warning blocks')
    need(any('$hold(' in line and line.count('9359390050000') == 2 and 'limit: 10000' in line for line in hold), 'target hold details')
    shared = {event['name'].rsplit('.', 1)[-1] for event in initial if event['role'] == 'shared_port'}
    need(shared == {'clk', 'rst_n', 'cmd_valid', 'cmd_ready', 'cmd_read', 'cmd_addr', 'cmd_wdata',
                    'cmd_wmask', 'rsp_valid', 'rsp_ready', 'rsp_rdata', 'rsp_err'}, 'all twelve shared ports')
    log = '\n'.join(lines)
    absent = ['XU_TASK_CLEAR_OBSERVED', 'XU_SOURCE_REQUEST', 'XU_SOURCE_ACCEPT', 'XU_CANDIDATE_UPLOAD_PASS', 'TASK_PASS', 'SOC_PASS']
    need(all(marker not in log for marker in absent), 'no full qualification marker')
    need(analysis['notifier_causality'] == 'NOT_PROVEN' and analysis['qualification'] == 'NOT_QUALIFIED', 'limited inference')
    observer = (ROOT / 'build/xu-s2c-unknown167/observer167.c.in').read_text()
    need('cbValueChange' in observer and 'vpi_get_value' in observer and
         not re.search(r'\bvpi_put_value\s*\(|\bvpi_control\s*\(|vpiForceFlag|cbReadWriteSynch|cbAfterDelay', observer), 'passive observer')
    result = dict(schema='xu-s2c-observation175-independent-review-v1',
                  status='REVIEW_PASS_DIAGNOSTIC_INFERENCES_ONLY_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
                  blocking_review_findings=[], original175_output_bytes_reproduced=True,
                  reviewed175_entry=identity(SRC / 'analyze175.py'), raw_log=identity(NATIVE / 'simulation.log'),
                  archive=identity(ARCHIVE), raw_payload_files=74, raw_payload_bytes=5260127,
                  events=dict(total=566, initial=131, value_change=304, fatal_snapshot=131),
                  fatal_operands=native, first_observed_x_fs=first_x, initial_target=initial_target,
                  native_timing_warning_blocks=25, native_target_hold_limit_fs=10000,
                  server_file_receipts_only=634, shared_ports_observed=sorted(shared),
                  limitations=['The native target hold warning and later X propagation are observations, not a proved causal path.',
                               'NOTIFIER starts X and invalid response data starts X; neither is proved to be the first fault.',
                               'Callbacks have dispatch serials, not scheduler phase labels; same-tick serial order cannot establish causality.',
                               'The 634 unreturned server input files were not independently rehashed locally.',
                               'The original mandatory fatal still rejects before the formal task window; VCS rc0 does not qualify functionality.',
                               'Library-model hold warning is not a complete SDF or STA timing proof.'],
                  next_minimal_query='Use the exact ownS2c9c16 netlist, own SDC/clock method and frozen libraries. Enumerate the literal escaped target components, assert unique D/CK/Q/RDN pins and ref DRNQV0_12TR40, then report exact D driver, CK source and native min-delay full data/clock path. Read the same cell model specify/UDP relationship on the server under a hash receipt. Do not infer Q-to-bias causality across unobserved/stateful boundaries.',
                  production_source_changes=0, remote_actions=0, new_native_experiments=0)
    (HERE / 'review175.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(result['status'])


if __name__ == '__main__':
    main()
