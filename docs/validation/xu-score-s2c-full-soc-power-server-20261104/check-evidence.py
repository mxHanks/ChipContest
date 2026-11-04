#!/usr/bin/env python3
"""Replay the actual S2c 12-task diagnostic from shared immutable export69.

PASS means evidence/rounded report arithmetic integrity, never energy qualification.
The absent native PT per-pin reports and mapped SAIF are deliberately not replayed.
"""
import argparse
import copy
import csv
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
SHARED = ROOT.parent / 'xu-score-server-export69-20261104'
PREFIX = 's2c-full-soc-power12-20261104-57'
TASK_IDS = list(range(12))
DURATION = 6604373333334
CONFIG = '5b5cf619e8b0e5c2fc050abe8b589d5f7544a98eed174f4fc979bffe60fa6018'
NET = '9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
STD = 'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723'
RAM = 'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'
SDC = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
SMALL = ['pt.log', 'power.rpt', 'units.rpt', 'tool-version.rpt', 'switching-before.rpt',
         'switching-after.rpt', 'coverage-before.rpt', 'coverage-after.rpt',
         'measured-sram-pins.json', 'task-mapped-receipt.json', 'sram-power.rpt',
         'check-timing.rpt', 'power.tcl']
ERROR = re.compile(r'^\s*(?:Error:|Fatal:|XU_FATAL:)|^\s*(?:Error|Warning):.*\((?:PT-063|LNK-001|CMD-005)\)', re.I)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def parse_power(text):
    need(re.findall(r'^Design\s*:\s*(\S+)\s*$', text, re.M) == ['xu_soc_ppa_top'], 'power design must be complete SoC')
    for unit in ['Dynamic', 'Leakage']:
        need(re.findall(r'^\s*' + unit + r' Power Units\s*=\s*(\S+)\s+(\S+)\s*$', text, re.M) == [('1', 'W')],
             'native power units must be explicit watts')
    result = {}
    for key, label in [('switching', 'Net Switching Power'), ('internal', 'Cell Internal Power'),
                       ('leakage', 'Cell Leakage Power'), ('total', 'Total Power')]:
        hits = re.findall(r'^\s*' + label + r'\s*=\s*([0-9.eE+-]+)\s+\(', text, re.M)
        need(len(hits) == 1, 'missing/ambiguous native power: ' + key)
        value = Decimal(hits[0])
        need(value.is_finite() and value >= 0, 'nonfinite or negative native power')
        result[key + '_power_w'] = str(value)
    # Text is rounded independently; do not demand its components sum exactly.
    return result


def verify_completion(log, marker, execution):
    need(execution['returncode'] == 0, 'nonzero PT return code')
    need(execution['command'][1:] == ['-f', 'power.tcl'], 'actual PT command differs')
    need(log.splitlines().count(marker) == 1, 'missing or repeated independent completion line')
    need(not any(ERROR.search(line) for line in log.splitlines()), 'native PT error/fatal diagnostic')


def verify_inputs(prepared, execution, prepared_body):
    need(prepared['schema'] == 'xu-s2c-full-soc-power-prepared-v1', 'wrong preparation schema')
    need(execution['schema'] == 'xu-s2c-full-soc-power-execution-v1', 'wrong execution schema')
    need(prepared['qualification'] == execution['qualification'] == 'NOT_QUALIFIED', 'qualification must remain unresolved')
    need(execution['status'] == 'EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING', 'actual run not terminal diagnostic')
    need(prepared['requested_task_ids'] == execution['requested_task_ids'] == TASK_IDS, 'complete 12-task set required')
    need(prepared['taskset_complete'] is True and execution['taskset_complete'] is True, 'taskset incomplete')
    need([t['task_id'] for t in prepared['tasks']] == [t['task_id'] for t in execution['tasks']] == TASK_IDS, 'task order/identity differs')
    need(len(prepared['input_sha256']) == 367, 'frozen input count differs')
    need(prepared['input_sha256'] == execution['input_sha256_before'] == execution['input_sha256_after'], 'frozen server before/after inputs differ')
    need(execution['prepared']['sha256'] == execution['prepared_sha256_after'] == sha(prepared_body), 'actual prepared input identity differs')
    need(execution['tool']['sha256'] == execution['tool_sha256_after'], 'actual PT executable changed')
    need(execution['library_compiler_root'] == '/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5', 'LC environment differs')
    need(prepared['source_context']['main_commit'] == 'd276b55ffecbe8d620f9a361bf5d0859299ba7b5', 'candidate main source differs')
    need(prepared['source_context']['source_profile']['e203_commit'] == '49a9436e01ea8ceeead94242e4a99c16e31a0865', 'candidate child source differs')
    need(prepared['power_tool_context']['base']['main_commit'] == 'ad866b9185b0ee505e720cad51effa5853191a50', 'isolated power tool differs')
    need(prepared['original_capture_tool_context']['main_commit'] == '5e75581319f926642ee7dc214ad825f3564a8e39', 'original capture tool differs')
    need(prepared['netlist']['sha256'] == NET and prepared['analysis_sdc']['sha256'] == SDC, 'actual mapped netlist or SDC differs')
    need([v['sha256'] for v in prepared['implementation_controls']['libraries']] == [STD, RAM], 'actual original two DBs differ')
    need(prepared['original_capture_configuration_sha256'] == CONFIG, 'formal activity capture config differs')
    need(prepared['strip_path'] == 'tb_xu_soc_ppa/dut', 'annotation strip path differs')


def parse_switching(text):
    rows = [x for x in text.splitlines() if re.match(r'^\s*Nets\s+\d', x)]
    need(len(rows) == 2 and len(set(rows)) == 1, 'native repeated overall net source counts differ')
    values = re.findall(r'(\d+)\(([\d.]+)%\)', rows[0])
    need(len(values) == 10, 'native switching source columns differ')
    result = {k: int(v[0]) for k, v in zip(
        ['file', 'ssa', 'ssa_force_annotated', 'ssa_force_implied', 'sca', 'clock', 'default', 'propagated', 'implied', 'not_annotated'], values)}
    result['total'] = int(rows[0].split()[-1])
    need(sum(v for k, v in result.items() if k != 'total') == result['total'], 'net source counts do not conserve')
    result['file_percent_native'] = values[0][1]
    return result


def parse_coverage(text):
    need('Coverage is defined as the percent of nets with at least 1 toggle' in text, 'coverage semantics differ')
    hits = re.findall(r'^xu_soc_ppa_top\s+([\d.]+)\s+(\d+)\s+(\d+)\s*$', text, re.M)
    need(len(hits) == 1, 'overall toggle coverage missing/ambiguous')
    percent, covered, total = hits[0]
    return dict(at_least_one_toggle_percent_native=percent, at_least_one_toggle_nets=int(covered), total_nets=int(total))


def verify_pins(measured, task, receipt):
    pins = measured['pins']
    need(measured['status'] == 'MEASURED_ACTIVITY_NOT_POWER_QUALIFIED', 'measured inputs not marked unresolved')
    need(receipt == task['mapped_macro_bridge_receipt'], 'independent bridge receipt differs from frozen preparation')
    need(receipt['macro_count'] == 336 and receipt['mapped_pin_bit_count'] == 22512, 'mapped inventory dimensions differ')
    names = [v['mapped_path'] for v in pins]
    need(len(names) == len(set(names)) == 22512, 'missing/duplicate mapped measured pin')
    groups = {}
    expected = set(['CEN', 'CLK', 'GWEN', 'RET1N'] + ['A[%d]' % i for i in range(10)] +
                   ['D[%d]' % i for i in range(16)] + ['Q[%d]' % i for i in range(16)] +
                   ['WEN[%d]' % i for i in range(16)] + ['EMA[%d]' % i for i in range(3)] + ['EMAW[%d]' % i for i in range(2)])
    for pin in pins:
        macro, name = pin['mapped_path'].rsplit('/', 1)
        groups.setdefault(macro, set()).add(name)
        need(pin['kind'] == 'PORT' and pin['path'] == 'tb_xu_soc_ppa/dut/' + pin['mapped_path'], 'native pin source path/kind differs')
        need(all(type(pin[key]) is int and pin[key] >= 0 for key in ['T0', 'T1', 'TX', 'TC', 'IG']), 'invalid measured integer statistics')
        need(pin['T0'] + pin['T1'] + pin['TX'] == DURATION, 'measured pin dwell does not conserve task window')
    need(set(groups) == set(task['macro_names']) and len(groups) == 336 and all(x == expected for x in groups.values()), '67-pin native macro bijection differs')
    unknown = [v for v in pins if v['TX']]
    total = sum(v['TX'] for v in pins)
    need(total == measured['alias_unknown_bit_ticks'] == receipt['measured_unknown_bit_ticks'], 'measured/bridge unknown dwell differs')
    need(all(v['mapped_path'].rsplit('/', 1)[-1].startswith('Q[') for v in unknown), 'unexpected unknown macro input')
    return dict(measured_input_pin_bits=len(pins), macro_count=len(groups), unknown_q_bits=len(unknown),
                all_window_unknown_q_bits=sum(v['TX'] == DURATION for v in unknown), unknown_q_bit_ticks=total)


def task_review(task, actual, data):
    ident = task['task_id']
    base = PREFIX + '/task_%02d/' % ident
    body = lambda name: data[base + name]
    text = lambda name: body(name).decode('utf-8')
    verify_completion(text('pt.log'), task['completion_marker'], actual['execution'])
    need(actual['status'] == 'EXECUTED_DIAGNOSTIC_REVIEW_PENDING', 'task execution status differs')
    window = task['activity_window']
    need(window['duration_ticks'] == DURATION and window['formal_elapsed_cycles'] == 990656 and window['formal_inclusive_cycles'] == 990657, 'formal task window differs')
    need(window['timescale_seconds'] == 1e-15 and window['end']['tick'] - window['begin']['tick'] == DURATION, 'formal fs task ticks differ')
    need(window['end']['cycle'] - window['begin']['cycle'] == 990656, 'elapsed cycles differ')
    need(window['pretask_clear']['accepted_writes'] == 33697 and window['pretask_clear']['verification_at_first_source_request'] is True, 'pretask clear policy differs')
    power = parse_power(text('power.rpt'))
    duration = Decimal(DURATION) * Decimal('1e-15')
    diagnostic = actual['diagnostic']
    need(diagnostic['qualification'] == 'NOT_QUALIFIED' and diagnostic['power_components'] == power, 'diagnostic/model power differs')
    need(Decimal(diagnostic['duration_seconds']) == duration, 'diagnostic duration differs')
    energy = Decimal(power['total_power_w']) * duration
    need(Decimal(diagnostic['diagnostic_energy_j']) == energy, 'rounded-power diagnostic energy arithmetic differs')
    need(text('tool-version.rpt').strip() == 'T-2022.03-SP5-1', 'actual native PT version differs')
    need(re.findall(r'^Time_unit\s*:\s*(\S+) Second\s*$', text('units.rpt'), re.M) == ['1e-09'], 'native library time unit differs')
    before = parse_switching(text('switching-before.rpt'))
    after = parse_switching(text('switching-after.rpt'))
    need(before == dict(file=49763, ssa=0, ssa_force_annotated=0, ssa_force_implied=0, sca=0, clock=0,
                        default=1132, propagated=0, implied=8435, not_annotated=86017, total=145347, file_percent_native='34.24'), 'before source coverage differs')
    need(after == dict(before, propagated=86017, not_annotated=0), 'after source coverage differs')
    coverage = parse_coverage(text('coverage-after.rpt'))
    need(coverage.pop('total_nets') == 145347, 'toggle coverage denominator differs')
    receipt = json.loads(body('task-mapped-receipt.json'))
    need(receipt['output_saif'] == task['saif'] and receipt['input_saif'] == task['canonical_saif'], 'mapped/canonical SAIF identities differ')
    measured = json.loads(body('measured-sram-pins.json'))
    pin_stats = verify_pins(measured, task, receipt)
    need(pin_stats == dict(measured_input_pin_bits=22512, macro_count=336, unknown_q_bits=5280,
                          all_window_unknown_q_bits=4256, unknown_q_bit_ticks=29636086623576352), 'actual measured unknown summary differs')
    macros = re.findall(r'^XU_SRAM_POWER_CELL name=(\S+) ref=(\S+)\s*$', text('sram-power.rpt'), re.M)
    need(len(macros) == 336 and {name for name, _ in macros} == set(task['macro_names']) and {ref for _, ref in macros} == {'RAMSP1024X16'}, 'actual macro power report coverage differs')
    need('28 endpoints which are not constrained for maximum delay' in text('check-timing.rpt'), 'same-netlist timing limitation changed')
    script = text('power.tcl')
    need('set_propagated_clock [all_clocks]' in script and 'set XU_CLOCK_MODE envelope' in script, 'actual propagated pre-CTS scenario differs')
    return dict(task_id=ident, formal_elapsed_cycles=990656, formal_inclusive_cycles=990657, duration_fs=DURATION,
                duration_seconds=str(duration), diagnostic_energy_j=str(energy), **power,
                file_nets=after['file'], default_nets=after['default'], propagated_nets=after['propagated'],
                implied_nets=after['implied'], not_annotated_nets=after['not_annotated'], total_nets=after['total'],
                file_percent_native=after['file_percent_native'], **coverage, **pin_stats,
                pt_log_sha256=sha(body('pt.log')), power_report_sha256=sha(body('power.rpt')),
                qualification='NOT_QUALIFIED')


def negative_checks(prepared, execution, prepared_body, data):
    checks = []
    def rejected(name, call):
        try:
            call()
        except (ValueError, KeyError):
            checks.append(name)
        else:
            raise ValueError('negative mutation was accepted: ' + name)
    task = prepared['tasks'][0]
    native_power = data[PREFIX + '/task_00/power.rpt'].decode()
    rejected('power-unit-W-to-mW', lambda: parse_power(native_power.replace('Dynamic Power Units = 1 W', 'Dynamic Power Units = 1 mW')))
    bad = copy.deepcopy(execution)
    bad['input_sha256_after'].pop(next(iter(bad['input_sha256_after'])))
    rejected('one-frozen-input-after-removed', lambda: verify_inputs(prepared, bad, prepared_body))
    marker = task['completion_marker']
    actual = execution['tasks'][0]['execution']
    log = data[PREFIX + '/task_00/pt.log'].decode()
    rejected('completion-only-Tcl-echo', lambda: verify_completion(log.replace('\n' + marker + '\n', '\nputs {' + marker + '}\n'), marker, actual))
    rejected('native-error-with-return-zero', lambda: verify_completion(log + '\nError: deliberate mutation\n', marker, actual))
    wrong = copy.deepcopy(actual)
    wrong['returncode'] = 1
    rejected('nonzero-native-return', lambda: verify_completion(log, marker, wrong))
    other = dict(data)
    mod = copy.deepcopy(task)
    mod['activity_window']['duration_ticks'] += 1
    rejected('formal-duration-one-fs-changed', lambda: task_review(mod, execution['tasks'][0], other))
    measured = json.loads(data[PREFIX + '/task_00/measured-sram-pins.json'])
    measured['pins'][0]['T0'] += 1
    rejected('measured-pin-dwell-nonconservation', lambda: verify_pins(measured, task, task['mapped_macro_bridge_receipt']))
    measured['pins'][0]['T0'] -= 1
    measured['alias_unknown_bit_ticks'] -= 1
    rejected('measured-unknown-dwell-changed', lambda: verify_pins(measured, task, task['mapped_macro_bridge_receipt']))
    other[PREFIX + '/task_00/power.rpt'] = native_power.replace('0.0348  (100.00%)', '0.0349  (100.00%)').encode()
    rejected('rounded-total-power-changed', lambda: task_review(task, execution['tasks'][0], other))
    return checks


def derived(data, manifest):
    prepared_body = data[PREFIX + '/prepared.json']
    prepared = json.loads(prepared_body)
    execution = json.loads(data[PREFIX + '/execution.json'])
    verify_inputs(prepared, execution, prepared_body)
    native = {row['path'][len(PREFIX) + 1:]: row for row in manifest if row['path'].startswith(PREFIX + '/')}
    need(len(native) == 362 and sum(v['bytes'] for v in native.values()) == 1350032481, 'selected actual export dimensions differ')
    missing = []
    for name, record in execution['artifacts'].items():
        if name in native:
            need(record['bytes'] == native[name]['bytes'] and record['sha256'] == native[name]['sha256'], 'execution/native artifact SHA differs: ' + name)
        else:
            missing.append(dict(relative_path=name, **record))
    need(set(execution['artifacts']) == (set(native) - {'execution.json'}) | {r['relative_path'] for r in missing}, 'artifact identity set differs')
    expected_missing = {'task_%02d/%s' % (i, name) for i in TASK_IDS for name in ['sram-pins-before.rpt', 'sram-pins-after.rpt', 'task-mapped.saif']}
    need({r['relative_path'] for r in missing} == expected_missing and len(missing) == 36, 'unreturned artifact boundary differs')
    for task, actual in zip(prepared['tasks'], execution['tasks']):
        for name, identity in actual['reports'].items():
            need(identity == execution['artifacts']['task_%02d/%s' % (task['task_id'], name)], 'nested native report identity differs')
        need(actual['execution']['log'] == execution['artifacts']['task_%02d/pt.log' % task['task_id']], 'nested native log identity differs')
        for key in ['script', 'measured_sram_pin_states', 'mapped_macro_bridge', 'saif']:
            record = task[key]
            name = record['path'].split('/' + PREFIX + '/', 1)[1]
            need(record == execution['artifacts'][name], 'prepared generated artifact differs from actual execution identity')
    rows = [task_review(t, a, data) for t, a in zip(prepared['tasks'], execution['tasks'])]
    energy = sum(Decimal(r['diagnostic_energy_j']) for r in rows)
    mean = sum(Decimal(r['total_power_w']) for r in rows) / Decimal(12)
    need(Decimal(execution['diagnostic_summary']['arithmetic_mean_reported_power_w']) == mean and
         Decimal(execution['diagnostic_summary']['sum_diagnostic_energy_j']) == energy, 'actual summary Decimal arithmetic differs')
    negative = negative_checks(prepared, execution, prepared_body, data)
    review = dict(status='PASS', meaning='Actual raw evidence integrity and diagnostic report arithmetic only',
                  qualification='NOT_QUALIFIED', task_count=12, frozen_inputs_before_after_equal=367,
                  actual_native_payload_count=362, actual_native_payload_bytes=1350032481,
                  unreturned_artifacts=len(missing), unreturned_pt_native_pin_reports=24, unreturned_mapped_saif=12,
                  same_configuration_sha256=CONFIG, same_original_mapped_netlist_sha256=NET,
                  same_duration_seconds=str(Decimal(DURATION) * Decimal('1e-15')),
                  sum_formal_elapsed_cycles=sum(r['formal_elapsed_cycles'] for r in rows),
                  arithmetic_mean_reported_power_w=str(mean), sum_diagnostic_energy_j=str(energy),
                  native_report_precision='Rounded native report text; products are reproducible arithmetic, not extra power precision',
                  pin_evidence='22,512 measured mapped-SAIF input pin records per task, not replay of unavailable PT pin attribute reports',
                  negative_mutations_rejected=negative)
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    selected = [dict(row, storage='../xu-score-server-export69-20261104/payload.tar.xz') for row in manifest if row['path'].startswith(PREFIX + '/')]
    return {'review.json': json_bytes(review), 'per-task-diagnostic.csv': stream.getvalue().encode(),
            'selected-native-index.json': json_bytes(selected), 'unreturned-server-artifacts.json': json_bytes(missing)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-derived', action='store_true', help='regenerate only derived local review/index/CSV')
    args = parser.parse_args()
    manifest = json.loads((SHARED / 'original-manifest.json').read_text())
    selected = [PREFIX + '/prepared.json', PREFIX + '/execution.json']
    selected.extend(PREFIX + '/task_%02d/%s' % (i, name) for i in TASK_IDS for name in SMALL)
    spec = importlib.util.spec_from_file_location('xu_shared_actual69', SHARED / 'check-evidence.py')
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    # The shared verifier streams all 435 raw payloads and validates every SHA.
    # Only roughly 120MB of review inputs are retained; no 1.37GB copy is made.
    data = shared.verify(selected=selected)
    result = derived(data, manifest)
    for name, body in result.items():
        if args.write_derived:
            (ROOT / name).write_bytes(body)
        else:
            need((ROOT / name).read_bytes() == body, 'committed derived evidence changed: ' + name)
    print(result['review.json'].decode(), end='')


if __name__ == '__main__':
    main()
