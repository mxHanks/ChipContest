#!/usr/bin/env python3
"""Offline review of actual PT compact SRAM pin queries and measured SAIF states.

This tool never runs EDA, opens declared server paths, updates old artifacts, or
qualifies annotation, Liberty power, task energy, timing, or a contest result.
Every comparison is evidence with an explicit unresolved policy, not a tolerance.
"""
from collections import Counter
from decimal import Decimal, localcontext
import argparse
import hashlib
import io
import stat
import struct
import sys
import json
from pathlib import Path
import re

HEADER = ('phase', 'desired_name', 'reported_name', 'toggle_rate', 'toggle_source',
          'glitch_rate', 'glitch_source', 'static_probability', 'static_source')
FIELDS = ('toggle_rate', 'glitch_rate', 'static_probability')
SOURCES = frozenset(('file', 'propagated', 'default', 'UNINITIALIZED',
                    'create_clock', 'set_switching_activity', 'set_case_analysis', 'implied'))
NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')
SHA = re.compile('[0-9a-f]{64}\\Z')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_identity(path, expected):
    """Freeze against a previously supplied expected SHA/size, not a fresh guess."""
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), 'regular non-symlink file required')
    require(type(expected.get('bytes')) is int and expected['bytes'] >= 0 and
            SHA.fullmatch(expected.get('sha256', '')), 'expected identity invalid')
    raw = path.read_bytes()
    found = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    require(all(found[key] == expected[key] for key in found), 'immutable input identity differs')
    return dict(path=str(path), **found)


def decimal_value(text, field):
    require(type(text) is str and 0 < len(text) <= 128 and NUMBER.fullmatch(text),
            'non-finite/invalid query number: ' + field)
    value = Decimal(text)
    require(value.is_finite() and (value == 0 or -400 <= value.adjusted() <= 400), 'query number not finite or exponent unreasonable')
    require(value != -2, 'query reports missing design object')
    require(value >= 0 or value == -1, 'invalid negative query number')
    require(field != 'static_probability' or value <= 1, 'probability exceeds one')
    return value


def parse_compact(path, phase, expected_names, raw_bytes=None):
    """Read the probe's exact TSV; preserve query strings and finite Decimals."""
    expected_names = set(expected_names)
    require(phase in ('before', 'after') and expected_names, 'invalid phase/inventory')
    rows = {}
    with (io.StringIO(raw_bytes.decode('utf-8'), newline='') if raw_bytes is not None else
          Path(path).open(encoding='utf-8', newline='')) as stream:
        header = stream.readline()
        require(header == '\t'.join(HEADER) + '\n', 'compact header differs')
        for number, raw in enumerate(stream, 2):
            require(raw.endswith('\n') and '\r' not in raw and '\x00' not in raw,
                    'unterminated/control-character compact row')
            parts = raw[:-1].split('\t')
            require(len(parts) == 9 and all(parts), 'compact row must have nine nonempty fields')
            row = dict(zip(HEADER, parts))
            name = row['desired_name']
            require(row['phase'] == phase, 'compact phase differs')
            require(name == row['reported_name'], 'PT desired/reported pin differs')
            require(name in expected_names, 'compact pin outside exact inventory')
            require(name not in rows, 'duplicate compact pin')
            for field in FIELDS:
                row[field + '_value'] = decimal_value(row[field], field)
                source = row[field.replace('rate', 'source') if field != 'static_probability' else 'static_source']
                require(source in SOURCES, 'unsupported query source: ' + source)
            row['line_number'] = number
            rows[name] = row
    require(set(rows) == expected_names, 'compact inventory incomplete')
    return rows


def checked_measurements(data, expected_names, duration_ticks):
    require(type(duration_ticks) is int and duration_ticks > 0, 'positive integer duration required')
    require(isinstance(data.get('pins'), list), 'measured pin list required')
    rows = {}
    metadata = {'mapped_path', 'path', 'kind'}
    stats = {'T0', 'T1', 'TX', 'TZ', 'TB', 'TC', 'IG'}
    for pin in data['pins']:
        require(isinstance(pin, dict) and set(pin) <= metadata | stats,
                'unrecognized measured statistic/field; no silent dropping')
        name = pin.get('mapped_path')
        require(name in expected_names and name not in rows, 'missing/extra/duplicate measurement')
        require(all(key in pin for key in ('T0', 'T1', 'TX', 'TC')), 'required measured state absent')
        require(all(type(pin.get(key, 0)) is int and pin.get(key, 0) >= 0 for key in stats),
                'measured stats must be nonnegative integers')
        require(sum(pin.get(key, 0) for key in ('T0', 'T1', 'TX', 'TZ', 'TB')) == duration_ticks,
                'measured dwell states do not sum to the exact SAIF duration')
        unknown = any(pin.get(key, 0) for key in ('TX', 'TZ', 'TB'))
        if not unknown:
            require(pin['T0'] + pin['T1'] == duration_ticks, 'known dwell does not cover duration')
        rows[name] = dict(pin)
    require(set(rows) == set(expected_names), 'measured inventory incomplete')
    return rows


def observed_comparison(pin, query, duration_ticks, timescale_seconds, library_time_unit_seconds):
    """Produce exact Decimal differences; never invent an acceptable tolerance.

    Decimal-exact equality is informative only. A nonzero residual remains for
    precision/conversion review; it is not automatically declared a mismatch or
    accepted by an arbitrary relative tolerance.
    """
    timescale, library_unit = Decimal(timescale_seconds), Decimal(library_time_unit_seconds)
    require(timescale.is_finite() and timescale > 0 and library_unit.is_finite() and library_unit > 0,
            'actual positive time units required')
    result = dict(mapped_path=pin['mapped_path'], raw_measurement=dict(pin), observations={})
    unknown = any(pin.get(key, 0) for key in ('TX', 'TZ', 'TB'))
    no_simple_formula = unknown or pin.get('IG', 0) != 0
    result['classification'] = ('UNKNOWN_OR_GLITCH_CONVERSION_REVIEW_REQUIRED' if no_simple_formula else
                                'KNOWN_NO_GLITCH')
    if no_simple_formula:
        for field in FIELDS:
            source = query[field.replace('rate', 'source') if field != 'static_probability' else 'static_source']
            result['observations'][field] = dict(raw=query[field], value=str(query[field + '_value']), source=source)
        return result
    require(pin['T0'] + pin['T1'] == duration_ticks, 'known dwell differs')
    with localcontext() as context:
        context.prec = 60
        elapsed = Decimal(duration_ticks) * timescale
        expected = dict(toggle_rate=Decimal(pin['TC']) * library_unit / elapsed,
                        glitch_rate=Decimal(0), static_probability=Decimal(pin['T1']) / duration_ticks)
        for field in FIELDS:
            found = query[field + '_value']
            source = query[field.replace('rate', 'source') if field != 'static_probability' else 'static_source']
            state = dict(raw=query[field], value=str(found), source=source, expected=str(expected[field]))
            if found == -1:
                state['comparison'] = 'QUERY_UNINITIALIZED_REVIEW_REQUIRED'
            else:
                delta = found - expected[field]
                state.update(delta=str(delta), comparison=('DECIMAL_EXACT_EQUAL' if delta == 0 else
                             'NONZERO_RESIDUAL_PRINTING_OR_CONVERSION_REVIEW_REQUIRED'))
                if field != 'static_probability':
                    state['delta_count_equivalent'] = str(delta * elapsed / library_unit)
                if expected[field] == 0 and found != 0:
                    state['comparison'] = 'KNOWN_ZERO_DIFFERS'
                if field == 'static_probability' and expected[field] == 1 and found != 1:
                    state['comparison'] = 'KNOWN_ONE_DIFFERS'
            if source != 'file':
                state['source_review'] = 'NOT_FILE_ANNOTATED_REVIEW_REQUIRED'
            result['observations'][field] = state
    return result


def source_counts(rows):
    return {field: dict(sorted(Counter(row[field.replace('rate', 'source') if field != 'static_probability'
        else 'static_source'] for row in rows.values()).items())) for field in FIELDS}


def phase_changes(before, after):
    require(set(before) == set(after), 'phase inventories differ')
    changes = []
    for name in sorted(before):
        changed = {key: [before[name][key], after[name][key]] for key in HEADER[3:]
                   if before[name][key] != after[name][key]}
        if changed:
            changes.append(dict(mapped_path=name, changed=changed))
    return changes

REQUEST_SCHEMA = 'xu-pt-pin-activity-review-request-v1'
RESULT_SCHEMA = 'xu-pt-pin-activity-review-v1'
NUMERIC_POLICY = 'decimal-exact-with-print-and-binary32-hypotheses-v1'
ROLES = frozenset(('probe_result', 'probe_tcl', 'pt_log', 'tool_version', 'units',
                   'before', 'after', 'inventory', 'measured', 'prepared', 'execution'))
ARTIFACTS = {'probe_tcl': 'probe.tcl', 'pt_log': 'pt.log', 'tool_version': 'tool-version.rpt',
             'units': 'units.rpt', 'before': 'pins-before.tsv', 'after': 'pins-after.tsv'}
COMPACT_STATUS = 'COMPACT_PIN_ACTIVITY_EXPORTED_REVIEW_PENDING_NOT_QUALIFIED'
MARKERS = ('XU_COMPACT_PIN_ACTIVITY_EXECUTED_REVIEW_PENDING', 'XU_COMPACT_PIN_PROBE_COMPLETE')
DIAGNOSTIC = re.compile(r'^[ \t]*(?:Error:|Error-|Fatal:|XU_FATAL:)|\b[1-9][0-9]* errors?\b', re.I)
PIN_WIDTHS = {'CLK': 1, 'CEN': 1, 'WEN': 16, 'A': 10, 'D': 16, 'EMA': 3,
              'EMAW': 2, 'GWEN': 1, 'RET1N': 1, 'Q': 16}
PIN_NAMES = frozenset(pin if width == 1 else '%s[%d]' % (pin, bit)
                     for pin, width in PIN_WIDTHS.items() for bit in range(width))
SOURCE_KEY = dict(toggle_rate='toggle_source', glitch_rate='glitch_source',
                  static_probability='static_source')


def load_json_bytes(raw):
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON constant')))


def identity(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def safe_file(path):
    path = Path(path)
    require(path.is_absolute(), 'local input path must be absolute')
    require(path.resolve(strict=True) == path and not path.is_symlink(),
            'symlink or noncanonical local input path')
    require(stat.S_ISREG(path.lstat().st_mode), 'regular local input required')
    return path


def declared_identity(record, label):
    require(isinstance(record, dict) and isinstance(record.get('path'), str) and
            record['path'].startswith('/') and not any(c in record['path'] for c in '\x00\r\n') and
            SHA.fullmatch(record.get('sha256', '')), 'invalid declared identity: ' + label)
    if 'bytes' in record:
        require(type(record['bytes']) is int and record['bytes'] >= 0, 'invalid bytes: ' + label)
    return record


def same_identity(left, right, label):
    declared_identity(left, label + '.left')
    declared_identity(right, label + '.right')
    require(left['path'] == right['path'] and left['sha256'] == right['sha256'] and
            ('bytes' not in left or 'bytes' not in right or left['bytes'] == right['bytes']),
            'provenance identity differs: ' + label)


def input_record(spec):
    require(isinstance(spec, dict) and set(spec) == {'local_path', 'origin_path', 'bytes', 'sha256'},
            'input requires exact local/origin/bytes/SHA fields')
    require(type(spec['bytes']) is int and spec['bytes'] >= 0 and SHA.fullmatch(spec['sha256']),
            'invalid frozen input identity')
    path = safe_file(spec['local_path'])
    raw = path.read_bytes()
    require(identity(raw) == {k: spec[k] for k in ('bytes', 'sha256')}, 'immutable input identity differs')
    origin = dict(path=spec['origin_path'], **identity(raw))
    declared_identity(origin, 'origin')
    return raw, origin


def parse_inventory(data, expected_macros, expected_pins):
    require(data.get('schema') == 'xu-mapped-sram-pin-inventory-v1' and
            data.get('status') == 'EXPORTED_REVIEW_PENDING', 'inventory schema/status differs')
    declared_identity(data.get('netlist'), 'inventory.netlist')
    require(isinstance(data.get('libraries'), list) and data['libraries'], 'actual inventory libraries absent')
    for item in data['libraries']:
        declared_identity(item, 'inventory.library')
    require(isinstance(data.get('provenance'), dict) and data['provenance'], 'inventory provenance absent')
    require(type(expected_macros) is int and expected_macros > 0 and
            type(expected_pins) is int and expected_pins == 67 * expected_macros,
            'explicit exact 67-pin macro scope required')
    records = data.get('macros')
    require(isinstance(records, list) and len(records) == expected_macros and
            type(data.get('macro_count')) is int and data['macro_count'] == expected_macros and
            type(data.get('pin_bit_count')) is int and data['pin_bit_count'] == expected_pins,
            'inventory declared scope differs')
    pins, macros = {}, set()
    for macro in records:
        name = macro.get('instance')
        require(isinstance(name, str) and name and not re.search(r'[\s\x00{}]', name) and
                all(part and part not in ('.', '..') for part in name.split('/')),
                'invalid literal actual macro name')
        require(name not in macros, 'duplicate actual macro')
        macros.add(name)
        require(macro.get('ref_name') == 'RAMSP1024X16' and
                isinstance(macro.get('lib_cell'), str) and
                re.fullmatch(r'[^/\s]+/RAMSP1024X16', macro['lib_cell']), 'unsupported actual macro reference/library')
        require(isinstance(macro.get('pins'), list) and len(macro['pins']) == 67, 'actual macro needs 67 pins')
        seen = set()
        for pin in macro['pins']:
            local = pin.get('name')
            require(local in PIN_NAMES and local not in seen, 'extra/duplicate actual macro pin')
            seen.add(local)
            full = name + '/' + local
            require(pin.get('full_name') == full and full not in pins, 'actual pin full_name differs/duplicates')
            direction = 'out' if local.startswith('Q[') else 'in'
            require(pin.get('direction') == direction, 'actual pin direction differs')
            pins[full] = dict(macro=name, name=local, direction=direction, lib_cell=macro['lib_cell'])
        require(seen == PIN_NAMES, 'actual macro pin set differs')
    require(len(pins) == expected_pins, 'actual pin total differs')
    return pins, macros


def unit_seconds(raw):
    text = raw.decode('utf-8')
    values = re.findall(r'^Time_unit[ \t]*:[ \t]*('+NUMBER.pattern[:-2]+r')[ \t]+Second[ \t]*$', text, re.M)
    # The installed report is deliberately parsed by its explicit physical unit.
    require(len(values) == 1, 'one explicit report_units Time_unit Second required')
    value = Decimal(values[0])
    require(value.is_finite() and value > 0, 'invalid actual library time unit')
    return value


def tcl_brace(value):
    require(isinstance(value, str) and value and not any(c in value for c in '{}\\\r\n'),
            'unsupported Tcl literal in bound provenance')
    return '{' + value + '}'


def checked_tcl_sources(text, prepared, task, libraries):
    """Accept the archived producer's explicit command lines, not comment hits.

    This is a conservative producer-format check, not an evaluator for arbitrary
    Tcl. There must be one actual occurrence of each bound loading command.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    expected = {
        'read_verilog': 'read_verilog ' + tcl_brace(prepared['netlist']['path']),
        'source': 'source ' + tcl_brace(prepared['analysis_sdc']['path']),
        'link_path': 'set_app_var link_path [list * ' + ' '.join(tcl_brace(lib['path']) for lib in libraries) + ']',
        'read_saif': 'if {![read_saif ' + tcl_brace(task['saif']['path']) + ' -strip_path ' +
                     tcl_brace(prepared['strip_path']) +
                     ' -report_inconsistent_annotation inconsistent.rpt]} {error {SAIF annotation command failed}}',
    }
    for command, required_line in expected.items():
        found = [line for line in lines if re.search(r'(?<![A-Za-z0-9_])' + command + r'[ \t]+', line)]
        require(found == [required_line], 'actual Tcl bound ' + command + ' command differs or is not unique')


def checked_evidence(request, raw, origins):
    require(set(request) == {'schema', 'task_id', 'expected_macro_count', 'expected_pin_bit_count',
                             'numeric_policy', 'files'}, 'request fields differ')
    require(request['schema'] == REQUEST_SCHEMA and request['numeric_policy'] == NUMERIC_POLICY,
            'unsupported request schema/numeric policy')
    require(type(request['task_id']) is int and 0 <= request['task_id'] < 12, 'invalid task id')
    require(set(request['files']) == ROLES, 'exact complete evidence roles required')
    data = {role: load_json_bytes(raw[role]) for role in
            ('probe_result', 'inventory', 'measured', 'prepared', 'execution')}
    probe, inventory, prepared, execution = (data[key] for key in
                                            ('probe_result', 'inventory', 'prepared', 'execution'))
    require(probe.get('status') == COMPACT_STATUS and
            probe.get('execution', {}).get('returncode') == 0, 'compact probe is not terminal exit-zero evidence')
    require(probe['execution'].get('command') == ['pt_shell', '-f', 'probe.tcl'], 'unexpected actual PT command')
    for role, filename in ARTIFACTS.items():
        same_identity(origins[role], probe.get('artifacts', {}).get(filename), 'compact.' + role)
    same_identity(probe['execution'].get('log'), origins['pt_log'], 'compact.execution.log')
    for role in ('prepared', 'execution'):
        same_identity(origins[role], probe.get('original_' + role), 'compact.original_' + role)
    same_identity(execution.get('prepared'), origins['prepared'], 'original.execution.prepared')
    require(execution.get('prepared_sha256_after') == origins['prepared']['sha256'],
            'original prepared after-run freeze differs')
    tool = declared_identity(execution.get('tool'), 'original.execution.tool')
    require(execution.get('tool_sha256_after') == tool['sha256'], 'original PT executable after-run freeze differs')
    require(execution.get('schema') == 'xu-soc-saif-power-execution-v1' and
            execution.get('status') in ('PARTIAL_EXECUTED_REVIEW_PENDING', 'EXECUTED_REVIEW_PENDING') and
            execution.get('qualification') == 'NOT_QUALIFIED', 'original PT execution is not a terminal review receipt')
    require(prepared.get('schema') == 'xu-soc-saif-power-prepared-v2' and
            prepared.get('status') in ('PARTIAL_PREPARED_REVIEW_PENDING', 'PREPARED_REVIEW_PENDING'),
            'unsupported original prepared schema/status')
    require(isinstance(prepared.get('tasks'), list) and isinstance(execution.get('tasks'), list) and
            all(isinstance(task, dict) and type(task.get('task_id')) is int for task in prepared['tasks'] + execution['tasks']),
            'original task records need strict integer task ids')
    tasks = [task for task in prepared['tasks'] if task['task_id'] == request['task_id']]
    runs = [task for task in execution.get('tasks', []) if task.get('task_id') == request['task_id']]
    require(len(tasks) == len(runs) == 1 and runs[0].get('execution', {}).get('returncode') == 0,
            'one exit-zero original task required')
    task = tasks[0]
    require(task.get('directory') == 'task_%02d' % request['task_id'], 'original task directory differs')
    same_identity(runs[0]['execution'].get('log'),
                  execution.get('artifacts', {}).get(task['directory'] + '/pt.log'),
                  'original task log/artifact')
    same_identity(task.get('measured_sram_pin_states'), origins['measured'], 'prepared.measured')
    same_identity(prepared.get('mapped_sram_inventory'), origins['inventory'], 'prepared.inventory')
    for key in ('netlist', 'analysis_sdc'):
        same_identity(prepared.get(key), probe.get(key), 'prepared/compact.' + key)
    same_identity(prepared.get('netlist'), inventory.get('netlist'), 'prepared/inventory.netlist')
    libraries = prepared.get('implementation', {}).get('libraries')
    require(isinstance(libraries, list) and libraries and len(libraries) == len(inventory['libraries']),
            'actual library inventory count differs')
    inventory_libs = {record['path']: record for record in inventory['libraries']}
    require(len(inventory_libs) == len(libraries), 'duplicate inventory libraries')
    for library in libraries:
        same_identity(library, inventory_libs.get(library.get('path')), 'prepared/inventory.library')
    for key in ('input_sha256_before', 'input_sha256_after'):
        require(isinstance(execution.get(key), dict), 'original input freeze absent')
        for library in libraries:
            require(execution[key].get(library['path']) == library['sha256'], 'original library input freeze differs')
        for field in ('netlist', 'analysis_sdc'):
            record = prepared[field]
            require(execution[key].get(record['path']) == record['sha256'], 'original mapped/SDC input freeze differs')
    require(execution.get('input_sha256_before') == execution.get('input_sha256_after'),
            'original PT inputs changed during run')
    log_lines = raw['pt_log'].decode('utf-8').splitlines()
    require(all(log_lines.count(marker) == 1 for marker in MARKERS), 'compact completion marker missing/duplicate')
    require(not any(DIAGNOSTIC.search(line) for line in log_lines), 'compact PT log contains fatal/error diagnostic')
    require(raw['tool_version'].decode('utf-8').strip() and
            raw['tool_version'].decode('utf-8').strip() in raw['pt_log'].decode('utf-8'),
            'actual PT tool version not bound to log')
    tcl = raw['probe_tcl'].decode('utf-8')
    require(all(tcl.count(marker) == 1 for marker in MARKERS) and
            'get_switching_activity -toggle_rate -glitch_rate -static_probability' in tcl,
            'compact query/marker contract absent from frozen Tcl')
    declared_identity(task.get('saif'), 'prepared.task.saif')
    same_identity(task['saif'], execution.get('artifacts', {}).get(task['directory'] + '/task-mapped.saif'),
                  'original mapped SAIF artifact')
    same_identity(origins['measured'], execution.get('artifacts', {}).get(task['directory'] + '/measured-sram-pins.json'),
                  'original measured pin artifact')
    declared_identity(task.get('canonical_saif'), 'prepared.task.canonical_saif')
    require(all(execution[key].get(task['canonical_saif']['path']) == task['canonical_saif']['sha256']
                for key in ('input_sha256_before', 'input_sha256_after')), 'original canonical SAIF input freeze differs')
    checked_tcl_sources(tcl, prepared, task, libraries)
    window = task.get('activity_window', {})
    duration = window.get('duration_ticks')
    require(type(duration) is int and duration > 0 and
            type(window.get('begin', {}).get('tick')) is int and type(window.get('end', {}).get('tick')) is int and
            window['end']['tick'] - window['begin']['tick'] == duration, 'formal task duration inconsistent')
    timescale = Decimal(str(window.get('timescale_seconds')))
    require(timescale.is_finite() and timescale > 0, 'actual SAIF time unit missing')
    bridge = task.get('mapped_macro_bridge_receipt', {})
    require(bridge.get('duration_ticks') == duration and
            Decimal(str(bridge.get('timescale_seconds'))) == timescale,
            'formal window and mapped SAIF bridge duration/unit differ')
    same_identity(task['saif'], bridge.get('output_saif'), 'prepared/bridge mapped SAIF')
    same_identity(task['canonical_saif'], bridge.get('input_saif'), 'prepared/bridge canonical SAIF')
    pins, macros = parse_inventory(inventory, request['expected_macro_count'], request['expected_pin_bit_count'])
    require(set(task.get('macro_names', [])) == macros and len(task['macro_names']) == len(macros),
            'prepared and actual macro identities differ')
    measured = checked_measurements(data['measured'], set(pins), duration)
    for name, pin in measured.items():
        require(pin.get('kind') in ('PORT', 'NET') and pin.get('path') == prepared.get('strip_path') + '/' + name,
                'measured SAIF path/kind differs from exact mapped pin')
    return dict(task=task, prepared=prepared, pins=pins, measured=measured, duration=duration,
                timescale=timescale, library_time_unit=unit_seconds(raw['units']))


def binary32(number):
    return struct.unpack('!f', struct.pack('!f', float(number)))[0]


def binary32_hypothesis(pin, duration, timescale, library_unit):
    """One uniform diagnostic model; empirical agreement never validates it."""
    scale = float(library_unit / timescale)
    rate = binary32(binary32(binary32(pin['TC']) / binary32(duration)) * scale)
    probability = binary32(pin['T1'] / (pin['T0'] + pin['T1'])) if pin['T0'] + pin['T1'] else .5
    return dict(toggle_rate=format(rate, '.6g'), static_probability=format(probability, '.6g'),
                status='UNIFORM_EMPIRICAL_HYPOTHESIS_ONLY_NOT_CONVERSION_PROOF')


def print_interval(raw):
    """Half a displayed last place, not a tolerance on the underlying value."""
    value = Decimal(raw)
    quantum = Decimal(1).scaleb(value.as_tuple().exponent)
    return value - quantum / 2, value + quantum / 2


def review_pin(pin, query, duration, timescale, library_unit):
    result = observed_comparison(pin, query, duration, str(timescale), str(library_unit))
    reasons = []
    for field in FIELDS:
        found = query[field + '_value']
        observation = result['observations'][field]
        source = query[SOURCE_KEY[field]]
        if source != 'file':
            reasons.append(field + ':SOURCE_' + source)
        if (found == -1) != (source == 'UNINITIALIZED'):
            reasons.append(field + ':VALUE_SOURCE_SENTINEL_CONTRADICTION')
        if found == -1:
            reasons.append(field + ':UNINITIALIZED')
        if 'expected' not in observation or found == -1:
            continue
        expected = Decimal(observation['expected'])
        if (expected in (0, 1) and field == 'static_probability' and found != expected) or \
                (expected == 0 and field in ('toggle_rate', 'glitch_rate') and found != 0) or \
                (expected > 0 and field in ('toggle_rate', 'glitch_rate') and found == 0):
            observation['numeric_review'] = 'KNOWN_BOUNDARY_DIFFERS'
            reasons.append(field + ':KNOWN_BOUNDARY_DIFFERS')
        elif found == expected:
            observation['numeric_review'] = 'DECIMAL_EXACT_EQUAL'
        else:
            low, high = print_interval(query[field])
            observation['display_interval'] = dict(low=str(low), high=str(high),
                limitation='Displayed decimal half-last-place only; no internal floating-point tolerance')
            observation['numeric_review'] = ('PRINT_ROUNDING_COMPATIBLE_REVIEW_PENDING' if low <= expected <= high else
                                            'CONVERSION_RESIDUAL_REVIEW_PENDING')
            reasons.append(field + ':' + observation['numeric_review'])
            if field in ('toggle_rate', 'glitch_rate'):
                width = (high - low) * Decimal(duration) * timescale / library_unit
                observation['display_interval_width_in_counts'] = str(width)
                observation['display_count_resolution'] = ('INSUFFICIENT_TO_DISTINGUISH_ONE_COUNT' if width >= 1 else
                                                          'SUB_COUNT_PRINT_RESOLUTION_ONLY')
    if result['classification'] != 'KNOWN_NO_GLITCH':
        reasons.append('UNKNOWN_DWELL_OR_IG_REQUIRES_SEPARATE_PT_LIBERTY_REVIEW')
    result['review_reasons'] = reasons
    hypothesis = binary32_hypothesis(pin, duration, timescale, library_unit)
    hypothesis['observed_numeric_agreement'] = {
        field: query[field + '_value'] == Decimal(hypothesis[field])
        for field in ('toggle_rate', 'static_probability')}
    hypothesis['unknown_policy'] = 'Unknown dwell retained; fitted SP fallback does not establish physical state or energy'
    result['uniform_binary32_hypothesis'] = hypothesis
    return result


def audit_request(request_path, output):
    request_path = safe_file(request_path)
    request_raw = request_path.read_bytes()
    request = load_json_bytes(request_raw)
    require(isinstance(request, dict) and isinstance(request.get('files'), dict), 'review request object/files required')
    require(set(request['files']) == ROLES, 'exact complete evidence roles required')
    raw, origins = {}, {}
    for role, spec in request['files'].items():
        raw[role], origins[role] = input_record(spec)
    context = checked_evidence(request, raw, origins)
    phases = {phase: parse_compact(None, phase, set(context['pins']), raw[phase]) for phase in ('before', 'after')}
    changes = phase_changes(phases['before'], phases['after'])
    output = Path(output).absolute()
    require(not output.exists() and output.parent.resolve(strict=True) == output.parent,
            'output must be a new directory in an existing canonical parent')
    output.mkdir()
    result = dict(schema=RESULT_SCHEMA, status='PARTIAL_KNOWN_UNRESOLVED_REVIEW_PENDING',
        qualification='NOT_QUALIFIED', numeric_policy=NUMERIC_POLICY, task_id=request['task_id'],
        request=dict(path=str(request_path), **identity(request_raw)), inputs=origins,
        generator=dict(path=str(Path(__file__).resolve()), **identity(Path(__file__).read_bytes())),
        scope=dict(macro_count=request['expected_macro_count'], pin_bit_count=len(context['pins']),
                   input_pin_count=sum(p['direction'] == 'in' for p in context['pins'].values()),
                   output_pin_count=sum(p['direction'] == 'out' for p in context['pins'].values())),
        duration_ticks=context['duration'], timescale_seconds=str(context['timescale']),
        actual_library_time_unit_seconds=str(context['library_time_unit']),
        phase_changes=changes, phase_change_count=len(changes), phases={},
        limitations=[
            'A file source says how PT obtained a value; it does not independently prove the value or power model.',
            'Measured SRAM states are an immutable prior extraction bound to prepared evidence, not a new parse of the raw SAIF.',
            'The binary32/6-digit rule is a uniform empirical hypothesis until independent actual PT synthetic probes validate its scope.',
            'Unknown TX/TZ/TB and IG are preserved, never converted to zero or accepted as a known state.',
            'No standard-cell coverage, inconsistent merged annotations, Liberty conditional power, full-SoC energy, timing or contest qualification is conferred.'])
    try:
        with (output / 'pin-observations.jsonl').open('x', encoding='utf-8') as stream:
            phase_counts = {phase: Counter() for phase in phases}
            for name in sorted(context['pins']):
                measured = context['measured'][name]
                record = dict(mapped_path=name, inventory=context['pins'][name], raw_measurement=measured, phases={})
                for phase, rows in phases.items():
                    review = review_pin(measured, rows[name], context['duration'], context['timescale'],
                                        context['library_time_unit'])
                    record['phases'][phase] = review
                    counts = phase_counts[phase]
                    counts[review['classification']] += 1
                    if any(measured.get(k, 0) for k in ('TX', 'TZ', 'TB')):
                        counts['UNKNOWN_DWELL:' + context['pins'][name]['direction']] += 1
                    if measured.get('TX', 0) == context['duration']:
                        counts['FULL_TX:' + context['pins'][name]['direction']] += 1
                    for field, observation in review['observations'].items():
                        counts[field + ':' + observation.get('numeric_review', 'UNKNOWN_OR_UNINITIALIZED_REVIEW_REQUIRED')] += 1
                    for reason in review['review_reasons']:
                        counts['REASON:' + reason] += 1
                    for field, agrees in review['uniform_binary32_hypothesis']['observed_numeric_agreement'].items():
                        counts['EMPIRICAL_BINARY32:' + field + (':AGREES' if agrees else ':DIFFERS')] += 1
                        category = 'KNOWN' if review['classification'] == 'KNOWN_NO_GLITCH' else 'UNKNOWN_OR_IG'
                        counts['EMPIRICAL_BINARY32:' + category + ':' + field + (':AGREES' if agrees else ':DIFFERS')] += 1
                stream.write(json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n')
        for phase, rows in phases.items():
            result['phases'][phase] = dict(source_counts=source_counts(rows), counts=dict(sorted(phase_counts[phase].items())))
        for role, spec in request['files'].items():
            reread, origin = input_record(spec)
            require(reread == raw[role] and origin == origins[role], 'input changed during audit: ' + role)
        require(request_path.read_bytes() == request_raw, 'request changed during audit')
        (output / 'request.json').write_bytes(request_raw)
        result['artifacts'] = {name: dict(path=str(output / name), **identity((output / name).read_bytes()))
                               for name in ('request.json', 'pin-observations.jsonl')}
        (output / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    except Exception as error:
        (output / 'failure.json').write_text(json.dumps(dict(status='FAIL', qualification='NOT_QUALIFIED',
            error=str(error), request_sha256=identity(request_raw)['sha256']), indent=2, sort_keys=True) + '\n')
        raise
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = audit_request(args.request, args.out)
    except (ValueError, OSError, KeyError, TypeError, ArithmeticError) as error:
        print('xu pin activity review failed: ' + str(error), file=sys.stderr)
        return 1
    print(result['status'] + ' qualification=' + result['qualification'] +
          ' pins=' + str(result['scope']['pin_bit_count']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
