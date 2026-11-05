"""Exact complete mixed-SRAM RTL-to-native inventory and lossless SAIF bridge."""
import copy
from pathlib import Path
import re
from common146 import canonical, identity, need, write

PIN_WIDTHS = {ref: dict(CLK=1, CEN=1, WEN=16, A=address, D=16, EMA=3,
                       EMAW=2, GWEN=1, RET1N=1, Q=16)
              for ref, address in [('RAMSP1024X16', 10), ('RAMSP128X16', 7)]}
STRIP = 'tb_xu_soc_ppa/dut'
COMPONENT = r'[A-Za-z_][A-Za-z0-9_$]*(?:\[\d+\])?'


def pin_names(ref):
    need(ref in PIN_WIDTHS, 'unsupported actual native SRAM ref: '+ref)
    return {p if w == 1 else '%s[%d]' % (p, bit)
            for p, w in PIN_WIDTHS[ref].items() for bit in range(w)}


def inventory_rows(path, groups):
    macros, seen = {}, set()
    with Path(path).open() as source:
        need(source.readline().rstrip('\n') == 'kind\tcell\tref_or_pin\tlibcell_or_direction', 'native inventory TSV header differs')
        for line in source:
            parts = line.rstrip('\n').split('\t')
            need(len(parts) == 4 and tuple(parts) not in seen, 'duplicate/malformed actual native inventory row')
            seen.add(tuple(parts))
            kind, cell, value, extra = parts
            need(all(re.fullmatch(COMPONENT+r'(?:\.'+COMPONENT+r')*', c) for c in cell.split('/')),
                 'unsupported literal native macro name: '+cell)
            if kind == 'MACRO':
                need(cell not in macros and value in PIN_WIDTHS and extra.count('/') == 1 and
                     extra.split('/')[1] == value, 'duplicate/unresolved/unsupported native macro')
                macros[cell] = dict(instance=cell, ref_name=value, lib_cell=extra, pins=[])
            elif kind == 'PIN':
                need(cell in macros and value.startswith(cell+'/'), 'native pin parent absent or differs')
                name = value[len(cell)+1:]
                need(name in pin_names(macros[cell]['ref_name']) and extra == ('out' if name.startswith('Q[') else 'in'),
                     'native pin name/direction differs: '+value)
                macros[cell]['pins'].append(dict(name=name, full_name=value, direction=extra))
            else:
                raise ValueError('unknown native inventory row kind')
    counts = {g['name']: 0 for g in groups}
    for row in macros.values():
        need({p['name'] for p in row['pins']} == pin_names(row['ref_name']) and
             len(row['pins']) == len(pin_names(row['ref_name'])), 'native macro complete pin set differs')
        matches = [g for g in groups if g['macro_ref'] == row['ref_name'] and
                   re.fullmatch(re.escape(g['instance_pattern']).replace(r'\*', '.*').replace(r'\?', '.'), row['instance'])]
        need(len(matches) == 1, 'native macro must match exactly one frozen memory group: '+row['instance'])
        row['group'] = matches[0]['name']; counts[row['group']] += 1
    need(all(counts[g['name']] == g['count'] for g in groups) and len(macros) == sum(g['count'] for g in groups),
         'native full inventory group/total count differs')
    return [macros[key] for key in sorted(macros)]


def bijection(rtl, native):
    need(rtl['schema'] == 'xu-profile-macro-inventory145-v1' and
         rtl['status'] == 'ELABORATED_REVIEW_PENDING_NOT_QUALIFIED' and rtl['dut_scope'] == 'tb_xu_soc_ppa.dut',
         'actual activity145 full macro inventory required')
    source, destination = {}, {}
    for row in rtl['macros']:
        relative = row['relative_instance']
        need(row['ref_name'] in PIN_WIDTHS and row['pin_widths'] == PIN_WIDTHS[row['ref_name']] and
             row['instance'] == rtl['dut_scope']+'.'+'.'.join(relative.split('/')),
             'RTL actual macro hierarchy/pin schema differs')
        key = tuple(relative.split('/'))
        need(all(re.fullmatch(COMPONENT, part) for part in key) and key not in source, 'RTL macro comparison collision')
        source[key] = row
    for row in native:
        # Expand literal generate-component dots ONLY in each enumerated actual
        # native macro for comparison. The original native name is the target;
        # no netlist, unrelated SAIF name, or destination undergoes replacement.
        key = tuple(part for component in row['instance'].split('/') for part in component.split('.'))
        need(key not in destination, 'native macro literal-dot comparison collision')
        destination[key] = row
    need(set(source) == set(destination), 'complete RTL/native macro bijection failed: missing=%d extra=%d' %
         (len(set(source)-set(destination)), len(set(destination)-set(source))))
    pairs, rows = {}, []
    for key in sorted(source):
        left, right = source[key], destination[key]
        need(left['ref_name'] == right['ref_name'] and left['group'] == right['group'], 'native/RTL macro group/ref differs')
        need({p['name'] for p in right['pins']} == pin_names(left['ref_name']), 'complete native pin set differs')
        canonical_scope = STRIP+'/'+left['relative_instance']
        for pin in right['pins']:
            original, target = canonical_scope+'/'+pin['name'], STRIP+'/'+pin['full_name']
            need(original not in pairs, 'source macro pin collision')
            pairs[original] = target
        rows.append(dict(rtl=left['instance'], native=right['instance'], ref_name=right['ref_name'], group=right['group']))
    need(len(rows) == rtl['macro_count'] == len(native) and len(pairs) == rtl['pin_bit_count'] == len(set(pairs.values())),
         'full mixed67/64 macro/pin bijection differs')
    return pairs, rows


def tree_index(tree, helper):
    instances, signals = {}, {}
    def visit(node, parent):
        if not isinstance(node, list) or not node:
            return
        if node[0] == 'INSTANCE':
            name = helper.decode_atom(node[1])
            need(name and '/' not in name, 'SAIF INSTANCE must be one literal component')
            parts = parent+[name]; path = '/'.join(parts)
            need(path not in instances, 'duplicate SAIF INSTANCE: '+path)
            instances[path] = node
            for child in node[2:]: visit(child, parts)
        elif node[0] in ('NET', 'PORT'):
            for child in node[1:]:
                name = helper.decode_atom(child[0]); key = (node[0], '/'.join(parent+[name]))
                need(name and '/' not in name and key not in signals, 'invalid/duplicate SAIF signal')
                signals[key] = (node, child)
        else:
            for child in node[1:]: visit(child, parent)
    visit(tree, [])
    return instances, signals


def stats(signal):
    return {key: value for key, value in signal.items() if key not in ('path', 'kind', 'mapped_path')}


def relocate(saif, out, rtl, native, reader, helper):
    saif, out = Path(saif).absolute(), Path(out).absolute()
    need(not out.exists() and saif.resolve() != out.resolve(), 'fresh mapped SAIF required')
    before = identity(saif)
    pairs, rows = bijection(rtl, native)
    measured = reader.read_saif(saif)
    source = {(s['kind'], s['path']): s for s in measured['signals']}
    tree = helper.raw_tree(saif.read_text())
    instances, nodes = tree_index(tree, helper)
    need(set(nodes) == set(source), 'independent SAIF readers differ')
    headers = copy.deepcopy([n for n in tree[1:] if n[0] != 'INSTANCE'])
    # Every nonpin behavioral model/RTL signal remains untouched. Only complete
    # inventoried pin paths may move; unrelated dotted names stay literal.
    removed, inject, comparisons, pins = set(), {}, [], []
    for original, target in sorted(pairs.items()):
        found = [source[(kind, original)] for kind in ('PORT', 'NET') if (kind, original) in source]
        need(found and all(stats(s) == stats(found[0]) for s in found), 'canonical pin missing/conflicts: '+original)
        native_values = [source[(kind, target)] for kind in ('PORT', 'NET') if (kind, target) in source]
        need(all(stats(s) == stats(found[0]) for s in native_values), 'existing native pin conflicts: '+target)
        if original != target:
            removed.update((s['kind'], original) for s in found)
            if not native_values: inject[target] = copy.deepcopy(nodes[(found[0]['kind'], original)][1])
        comparisons.append([original, target, stats(found[0])])
        pins.append(dict(found[0], path=target, mapped_path=target[len(STRIP)+1:]))
    for key in sorted(removed):
        section, node = nodes[key]; section.remove(node)
    for target, signal in sorted(inject.items()):
        scope, name = target.rsplit('/', 1); parts = scope.split('/')
        for depth in range(1, len(parts)+1):
            key = '/'.join(parts[:depth])
            if key not in instances:
                node = ['INSTANCE', helper.atom(parts[depth-1]).replace('.', r'\.')]
                (tree if depth == 1 else instances['/'.join(parts[:depth-1])]).append(node)
                instances[key] = node
        destination = instances[scope]
        section = next((n for n in destination[2:] if n[0] == 'PORT'), None)
        if section is None: section = ['PORT']; destination.append(section)
        signal[0] = helper.atom(name); section.append(signal)
    candidates = set()
    for _, path in removed:
        scope = path.rsplit('/', 1)[0]; node = instances[scope]
        node[2:] = [n for n in node[2:] if not (n[0] in ('PORT', 'NET') and len(n) == 1)]
        parts = scope.split('/'); candidates.update('/'.join(parts[:i]) for i in range(1, len(parts)+1))
    for scope in sorted(candidates, key=lambda p: p.count('/'), reverse=True):
        node = instances[scope]
        if len(node) == 2:
            parent = scope.rpartition('/')[0]
            (instances[parent] if parent else tree).remove(node); del instances[scope]
    with out.open('x') as stream: helper.write_sexpr(stream, tree)
    transformed = reader.read_saif(out)
    observed = {(s['kind'], s['path']): s for s in transformed['signals']}
    preserved = {k: v for k, v in source.items() if k not in removed}
    need(all(observed.get(k) == v for k, v in preserved.items()), 'nonrelocated activity changed')
    need(set(observed) == set(preserved)|{('PORT', p) for p in inject}, 'mapped SAIF missing/extra signals')
    for pin in pins:
        values = [observed[(kind, pin['path'])] for kind in ('PORT', 'NET') if (kind, pin['path']) in observed]
        need(values and all(stats(v) == stats(pin) for v in values), 'mapped pin statistics changed')
    need([n for n in helper.raw_tree(out.read_text())[1:] if n[0] != 'INSTANCE'] == headers and
         all(transformed[k] == measured[k] for k in ('duration_ticks', 'timescale_seconds')), 'SAIF headers/time base changed')
    need(identity(saif) == before, 'normalized input changed during relocation')
    unknown = sum(p.get(k, 0) for p in pins for k in ('TX', 'TZ', 'TB'))
    q = [p for p in pins if p['mapped_path'].rsplit('/', 1)[1].startswith('Q[')]
    summary = dict(pin_count=len(pins), q_pin_count=len(q), measured_unknown_bit_ticks=unknown,
                   q_tx_positive=sum(p.get('TX', 0)>0 for p in q),
                   q_tx_full_window=sum(p.get('TX', 0) == measured['duration_ticks'] for p in q),
                   duration_ticks=measured['duration_ticks'], timescale_seconds=measured['timescale_seconds'])
    receipt = dict(schema='xu-profile-mapped-saif146-v1', status='RELOCATED_DIAGNOSTIC_NOT_QUALIFIED',
                   input_saif=before, output_saif=identity(out), macro_count=len(native), pin_bit_count=len(pairs),
                   macro_bijection_sha256=canonical(rows), per_bit_comparison_sha256=canonical(comparisons),
                   measured_summary=summary, nonrelocated_signal_count_preserved=len(preserved),
                   source_records_removed=len(removed), injected_pin_bits=len(inject),
                   policy='Complete actual native/RTL macro and bit-pin bijection; retain all statistics including TX TZ TB IG; literal native destinations.')
    return receipt, dict(status='MEASURED_DIAGNOSTIC_NOT_QUALIFIED', pins=pins, measured_summary=summary)
