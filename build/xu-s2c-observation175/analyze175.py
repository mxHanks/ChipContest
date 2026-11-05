#!/usr/bin/env python3
"""Independent read-only analysis of actual167 in verified progress174.

No EDA, remote operation, source change, timing suppression or synthetic native
result. Server input receipts and source snapshots remain distinct evidence.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FOLDER = 's2c-passive-unknown-20261105-167'
ARCHIVE_SHA = 'df0166018b47d6ad78917928f23fc77c5a32213b8f386b56610f4e67fa64dfd4'
STATE_SHA = '028a40005f70a622ff751933c88af3de475037d4b663ade38339093f391bfe8e'
LOG_SHA = '6cc4f79e52fd9dcc809cdcbeb848e92ac6708e2317ef22dca720d0714f82b656'
MAPPED_SHA = '9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
FATAL = 'XU_CANDIDATE_REJECT unknown commit/FIFO ownership state'
SEMANTICS = 'CALLBACK_DISPATCH_ORDER_ONLY_NOT_CAUSALITY_OR_VPI_SCHEDULER_PHASE'
EVENT_RE = re.compile(r'^XU_UNKNOWN167_EVENT serial=(\d+) tick_fs=(\d+) reason=(\S+) role=(\S+) bits=(\d+) aval=([0-9a-f]{16}) bval=([0-9a-f]{16}) name=(\S+)$')


def need(ok, text):
    if not ok:
        raise ValueError(text)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def identity(path):
    p = Path(path)
    need(p.is_file() and not p.is_symlink(), 'regular evidence file required')
    return dict(path=str(p), bytes=p.stat().st_size, sha256=sha(p))


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def four_state(a, b, width):
    aval, bval = int(a, 16), int(b, 16)
    return ''.join(('x' if (aval >> i) & 1 else 'z') if (bval >> i) & 1 else
                   str((aval >> i) & 1) for i in range(width - 1, -1, -1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, default=ROOT / 'build/xu-score-resume-20261103/progress174')
    parser.add_argument('--archive', type=Path, default=ROOT / 'build/xu-score-resume-20261103/xu-server-two-candidate-progress-20261105-174.tar.xz')
    parser.add_argument('--out', type=Path, default=HERE)
    args = parser.parse_args()
    evidence = args.evidence_root.resolve(); source = evidence / FOLDER
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    need(identity(args.archive)['sha256'] == ARCHIVE_SHA and args.archive.stat().st_size == 188212, 'actual174 archive identity differs')
    manifest = read(evidence / 'manifest.json')
    need(len(manifest['files']) == 74 and sum(r['bytes'] for r in manifest['files']) == 5260127, 'actual174 payload totals differ')
    copied = {}
    for r in manifest['files']:
        name = PurePosixPath(r['path'])
        need(not name.is_absolute() and '..' not in name.parts and str(name) == r['path'], 'unsafe payload path')
        need(r['path'] not in copied, 'duplicate payload path')
        local = evidence / r['path']; actual = identity(local)
        need(actual['sha256'] == r['sha256'] and actual['bytes'] == r['bytes'], 'copied174 payload changed')
        copied[r['path']] = actual
    need(sha(source / 'state.json') == STATE_SHA and sha(source / 'simulation.log') == LOG_SHA, 'actual167 terminal/log changed')
    state = read(source / 'state.json'); log = (source / 'simulation.log').read_text(); lines = log.splitlines()
    need(state['status'] == 'COLLECTED_ORIGINAL_UNKNOWN_FATAL167_NOT_QUALIFIED' and state['qualification'] == 'NOT_QUALIFIED', 'unexpected167 status')
    need(state['inputs_equal_before_after'] is True and state['identity_errors'] == [] and
         state['inputs_before'] == state['inputs_after'] and len(state['inputs_before']) == 634, 'server634 input receipts differ')
    input_map = {r['input_path']: r for r in state['inputs_before']}
    target_rows = [r for r in input_map.values() if r['path'].endswith('s2c/ppa/mapped.v')]
    need(len(target_rows) == 1 and target_rows[0]['sha256'] == MAPPED_SHA, 'ownS2c mapped target differs')
    own_mapped = target_rows[0]
    # Earlier readonly123 already preserved the parsed identifier components.
    # A literal dot in the escaped instance dp_gt0.vec_31_dfflr is not another
    # hierarchy boundary: never convert every VPI display dot to a PT slash.
    static_root = ROOT / 'build/xu-score-resume-20261103/function129/mapped-connectivity-20261105-123'
    static_state = read(static_root / 'state.json'); connectivity = read(static_root / 'connectivity.json')
    need(static_state['status'] == 'EXTRACTED_FROZEN_MAPPED_CONNECTIVITY123_NOT_QUALIFIED' and
         static_state['inputs_equal_before_after'] is True and static_state['identity_errors'] == [] and
         static_state['inputs_before'] == static_state['inputs_after'], 'historical123 readonly receipts differ')
    static_mapped = [r for r in static_state['inputs_before'] if r['path'] == own_mapped['path']]
    need(static_mapped == [own_mapped] and static_state['result']['sha256'] == sha(static_root / 'connectivity.json'),
         'historical123 graph is not bound to same own9c16')
    target_components = connectivity['target_cell']['instance']
    need(target_components[-2:] == ['dp_gt0.vec_31_dfflr', 'qout_r_reg[0]'] and
         connectivity['target_cell']['type'] == 'DRNQV0_12TR40', 'native target components/ref differ')
    original_power = read(ROOT / 'build/xu-score-resume-20261103/next-results-export-69/s2c-full-soc-power12-20261104-57/prepared.json')
    need(original_power['netlist']['sha256'] == MAPPED_SHA and
         original_power['analysis_sdc']['sha256'] == '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98',
         'ownS2c analysis input provenance differs')
    steps = state['steps']; need([r['name'] for r in steps] == ['vpi-build', 'vcs-build', 'simulation'] and
        all(r['status'] == 'EXITED' and r['returncode'] == 0 for r in steps), 'native167 steps not terminal rc0')
    for step in steps:
        local = source / Path(step['log']['path']).name
        need(sha(local) == step['log']['sha256'] and local.stat().st_size == step['log']['bytes'], 'native log receipt mismatch')
    need(not any('notimingcheck' in a or 'nospecify' in a for step in steps for a in step['command']), 'timing suppression present')
    tb = (source / 'tb_private147.sv').read_text()
    fatal_lines = [i for i, line in enumerate(tb.splitlines(), 1) if '$fatal(1,"' + FATAL + '")' in line]
    fatal_re = (r'^Fatal: "([^"\n]+)", (\d+): ([^\n]+): at time (\d+) fs\n([^\n]+)\n'
                r'\$finish called from file "([^"\n]+)", line (\d+)\.\n\$finish at simulation time\s+(\d+)\n')
    fatal = re.findall(fatal_re, log, re.M)
    tb_ref = next(r for r in input_map.values() if r['path'].endswith('/' + FOLDER + '/tb_private147.sv'))
    need(len(fatal) == 1 and len(fatal_lines) == 1 and len(re.findall(r'^(?:Fatal|FATAL):', log, re.M)) == 1, 'native fatal not unique')
    f = fatal[0]
    need(f[0] == f[5] == tb_ref['path'] and int(f[1]) == int(f[6]) == fatal_lines[0] == 214 and
         f[4] == FATAL and int(f[3]) == int(f[7]) == 9359423333333, 'native fatal source/line/message/time differs')
    # Prove the actual generated source still matches the approved pure
    # transformation of original147, rather than trusting the terminal label.
    adapter = ROOT / 'build/xu-s2c-unknown167/unknown167.py'
    spec = importlib.util.spec_from_file_location('xu175_reviewed167_contract', str(adapter))
    u = importlib.util.module_from_spec(spec); spec.loader.exec_module(u)
    need(sha(adapter) == '241fd58249e872ab0c06faa107b6e33221cc4b2622c7b267882cf95a8517a011', 'reviewed167 producer changed')
    original147 = ROOT / 'build/xu-score-resume-20261103/serverfailed159/s2c-private-native-20261105-147/tb_private147.sv'
    original_tb = original147.read_text()
    need(tb == u.tb_instrument(original_tb), 'actual167 TB is not the exact reversible approved147 transform')
    need(re.findall(r'\$fatal\(1,"([^"\n]*)"', tb) == re.findall(r'\$fatal\(1,"([^"\n]*)"', original_tb) and
         len(re.findall(r'\$fatal\(1,"([^"\n]*)"', tb)) == 87 and
         re.findall(r'always\s*@\([^\n]+', tb) == re.findall(r'always\s*@\([^\n]+', original_tb) and
         tb.count('$xu_private147_sample(') == 3, '87fatal/3edges/3samplers changed')
    m147 = u.load147(ROOT / 'build/xu-campaign-batch154/private147')
    need((source / 'xu_private147.c').read_text() == u.c_instrument(m147.generate_c()), 'actual167 C differs from original147 plus passive observer')
    observer = (adapter.parent / 'observer167.c.in').read_text()
    need(not re.search(r'\bvpi_put_value\s*\(|\bvpi_control\s*\(|vpiForceFlag|cbReadWriteSynch|cbAfterDelay', observer), 'new observer changes DUT or scheduling')
    for name in ['unknown167.py', 'observer167.c.in']:
        refs = [r for r in input_map.values() if r['path'].endswith('/xu-s2c-unknown167/' + name)]
        need(len(refs) == 1 and refs[0]['sha256'] == sha(adapter.parent / name), 'server producer receipt mismatch')
    binds, _ = u.observer_bindings(log)
    need(len(binds) == 131, 'actual native131 binding count differs')
    need(log.count('XU_UNKNOWN167_SCOPE index=2 definition=DRNQV0_12TR40 name=' + u.TARGET + '\n') == 1,
         'actual native target cell definition differs')
    events = []
    for number, line in enumerate(lines, 1):
        match = EVENT_RE.fullmatch(line)
        if match:
            q = match.groups(); event = dict(serial=int(q[0]), tick_fs=int(q[1]), reason=q[2], role=q[3], bits=int(q[4]),
                aval=q[5], bval=q[6], name=q[7])
            events.append(event)
    need(events == state['observed_events'] and len(events) == 566 and
         [e['serial'] for e in events] == list(range(1, 567)), 'raw566 events differ from terminal state')
    for event in events:
        event['four_state'] = four_state(event['aval'], event['bval'], event['bits'])
        event['source_line'] = next(i for i, line in enumerate(lines, 1) if line.startswith('XU_UNKNOWN167_EVENT serial=%d ' % event['serial']))
    initial = [e for e in events if e['reason'] == 'first_observed_window_event']
    final = [e for e in events if e['reason'] == 'before_original_unknown_fatal']
    changes = [e for e in events if e['reason'] == 'value_change']
    need(len(initial) == len(final) == 131 and len(changes) == 304 and
         {e['name'] for e in initial} == {e['name'] for e in final} == {r[3] for r in binds}, 'full native snapshots not bijective')
    need({e['tick_fs'] for e in initial} == {9359300000000} and {e['tick_fs'] for e in final} == {9359423333333}, 'snapshot times differ')
    trigger = re.findall(r'^XU_UNKNOWN167_TRIGGER tick_fs=(\d+) (.*)$', log, re.M)
    need(len(trigger) == 1 and int(trigger[0][0]) == int(f[3]), 'task-local trigger missing')
    local_values = dict(re.findall(r'(\w+)=([01xz]+)', trigger[0][1]))
    native_values = {name: next(e['four_state'] for e in final if e['role'] == name) for name, _, _ in u.EIGHT}
    tb_values = {name: next(e['four_state'] for e in final if e['name'] == 'tb_xu_soc_ppa.' + target) for name, target, _ in u.EIGHT}
    need(local_values == native_values == tb_values == state['original_unknown_values'] == state['native_values_at_original_fatal'] ==
         state['tb_values_at_original_fatal'], 'fatal task-local/native/sampled state differs')
    need([name for name, value in local_values.items() if re.search('[xz]', value)] == ['bias_commit'] and
         state['current_native_vs_sampled_differences'] == [] and state['unknown_operands'] == ['bias_commit'], 'unknown classification differs')
    def picked(reason, role=None, suffix=None):
        found = [e for e in events if e['reason'] == reason and (role is None or e['role'] == role) and
                 (suffix is None or e['name'].endswith(suffix))]
        need(len(found) == 1, 'expected unique event differs'); return found[0]
    initial_target = {role: picked('first_observed_window_event', role)['four_state'] for role in ['fifo_CK', 'fifo_D', 'fifo_Q', 'fifo_NOTIFIER']}
    need(initial_target == dict(fifo_CK='1', fifo_D='0', fifo_Q='0', fifo_NOTIFIER='x'), 'initial target snapshot differs')
    hold_blocks = []
    for i, line in enumerate(lines):
        if 'Timing violation in ' in line:
            actual_scope = re.sub(r'\s+', '', line.split('Timing violation in ', 1)[1]).replace('\\', '')
            hold_blocks.append(dict(source_line=i + 1, header=line, detail=lines[i + 1], canonical_scope=actual_scope))
    target_hold = [r for r in hold_blocks if r['canonical_scope'] == u.TARGET]
    need(len(target_hold) == 1 and target_hold[0]['detail'].count('9359390050000') == 2 and
         'limit: 10000' in target_hold[0]['detail'], 'target native CK/D coincident hold block differs')
    onset = {}
    for role in ['fifo_D', 'fifo_Q', 'bias_commit']:
        onset[role] = next(e for e in changes if e['role'] == role and re.search('[xz]', e['four_state']))
    notifier = next(e for e in changes if e['role'] == 'fifo_NOTIFIER')
    need(onset['fifo_Q']['tick_fs'] == 9359390060000 and onset['bias_commit']['tick_fs'] == 9359416896667 and
         notifier['tick_fs'] == 9359390050000 and notifier['four_state'] == '0', 'key native observations differ')
    done = re.findall(r'^XU_UNKNOWN167_SNAPSHOT_DONE nodes=131 failed=0 tick_fs=9359423333333 original_fatal_retained=1 NOT_QUALIFIED$', log, re.M)
    need(len(done) == 1 and state['callback_serial_semantics'] == SEMANTICS and state['notifier_causality'] == 'NOT_PROVEN', 'observation semantics differ')
    snapshot = read(evidence / 'snapshot171.json')
    captures = [r for r in snapshot['captures'] if r['archive_path'].startswith(FOLDER + '/')]
    need(len(captures) == 9 and all(r['metadata_unchanged_during_read'] is True for r in captures), 'source167 capture metadata unstable')
    for r in captures:
        need(copied[r['archive_path']]['sha256'] == r['observed_bytes_sha256'] and
             copied[r['archive_path']]['bytes'] == r['bytes_observed'], 'snapshot source bytes differ from archive bytes')
    live = [r for r in snapshot['live_process_observations'] if r.get('name') == 's2c_unknown167']
    need(len(live) == 1 and live[0]['queue_status'] == 'COMPLETED_DIAGNOSTIC_NOT_QUALIFIED' and live[0]['actual'] is None, '174 process observation differs')
    absent_markers = ['XU_TASK_CLEAR_OBSERVED', 'XU_SOURCE_REQUEST', 'XU_SOURCE_ACCEPT',
                      'XU_CANDIDATE_UPLOAD_PASS', 'TASK_PASS', 'SOC_PASS']
    need(all(marker not in log for marker in absent_markers), 'unexpected task completion marker')
    boundary = {name: re.findall(r'^' + name + r' (.*)$', log, re.M) for name in ['XU_TASK_CLEAR_BEGIN', 'XU_TASK_CLEAR_LAST_WRITE']}
    timeline = [e for e in changes if e['role'] in ['fifo_D', 'fifo_Q', 'fifo_NOTIFIER', 'bias_commit'] or
        (e['role'] == 'target_net' and e['name'].endswith('.n0')) or
        (e['role'] == 'shared_port' and not e['name'].endswith('.clk')) or
        (e['role'] == 'fifo_net' and e['name'].endswith(('.o_vld', '.i_vld', '.o_rdy', '.dp_gt0.vec_r_0'))) ]
    save(out / 'events175.json', dict(schema='xu-s2c-native167-events175-v1', qualification='NOT_QUALIFIED',
        source_log=identity(source / 'simulation.log'), semantics=SEMANTICS, events=events))
    report = dict(schema='xu-s2c-native-observation175-v1', status='INDEPENDENT_ACTUAL167_ANALYSIS_COMPLETE_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
        archive=identity(args.archive), verified_copied_payload_files=len(copied), verified_copied_payload_bytes=5260127,
        own_s2c_mapped_target_server_receipt=own_mapped, actual167_source_files=[copied[r['archive_path']] for r in captures],
        source_snapshot_metadata=captures, snapshot_semantics=snapshot['all_copies_are_observations_not_terminal_freezes'],
        source_capture_limit='Nine167 source metadata observations were unchanged while copied; this does not make remote sources terminal freezes.',
        server_input_receipts=dict(before_after_equal=True, count=634, identity_errors=[],
            limitation='634 server receipts independently compared as recorded; unreturned server files were not locally rehashed.'),
        native_steps=[dict(name=s['name'], returncode=s['returncode'], log=s['log']) for s in steps],
        original_native_fatal=dict(message=FATAL, source=f[0], source_line=214, scope=f[2], tick_fs=int(f[3]), simulator_returncode=0,
            meaning='Mandatory rejection reproduced; simulator rc0 is not function/qualification success.'),
        retained_source_checks=dict(identical_approved167_transforms=True, original147_fatals=87, original_always_edges=3, original_sample_calls=3,
            new_observer_dut_writes=0, timing_suppression=False),
        native_bindings=131, event_counts=dict(Counter(e['reason'] for e in events)),
        fatal_eight_signals=[dict(logical=n, width=w, task_local=local_values[n], tb_sampled=tb_values[n], current_native=native_values[n]) for n, _, w in u.EIGHT],
        fatal_native_sampled_differences=[], unknown_fatal_operands=['bias_commit'],
        initial_target=initial_target,
        initial_native_tb_differences=[dict(logical=n, current_native=picked('first_observed_window_event', n)['four_state'],
            tb_sampled=picked('first_observed_window_event', suffix='.' + t)['four_state']) for n, t, _ in u.EIGHT
            if picked('first_observed_window_event', n)['four_state'] != picked('first_observed_window_event', suffix='.' + t)['four_state']],
        initial_unknown_nodes=[e for e in initial if re.search('[xz]', e['four_state'])],
        final_unknown_nodes=[e for e in final if re.search('[xz]', e['four_state'])],
        shared_ports=[dict(name=name, initial=picked('first_observed_window_event', 'shared_port', '.' + name)['four_state'],
            fatal=picked('before_original_unknown_fatal', 'shared_port', '.' + name)['four_state'],
            transitions=[e for e in changes if e['role'] == 'shared_port' and e['name'].endswith('.' + name)]) for name in u.SHARED],
        target_cell_definition='DRNQV0_12TR40', native_target_hold=target_hold[0], native_timing_violation_count=len(hold_blocks),
        historical_same_mapped_static123=dict(state=identity(static_root / 'state.json'),
            graph=identity(static_root / 'connectivity.json'), target_cell=connectivity['target_cell'],
            target_q_to_fifo_o_vld=connectivity['target_q_to_fifo_o_vld'], limits=connectivity['important_limits'],
            semantics='Previously frozen same9c16 static potential connectivity; not a new native timing or Boolean sensitization proof.'),
        target_first_unknown_observations=onset, target_notifier_first_observed_change=notifier,
        notifier_to_q_x_fs=onset['fifo_Q']['tick_fs'] - notifier['tick_fs'],
        q_x_to_bias_x_fs=onset['bias_commit']['tick_fs'] - onset['fifo_Q']['tick_fs'],
        bias_x_to_fatal_fs=int(f[3]) - onset['bias_commit']['tick_fs'],
        timeline=timeline, source_clear_boundary=boundary, absent_completion_markers=absent_markers,
        recorded_process_observation=live[0], callback_semantics=SEMANTICS, notifier_causality='NOT_PROVEN',
        observations=[
            'Only bias_commit is x at fatal; task-local, original TB sample and current native value agree for all eight signals.',
            'Target Q starts known0 in this observation window; its first observed x is after native coincident CK/D hold warning. Initial NOTIFIER=x and invalid shared rsp_rdata=x are recorded, not called first faults.',
            'Notifier->internal n0->Q and later protocol/bias unknown observations are temporally consistent with hold-model contamination, but callback serial order cannot prove scheduler phase or connectivity/causality.',
            'Earlier transient D=x and already-unknown invalid/unused data are retained; unknown histories before the observation window and unobserved nodes remain unresolved.',
            'No XU_TASK_CLEAR_OBSERVED/source request/task pass occurred; this rejects qualification before the formal task window.'],
        next_minimal_readonly_query=dict(target=own_mapped, same_map_required=True, implementation_status='PROPOSED_ONLY_NOT_IMPLEMENTED_OR_RUN',
            priority=['Identify exact D driver cell/net, actual CK source/clock path and reset/ENABLE_RDN state on own9c16.',
                'Run own9c16 native minimum-delay report to this exact D pin with the original S2c libraries/SDC/clock method; include full data/clock path and actual pin arcs. Do not borrow baseline116 or S2e155.',
                'Read exact frozen DRNQV0_12TR40 specify/UDP relationship for NOTIFIER/n0/Q on the server, preserving model SHA; no model or testbench edits.',
                'Trace native connectivity from target Q through observed FIFO protocol to io_cacheWriteEnable, naming any unobserved boundary; observations alone do not prove this path.'],
            target_vpi_display=u.TARGET, target_identifier_components=target_components,
            target_pt_cell_candidate='/'.join(target_components),
            target_pt_pin_candidates={p: '/'.join(target_components) + '/' + p for p in ['D', 'CK', 'Q', 'RDN']},
            candidate_names_require_native_uniqueness_check=True,
            identifier_rule='Preserve literal dp_gt0.vec_31_dfflr and qout_r_reg[0]; never dot-to-slash replacement or unreviewed wildcard matching.',
            own_s2c_sdc=original_power['analysis_sdc'],
            own_s2c_libraries=original_power['implementation_controls']['libraries'],
            clock_method='Reconstruct and explicitly freeze the ownS2c original analysis clock method. No inheritance from baseline116 or155; if a new method is explored, label it an independent experiment.',
            inputs_to_freeze=['original S2c mapped9c16 bytes', 'original S2c analysis SDC and explicit clock scope/method',
                'same standard/SRAM SS library bytes and native PT executable', 'target DRNQV0_12TR40 Verilog model SHA', 'query source and exact pin names'],
            constraints=['No TB sampling changes', 'No force, DUT initialization, two-state conversion or timing-check suppression',
                'No arbitrary inserted delay', 'No new EDA job launched by175 analysis', 'New native work must use the existing single-slot controller']),
        limitations=['This analysis is not function, full150MHz, storage or energy qualification.',
            'Times are native fs and callback serials are dispatch order only. The observer did not label event scheduler phases.',
            'Only the target cell/fifo top and12shared ports were observed, not the entire native driver/clock/protocol cone.',
            'No SDF annotation or complete STA proof is inferred from the library-model VCS hold warning.',
            'No production source, original evidence or server process was modified.'])
    save(out / 'analysis175.json', report)
    print('XU175_INDEPENDENT_ANALYSIS_PASS_NOT_QUALIFIED events=566 nodes=131 fatal_unknown=bias_commit')
    print('analysis175_sha256=' + sha(out / 'analysis175.json'))


if __name__ == '__main__':
    main()
