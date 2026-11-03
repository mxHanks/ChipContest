"""Synthetic name-bijection/tamper checks; never actual PT or power evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_saif_mapped_test', ROOT / 'tools/ppa/xu_saif_mapped_macros.py')
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)
alias = bridge.alias
reader = alias.activity_module()
STRIP = 'tb/dut'


def signals(path):
    return {(item['kind'], item['path']): item for item in reader.read_saif(path)['signals']}


def write_saif(path, records):
    tree = ['SAIFILE', ['SAIFVERSION', '"2.0"'], ['DESIGN', '"xu synthetic host fixture; not PT"'],
            ['DATE', '"literal \\"quoted\\" header"'], ['TIMESCALE', '1', 'ns'], ['DURATION', '10.00']]
    instances = {}
    for kind, name, stats in records:
        parts = name.split('/')
        for depth in range(1, len(parts)):
            scope = '/'.join(parts[:depth])
            if scope not in instances:
                node = ['INSTANCE', alias.atom(parts[depth - 1])]
                (tree if depth == 1 else instances['/'.join(parts[:depth - 1])]).append(node)
                instances[scope] = node
        parent = instances['/'.join(parts[:-1])]
        section = next((item for item in parent[2:] if item[0] == kind), None)
        if section is None:
            section = [kind]
            parent.append(section)
        section.append([alias.atom(parts[-1])] + [[key, str(value)] for key, value in stats.items()])
    with path.open('w') as stream:
        alias.write_sexpr(stream, tree)


class MappedMacroTests(unittest.TestCase):
    def fixture(self, directory, full=False):
        paths = ['tb.dut.shared.storage.macro_storage.depth_bank[0].width_lane[0].macro',
                 'tb.dut.weights.bank_0.macro']
        mapping = alias.generate(ROOT, directory / 'observer', dut_scope='tb.dut',
                                 placement='include', macro_paths=None if full else paths)
        mapping_path = directory / 'observer/xu_sram_activity_alias.mapping.json'
        actual = []
        for macro in mapping['macros']:
            relative = alias.slash(macro['instance'])[len(STRIP) + 1:]
            if '/macro_storage/' in relative:
                parent, suffix = relative.split('/macro_storage/', 1)
                relative = parent + '/macro_storage.' + suffix.replace('/', '.')
            actual.append(relative)
        declared = dict(path='/xu/synthetic/not-a-real-artifact', sha256='0' * 64)
        inventory = dict(schema=bridge.INVENTORY_SCHEMA, status='EXPORTED_REVIEW_PENDING',
                         netlist=declared, libraries=[declared], macro_count=len(actual), pin_bit_count=len(actual) * 67,
                         provenance=dict(synthetic_host_fixture=True), macros=[])
        pairs, records = {}, []
        for macro, cell in zip(mapping['macros'], actual):
            inventory['macros'].append(dict(instance=cell, ref_name=bridge.REF_NAME,
                lib_cell='SYNTHETIC/' + bridge.REF_NAME,
                pins=[dict(name=name, full_name=cell + '/' + name,
                           direction='out' if name.startswith('Q[') else 'in') for name in sorted(bridge.PIN_NAMES)]))
            for index, name in enumerate(sorted(bridge.PIN_NAMES)):
                canonical = alias.slash(macro['instance']) + '/' + name
                pairs[canonical] = STRIP + '/' + cell + '/' + name
                records.append(('PORT', canonical, dict(T0=1, T1=2, TX=3, TZ=1, TB=3, TC=index, IG=2)))
        records.extend([('NET', 'tb/dut/unrelated/macro_storage.depth_bank[0].CLK', dict(T0=10, T1=0, TX=0, TC=11)),
                        ('NET', 'tb/dut/shared/storage/macro_storage/depth_bank[0]/width_lane[0]/macro_extra/keep',
                         dict(T0=4, T1=6, TX=0, TC=17)),
                        ('PORT', 'tb/dut/unrelated/space and "quote"[2]', dict(T0=0, T1=0, TX=10, TC=0, IG=6))])
        inventory_path, source = directory / 'inventory.json', directory / 'normalized.saif'
        alias.write_json(inventory_path, inventory)
        write_saif(source, records)
        return mapping_path, inventory_path, inventory, source, records, pairs

    def run_bridge(self, d, mapping, inventory, source):
        return bridge.relocate(source, mapping, inventory, d / 'mapped.saif', STRIP)

    def assert_failure(self, d, mapping, inventory, source):
        before = {path: alias.sha(path) for path in (mapping, inventory, source)}
        with self.assertRaises((ValueError, KeyError, TypeError)):
            self.run_bridge(d, mapping, inventory, source)
        self.assertFalse((d / 'mapped.saif').exists())
        self.assertFalse((d / 'mapped.saif.receipt.json').exists())
        self.assertEqual(before, {path: alias.sha(path) for path in before})

    def test_literal_mapped_dots_mixed_hierarchy_and_every_statistic_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            mapping, inventory_path, _, source, _, pairs = self.fixture(d)
            original = signals(source)
            before = alias.sha(source)
            receipt = self.run_bridge(d, mapping, inventory_path, source)
            observed = signals(d / 'mapped.saif')
            moved = {('PORT', path) for path, target in pairs.items() if path != target}
            injected = {('PORT', target) for path, target in pairs.items() if path != target}
            self.assertEqual(set(observed), (set(original) - moved) | injected)
            for path, target in pairs.items():
                self.assertEqual(alias.stats(original[('PORT', path)]), alias.stats(observed[('PORT', target)]))
            for key in set(original) - moved:
                self.assertEqual(original[key], observed[key])
            tree = alias.raw_tree((d / 'mapped.saif').read_text())
            instances, _ = bridge.tree_index(tree)
            self.assertIn('tb/dut/shared/storage/macro_storage.depth_bank[0].width_lane[0].macro', instances)
            self.assertEqual(alias.decode_atom(instances['tb/dut/shared/storage/macro_storage.depth_bank[0].width_lane[0].macro'][1]),
                             'macro_storage.depth_bank[0].width_lane[0].macro')
            self.assertNotIn('tb/dut/shared/storage/macro_storage/depth_bank[0]/width_lane[0]/macro', instances)
            self.assertIn('tb/dut/shared/storage/macro_storage/depth_bank[0]/width_lane[0]/macro_extra', instances)
            self.assertIn('(DURATION 10.00)', (d / 'mapped.saif').read_text())
            self.assertIn('(DATE "literal \\"quoted\\" header")', (d / 'mapped.saif').read_text())
            self.assertEqual(alias.sha(source), before)
            self.assertEqual(receipt['input_saif']['sha256'], before)
            self.assertEqual(receipt['inventory']['sha256'], alias.sha(inventory_path))
            self.assertEqual(receipt['output_saif']['sha256'], alias.sha(d / 'mapped.saif'))
            self.assertEqual(receipt['relocated_pin_bits_added_as_port'], 67)
            self.assertEqual(receipt['unchanged_pin_bits_verified'], 67)
            self.assertEqual(receipt['measured_unknown_bit_ticks'], 134 * 7)
            self.assertIn('NOT_CAPTURE_ANNOTATION_OR_POWER_QUALIFIED', receipt['status'])

    def test_exact_native_net_port_and_both_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            mapping, inventory_path, _, source, records, pairs = self.fixture(d)
            moved = [(path, target) for path, target in sorted(pairs.items()) if path != target][:3]
            for (path, target), kinds in zip(moved, [('NET',), ('PORT',), ('NET', 'PORT')]):
                stats = next(stats for _, name, stats in records if name == path)
                records += [(kind, target, copy.deepcopy(stats)) for kind in kinds]
            write_saif(source, records)
            receipt = self.run_bridge(d, mapping, inventory_path, source)
            self.assertEqual(receipt['native_mapped_pin_bits_verified_reused'], 3)
            self.assertEqual(receipt['native_mapped_net_and_port_bits_verified'], 1)
            self.assertEqual(receipt['relocated_pin_bits_added_as_port'], 64)
            observed = signals(d / 'mapped.saif')
            self.assertNotIn(('PORT', moved[0][1]), observed)
            self.assertNotIn(('NET', moved[1][1]), observed)

    def test_complete_current_336_macro_profile_and_topology_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            mapping, inventory_path, _, source, _, pairs = self.fixture(d, full=True)
            self.assertEqual(len(pairs), 22512)
            receipt = self.run_bridge(d, mapping, inventory_path, source)
            self.assertEqual(receipt['macro_count'], 336)
            self.assertEqual(receipt['mapped_pin_bit_count'], 22512)
            self.assertEqual(receipt['relocated_pin_bits_added_as_port'], 320 * 67)
            self.assertEqual(receipt['unchanged_pin_bits_verified'], 16 * 67)
            self.assertEqual(len(signals(d / 'mapped.saif')), 22512 + 3)
            (d / 'mapped.saif').unlink()
            (d / 'mapped.saif.receipt.json').unlink()
            changed = json.loads(mapping.read_text())
            changed['macros'][0]['group'] = 'wrong-profile'
            alias.write_json(mapping, changed)
            self.assert_failure(d, mapping, inventory_path, source)

    def test_canonical_net_only_and_agreeing_cross_kind_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            mapping, inventory_path, _, source, records, pairs = self.fixture(d)
            moved = [path for path, target in sorted(pairs.items()) if path != target][:2]
            records = [('NET' if name == moved[0] else kind, name, stats) for kind, name, stats in records]
            stats = next(stats for _, name, stats in records if name == moved[1])
            records.append(('NET', moved[1], dict(stats)))
            write_saif(source, records)
            receipt = self.run_bridge(d, mapping, inventory_path, source)
            self.assertEqual(receipt['canonical_net_and_port_bits_verified'], 1)
            self.assertEqual(receipt['source_records_removed'], 68)
            self.assertIn(('PORT', pairs[moved[0]]), signals(d / 'mapped.saif'))

    def test_native_statistic_value_or_attribute_set_conflicts_fail(self):
        for mode in ('TC', 'IG', 'TX', 'TZ', 'TB', 'missing_zero', 'extra_zero', 'source_conflict'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)
                mapping, inventory_path, _, source, records, pairs = self.fixture(d)
                path, target = next((path, target) for path, target in pairs.items() if path != target)
                stats = copy.deepcopy(next(stats for _, name, stats in records if name == path))
                if mode in ('TX', 'TZ', 'TB'):
                    stats[mode] += 1
                    stats['T0'] -= 1
                elif mode == 'missing_zero':
                    # Replace the canonical record so IG=0, then omit that key natively.
                    records = [(kind, name, dict(value, IG=0) if name == path else value) for kind, name, value in records]
                    del stats['IG']
                elif mode == 'extra_zero':
                    stats['EXTRA'] = 0
                else:
                    stats['TC' if mode == 'source_conflict' else mode] += 1
                records.append(('NET', path if mode == 'source_conflict' else target, stats))
                write_saif(source, records)
                self.assert_failure(d, mapping, inventory_path, source)

    def test_missing_extra_duplicate_and_ambiguous_saif_fail(self):
        for mode in ('missing', 'extra_source', 'extra_target', 'duplicate', 'duplicate_instance', 'duplicate_stat', 'slash_atom'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)
                mapping, inventory_path, _, source, records, pairs = self.fixture(d)
                path, target = next((path, target) for path, target in pairs.items() if path != target)
                stats = copy.deepcopy(next(stats for _, name, stats in records if name == path))
                if mode == 'missing':
                    records = [(kind, name, value) for kind, name, value in records if name != path]
                elif mode in ('extra_source', 'extra_target'):
                    records.append(('PORT', (path if mode == 'extra_source' else target).rsplit('/', 1)[0] + '/WEN[16]', stats))
                elif mode == 'duplicate':
                    records.append(('PORT', path, stats))
                write_saif(source, records)
                if mode == 'duplicate_instance':
                    text = source.read_text()
                    source.write_text(text[:-2] + '(INSTANCE tb)\n)\n')
                elif mode == 'duplicate_stat':
                    source.write_text(source.read_text().replace('(IG 2)', '(IG 2) (IG 2)', 1))
                elif mode == 'slash_atom':
                    source.write_text(source.read_text().replace('(INSTANCE shared', '(INSTANCE shared/other', 1))
                self.assert_failure(d, mapping, inventory_path, source)

    def test_inventory_exact_sets_full_names_directions_refs_and_collision_fail(self):
        modes = ('missing_macro', 'extra_macro', 'duplicate_macro', 'same_count_wrong_macro', 'dot_slash_collision',
                 'missing_pin', 'extra_pin', 'duplicate_pin', 'same_count_wrong_pin', 'wrong_full_name',
                 'wrong_direction', 'wrong_ref', 'wrong_lib', 'wrong_count', 'wrong_schema', 'no_provenance')
        for mode in modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)
                mapping, inventory_path, inventory, source, _, _ = self.fixture(d)
                macro = inventory['macros'][0]
                if mode == 'missing_macro':
                    inventory['macros'].pop()
                elif mode in ('extra_macro', 'duplicate_macro'):
                    inventory['macros'].append(copy.deepcopy(macro))
                    inventory.update(macro_count=3, pin_bit_count=201)
                elif mode in ('same_count_wrong_macro', 'dot_slash_collision'):
                    changed = inventory['macros'][1]
                    changed['instance'] = ('wrong/macro' if mode == 'same_count_wrong_macro' else
                                           macro['instance'].replace('/storage/', '.storage/'))
                    for pin in changed['pins']:
                        pin['full_name'] = changed['instance'] + '/' + pin['name']
                elif mode == 'missing_pin':
                    macro['pins'].pop()
                elif mode == 'extra_pin':
                    macro['pins'].append(copy.deepcopy(macro['pins'][0]))
                elif mode == 'duplicate_pin':
                    macro['pins'][1] = copy.deepcopy(macro['pins'][0])
                elif mode == 'same_count_wrong_pin':
                    macro['pins'][0].update(name='A[10]', full_name=macro['instance'] + '/A[10]')
                elif mode == 'wrong_full_name':
                    macro['pins'][0]['full_name'] = 'wrong/' + macro['pins'][0]['name']
                elif mode == 'wrong_direction':
                    macro['pins'][0]['direction'] = 'out'
                elif mode == 'wrong_ref':
                    macro['ref_name'] = 'RAMSP1024X8'
                elif mode == 'wrong_lib':
                    macro['lib_cell'] = 'WRONG/RAMSP1024X8'
                elif mode == 'wrong_count':
                    inventory['pin_bit_count'] += 1
                elif mode == 'wrong_schema':
                    inventory['schema'] += '-unknown'
                else:
                    inventory['provenance'] = {}
                alias.write_json(inventory_path, inventory)
                self.assert_failure(d, mapping, inventory_path, source)

    def test_mapping_tamper_json_duplicates_and_exact_strip_guard_fail(self):
        for mode in ('generator_sha', 'duplicate_macro', 'same_count_wrong_macro', 'wrong_bit_count', 'duplicate_json_key', 'strip'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)
                mapping_path, inventory_path, _, source, _, _ = self.fixture(d)
                mapping = json.loads(mapping_path.read_text())
                if mode == 'generator_sha':
                    mapping['generator']['sha256'] = 'f' * 64
                elif mode == 'duplicate_macro':
                    mapping['macros'][1] = copy.deepcopy(mapping['macros'][0])
                elif mode == 'same_count_wrong_macro':
                    mapping['macros'][0]['instance'] = 'tb.dut.wrong.macro'
                elif mode == 'wrong_bit_count':
                    mapping['alias_bit_count'] += 1
                alias.write_json(mapping_path, mapping)
                if mode == 'duplicate_json_key':
                    mapping_path.write_text(mapping_path.read_text().replace('{', '{"schema":"wrong",', 1))
                if mode == 'strip':
                    with self.assertRaisesRegex(ValueError, 'strip-path'):
                        bridge.relocate(source, mapping_path, inventory_path, d / 'mapped.saif', 'wrong/dut')
                    self.assertFalse((d / 'mapped.saif').exists())
                else:
                    self.assert_failure(d, mapping_path, inventory_path, source)

    def test_existing_outputs_inputs_and_receipt_write_failure_are_safe(self):
        for mode in ('out_exists', 'receipt_exists', 'out_is_input', 'symlink', 'receipt_parent_is_file'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)
                mapping, inventory_path, _, source, _, _ = self.fixture(d)
                out, receipt = d / 'mapped.saif', d / 'mapped.saif.receipt.json'
                before = alias.sha(source)
                if mode == 'out_exists':
                    out.write_text('keep output')
                elif mode == 'receipt_exists':
                    receipt.write_text('keep receipt')
                elif mode == 'out_is_input':
                    out = source
                elif mode == 'symlink':
                    out.symlink_to(d / 'missing')
                else:
                    (d / 'block').write_text('keep parent')
                    receipt = d / 'block/receipt.json'
                with self.assertRaises((ValueError, OSError)):
                    bridge.relocate(source, mapping, inventory_path, out, STRIP, receipt)
                self.assertEqual(alias.sha(source), before)
                if mode == 'out_exists':
                    self.assertEqual(out.read_text(), 'keep output')
                elif mode == 'receipt_exists':
                    self.assertEqual(receipt.read_text(), 'keep receipt')
                    self.assertFalse(out.exists())
                elif mode == 'receipt_parent_is_file':
                    self.assertFalse(out.exists())
                    self.assertEqual((d / 'block').read_text(), 'keep parent')

    def test_interrupted_writer_leaves_no_partial_output_or_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            mapping, inventory_path, _, source, _, _ = self.fixture(d)
            before = alias.sha(source)

            def interrupted(stream, tree):
                stream.write('(SAIFILE partial')
                raise KeyboardInterrupt()

            with mock.patch.object(alias, 'write_sexpr', interrupted), self.assertRaises(KeyboardInterrupt):
                self.run_bridge(d, mapping, inventory_path, source)
            self.assertEqual(alias.sha(source), before)
            self.assertFalse((d / 'mapped.saif').exists())
            self.assertFalse((d / 'mapped.saif.receipt.json').exists())


if __name__ == '__main__':
    unittest.main()
