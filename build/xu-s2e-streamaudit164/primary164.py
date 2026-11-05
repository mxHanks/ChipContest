"""Primary line-stream native extractor. Entire original bytes are hashed."""
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import lzma
from pathlib import Path
import re
from common164 import BAD, check, identity, need, stat_key

CORE = {'activity_checker_status': 'string', 'full_name': 'string', 'glitch_rate': 'double',
        'static_probability': 'float', 'toggle_rate': 'double', 'x_probability': 'float'}
OPTIONAL = ['relative_toggle_rate', 'actual_fall_transition_max', 'actual_fall_transition_min',
    'actual_rise_transition_max', 'actual_rise_transition_min', 'actual_transition_max', 'actual_transition_min',
    'pin_capacitance_max', 'pin_capacitance_min', 'fanout_load', 'total_capacitance_max', 'total_capacitance_min',
    'wire_capacitance_max', 'wire_capacitance_min']
SELECTED = set(CORE)|set(OPTIONAL)
SEMANTICS = 'Before/after EXPLICIT update_power only; native getters may trigger lazy switching/power propagation.'


def category(name, value):
    if value is None: return 'ABSENT_FROM_NATIVE_REPORT'
    try: numeric = Decimal(value)
    except (InvalidOperation, ValueError): return 'NATIVE_TEXT_OR_NONFINITE'
    if not numeric.is_finite(): return 'NATIVE_TEXT_OR_NONFINITE'
    if name in ('static_probability', 'x_probability') and not 0 <= numeric <= 1: return 'NATIVE_SENTINEL'
    if name in ('toggle_rate', 'relative_toggle_rate', 'glitch_rate') and numeric < 0: return 'NATIVE_SENTINEL'
    return 'NATIVE_ZERO' if numeric == 0 else 'NATIVE_NONZERO'


SOURCE_LABELS = {'file': 'file', 'default': 'Default', 'propagated': 'propagated',
                 'no_switching_activity': 'UNINITIALIZED'}


def source_membership(path, expected, pins, source):
    """Hash every original byte; a native explicit empty list is evidence too.

    PT omits the List title for a source with zero nets and instead emits
    No nets found with activity info from SOURCE. This differs from a missing
    title, a truncated nonempty report, or an unidentified source.
    """
    need(source in SOURCE_LABELS, 'unsupported original source-report selector')
    label = SOURCE_LABELS[source]
    before = check(path, expected); key = stat_key(path)
    digest, matches, offset = hashlib.sha256(), {}, 0
    title, declaration, footer, count, mode = None, None, None, 0, None
    with Path(path).open('rb') as stream:
        for line in stream:
            digest.update(line)
            text = line.decode(errors='strict').rstrip('\r\n')
            need(not BAD.search(text), 'native source report contains error: '+str(path))
            header = re.fullmatch(r'List of nets with activity from (.+)', text)
            empty = re.fullmatch(r'No nets found with activity info from (.+)', text)
            if header or empty:
                need(declaration is None, 'duplicate or conflicting native source declaration')
                marker = header or empty
                need(marker.group(1) == label, 'native source declaration differs from requested selector')
                mode = 'NATIVE_NONEMPTY_LIST' if header else 'NATIVE_EXPLICIT_EMPTY_LIST'
                title = text if header else None
                declaration = dict(raw_text=line.decode(), report_byte_start=offset,
                    report_byte_end=offset+len(line), source_label=label, mode=mode)
            ending = re.fullmatch(r'([0-9]+) nets with activity info from (.+)', text)
            if ending:
                need(mode == 'NATIVE_NONEMPTY_LIST' and footer is None and ending.group(2) == label,
                     'native source footer/source differs')
                need(int(ending.group(1)) == count and count > 0, 'complete native source row count differs')
                footer = dict(raw_text=line.decode(), report_byte_start=offset,
                    report_byte_end=offset+len(line), row_count=count)
            if declaration is not None and line.startswith(b'\t'):
                columns = line.rstrip(b'\r\n').split(b'\t')
                need(mode == 'NATIVE_NONEMPTY_LIST' and footer is None and len(columns) == 3 and
                     columns[0] == b'' and columns[1].strip() and columns[2].strip(),
                     'native source columns/mode differ')
                count += 1
                driver = columns[2].strip().decode()
                if driver in pins:
                    matches.setdefault(driver, []).append(dict(raw_text=line.decode(), report_byte_start=offset,
                        report_byte_end=offset+len(line), title=title, match_column='exact saved native driver-pin column'))
            offset += len(line)
    # Byte identity and native report semantics deliberately have separate gates:
    # the old combined error misidentified a valid explicit-empty report as SHA failure.
    need(key == stat_key(path) and digest.hexdigest() == before['sha256'] and offset == before['bytes'],
         'complete source-report streaming identity differs')
    need(declaration is not None and
         ((mode == 'NATIVE_EXPLICIT_EMPTY_LIST' and not matches and count == 0 and footer is None) or
          (mode == 'NATIVE_NONEMPTY_LIST' and footer is not None)),
         'native source report declaration/completeness differs')
    after = check(path, expected); need(after == before, 'source-report changed during membership parse')
    return dict(original_before=before, original_after=after, title=title, requested_source=source,
        native_declaration=declaration, native_footer=footer, native_row_count=count,
        complete_source_bytes_streamed=offset, stream_sha256=digest.hexdigest(),
        interpretation='Saved driver-column match only; absent load/input pin does not prove no file annotation.'), matches


def extract(path, expected, measured, phase, out, memberships, previous=None):
    """Only a line and selected attributes of the current block are buffered."""
    before = check(path, expected); original_stat = stat_key(path)
    digest, block_digest = hashlib.sha256(), None
    marker, start, attrs, pending, design, diagnostics = None, 0, {}, None, False, []
    offset, seen, current = 0, set(), {}
    counts, cross, changes, diagnostic_counts = Counter(), Counter(), Counter(), Counter()
    need(not Path(out).exists(), 'fresh compact extraction required')

    def finish(end, stream):
        if marker is None: return
        need(marker in measured and marker not in seen and 0 < end-start < 2*1024*1024, 'native pin inventory/block size differs')
        need(design and pending is None and all(k in attrs and attrs[k]['type'] == v for k, v in CORE.items()), 'native pin core/scope differs: '+marker)
        need(attrs['full_name']['value'] == marker, 'native full_name differs')
        sig = {k: [v['type'], v['value']] for k, v in attrs.items()}; current[marker] = sig
        if previous is not None:
            need(marker in previous, 'before/after pin inventory differs')
            for name in SELECTED: changes[name+(':UNCHANGED' if previous[marker].get(name) == sig.get(name) else ':CHANGED')] += 1
        classes = {name: category(name, attrs[name]['value'] if name in attrs else None) for name in SELECTED}
        for name, value in classes.items(): counts[name+':'+value] += 1
        values = {k: v for k, v in measured[marker].items() if k not in ('kind', 'path', 'mapped_path')}
        role = 'SRAM_OUTPUT_Q' if marker.rsplit('/', 1)[1].startswith('Q[') else 'SRAM_INPUT'
        duration = sum(values.get(k, 0) for k in ('T0', 'T1', 'TX', 'TZ', 'TB'))
        tx = 'TX_ZERO' if values.get('TX', 0) == 0 else 'TX_WHOLE_WINDOW' if values['TX'] == duration else 'TX_PARTIAL_WINDOW'
        counts['role:'+role] += 1; counts['measured:'+tx] += 1
        counts['MEASURED_UNKNOWN_ANY_POSITIVE'] += any(values.get(k, 0)>0 for k in ('TX', 'TZ', 'TB'))
        cross['|'.join((role, tx, 'getter_x='+classes['x_probability'], 'getter_sp='+classes['static_probability'], 'getter_toggle='+classes['toggle_rate']))] += 1
        row = dict(pin=marker, phase=phase, phase_semantics=SEMANTICS, original_byte_range=[start, end],
            block_sha256=block_digest.hexdigest(), attributes=attrs, diagnostics=diagnostics, classes=classes,
            measured_saif=values, pin_role=role, source_driver_matches={k: m.get(marker, []) for k, m in memberships.items()},
            qualification='NOT_QUALIFIED')
        stream.write((json.dumps(row, sort_keys=True)+'\n').encode()); seen.add(marker)

    with Path(path).open('rb') as source, lzma.open(str(out), 'xb', preset=1) as compact:
        for line in source:
            digest.update(line); text = line.decode(errors='strict').rstrip('\r\n')
            need(not BAD.search(text), 'native report contains error: '+str(path))
            match = re.fullmatch(r'XU_SRAM_PIN name=(.+)', text)
            if match:
                finish(offset, compact)
                marker, start, attrs, pending, design, diagnostics = match.group(1), offset, {}, None, False, []
                block_digest = hashlib.sha256()
            if marker is None:
                need(not line.strip(), 'unrepresented nonempty native report prefix')
                need(offset == 0 and not line, 'even whitespace native report prefix must be represented')
            else:
                block_digest.update(line)
                design = design or re.fullmatch(r'Design\s*:\s*xu_soc_ppa_top\s*', text) is not None
                if pending is not None:
                    need(text[:1].isspace() and text.strip() and not re.match(r'\s+(?:string|float|double|boolean|integer)\s+', text), 'invalid wrapped native value')
                    attrs[pending]['value'] = text.strip(); attrs[pending]['raw_text'] += line.decode()
                    attrs[pending]['byte_end'] = offset+len(line); pending = None
                else:
                    item = re.match(r'^[ \t]+(string|float|double|boolean|integer)[ \t]+(\w+)\b[ \t]*(.*)$', text)
                    if item and item.group(2) in SELECTED:
                        typ, name, value = item.groups(); need(name not in attrs, 'duplicate native selected attribute')
                        attrs[name] = dict(type=typ, value=value.strip(), raw_text=line.decode(), byte_start=offset, byte_end=offset+len(line))
                        if not value.strip(): pending = name
                if re.match(r'^(?:Information|Warning|Error|Fatal):|^\s*Running (?:switching activity propagation|averaged power analysis|power calculation)', text):
                    diagnostics.append(dict(raw_text=line.decode(), byte_start=offset, byte_end=offset+len(line)))
                    diagnostic_counts[text.strip()] += 1
            offset += len(line)
        finish(offset, compact)
    need(seen == set(measured) and original_stat == stat_key(path) and offset == before['bytes'] and digest.hexdigest() == before['sha256'],
         'native extraction complete pin/byte inventory or SHA differs')
    after = check(path, expected); need(after == before, 'original native report changed during extraction')
    return dict(phase=phase, status='EXTRACTED_DIAGNOSTIC_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
        original_before=before, original_after=after, compact=identity(out), pin_count=len(seen),
        selected_attribute_counts=dict(counts), measured_native_cross_counts=dict(cross), before_after_counts=dict(changes),
        native_diagnostic_counts=dict(diagnostic_counts)), current
