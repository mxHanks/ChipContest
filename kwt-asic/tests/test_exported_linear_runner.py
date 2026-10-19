"""Reject malformed exports and stale/incorrect goldens before HDL compilation."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("exported_linear_runner", ROOT / "scripts/verify/run_exported_linear.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
MODEL = RUNNER.LINEAR.load_module("export_runner_test_model", ROOT / "model/fixed16_acc48.py")


def structural_manifest():
    # A structural fixture only, never labelled as data from real KWT weights.
    return {"schema": "kwt_ffn_export_v1", "status": "PASS", "format": RUNNER.FORMAT,
            "shape": copy.deepcopy(RUNNER.SHAPE), "scope": "unit-test structure only",
            "end_marker": "KWT_EXPORT_COMPLETED", "restoration": {"status": "PASS"},
            "source": {"commit": RUNNER.PINNED_COMMIT},
            "input": {"kind": "synthetic_zero_silence_smoke", "sample_rate": 16000, "channels": 1, "samples": 16000},
            "layers": [{"layer_id": i, "shape": copy.deepcopy(RUNNER.SHAPE),
                        "files": {role: {} for role in RUNNER.MEMORY_SPECS},
                        "scales": {"x_exp": -12, "w_exp": -11, "bias_exp": -23, "y_exp": -23},
                        "checkpoint_keys": {role: f"test-layer-{i}/{role}" for role in ("kernel", "bias", "gamma", "beta")},
                        "float_tensors": {}} for i in range(12)]}


class ExportStructureTests(unittest.TestCase):
    def test_valid_structure_preserves_twelve_ordered_layers(self):
        self.assertEqual(len(RUNNER.validate_manifest_structure(structural_manifest())), 12)

    def test_rejects_duplicate_or_reordered_layers(self):
        manifest = structural_manifest()
        manifest["layers"][11]["layer_id"] = 10
        with self.assertRaisesRegex(ValueError, "order 0..11"):
            RUNNER.validate_manifest_structure(manifest)

    def test_rejects_incomplete_or_wrong_format_export(self):
        for key, value in (("format", "fp32"), ("status", "FAIL"), ("schema", "untrusted_unknown_v1")):
            manifest = structural_manifest()
            manifest[key] = value
            with self.assertRaises(ValueError):
                RUNNER.validate_manifest_structure(manifest)
        manifest = structural_manifest()
        manifest["layers"].pop()
        with self.assertRaises(ValueError):
            RUNNER.validate_manifest_structure(manifest)

    def test_rejects_transposed_shape_and_misaligned_bias_scale(self):
        manifest = structural_manifest()
        manifest["shape"]["w"] = [256, 64]
        with self.assertRaises(ValueError):
            RUNNER.validate_manifest_structure(manifest)
        manifest = structural_manifest()
        manifest["layers"][0]["scales"]["bias_exp"] = -12
        with self.assertRaisesRegex(ValueError, "product scale"):
            RUNNER.validate_manifest_structure(manifest)

    def test_rejects_missing_sample_or_wrong_source_commit(self):
        manifest = structural_manifest()
        manifest["input"] = {}
        with self.assertRaises(ValueError):
            RUNNER.validate_manifest_structure(manifest)
        manifest = structural_manifest()
        manifest["source"]["commit"] = "237e4097"
        with self.assertRaises(ValueError):
            RUNNER.validate_manifest_structure(manifest)


class ExportMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, payload, bits=16, count=6336):
        path = self.root / "x.mem"
        path.write_bytes(payload)
        return {"path": "x.mem", "bits": bits, "count": count, "sha256": hashlib.sha256(payload).hexdigest()}

    def test_reads_signed_extreme_exactly(self):
        metadata = self.write(b"8000\n" + b"0000\n" * 6334 + b"7fff\n")
        values, _, _ = RUNNER.read_memory(self.root, metadata, "x")
        self.assertEqual((values[0], values[-1], len(values)), (-32768, 32767, 6336))

    def test_rejects_stale_hash(self):
        metadata = self.write(b"0000\n" * 6336)
        (self.root / "x.mem").write_bytes(b"0001\n" * 6336)
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            RUNNER.read_memory(self.root, metadata, "x")

    def test_rejects_short_unknown_and_wrong_width_images(self):
        for payload in (b"0000\n" * 6335, b"xxxx\n" * 6336, b"00000\n" * 6336):
            with self.assertRaises(ValueError):
                RUNNER.read_memory(self.root, self.write(payload), "x")
        with self.assertRaises(ValueError):
            RUNNER.read_memory(self.root, self.write(b"0000\n" * 6336, bits=40), "x")

    def test_rejects_absolute_traversal_and_symlink_members(self):
        for name in ("/tmp/x.mem", "../x.mem", "layer/../../x.mem", "layer\\x.mem"):
            with self.assertRaises(ValueError):
                RUNNER.relative_file(self.root, name)
        (self.root / "original").write_text("0")
        (self.root / "linked").symlink_to(self.root / "original")
        with self.assertRaises(ValueError):
            RUNNER.relative_file(self.root, "linked")

    def test_recomputes_goldens_and_rejects_one_changed_word(self):
        arrays = {"x": [0] * 6336, "w": [0] * 16384, "bias": [-3] * 256, "y": [-3] * 25344}
        arrays["x"][-1] = -32768
        arrays["w"][-1] = -32768
        arrays["y"][-1] = (1 << 30) - 3
        RUNNER.verify_layer_golden(arrays, MODEL, 11)
        arrays["y"][-1] += 1
        with self.assertRaisesRegex(ValueError, "layer=11 index=25343"):
            RUNNER.verify_layer_golden(arrays, MODEL, 11)


class SourceRelocationTests(unittest.TestCase):
    def test_explicit_override_keeps_inventory_and_byte_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            relocated = project / "relocated-source"
            source_payloads = {
                "models_data_v2_12_labels/kwt1/best_weights.index": b"test checkpoint index",
                "models_data_v2_12_labels/kwt1/best_weights.data-00000-of-00001": b"test checkpoint data",
                "README.md": b"unit-test source fixture, not real KWT data",
            }
            inventory = []
            for name, payload in source_payloads.items():
                path = relocated / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
                inventory.append({"path": name, "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)})
            provenance = project / "docs/runs/kwt-source-manifest.json"
            provenance.parent.mkdir(parents=True)
            provenance.write_text(json.dumps({"status": "PASS", "commit": RUNNER.PINNED_COMMIT,
                                              "files": [{**item, "path": RUNNER.PINNED_COMMIT + "/" + item["path"]}
                                                        for item in inventory]}))
            implementation = []
            for name in ("scripts/model/export_kwt.py", "model/fixed16_acc48.py"):
                path = project / name
                path.parent.mkdir(parents=True, exist_ok=True)
                payload = b"unit-test implementation fixture"
                path.write_bytes(payload)
                implementation.append({"path": name, "sha256": hashlib.sha256(payload).hexdigest()})
            parameters = [{"name": "unit-test parameter"}]
            manifest = {"source": {"source_directory": str(project / "missing-original-source"),
                                   "files": inventory, "inventory_sha256": RUNNER.canonical_hash(inventory),
                                   "checkpoint": inventory[:2],
                                   "provenance_manifest_sha256": hashlib.sha256(provenance.read_bytes()).hexdigest()},
                        "implementation": implementation,
                        "restoration": {"parameters": parameters, "model_variables": 1,
                                        "parameter_set_sha256": RUNNER.canonical_hash(parameters)}}
            original_manifest = copy.deepcopy(manifest)
            with mock.patch.object(RUNNER, "ROOT", project):
                with self.assertRaisesRegex(ValueError, "existing absolute source directory"):
                    RUNNER.validate_source(manifest)
                records = RUNNER.validate_source(manifest, source_root=relocated)
                for name in source_payloads:
                    self.assertIn(str(relocated / name), [item["path"] for item in records])
                self.assertEqual(manifest, original_manifest)
                (relocated / "README.md").write_bytes(b"modified source bytes")
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    RUNNER.validate_source(manifest, source_root=relocated)
                (relocated / "README.md").write_bytes(source_payloads["README.md"])
                manifest["source"]["inventory_sha256"] = "0" * 64
                with self.assertRaisesRegex(ValueError, "source inventory hash mismatch"):
                    RUNNER.validate_source(manifest, source_root=relocated)


if __name__ == "__main__":
    unittest.main()
