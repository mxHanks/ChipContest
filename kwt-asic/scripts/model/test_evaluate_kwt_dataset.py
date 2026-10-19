"""Independent numerical guard tests; run in .venv-kwt (NumPy 1.19.5)."""
from pathlib import Path
import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from model import fixed16_acc48 as fixed
import evaluate_kwt_dataset as evaluator


class QuantizerTests(unittest.TestCase):
    def assert_codes(self, values, bits, exponent):
        values = np.asarray(values, dtype=np.float32)
        actual, clips = evaluator.quantize_float32(values, bits, exponent)
        expected = [fixed.encode_scalar(float(v), bits, exponent) for v in values.flat]
        self.assertEqual(actual.ravel().tolist(), expected)
        self.assertEqual(clips, sum(1 for v in values.flat if round(
            fixed._fraction(float(v)) / fixed._scale(exponent)) not in
            range(-(1 << (bits - 1)), 1 << (bits - 1))))

    def test_rne_half_ties_and_neighbors(self):
        for exponent in (-20, -3, 0, 16):
            ties = np.ldexp(np.arange(-32, 33, dtype=np.float32) + np.float32(0.5), exponent)
            self.assert_codes(np.concatenate([ties, np.nextafter(ties, np.float32(-np.inf)),
                                               np.nextafter(ties, np.float32(np.inf))]), 16, exponent)

    def test_float32_subnormals_extremes_and_negative_zero(self):
        values = np.array([0.0, -0.0, np.nextafter(np.float32(0), np.float32(1)),
                           -np.nextafter(np.float32(0), np.float32(1)),
                           np.finfo(np.float32).max, -np.finfo(np.float32).max], dtype=np.float32)
        for exponent in (-64, 0, 64):
            for bits in (16, 40):
                self.assert_codes(values, bits, exponent)

    def test_saturation_boundaries(self):
        for bits in (16, 40):
            lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
            values = np.array([lo - 1, lo, lo + 1, hi - 1, hi, hi + 1], dtype=np.float32)
            self.assert_codes(values, bits, 0)

    def test_random_float32_exact_reference(self):
        rng = np.random.RandomState(8191)
        values = rng.normal(size=1024).astype(np.float32)
        for exponent in (-16, -4, 1, 12):
            self.assert_codes(values, 16, exponent)

    def test_rejects_nonfinite_and_wrong_float_dtype(self):
        for values in (np.array([np.nan], dtype=np.float32), np.array([np.inf], dtype=np.float32),
                       np.zeros(1, dtype=np.float64), np.zeros(1, dtype=np.int64)):
            with self.assertRaises(ValueError):
                evaluator.quantize_float32(values, 16, 0)

    def test_rejects_unsupported_exponent_and_width(self):
        values = np.zeros(1, dtype=np.float32)
        for exponent in (-65, 65, True, 0.5):
            with self.assertRaises(ValueError):
                evaluator.quantize_float32(values, 16, exponent)
        for bits in (8, 48, True):
            with self.assertRaises(ValueError):
                evaluator.quantize_float32(values, bits, 0)


class MatrixTests(unittest.TestCase):
    def test_int64_matmul_matches_canonical_at_extreme_ranges(self):
        x = np.full((1, 99, 64), -32768, dtype=np.int64)
        w = np.full((64, 256), -32768, dtype=np.int64)
        bias = np.full((256,), (1 << 39) - 1, dtype=np.int64)
        actual = evaluator.integer_linear(x, w, bias)
        expected = fixed.linear99x64x256(x[0].tolist(), w.tolist(), bias.tolist())
        self.assertTrue(np.array_equal(actual[0], np.array(expected, dtype=np.int64)))
        self.assertEqual(int(actual[0, 0, 0]), (1 << 39) - 1 + 64 * (1 << 30))

    def test_negative_extremes_and_k_order(self):
        rng = np.random.RandomState(7)
        x = rng.randint(-32768, 32768, size=(1, 99, 64)).astype(np.int64)
        w = rng.randint(-32768, 32768, size=(64, 256)).astype(np.int64)
        bias = np.full((256,), -(1 << 39), dtype=np.int64)
        actual = evaluator.integer_linear(x, w, bias)
        expected = fixed.linear99x64x256(x[0].tolist(), w.tolist(), bias.tolist())
        self.assertTrue(np.array_equal(actual[0], np.array(expected, dtype=np.int64)))

    def test_rejects_bad_shape_type_and_range(self):
        x = np.zeros((1, 99, 64), dtype=np.int64)
        w = np.zeros((64, 256), dtype=np.int64)
        bias = np.zeros(256, dtype=np.int64)
        for values in (x[0], x.astype(np.int16), np.full_like(x, 32768)):
            with self.assertRaises(ValueError):
                evaluator.integer_linear(values, w, bias)
        with self.assertRaises(ValueError):
            evaluator.integer_linear(x, w, np.full_like(bias, 1 << 39))


class StatisticsTests(unittest.TestCase):
    def test_error_sums_matches_canonical_reference(self):
        rng = np.random.RandomState(3)
        reference = rng.normal(size=(2, 99, 256)).astype(np.float32)
        decoded = reference.astype(np.float64) + rng.normal(size=reference.shape) * 1e-4
        actual = evaluator.error_sums(decoded, reference)
        sums = fixed.ErrorSums()
        for i in range(2):
            sums.update(decoded[i].ravel().tolist(), reference[i].ravel().tolist())
        total = evaluator.aggregate(actual["sse"].tolist(), actual["reference_energy"].tolist(), 2)
        expected = sums.report()
        self.assertAlmostEqual(total["nrmse"], expected["nrmse"], places=16)
        self.assertAlmostEqual(total["sum_error_sq"], expected["sum_error_sq"], places=14)

    def test_aggregation_is_not_mean_sample_nrmse(self):
        result = evaluator.aggregate([1.0, 1.0], [1.0, 10000.0], 2)
        self.assertAlmostEqual(result["nrmse"], (2.0 / 10001.0) ** 0.5)
        self.assertGreater(abs(result["nrmse"] - (1.0 + 0.01) / 2), 0.4)

    def test_zero_reference_floor_and_invalid_samples(self):
        reference = np.zeros((1, 99, 256), dtype=np.float32)
        result = evaluator.error_sums(np.full(reference.shape, 1e-10), reference)
        self.assertAlmostEqual(float(result["nrmse"][0]), 0.01)
        for arguments in (([], [], 0), ([1.0], [], 1), ([float("nan")], [0.0], 1)):
            with self.assertRaises(ValueError):
                evaluator.aggregate(*arguments)
        with self.assertRaises(ValueError):
            evaluator.error_sums(reference[0], reference[0])

    def test_completed_evaluation_with_failed_precision_gate_exits_nonzero(self):
        report = {"status": "FAIL", "evaluation_completed": True,
                  "dataset": {"evaluated_samples": 1}, "max_layer_nrmse": 0.04,
                  "max_sample_layer_nrmse": 0.04, "development_3_percent_gate": "FAIL"}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            with mock.patch.object(evaluator, "evaluate", return_value=report):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = evaluator.main(["--output", str(output)])
            self.assertEqual(code, 1)
            written = json.loads((output / "result.json").read_text())
            self.assertEqual(written["status"], "FAIL")
            self.assertEqual(written["exit_code"], 1)


if __name__ == "__main__":
    unittest.main()
