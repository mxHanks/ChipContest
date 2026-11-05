#!/usr/bin/env python3
"""Independent xu159 original-package audit. Read-only, no EDA or remote access."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

HERE = Path(__file__).resolve().parent
B = '/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/'
C = 'unified-experiment-control-20261105-150/'
T = 's2e-own-timing-repair-20261105-155/'
A = 'eight-formal-activity12-20261105-145/'
FAILED = ('baseline_h1_h2', 's1_h2_only', 's1_sram_bias', 's2b', 's2d', 'pe32')


def need(value, message):
    if not value:
        raise ValueError(message)


def ident(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def package(path, size, sha, count, total):
    need(ident(path.read_bytes()) == dict(bytes=size, sha256=sha), 'original archive identity differs')
    payload = {}
    with tarfile.open(str(path), 'r:xz') as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            need(member.isfile() and not name.is_absolute() and '..' not in name.parts and
                 member.name not in payload and not {'private-docs', 'private-manuals'} & set(name.parts),
                 'unsafe/duplicate/private archive member')
            raw = archive.extractfile(member).read()
            need(len(raw) == member.size, 'truncated original archive member')
            payload[member.name] = raw
    manifest = json.loads(payload.pop('manifest.json'))
    need(len(manifest) == len(payload) == count and {r['path'] for r in manifest} == set(payload),
         'original manifest inventory differs')
    need(sum(len(v) for v in payload.values()) == total, 'original payload byte total differs')
    for row in manifest:
        need(ident(payload[row['path']]) == {k: row[k] for k in ('bytes', 'sha256')},
             'original payload identity differs: ' + row['path'])
    return payload


def audit(p, history):
    js = lambda n: json.loads(p[n])
    checked = set()

    def receipt(row):
        need(row['path'].startswith(B), 'unexpected receipt scope')
        n = row['path'][len(B):]
        need(n in p and ident(p[n]) == {k: row[k] for k in ('bytes', 'sha256')},
             'returned original body/receipt differs: ' + n)
        checked.add(n)

    state = js(C + 'state.json')
    before = json.loads(history[C + 'state.json'])
    need(set(state['jobs']) == set(before['jobs']) and len(state['jobs']) == 24, 'queue must retain24 jobs')
    for name in state['jobs']:
        n = C + 'registrations/' + name + '.json'
        need(p[n] == history[n], 'registered immutable job changed: ' + name)
        receipt(state['jobs'][name]['registration'])
    expected = {name: 'COMPLETED_DIAGNOSTIC_NOT_QUALIFIED' for name in
                ('s2e_power130', 'eight_freeze138', 'baseline_rdc142', 's2e_timing155')}
    expected.update({name: 'FAILED_REVIEW_REQUIRED' for name in
                     ('s2e_timing134', 'mapped_private147', 's2e_streamaudit156')})
    expected.update({'activity145_' + c: 'FAILED_REVIEW_REQUIRED' for c in FAILED})
    expected.update({'power146_' + c: 'BLOCKED_DEPENDENCY_NOT_QUALIFIED' for c in FAILED})
    expected.update(activity145_pe64='RUNNING', activity145_compact32_128='WAIT_DEPENDENCY',
                    power146_pe64='WAIT_DEPENDENCY', power146_compact32_128='WAIT_DEPENDENCY',
                    zz_campaign_report154='WAIT_DEPENDENCY')
    need({n: r['status'] for n, r in state['jobs'].items()} == expected, 'actual159 historical queue status differs')
    live = js('live159-observation.json')
    observations = {r['name']: r for r in live['observations']}
    need(observations['controller153']['actual'] == state['controller_identity'] == before['controller_identity'],
         'historical159 actual controller identity differs')
    running = observations['activity145_pe64']['actual']
    need(running == state['jobs']['activity145_pe64']['worker_identity'] and running['pid'] == 317009 and
         running == js(C + 'runs/activity145_pe64/spawn.json')['worker_identity'] and
         state['jobs']['activity145_pe64']['worker_identity_alive'] is True and
         running in state['jobs']['activity145_pe64']['live_processes'], 'historical159 pe64 live identity differs')
    need(all(r['actual'] is None for n, r in observations.items() if n not in ('controller153', 'activity145_pe64')),
         'unexpected other original live observation')
    old_events = history[C + 'events.jsonl']
    need(p[C + 'events.jsonl'].startswith(old_events), 'append-only event history changed')

    activity = {}
    for candidate in FAILED + ('pe64',):
        prefix = A + candidate + '/'
        result = js(prefix + 'result.json')
        need(result['profile'] == candidate and result['current_task_id'] == 0 and result['tasks'] == [] and
             result['qualification'] == 'NOT_QUALIFIED', 'activity task0/no completed tasks differs: ' + candidate)
        want = 'RUNNING' if candidate == 'pe64' else 'FAIL_REVIEW_REQUIRED_NOT_QUALIFIED'
        need(result['status'] == want, 'activity original status differs')
        log = p[prefix + 'task_00/simulation.log'].decode()
        tb = p[prefix + 'simulator/tb_xu_profile145.sv'].decode()
        need('accel_soc.verilog.verilog' in log and 'Cannot open file' in log and
             '+MAX_CYCLES=4000000' in log and '+TESTCASE=' + B + prefix + 'firmware/accel_soc.verilog' in log and
             '$readmemh({testcase,".verilog"},program_bytes);' in tb,
             'original doubled-firmware-suffix failure evidence differs: ' + candidate)
        markers = {k: len(re.findall('^' + k + r'\b', log, re.M)) for k in
                   ('XU_CLEAR_BEGIN145', 'XU_CLEAR_LAST145', 'XU_SOURCE_REQUEST145', 'XU_SOURCE_ACCEPT145')}
        need(all(v == 0 for v in markers.values()), 'failed task unexpectedly reached clear/source proof')
        if candidate != 'pe64':
            need('PPA_PROGRESS cycles=4000000 layer=0 writes=0 completed=0' in log and
                 'SoC timeout layer=0 writes=0' in log and 'Fatal:' in log, 'original fatal timeout differs')
            receipt(state['jobs']['activity145_' + candidate]['terminal_receipt'])
        activity[candidate] = dict(status=want, completed_tasks=0, current_task_id=0, markers=markers,
            simulation_log=ident(p[prefix + 'task_00/simulation.log']),
            doubled_firmware_suffix_observed=True, timeout_observed=candidate != 'pe64')

    timing = js(T + 'state.json')
    need(timing['status'] == 'EXECUTED_OWN_S2E_SAME_MAPPED_DC_PT_FULL_FM_NOT_QUALIFIED' and
         timing['qualification'] == 'NOT_QUALIFIED' and timing['formal_passing'] == 42338 and
         timing['frozen_before'] == timing['frozen_after'] and len(timing['frozen_before']) == 204 and
         timing['frozen_input_errors'] == [] and timing['resume155_adopted_originals_rechecked'] is True,
         '155 terminal identity/FM/frozen inputs differ')
    need(len(timing['runs']) == 8 and [r['tool'] for r in timing['runs']] ==
         ['dc', 'pt', 'dc', 'dc', 'pt', 'dc', 'pt', 'fm'], '155 exact original/native phase order differs')
    native = []
    for i, run in enumerate(timing['runs']):
        need(run['returncode'] == 0 and run['marker_count'] == 1 and run['errors'] == [], 'native155 phase failed')
        receipt(run['log']); receipt(run['script'])
        if i < 5:
            need(run['execution_provenance'] == 'ADOPTED_ORIGINAL134_NATIVE_PHASE_NOT_RERUN' and
                 run == json.loads(history[T + 'state.json'])['runs'][i], 'original134 adoption differs')
        log = p[run['log']['path'][len(B):]].decode()
        marker = ('XU_S2E_TIMING134_FORMALITY_PASS' if run['tool'] == 'fm' else
                  'XU_S2E_TIMING134_PT_DONE_NOT_QUALIFIED' if run['tool'] == 'pt' else
                  'XU_S2E_TIMING134_INVENTORY_DONE_NOT_QUALIFIED' if 'inventory.tcl' in run['command'][-1] else
                  'XU_S2E_TIMING134_HOLD_DONE_NOT_QUALIFIED' if i == 2 else
                  'XU_S2E_TIMING134_REPAIR_DONE_NOT_QUALIFIED')
        need(sum(s.strip() == marker for s in log.splitlines()) == 1, 'unique native marker absent: ' + marker)
        need(not re.search(r'^(?:Error:|Fatal:)', log, re.M), 'native155 log contains Error/Fatal')
        native.append(dict(index=i, tool=run['tool'], scope='ADOPTED134' if i < 5 else 'NEW155',
                           returncode=0, log=ident(p[run['log']['path'][len(B):]])))
    fm = p[T + 'final/fm.log'].decode()
    need(sum(s.strip() == 'Verification SUCCEEDED' for s in fm.splitlines()) == 1 and
         re.search(r'^Passing \(equivalent\).*\s42338\s*$', fm, re.M) and
         re.search(r'^Failing \(not equivalent\)\s+(?:0\s+){7}0\s*$', fm, re.M), 'full155 native FM count differs')
    verify = p[T + 'final/verify.tcl'].decode()
    need(len(timing['svf_chain']) == 3 and
         timing['svf_chain'][0]['sha256'] == '1a00803ebb654285dad15c76978fe1da50dd9732860f6af82a9a2d9117e668a9' and
         all(row['path'] in verify for row in timing['svf_chain']) and
         all(row['path'].startswith(B + T) and row['path'] in verify
             for row in timing['final_outputs'].values() if row['path'].endswith('mapped.v')),
         '155 complete FM own S2e SVF/final mapped input chain differs')
    for row in timing['reports'].values():
        receipt(row)
    for row in timing['generated'].values():
        receipt(row)
    coverage = p[T + 'final/analysis-coverage.rpt'].decode()
    need(re.search(r'^All Checks\s+298878\s+271661 \( 91%\)\s+0 \(  0%\)\s+27217 \(  9%\)', coverage, re.M),
         '155 complete coverage counts differ')
    need(re.search(r'^recovery\s+17783\s+17781 \(100%\)\s+0 \(  0%\)\s+2 \(  0%\)', coverage, re.M) and
         'There are 31 endpoints which are not constrained for maximum delay.' in
         p[T + 'final/check-timing.rpt'].decode() and
         p[T + 'final/timing-slack.tsv'].decode() == timing['timing'],
         '155 untested recovery/unconstrained endpoints/slack report differs')
    need(len(timing['remaining_electrical']) == 3 and all(r['kind'] == 'min_capacitance' and r['load'] == 0
         for r in timing['remaining_electrical'].values()), 'three original PLIC electrical gates differ')

    private = js('s2c-private-native-20261105-147/state.json')
    need(private['status'] == 'FAIL_PRIVATE147_NOT_QUALIFIED' and private['qualification'] == 'NOT_QUALIFIED' and
         private['private_qualification_gates_discharged'] == 0 and private['inputs_equal_before_after'] is True and
         private['inputs_before'] == private['inputs_after'] and len(private['inputs_before']) == 632 and
         private['identity_errors'] == [], 'private147 original failure/integrity differs')
    for step in private['steps']:
        receipt(step['log'])
    plog = p['s2c-private-native-20261105-147/simulation.log'].decode()
    need('Timing violation' in plog and 'XU_CANDIDATE_REJECT unknown commit/FIFO ownership state' in plog and
         private['final_qualification_gate'] not in plog and
         private['error']['message'] == 'mandatory terminal qualification gate not reached exactly once',
         'private147 mandatory rejection evidence differs')
    stream = js('s2e-native-pin-streamaudit-20261105-156/state.json')
    need(stream['status'] == 'FAIL_DIAGNOSTIC_NOT_QUALIFIED' and stream['tasks'] == [] and
         stream['current_task_id'] == 0 and stream['current_phase'] == 'before' and
         stream['error'] == 'ValueError: complete source-report streaming identity differs' and
         'complete source-report streaming identity differs' in p['s2e-native-pin-streamaudit-20261105-156/failure.txt'].decode(),
         'stream156 original identity failure differs')
    return dict(schema='xu-failed159-independent-audit-v1', qualification='NOT_QUALIFIED',
        original_payload_files=232, original_payload_bytes=46315396,
        observation_epoch=live['epoch'], historical_queue_status_counts=dict(Counter(expected.values())),
        historical_status_by_job=expected, locally_matched_output_receipts=len(checked),
        immutable24_registrations_equal157=True, append_only_events_preserved=True,
        historical_live_controller=state['controller_identity'], historical_live_pe64=running,
        activity=activity, timing155=dict(status=timing['status'], frozen_before_after_equal=204,
            native_phases=native, formal_passing=42338, total_checks=298878, untested_checks=27217,
            remaining_electrical=timing['remaining_electrical'], timing_slack_original=timing['timing'],
            final_mapped_receipts=timing['final_outputs']),
        private147=dict(status=private['status'], inputs_equal_before_after=632, gates_discharged=0,
                        mandatory_rejection='unknown commit/FIFO ownership state'),
        stream156=dict(status=stream['status'], task=0, phase='before', error=stream['error']),
        limitations=['Immutable159 historical process observations do not prove current liveness.',
            'External original input bodies, mapped/SVF files and two large native-cell reports are server receipts only.',
            'Five155 phases adopt134 original executions; only final DC/PT/FM are new155 native executions.',
            'No runtime repair, qualification waiver, score, full timing or energy acceptance is inferred.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-results', action='store_true')
    args = parser.parse_args()
    if not args.write_results:
        manifest = json.loads((HERE / 'input-manifest.json').read_text())
        for name, row in manifest['files'].items():
            need(ident((HERE / name).read_bytes()) == row, 'local delivery identity differs: ' + name)
    payload = package(HERE / 'xu-server-failed-campaign-20261105-159.tar.xz', 867328,
        '676da6baf9142f6e7f234a0c6e870e9229102dcab73bf083ff3c20316fd128d1', 232, 46315396)
    history = package(HERE.parent / 'xu-score-campaign157-20261105/xu-server-autonomous-campaign-20261105-157.tar.xz',
        591260, '37a340dc1d24f0d6b7eecc0194a492fee6077953818dea141b25021e4f30fe18', 167, 40767862)
    result = audit(payload, history)
    raw = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode()
    target = HERE / 'analysis159.json'
    if args.write_results:
        need(not target.exists(), 'fresh independent159 analysis required')
        target.write_bytes(raw)
    else:
        need(target.read_bytes() == raw, 'saved independent159 analysis differs')
    print(json.dumps(dict(status='ACTUAL159_FAILURES_AND_COMPLETE155_NATIVE_FM_VERIFIED',
        qualification='NOT_QUALIFIED', activity_failed=6, historical_pe64='RUNNING', formal_passing=42338), sort_keys=True))


if __name__ == '__main__':
    main()
