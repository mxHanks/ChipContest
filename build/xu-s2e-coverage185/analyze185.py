#!/usr/bin/env python3
"""xu local analysis of original ownS2e155 reports. No EDA, mutation or remote IO."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FOLDER = 's2e-own-timing-repair-20261105-155'
SERVER = '/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/'
ACTIVITY = 's2e-formal-activity12-20261105-120'


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ident(path):
    path = Path(path)
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest())


def save(path, data):
    Path(path).write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')


def archive(path, expected_size, expected_sha, count, total, wanted):
    identity = ident(path)
    need(identity['bytes'] == expected_size and identity['sha256'] == expected_sha, 'original archive identity differs')
    actual, bodies = {}, {}
    with tarfile.open(str(path), 'r:xz') as tar:
        for member in tar:
            name = PurePosixPath(member.name)
            need(member.isfile() and not member.issym() and not member.islnk() and not member.sparse and
                 not name.is_absolute() and '..' not in name.parts and str(name) == member.name and
                 member.name not in actual and member.size <= 512 * 1024 * 1024, 'unsafe original member')
            h, size, chunks = hashlib.sha256(), 0, []
            stream = tar.extractfile(member)
            for part in iter(lambda: stream.read(1048576), b''):
                h.update(part)
                size += len(part)
                if member.name in wanted or member.name == 'manifest.json':
                    chunks.append(part)
            need(size == member.size, 'truncated original member')
            actual[member.name] = dict(path=member.name, bytes=size, sha256=h.hexdigest())
            if chunks:
                bodies[member.name] = b''.join(chunks)
    manifest = json.loads(bodies.pop('manifest.json'))
    need(isinstance(manifest, list) and len(manifest) == count, 'archive manifest schema/count')
    declared = {row['path']: row for row in manifest}
    actual.pop('manifest.json')
    need(len(declared) == len(actual) == count and declared == actual and
         sum(row['bytes'] for row in actual.values()) == total, 'every original payload SHA/size')
    need(set(bodies) == wanted, 'requested original body missing')
    return identity, actual, bodies


def coverage(raw):
    lines = raw.decode().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith('Constrained ')) + 3
    rows, block = [], []
    def append():
        if not block:
            return
        tokens = ' '.join(line for _, line in block).split()
        need(len(tokens) == 7 and tokens[5] == 'untested', 'unexpected coverage row layout')
        keys = ['constrained_pin', 'related_pin', 'clock', 'check_type', 'condition', 'slack_status', 'reason']
        row = dict(zip(keys, tokens))
        row['source_line'] = block[0][0]
        row['source_end_line'] = block[-1][0]
        # Slash is the native hierarchy separator; literal dots/brackets remain.
        m = re.fullmatch(r'(.+?)(?:\((rise|fall|high|low)\))?', tokens[0])
        row['pin'] = m.group(1)
        row['transition_or_level'] = m.group(2) or ''
        row['cell_hierarchy'] = row['pin'].rsplit('/', 1)[0] if '/' in row['pin'] else ''
        row['pin_leaf'] = row['pin'].rsplit('/', 1)[-1]
        row['scope_first_five_components'] = '/'.join(row['pin'].split('/')[:5])
        row['macro_group'] = macro_group(row['pin'])
        row['raw_block_sha256'] = digest(('\n'.join(line for _, line in block) + '\n').encode())
        rows.append(row)
    for number, line in enumerate(lines[start:], start + 1):
        if line and not line[0].isspace():
            append()
            block = [] if line == '1' else [(number, line)]
        elif block:
            block.append((number, line))
    append()
    summary = {}
    pattern = r'^(\w+)\s+(\d+)\s+(\d+)\s+\(\s*\d+%\)\s+(\d+)\s+\(\s*\d+%\)\s+(\d+)\s+\(\s*\d+%\)$'
    for line in lines[:start]:
        m = re.match(pattern, line)
        if m:
            summary[m[1]] = dict(total=int(m[2]), met=int(m[3]), violated=int(m[4]), untested=int(m[5]))
    all_checks = re.search(r'^All Checks\s+(\d+)\s+(\d+).*?\s+(\d+)\s+\(\s*\d+%\)\s+(\d+)\s+\(\s*\d+%\)$', raw.decode(), re.M)
    need(all_checks is not None, 'coverage total missing')
    totals = dict(total=int(all_checks[1]), met=int(all_checks[2]), violated=int(all_checks[3]), untested=int(all_checks[4]))
    need(sum(row['untested'] for row in summary.values()) == len(rows) == totals['untested'], 'detailed coverage count differs')
    return rows, summary, totals


def macro_group(pin):
    if pin.startswith('u_shared/storage/'):
        return 'shared_sram'
    if '/u_e203_itcm_ram/' in pin:
        return 'itcm_sram'
    if '/u_e203_dtcm_ram/' in pin:
        return 'dtcm_sram'
    if '/u_accel_icb_slave/' in pin and '/weightBanks/' in pin and '/macro/' in pin:
        return 'accelerator_weight_sram'
    return 'nonmacro_or_unclassified'


def grouped(rows, keys):
    counts = Counter(tuple(row[key] for key in keys) for row in rows)
    return [dict(dict(zip(keys, values)), count=count) for values, count in sorted(counts.items())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=HERE)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    root159 = ROOT / 'build/xu-score-resume-20261103/serverfailed159'
    selected = {FOLDER + '/state.json', FOLDER + '/repair-plan.json'}
    selected |= {str(path.relative_to(root159)) for path in (root159 / FOLDER / 'final').iterdir() if path.is_file()}
    selected |= {FOLDER + '/' + stage + '/analysis-coverage.rpt' for stage in ['original-inventory', 'posthold-inventory']}
    package159 = ROOT / 'docs/validation/xu-score-failed159-20261105/xu-server-failed-campaign-20261105-159.tar.xz'
    original159, payload159, data = archive(package159, 867328, '676da6baf9142f6e7f234a0c6e870e9229102dcab73bf083ff3c20316fd128d1',
                                           232, 46315396, selected)
    for name, raw in data.items():
        need((root159 / name).read_bytes() == raw, 'unpacked input differs from original archive: ' + name)
    state = json.loads(data[FOLDER + '/state.json'])
    need(state['status'] == 'EXECUTED_OWN_S2E_SAME_MAPPED_DC_PT_FULL_FM_NOT_QUALIFIED' and
         state['qualification'] == 'NOT_QUALIFIED' and state['frozen_before'] == state['frozen_after'] and
         state['frozen_input_errors'] == [], 'own155 terminal/frozen receipt differs')
    mapped = next(value for path, value in state['final_outputs'].items() if path.endswith('/mapped.v'))
    need(mapped['sha256'] == '3440182eca862290a874bedc4eb3f94168681a7028d584d15217a13dbeafa794', 'wrong own155 graph')
    def raw(name):
        return data[FOLDER + '/final/' + name]
    def text(name):
        return raw(name).decode()
    rows, summary, totals = coverage(raw('analysis-coverage.rpt'))
    need(totals == dict(total=298878, met=271661, violated=0, untested=27217), 'own155 coverage totals')
    reasons = Counter(row['reason'] for row in rows)
    need(reasons == Counter(constant_disabled=17672, no_clock=9219, false_paths=276, no_endpoint_clock=48, unknown=2), 'reason totals')
    rowtuple = lambda row: tuple(row[k] for k in ['constrained_pin', 'related_pin', 'clock', 'check_type', 'condition', 'slack_status', 'reason'])
    stage_comparison = {}
    for stage in ['original-inventory', 'posthold-inventory']:
        previous, _, _ = coverage(data[FOLDER + '/' + stage + '/analysis-coverage.rpt'])
        a, b = Counter(map(rowtuple, previous)), Counter(map(rowtuple, rows))
        stage_comparison[stage] = dict(untested=len(previous), added=sum((b-a).values()), removed=sum((a-b).values()))
    check_lines = text('check-timing.rpt').splitlines()
    check_groups, group = {}, ''
    for number, line in enumerate(check_lines, 1):
        m = re.match(r"Information: Checking '([^']+)'", line)
        if m:
            group = m[1]
        if line.startswith(('u_soc/', 'io_')):
            check_groups.setdefault(group, []).append(dict(pin=line, source_line=number))
    missing = check_groups['no_clock']
    unconstrained = check_groups['unconstrained_endpoints']
    need(len(missing) == 24 and len(unconstrained) == 31, 'check_timing count')
    need(all(re.search(r'/u_perips_apb_uart[012]/fifo_tx_data_reg\[[0-7]\]/E$', x['pin']) for x in missing), 'UART missing-clock population')
    uart_cells = {x['pin'].rsplit('/', 1)[0] for x in missing}
    need(len(uart_cells) == 24 and
         {x['pin'] for x in unconstrained if '/fifo_tx_data_reg' in x['pin']} == {c + '/D' for c in uart_cells}, 'UART D/E matching')
    no_clock = [row for row in rows if row['reason'] == 'no_clock']
    need(Counter(row['constrained_pin'].rsplit('/',1)[-1] for row in no_clock) == Counter({'RDN(low)':8766, 'SDN(low)':429, 'E(high)':24}) and
         all(row['check_type'] == 'min_pulse_width' for row in no_clock), 'no_clock pin/check breakdown')
    unknown = [row for row in rows if row['reason'] == 'unknown']
    need(all(row['check_type'] == 'recovery' and row['clock'] == 'xu_lfextclk' and row['constrained_pin'].endswith('/SDN(rise)') for row in unknown), 'PMU recovery unknown')
    false = [row for row in rows if row['reason'] == 'false_paths']
    need(len({row['pin'] for row in false}) == 70 and all(row['pin'] in text('exceptions.rpt') for row in false), 'false-path target references')
    # Exact existing from/to selections: no new native query is performed.
    pairs = re.findall(r'set src \[get_(ports|pins) -quiet \{([^}]+)\}\]\nset dst \[get_pins -quiet \{([^}]+)\}\]', text('sta.tcl'))
    hf = []
    for kind, source, target in pairs:
        if kind == 'ports' and not any(row['target_pin'] == target for row in hf):
            hf.append(dict(source_object=source, target_pin=target))
    need(len(hf) == 5, 'five original HF reset selections')
    reset_rows = list(csv.DictReader(io.StringIO(text('reset-paths.tsv')), delimiter='\t'))
    need(len(reset_rows) == 16 and sum(row['source_kind'] == 'HF_RESET' and row['check'] == 'recovery' and
                                    row['count'] == '0' and row['status'] == 'NO_PATH_UNKNOWN' for row in reset_rows) == 5, 'HF no-path rows')
    need(all('No constrained paths.' in text('reset-%d-hf_reset-recovery.rpt' % i) for i in range(5)), 'HF raw no-path reports')
    pre_reset = list(csv.DictReader(io.StringIO(text('reset-preflight.tsv')), delimiter='\t'))
    constraints = text('constraints.rpt')
    caps = re.findall(r'Pin: (\S+)\s+Capacitance\s+([\d.]+)\s+- min_capacitance\s+([\d.]+).*?Slack\s+(-?[\d.]+) \(VIOLATED\)', constraints, re.S)
    need(len(caps) == 3 and {x[0] for x in caps} == set(state['remaining_electrical']), 'PLIC mincap gates')
    warnings = [dict(source_line=n, text=line) for n,line in enumerate(text('pt.log').splitlines(),1) if line.startswith(('Warning:', 'Error:', 'Fatal:'))]
    need(not any(x['text'].startswith(('Error:', 'Fatal:')) for x in warnings), 'original155 native error unexpectedly present')
    # Original120 reset evidence is RTL/internal ACCEL.rst_n, not own155 async pins.
    wanted125 = {ACTIVITY + '/result.json'} | {ACTIVITY + '/task_%02d/%s' % (i,n) for i in range(12) for n in ['result.json','simulation.log']}
    package125 = ROOT / 'docs/validation/xu-score-s2e-activity120-server125-20261105/payload.tar.xz'
    original125, payload125, activity = archive(package125, 8171768, 'ebfba2f46193dca30362ccce4fbbe602be238abd21a316240da0da2f828fbf10',
                                               88, 465539700, wanted125)
    readiness = []
    for i in range(12):
        name = ACTIVITY + '/task_%02d/result.json' % i
        record = json.loads(activity[name])['activity_window']['accelerator_reset_readiness']
        log = activity[ACTIVITY + '/task_%02d/simulation.log' % i].decode()
        need(record['actual_reset_clock_edges'] == 4594 and 'actual_reset_clock_edges=4594' in log, 'capture120 reset sample receipt')
        readiness.append(dict(task_id=i, **record))
    fieldnames = list(rows[0])
    with (out / 'untested185.csv').open('w', newline='') as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    targets = dict(schema='xu-s2e185-exact-targets-v1', qualification='NOT_QUALIFIED', own_final_mapped=mapped,
                   own_sdc=state['frozen_before'][SERVER+'s2e-ppa-campaign-20261104-89/ppa/constraints.sdc'],
                   scope_method=next(value for path,value in state['frozen_before'].items() if path.endswith('/xu-ts16.tcl')),
                   own_libraries=[value for path,value in state['frozen_before'].items() if path.endswith('.db')],
                   uart_missing_clock=missing, unconstrained=unconstrained, pmu_unknown_recovery=unknown,
                   hf_recovery_queries=hf, reset_pre_repair_refs=pre_reset,
                   plic_min_capacitance=state['remaining_electrical'],
                   limits=['Only exact own155 objects may be queried; no borrowing baseline116 or S2c.',
                           'UART cell reference/latch identity remains to be confirmed natively; E naming alone is insufficient.',
                           'Constant-disabled/no-clock/false-path categories are not automatic waivers.',
                           'No changes to graph, constraints, scope method, model, TB, timing checks or reset initialization.'])
    save(out / 'targets185.json', targets)
    save(out / 'native-diagnostics185.json', dict(qualification='NOT_QUALIFIED', source_log=payload159[FOLDER+'/final/pt.log'], warnings_and_errors=warnings))
    consumed = [dict(source_archive='159', **payload159[name]) for name in sorted(selected)] + [dict(source_archive='125', **payload125[name]) for name in sorted(wanted125)]
    save(out / 'inputs185.json', dict(schema='xu-s2e185-input-manifest-v1', qualification='NOT_QUALIFIED',
                                    archives=[original159, original125], consumed_members=consumed,
                                    checked_archive_payloads=[dict(id='159',files=232,bytes=46315396),dict(id='125',files=88,bytes=465539700)],
                                    limitation='Returned bodies independently hashed; remote mapped/SDC/library/clock-helper bodies are identity receipts, not local rereads.'))
    disabled = [row for row in rows if row['reason'] == 'constant_disabled']
    minperiod = [row for row in disabled if row['check_type'] == 'min_period']
    need(len(minperiod) == 10416 and len({row['cell_hierarchy'] for row in minperiod}) == 336 and
         set(Counter(row['cell_hierarchy'] for row in minperiod).values()) == {31}, 'SRAM minperiod conditional population')
    gpio_unconstrained = {x['pin'] for x in unconstrained if x['pin'].startswith('io_pads_gpioA_o_oval[')}
    delay_refused = {m[1] for item in warnings for m in [re.search(r'Cannot set output delay on a clock port \(([^)]+)\)', item['text'])] if m}
    need(len(gpio_unconstrained) == 5 and gpio_unconstrained == delay_refused and
         all(pin in text('clocks.rpt') for pin in gpio_unconstrained), 'GPIO forwarded-clock diagnostic correlation')
    warning_codes = Counter(re.search(r'\(([A-Z]+-\d+)\)\s*$', x['text'])[1] for x in warnings)
    report = dict(schema='xu-s2e-own155-coverage185-v1', status='CLASSIFIED_ORIGINAL155_REPORTS_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
                  own_final_mapped_server_receipt=mapped, coverage_summary=summary, all_checks=totals,
                  reason_counts=dict(reasons), type_reason=grouped(rows,['check_type','reason']),
                  hierarchy_reason_counts=grouped(rows,['scope_first_five_components','reason']),
                  condition_reason_counts=grouped(rows,['condition','reason']),
                  untested_detail=dict(file='untested185.csv',records=len(rows),sha256=ident(out/'untested185.csv')['sha256'],
                                       semantics='Every original record retained in order, including duplicate endpoints/check conditions; literal dotted components preserved.'),
                  original_to_final_untested_multiset=stage_comparison,
                  no_clock_width_classes=grouped(no_clock,['pin_leaf','transition_or_level']),
                  library_width_constraint_evidence=[dict(pin_class=pin,level=level,untested_checks=count,
                       native_type='min_pulse_width',numeric_library_min_width=None,
                       numeric_hold_setup_constraint=None,
                       missing='These reports identify check category and pin, but contain no required library width/hold table value for this class. Need exact native ref/libpin/arc attributes on own155.',
                       existing_reset_evidence_applicability=('Internal RTL accelerator reset sampling is not a waveform proof at every final155 async pin.' if pin != 'E' else
                           'UART E high-width/clock-enable checks are not covered by accelerator reset sampling.'))
                       for pin,level,count in [('RDN','low',8766),('SDN','low',429),('E','high',24)]],
                  no_clock_correction='9219 is the native reason count for min_pulse_width: 8766 RDN(low),429 SDN(low),24 UART E(high). It is not 9219 missing register CK clocks. check_timing separately reports24 UART E clock pins without clocks.',
                  actual_missing_register_clock_pins=missing, actual_unconstrained_endpoints=unconstrained,
                  pmu_unknown_recovery=unknown, uart_native_ref_or_latch_identity='NOT_PROVEN_BY_RETURNED_159_BODIES; query native ref/is_level_sensitive/library pin next.',
                  false_paths=dict(checks=276,unique_pins=70,every_target_text_present_in_own_exceptions=True,policy='Recorded exceptions require their own CDC/mode justification; no automatic waiver.'),
                  constant_disabled=dict(checks=17672,macro_min_period_checks=10416,macro_instances=336,conditional_min_period_branches_per_macro=31,
                                         by_macro_group_and_type=grouped(disabled,['macro_group','check_type']),
                                         policy='A native disabled reason is mode-specific evidence, not proof all reachable modes or active library constraints are covered.'),
                  hf_reset_source_specific_queries=dict(rows=reset_rows,five_no_constrained_path_reports=True,
                       limit='Five source-specific empty recovery selections overlap the two PMU unknown targets; do not add them as five independent coverage unknowns. Filters/max-path/default constrained visibility remain possible display limits.'),
                  plic_min_capacitance=[dict(pin=p,load_pf=load,min_cap_pf=limit,slack_pf=slack) for p,load,limit,slack in caps],
                  gpio_forward_clock_diagnostics=dict(unconstrained_pins=sorted(gpio_unconstrained),
                       same_pins_named_in_clock_sources_and_refused_output_delay_warnings=True,
                       warning_code='UITE-485',
                       limit='Correlation with forwarded clock sources does not waive maximum-delay endpoint constraints or establish an accepted timing boundary.'),
                  unexpandable_clock_set=dict(count=1,reported_clocks=['xu_hfextclk','xu_jtag_tck','xu_lfextclk','xu_plldiv_envelope'],
                      source='check-timing.rpt unexpandable_clocks section; pt.log PTE-052/PTE-016. It is one set, not one newly discovered missing clock.'),
                  native_diagnostic_counts=dict(warnings=len(warnings),errors=0,fatals=0,warning_codes=dict(warning_codes)),
                  further_native_warning_limits=['PTE-003 says timing arcs were disabled by timing-loop breaking or constant propagation; the returned final package has no full report_disable_timing or case-value proof per arc.',
                      '18 PTE-060 warnings report no inferred clock-gating check on named pin pairs; the27 reported met gating checks do not by themselves prove those excluded pairs safe.',
                      'PTE-052 warns the common-base-period expansion limit can leave cross-clock paths unconstrained; the single failed clock set is not waived.',
                      'Six UITE-416 invalid-start-point warnings are retained with the LF watchdog source-specific path reports.'],
                  reset_width_evidence=dict(capture='original120 RTL/internal ACCEL.rst_n',readiness=readiness,
                     sampled_first_to_last_asserted_span_fs=readiness[0]['last_reset_tick']-readiness[0]['first_reset_tick'],
                     covered='4594 sampled asserted internal accelerator-reset clock edges and empty FIFO readiness at this RTL observation point.',
                     not_covered=['No per-final155 RDN/SDN/E physical pulse trace or minimum-width library table values are in these returned reports.',
                                  'The first/last sampled reset span is not a measured continuous pulse width at every mapped pin.',
                                  'The activity SAIF formal window begins after reset/clear; it cannot supply the startup async pulse traces.',
                                  'Neither readiness nor long asserted reset proves deassertion recovery/removal against each local clock.',
                                  'UART E high-width is an enable/clock issue; internal accelerator reset evidence does not cover it.',
                                  'No library numeric hold/min-pulse-width values for these untested RDN/SDN/E classes are returned; do not invent or compare an assumed 10ps value from another graph/model.']),
                  next_minimal_readonly_query=dict(implementation='PROPOSED_ONLY_NOT_IMPLEMENTED_OR_RUN_BY185', target_file='targets185.json',
                      frozen_inputs=['exact own155 final mapped3440182e bytes','own89 SDC404c7de9 bytes','scope45037c4a bytes and same method','same standard/SRAM SS libraries and PT executable','query source'],
                      steps=['Enumerate each UART cell, exact E/D pins, ref/library cell, level-sensitive/sequential attributes, case/constant values and driver/clock paths; do not create artificial clocks.',
                             'For RDN(low)/SDN(low)/E(high) populations, enumerate actual refs/libpins and native width/conditional arcs with supported owner/index/from/to attributes. Query constant/case/disable reasons and report active and untested checks separately; never timing_arc full_name.',
                             'For both PMU SDN recovery targets and five source-specific HF queries, preserve existing selection first, then independent unfiltered read-only visibility reports and exact clock/async arcs. Empty/untested remains unknown.',
                             'Report the five GPIO native clock-source roles and refused output-delay diagnostics; do not silently waive unconstrained endpoints.',
                             'For three PLIC Q pins retain native mincap/load/consumer facts and for the clock set retain actual periods/waveform expansion limits; no source/SDC fixes in this diagnosis.'],
                      runtime_policy='Existing controller only; one native slot, fresh output, immutable registrations and retained failure logs.'),
                  limitations=['Classification does not qualify complete150MHz, function, physical storage or energy.',
                               'Remote final mapped and native-cells bodies were not returned; do not claim independent local whole-netlist or UART-ref verification.',
                               'All original native warnings remain in native-diagnostics185.json and the original package; nothing is suppressed.',
                               'No graph, SDC, clock method, model, TB or production Chisel/RTL was edited; no new EDA or remote action.'])
    save(out / 'analysis185.json', report)
    print('XU185_CLASSIFIED_NOT_QUALIFIED rows=27217 no_clock_width=9219 missing_register_clock=24 unconstrained=31')


if __name__ == '__main__':
    main()
