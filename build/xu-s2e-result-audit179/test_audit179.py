#!/usr/bin/env python3
"""Local unit/negative checks; no mocked result is counted as native evidence."""
import copy
from decimal import Decimal
from pathlib import Path
import unittest
import audit179 as a

POWER = '''Design : xu_soc_ppa_top
Dynamic Power Units = 1 W
Leakage Power Units = 1 W
Net Switching Power = 1.2e-2 (30%)
Cell Internal Power = 2e-2 (60%)
Cell Leakage Power = 0.003 (10%)
Total Power = 3.5e-2 (100%)
'''


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.refs = a.reference_data()

    def test_actual_reference_freeze(self):
        self.assertEqual(self.refs['state']['formal_passing'], 42338)
        self.assertEqual(len(self.refs['state']['frozen_before']), 204)

    def test_actual_155_native_complete_fm(self):
        a.native_fm((a.HERE / 'references/155-final-fm.log').read_text())

    def test_fm_rejects_zero_rc_without_success_marker(self):
        raw = (a.HERE / 'references/155-final-fm.log').read_text()
        with self.assertRaises(ValueError):
            a.native_fm(raw.replace('\nXU_S2E_TIMING134_FORMALITY_PASS\n', '\n'))

    def test_fm_rejects_scope_or_duplicate_marker(self):
        raw = (a.HERE / 'references/155-final-fm.log').read_text()
        for poisoned in [raw.replace('42338 Passing compare points', '42337 Passing compare points'),
                         raw + '\nXU_S2E_TIMING134_FORMALITY_PASS\n', raw + '\nError: bad\n']:
            with self.subTest(poison=poisoned[-40:]), self.assertRaises(ValueError):
                a.native_fm(poisoned)

    def test_watts_decimal_and_native_precision(self):
        result = a.power_values(POWER)
        self.assertEqual(result['total_power_w'], '0.035')
        self.assertEqual(Decimal(result['total_power_w']) * Decimal(5788953333333) * Decimal('1e-15'),
                         Decimal('0.000202613366666655'))

    def test_rejects_wrapper_or_changed_units(self):
        for raw in [POWER.replace('xu_soc_ppa_top', 'accel_icb_slave'), POWER.replace('1 W', '1 mW'),
                    POWER.replace('1 W', '1000 W')]:
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError): a.power_values(raw)

    def test_rejects_ambiguous_invalid_power(self):
        for raw in [POWER + 'Total Power = 1e-3 (100%)\n', POWER.replace('3.5e-2', '-1'),
                    POWER.replace('3.5e-2', 'NaN'), POWER.replace('3.5e-2', '1e99999999999999999999999')]:
            with self.subTest(raw=raw[-80:]), self.assertRaises((ValueError, ArithmeticError)):
                a.power_values(raw)

    def test_geometry_not_128_or_32bit(self):
        self.assertEqual(len(a.PIN_NAMES), 67)
        self.assertIn('A[9]', a.PIN_NAMES)
        self.assertNotIn('A[10]', a.PIN_NAMES)
        self.assertIn('Q[15]', a.PIN_NAMES)
        self.assertNotIn('Q[16]', a.PIN_NAMES)

    def test_report_set(self):
        reports = a.expected_reports()
        self.assertEqual(len(reports), len(set(reports)))
        for required in ['source-propagated-before.rpt', 'source-no_switching_activity-after.rpt',
                         'sram-pins-before.rpt', 'sram-pins-after.rpt', 'update-power.rpt']:
            self.assertIn(required, reports)

    def test_missing_full12_cannot_be_complete(self):
        class Empty:
            @staticmethod
            def has(name): return False
        status = a.campaign(Empty(), a.ROOT12, list(range(12)), self.refs)
        self.assertFalse(status['complete'])
        self.assertEqual(status['status'], 'OBSERVED_INCOMPLETE_NOT_QUALIFIED')
        self.assertNotIn('sum_diagnostic_energy_j', status)

    def test_failed_task0_not_complete(self):
        class Failed:
            @staticmethod
            def has(name): return name.endswith('/result.json')
            @staticmethod
            def json(name): return dict(status='FAIL166_NOT_QUALIFIED', error='original failure')
        status = a.campaign(Failed(), a.ROOT0, [0], self.refs)
        self.assertFalse(status['complete'])
        self.assertEqual(status['source_error'], 'original failure')

    def test_task0_claim_with_missing_receipts_rejected(self):
        class Partial:
            @staticmethod
            def has(name): return name.endswith('/result.json')
            @staticmethod
            def json(name): return dict(status=a.TASK0)
        with self.assertRaises(ValueError): a.campaign(Partial(), a.ROOT0, [0], self.refs)

    def test_historical_identity_keeps155_energy_null(self):
        comparison = a.load(a.HERE / 'references/165-comparison.json')
        self.assertIsNone(comparison['newer_s2e155']['diagnostic_energy12_j'])
        self.assertEqual(comparison['original_map_comparison']['s2e']['mapped_sha256'], a.OLDNET)
        self.assertNotEqual(a.NET, a.OLDNET)


if __name__ == '__main__':
    unittest.main(verbosity=2)
