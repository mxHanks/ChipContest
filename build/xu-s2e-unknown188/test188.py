#!/usr/bin/env python3
"""Host checks for the local evidence classifier, without native EDA tools."""
import json
from pathlib import Path
import tempfile
import unittest

import analyze188 as a
from saif188 import selected_signals


class SaifTests(unittest.TestCase):
    def parse(self, body, wanted={'top/mac/Q[0]'}, duration=10, time='1 fs'):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'input.saif'
            p.write_text('(SAIFILE (TIMESCALE %s) (DURATION 1e1) (INSTANCE top (INSTANCE mac (PORT %s))))' % (time, body))
            return selected_signals(p, wanted, duration)

    def test_exponential_duration_and_escaped_pin(self):
        selected, receipt = self.parse(r'(Q\[0\] (T0 1) (T1 2) (TX 3) (TZ 4) (TC 5))')
        self.assertEqual(selected[('PORT', 'top/mac/Q[0]')]['TX'], 3)
        self.assertEqual(receipt, dict(signal_records=1, selected_records=1, duration_fs=10))

    def test_duplicate_selected_record_rejected(self):
        q = '(Q[0] (T0 10) (T1 0) (TX 0) (TC 0))'
        with self.assertRaisesRegex(ValueError, 'duplicate selected'):
            self.parse(q + q)

    def test_missing_selected_pin_rejected(self):
        with self.assertRaisesRegex(ValueError, 'missing selected'):
            self.parse('(Q[1] (T0 10) (T1 0) (TX 0) (TC 0))')

    def test_bad_dwell_rejected(self):
        with self.assertRaisesRegex(ValueError, 'dwell sum'):
            self.parse('(Q[0] (T0 1) (T1 0) (TX 0) (TC 0))')

    def test_negative_fractional_and_nan_rejected(self):
        for value in ['-1', '0.5', 'NaN']:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'invalid statistic'):
                self.parse('(Q[0] (T0 %s) (T1 0) (TX 10) (TC 0))' % value)

    def test_wrong_timebase_rejected(self):
        with self.assertRaisesRegex(ValueError, 'root/timebase'):
            self.parse('(Q[0] (T0 10) (T1 0) (TX 0) (TC 0))', time='1 ps')

    def test_duplicate_stats_rejected(self):
        with self.assertRaisesRegex(ValueError, 'invalid selected SAIF stats'):
            self.parse('(Q[0] (T0 10) (T0 0) (T1 0) (TX 0) (TC 0))')

    def test_unrelated_records_counted_but_not_returned(self):
        selected, receipt = self.parse('(A[0] (T0 10) (T1 0) (TX 0) (TC 0)) (Q[0] (T0 10) (T1 0) (TX 0) (TC 0))')
        self.assertEqual(len(selected), 1)
        self.assertEqual(receipt['signal_records'], 2)

    def test_both_port_and_net_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'dual.saif'
            q = '(Q[0] (T0 10) (T1 0) (TX 0) (TC 0))'
            p.write_text('(SAIFILE (TIMESCALE 1 fs) (DURATION 10) (INSTANCE top (INSTANCE mac (PORT %s) (NET %s))))' % (q, q))
            selected, receipt = selected_signals(p, {'top/mac/Q[0]'}, 10)
            self.assertEqual({k[0] for k in selected}, {'NET', 'PORT'})
            self.assertEqual(receipt['selected_records'], 2)


class MarginalTests(unittest.TestCase):
    def test_overlap_without_independence(self):
        self.assertEqual(a.overlap(7, 6, 10), (3, 6))
        self.assertEqual(a.overlap(7, 10, 10), (7, 7))
        self.assertEqual(a.overlap(7, 0, 10), (0, 0))
        self.assertEqual(a.overlap(0, 10, 10), (0, 0))

    def test_invalid_overlap_rejected(self):
        for x, y in [(-1, 0), (11, 0), (0, 11)]:
            with self.subTest(x=x, y=y), self.assertRaisesRegex(ValueError, 'invalid marginal'):
                a.overlap(x, y, 10)

    def test_no_unproved_control_alias(self):
        self.assertTrue({'CEN', 'GWEN', 'RET1N', 'WEN[0]', 'EMA[0]', 'EMAW[0]'} <= a.PINS)
        self.assertFalse({'NCS', 'WEB', 'NAP', 'CE'} & a.PINS)
        self.assertEqual(len(a.PINS), 67)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'duplicate.json'; p.write_text('{"status":1,"status":2}')
            with self.assertRaisesRegex(ValueError, 'duplicate JSON'):
                a.load(p)

    def test_frozen_source_index(self):
        self.assertEqual(a.sha(a.HERE / 'sources188.json'), a.SOURCE_SHA)
        index = a.load(a.HERE / 'sources188.json')
        self.assertEqual(len(index['files']), 40)
        for row in index['local_references']:
            self.assertTrue(a.same(a.ident(a.HERE / row['path']), row))


if __name__ == '__main__':
    unittest.main(verbosity=2)
