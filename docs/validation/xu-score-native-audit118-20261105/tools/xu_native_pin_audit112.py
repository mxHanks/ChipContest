#!/usr/bin/env python3
"""Read-only independent replay of extractor93 against the original PT57 reports.

No EDA tool is invoked. No activity, library, timing or design input is modified.
Successful replay proves recorded bytes and statistics, not physical known state,
the cause of PT's X handling, a synchronized before/after snapshot, or energy.
Python 3.6 compatible; all output is confined to a new --output directory.
"""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import lzma
from pathlib import Path
import re
import traceback

EXECUTION_SHA = '45acb972f44b2a3009dca012836db6f2bde0a95d1de538d085fa27f882c6a3b9'
PREPARED_SHA = 'cb363beafeac51329aab8f04843999021c17cf05dd22a1d1f3ee505ceb70a103'
EXTRACTOR_SHA = '784841b104370b5cf15d7b4f7ed72cce56d498214bbb4ef511e59e39ad868347'
DURATION = 6604373333334
PINS = 22512
CORE = {'activity_checker_status': 'string', 'full_name': 'string',
        'glitch_rate': 'double', 'static_probability': 'float',
        'toggle_rate': 'double', 'x_probability': 'float'}
OPTIONAL = ['relative_toggle_rate', 'actual_fall_transition_max',
            'actual_fall_transition_min', 'actual_rise_transition_max',
            'actual_rise_transition_min', 'actual_transition_max',
            'actual_transition_min', 'pin_capacitance_max', 'pin_capacitance_min',
            'fanout_load', 'total_capacitance_max', 'total_capacitance_min',
            'wire_capacitance_max', 'wire_capacitance_min']
SELECTED = set(CORE).union(OPTIONAL)
PHASE_SEMANTICS = 'before/after EXPLICIT update_power; report_attribute getters may lazily propagate/compute power'
ANNOTATION_LIMIT = 'NOT_PRESENT_IN_SAVED_ATTRIBUTE_REPORT; activity_checker_status is not file/default/propagated source'
LIMITS = [
    'Native x_probability=0 is an engine attribute at getter evaluation time; it does not establish a physically known Q value.',
    'Before means before EXPLICIT update_power; original attribute getters can trigger lazy switching propagation and averaged power analysis.',
    'Selected source-report membership is an exact match in the saved driver-pin column only. Absence for a load/input pin is not evidence of no file annotation.',
    'Replay does not establish how PT transformed, ignored, normalized or defaulted SAIF unknown dwell, nor why the native value is zero.',
    'No physical state assignment, energy correction, full waveform, timing qualification or contest score is inferred.'
]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate JSON key: ' + str(key))
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def dump(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stat_key(path):
    s = Path(path).stat()
    return (s.st_size, s.st_mtime_ns, s.st_ino)


def identity(path):
    path = Path(path)
    before = stat_key(path)
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    need(before == stat_key(path), 'file changed while hashing: ' + str(path))
    return dict(path=str(path.resolve()), bytes=before[0], sha256=digest.hexdigest())


def check_identity(path, receipt):
    actual = identity(path)
    need(actual['bytes'] == receipt['bytes'] and actual['sha256'] == receipt['sha256'],
         'identity differs: ' + str(path))
    return actual


def same_bytes(a, b):
    return a['bytes'] == b['bytes'] and a['sha256'] == b['sha256']


def number(value):
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def category(name, attribute):
    if attribute is None:
        return 'ABSENT_FROM_ORIGINAL_REPORT'
    if attribute['type'] == 'string':
        return 'NATIVE_STRING_NOT_ANNOTATION_SOURCE'
    value = number(attribute['value'])
    if value is None:
        return 'NONFINITE_OR_NOT_NUMERIC_NATIVE_TEXT'
    if name in ('static_probability', 'x_probability'):
        if not Decimal(0) <= value <= Decimal(1):
            return 'OUTSIDE_PROBABILITY_RANGE_NATIVE_SENTINEL'
        return 'NATIVE_ZERO' if value == 0 else ('NATIVE_ONE' if value == 1 else 'NATIVE_INTERIOR_PROBABILITY')
    if name in ('toggle_rate', 'relative_toggle_rate', 'glitch_rate'):
        if value < 0:
            return 'NEGATIVE_NATIVE_SENTINEL_NOT_MEASURED_RATE'
        return 'NATIVE_ZERO' if value == 0 else 'NATIVE_POSITIVE'
    return 'NATIVE_FINITE_VALUE_UNIT_NOT_INFERRED'


def original_attributes(raw, start, pin):
    """Independent line parser, including native wrapped scalar values."""
    need(raw.startswith(('XU_SRAM_PIN name=' + pin + '\n').encode()), 'original marker differs')
    need(b'\nXU_SRAM_PIN name=' not in raw, 'compact range contains another pin block')
    need(re.search(rb'(?m)^Design\s*:\s*xu_soc_ppa_top\s*$', raw) is not None,
         'original attribute scope differs')
    lines = raw.splitlines(keepends=True)
    offsets, pos = [], start
    for line in lines:
        offsets.append(pos)
        pos += len(line)
    attrs = {}
    for i, line in enumerate(lines):
        match = re.match(rb'^[ \t]+(string|float|double|boolean|integer)[ \t]+(\w+)\b[ \t]*([^\r\n]*)\r?\n?$', line)
        if match is None:
            continue
        typ, name, value = [x.decode('utf-8') for x in match.groups()]
        if name not in SELECTED:
            continue
        need(name not in attrs, 'duplicate original selected attribute: ' + name)
        end = i + 1
        if not value.strip():
            need(end < len(lines), 'missing wrapped original value')
            value = lines[end].strip().decode('utf-8')
            need(lines[end][:1] in (b' ', b'\t') and value and
                 re.match(rb'^[ \t]+(?:string|float|double|boolean|integer)[ \t]', lines[end]) is None,
                 'invalid wrapped original value')
            end += 1
        attrs[name] = dict(type=typ, value=value.strip(),
                           raw_text=b''.join(lines[i:end]).decode('utf-8'),
                           report_byte_start=offsets[i],
                           report_byte_end=offsets[end] if end < len(lines) else pos)
    need(set(CORE).issubset(attrs), 'missing original native core attribute')
    need(all(attrs[k]['type'] == v for k, v in CORE.items()), 'original native core types differ')
    need(attrs['full_name']['value'] == pin, 'original full_name differs')
    return attrs


def original_diagnostics(raw, start):
    result, pos = [], start
    for line in raw.splitlines(keepends=True):
        if re.match(rb'^(?:Information|Warning|Error|Fatal):', line) or re.match(
                rb'^[ \t]*Running (?:switching activity propagation|averaged power analysis|power calculation)', line):
            result.append(dict(report_byte_start=pos, report_byte_end=pos + len(line),
                               raw_text=line.decode('utf-8')))
        pos += len(line)
    return result


def saif_pin_values(path, measured):
    """Parse full immutable mapped SAIF without the original producer module."""
    text = Path(path).read_text(errors='strict')
    token_re = re.compile(r'//[^\n]*|/\*.*?\*/|\(|\)|"(?:\\.|[^"\\])*"|(?:\\.|[^\s()])+', re.S)
    roots, stack = [], []
    for match in token_re.finditer(text):
        token = match.group(0)
        if token.startswith('//') or token.startswith('/*'):
            continue
        if token == '(':
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
        elif token == ')':
            need(stack, 'unbalanced mapped SAIF close')
            stack.pop()
        else:
            need(stack, 'mapped SAIF token outside expression')
            stack[-1].append(token[1:-1] if token.startswith('"') else token)
    need(not stack and len(roots) == 1 and roots[0][0] == 'SAIFILE', 'invalid mapped SAIF root')
    tree = roots[0]
    headers = {}
    for node in tree[1:]:
        if isinstance(node, list) and node and node[0] != 'INSTANCE':
            need(node[0] not in headers, 'duplicate mapped SAIF header')
            headers[node[0]] = node[1:]
    need(len(headers.get('DURATION', [])) == 1 and number(headers['DURATION'][0]) == DURATION,
         'mapped SAIF window differs')
    units = {'s': Decimal(1), 'ms': Decimal('1e-3'), 'us': Decimal('1e-6'),
             'ns': Decimal('1e-9'), 'ps': Decimal('1e-12'), 'fs': Decimal('1e-15')}
    timescale = headers.get('TIMESCALE', [])
    need(len(timescale) == 2 and timescale[1] in units and
         number(timescale[0]) is not None and number(timescale[0]) * units[timescale[1]] == Decimal('1e-15'),
         'mapped SAIF timebase differs')
    wanted = {(row['kind'], row['path']): row for row in measured.values()}
    need(len(wanted) == len(measured), 'duplicate measured SAIF identity')
    seen_all, selected = set(), {}

    def unescape(value):
        return re.sub(r'\\(.)', r'\1', value)

    def visit(node, parent):
        need(isinstance(node, list) and node, 'invalid mapped SAIF expression')
        if node[0] == 'INSTANCE':
            need(len(node) >= 2 and isinstance(node[1], str), 'invalid mapped INSTANCE')
            for item in node[2:]:
                visit(item, parent + [unescape(node[1])])
        elif node[0] in ('NET', 'PORT'):
            for item in node[1:]:
                need(isinstance(item, list) and item and isinstance(item[0], str), 'invalid mapped signal')
                key = (node[0], '/'.join(parent + [unescape(item[0])]))
                need(key not in seen_all, 'duplicate mapped signal')
                seen_all.add(key)
                stats = {}
                for pair in item[1:]:
                    need(isinstance(pair, list) and len(pair) == 2 and pair[0] not in stats,
                         'invalid/duplicate mapped statistic')
                    v = number(pair[1])
                    need(v is not None and v >= 0 and v == int(v), 'nonintegral mapped statistic')
                    stats[pair[0]] = int(v)
                need(set(('T0', 'T1', 'TX', 'TC')).issubset(stats), 'mapped statistics missing')
                need(sum(stats.get(k, 0) for k in ('T0', 'T1', 'TX', 'TZ', 'TB')) == DURATION,
                     'mapped dwell not conserved')
                if key in wanted:
                    row = wanted[key]
                    need(stats == {k: row[k] for k in stats} and set(stats) == {'T0', 'T1', 'TX', 'TC', 'IG'},
                         'mapped body/measured pin statistics differ')
                    selected[row['mapped_path']] = stats
        else:
            for item in node[1:]:
                if isinstance(item, list):
                    visit(item, parent)

    for node in tree[1:]:
        if isinstance(node, list) and node[0] == 'INSTANCE':
            visit(node, [])
    need(set(selected) == set(measured), 'mapped SAIF missing selected pins')
    return selected, len(seen_all)


def source_driver_membership(path, pins):
    matches, offset, title = {}, 0, None
    with Path(path).open('rb') as src:
        for line in src:
            if line.startswith(b'List of nets with activity from '):
                need(title is None, 'duplicate source listing title')
                title = line.decode().rstrip('\r\n')
            if title is not None and line.startswith(b'\t'):
                columns = line.rstrip(b'\r\n').split(b'\t')
                need(len(columns) == 3 and columns[0] == b'', 'unexpected source listing columns')
                driver = columns[2].strip().decode('utf-8')
                if driver in pins:
                    matches.setdefault(driver, []).append(dict(raw_text=line.decode('utf-8'),
                        report_byte_start=offset, report_byte_end=offset + len(line),
                        title=title, match_column='exact native driver pin column'))
            offset += len(line)
    return matches


def signature(row):
    return {k: (v['type'], v['value']) for k, v in row['attributes'].items()}


def replay_phase(compact, receipt, raw_path, source_receipt, measured, expected,
                 phase, out, task_id, previous=None, sample_limit=4, expected_count=PINS):
    compact_identity = check_identity(compact, receipt)
    raw_before = stat_key(raw_path)
    need(raw_before[0] == source_receipt['bytes'], 'raw report size differs')
    digest, pos, seen, current = hashlib.sha256(), 0, set(), {}
    counts, cross, native_tx_values, comparison, diagnostic_counts = Counter(), Counter(), Counter(), Counter(), Counter()
    samples, sample_categories = [], set()
    with lzma.open(str(compact), 'rb') as src, Path(raw_path).open('rb') as original:
        for line_number, line in enumerate(src, 1):
            need(line.endswith(b'\n') and len(line) < 128 * 1024, 'compact line malformed/oversize')
            row = json.loads(line.decode('utf-8'), object_pairs_hook=lambda pairs: unique_pairs(pairs))
            pin = row['pin']
            need(pin in measured and pin not in seen, 'unexpected/duplicate compact pin')
            need(row['phase'] == phase and row['phase_semantics'] == PHASE_SEMANTICS,
                 'compact phase semantics differ')
            need(row['annotation_source'] == ANNOTATION_LIMIT, 'compact annotation boundary differs')
            need(row['report_byte_start'] == pos and type(row['block_bytes']) is int and
                 0 < row['block_bytes'] < 2 * 1024 * 1024 and
                 row['report_byte_end'] == pos + row['block_bytes'], 'raw compact range differs')
            raw = original.read(row['block_bytes'])
            need(len(raw) == row['block_bytes'] and sha(raw) == row['block_sha256'], 'original block SHA differs')
            digest.update(raw)
            attrs = original_attributes(raw, pos, pin)
            need(attrs == row['attributes'], 'compact/native attributes differ: ' + pin)
            classes = {name: category(name, attrs.get(name)) for name in SELECTED}
            need(classes == row['classes'], 'compact native classification differs')
            for name, value in classes.items():
                counts[name + ':' + value] += 1
            stats = {k: measured[pin][k] for k in ('T0', 'T1', 'TX', 'TC', 'IG')}
            need(stats == row['mapped_saif_measured_input'], 'compact/measured SAIF statistics differ')
            need(original_diagnostics(raw, pos) == row['native_diagnostics'], 'original diagnostic inventory differs')
            role = 'SRAM_OUTPUT_Q' if pin.rsplit('/', 1)[-1].startswith('Q[') else 'SRAM_INPUT'
            need(role == row['pin_role'], 'compact pin role differs')
            counts['pin_role:' + role] += 1
            tx = 'TX_ZERO' if stats['TX'] == 0 else ('TX_WHOLE_WINDOW' if stats['TX'] == DURATION else 'TX_PARTIAL_WINDOW')
            if stats['TX']:
                counts['measured_input_TX_positive'] += 1
            if stats['TX'] == DURATION:
                counts['measured_input_TX_whole_window'] += 1
            cross['|'.join((role, tx, 'x=' + classes['x_probability'],
                           'SP=' + classes['static_probability'], 'TR=' + classes['toggle_rate']))] += 1
            if stats['TX']:
                native_tx_values['|'.join([role, tx] + [
                    name + '=' + attrs[name]['type'] + ':' + attrs[name]['value']
                    for name in ('x_probability', 'static_probability', 'toggle_rate')])] += 1
            for diagnostic in row['native_diagnostics']:
                a, b = diagnostic['report_byte_start'], diagnostic['report_byte_end']
                need(pos <= a <= b <= pos + len(raw) and raw[a-pos:b-pos].decode() == diagnostic['raw_text'],
                     'compact native diagnostic text differs')
                label = diagnostic['raw_text'].strip()
                diagnostic_counts[label] += 1
                if any(x in label for x in ('switching activity propagation', 'averaged power analysis', 'power calculation')):
                    counts['lazy_activity_or_power_engine_diagnostic'] += 1
            sig = signature(row)
            current[pin] = sig
            if previous is not None:
                need(pin in previous, 'before/after pin mismatch')
                for name in SELECTED:
                    a, b = previous[pin].get(name), sig.get(name)
                    comparison[name + (':RAW_UNCHANGED' if a == b else ':RAW_CHANGED')] += 1
                    if a != b and a is not None and b is not None:
                        av, bv = number(a[1]), number(b[1])
                        if av is not None and bv is not None and av == bv:
                            comparison[name + ':NUMERIC_EQUAL_TEXT_CHANGED'] += 1
            sample_key = None
            if stats['TX']:
                sample_key = tx + '|' + classes['static_probability'] + '|' + classes['toggle_rate']
            elif role == 'SRAM_OUTPUT_Q':
                sample_key = 'TX_ZERO_Q'
            elif 'relative_toggle_rate' not in attrs:
                sample_key = 'ABSENT_RELATIVE_RATE_INPUT'
            if sample_key is not None and sample_key not in sample_categories and len(samples) < sample_limit:
                sample_categories.add(sample_key)
                stem = 'task_%02d-%s-sample_%02d' % (task_id, phase, len(samples))
                block_path, row_path = out / (stem + '.original.txt'), out / (stem + '.compact.jsonl')
                block_path.write_bytes(raw)
                row_path.write_bytes(line)
                samples.append(dict(pin=pin, selection_category=sample_key,
                    original_block=identity(block_path), compact_line=identity(row_path),
                    original_report_range=[pos, pos + len(raw)],
                    original_report_identity=source_receipt,
                    measured_saif_statistics=stats, native_classes={k: classes[k] for k in
                        ('x_probability', 'static_probability', 'toggle_rate', 'relative_toggle_rate')},
                    source_driver_list_matches={}))
            pos += len(raw)
            seen.add(pin)
            if line_number % 8192 == 0:
                print('XU_AUDIT112 task=%02d phase=%s rows=%d raw_bytes=%d' %
                      (task_id, phase, line_number, pos), flush=True)
        need(original.read(1) == b'', 'original report has unrepresented trailing bytes')
    need(seen == set(measured) and len(seen) == expected_count, 'compact exact pin inventory differs')
    need(raw_before == stat_key(raw_path), 'original report changed during replay')
    need(pos == source_receipt['bytes'] and digest.hexdigest() == source_receipt['sha256'],
         'complete original report SHA differs')
    need(check_identity(compact, receipt) == compact_identity, 'compact changed during replay')
    need(dict(counts) == expected['selected_attribute_counts'], '93 summary attribute counts differ')
    need(dict(comparison) == expected['before_after_comparison_counts'], '93 before/after counts differ')
    expected_diagnostics = {d['raw_text']: d['count'] for d in expected['native_diagnostics']}
    need(dict(diagnostic_counts) == expected_diagnostics, '93 diagnostic summary differs')
    if previous is not None:
        need(set(previous) == set(current), 'before/after exact pin set differs')
    return dict(phase=phase, rows=len(seen), compact=compact_identity,
        source_actual=dict(path=str(Path(raw_path).resolve()), bytes=pos, sha256=digest.hexdigest()),
        all_original_blocks_and_selected_attribute_text_replayed=True,
        native_attribute_counts=dict(counts), tx_native_attribute_cross_counts=dict(cross),
        tx_positive_native_literal_value_counts=dict(native_tx_values),
        before_after_type_value_counts=dict(comparison), native_diagnostic_counts=dict(diagnostic_counts),
        samples=samples, qualification='NOT_QUALIFIED'), current


def unique_pairs(pairs):
    out = {}
    for k, v in pairs:
        need(k not in out, 'duplicate compact JSON key')
        out[k] = v
    return out


def audit(campaign, native_root, out):
    campaign, native_root, out = Path(campaign).resolve(), Path(native_root).resolve(), Path(out).resolve()
    need(out != campaign and campaign not in out.parents and
         out != native_root and native_root not in out.parents,
         'output must be outside the immutable campaign and extractor directories')
    out.mkdir(parents=True, exist_ok=False)
    state = dict(schema='xu-independent-native-pin-audit112-v1', status='RUNNING',
                 qualification='NOT_QUALIFIED', tool=identity(__file__), tasks=[], limitations=LIMITS)
    dump(out / 'state.json', state)
    watched = {}
    try:
        execution_path, prepared_path, native_state_path = campaign / 'execution.json', campaign / 'prepared.json', native_root / 'state.json'
        for path, expected_sha in ((execution_path, EXECUTION_SHA), (prepared_path, PREPARED_SHA)):
            ident = identity(path)
            need(ident['sha256'] == expected_sha, 'fixed PT57 receipt differs')
            watched[path] = ident
        native_state_identity = identity(native_state_path)
        watched[native_state_path] = native_state_identity
        execution, prepared, native_state = load(execution_path), load(prepared_path), load(native_state_path)
        need(execution['status'] == 'EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING' and
             execution['requested_task_ids'] == list(range(12)), 'PT57 campaign not complete')
        need(native_state['status'] == 'EXTRACTED_24_ORIGINAL_REPORTS_NOT_QUALIFIED' and
             native_state['native_pin_blocks'] == 540288 and native_state['original_reports_streamed'] == 24 and
             len(native_state['tasks']) == 12, 'extractor93 campaign not complete')
        need(native_state['tool']['sha256'] == EXTRACTOR_SHA, 'extractor93 version differs')
        need(same_bytes(native_state['execution'], watched[execution_path]) and
             same_bytes(native_state['prepared'], watched[prepared_path]), '93 original receipt identity differs')
        state['input_receipts'] = dict(execution=watched[execution_path], prepared=watched[prepared_path],
                                       native_state=native_state_identity)
        for task_id in range(12):
            taskname = 'task_%02d' % task_id
            summary_path = native_root / taskname / 'summary.json'
            watched[summary_path] = identity(summary_path)
            summary = load(summary_path)
            need(summary['task_id'] == task_id and summary == native_state['tasks'][task_id], '93 per-task/state summary mismatch')
            measured_path = campaign / taskname / 'measured-sram-pins.json'
            measured_receipt = execution['artifacts'][taskname + '/measured-sram-pins.json']
            measured_identity = check_identity(measured_path, measured_receipt)
            watched[measured_path] = measured_identity
            need(same_bytes(summary['measured_input'], measured_identity), '93 measured input identity differs')
            measured_data = load(measured_path)
            measured = {r['mapped_path']: r for r in measured_data['pins']}
            need(len(measured) == len(measured_data['pins']) == PINS, 'measured pin count differs')
            for row in measured.values():
                need(all(type(row[k]) is int and row[k] >= 0 for k in ('T0', 'T1', 'TX', 'TC', 'IG')) and
                     row['T0'] + row['T1'] + row['TX'] == DURATION, 'measured input statistics invalid')
            saif_path = campaign / taskname / 'task-mapped.saif'
            saif_receipt = execution['artifacts'][taskname + '/task-mapped.saif']
            saif_identity = check_identity(saif_path, saif_receipt)
            saif_selected, saif_signal_count = saif_pin_values(saif_path, measured)
            need(set(saif_selected) == set(measured), 'SAIF selected pin set differs')
            need(check_identity(saif_path, saif_receipt) == saif_identity, 'mapped SAIF changed during parse')
            result = dict(task_id=task_id, measured_input=measured_identity,
                          mapped_saif=saif_identity, mapped_saif_body_selected_pins_verified=PINS,
                          mapped_saif_total_signal_records=saif_signal_count,
                          measured_unknown_bit_ticks=sum(row['TX'] for row in measured.values()),
                          qualification='NOT_QUALIFIED')
            previous = None
            for phase in ('before', 'after'):
                phase_summary = summary[phase]
                raw_path = campaign / taskname / ('sram-pins-' + phase + '.rpt')
                raw_receipt = execution['artifacts'][taskname + '/' + raw_path.name]
                need(same_bytes(phase_summary['source_actual'], raw_receipt) and
                     same_bytes(phase_summary['source_recorded_receipt'], raw_receipt), '93 original source receipt differs')
                compact = native_root / taskname / ('native-' + phase + '.jsonl.xz')
                result[phase], current = replay_phase(compact, phase_summary['compact_rows'], raw_path,
                    raw_receipt, measured, phase_summary, phase, out, task_id, previous=previous,
                    sample_limit=4 if task_id == 0 else 0)
                selected = {s['pin'] for s in result[phase]['samples']}
                source_lists = {}
                for source_name in ('file', 'default', 'propagated', 'no_switching_activity'):
                    report_name = 'source-' + source_name + '-' + phase + '.rpt'
                    report_path = campaign / taskname / report_name
                    report_identity = check_identity(report_path, execution['artifacts'][taskname + '/' + report_name])
                    membership = source_driver_membership(report_path, selected)
                    source_lists[source_name] = dict(identity=report_identity,
                        selected_exact_driver_pin_matches=sum(len(v) for v in membership.values()),
                        interpretation='saved native driver-column membership only; absent load pin is not no-annotation proof')
                    for sample in result[phase]['samples']:
                        if sample['pin'] in membership:
                            sample['source_driver_list_matches'][source_name] = membership[sample['pin']]
                result[phase]['source_report_lists'] = source_lists
                previous = current
            state['tasks'].append(result)
            dump(out / (taskname + '-summary.json'), result)
            dump(out / 'state.json', state)
            print('XU_AUDIT112_TASK_COMPLETE task=%d rows=45024 original_reports=2 NOT_QUALIFIED' % task_id, flush=True)
        for path, ident in watched.items():
            need(identity(path) == ident, 'watched input changed during independent audit: ' + str(path))
        state['status'] = 'REPLAYED_24_COMPACTS_AND_ORIGINAL_REPORTS_NOT_QUALIFIED'
        state['native_pin_rows_replayed'] = sum(t[p]['rows'] for t in state['tasks'] for p in ('before', 'after'))
        need(state['native_pin_rows_replayed'] == 540288, 'total row count differs')
        state['original_report_bytes_replayed'] = sum(t[p]['source_actual']['bytes'] for t in state['tasks'] for p in ('before', 'after'))
        state['compact_bytes_rehashed'] = sum(t[p]['compact']['bytes'] for t in state['tasks'] for p in ('before', 'after'))
        state['mapped_saif_pin_rows_verified'] = 12 * PINS
        state['interpretation'] = 'Input SAIF TX and native x_probability are separate recorded observations. This audit verifies their exact intersection and original bytes, without asserting a physical X-to-known transition or its cause.'
        dump(out / 'state.json', state)
        aggregate = Counter()
        task_rows = []
        for task in state['tasks']:
            task_rows.append(dict(task_id=task['task_id'], phases={phase: dict(
                rows=task[phase]['rows'],
                measured_TX_positive=task[phase]['native_attribute_counts'].get('measured_input_TX_positive', 0),
                measured_TX_whole_window=task[phase]['native_attribute_counts'].get('measured_input_TX_whole_window', 0),
                native_x_probability_zero=task[phase]['native_attribute_counts'].get('x_probability:NATIVE_ZERO', 0),
                tx_native_attribute_cross_counts=task[phase]['tx_native_attribute_cross_counts'])
                for phase in ('before', 'after')}))
            for phase in ('before', 'after'):
                aggregate.update(task[phase]['tx_native_attribute_cross_counts'])
        dump(out / 'summary.json', dict(status=state['status'], qualification='NOT_QUALIFIED',
            native_pin_rows_replayed=state['native_pin_rows_replayed'],
            original_report_bytes_replayed=state['original_report_bytes_replayed'],
            compact_bytes_rehashed=state['compact_bytes_rehashed'],
            aggregate_tx_native_attribute_cross_counts=dict(aggregate), tasks=task_rows,
            limitations=LIMITS, interpretation=state['interpretation']))
        artifacts = {p.name: identity(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != 'output-manifest.json'}
        dump(out / 'output-manifest.json', dict(status=state['status'], artifacts=artifacts, qualification='NOT_QUALIFIED'))
        print(state['status'] + ' rows=' + str(state['native_pin_rows_replayed']), flush=True)
    except BaseException as error:
        state['status'] = 'FAILED_NOT_QUALIFIED'
        state['error'] = type(error).__name__ + ': ' + str(error)
        state['traceback'] = traceback.format_exc()
        dump(out / 'state.json', state)
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign', type=Path, required=True)
    p.add_argument('--native-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    audit(args.campaign, args.native_root, args.output)


if __name__ == '__main__':
    main()
