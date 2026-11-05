#!/usr/bin/env python3
"""Pure Python mixed-ref inventory and lossless SAIF boundary checks."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load(HERE / 'macro145.py', 'xu_macro145_tested')
h = load(ROOT / 'tools/ppa/xu_sram_activity_alias.py', 'xu_macro145_test_helpers')
r = load(ROOT / 'tools/scripts/xu_soc_activity.py', 'xu_macro145_test_reader')


class Macro145(unittest.TestCase):
    def setUp(self):
        self.groups = [dict(name=ref, macro_ref=ref, instance_pattern='u_accel_icb_slave/*',
                            count=1, width=16, depth=2 ** pins['A'])
                       for ref, pins in m.PIN_WIDTHS.items()]
        self.log = '\n'.join('XU_MACRO145 ref=%s scope=tb.dut.u_accel_icb_slave.m%d.xu_pin_probe a_bits=%d pin_bits=%d' %
                             (ref, i, pins['A'], sum(pins.values()))
                             for i, (ref, pins) in enumerate(m.PIN_WIDTHS.items()))
        self.log += '\nXU_X145 scope=tb.dut.u_accel_icb_slave.x.xu_x_probe words=64\n'
        self.inventory = m.parse_inventory(self.log, self.groups, 2, 'tb.dut', 1)

    def fixture(self, path, flattened=False, mismatch=False, omit=False):
        stats = lambda: [['T0', '2'], ['T1', '2'], ['TX', '2'], ['TZ', '1'], ['TB', '3'], ['TC', '7'], ['IG', '5']]
        accel = ['INSTANCE', 'u_accel_icb_slave']
        for i, macro in enumerate(self.inventory['macros']):
            alias = ['NET']
            for pin, width in macro['pin_widths'].items():
                for bit in range(width):
                    name = pin if width == 1 else '%s[%d]' % (pin, bit)
                    if omit and i == 0 and name == 'CLK':
                        continue
                    alias.append([h.atom(('xu_pin_probe.' if flattened else '') + name)] + stats())
            alias.append(['xu_in_CLK'] + stats())
            probe = alias if flattened else ['INSTANCE', 'xu_pin_probe', alias]
            native = stats()
            if mismatch:
                native[0][1] = '3'; native[1][1] = '1'
            accel.append(['INSTANCE', 'm%d' % i, ['NET', ['CLK'] + native], probe])
        tree = ['SAIFILE', ['TIMESCALE', '1', 'fs'], ['DURATION', '10'],
                ['INSTANCE', 'tb', ['INSTANCE', 'dut', ['NET', ['ordinary'] + stats()], accel]]]
        with path.open('w') as stream:
            h.write_sexpr(stream, tree)

    def test_global_passive_bind_and_x_echo(self):
        sv = m.render_probes(m.PIN_WIDTHS)
        self.assertIn('bind RAMSP1024X16', sv)
        self.assertIn('bind RAMSP128X16', sv)
        self.assertIn('input [6:0] xu_in_A', sv)
        self.assertIn('bind XRowBuffer', sv)
        self.assertIn('xu_data[xu_addr]!==xu_word', sv)
        self.assertIn('xu_accelerator &&', sv)
        self.assertNotIn('force ', sv)

    def test_mixed_inventory_has_actual_bit_total(self):
        self.assertEqual(self.inventory['pin_bit_count'], 131)
        self.assertEqual(len(self.inventory['x_buffers']), 1)
        for change in [self.log + self.log.splitlines()[0], self.log.replace('a_bits=7', 'a_bits=10'),
                       self.log.replace('.m1.', '.unmatched.m1.').replace('u_accel_icb_slave.m0', 'other.m0')]:
            with self.assertRaises(ValueError):
                m.parse_inventory(change, self.groups, 2, 'tb.dut', 1)

    def test_normalization_preserves_all_unknown_buckets_and_nonaliases(self):
        for flattened in (False, True):
            with self.subTest(flattened=flattened), tempfile.TemporaryDirectory() as directory:
                raw, out = [Path(directory) / name for name in ('raw.saif', 'out.saif')]
                self.fixture(raw, flattened=flattened)
                original = raw.read_bytes()
                receipt = m.normalize(raw, out, self.inventory, r, h)
                self.assertEqual(raw.read_bytes(), original)
                self.assertEqual(receipt['pin_bit_count'], 131)
                self.assertEqual(receipt['native_pin_bits_verified_reused'], 2)
                self.assertEqual(receipt['alias_unknown_bit_ticks'], 131 * 6)
                signals = {(s['kind'], s['path']): s for s in r.read_saif(out)['signals']}
                self.assertEqual(signals['NET', 'tb/dut/ordinary']['TB'], 3)
                self.assertEqual(signals['PORT', 'tb/dut/u_accel_icb_slave/m1/A[6]']['IG'], 5)
                self.assertFalse(any('xu_pin_probe' in p for _, p in signals))

    def test_missing_alias_and_native_mismatch_fail_without_output(self):
        for kwargs in (dict(omit=True), dict(mismatch=True)):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as directory:
                raw, out = [Path(directory) / name for name in ('raw.saif', 'out.saif')]
                self.fixture(raw, **kwargs)
                with self.assertRaises(ValueError):
                    m.normalize(raw, out, self.inventory, r, h)
                self.assertFalse(out.exists())

    def test_no_clobber_and_bad_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            raw, out = [Path(directory) / name for name in ('raw.saif', 'out.saif')]
            self.fixture(raw)
            out.write_text('keep')
            with self.assertRaises(ValueError):
                m.normalize(raw, out, self.inventory, r, h)
            self.assertEqual(out.read_text(), 'keep')
            inventory = copy.deepcopy(self.inventory); inventory['pin_bit_count'] += 1
            with self.assertRaises(ValueError):
                m.normalize(raw, out.with_name('other.saif'), inventory, r, h)


if __name__ == '__main__':
    unittest.main()
