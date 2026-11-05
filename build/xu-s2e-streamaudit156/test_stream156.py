#!/usr/bin/env python3
"""Host checks: independent native reparse, unknown preservation and immutable fail paths."""
import copy
import hashlib
import json
import lzma
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common156 import canonical, identity, read, write
import audit156
import primary156 as primary
import replay156 as replay
import saif156


class Stream156(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xu156-check-'); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.measured = {name: dict(path=saif156.STRIP+'/'+name, mapped_path=name, kind='PORT', **stats) for name, stats in [
            ('u_ram/Q[0]', dict(T0=0, T1=0, TX=10, TC=0, IG=0)),
            ('u_ram/Q[1]', dict(T0=2, T1=2, TX=2, TZ=1, TB=3, TC=7, IG=5)),
            ('u_ram/CLK', dict(T0=5, T1=5, TX=0, TC=8, IG=0))]}
        self.report = self.root/'report.rpt'
        self.report.write_text(''.join('XU_SRAM_PIN name='+pin+'\nDesign : xu_soc_ppa_top\n'+
            '    string full_name\n        '+pin+'\n'+
            '    string activity_checker_status Annotated\n    double glitch_rate 0\n    float static_probability 0.5\n'+
            '    double toggle_rate 0\n    float x_probability 0\n    double relative_toggle_rate -1\n'+
            'Information: synthetic getter diagnostic\n' for pin in self.measured))
        self.memberships = {'file': {'u_ram/Q[0]': [dict(raw_text='\tn\tu_ram/Q[0]\n', report_byte_start=1,
            report_byte_end=2, title='file', match_column='exact saved native driver-pin column')]}}

    def extract(self, previous=None, phase='before'):
        compact = self.root/(phase+'.jsonl.xz')
        result, signature = primary.extract(self.report, identity(self.report), self.measured, phase, compact, self.memberships, previous)
        return result, signature, compact

    def test_complete_raw_block_replay_preserves_unknown_and_getter_zero_limit(self):
        result, signature, compact = self.extract()
        before = identity(self.report)
        target = self.root/'samples'; target.mkdir()
        replayed, independently_parsed = replay.replay(self.report, before, compact, result['compact'], self.measured, 'before', result, target, self.memberships)
        self.assertEqual(signature, independently_parsed)
        self.assertEqual(replayed['complete_original_bytes_replayed'], before['bytes'])
        self.assertEqual(replayed['pin_count'], 3)
        self.assertEqual(replayed['selected_attribute_counts']['x_probability:NATIVE_ZERO'], 3)
        self.assertEqual(replayed['selected_attribute_counts']['MEASURED_UNKNOWN_ANY_POSITIVE'], 2)
        self.assertEqual(replayed['qualification'], 'NOT_QUALIFIED')
        self.assertEqual(identity(self.report), before)
        self.assertGreater(len(replayed['samples']), 0)
        for sample in replayed['samples']:
            begin, end = sample['original_report_range']
            self.assertEqual(Path(sample['original_block']['path']).read_bytes(), self.report.read_bytes()[begin:end])
        self.assertTrue(any('physically known' in limit for limit in audit156.LIMITS))

    def test_before_after_type_value_differences_are_independently_replayed(self):
        first, previous, _ = self.extract()
        self.report.write_text(self.report.read_text().replace('toggle_rate 0\n', 'toggle_rate 1\n'))
        second, _, compact = self.extract(previous, 'after')
        target = self.root/'samples'; target.mkdir()
        parsed, _ = replay.replay(self.report, identity(self.report), compact, second['compact'], self.measured, 'after', second, target, self.memberships, previous)
        self.assertEqual(parsed['before_after_counts']['toggle_rate:CHANGED'], 3)
        self.assertEqual(parsed['before_after_counts']['x_probability:UNCHANGED'], 3)

    def test_forged_compact_attribute_is_rejected_by_independent_raw_reparse(self):
        result, _, compact = self.extract(); changed = self.root/'forged.xz'
        rows = [json.loads(line) for line in lzma.open(str(compact), 'rb')]
        rows[0]['attributes']['x_probability']['value'] = '1'
        with lzma.open(str(changed), 'xb') as stream:
            for row in rows: stream.write((json.dumps(row)+'\n').encode())
        target = self.root/'samples'; target.mkdir()
        with self.assertRaisesRegex(ValueError, 'independent raw'):
            replay.replay(self.report, identity(self.report), changed, identity(changed), self.measured, 'before', result, target, self.memberships)

    def test_duplicate_native_pin_missing_core_and_unrepresented_prefix_rejected(self):
        text = self.report.read_text()
        for index, changed in enumerate((text+text, text.replace('    float x_probability 0\n', ''), '\n'+text)):
            self.report.write_text(changed)
            with self.assertRaises(ValueError):
                primary.extract(self.report, identity(self.report), self.measured, 'before', self.root/('%d.xz'%index), self.memberships)

    def test_big_native_reports_are_not_read_as_whole_text_or_bytes(self):
        text, data = Path.read_text, Path.read_bytes
        def no_text(path, *args, **kwargs):
            if path == self.report: raise AssertionError('whole native report read_text')
            return text(path, *args, **kwargs)
        def no_data(path, *args, **kwargs):
            if path == self.report: raise AssertionError('whole native report read_bytes')
            return data(path, *args, **kwargs)
        with patch.object(Path, 'read_text', no_text), patch.object(Path, 'read_bytes', no_data):
            result, _, compact = self.extract(); target = self.root/'samples'; target.mkdir()
            replay.replay(self.report, identity(self.report), compact, result['compact'], self.measured, 'before', result, target, self.memberships)

    def test_source_membership_matches_only_saved_driver_pin_column(self):
        path = self.root/'source.rpt'; path.write_text('List of nets with activity from file\n\tu_ram/Q[1]\tunrelated_driver\n\tnet\tu_ram/Q[0]\n')
        result, matches = primary.source_membership(path, identity(path), self.measured)
        self.assertEqual(set(matches), {'u_ram/Q[0]'})
        self.assertEqual(result['original_before'], result['original_after'])
        self.assertIn('absent', result['interpretation'])
        path.write_text(path.read_text()+'List of nets with activity from file\n')
        with self.assertRaises(ValueError): primary.source_membership(path, identity(path), self.measured)

    def test_native_sentinel_is_not_a_physical_probability(self):
        self.assertEqual(primary.category('x_probability', '-1'), 'NATIVE_SENTINEL')
        self.assertEqual(replay.classification('x_probability', '-1'), 'NATIVE_SENTINEL')
        self.assertEqual(primary.category('x_probability', 'NaN'), 'NATIVE_TEXT_OR_NONFINITE')
        self.assertEqual(replay.classification('x_probability', None), 'ABSENT_FROM_NATIVE_REPORT')

    def test_saif_body_retains_all_unknown_buckets_and_actual_duration(self):
        path = self.root/'input.saif'
        path.write_text('(SAIFILE (TIMESCALE 1 fs) (DURATION 10) (INSTANCE tb (INSTANCE dut (PORT (Q\\[0\\] (T0 2) (T1 2) (TX 2) (TZ 1) (TB 3) (TC 7) (IG 5))))))')
        found, _ = saif156.signals(path, 10)
        self.assertEqual(found['PORT', 'tb/dut/Q[0]'], dict(T0=2, T1=2, TX=2, TZ=1, TB=3, TC=7, IG=5))
        with self.assertRaises(ValueError): saif156.signals(path, 11)
        path.write_text(path.read_text().replace('(T0 2)', '(T0 3)'))
        with self.assertRaises(ValueError): saif156.signals(path, 10)

    def test_native_macro_bijection_uses_literal_enumerated_hierarchy(self):
        macros, actual = [], []
        for index in range(336):
            original = 'tb_xu_soc_ppa.dut.u_ram.bank[%d].macro' % index
            name = 'u_ram/bank[%d].macro' % index
            macros.append(dict(instance=original))
            actual.append(dict(instance=name, ref_name='RAMSP1024X16', pins=[dict(name=p, full_name=name+'/'+p,
                direction='out' if p.startswith('Q[') else 'in') for p in sorted(saif156.PINS)]))
        mapping = dict(schema='xu-s2e-sram-activity-alias-v1', pin_widths=saif156.WIDTHS, macro_count=336, alias_bit_count=22512,
            dut_scope='tb_xu_soc_ppa.dut', macros=macros)
        inventory = dict(schema='xu-mapped-sram-pin-inventory-v1', status='EXPORTED_REVIEW_PENDING', macro_count=336,
            pin_bit_count=22512, macros=actual)
        pairs, digest = saif156.binding(mapping, inventory)
        self.assertEqual(len(pairs), 22512)
        self.assertEqual(pairs[saif156.STRIP+'/u_ram/bank[0]/macro/A[9]'], saif156.STRIP+'/u_ram/bank[0].macro/A[9]')
        inventory['macros'][0]['pins'].pop()
        with self.assertRaises(ValueError): saif156.binding(mapping, inventory)

    def test_failed_fresh_attempt_has_terminal_receipt_and_repeat_cannot_edit_it(self):
        out = self.root/'audit'
        with self.assertRaises((ValueError, FileNotFoundError)): audit156.run(self.root/'missing', out)
        before = identity(out/'state.json')
        self.assertEqual(read(out/'state.json')['status'], audit156.FAILURE)
        with self.assertRaises(ValueError): audit156.run(self.root/'missing', out)
        self.assertEqual(identity(out/'state.json'), before)

    def test_exact_own130_receipts_are_frozen_without_old112_duration(self):
        frozen = read(HERE/'receipts156.json')
        self.assertEqual(frozen['duration_ticks'], 5788953333333)
        self.assertEqual(frozen['execution']['sha256'], 'f9ae8ff27792632f857004b971fb1d206002f510ca97e41d9b66ddb9f142bc66')
        self.assertEqual(frozen['prepared']['sha256'], '99b5f66b5388395a6d5b70c3ad0c6482fd346d148b6715596c4c9499f205ed5c')
        self.assertEqual(frozen['frozen_input_count'], 554)

    def test_actual_own130_archived_macro_and_measured_receipts_match_original_hashes(self):
        base = HERE.parent/'xu-score-resume-20261103'
        mapping_path = base/'terminal122/s2e-formal-activity12-20261105-120/simulator/sram-pin-alias/xu_s2e_sram_activity_alias.mapping.json'
        inventory_path = base/'progress135/s2e-full-soc-power12-20261105-130/inventory/inventory.json'
        measured_path = base/'progress135/s2e-full-soc-power12-20261105-130/task_00/measured-sram-pins.json'
        prepared_path = base/'terminal151/s2e-full-soc-power12-20261105-130/prepared.json'
        if not all(p.is_file() for p in (mapping_path, inventory_path, measured_path, prepared_path)):
            self.skipTest('actual130 local archived evidence absent')
        task = read(prepared_path)['tasks'][0]; bridge = task['mapped_macro_bridge_receipt']
        self.assertEqual(identity(mapping_path)['sha256'], bridge['mapping']['sha256'])
        self.assertEqual(identity(inventory_path)['sha256'], bridge['inventory']['sha256'])
        self.assertEqual(identity(measured_path)['sha256'], task['measured_sram_pin_states']['sha256'])
        frozen = read(HERE/'receipts156.json')
        def local_receipt_check(path, expected):
            actual = identity(path)
            self.assertEqual((actual['bytes'],actual['sha256']),(expected['bytes'],expected['sha256']))
            return dict(expected)
        with patch.object(audit156, 'check', local_receipt_check):
            execution, prepared, receipts = audit156.frozen_receipts(prepared_path.parent)
        self.assertEqual(receipts['execution'], frozen['execution'])
        pairs, macro_sha = saif156.binding(read(mapping_path), read(inventory_path))
        self.assertEqual(macro_sha, bridge['macro_bijection_sha256'])
        measured = {row['mapped_path']: row for row in read(measured_path)['pins']}
        rows = [[original, target, {k:v for k,v in measured[target[len(saif156.STRIP)+1:]].items() if k not in ('path','kind','mapped_path')}]
                for original, target in sorted(pairs.items())]
        self.assertEqual(canonical(rows), bridge['per_bit_comparison_sha256'])
        self.assertEqual(sum(row[2].get(k,0) for row in rows for k in ('TX','TZ','TB')), bridge['measured_unknown_bit_ticks'])
        self.assertEqual(len(measured),22512)


if __name__ == '__main__': unittest.main()
