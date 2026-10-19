"""Contract and error-aggregation tests; no external packages or KWT data needed."""

from fractions import Fraction
import math
from pathlib import Path
import random
import tempfile
import unittest

from model.fixed16_acc48 import (
    BIAS_BITS, COLS, INNER, LAYERS, ROWS, Y_BITS, ErrorSums, Fixed16Scales,
    LayerNRMSE, LayerParameters, checked_signed, decode_exact, decode_output,
    decode_scalar, dot64, encode_scalar, linear99x64x256, quantize_linear_inputs,
    read_hex_mem, validate_layer_set, write_hex_mem, write_linear_mem_vectors,
)


def zeros(rows, cols):
    return [[0] * cols for _ in range(rows)]


class EncodingTests(unittest.TestCase):
    def test_ties_to_even_both_signs(self):
        cases = {Fraction(1, 2): 0, Fraction(3, 2): 2, Fraction(5, 2): 2,
                 Fraction(-1, 2): 0, Fraction(-3, 2): -2, Fraction(-5, 2): -2}
        for value, expected in cases.items():
            self.assertEqual(encode_scalar(value, 16, 0), expected)
            self.assertEqual(encode_scalar(value / 4, 16, -2), expected)

    def test_float_neighbors_and_saturation(self):
        # Adjacent binary64 values, also usable on Python 3.8 (no nextafter).
        self.assertEqual(encode_scalar(float.fromhex("0x1.3ffffffffffffp+1"), 16, 0), 2)
        self.assertEqual(encode_scalar(float.fromhex("0x1.4000000000001p+1"), 16, 0), 3)
        for value, expected in [(32767.5, 32767), (32766.5, 32766),
                                (-32768.5, -32768), (-32767.5, -32768),
                                (10**100, 32767), (-10**100, -32768)]:
            self.assertEqual(encode_scalar(value, 16, 0), expected)

    def test_explicit_power_of_two_scaling(self):
        scales = Fixed16Scales(-6, -7)
        self.assertEqual(scales.y_exp, -13)
        self.assertEqual(decode_exact(-3, 16, -2), Fraction(-3, 4))
        self.assertEqual(decode_scalar(17, 48, 3), 136.0)
        for bits in (16, 40, 48):
            for code in (-(1 << (bits - 1)), -1, 0, 1, (1 << (bits - 1)) - 1):
                self.assertEqual(encode_scalar(decode_exact(code, bits, -12), bits, -12), code)

    def test_reject_invalid_and_nonfinite_values(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                encode_scalar(value, 16, -5)
        for value in (True, "1.0", 1j):
            with self.assertRaises(TypeError):
                encode_scalar(value, 16, 0)
        for exponent in (True, 1.5, "2"):
            with self.assertRaises(TypeError):
                Fixed16Scales(exponent, 0)
        with self.assertRaises(ValueError):
            decode_scalar(1, 16, 2000)
        with self.assertRaises(ValueError):
            decode_scalar(1, 16, -2000)
        with self.assertRaises(ValueError):
            checked_signed(32768, 16)
        with self.assertRaises(TypeError):
            checked_signed(1.0, 16)


class IntegerLinearTests(unittest.TestCase):
    def test_dot_extremes_bias_and_cancellation(self):
        max_bias, min_bias = (1 << 39) - 1, -(1 << 39)
        self.assertEqual(dot64([-32768] * 64, [-32768] * 64, max_bias),
                         (1 << 36) + max_bias)
        self.assertEqual(dot64([-32768] * 64, [32767] * 64, min_bias),
                         -64 * 32768 * 32767 + min_bias)
        self.assertEqual(dot64([32767] * 64, [1, -1] * 32, -123), -123)
        self.assertEqual(dot64([0] * 64, [-32768] * 64, min_bias), min_bias)
        self.assertLess((1 << 39) + (1 << 36), 1 << 47)

    def test_random_dot_matches_independent_sum(self):
        rng = random.Random(0xF1648)
        for _ in range(100):
            x = [rng.randrange(-32768, 32768) for _ in range(64)]
            w = [rng.randrange(-32768, 32768) for _ in range(64)]
            bias = rng.randrange(-(1 << 39), 1 << 39)
            self.assertEqual(dot64(x, w, bias), bias + sum(a * b for a, b in zip(x, w)))

    def test_dot_rejects_wrong_lengths_or_ranges(self):
        for x, w, bias, error in [([0] * 63, [0] * 64, 0, ValueError),
                                  ([0] * 64, [0] * 65, 0, ValueError),
                                  ([32768] * 64, [0] * 64, 0, ValueError),
                                  ([0] * 64, [0] * 64, 1 << 39, ValueError),
                                  ([True] * 64, [0] * 64, 0, TypeError)]:
            with self.assertRaises(error):
                dot64(x, w, bias)

    def test_full_matrix_orientation_and_last_row_column(self):
        x, w = zeros(ROWS, INNER), zeros(INNER, COLS)
        for r in range(ROWS):
            x[r][r % INNER] = r + 1
        for k in range(INNER):
            for c in range(COLS):
                w[k][c] = 3 * k - c
        bias = [c - 120 for c in range(COLS)]
        output = linear99x64x256(x, w, bias)
        expected = [[bias[c] + (r + 1) * (3 * (r % INNER) - c)
                     for c in range(COLS)] for r in range(ROWS)]
        self.assertEqual(output, expected)
        self.assertEqual(output[98][255], 135 + 99 * (3 * 34 - 255))

    def test_full_matrix_deterministic_random_selected_outputs(self):
        rng = random.Random(2374097)
        x = [[rng.randrange(-32768, 32768) for _ in range(INNER)] for _ in range(ROWS)]
        w = [[rng.randrange(-32768, 32768) for _ in range(COLS)] for _ in range(INNER)]
        bias = [rng.randrange(-(1 << 39), 1 << 39) for _ in range(COLS)]
        y = linear99x64x256(x, w, bias)
        for r in (0, 1, 63, 64, 98):
            for c in (0, 1, 127, 128, 255):
                self.assertEqual(y[r][c], bias[c] + sum(x[r][k] * w[k][c] for k in range(INNER)))

    def test_strict_full_shapes_and_values(self):
        x, w, bias = zeros(ROWS, INNER), zeros(INNER, COLS), [0] * COLS
        for bad_x, bad_w, bad_b in [(x[:-1], w, bias),
                                   (x, list(zip(*w)), bias),
                                   (x, w, bias[:-1]),
                                   (x[:98] + [[0] * 63], w, bias)]:
            with self.assertRaises(ValueError):
                linear99x64x256(bad_x, bad_w, bad_b)
        x[-1][-1] = 0.0
        with self.assertRaises(TypeError):
            linear99x64x256(x, w, bias)

    def test_quantize_decode_bias_product_scale(self):
        scales = Fixed16Scales(-2, -3)
        x, w, b = quantize_linear_inputs([[0.5] * INNER for _ in range(ROWS)],
                                         [[0.25] * COLS for _ in range(INNER)],
                                         [-0.125] * COLS, scales)
        self.assertEqual((x[0][0], w[0][0], b[0]), (2, 2, -4))
        y = linear99x64x256(x, w, b)
        self.assertEqual(y[-1][-1], 252)
        self.assertEqual(decode_output(y, scales)[-1][-1], 7.875)

    def test_layer_parameters_are_copied_and_independent(self):
        w, b = zeros(INNER, COLS), [0] * COLS
        layers = []
        for layer_id in range(LAYERS):
            b[0] = layer_id
            layers.append(LayerParameters(layer_id, w, b, Fixed16Scales(-10, -11)))
        w[0][0], b[0] = 999, 999
        self.assertEqual([p.bias[0] for p in layers], list(range(LAYERS)))
        self.assertTrue(all(p.weights[0][0] == 0 for p in layers))
        ordered = validate_layer_set(reversed(layers))
        self.assertEqual([p.layer_id for p in ordered], list(range(LAYERS)))
        self.assertEqual(ordered[11].compute(zeros(ROWS, INNER))[98][0], 11)
        with self.assertRaises(ValueError):
            validate_layer_set(layers[:-1] + [layers[0]])


class NRMSETests(unittest.TestCase):
    def test_aggregate_energy_not_mean_sample_nrmse(self):
        stats = ErrorSums()
        stats.update([2.0], [1.0])
        stats.update([100.0], [100.0])
        report = stats.report()
        self.assertAlmostEqual(report["nrmse"], math.sqrt(1.0 / 10001.0))
        self.assertNotAlmostEqual(report["nrmse"], 0.5)
        self.assertEqual((report["count"], report["samples"]), (2, 2))

    def test_denominator_floor_and_empty_rejection(self):
        stats = ErrorSums()
        with self.assertRaises(ValueError):
            stats.report()
        with self.assertRaises(ValueError):
            stats.update([], [])
        stats.update([1e-10], [0.0])
        self.assertAlmostEqual(stats.report()["nrmse"], 0.01)
        tiny = ErrorSums()
        tiny.update([2e-10], [1e-10])
        self.assertAlmostEqual(tiny.report()["nrmse"], 0.01)

    def test_invalid_sample_does_not_mutate_prior_statistics(self):
        stats = ErrorSums()
        stats.update([1.0], [1.0])
        before = stats.report()
        for actual, reference in [([1.0, math.nan], [1.0, 2.0]),
                                   ([math.inf], [0.0]), ([0.0], [-math.inf]),
                                   ([1e308], [-1e308]), ([1], [1, 2])]:
            with self.assertRaises(ValueError):
                stats.update(actual, reference)
            self.assertEqual(stats.report(), before)

    def test_per_layer_full_shape_all_layers_and_maximum(self):
        stats = LayerNRMSE()
        reference = [[1.0] * COLS for _ in range(ROWS)]
        for layer in range(LAYERS):
            actual = [[1.0 + layer * 0.001] * COLS for _ in range(ROWS)]
            stats.update(layer, actual, reference)
        report = stats.report()
        self.assertAlmostEqual(report["max_layer_nrmse"], 0.011)
        self.assertTrue(report["within_3pct_for_recorded_samples"])
        self.assertEqual(report["layers"]["11"]["count"], ROWS * COLS)

    def test_missing_layer_or_wrong_shape_not_accepted(self):
        stats = LayerNRMSE()
        with self.assertRaises(ValueError):
            stats.report(False)
        with self.assertRaises(ValueError):
            stats.update(0, [], [])
        out = zeros(ROWS, COLS)
        stats.update(0, out, out)
        with self.assertRaises(ValueError):
            stats.report()
        self.assertFalse(stats.report(False)["within_3pct_for_recorded_samples"])
        for layer in (-1, 12):
            with self.assertRaises(ValueError):
                stats.update(layer, out, out)


class MemoryTests(unittest.TestCase):
    def test_hex_round_trip_extremes_and_bad_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.mem"
            for bits in (16, BIAS_BITS, Y_BITS):
                values = [-(1 << (bits - 1)), -1, 0, 1, (1 << (bits - 1)) - 1]
                info = write_hex_mem(path, values, bits)
                self.assertEqual(info["count"], 5)
                self.assertEqual(read_hex_mem(path, bits, 5), values)
            for bad in ("", "xxx\n", "10000\n", "000\n", "0000 0000\n"):
                path.write_text(bad)
                with self.assertRaises(ValueError):
                    read_hex_mem(path, 16)
            path.write_text("ff\n")
            with self.assertRaises(ValueError):
                read_hex_mem(path, 5)

    def test_full_vector_export_layout_and_hash(self):
        import hashlib
        x, w, bias = zeros(ROWS, INNER), zeros(INNER, COLS), [0] * COLS
        x[98][63], w[63][255], bias[255] = -32768, -32768, -1
        with tempfile.TemporaryDirectory() as tmp:
            manifest = write_linear_mem_vectors(tmp, x, w, bias, Fixed16Scales(-9, -8))
            self.assertEqual(manifest["scales"]["y_exp"], -17)
            for metadata in manifest["files"].values():
                self.assertEqual(hashlib.sha256(Path(metadata["path"]).read_bytes()).hexdigest(),
                                 metadata["sha256"])
            self.assertEqual(read_hex_mem(Path(tmp) / "x.mem", 16, ROWS * INNER)[-1], -32768)
            self.assertEqual(read_hex_mem(Path(tmp) / "w.mem", 16, INNER * COLS)[-1], -32768)
            y = read_hex_mem(Path(tmp) / "y.mem", 48, ROWS * COLS)
            self.assertEqual(y[-1], (1 << 30) - 1)
            self.assertEqual(y[255], -1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
