#!/usr/bin/env python3
"""Verify immutable native audit receipts; never infer physical Q or energy."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import lzma
from pathlib import Path, PurePosixPath
import re
import tarfile

ROOT = Path(__file__).resolve().parent
P112 = 's2c-native-pin-audit-20261104-112/'
STATUS = 'REPLAYED_24_COMPACTS_AND_ORIGINAL_REPORTS_NOT_QUALIFIED'
PINS = 22512
DURATION = 6604373333334
ATTRIBUTES = {'activity_checker_status', 'full_name', 'glitch_rate', 'static_probability',
              'toggle_rate', 'x_probability', 'relative_toggle_rate', 'actual_fall_transition_max',
              'actual_fall_transition_min', 'actual_rise_transition_max', 'actual_rise_transition_min',
              'actual_transition_max', 'actual_transition_min', 'pin_capacitance_max', 'pin_capacitance_min',
              'fanout_load', 'total_capacitance_max', 'total_capacitance_min',
              'wire_capacitance_max', 'wire_capacitance_min'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def obj(body):
    return json.loads(body, object_pairs_hook=unique)


def archive(path, manifest_path, digest, size, count, payload_bytes):
    need(path.stat().st_size == size and sha(path.read_bytes()) == digest, 'outer archive differs')
    manifest = obj(manifest_path.read_bytes())
    expected = {row['path']: row for row in manifest}
    need(len(expected) == len(manifest) == count and sum(row['bytes'] for row in manifest) == payload_bytes,
         'manifest dimensions differ')
    data, internal = {}, None
    with tarfile.open(path, 'r|xz') as stream:
        for member in stream:
            name = PurePosixPath(member.name)
            need(member.isfile() and not name.is_absolute() and '..' not in name.parts and
                 member.name not in data and member.size < 64000000, 'unsafe/duplicate tar member')
            body = stream.extractfile(member).read()
            if member.name == 'manifest.json':
                need(internal is None, 'duplicate internal manifest')
                internal = obj(body)
                continue
            need(dict(path=member.name, bytes=len(body), sha256=sha(body)) == expected.get(member.name),
                 'original bytes differ: ' + member.name)
            data[member.name] = body
    need(internal == manifest and set(data) == set(expected), 'unaccounted/missing original payload')
    return data


def reference(name, compressed_size, compressed_sha, raw_size, raw_sha):
    body = (ROOT / 'references' / name).read_bytes()
    need(len(body) == compressed_size and sha(body) == compressed_sha, 'reference compression differs')
    raw = lzma.decompress(body)
    need(len(raw) == raw_size and sha(raw) == raw_sha, 'reference original bytes differ')
    return obj(raw)


def same_identity(a, b):
    return a['bytes'] == b['bytes'] and a['sha256'] == b['sha256']


def verify118(data):
    state, summary, output = [obj(data[P112 + name]) for name in
                              ['state.json', 'summary.json', 'output-manifest.json']]
    need(state['schema'] == 'xu-independent-native-pin-audit112-v1' and
         state['status'] == summary['status'] == output['status'] == STATUS and
         state['qualification'] == summary['qualification'] == output['qualification'] == 'NOT_QUALIFIED',
         'actual112 terminal scope differs')
    tool = (ROOT / 'tools/xu_native_pin_audit112.py').read_bytes()
    need(len(tool) == state['tool']['bytes'] == 30407 and sha(tool) == state['tool']['sha256'] ==
         'b878d55ca38fb13a87853a46e69d5d221bb23d1af3a14b10020ec3eb7bbfa6ae', 'actual112 producer differs')
    execution = reference('pt57-execution.json.xz', 32336,
        '4c6da0dc4298a79556cca1b17501d3b5df8bb909838fad1e816af1e418b76c7c', 415497,
        '45acb972f44b2a3009dca012836db6f2bde0a95d1de538d085fa27f882c6a3b9')
    native = reference('native93-state.json.xz', 5084,
        '11b4021b9d49ceab8f305a34b2b7c392d0c53d1f5f46c82898c20c8732d46580', 139221,
        '1751f3d28c8a67ea5fc3d3ffe78d9f3b905f33a9d9011e9e4f0ba3726bd72abb')
    need(state['input_receipts']['execution'] == native['execution'] and
         state['input_receipts']['prepared'] == native['prepared'] and
         state['input_receipts']['native_state']['sha256'] ==
         '1751f3d28c8a67ea5fc3d3ffe78d9f3b905f33a9d9011e9e4f0ba3726bd72abb' and
         execution['status'] == 'EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING' and
         native['status'] == 'EXTRACTED_24_ORIGINAL_REPORTS_NOT_QUALIFIED', 'fixed PT57/93 binding differs')
    need([task['task_id'] for task in state['tasks']] == list(range(12)) and
         [task['task_id'] for task in summary['tasks']] == list(range(12)), 'exact12 tasks differ')
    totals, aggregate = Counter(), Counter()
    original_paths, compact_paths = set(), set()
    for task, short, prior in zip(state['tasks'], summary['tasks'], native['tasks']):
        task_id = task['task_id']
        prefix = 'task_%02d/' % task_id
        need(obj(data[P112 + 'task_%02d-summary.json' % task_id]) == task,
             'per-task/state body differs')
        need(task['qualification'] == 'NOT_QUALIFIED' and
             task['mapped_saif_body_selected_pins_verified'] == PINS and
             task['mapped_saif_total_signal_records'] == 137439 and
             task['measured_unknown_bit_ticks'] == 29636086623576352 and
             same_identity(task['mapped_saif'], execution['artifacts'][prefix + 'task-mapped.saif']) and
             same_identity(task['measured_input'], execution['artifacts'][prefix + 'measured-sram-pins.json']) and
             task['measured_input'] == prior['measured_input'], 'SAIF/measured pin body-audit scope differs')
        for phase in ['before', 'after']:
            report = task[phase]
            counts = report['native_attribute_counts']
            cross = report['tx_native_attribute_cross_counts']
            expected_cross = {
                'SRAM_INPUT|TX_ZERO|x=NATIVE_ZERO|SP=NATIVE_INTERIOR_PROBABILITY|TR=NATIVE_POSITIVE': 12168,
                'SRAM_INPUT|TX_ZERO|x=NATIVE_ZERO|SP=NATIVE_ONE|TR=NATIVE_ZERO': 1864,
                'SRAM_INPUT|TX_ZERO|x=NATIVE_ZERO|SP=NATIVE_ZERO|TR=NATIVE_ZERO': 3104,
                'SRAM_OUTPUT_Q|TX_PARTIAL_WINDOW|x=NATIVE_ZERO|SP=NATIVE_INTERIOR_PROBABILITY|TR=NATIVE_POSITIVE': 656,
                'SRAM_OUTPUT_Q|TX_PARTIAL_WINDOW|x=NATIVE_ZERO|SP=NATIVE_ZERO|TR=NATIVE_ZERO': 368,
                'SRAM_OUTPUT_Q|TX_WHOLE_WINDOW|x=NATIVE_ZERO|SP=NATIVE_INTERIOR_PROBABILITY|TR=NATIVE_ZERO': 4256,
                'SRAM_OUTPUT_Q|TX_ZERO|x=NATIVE_ZERO|SP=NATIVE_INTERIOR_PROBABILITY|TR=NATIVE_POSITIVE': 64,
                'SRAM_OUTPUT_Q|TX_ZERO|x=NATIVE_ZERO|SP=NATIVE_ONE|TR=NATIVE_ZERO': 1,
                'SRAM_OUTPUT_Q|TX_ZERO|x=NATIVE_ZERO|SP=NATIVE_ZERO|TR=NATIVE_ZERO': 31}
            need(cross == expected_cross and
                 counts['relative_toggle_rate:ABSENT_FROM_ORIGINAL_REPORT'] == 2272 and
                 counts['relative_toggle_rate:NATIVE_POSITIVE'] == 12888 and
                 counts['relative_toggle_rate:NATIVE_ZERO'] == 7352,
                 'README per-phase cross/optional-relative-rate table differs')
            need(report['rows'] == PINS and report['phase'] == phase and
                 report['all_original_blocks_and_selected_attribute_text_replayed'] is True and
                 report['qualification'] == 'NOT_QUALIFIED' and
                 report['source_actual'] == prior[phase]['source_actual'] and
                 report['compact'] == prior[phase]['compact_rows'] and
                 counts == prior[phase]['selected_attribute_counts'] and
                 report['before_after_type_value_counts'] == prior[phase]['before_after_comparison_counts'] and
                 same_identity(report['source_actual'], execution['artifacts'][prefix + 'sram-pins-' + phase + '.rpt']),
                 'complete original/compact per-phase binding differs')
            original_paths.add(report['source_actual']['path'])
            compact_paths.add(report['compact']['path'])
            need(sum(cross.values()) == PINS and
                 all(sum(value for key, value in counts.items() if key.startswith(name + ':')) == PINS
                     for name in ATTRIBUTES), 'per-attribute/cross count conservation differs')
            derived = Counter()
            for key, value in cross.items():
                role, tx, x, sp, tr = key.split('|')
                need(type(value) is int and value > 0 and role in ['SRAM_INPUT', 'SRAM_OUTPUT_Q'] and
                     tx in ['TX_ZERO', 'TX_PARTIAL_WINDOW', 'TX_WHOLE_WINDOW'] and x == 'x=NATIVE_ZERO',
                     'native cross row scope differs')
                derived['role:' + role] += value
                derived['static_probability:' + sp.split('=', 1)[1]] += value
                derived['toggle_rate:' + tr.split('=', 1)[1]] += value
                if tx != 'TX_ZERO':
                    need(role == 'SRAM_OUTPUT_Q', 'input SAIF TX-positive pin is not Q')
                    derived['TX_positive'] += value
                if tx == 'TX_WHOLE_WINDOW':
                    derived['TX_whole'] += value
            need(derived['role:SRAM_INPUT'] == counts['pin_role:SRAM_INPUT'] == 17136 and
                 derived['role:SRAM_OUTPUT_Q'] == counts['pin_role:SRAM_OUTPUT_Q'] == 5376 and
                 derived['TX_positive'] == counts['measured_input_TX_positive'] == 5280 and
                 derived['TX_whole'] == counts['measured_input_TX_whole_window'] == 4256 and
                 counts['x_probability:NATIVE_ZERO'] == PINS, 'native x/SAIF TX conservation differs')
            need(all(counts[key] == value for key, value in derived.items()
                     if key.startswith(('static_probability:', 'toggle_rate:'))), 'SP/TR cross marginals differ')
            literals = report['tx_positive_native_literal_value_counts']
            need(sum(literals.values()) == 5280 and
                 all('|x_probability=float:0.000000|' in key for key in literals) and
                 literals['SRAM_OUTPUT_Q|TX_WHOLE_WINDOW|x_probability=float:0.000000|static_probability=float:0.500000|toggle_rate=double:0'] == 4256,
                 'whole-window input-TX/native-value intersection differs')
            literal_cross = Counter()
            for key, value in literals.items():
                role, tx, x, sp, tr = key.split('|')
                spn, trn = Decimal(sp.rsplit(':', 1)[1]), Decimal(tr.rsplit(':', 1)[1])
                spclass = 'NATIVE_ZERO' if spn == 0 else ('NATIVE_ONE' if spn == 1 else 'NATIVE_INTERIOR_PROBABILITY')
                trclass = 'NATIVE_ZERO' if trn == 0 else 'NATIVE_POSITIVE'
                need(0 <= spn <= 1 and trn >= 0, 'native literals outside classified domain')
                literal_cross['|'.join([role, tx, 'x=NATIVE_ZERO', 'SP=' + spclass, 'TR=' + trclass])] += value
            need(dict(literal_cross) == {key: value for key, value in cross.items() if '|TX_ZERO|' not in key},
                 'native literal/class intersection differs')
            need(short['phases'][phase] == dict(rows=PINS, measured_TX_positive=5280,
                 measured_TX_whole_window=4256, native_x_probability_zero=PINS,
                 tx_native_attribute_cross_counts=cross), 'short phase summary differs')
            if phase == 'before':
                need(report['before_after_type_value_counts'] == {} and
                     counts['lazy_activity_or_power_engine_diagnostic'] == 3 and
                     report['native_diagnostic_counts'].get('Information: Running averaged power analysis... (PWR-601)') == 1,
                     'before getter lazy-engine boundary must remain visible')
            else:
                need(report['before_after_type_value_counts'] == {name + ':RAW_UNCHANGED': PINS for name in ATTRIBUTES},
                     'selected attribute type/value equality differs')
            for source, record in report['source_report_lists'].items():
                need(same_identity(record['identity'], execution['artifacts'][prefix + 'source-' + source + '-' + phase + '.rpt']),
                     'native source-driver membership report identity differs')
            aggregate.update(cross)
            totals['rows'] += report['rows']
            totals['original_bytes'] += report['source_actual']['bytes']
            totals['compact_bytes'] += report['compact']['bytes']
    need(len(original_paths) == len(compact_paths) == 24 and
         totals == dict(rows=540288, original_bytes=19326860762, compact_bytes=131728568) and
         state['native_pin_rows_replayed'] == summary['native_pin_rows_replayed'] == totals['rows'] and
         state['original_report_bytes_replayed'] == summary['original_report_bytes_replayed'] == totals['original_bytes'] and
         state['compact_bytes_rehashed'] == summary['compact_bytes_rehashed'] == totals['compact_bytes'] and
         state['mapped_saif_pin_rows_verified'] == 270144 and
         dict(aggregate) == summary['aggregate_tx_native_attribute_cross_counts'], 'complete24-phase totals differ')
    present = {name[len(P112):]: body for name, body in data.items() if name.startswith(P112)}
    missing = set(output['artifacts']) - set(present)
    need(missing == {'task_00-%s-sample_%02d.compact.jsonl' % (phase, sample)
                     for phase in ['before', 'after'] for sample in range(4)} and
         len(output['artifacts']) == 30, 'actual118 missing8-jsonl boundary differs')
    for name, record in output['artifacts'].items():
        if name in present:
            need(len(present[name]) == record['bytes'] and sha(present[name]) == record['sha256'],
                 '112 output manifest/body differs')
    driver = data['s2c-native-pin-audit-launch-20261104-112/driver.log'].decode()
    need([int(value) for value in re.findall(r'^XU_AUDIT112_TASK_COMPLETE task=(\d+) rows=45024 original_reports=2 NOT_QUALIFIED$', driver, re.M)] == list(range(12)) and
         driver.splitlines().count(STATUS + ' rows=540288') == 1, '12 actual native replay terminal markers differ')
    observed = {row['prefix']: row for row in obj(data['live118-observation.json'])['observed']}
    need(observed['s2c-native-pin-audit-launch-20261104-112']['pid'] == 2501 and
         observed['s2c-native-pin-audit-launch-20261104-112']['pid_alive_now'] is False and
         observed['s2c-native-pin-audit-20261104-112']['status'] == STATUS, 'actual112 terminal process observation differs')
    return state, output, aggregate


def native_class(name, attribute):
    if attribute is None:
        return 'ABSENT_FROM_ORIGINAL_REPORT'
    if attribute['type'] == 'string':
        return 'NATIVE_STRING_NOT_ANNOTATION_SOURCE'
    value = Decimal(attribute['value'])
    if not value.is_finite():
        return 'NONFINITE_OR_NOT_NUMERIC_NATIVE_TEXT'
    if name in ['static_probability', 'x_probability']:
        if not 0 <= value <= 1:
            return 'OUTSIDE_PROBABILITY_RANGE_NATIVE_SENTINEL'
        return 'NATIVE_ZERO' if value == 0 else ('NATIVE_ONE' if value == 1 else 'NATIVE_INTERIOR_PROBABILITY')
    if name in ['toggle_rate', 'relative_toggle_rate', 'glitch_rate']:
        if value < 0:
            return 'NEGATIVE_NATIVE_SENTINEL_NOT_MEASURED_RATE'
        return 'NATIVE_ZERO' if value == 0 else 'NATIVE_POSITIVE'
    return 'NATIVE_FINITE_VALUE_UNIT_NOT_INFERRED'


def independent_attributes(raw, report_start, pin):
    """Read actual returned report lines, not the extractor/auditor functions."""
    need(raw.startswith(('XU_SRAM_PIN name=' + pin + '\n').encode()) and
         raw.count(b'XU_SRAM_PIN name=') == 1 and b'Design : xu_soc_ppa_top' in raw,
         'original sample scope differs')
    lines = raw.splitlines(keepends=True)
    offsets, cursor = [], report_start
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)
    result = {}
    pattern = re.compile(rb'^[ \t]+(string|float|double|boolean|integer)[ \t]+(\w+)[ \t]*([^\r\n]*)\r?\n?$')
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match is None:
            continue
        kind, name, inline = [value.decode() for value in match.groups()]
        if name not in ATTRIBUTES:
            continue
        need(name not in result, 'duplicate selected native attribute')
        value, end = inline.strip(), index + 1
        if not value:
            need(end < len(lines) and lines[end][:1] in [b' ', b'\t'] and
                 pattern.match(lines[end]) is None, 'invalid wrapped native scalar')
            value = lines[end].strip().decode()
            need(value, 'empty wrapped scalar')
            end += 1
        result[name] = dict(type=kind, value=value, raw_text=b''.join(lines[index:end]).decode(),
                            report_byte_start=offsets[index],
                            report_byte_end=offsets[end] if end < len(lines) else cursor)
    need(result.get('full_name', {}).get('value') == pin and
         {'full_name', 'activity_checker_status', 'glitch_rate', 'static_probability',
          'toggle_rate', 'x_probability'}.issubset(result), 'native required field/name differs')
    return result


def verify119(data118, data119, state, output):
    original112 = {name: body for name, body in data118.items() if name.startswith(P112)}
    need(all(data119.get(name) == body for name, body in original112.items()),
         'immutable112 output changed between118/119')
    returned = {name[len(P112):]: body for name, body in data119.items() if name.startswith(P112)}
    need(set(returned) == set(output['artifacts']) | {'output-manifest.json'},
         '119 must return all30 manifested112 artifacts plus output manifest')
    for name, record in output['artifacts'].items():
        body = returned[name]
        need(len(body) == record['bytes'] and sha(body) == record['sha256'], 'complete112 output identity differs')
    checked, missing_relative, whole_tx = 0, 0, 0
    for phase in ['before', 'after']:
        samples = state['tasks'][0][phase]['samples']
        need(len(samples) == 4, 'actual112 sample selection differs')
        for index, sample in enumerate(samples):
            stem = 'task_00-%s-sample_%02d' % (phase, index)
            raw, compact = returned[stem + '.original.txt'], returned[stem + '.compact.jsonl']
            row = obj(compact)
            for body, label in [(raw, 'original_block'), (compact, 'compact_line')]:
                record = sample[label]
                need(len(body) == record['bytes'] and sha(body) == record['sha256'],
                     'sample original/compact identity differs')
            start, end = sample['original_report_range']
            need(start == row['report_byte_start'] and end == row['report_byte_end'] and
                 row['block_bytes'] == end - start == len(raw) and row['block_sha256'] == sha(raw) and
                 row['phase'] == phase and row['pin'] == sample['pin'] and
                 sample['original_report_identity'] == state['tasks'][0][phase]['source_actual'],
                 'original sample range/phase/input identity differs')
            need(row['phase_semantics'] == 'before/after EXPLICIT update_power; report_attribute getters may lazily propagate/compute power' and
                 row['annotation_source'] == 'NOT_PRESENT_IN_SAVED_ATTRIBUTE_REPORT; activity_checker_status is not file/default/propagated source',
                 'unknown provenance or unsynchronized phase boundary must remain explicit')
            attrs = independent_attributes(raw, start, row['pin'])
            need(attrs == row['attributes'] and
                 {name: native_class(name, attrs.get(name)) for name in ATTRIBUTES} == row['classes'] and
                 sample['native_classes'] == {name: row['classes'][name] for name in
                    ['relative_toggle_rate', 'static_probability', 'toggle_rate', 'x_probability']},
                 'native original lines/selected type-value/classification differ')
            stats = row['mapped_saif_measured_input']
            need(stats == sample['measured_saif_statistics'] and
                 all(type(stats[name]) is int and stats[name] >= 0 for name in ['T0', 'T1', 'TX', 'TC', 'IG']) and
                 stats['T0'] + stats['T1'] + stats['TX'] == DURATION, 'sample input-SAIF conservation differs')
            pos, diagnostics = start, []
            for line in raw.splitlines(keepends=True):
                if re.match(rb'^(?:Information|Warning|Error|Fatal):', line) or re.match(
                        rb'^[ \t]*Running (?:switching activity propagation|averaged power analysis|power calculation)', line):
                    diagnostics.append(dict(report_byte_start=pos, report_byte_end=pos + len(line), raw_text=line.decode()))
                pos += len(line)
            need(diagnostics == row['native_diagnostics'], 'sample original lazy/warning diagnostics differ')
            for source, matches in sample['source_driver_list_matches'].items():
                need(source in state['tasks'][0][phase]['source_report_lists'], 'source-driver report identity absent')
                for match in matches:
                    need(match['match_column'] == 'exact native driver pin column' and
                         match['raw_text'].rstrip().split('\t')[-1].strip() == row['pin'],
                         'source membership is not an exact driver-column match')
            if 'relative_toggle_rate' not in attrs:
                need(row['classes']['relative_toggle_rate'] == 'ABSENT_FROM_ORIGINAL_REPORT',
                     'absent optional rate was coerced to zero')
                missing_relative += 1
            if stats['TX'] == DURATION:
                need(stats['T0'] == stats['T1'] == stats['TC'] == 0 and
                     attrs['x_probability']['value'] == '0.000000' and
                     attrs['static_probability']['value'] == '0.500000' and
                     attrs['toggle_rate']['value'] == '0' and row['pin_role'] == 'SRAM_OUTPUT_Q',
                     'actual whole-window input-TX/native attribute evidence differs')
                whole_tx += 1
            checked += 1
    need(checked == 8 and missing_relative == 2 and whole_tx == 2,
         'all eight selected native samples were not replayed')
    need(obj(data119['omitted119-bodies.json']) == [], '119 explicit oversized omission differs')
    return dict(original_sample_blocks=checked, compact_sample_rows=checked,
                absent_relative_rate_preserved=missing_relative,
                input_whole_window_TX_with_native_x0_SP_half_TR0=whole_tx)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', type=Path)
    args = parser.parse_args()
    tools = obj((ROOT / 'tools-manifest.json').read_bytes())
    expected_tools = {
        'tools/export118.py': (2533, 'd0af4de31c226dd5640152384e3abc51f3a43f4b8051fd3f93d0b6f0bd8d4d8c'),
        'tools/export119.py': (2637, 'fc0085c9387cb8edc5c302a942895c116eb9d0b71b55293f00154a9d344497ed'),
        'tools/launch_native_pin_audit112.py': (2194, 'c01ca50b09d90d4ae55db51424670e6358e483f48bca160dd9359b75f84b0cf6'),
        'tools/xu_native_pin_audit112.py': (30407, 'b878d55ca38fb13a87853a46e69d5d221bb23d1af3a14b10020ec3eb7bbfa6ae')}
    need(len(tools) == 4 and {row['path'] for row in tools} == set(expected_tools), 'tools manifest differs')
    for row in tools:
        body = (ROOT / row['path']).read_bytes()
        need((len(body), sha(body)) == (row['bytes'], row['sha256']) == expected_tools[row['path']],
             'public producer/exporter bytes differ')
    data = archive(ROOT / 'payload.tar.xz', ROOT / 'payload-manifest.json',
        '5575e63f83f67ada7dda6d5b1a571d8a54c274df0d95f0fb4c7f9423d97b94f0', 146208, 42, 6608026)
    state, output, aggregate = verify118(data)
    supplement = archive(ROOT / 'supplement119.tar.xz', ROOT / 'supplement119-manifest.json',
        'ec9657776616f72bc98bb7c876acf71a77bdc9614ab31b9581f4c780c3acb934', 872692, 59, 46164286)
    samples = verify119(data, supplement, state, output)
    if args.extract:
        args.extract.mkdir(exist_ok=False)
        for label, contents in [('actual118', data), ('actual119', supplement)]:
            for name, body in contents.items():
                target = args.extract / label / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
    print(json.dumps(dict(status='PASS', qualification='NOT_QUALIFIED',
        rows=state['native_pin_rows_replayed'], original_report_bytes=state['original_report_bytes_replayed'],
        compact_bytes=state['compact_bytes_rehashed'], aggregate_tx_native_attribute_cross_counts=dict(aggregate),
        local_original_and_compact_samples=samples,
        limitation='Local receipt/statistic verification; complete original report bodies were replayed on server, not returned locally.'),
        sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
