"""Independent bounded-block reparse of every byte in primary156 extraction."""
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import lzma
from pathlib import Path
import re
from common156 import check, identity, need, stat_key

CORE = {'activity_checker_status': 'string', 'full_name': 'string', 'glitch_rate': 'double',
        'static_probability': 'float', 'toggle_rate': 'double', 'x_probability': 'float'}
SELECTED = set(CORE)|{'relative_toggle_rate', 'actual_fall_transition_max', 'actual_fall_transition_min',
    'actual_rise_transition_max', 'actual_rise_transition_min', 'actual_transition_max', 'actual_transition_min',
    'pin_capacitance_max', 'pin_capacitance_min', 'fanout_load', 'total_capacitance_max', 'total_capacitance_min',
    'wire_capacitance_max', 'wire_capacitance_min'}


def classification(name, value):
    if value is None: return 'ABSENT_FROM_NATIVE_REPORT'
    try: numeric = Decimal(value)
    except (InvalidOperation, ValueError): return 'NATIVE_TEXT_OR_NONFINITE'
    if not numeric.is_finite(): return 'NATIVE_TEXT_OR_NONFINITE'
    if name in {'static_probability', 'x_probability'} and (numeric < 0 or numeric > 1): return 'NATIVE_SENTINEL'
    if name in {'toggle_rate', 'relative_toggle_rate', 'glitch_rate'} and numeric < 0: return 'NATIVE_SENTINEL'
    return 'NATIVE_NONZERO' if numeric else 'NATIVE_ZERO'


def parse_block(raw, start, pin):
    """A second parser over a bounded raw block, independent of line-state extraction."""
    need(raw.startswith(('XU_SRAM_PIN name='+pin+'\n').encode()), 'raw block marker differs')
    need(b'\nXU_SRAM_PIN name=' not in raw, 'raw block contains another native pin')
    need(re.search(rb'(?m)^Design\s*:\s*xu_soc_ppa_top\s*$', raw) is not None, 'raw block design differs')
    lines = raw.splitlines(keepends=True)
    offsets, pos = [], start
    for line in lines: offsets.append(pos); pos += len(line)
    attrs, diagnostics = {}, []
    for index, line in enumerate(lines):
        if re.match(rb'^(?:Information|Warning|Error|Fatal):', line) or re.match(
                rb'^[ \t]*Running (?:switching activity propagation|averaged power analysis|power calculation)', line):
            diagnostics.append(dict(raw_text=line.decode(), byte_start=offsets[index], byte_end=offsets[index]+len(line)))
        match = re.match(rb'^[ \t]+(string|float|double|boolean|integer)[ \t]+(\w+)\b[ \t]*([^\r\n]*)\r?\n?$', line)
        if match is None: continue
        typ, name, value = [v.decode() for v in match.groups()]
        if name not in SELECTED: continue
        need(name not in attrs, 'duplicate raw selected attribute')
        end = index+1
        if not value.strip():
            need(end < len(lines) and lines[end][:1] in (b' ', b'\t') and lines[end].strip() and
                 re.match(rb'^[ \t]+(?:string|float|double|boolean|integer)[ \t]', lines[end]) is None, 'invalid raw wrapped attribute')
            value = lines[end].strip().decode(); end += 1
        attrs[name] = dict(type=typ, value=value.strip(), raw_text=b''.join(lines[index:end]).decode(),
            byte_start=offsets[index], byte_end=offsets[end] if end < len(lines) else pos)
    need(set(CORE) <= set(attrs) and all(attrs[k]['type'] == v for k, v in CORE.items()) and
         attrs['full_name']['value'] == pin, 'raw block native core types/identity differ')
    return attrs, diagnostics


def replay(path, expected, compact_path, compact_expected, measured, phase, primary, out, memberships, previous=None, sample_limit=4):
    before, compact_before = check(path, expected), check(compact_path, compact_expected)
    original_stat = stat_key(path)
    digest, offset, seen, current = hashlib.sha256(), 0, set(), {}
    counts, cross, changes, diagnostic_counts = Counter(), Counter(), Counter(), Counter()
    samples, categories = [], set()
    with Path(path).open('rb') as original, lzma.open(str(compact_path), 'rb') as compact:
        for line in compact:
            need(line.endswith(b'\n') and len(line) < 128*1024, 'compact pin line malformed/oversize')
            def unique(pairs):
                value = {}
                for key, item in pairs: need(key not in value, 'duplicate compact key'); value[key] = item
                return value
            row = json.loads(line.decode(), object_pairs_hook=unique); pin = row['pin']
            need(pin in measured and pin not in seen and row['phase'] == phase and row['qualification'] == 'NOT_QUALIFIED', 'compact pin/phase differs')
            begin, end = row['original_byte_range']
            need(begin == offset and type(end) is int and 0 < end-begin < 2*1024*1024, 'compact block range differs')
            raw = original.read(end-begin)
            need(len(raw) == end-begin and hashlib.sha256(raw).hexdigest() == row['block_sha256'], 'raw block SHA differs')
            digest.update(raw); attrs, diagnostics = parse_block(raw, begin, pin)
            need(attrs == row['attributes'] and diagnostics == row['diagnostics'], 'independent raw attribute/diagnostic parse differs')
            classes = {name: classification(name, attrs[name]['value'] if name in attrs else None) for name in SELECTED}
            need(classes == row['classes'], 'independent raw classifications differ')
            values = {k: v for k, v in measured[pin].items() if k not in ('kind', 'path', 'mapped_path')}
            need(values == row['measured_saif'], 'compact original measured input differs')
            need(row['source_driver_matches'] == {k: value.get(pin, []) for k, value in memberships.items()}, 'compact source membership differs')
            for name, value in classes.items(): counts[name+':'+value] += 1
            role = 'SRAM_OUTPUT_Q' if re.search(r'/Q\[\d+\]$', pin) else 'SRAM_INPUT'
            need(role == row['pin_role'], 'compact native pin role differs')
            duration = values['T0']+values['T1']+sum(values.get(k, 0) for k in ('TX', 'TZ', 'TB'))
            tx = 'TX_ZERO' if not values.get('TX', 0) else 'TX_WHOLE_WINDOW' if values['TX'] == duration else 'TX_PARTIAL_WINDOW'
            counts['role:'+role] += 1; counts['measured:'+tx] += 1
            counts['MEASURED_UNKNOWN_ANY_POSITIVE'] += any(values.get(k, 0)>0 for k in ('TX', 'TZ', 'TB'))
            cross['|'.join((role, tx, 'getter_x='+classes['x_probability'], 'getter_sp='+classes['static_probability'], 'getter_toggle='+classes['toggle_rate']))] += 1
            signature = {k: [v['type'], v['value']] for k, v in attrs.items()}; current[pin] = signature
            if previous is not None:
                need(pin in previous, 'independent before/after inventory differs')
                for name in SELECTED: changes[name+(':UNCHANGED' if previous[pin].get(name) == signature.get(name) else ':CHANGED')] += 1
            for diagnostic in diagnostics: diagnostic_counts[diagnostic['raw_text'].strip()] += 1
            sample_key = role+'|'+tx+'|'+classes['static_probability']+'|'+classes['toggle_rate']
            if len(samples) < sample_limit and sample_key not in categories:
                categories.add(sample_key); stem = '%s-sample_%02d' % (phase, len(samples))
                raw_path, line_path = Path(out)/(stem+'.original.txt'), Path(out)/(stem+'.compact.jsonl')
                with raw_path.open('xb') as target: target.write(raw)
                with line_path.open('xb') as target: target.write(line)
                samples.append(dict(pin=pin, category=sample_key, original_block=identity(raw_path), compact_line=identity(line_path),
                    original_report_range=[begin, end], original_report=before, measured_saif=values,
                    source_driver_matches=row['source_driver_matches'], qualification='NOT_QUALIFIED'))
            offset = end; seen.add(pin)
        need(original.read(1) == b'', 'unrepresented native report trailing bytes')
    need(seen == set(measured) and original_stat == stat_key(path) and offset == expected['bytes'] and digest.hexdigest() == expected['sha256'],
         'independent full original report bytes/SHA/inventory differs')
    need(dict(counts) == primary['selected_attribute_counts'] and dict(cross) == primary['measured_native_cross_counts'] and
         dict(changes) == primary['before_after_counts'] and dict(diagnostic_counts) == primary['native_diagnostic_counts'], 'independent primary summary differs')
    after = check(path, expected); need(after == before, 'original changed during raw replay')
    need(check(compact_path, compact_expected) == compact_before, 'compact changed during raw replay')
    return dict(status='REPLAYED_EVERY_ORIGINAL_BLOCK_NOT_QUALIFIED', qualification='NOT_QUALIFIED', phase=phase,
        original_before=before, original_after=after, compact_before=compact_before, compact_after=compact_before,
        pin_count=len(seen), complete_original_bytes_replayed=offset, raw_block_sha_and_selected_attribute_text_verified=True,
        selected_attribute_counts=dict(counts), measured_native_cross_counts=dict(cross), before_after_counts=dict(changes),
        native_diagnostic_counts=dict(diagnostic_counts), samples=samples), current
