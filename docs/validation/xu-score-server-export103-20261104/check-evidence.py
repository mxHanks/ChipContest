#!/usr/bin/env python3
"""Verify exact actual103 raw bytes and the limited claims made in README."""
import argparse
import csv
import hashlib
import io
import json
import re
import tarfile
from fractions import Fraction
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
ARCHIVE_SHA = '23edcf303dcc05b0ce120185bf2751dc1920a1e9bea7a1cb4388d5c8bc282ef2'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def verify(extract=None):
    archive = ROOT / 'payload.tar.xz'
    need(archive.stat().st_size == 342100 and sha(archive.read_bytes()) == ARCHIVE_SHA,
         'immutable original export103 archive differs')
    manifest = json.loads((ROOT / 'payload-manifest.json').read_text())
    expected = {row['path']: row for row in manifest}
    need(len(expected) == len(manifest) == 110 and
         sum(row['bytes'] for row in manifest) == 23145122, 'manifest dimensions differ')
    found = {}
    internal = None
    with tarfile.open(archive, 'r|xz') as stream:
        for member in stream:
            path = PurePosixPath(member.name)
            need(member.isfile() and not path.is_absolute() and '..' not in path.parts and
                 member.name not in found and member.size < 64000000, 'unsafe/duplicate member')
            body = stream.extractfile(member).read()
            if member.name == 'manifest.json':
                need(internal is None, 'duplicate internal manifest')
                internal = json.loads(body)
                continue
            need(dict(path=member.name, bytes=len(body), sha256=sha(body)) ==
                 expected.get(member.name), 'original raw member differs: ' + member.name)
            found[member.name] = body
    need(internal == manifest and set(found) == set(expected), 'missing/unaccounted raw body')

    def obj(name):
        return json.loads(found[name])

    def text(name):
        return found[name].decode()

    def rows(name):
        return list(csv.DictReader(io.StringIO(text(name)), delimiter='\t'))

    cleanup = 'full-soc-unloaded-cell-cleanup-20261104-95/'
    state = obj(cleanup + 'state.json')
    need(state['status'] == 'EXECUTED_NOT_QUALIFIED' and state['candidate_count'] == 20 and
         state['parent_mapped_sha256'] == '5a1e30ca4c9f14a8eabb349575a9f3069038c15ec38577edeacf0c9613cfa048' and
         state['mapped_netlist_sha256'] == 'a38717c9f775148c54f748343c77da9cf3bf593fec72e5bfc706ee5f3043ce59',
         'actual95 identity differs')
    for label, run in zip(['dc', 'pt'], state['runs']):
        need(run['returncode'] == 0 and run['marker_count'] == 1 and run['errors'] == [] and
             sha(found[cleanup + label + '.log']) == run['log_sha256'] and
             sha(found[cleanup + ('repair.tcl' if label == 'dc' else 'sta.tcl')]) == run['script_sha256'],
             'actual95 native execution differs')
    for name, record in dict(state['reports'], **state['audits']).items():
        need(len(found[cleanup + name]) == record['bytes'] and
             sha(found[cleanup + name]) == record['sha256'], 'actual95 report differs')
    before = rows(cleanup + 'removal-preflight.tsv')
    removed = rows(cleanup + 'removed-cells.tsv')
    upstream = rows(cleanup + 'post-cleanup-upstream.tsv')
    need(len(before) == len(removed) == 20 and
         {row['cell'] for row in before} == {row['cell'] for row in removed} and
         all(row['is_sequential'] == 'false' and row['parent_ref_instance_count'] == '1' and
             row['output'] == row['leaf_connections'] for row in before) and
         all(row['removed'] == '1' for row in removed), 'actual95 exact preflight/removal differs')
    unloaded = [row for row in upstream if row['source_only'] == '1']
    cap = text(cleanup + 'constraints.rpt').split('    Pin: ')[1:]
    need(len(upstream) == 44 and len(unloaded) == len(cap) == 17 and
         {part.splitlines()[0] for part in cap} == {row['driver'] for row in unloaded},
         'actual95 remaining17 min-cap/source-only inventory differs')
    need(re.search(r'All Checks\s+294473\s+267344.*?\s5\s+\(.*?27124',
                   text(cleanup + 'analysis-coverage.rpt')) is not None and
         'min\t1\t-0.121483' in text(cleanup + 'timing-slack.tsv'),
         'actual95 unclosed timing coverage must remain visible')

    reset = 'pmu-reset-unconstrained-paths-20261104-94/'
    state = obj(reset + 'state.json')
    need(state['status'] == 'EXECUTED_READ_ONLY_CLOCK_DIAGNOSTIC_NOT_QUALIFIED' and
         state['input_sha256_before'] == state['input_sha256_after'] and
         [len(run['errors']) for run in state['runs']] == [0, 0, 2],
         'actual94 original freeze/errors differ')
    for run in state['runs']:
        need(run['returncode'] == 0 and run['marker_count'] == 1 and
             sha(found[reset + run['script']]) == run['script_sha256'],
             'actual94 script/return differs')
    query = rows(reset + 'paths.tsv')
    need(len(query) == 16 and len([row for row in query if row['source_kind'] == 'HF_RESET' and
         row['check'] == 'recovery' and row['count'] == '0' and row['status'] == 'NO_PATH_UNKNOWN']) == 5,
         'actual94 five HF recovery gaps differ')
    for index, arrival in [(0, '0.8927571774'), (1, '0.8930612803')]:
        report = text(reset + 'reported-unconstrained-hf-%d-recovery.rpt' % index)
        need('(Path is unconstrained)' in report and
             re.search(r'data arrival time\s+' + re.escape(arrival), report),
             'actual94 unconstrained PMU delay differs')
    for index in [2, 3, 4]:
        need('No paths with slack less than 0.0000000000.' in
             text(reset + 'reported-unconstrained-hf-%d-recovery.rpt' % index),
             'actual94 AON HF recovery report result differs')
    witness = obj(reset + 'clock-phase-witness.json')
    gap = witness['nearest_positive_capture_gap']['gap_ns']
    need(Fraction(gap['numerator'], gap['denominator']) == Fraction(13012441, 500000000) and
         witness['status'] == 'EXACT_CLOCK_EDGE_PROXIMITY_ONLY_NOT_RECOVERY_SLACK',
         'actual94 finite phase witness differs')

    audit = 'mapped-warning-audit-20261104-101/'
    state = obj(audit + 'state.json')
    need(state['status'] == 'EXECUTED_LINT_AND_SOURCE_REVIEW_NOT_FUNCTIONAL_QUALIFIED' and
         state['inputs_before'] == state['inputs_after'] and not state['runtime_simulation_executed'] and
         state['actual_lint_error_counts'] == {} and state['actual_lint_warning_counts'] == {'OPD': 2},
         'actual101 compile-only warning scope differs')
    log = text(audit + 'vcs-lint.log')
    need(log.count('This udp will be overridden by the last declaration.') == 2 and
         sha(found[audit + 'vcs-lint.log']) == state['steps'][0]['log']['sha256'],
         'actual101 native last-definition warning differs')
    ports = obj(audit + 'missing-port-source-direction-review.json')
    need(ports['instances_parsed'] == 127548 and ports['counts'] == {
         'instances_with_omitted_ports': 148, 'omitted_output': 952} and
         all(pin['direction'] == 'output' for row in ports['instances'] for pin in row['missing_ports']),
         'actual101 omitted-port direction review differs')
    udp = obj(audit + 'duplicate-udp-token-review.json')
    need([(row['name'], row['complete_definition_tokens_identical']) for row in udp['duplicates']] ==
         [('udp_tlatrf', True), ('udp_tlatrf2', False)] and not udp['source_body_exported'],
         'actual101 nonidentical duplicate must remain unresolved')

    primitive = obj('vpi-vendor-preload-primitive-20261104-100/state.json')
    need(primitive['status'] == 'FAIL_PRIMITIVE_NOT_QUALIFIED' and primitive['cases'] == [] and
         'positive/negative actual behavior differs: reference' in primitive['error'] and
         'native_memory_geometry' in text('vpi-vendor-preload-primitive-20261104-100/reference/sim.log'),
         'actual100 failed reference must remain failure')
    pins = obj('s2c-native-pin-stream-20261104-93/state.json')
    need(pins['status'] == 'RUNNING' and len(pins['tasks']) == 6 and
         [row['task_id'] for row in pins['tasks']] == list(range(6)),
         'actual93 is the live6/12 snapshot, not terminal12/12')
    launch = obj('s2e-ppa-deploy-20261104-89/state.json')
    need(launch['status'] == 'CAMPAIGN_LAUNCHED_NOT_QUALIFIED' and launch['pid'] == 152796 and
         launch['campaign_pid'] == 156772, 'actual89 bootstrap/campaign PID identity differs')
    observation = obj('live103-observation.json')['observed']
    worker = [row for row in observation if row['prefix'] == 'actual93_worker_from_launcher'][0]
    campaign = [row for row in observation if row['prefix'] == 's2e-ppa-campaign-20261104-89'][0]
    need(worker['pid'] == 144236 and worker['pid_alive_now'] and
         'xu_extract_pt_pin_reports93.py extract' in worker['process_command'] and
         campaign['status'] == 'ABSENT_OR_NO_STATE', 'actual103 live/absent observation differs')
    if extract:
        extract.mkdir(exist_ok=False)
        for name, body in found.items():
            destination = extract / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(body)
    return dict(status='PASS', qualification='NOT_QUALIFIED', archive_sha256=ARCHIVE_SHA,
                returned_payload_count=110, returned_payload_bytes=23145122,
                cleanup95_removed=20, cleanup95_remaining_min_cap=17,
                reset94_unconstrained_PMU_paths=2, reset94_original_SEL005_errors=2,
                actual101_nonidentical_duplicate_UDP='udp_tlatrf2_UNRESOLVED',
                actual100_reference_failure='PRESERVED', actual93_tasks_at_snapshot=6,
                actual89_campaign_state='ABSENT_AT_SNAPSHOT_NOT_INFERRED_FROM_BOOTSTRAP')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.extract), sort_keys=True, indent=2))
