#!/usr/bin/env python3
"""Verify immutable actual82 payloads and review actual80 without changing them."""
import argparse
import csv
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
ARCHIVE_SHA = '636694128def9585a028290434b7081ed3851000209216d36d20ba8fc69eded5'
PREFIX = 'pmu-reset-condition-20261104-80/'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(selected=(), extract=None):
    archive = ROOT / 'payload.tar.xz'
    need(archive.stat().st_size == 161848 and sha(archive.read_bytes()) == ARCHIVE_SHA,
         'immutable actual82 archive identity differs')
    manifest = json.loads((ROOT / 'original-manifest.json').read_text())
    expected = {row['path']: row for row in manifest}
    need(len(manifest) == len(expected) == 53 and sum(row['bytes'] for row in manifest) == 12372947,
         'actual82 source manifest dimensions differ')
    if extract:
        extract = Path(extract)
        extract.mkdir(exist_ok=False)
    selected = set(selected)
    found, observed, seen, inside = {}, {}, set(), None
    with tarfile.open(archive, mode='r|xz') as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            need(member.isfile() and not path.is_absolute() and '..' not in path.parts
                 and member.name not in seen, 'unsafe or duplicate native archive member')
            need(member.size < 64000000, 'unexpected oversized actual82 member')
            seen.add(member.name)
            keep = member.name in selected or member.name == 'manifest.json'
            content = bytearray() if keep else None
            digest, size, writer = hashlib.sha256(), 0, None
            if extract:
                out = extract / member.name
                out.parent.mkdir(parents=True, exist_ok=True)
                writer = out.open('xb')
            try:
                with tar.extractfile(member) as source:
                    for block in iter(lambda: source.read(1024 * 1024), b''):
                        size += len(block)
                        digest.update(block)
                        if keep:
                            content.extend(block)
                        if writer:
                            writer.write(block)
            finally:
                if writer:
                    writer.close()
            need(size == member.size, 'native member size differs')
            if member.name == 'manifest.json':
                inside = json.loads(content)
            else:
                observed[member.name] = dict(path=member.name, bytes=size, sha256=digest.hexdigest())
                if keep:
                    found[member.name] = bytes(content)
    need(inside == manifest and observed == expected, 'all 53 native payload SHA/size comparisons must match')
    need(set(found) == selected, 'selected native evidence missing')
    return found


def review(extract=None):
    names = ['state.json', 'diagnosis.log', 'installed-docs.log', 'reset-paths.tsv',
             'installed-vars-recovery.txt', 'installed-vars-removal.txt', 'pins.tsv',
             'timing-arcs.tsv', 'analysis-coverage.rpt', 'case-analysis.rpt']
    names += ['reset-%d-%s.rpt' % (i, check) for i in range(5) for check in ('recovery', 'removal')]
    data = verify([PREFIX + name for name in names] + ['actual61-current-identities-20261104-82.json',
                  'standard-cell-model-inventory-20261104-81/state.json'], extract)
    native = {name: data[PREFIX + name] for name in names}
    state = json.loads(native['state.json'])
    need(state['status'] == 'EXECUTED_DIAGNOSTIC_NOT_QUALIFIED', 'actual80 terminal diagnostic status differs')
    need(len(state['runs']) == 2, 'actual80 two native executions required')
    error = 'Error: Nothing matched for -of_objects collection (SEL-005)'
    for index, (name, count) in enumerate((('installed-docs.log', 0), ('diagnosis.log', 2))):
        log = native[name].decode()
        errors = [line for line in log.splitlines() if re.match(r'^\s*(?:Error:|Error-|XU_FATAL:)', line)]
        run = state['runs'][index]
        need(run['returncode'] == 0 and run['marker_count'] == 1 and run['errors'] == errors == [error] * count,
             'actual80 error-bearing execution record differs')
        need(run['log_sha256'] == sha(native[name]), 'actual80 native log SHA differs')
    helper = ROOT / 'tools/launch_reset_condition80.py'
    need(sha(helper.read_bytes()) == 'e9547692c83c12345c00d794379369823541fc2d0a97f2397c0f8ed18dc3fc0f',
         'exact actual80 launcher differs')
    need(state['input_sha256']['/storage2/2026contest/server4/s4_23usr/Desktop/launch_reset_condition80.py']
         == sha(helper.read_bytes()), 'actual80 launcher does not bind frozen receipt')
    for key, content in native.items():
        if key not in ('state.json',):
            need(state['outputs'][key] == dict(bytes=len(content), sha256=sha(content)), 'actual80 output receipt differs: ' + key)
    paths = list(csv.DictReader(io.StringIO(native['reset-paths.tsv'].decode()), delimiter='\t'))
    need(len(paths) == 10, 'all ten reset reports required')
    for row in paths:
        missing = row['index'] in ('0', '1') and row['check'] == 'recovery'
        need(row['path_count'] == ('0' if missing else '1'), 'actual reset path count differs')
        need(row['status'] == ('UNKNOWN' if missing else 'PATHS_PRESENT_DIAGNOSTIC_ONLY'),
             'missing recovery path must remain UNKNOWN')
    for key in ('installed-vars-recovery.txt', 'installed-vars-removal.txt'):
        need(native[key] == b'timing_disable_recovery_removal_checks = "false"\n', 'actual default is not false')
    log = native['diagnosis.log'].decode()
    expansion = [(i + 1, line) for i, line in enumerate(log.splitlines()) if '(PTE-052)' in line]
    need(len(expansion) == 1 and 'can cause paths between these clocks to be unconstrained' in expansion[0][1],
         'actual clock expansion warning differs')
    pins = list(csv.DictReader(io.StringIO(native['pins.tsv'].decode()), delimiter='\t'))
    # Some leaf_connection records contain an extra field; the three fields used
    # here are fixed columns of native per-pin attribute/nets records.
    empty_nets = [row['pin'] for row in pins if row['field'] == 'nets' and row['value'] == '']
    need(len(empty_nets) == 2 and empty_nets[0].endswith('/erst_reset_r_reg/D')
         and empty_nets[1].endswith('/reg_2/q_reg/D'), 'two native empty-net objects differ')
    arrivals = {row['pin']: row['value'] for row in pins if row['field'] == 'max_rise_arrival' and row['pin'].endswith('/SDN')}
    need(list(arrivals.values()) == ['VALUE 0.892707', 'VALUE 0.892943'], 'PMU max-rise arrivals differ')
    arcs = list(csv.reader(io.StringIO(native['timing-arcs.tsv'].decode()), delimiter='\t'))
    delays = [row[4] for row in arcs if len(row) == 5 and row[1:4] == ['timing_arc', 'arc_005', 'delay_max']]
    need(delays[:2] == ['VALUE -0.136499', 'VALUE -0.136345'], 'two native conditional recovery values differ')
    coverage = native['analysis-coverage.rpt'].decode()
    need(re.search(r'^recovery\s+17597\s+17595\s+\(100%\)\s+0\s+\(\s*0%\)\s+2\s+\(\s*0%\)', coverage, re.M),
         'native recovery coverage differs')
    for i in (2, 3, 4):
        report = native['reset-%d-recovery.rpt' % i].decode()
        need('u_sirv_aon/wdog/AsyncResetRegVec_6_1/reg_0/q_reg' in report
             and 'rising edge-triggered flip-flop clocked by xu_lfextclk' in report,
             'existing AON recovery report must preserve its LF watchdog startpoint')
    identities = json.loads(data['actual61-current-identities-20261104-82.json'])
    need(identities['mapped.v']['sha256'] == '502a29a0f990d2b1f9394b80da35639cfbb81b9021ad01355f96ab1465dc7597'
         and identities['state.json']['sha256'] == '1163c63ba568db5040177f844bb4c3d0518029f4e3e85f58d376950a4f646df1',
         'unchanged failed actual61 identity differs')
    inventory = json.loads(data['standard-cell-model-inventory-20261104-81/state.json'])
    need(inventory['models'] == [] and inventory['status'] == 'READ_ONLY_INVENTORY_NOT_SIMULATION',
         'actual81 filtered inventory differs')
    return dict(status='PASS', qualification='NOT_QUALIFIED', archive_bytes=161848,
                archive_sha256=ARCHIVE_SHA, payload_count=53, payload_bytes=12372947,
                actual80_status=state['status'], installed_docs_errors=0, diagnosis_errors=2,
                unknown_recovery_checks=2, clock_expansion_warning_line=expansion[0][0],
                empty_net_query_objects=empty_nets,
                next_hypothesis='HF-to-LF recovery clock-edge expansion; not yet proved')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--extract', type=Path)
    args = parser.parse_args()
    print(json.dumps(review(args.extract), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
