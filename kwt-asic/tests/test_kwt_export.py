"""Exporter safety/selection tests; no TensorFlow install needed for these."""
import importlib.util
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("export_kwt", ROOT / "scripts/model/export_kwt.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def inventory():
    result = {}
    for layer in range(12):
        prefix = "layer_with_weights-0/enc_layers/%d/" % layer
        for name, shape in (("ffn/layer_with_weights-0/kernel", [64, 256]),
                            ("ffn/layer_with_weights-0/bias", [256]),
                            ("layernorm1/gamma", [64]), ("layernorm1/beta", [64])):
            result[prefix + name + exporter.SUFFIX] = shape
    return result


class KWTExportTests(unittest.TestCase):
    def test_power_of_two_scale_exact_boundary(self):
        for exponent in (-80, -20, -1, 0, 18, 80):
            bound = math.ldexp(32767.0, exponent)
            self.assertEqual(exporter.choose_scale_exp(bound), exponent)
            self.assertEqual(exporter.choose_scale_exp(math.ldexp(32767.0 + 2**-38, exponent)), exponent + 1)
            self.assertEqual(exporter.choose_scale_exp(math.ldexp(32767.0 - 2**-38, exponent)), exponent)

    def test_scale_handles_tiny_zero_and_invalid_bounds(self):
        self.assertEqual(exporter.choose_scale_exp(0), 0)
        self.assertEqual(exporter.choose_scale_exp(float.fromhex("0x0.0000000000001p-1022")), -1088)
        for bound in (-1, math.inf, math.nan):
            with self.assertRaises(ValueError):
                exporter.choose_scale_exp(bound)

    def test_layernorm_bound_uses_only_parameters(self):
        self.assertEqual(exporter.layernorm_bound([-2] * 64, [0.5] * 64), 16.5)
        with self.assertRaises(ValueError):
            exporter.layernorm_bound([1] * 63, [0] * 64)
        with self.assertRaises(ValueError):
            exporter.layernorm_bound([math.nan] * 64, [0] * 64)

    def test_exact_checkpoint_layer_order_and_ignores_optimizer_slots(self):
        shapes = inventory()
        original = next(iter(shapes))
        shapes[original.replace(exporter.SUFFIX, "/.OPTIMIZER_SLOT/optimizer/m" + exporter.SUFFIX)] = [64, 256]
        layers = exporter.select_checkpoint_layers(shapes)
        self.assertEqual(len(layers), 12)
        for i, layer in enumerate(layers):
            self.assertIn("/enc_layers/%d/" % i, layer["kernel"])
            self.assertNotIn("OPTIMIZER_SLOT", layer["kernel"])

    def test_missing_wrong_shape_and_duplicate_checkpoint_layers_rejected(self):
        for mode in ("missing", "shape", "duplicate"):
            shapes = inventory()
            key = next(iter(shapes))
            if mode == "missing":
                del shapes[key]
            elif mode == "shape":
                shapes[key] = [256, 64]
            else:
                shapes.update({k.replace("layer_with_weights-0/enc_layers", "layer_with_weights-1/enc_layers"): v
                               for k, v in list(shapes.items())})
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                exporter.select_checkpoint_layers(shapes)

    def test_clipping_counts_rne_range_not_just_float_range(self):
        self.assertEqual(exporter.clipping_count([32767.49, -32768.5, 0.5], 16, 0), 0)
        self.assertEqual(exporter.clipping_count([32767.5, -32768.5001], 16, 0), 2)
        self.assertEqual(exporter.clipping_count([16383.75], 16, -1), 1)


if __name__ == "__main__":
    unittest.main()
