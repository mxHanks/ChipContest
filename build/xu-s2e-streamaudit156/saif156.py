"""Independent immutable SAIF body and full canonical/native relocation audit."""
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from common156 import canonical, check, need, read

STRIP = 'tb_xu_soc_ppa/dut'
WIDTHS = dict(CLK=1, CEN=1, WEN=16, A=10, D=16, EMA=3, EMAW=2, GWEN=1, RET1N=1, Q=16)
PINS = {name if width == 1 else '%s[%d]' % (name, bit) for name, width in WIDTHS.items() for bit in range(width)}


def signals(path, duration):
    # SAIF inputs are ~13MB each. Native attribute reports (~800MB each) never
    # use this tree reader; those are line-streamed and bounded-block replayed.
    text = Path(path).read_text()
    tokens = re.finditer(r'//[^\n]*|/\*.*?\*/|\(|\)|"(?:\\.|[^"\\])*"|(?:\\.|[^\s()])+', text, re.S)
    roots, stack = [], []
    for match in tokens:
        token = match.group()
        if token.startswith('//') or token.startswith('/*'): continue
        if token == '(':
            node = []; (stack[-1] if stack else roots).append(node); stack.append(node)
        elif token == ')':
            need(stack, 'unbalanced SAIF close'); stack.pop()
        else:
            need(stack, 'SAIF atom outside expression'); stack[-1].append(token[1:-1] if token.startswith('"') else token)
    need(not stack and len(roots) == 1 and roots[0][0] == 'SAIFILE', 'invalid SAIF root')
    headers = {}
    for node in roots[0][1:]:
        if node[0] != 'INSTANCE':
            need(node[0] not in headers, 'duplicate SAIF header'); headers[node[0]] = node[1:]
    need(len(headers.get('DURATION', [])) == 1 and Decimal(headers['DURATION'][0]) == duration, 'actual130 SAIF duration differs')
    units = dict(s=Decimal(1), ms=Decimal('1e-3'), us=Decimal('1e-6'), ns=Decimal('1e-9'), ps=Decimal('1e-12'), fs=Decimal('1e-15'))
    scale = headers.get('TIMESCALE', [])
    need(len(scale) == 2 and scale[1] in units and Decimal(scale[0])*units[scale[1]] == Decimal('1e-15'), 'actual130 SAIF timescale differs')
    found, instances = {}, set()
    unescape = lambda v: re.sub(r'\\(.)', r'\1', v)
    def visit(node, parents):
        need(isinstance(node, list) and node, 'invalid SAIF body')
        if node[0] == 'INSTANCE':
            name = unescape(node[1]); scope = parents+[name]
            need(name and '/' not in name and '/'.join(scope) not in instances, 'duplicate/invalid SAIF hierarchy')
            instances.add('/'.join(scope))
            for child in node[2:]: visit(child, scope)
        elif node[0] in ('NET', 'PORT'):
            for signal in node[1:]:
                name = unescape(signal[0]); key = (node[0], '/'.join(parents+[name]))
                need(name and '/' not in name and key not in found, 'duplicate/invalid SAIF signal')
                stats = {}
                for pair in signal[1:]:
                    need(len(pair) == 2 and pair[0] not in stats, 'duplicate/invalid SAIF statistic')
                    number = Decimal(pair[1]); need(number.is_finite() and number >= 0 and number == int(number), 'invalid SAIF statistic value')
                    stats[pair[0]] = int(number)
                need({'T0', 'T1', 'TX', 'TC'} <= set(stats) and sum(stats.get(k, 0) for k in ('T0', 'T1', 'TX', 'TZ', 'TB')) == duration,
                     'SAIF dwell/statistic set differs')
                found[key] = stats
        else:
            for child in node[1:]:
                if isinstance(child, list): visit(child, parents)
    for node in roots[0][1:]:
        if node[0] == 'INSTANCE': visit(node, [])
    need(found, 'empty SAIF activity')
    return found, headers


def binding(mapping, inventory):
    need(mapping['schema'] == 'xu-s2e-sram-activity-alias-v1' and mapping['pin_widths'] == WIDTHS and
         mapping['macro_count'] == inventory['macro_count'] == 336 and mapping['alias_bit_count'] == 22512 and
         mapping['dut_scope'].replace('.', '/') == STRIP, 'own130 observer mapping schema/geometry differs')
    need(inventory['schema'] == 'xu-mapped-sram-pin-inventory-v1' and inventory['status'] == 'EXPORTED_REVIEW_PENDING' and
         inventory['pin_bit_count'] == 22512, 'own130 mapped inventory schema/geometry differs')
    left, right = {}, {}
    for row in mapping['macros']:
        instance = row['instance'].replace('.', '/')
        need(instance.startswith(STRIP+'/') and instance not in left, 'duplicate/outside canonical macro')
        left[instance] = instance
    for row in inventory['macros']:
        name = row['instance']; key = STRIP+'/'+name.replace('.', '/')
        need(key not in right and row['ref_name'] == 'RAMSP1024X16' and len(row['pins']) == 67 and
             {p['name'] for p in row['pins']} == PINS, 'native complete pin macro inventory differs')
        for pin in row['pins']:
            need(pin['full_name'] == name+'/'+pin['name'] and pin['direction'] == ('out' if pin['name'].startswith('Q[') else 'in'), 'native pin identity/direction differs')
        right[key] = STRIP+'/'+name
    need(set(left) == set(right) and len(left) == 336, 'own130 complete macro bijection differs')
    pairs = {key+'/'+pin: right[key]+'/'+pin for key in sorted(left) for pin in sorted(PINS)}
    need(len(pairs) == len(set(pairs.values())) == 22512, 'own130 full bit-pin bijection differs')
    return pairs, canonical(sorted((key, right[key][len(STRIP)+1:]) for key in left))


def audit(task, measured_path, mapping_path, inventory_path, duration):
    measured_receipt = read(measured_path); rows = measured_receipt['pins']
    measured = {row['mapped_path']: row for row in rows}
    need(len(measured) == len(rows) == 22512 and measured_receipt['status'] == 'MEASURED_INPUT_ACTIVITY_NOT_NATIVE_PT_OR_POWER_QUALIFIED', 'actual130 complete measured pins required')
    pairs, macro_hash = binding(read(mapping_path), read(inventory_path))
    need(set(STRIP+'/'+p for p in measured) == set(pairs.values()), 'measured/native macro pin set differs')
    canonical_saif = check(task['canonical_saif']['path'], task['canonical_saif'])
    mapped_saif = check(task['saif']['path'], task['saif'])
    source, source_headers = signals(canonical_saif['path'], duration)
    destination, destination_headers = signals(mapped_saif['path'], duration)
    need(source_headers == destination_headers, 'original SAIF headers changed')
    removed, injected, comparisons = set(), {}, []
    for original, target in sorted(pairs.items()):
        values = [source[(kind, original)] for kind in ('PORT', 'NET') if (kind, original) in source]
        need(values and all(v == values[0] for v in values), 'canonical pin missing/conflicting')
        existing = [source[(kind, target)] for kind in ('NET', 'PORT') if (kind, target) in source]
        need(all(v == values[0] for v in existing), 'existing native input pin conflicts')
        if original != target:
            removed.update((kind, original) for kind in ('NET', 'PORT') if (kind, original) in source)
            if not existing: injected[('PORT', target)] = values[0]
        expected_values = [destination[(kind, target)] for kind in ('PORT', 'NET') if (kind, target) in destination]
        need(expected_values and all(v == values[0] for v in expected_values), 'mapped original pin statistics differ')
        row = measured[target[len(STRIP)+1:]]
        need(row['path'] == target and (row['kind'], row['path']) in destination and
             values[0] == {k: v for k, v in row.items() if k not in ('path', 'kind', 'mapped_path')}, 'measured receipt/body statistics differ')
        comparisons.append([original, target, values[0]])
    preserved = {k: v for k, v in source.items() if k not in removed}
    need(set(destination) == set(preserved)|set(injected) and all(destination[k] == v for k, v in preserved.items()) and
         all(destination[k] == v for k, v in injected.items()), 'nonrelocated original SAIF body differs')
    bridge = task['mapped_macro_bridge_receipt']
    need(bridge['per_bit_comparison_sha256'] == canonical(comparisons), '130 recorded full per-bit comparison SHA differs')
    # Original macro hash records canonical full path and native relative path.
    need(bridge['macro_bijection_sha256'] == macro_hash, '130 recorded full macro bijection SHA differs')
    q = [row for key, row in measured.items() if key.rsplit('/', 1)[1].startswith('Q[')]
    summary = dict(pin_count=len(measured), q_pin_count=len(q), measured_unknown_bit_ticks=sum(row.get(k, 0) for row in rows for k in ('TX', 'TZ', 'TB')),
        q_tx_positive=sum(row.get('TX', 0)>0 for row in q), q_tx_full_window=sum(row.get('TX', 0) == duration for row in q),
        duration_ticks=duration, timescale_seconds='1E-15')
    need(summary == measured_receipt['measured_summary'] == task['measured_summary'] and
         summary['measured_unknown_bit_ticks'] == measured_receipt['alias_unknown_bit_ticks'] == bridge['measured_unknown_bit_ticks'] and len(q) == 5376,
         'complete original measured unknown summary differs')
    need(check(canonical_saif['path'], task['canonical_saif']) == canonical_saif and check(mapped_saif['path'], task['saif']) == mapped_saif,
         'original SAIF changed during body audit')
    return measured, dict(status='AUDITED_COMPLETE_ORIGINAL_SAIF_BODY_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
        canonical_saif=canonical_saif, mapped_saif=mapped_saif, measured_summary=summary,
        canonical_signal_records=len(source), mapped_signal_records=len(destination), nonrelocated_signal_records_preserved=len(preserved),
        per_bit_comparison_sha256=canonical(comparisons), macro_bijection_sha256=macro_hash)
