"""Strict alias provenance and actual four-state port-waveform checks.

The default simulator probe uses an open contract stand-in. Set both
XU_SRAM_VENDOR_MODEL and XU_SRAM_VENDOR_SHA256 for the private vendor model.
Neither test is VCS SAIF or mapped-power qualification.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_sram_activity_alias', ROOT / 'tools/ppa/xu_sram_activity_alias.py')
alias = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(alias)
activity = alias.activity_module()

STAND_IN = '''// xu open four-state port contract; not a vendor/power/timing model.
`timescale 1ns/1ps
`celldefine
module RAMSP1024X16(output reg [15:0] Q, input CLK,CEN,GWEN,
 input [15:0] WEN, input [9:0] A, input [15:0] D,
 input [2:0] EMA,input [1:0] EMAW,input RET1N);
 reg [15:0] contents[0:1023];
 integer bit_index;
 always @(posedge CLK) if(!CEN) begin
  if(!GWEN) begin
   for(bit_index=0;bit_index<16;bit_index=bit_index+1)
    if(!WEN[bit_index]) contents[A][bit_index] <= D[bit_index];
  end else Q <= contents[A];
 end
endmodule
`endcelldefine
'''


def native_signals(parsed):
    return {(s['kind'], s['path']): s for s in parsed['signals']}


class AliasNormalizationTests(unittest.TestCase):
    def fixture(self, directory):
        mapping = alias.generate(ROOT, directory / 'observer', dut_scope='tb.dut',
                                 placement='include', macro_paths=['tb.dut.macro'])
        mapping_path = directory / 'observer/xu_sram_activity_alias.mapping.json'
        _, pairs = alias.validate_mapping(mapping_path)
        raw = directory / 'raw.saif'
        signals = []
        for i, path in enumerate(sorted(pairs)):
            # Include both X/Z and TB dwell; no unknowns may be discarded.
            values = [2, 3, 4, 1, 0] if path.endswith('/Q[0]') else [10, 0, 0, 0, i % 3]
            signals.append((path, 'NET', dict(zip(['T0', 'T1', 'TX', 'TZ', 'TC'], values))))
        signals.append(('tb/dut/regular[2]', 'NET', dict(T0=1, T1=2, TX=3, TZ=1, TB=3, TC=7, IG=2)))
        self.write_raw(raw, signals)
        return mapping, mapping_path, pairs, raw, signals

    def write_raw(self, path, signals):
        root = ['SAIFILE', ['SAIFVERSION', '"2.0"'], ['DESIGN', '"xu design with spaces"'],
                ['DATE', '"literal \\"quoted\\" text"'], ['TIMESCALE', '1', 'ns'], ['DURATION', '10']]
        branches = {}
        for name, kind, values in signals:
            parts = name.split('/')
            for i in range(1, len(parts)):
                scope = '/'.join(parts[:i])
                if scope not in branches:
                    node = ['INSTANCE', alias.atom(parts[i - 1])]
                    (root if i == 1 else branches['/'.join(parts[:i - 1])]).append(node)
                    branches[scope] = node
            scope = branches['/'.join(parts[:-1])]
            section = next((n for n in scope[2:] if n[0] == kind), None)
            if section is None:
                section = [kind]
                scope.append(section)
            section.append([alias.atom(parts[-1])] + [[key, str(value)] for key, value in values.items()])
        with path.open('w') as output:
            alias.write_sexpr(output, root)

    def test_complete_mapping_unknowns_headers_and_every_nonalias_signal_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            _, mapping_path, pairs, raw, _ = self.fixture(d)
            before = alias.sha(raw)
            result = alias.normalize(raw, mapping_path, d / 'normalized.saif')
            output = native_signals(activity.read_saif(d / 'normalized.saif'))
            original = native_signals(activity.read_saif(raw))
            self.assertEqual(alias.sha(raw), before)
            self.assertEqual(result['alias_bit_count'], 67)
            self.assertEqual(result['mapped_pin_bits_added_as_port'], 67)
            self.assertEqual(result['alias_unknown_bit_ticks'], 5)
            self.assertEqual(output[('NET', 'tb/dut/regular[2]')], original[('NET', 'tb/dut/regular[2]')])
            self.assertIn('(DESIGN "xu design with spaces")', (d / 'normalized.saif').read_text())
            self.assertIn('(DATE "literal \\"quoted\\" text")', (d / 'normalized.saif').read_text())
            for source, target in pairs.items():
                self.assertEqual(alias.stats(output[('PORT', target)]), alias.stats(original[('NET', source)]))
            self.assertFalse(any('/xu_sram_activity_alias/' in s['path'] for s in output.values()))
            self.assertEqual(result['raw_saif']['sha256'], before)
            self.assertEqual(result['normalized_saif']['sha256'], alias.sha(d / 'normalized.saif'))
            self.assertEqual(result['alias_name_encoding_counts'],
                             dict(hierarchical=67, vcs_generate_net_atom=0))

    def test_observed_vcs_generate_net_atoms_preserve_all_statistics_and_literal_dots(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            _, mapping_path, pairs, raw, signals = self.fixture(d)
            # Actual VCS 2020 spelling: the generate block and pin are one
            # literal NET atom below the observer INSTANCE, not two scopes.
            vcs = {path: path.rsplit('/', 1)[0] + '.' + path.rsplit('/', 1)[1] for path in pairs}
            self.assertIn('tb/xu_sram_activity_alias/macro_0000.CLK', vcs.values())
            signals = [(path, kind, dict(T0=1, T1=2, TX=3, TZ=1, TB=3, TC=7, IG=2)
                        if path.endswith('/CLK') else values) for path, kind, values in signals]
            signals = [(vcs.get(path, path), kind, values) for path, kind, values in signals]
            unrelated = [('tb/dut/macro_0000.CLK', 'NET', dict(T0=1, T1=2, TX=3, TZ=1, TB=3, TC=7, IG=2)),
                         ('tb/unrelated/xu_sram_activity_alias.macro_0000.CLK', 'PORT',
                          dict(T0=3, T1=1, TX=2, TZ=4, TC=5))]
            signals += unrelated
            self.write_raw(raw, signals)
            before = alias.sha(raw)
            result = alias.normalize(raw, mapping_path, d / 'normalized.saif')
            original = native_signals(activity.read_saif(raw))
            output = native_signals(activity.read_saif(d / 'normalized.saif'))
            self.assertEqual(alias.sha(raw), before)
            self.assertEqual(result['alias_name_encoding_counts'],
                             dict(hierarchical=0, vcs_generate_net_atom=67))
            self.assertEqual(result['alias_name_comparison_sha256'], alias.canonical_hash(sorted(vcs.items())))
            self.assertEqual(result['mapped_pin_bits_added_as_port'], 67)
            self.assertEqual(result['alias_unknown_bit_ticks'], 12)
            for source, target in pairs.items():
                self.assertEqual(alias.stats(output[('PORT', target)]), alias.stats(original[('NET', vcs[source])]))
            for path, kind, _ in unrelated + [('tb/dut/regular[2]', 'NET', {})]:
                self.assertEqual(output[(kind, path)], original[(kind, path)])
            self.assertFalse(any('/xu_sram_activity_alias/' in path for _, path in output))
            self.assertEqual(len(output), 67 + len(unrelated) + 1)
            self.assertIn('(DATE "literal \\"quoted\\" text")', (d / 'normalized.saif').read_text())

    def test_mixed_exact_encodings_require_one_source_per_bit(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            _, mapping_path, pairs, raw, signals = self.fixture(d)
            selected = sorted(pairs)[::2]
            vcs = {path: path.rsplit('/', 1)[0] + '.' + path.rsplit('/', 1)[1] for path in selected}
            self.write_raw(raw, [(vcs.get(path, path), kind, values) for path, kind, values in signals])
            result = alias.normalize(raw, mapping_path, d / 'normalized.saif')
            self.assertEqual(result['alias_name_encoding_counts'],
                             dict(hierarchical=67 - len(selected), vcs_generate_net_atom=len(selected)))
            self.assertEqual(result['mapped_pin_bits_added_as_port'], 67)

    def test_duplicate_encodings_and_unsupported_flattening_fail_without_output(self):
        for mode in ('duplicate_NET', 'duplicate_PORT', 'extra_dot', 'nested_dot', 'scalar_index', 'block_index'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)
                _, mapping_path, pairs, raw, signals = self.fixture(d)
                canonical = 'tb/xu_sram_activity_alias/macro_0000/CLK'
                values = next(values for path, _, values in signals if path == canonical)
                if mode.startswith('duplicate_'):
                    signals.append(('tb/xu_sram_activity_alias/macro_0000.CLK', mode.split('_')[1], dict(values)))
                else:
                    unsupported = {'extra_dot': 'macro_0000.extra.CLK', 'nested_dot': 'macro_0000/extra.CLK',
                                   'scalar_index': 'macro_0000.CLK[0]', 'block_index': 'macro_00000.CLK'}[mode]
                    signals = [(('tb/xu_sram_activity_alias/' + unsupported) if path == canonical else path,
                                kind, stats) for path, kind, stats in signals]
                self.write_raw(raw, signals)
                before = alias.sha(raw)
                with self.assertRaises(ValueError):
                    alias.normalize(raw, mapping_path, d / 'bad.saif')
                self.assertFalse((d / 'bad.saif').exists())
                self.assertFalse((d / 'bad.saif.receipt.json').exists())
                self.assertEqual(alias.sha(raw), before)

    def test_native_net_port_or_both_reused_without_introduced_cross_kind_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            _, mapping_path, pairs, raw, signals = self.fixture(d)
            first = sorted(pairs)[:3]
            for index, source in enumerate(first):
                values = next(stats for path, _, stats in signals if path == source)
                for kind in (['NET'], ['PORT'], ['NET', 'PORT'])[index]:
                    signals.append((pairs[source], kind, copy.deepcopy(values)))
            self.write_raw(raw, signals)
            result = alias.normalize(raw, mapping_path, d / 'normalized.saif')
            output = native_signals(activity.read_saif(d / 'normalized.saif'))
            self.assertEqual(result['native_pin_bits_verified_reused'], 3)
            self.assertEqual(result['preexisting_native_net_and_port_bits_preserved'], 1)
            self.assertEqual(result['mapped_pin_bits_added_as_port'], 64)
            self.assertNotIn(('PORT', pairs[first[0]]), output)
            self.assertNotIn(('NET', pairs[first[1]]), output)

    def test_missing_extra_native_mismatch_and_duplicate_alias_fail_without_output(self):
        for mode in ('missing', 'extra', 'mismatch', 'duplicate'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)
                _, mapping_path, pairs, raw, signals = self.fixture(d)
                source = sorted(pairs)[0]
                values = next(stats for path, _, stats in signals if path == source)
                if mode == 'missing':
                    signals = [s for s in signals if s[0] != source]
                elif mode == 'extra':
                    signals.append(('tb/xu_sram_activity_alias/extra', 'NET', dict(values)))
                elif mode == 'mismatch':
                    signals.append((pairs[source], 'PORT', dict(T0=9, T1=1, TX=0, TZ=0, TC=0)))
                else:
                    signals.append((source, 'PORT', dict(values)))
                self.write_raw(raw, signals)
                before = alias.sha(raw)
                with self.assertRaises(ValueError):
                    alias.normalize(raw, mapping_path, d / 'bad.saif')
                self.assertFalse((d / 'bad.saif').exists())
                self.assertFalse((d / 'bad.saif.receipt.json').exists())
                self.assertEqual(alias.sha(raw), before)

    def test_source_tampering_nonbijective_mapping_and_overwrite_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            mapping, mapping_path, _, raw, _ = self.fixture(d)
            observer = Path(mapping['observer_source']['path'])
            observer.write_text(observer.read_text() + '// changed\n')
            with self.assertRaisesRegex(ValueError, 'source identity changed'):
                alias.normalize(raw, mapping_path, d / 'bad.saif')
            observer.write_text(observer.read_text()[:-len('// changed\n')])
            mapping['macros'].append(mapping['macros'][0])
            mapping['macro_count'] = 2
            alias.write_json(mapping_path, mapping)
            with self.assertRaisesRegex(ValueError, 'bijective'):
                alias.normalize(raw, mapping_path, d / 'bad.saif')
            with self.assertRaisesRegex(ValueError, 'paths must differ'):
                alias.normalize(raw, mapping_path, raw)

    def test_native_unknown_buckets_must_match_and_existing_output_is_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            _, mapping_path, pairs, raw, signals = self.fixture(d)
            source = next(path for path in pairs if path.endswith('/Q[0]'))
            signals.append((pairs[source], 'PORT', dict(T0=2, T1=3, TX=1, TZ=4, TC=0)))
            self.write_raw(raw, signals)
            with self.assertRaisesRegex(ValueError, 'native macro pin differs'):
                alias.normalize(raw, mapping_path, d / 'bad.saif')
            protected = d / 'existing.saif'
            protected.write_text('previous result\n')
            before = alias.sha(protected)
            with self.assertRaisesRegex(ValueError, 'must be new files'):
                alias.normalize(raw, mapping_path, protected)
            self.assertEqual(alias.sha(protected), before)

    def test_full_soc_exact_group_counts_and_bind_is_synthesis_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            mapping = alias.generate(ROOT, d / 'bound')
            mapping_path = d / 'bound/xu_sram_activity_alias.mapping.json'
            _, pairs = alias.validate_mapping(mapping_path)
            self.assertEqual(mapping['macro_count'], 336)
            self.assertEqual(len(pairs), 22512)
            encodings = alias.alias_name_encodings(mapping, pairs)
            self.assertEqual(len(encodings), 45024)
            self.assertEqual(encodings['tb_xu_soc_ppa/dut/xu_sram_activity_alias/macro_0335.Q[15]'],
                             ('tb_xu_soc_ppa/dut/xu_sram_activity_alias/macro_0335/Q[15]', 'vcs_generate_net_atom'))
            self.assertEqual({group: sum(m['group'] == group for m in mapping['macros'])
                              for group in ('shared', 'itcm', 'dtcm', 'accelerator_weights')},
                             dict(shared=256, itcm=32, dtcm=32, accelerator_weights=16))
            text = Path(mapping['observer_source']['path']).read_text()
            self.assertIn('`ifndef SYNTHESIS', text)
            self.assertIn('bind tb_xu_soc_ppa.dut xu_sram_activity_alias_observer xu_sram_activity_alias();', text)
            self.assertIn('initial Q = tb_xu_soc_ppa.dut.', text)
            self.assertNotIn('force ', text)


@unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'), 'Icarus required')
class FourStatePortProbeTests(unittest.TestCase):
    def run_probe(self, vendor=None, expected_hash=None):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            model = d / 'open_model.sv'
            if vendor is None:
                model.write_text(STAND_IN)
            else:
                model = Path(vendor).resolve()
                self.assertEqual(alias.sha(model), expected_hash, 'vendor source SHA differs')
            base = 'tb_xu_sram_activity_alias.dut.'
            paths = [base + name + '.macro_storage.depth_bank[0].width_lane[%d].macro' % lane
                     for name, lanes in [('live', 2), ('idle', 1)] for lane in range(lanes)]
            mapping = alias.generate(ROOT, d / 'observer', dut_scope=base[:-1], placement='include', macro_paths=paths)
            (d / 'observer/xu_sram_activity_alias_dump.svh').write_text('\n'.join(
                '$dumpvars(0,' + path + '.' + pin + ');' for path in paths for pin in alias.PIN_WIDTHS) + '\n')
            command = ['iverilog', '-g2012', '-DARM_UD_MODEL', '-I', str(d / 'observer'), '-s', 'tb_xu_sram_activity_alias',
                       '-o', str(d / 'sim.vvp'), str(model), str(ROOT / 'tools/ppa/xu_sirv_sram_adapter.sv'),
                       str(ROOT / 'tests/ppa/tb_xu_sram_activity_alias.sv')]
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            run = subprocess.run(['vvp', str(d / 'sim.vvp')], cwd=d, check=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            self.assertIn(b'XU_SRAM_ACTIVITY_ALIAS_PROBE_PASS', run.stdout)
            with (d / 'xu_sram_alias_probe.vcd').open() as source:
                activity.vcd_to_saif(source, d / 'raw.saif', 2000, 100000, 'tb_xu_sram_activity_alias')
            observed = native_signals(activity.read_saif(d / 'raw.saif'))
            _, pairs = alias.validate_mapping(d / 'observer/xu_sram_activity_alias.mapping.json')
            # The assertion is independent of normalization: compare all 201
            # measured observer bits to the actual macro ports in the waveform.
            for source, target in pairs.items():
                self.assertEqual(alias.stats(observed[('NET', source)]), alias.stats(observed[('NET', target)]), target)
            live = paths[0].replace('.', '/')
            idle = paths[2].replace('.', '/')
            self.assertEqual([observed[('NET', live + '/CLK')][key] for key in ('T0', 'T1', 'TX', 'TC')], [68000, 30000, 0, 12])
            self.assertEqual([observed[('NET', idle + '/CLK')][key] for key in ('T0', 'T1', 'TX', 'TC')], [98000, 0, 0, 0])
            self.assertEqual(observed[('NET', idle + '/CEN')]['T1'], 98000)
            self.assertEqual(observed[('NET', idle + '/RET1N')]['T1'], 98000)
            self.assertEqual(observed[('NET', idle + '/Q[0]')]['TX'], 98000)
            self.assertGreater(observed[('NET', live + '/Q[0]')]['TX'], 0)
            upper = paths[1].replace('.', '/')
            self.assertEqual(observed[('NET', upper + '/D[15]')]['TZ'], 20000)
            self.assertEqual(observed[('NET', upper + '/D[0]')]['TX'], 20000)
            self.assertEqual(observed[('NET', live + '/WEN[0]')]['TC'], 1)
            self.assertEqual(observed[('NET', live + '/WEN[8]')]['TC'], 2)
            before = alias.sha(d / 'raw.saif')
            result = alias.normalize(d / 'raw.saif', d / 'observer/xu_sram_activity_alias.mapping.json', d / 'normalized.saif')
            self.assertEqual(result['native_pin_bits_verified_reused'], 201)
            self.assertEqual(result['mapped_pin_bits_added_as_port'], 0)
            self.assertGreater(result['alias_unknown_bit_ticks'], 0)
            self.assertEqual(before, alias.sha(d / 'raw.saif'))
            self.assertEqual(mapping['mode'], 'explicit_probe_only')

    def test_open_four_state_clock_gating_idle_byte_writes_and_unknown_Q(self):
        self.run_probe()

    @unittest.skipUnless(os.environ.get('XU_SRAM_VENDOR_MODEL') and os.environ.get('XU_SRAM_VENDOR_SHA256'),
                         'private vendor model path and SHA must be explicitly supplied')
    def test_private_vendor_port_waveforms_match_all_alias_bits(self):
        self.run_probe(os.environ['XU_SRAM_VENDOR_MODEL'], os.environ['XU_SRAM_VENDOR_SHA256'])


if __name__ == '__main__':
    unittest.main()
