"""Streaming native pin audit; a getter X=0 never proves known measured Q."""
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from common146 import BAD, identity, need, write

CORE = {'activity_checker_status': 'string', 'full_name': 'string', 'glitch_rate': 'double',
        'static_probability': 'float', 'toggle_rate': 'double', 'x_probability': 'float'}
SELECTED = set(CORE)|{'relative_toggle_rate', 'actual_transition_max', 'actual_transition_min',
                      'pin_capacitance_max', 'pin_capacitance_min', 'total_capacitance_max', 'total_capacitance_min'}
LIMITS = [
    'DIAGNOSTIC_NOT_QUALIFIED: measured TX/TZ/TB retained; native x_probability=0 is a getter value, never proof of physically known Q.',
    'Before/after means before/after EXPLICIT update_power; attribute getters may trigger lazy propagation and power.',
    'Source membership matches saved driver-pin columns only; absence for a load does not prove no file annotation.',
    'SRAM when/internal_power modes, timing coverage/RDC, numerical workloads and contest energy remain unqualified.'
]


def number(value):
    try: result = Decimal(value)
    except (InvalidOperation, ValueError): return None
    return result if result.is_finite() else None


def category(name, value):
    if value is None: return 'ABSENT_FROM_NATIVE_REPORT'
    numeric = number(value)
    if numeric is None: return 'NATIVE_TEXT'
    if name in ('x_probability', 'static_probability') and not 0 <= numeric <= 1: return 'NATIVE_SENTINEL'
    if name in ('toggle_rate', 'relative_toggle_rate', 'glitch_rate') and numeric < 0: return 'NATIVE_SENTINEL'
    return 'NATIVE_ZERO' if numeric == 0 else 'NATIVE_NONZERO'


def source_membership(path, pins):
    result, title = {}, None
    with Path(path).open('rb') as source:
        offset = 0
        for line in source:
            if line.startswith(b'List of nets with activity from '):
                need(title is None, 'duplicate source-report title')
                title = line.decode().rstrip('\r\n')
            if title is not None and line.startswith(b'\t'):
                columns = line.rstrip(b'\r\n').split(b'\t')
                need(len(columns) == 3 and columns[0] == b'', 'native source report columns differ')
                driver = columns[2].strip().decode()
                if driver in pins:
                    result.setdefault(driver, []).append([offset, offset+len(line)])
            offset += len(line)
    need(title is not None, 'native source report title missing: '+str(path))
    return result


def audit_phase(directory, phase, measured, previous, compact):
    path = directory/('sram-pins-%s.rpt' % phase)
    before = path.stat()
    digest, count, offset = hashlib.sha256(), 0, 0
    seen, current, counts, cross, changes, diagnostics = set(), {}, Counter(), Counter(), Counter(), Counter()
    membership = {source: source_membership(directory/('source-%s-%s.rpt' % (source, phase)), measured)
                  for source in ('file', 'default', 'propagated', 'no_switching_activity')}
    marker, start, attrs, pending, design, block_digest = None, 0, {}, None, False, None

    def finish(end, output):
        if marker is None: return
        need(marker in measured and marker not in seen, 'unexpected/duplicate native pin: '+str(marker))
        need(design and pending is None and all(k in attrs and attrs[k]['type'] == typ for k, typ in CORE.items()),
             'native pin report design/core/wrapped value differs: '+marker)
        need(attrs['full_name']['value'] == marker, 'native full_name differs')
        signature = {k: [v['type'], v['value']] for k, v in attrs.items()}
        current[marker] = signature
        if previous is not None:
            need(marker in previous, 'before/after native inventory differs')
            for attr in SELECTED:
                changes[attr+(':UNCHANGED' if previous[marker].get(attr) == signature.get(attr) else ':CHANGED')] += 1
        classes = {k: category(k, attrs[k]['value'] if k in attrs else None) for k in SELECTED}
        for key, value in classes.items(): counts[key+':'+value] += 1
        values = {k: v for k, v in measured[marker].items() if k not in ('kind', 'path', 'mapped_path')}
        role = 'SRAM_OUTPUT_Q' if marker.rsplit('/', 1)[1].startswith('Q[') else 'SRAM_INPUT'
        tx = 'MEASURED_TX_POSITIVE' if values.get('TX', 0)>0 else 'MEASURED_TX_ZERO'
        counts['role:'+role] += 1
        counts[tx] += 1
        counts['MEASURED_UNKNOWN_ANY_POSITIVE'] += any(values.get(k, 0)>0 for k in ('TX', 'TZ', 'TB'))
        cross['|'.join((role, tx, 'getter_x='+classes['x_probability'], 'getter_toggle='+classes['toggle_rate']))] += 1
        output.write(json.dumps(dict(pin=marker, phase=phase, original_byte_range=[start, end],
            original_block_sha256=block_digest.hexdigest(), measured_saif=values, native_attributes=attrs,
            native_classes=classes, role=role, source_driver_matches={k: v.get(marker, []) for k, v in membership.items()},
            qualification='DIAGNOSTIC_NOT_QUALIFIED'), sort_keys=True)+'\n')
        seen.add(marker)

    # Only one line and one pin's selected attributes are resident; never read
    # an 800MB attribute report as text/bytes or split it into whole-file blocks.
    with path.open('rb') as source, compact.open('x') as output:
        for line in source:
            digest.update(line)
            need(not BAD.search(line.decode(errors='replace')), 'native report contains error: '+str(path))
            match = re.fullmatch(rb'XU_SRAM_PIN name=(.+)\r?\n?', line)
            if match:
                finish(offset, output)
                marker, start, attrs, pending, design = match.group(1).decode(), offset, {}, None, False
                block_digest = hashlib.sha256(); count += 1
            if marker is not None:
                block_digest.update(line)
                text = line.decode(errors='strict').rstrip('\r\n')
                design = design or re.fullmatch(r'Design\s*:\s*xu_soc_ppa_top\s*', text) is not None
                if pending is not None:
                    need(text[:1].isspace() and text.strip() and not re.match(r'\s+(?:string|float|double|boolean|integer)\s+', text),
                         'invalid native wrapped selected value')
                    attrs[pending]['value'] = text.strip(); attrs[pending]['byte_end'] = offset+len(line); pending = None
                else:
                    attr = re.match(r'^[ \t]+(string|float|double|boolean|integer)[ \t]+(\w+)\b[ \t]*(.*)$', text)
                    if attr and attr.group(2) in SELECTED:
                        typ, name, value = attr.groups()
                        need(name not in attrs, 'duplicate native selected attribute: '+name)
                        attrs[name] = dict(type=typ, value=value.strip(), byte_start=offset, byte_end=offset+len(line))
                        if not value.strip(): pending = name
                if re.match(r'^(?:Information|Warning|Error|Fatal):|^\s*Running (?:switching activity propagation|averaged power analysis|power calculation)', text):
                    diagnostics[text.strip()] += 1
            else:
                need(not line.strip(), 'unrepresented prefix in native pin report')
            offset += len(line)
        finish(offset, output)
    after = path.stat()
    need((before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino),
         'native report changed while streaming')
    need(seen == set(measured) and count == len(measured), 'native complete exact pin inventory differs')
    return dict(status='AUDITED_DIAGNOSTIC_NOT_QUALIFIED', phase=phase, pin_count=count,
                original=dict(path=str(path), bytes=offset, sha256=digest.hexdigest()), compact=identity(compact),
                selected_attribute_counts=dict(counts), measured_native_cross_counts=dict(cross),
                before_after_counts=dict(changes), native_diagnostic_counts=dict(diagnostics),
                source_membership_counts={k: len(v) for k, v in membership.items()}), current


def audit(directory, measured_path, output_directory=None):
    directory = Path(directory)
    output = Path(output_directory) if output_directory is not None else directory
    from common146 import read
    measured_receipt = read(measured_path)
    measured = {p['mapped_path']: p for p in measured_receipt['pins']}
    need(len(measured) == len(measured_receipt['pins']), 'duplicate measured mapped pin')
    result = dict(schema='xu-native-pin-audit146-v1', status='AUDITED_DIAGNOSTIC_NOT_QUALIFIED',
                  qualification='NOT_QUALIFIED', measured=identity(measured_path), limitations=LIMITS, phases=[])
    previous = None
    for phase in ('before', 'after'):
        entry, previous = audit_phase(directory, phase, measured, previous, output/('native-%s.jsonl' % phase))
        result['phases'].append(entry)
    write(output/'native-audit.json', result)
    return result
