#!/usr/bin/env python3
"""Relocate measured SRAM SAIF bits using an actual PrimeTime pin inventory.

Only explicitly inventoried RAMSP1024X16 cells participate. Slash separates
actual mapped hierarchy; a dot inside an actual cell component remains literal.
This bridge proves preservation and a name bijection, never capture, annotation,
power, or contest qualification. It does not modify the input SAIF or normalizer.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_mapped_alias', ROOT / 'tools/ppa/xu_sram_activity_alias.py')
alias = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(alias)
require = alias.require
INVENTORY_SCHEMA = 'xu-mapped-sram-pin-inventory-v1'
RECEIPT_SCHEMA = 'xu-saif-mapped-macros-v1'
REF_NAME = 'RAMSP1024X16'
PIN_NAMES = {pin if width == 1 else '%s[%d]' % (pin, bit)
             for pin, width in alias.PIN_WIDTHS.items() for bit in range(width)}


def load_json(path):
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def declared_identity(record, label):
    require(isinstance(record, dict) and isinstance(record.get('path'), str) and record['path'] and
            isinstance(record.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', record['sha256']),
            'invalid declared identity: ' + label)
    if 'bytes' in record:
        require(type(record['bytes']) is int and record['bytes'] >= 0, 'invalid identity byte count: ' + label)


def mapping_macros(path, strip_path):
    """Check the mapping profile without dereferencing archived remote paths.

    The source normalizer itself must be the exact recorded version. Original
    capture provenance and its normalization receipt remain the caller's audit.
    """
    mapping = load_json(path)
    require(mapping.get('schema') == alias.SCHEMA and mapping.get('pin_widths') == alias.PIN_WIDTHS,
            'unsupported observer mapping/pin widths')
    require(mapping.get('placement') in ('bind', 'include'), 'invalid observer placement')
    dut = alias.slash(mapping['dut_scope'])
    alias.hierarchy(mapping['observer_scope'])
    require(strip_path == dut, 'strip-path must exactly equal mapping dut_scope: ' + dut)
    records = mapping['macros']
    require(isinstance(records, list) and records and type(mapping.get('macro_count')) is int and
            len(records) == mapping['macro_count'], 'invalid macro mapping count')
    require(type(mapping.get('alias_bit_count')) is int and mapping['alias_bit_count'] == len(records) * len(PIN_NAMES),
            'mapping alias bit count differs')
    for key in ('observer_source', 'generator', 'saif_reader'):
        declared_identity(mapping.get(key), 'mapping.' + key)
    for key, local_path in [('generator', alias.__file__), ('saif_reader', ROOT / 'tools/scripts/xu_soc_activity.py')]:
        require(mapping[key]['sha256'] == alias.sha(local_path), 'mapping uses a different ' + key + ' source SHA')
        if 'bytes' in mapping[key]:
            require(mapping[key]['bytes'] == Path(local_path).stat().st_size, 'mapping ' + key + ' byte count differs')
    require(isinstance(mapping.get('source_files'), list), 'mapping source_files must be a list')
    for item in mapping['source_files']:
        declared_identity(item, 'mapping.source_files')
    if mapping.get('mode') == 'source_guarded_full_soc_336':
        expected, _ = alias.full_soc_macros(ROOT, mapping['dut_scope'])
        require(records == expected, 'full-SoC macro list differs from the current guarded 336-macro profile')
    else:
        require(mapping.get('mode') == 'explicit_probe_only' and not mapping['source_files'], 'unsupported mapping profile')
    canonical = {}
    for record in records:
        require(isinstance(record, dict), 'invalid mapping macro record')
        full = alias.slash(record['instance'])
        require(full.startswith(dut + '/'), 'mapping macro lies outside exact DUT scope')
        relative = full[len(dut) + 1:]
        require(relative not in canonical, 'duplicate canonical macro: ' + relative)
        canonical[relative] = full
    return mapping, canonical


def inventory_macros(path):
    inventory = load_json(path)
    require(inventory.get('schema') == INVENTORY_SCHEMA, 'unsupported mapped SRAM inventory schema')
    require(inventory.get('status') == 'EXPORTED_REVIEW_PENDING', 'inventory must be an exported review-pending inventory')
    declared_identity(inventory.get('netlist'), 'inventory.netlist')
    require(isinstance(inventory.get('libraries'), list) and inventory['libraries'], 'inventory libraries must be nonempty')
    for item in inventory['libraries']:
        declared_identity(item, 'inventory.libraries')
    require(isinstance(inventory.get('provenance'), dict) and inventory['provenance'], 'inventory provenance must be nonempty')
    records = inventory.get('macros')
    require(isinstance(records, list) and records and type(inventory.get('macro_count')) is int and
            len(records) == inventory['macro_count'], 'inventory macro count differs')
    require(type(inventory.get('pin_bit_count')) is int and inventory['pin_bit_count'] == len(records) * len(PIN_NAMES),
            'inventory pin bit count differs')
    actual, comparison = {}, {}
    all_pins = set()
    for record in records:
        require(isinstance(record, dict), 'invalid inventory macro record')
        cell = record.get('instance')
        require(isinstance(cell, str) and cell and all(component and alias.hierarchy(component)
                for component in cell.split('/')), 'invalid actual macro cell name')
        require(cell not in actual, 'duplicate actual macro cell: ' + cell)
        require(record.get('ref_name') == REF_NAME, 'unexpected actual macro reference: ' + cell)
        require(isinstance(record.get('lib_cell'), str) and
                record['lib_cell'].count('/') == 1 and record['lib_cell'].split('/')[0] and
                record['lib_cell'].split('/')[1] == REF_NAME and not re.search(r'\s', record['lib_cell']),
                'unexpected actual macro library cell: ' + cell)
        pins = record.get('pins')
        require(isinstance(pins, list) and len(pins) == len(PIN_NAMES), 'actual macro must have exactly 67 bit pins: ' + cell)
        seen = set()
        for pin in pins:
            require(isinstance(pin, dict) and pin.get('name') in PIN_NAMES, 'unexpected actual macro pin: ' + cell)
            name = pin['name']
            require(name not in seen, 'duplicate actual macro pin: ' + cell + '/' + name)
            seen.add(name)
            require(pin.get('full_name') == cell + '/' + name, 'actual full pin name differs: ' + cell + '/' + name)
            require(pin['full_name'] not in all_pins, 'duplicate actual full pin name: ' + pin['full_name'])
            all_pins.add(pin['full_name'])
            expected_direction = 'out' if name.startswith('Q[') else 'in'
            require(pin.get('direction') == expected_direction, 'actual pin direction differs: ' + pin['full_name'])
        require(seen == PIN_NAMES, 'actual macro pin set differs: ' + cell)
        # The only dot comparison is over this explicit, complete macro list.
        # Its result is never used to construct the actual destination hierarchy.
        key = cell.replace('.', '/')
        require(key not in comparison, 'actual macro dot/slash comparison collision: ' + key)
        comparison[key] = cell
        actual[cell] = record
    return inventory, actual, comparison


def tree_index(tree):
    instances, signals = {}, {}

    def visit(node, parent):
        if not isinstance(node, list) or not node:
            return
        if node[0] == 'INSTANCE':
            require(len(node) >= 2 and isinstance(node[1], str), 'invalid SAIF INSTANCE')
            name = alias.decode_atom(node[1])
            require(name and '/' not in name, 'SAIF INSTANCE atom must be a single literal hierarchy component')
            current = parent + [name]
            path = '/'.join(current)
            require(path not in instances, 'duplicate SAIF INSTANCE: ' + path)
            instances[path] = node
            for child in node[2:]:
                visit(child, current)
        elif node[0] in ('NET', 'PORT'):
            for signal in node[1:]:
                require(isinstance(signal, list) and signal and isinstance(signal[0], str), 'invalid SAIF signal')
                name = alias.decode_atom(signal[0])
                require(name and '/' not in name, 'SAIF signal atom contains a hierarchy separator')
                key = (node[0], '/'.join(parent + [name]))
                require(key not in signals, 'duplicate SAIF signal: ' + str(key))
                signals[key] = (node, signal)
        else:
            for child in node[1:]:
                visit(child, parent)
    visit(tree, [])
    return instances, signals


def relocate(saif, mapping_path, inventory_path, out, strip_path, receipt_path=None):
    saif, mapping_path, inventory_path, out = [Path(p).absolute() for p in (saif, mapping_path, inventory_path, out)]
    receipt_path = Path(receipt_path).absolute() if receipt_path else out.with_suffix(out.suffix + '.receipt.json')
    paths = (saif, mapping_path, inventory_path, out, receipt_path)
    require(len({p.resolve() for p in paths}) == len(paths), 'input, mapping, inventory, output and receipt paths must differ')
    require(not any(p.exists() or p.is_symlink() for p in (out, receipt_path)), 'output SAIF and receipt must be new files')
    before = {key: alias.identity(path) for key, path in
              [('input_saif', saif), ('mapping', mapping_path), ('inventory', inventory_path)]}
    mapping, canonical = mapping_macros(mapping_path, strip_path)
    inventory, actual, comparisons = inventory_macros(inventory_path)
    require(set(canonical) == set(comparisons), 'mapped/canonical macro bijection differs: missing=%d extra=%d' %
            (len(set(canonical) - set(comparisons)), len(set(comparisons) - set(canonical))))
    require(len(actual) == mapping['macro_count'], 'mapped/canonical macro count differs')
    pairs = {canonical[key] + '/' + name: strip_path + '/' + comparisons[key] + '/' + name
             for key in sorted(canonical) for name in sorted(PIN_NAMES)}
    require(len(pairs) == len(set(pairs.values())) == mapping['alias_bit_count'], 'mapped/canonical pin bijection differs')
    reader = alias.activity_module()
    measured = reader.read_saif(saif)
    source = {(s['kind'], s['path']): s for s in measured['signals']}
    tree = alias.raw_tree(saif.read_text())
    instances, signal_nodes = tree_index(tree)
    require(set(signal_nodes) == set(source), 'raw SAIF tree and activity reader differ')
    headers = copy.deepcopy([node for node in tree[1:] if node[0] != 'INSTANCE'])
    macro_scopes = set(canonical.values()) | {strip_path + '/' + cell for cell in actual}
    expected_paths = set(pairs) | set(pairs.values())
    for signal in measured['signals']:
        # No arbitrary dotted RTL name is interpreted or rewritten.
        if signal['path'] in expected_paths:
            continue
        scope = signal['path'].rpartition('/')[0]
        while scope:
            require(scope not in macro_scopes,
                    'unexpected activity within an explicitly mapped macro: ' + signal['path'])
            scope = scope.rpartition('/')[0]
    removed, injected, comparison_rows = set(), {}, []
    reused, unchanged, source_both, target_both = 0, 0, 0, 0
    for original, target in sorted(pairs.items()):
        original_signals = [source[(kind, original)] for kind in ('PORT', 'NET') if (kind, original) in source]
        require(original_signals, 'missing measured canonical macro pin: ' + original)
        stats = alias.stats(original_signals[0])
        require(all(alias.stats(item) == stats for item in original_signals), 'conflicting canonical NET/PORT statistics: ' + original)
        source_both += len(original_signals) == 2
        native = [source[(kind, target)] for kind in ('NET', 'PORT') if (kind, target) in source]
        require(all(alias.stats(item) == stats for item in native), 'native mapped macro pin statistics differ: ' + target)
        if original == target:
            unchanged += 1
        else:
            removed.update((item['kind'], original) for item in original_signals)
            if native:
                reused += 1
                target_both += len(native) == 2
            else:
                selected = original_signals[0]
                injected[target] = copy.deepcopy(signal_nodes[(selected['kind'], original)][1])
        comparison_rows.append([original, target, stats])
    for key in sorted(removed):
        section, signal = signal_nodes[key]
        section.remove(signal)
    for target, signal in sorted(injected.items()):
        scope, name = target.rsplit('/', 1)
        parts = scope.split('/')
        for depth in range(1, len(parts) + 1):
            key = '/'.join(parts[:depth])
            if key not in instances:
                node = ['INSTANCE', alias.atom(parts[depth - 1])]
                (tree if depth == 1 else instances['/'.join(parts[:depth - 1])]).append(node)
                instances[key] = node
        destination = instances[scope]
        section = next((node for node in destination[2:] if node[0] == 'PORT'), None)
        if section is None:
            section = ['PORT']
            destination.append(section)
        signal[0] = alias.atom(name)
        section.append(signal)
    # Remove only containers emptied by relocation. In particular, do not
    # leave nonexistent canonical generate INSTANCE rows in PT's hierarchy
    # report, and do not discard unrelated siblings or preexisting empties.
    emptied_scopes = {path.rsplit('/', 1)[0] for _, path in removed}
    candidates = set()
    for scope in emptied_scopes:
        node = instances[scope]
        node[2:] = [child for child in node[2:] if not
                    (isinstance(child, list) and child and child[0] in ('NET', 'PORT') and len(child) == 1)]
        parts = scope.split('/')
        candidates.update('/'.join(parts[:depth]) for depth in range(1, len(parts) + 1))
    for scope in sorted(candidates, key=lambda value: value.count('/'), reverse=True):
        node = instances[scope]
        if len(node) == 2:
            parent = scope.rpartition('/')[0]
            (instances[parent] if parent else tree).remove(node)
            del instances[scope]
    out.parent.mkdir(parents=True, exist_ok=True)
    wrote_out, wrote_receipt = False, False
    try:
        with out.open('x') as stream:
            wrote_out = True
            alias.write_sexpr(stream, tree)
        transformed = reader.read_saif(out)
        observed = {(s['kind'], s['path']): s for s in transformed['signals']}
        preserved = {key: value for key, value in source.items() if key not in removed}
        require(all(observed.get(key) == value for key, value in preserved.items()), 'nonrelocated SAIF statistics changed')
        require(set(observed) == set(preserved) | {('PORT', path) for path in injected}, 'output has missing or extra signal records')
        for original, target in pairs.items():
            values = [alias.stats(observed[(kind, target)]) for kind in ('NET', 'PORT') if (kind, target) in observed]
            expected = next(alias.stats(source[(kind, original)]) for kind in ('PORT', 'NET') if (kind, original) in source)
            require(values and all(value == expected for value in values), 'relocated per-pin statistics differ: ' + target)
        output_tree = alias.raw_tree(out.read_text())
        tree_index(output_tree)
        require([node for node in output_tree[1:] if node[0] != 'INSTANCE'] == headers, 'SAIF headers changed')
        require(transformed['duration_ticks'] == measured['duration_ticks'] and
                transformed['timescale_seconds'] == measured['timescale_seconds'], 'SAIF time base changed')
        for key, path in [('input_saif', saif), ('mapping', mapping_path), ('inventory', inventory_path)]:
            require(alias.identity(path) == before[key], 'input changed during relocation: ' + key)
        receipt = dict(schema=RECEIPT_SCHEMA, status='RELOCATED_NOT_CAPTURE_ANNOTATION_OR_POWER_QUALIFIED',
                       **before, output_saif=alias.identity(out), generator=alias.identity(__file__),
                       strip_path=strip_path, macro_count=len(actual), mapped_pin_bit_count=len(pairs),
                       source_records_removed=len(removed), relocated_pin_bits_added_as_port=len(injected),
                       native_mapped_pin_bits_verified_reused=reused, unchanged_pin_bits_verified=unchanged,
                       canonical_net_and_port_bits_verified=source_both, native_mapped_net_and_port_bits_verified=target_both,
                       other_signal_records_preserved=len(preserved), duration_ticks=measured['duration_ticks'],
                       timescale_seconds=measured['timescale_seconds'],
                       macro_bijection_sha256=alias.canonical_hash(sorted((canonical[key], comparisons[key]) for key in canonical)),
                       per_bit_comparison_sha256=alias.canonical_hash(comparison_rows),
                       measured_unknown_bit_ticks=sum(row[2].get(key, 0) for row in comparison_rows for key in ('TX', 'TZ', 'TB')),
                       mapping_declared_generator=mapping['generator'], mapping_declared_observer_source=mapping['observer_source'],
                       inventory_declared_provenance=inventory['provenance'],
                       policy='Exact complete 67-pin macro bijection; strict statistics and attribute sets; literal mapped dots; input immutable.',
                       limitation='This proves name relocation and measured-statistic preservation only. Original capture provenance, PT annotation, Liberty power and contest qualification remain separate reviews.')
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with receipt_path.open('x') as stream:
            wrote_receipt = True
            stream.write(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        return receipt
    except BaseException:
        if wrote_out:
            out.unlink()
        if wrote_receipt:
            receipt_path.unlink()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saif', type=Path, required=True, help='immutable already-normalized measured SAIF')
    parser.add_argument('--mapping', type=Path, required=True, help='original observer mapping')
    parser.add_argument('--inventory', type=Path, required=True, help='actual PT-exported bit pin inventory')
    parser.add_argument('--strip-path', required=True, help='exact slash DUT scope used by read_saif -strip_path')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    print(json.dumps(relocate(args.saif, args.mapping, args.inventory, args.out, args.strip_path, args.receipt), sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('FAIL: ' + str(exc), file=sys.stderr)
        sys.exit(1)
