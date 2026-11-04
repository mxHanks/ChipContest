#!/usr/bin/env python3
"""Verify immutable actual110 bytes and the finite claims in this directory."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

ROOT = Path(__file__).resolve().parent
ARCHIVE_SHA = 'ee7d293f161c855481d253cb0af8edcde82174f9da98e491157edffe0d179949'
P105 = 'vpi-vendor-preload-primitive-20261104-105/'
P108 = 'mapped-udp-review-20261104-108/'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def verify(extract=None):
    archive = ROOT / 'payload.tar.xz'
    need(archive.stat().st_size == 25432 and sha(archive.read_bytes()) == ARCHIVE_SHA,
         'actual110 archive identity differs')
    manifest = json.loads((ROOT / 'payload-manifest.json').read_text())
    expected = {row['path']: row for row in manifest}
    need(len(expected) == len(manifest) == 46 and sum(row['bytes'] for row in manifest) == 882860,
         'actual110 manifest dimensions differ')
    found, internal = {}, None
    with tarfile.open(archive, 'r|xz') as stream:
        for member in stream:
            path = PurePosixPath(member.name)
            need(member.isfile() and not path.is_absolute() and '..' not in path.parts and
                 member.name not in found and member.size < 12000000, 'unsafe/duplicate member')
            body = stream.extractfile(member).read()
            if member.name == 'manifest.json':
                need(internal is None, 'duplicate internal manifest')
                internal = json.loads(body)
                continue
            need(dict(path=member.name, bytes=len(body), sha256=sha(body)) == expected.get(member.name),
                 'raw payload differs: ' + member.name)
            found[member.name] = body
    need(internal == manifest and set(found) == set(expected), 'unaccounted/missing raw member')

    def obj(name):
        return json.loads(found[name])

    def text(name):
        return found[name].decode()

    primitive = obj(P105 + 'state.json')
    need(primitive['status'] == 'EXECUTED_READONLY_GEOMETRY_VENDOR_VPI_PRELOAD_AND_TWO_REJECTIONS_NOT_FULL_SOC_ACTIVITY_OR_ENERGY'
         and primitive['input_sha256_before'] == primitive['input_sha256_after'],
         'actual105 terminal scope/freeze differs')
    cases = primitive['cases']
    need([(row['name'], row['expected_pass'], row['actual_pass']) for row in cases] == [
         ('diagnostic_only', True, True), ('reference', True, True),
         ('wrong_bit_column_packing', False, False), ('swapped_handle_tags', False, False)],
         'actual105 four native outcomes differ')
    for case in cases:
        prefix = P105 + case['name'] + '/'
        need(sha(found[prefix + 'probe.c']) == case['code_sha256'] and
             sha(found[prefix + 'tb.sv']) == case['testbench_sha256'], 'actual105 case source differs')
        need([run['command']['name'] for run in case['runs']] == ['cc', 'vcs', 'sim'],
             'actual105 native execution sequence differs')
        for run in case['runs']:
            need(run['returncode'] == 0 and sha(found[prefix + run['command']['name'] + '.log']) == run['log_sha256'],
                 'actual105 log/native return differs')
        log = text(prefix + 'sim.log')
        geometry = re.findall(r'^XU_PRIMITIVE105_GEOMETRY tag=(\d+) row=(\d+) role=indexed_word exists=1 type=48 size=64 .*? index_handle=1 index_known=1 index=(\d+)$', log, re.M)
        need(len(geometry) == 512 and {(int(tag), int(row)) for tag, row, index in geometry} ==
             {(tag, row) for tag in [0, 1] for row in range(256)} and
             all(row == index for tag, row, index in geometry), 'actual105 VCS 2x256 native geometry differs')
        need(log.count('owned_rows=256 word_bits=64 unique_rows_checked=256') == 2,
             'actual105 complete geometry guard differs')
        if case['name'] == 'diagnostic_only':
            need('XU_PRIMITIVE105_DIAGNOSTIC status=PASS macros=2 writes=0' in log and
                 'XU_PRIMITIVE105_PRELOAD' not in log, 'read-only diagnostic performed writes')
        elif case['name'] == 'reference':
            need(log.count('writes=1 row=3 Q_uninitialized=1') == 2 and
                 'XU_PRIMITIVE105_RESULT status=PASS macro_handles=2 memory_word_writes=2 read_checks=8 hold_checks=4 Q_callbacks=8 NOT_FULL_SOC_OR_ACTIVITY_OR_ENERGY' in log,
                 'actual105 natural-Q/read/hold result differs')
            reads = re.findall(r'^XU_PRIMITIVE105_READ tag=(\d) column=(\d) expected=([0-9a-f]{4}) actual=([0-9a-f]{4}) unknown_mask=0000$', log, re.M)
            need(len(reads) == 8 and all(expected == actual for tag, column, expected, actual in reads)
                 and {(int(tag), int(col)) for tag, col, expected, actual in reads} ==
                 {(tag, col) for tag in [0, 1] for col in range(4)}, 'actual105 physical readback differs')
            edges = re.findall(r'^XU_PRIMITIVE105_EDGES tag=(\d) rises=(\d+) falls=(\d+) expected_rises=(\d+) expected_falls=(\d+) X_to_binary=16 binary_to_X=0 vector_notifications=4$', log, re.M)
            need(len(edges) == 2 and all(rise == erise and fall == efall for tag, rise, fall, erise, efall in edges),
                 'actual105 observed bitwise edges differ')
        else:
            need('XU_PRIMITIVE105_ERROR physical_port_tag_or_readback' in log and
                 'Fatal:' in log and 'XU_PRIMITIVE105_RESULT status=PASS' not in log,
                 'negative mutation was not rejected by actual physical readback')

    udp = obj(P108 + 'state.json')
    need(udp['status'] == 'EXECUTED_ORIGINAL_UDP_DEPENDENCY_AND_FINITE_BEHAVIOR_NOT_QUALIFIED'
         and udp['qualification'] == 'NOT_QUALIFIED' and udp['inputs_before'] == udp['inputs_after']
         and udp['source_body_exported'] is False, 'actual108 terminal scope/freeze differs')
    need(sha(found['tools/xu_udp_review108.py']) == udp['tool']['sha256'] ==
         '53edd2c4da4e2a335d8332f7909918d43fc77dfd79078d96229f5a45bec30991', 'actual108 tool differs')
    for item in udp['reviews']:
        name = 'source-' + item['mode'] + '.json'
        body = found[P108 + name]
        need(len(body) == item['report']['bytes'] and sha(body) == item['report']['sha256'],
             'actual108 source-review identity differs')
        report = obj(P108 + name)
        need(report['active_module_count'] == 1270 and report['mapped_module_count'] == 927 and
             report['mapped_instance_declarations'] == 127548 and
             [(row['name'], row['complete_tokens_identical'], row['unique_caller_cells'],
               row['mapped_reachable_instance_count']) for row in report['duplicates']] ==
             [('udp_tlatrf', True, 0, 0), ('udp_tlatrf2', False, 0, 0)],
             'actual108 finite parser result differs')
    for item in udp['probes']:
        prefix = P108 + 'probe-' + item['name'] + '/'
        result = obj(prefix + 'result.json')
        need(sha(found[prefix + 'result.json']) == item['result']['sha256'] and
             result['counters'] == item['counters'] and result['compile_returncode'] == 0 and
             result['simulation_returncode'] == 0 and result['qualification'] == 'NOT_QUALIFIED',
             'actual108 finite native result differs')
        for label, filename in [('compile_log', 'vcs.log'), ('simulation_log', 'sim.log'), ('testbench', 'tb.sv')]:
            need(sha(found[prefix + filename]) == result[label]['sha256'], 'actual108 native byte identity differs')
    need(udp['probes'][0]['counters']['steps'] == 16641 and udp['probes'][0]['counters']['pair_diffs'] == 0 and
         udp['probes'][1]['counters']['steps'] == 107521 and udp['probes'][1]['counters']['pair_diffs'] == 3668 and
         udp['probes'][1]['counters']['original_first_diffs'] == 3668 and
         all(row['counters']['original_last_diffs'] == 0 for row in udp['probes']),
         'actual108 behavior counterexample/last-selection result differs')
    observed = obj('live110-observation.json')
    need(observed['vendor_fragments_exported'] is False and len(observed['observed']) == 2 and
         all(not row['alive'] and row['command'] == '' for row in observed['observed']),
         'actual110 terminal observation differs')
    if extract:
        extract.mkdir(exist_ok=False)
        for name, body in found.items():
            destination = extract / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(body)
    return dict(status='PASS', qualification='NOT_QUALIFIED', payload_count=46,
                payload_bytes=882860, archive_sha256=ARCHIVE_SHA,
                actual105_reference='8_reads_4_holds_512_native_rows_two_rejections',
                actual108_tlatrf2_finite_steps=107521, actual108_tlatrf2_pair_differences=3668,
                original_matches_last_on_sampled_steps=True,
                caller_zero_scope='SOURCE_PARSER_ONLY_NOT_GLOBAL_NO_CALLERS_PROOF')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.extract), sort_keys=True, indent=2))
