"""Guard tests for effective-width encoding and mathematical accumulator bounds."""
from fractions import Fraction
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from model import fixed16_acc48 as fixed
import sweep_kwt_precision as sweep


class PrecisionTests(unittest.TestCase):
    def test_scale_checks_smaller_positive_peak(self):
        self.assertEqual(sweep.scale_exponent(32767.0, 16), 0)
        self.assertEqual(sweep.scale_exponent(32767.0, 12), 5)
        for bits in (8, 10, 12, 14, 16):
            peak = (1 << (bits - 1)) - 1
            for bound in (0.000001, 0.5, 3.7, 11.3, float(peak), float(peak + 1)):
                exp = sweep.scale_exponent(bound, bits)
                capacity = lambda e: peak * (Fraction(1 << e) if e >= 0 else Fraction(1, 1 << -e))
                self.assertGreaterEqual(capacity(exp), Fraction.from_float(bound))
                self.assertLess(capacity(exp - 1), Fraction.from_float(bound))

    def test_scale_zero_and_invalid_domain(self):
        self.assertEqual(sweep.scale_exponent(0.0, 8), 0)
        for bound, bits in ((-1.0, 8), (math.inf, 8), (math.nan, 8), (1.0, 1), (1.0, 17), (1.0, True)):
            with self.assertRaises(ValueError):
                sweep.scale_exponent(bound, bits)

    def test_effective_range_rne_saturation_matches_fraction(self):
        for bits in (8, 10, 12, 14, 16, 40):
            peak = (1 << (bits - 1)) - 1
            vals = np.array([-2 * peak, -peak - 1, -peak, -1.5, -0.5, 0.5, 1.5, peak, peak + 1], dtype=np.float32)
            for exponent in (-4, 0, 2):
                actual, clips = sweep.encode(vals, bits, exponent)
                expected = [fixed.encode_scalar(float(v), bits, exponent) for v in vals]
                self.assertEqual(actual.tolist(), expected)
                self.assertTrue(np.all(actual >= -(1 << (bits - 1))))
                self.assertTrue(np.all(actual <= peak))
                exact = [round(Fraction.from_float(float(v)) / fixed._scale(exponent)) for v in vals]
                self.assertEqual(clips, sum(v < -(1 << (bits - 1)) or v > peak for v in exact))

    def test_rejects_encoding_wrong_domain(self):
        for vals, bits, exp in ((np.zeros(1, dtype=np.float64), 8, 0),
                                (np.array([math.nan], dtype=np.float32), 8, 0),
                                (np.zeros(1, dtype=np.float32), 17, 0),
                                (np.zeros(1, dtype=np.float32), 8, 65)):
            with self.assertRaises(ValueError):
                sweep.encode(vals, bits, exp)

    def test_bias40_needs41_acc_for_all_candidates(self):
        for xb, wb in sweep.CANDIDATES:
            bound = sweep.accumulator_bound(xb, wb, -(1 << 39), (1 << 39) - 1)
            self.assertEqual(bound["signed_bits"], 41)
            self.assertLessEqual(bound["minimum"], -(1 << 39))
            self.assertGreater(bound["maximum"], (1 << 39) - 1)

    def test_accumulator_interval_exact_small_exhaustive_domain(self):
        for xb, wb in ((2, 2), (2, 3), (3, 2), (3, 3)):
            products = [x * w for x in range(-(1 << (xb - 1)), 1 << (xb - 1))
                        for w in range(-(1 << (wb - 1)), 1 << (wb - 1))]
            for low, high in ((-8, 7), (-1, 0), (0, 0)):
                bound = sweep.accumulator_bound(xb, wb, low, high)
                reachable = [bias + k * product for bias in (low, high) for k in range(65) for product in products]
                self.assertEqual(bound["minimum"], min(reachable))
                self.assertEqual(bound["maximum"], max(reachable))
                bits = bound["signed_bits"]
                self.assertGreaterEqual(bound["minimum"], -(1 << (bits - 1)))
                self.assertLessEqual(bound["maximum"], (1 << (bits - 1)) - 1)
                self.assertTrue(bound["minimum"] < -(1 << (bits - 2)) or bound["maximum"] > (1 << (bits - 2)) - 1)

    def test_required_signed_bits_boundary(self):
        for bits in (2, 8, 16, 40, 41, 48):
            self.assertEqual(sweep.required_signed_bits(-(1 << (bits - 1)), (1 << (bits - 1)) - 1), bits)
            self.assertEqual(sweep.required_signed_bits(-(1 << (bits - 1)) - 1, 0), bits + 1)
            self.assertEqual(sweep.required_signed_bits(0, 1 << (bits - 1)), bits + 1)
        with self.assertRaises(ValueError):
            sweep.required_signed_bits(1, 0)

    def test_precision_score_uses_ratio_not_percent(self):
        self.assertEqual(sweep.precision_score_proxy(0.0), 10.0)
        self.assertEqual(sweep.precision_score_proxy(0.003), 9.0)
        self.assertAlmostEqual(sweep.precision_score_proxy(0.03), 0.0)
        self.assertEqual(sweep.precision_score_proxy(0.05), 0.0)
        for value in (math.inf, math.nan, -0.1):
            with self.assertRaises(ValueError):
                sweep.precision_score_proxy(value)


if __name__ == "__main__":
    unittest.main()
