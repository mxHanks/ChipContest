"""xu: independent fixture compatibility and external-inference input guards."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/model"))
from model import fixed16_acc48 as fixed
import export_kwt as exporter
import evaluate_kwt_dataset as evaluator


class ExistingFixtureTests(unittest.TestCase):
    def test_all_twelve_existing_layers_match_canonical_integer_model(self):
        fixture = ROOT / "tests/e203/vectors"
        manifest = json.loads((fixture / "kwt-silence-v1.json").read_text())
        archive = fixture / "kwt-silence-v1.tar.gz"
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
                         manifest["archive_sha256"])
        outputs = 0
        with tarfile.open(str(archive), "r:gz") as stream:
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                for layer_id in range(12):
                    arrays = {}
                    for name, bits, count in (("x", 16, 6336), ("w", 16, 16384),
                                              ("bias", 40, 256), ("y", 48, 25344)):
                        key = "layer_{:02d}/{}.mem".format(layer_id, name)
                        data = stream.extractfile(key).read()
                        self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["files"][key])
                        path = directory / (name + ".mem")
                        path.write_bytes(data)
                        arrays[name] = fixed.read_hex_mem(path, bits, count)
                    x = [arrays["x"][i:i + 64] for i in range(0, 6336, 64)]
                    w = [arrays["w"][i:i + 256] for i in range(0, 16384, 256)]
                    actual = fixed.linear99x64x256(x, w, arrays["bias"])
                    flat = [value for row in actual for value in row]
                    self.assertEqual(flat, arrays["y"], "layer " + str(layer_id))
                    emitted = directory / "computed-y.mem"
                    fixed.write_hex_mem(emitted, flat, 48)
                    self.assertEqual(emitted.read_bytes(), (directory / "y.mem").read_bytes())
                    outputs += len(flat)
        self.assertEqual(outputs, 304128)

    def test_frozen_scale_source_and_checkpoint_identity(self):
        contract = json.loads(exporter.SCALE_CONTRACT.read_text())
        source = json.loads(exporter.SOURCE_MANIFEST.read_text())
        fixture_record = contract["source_fixture"]
        fixture_path = ROOT / fixture_record["path"]
        self.assertEqual(hashlib.sha256(fixture_path.read_bytes()).hexdigest(), fixture_record["sha256"])
        fixture = json.loads(fixture_path.read_text())
        self.assertEqual(source["commit"], exporter.COMMIT)
        self.assertEqual(contract["source_commit"], exporter.COMMIT)
        self.assertEqual(len(source["files"]), 104)
        pinned = {item["path"]: item for item in source["files"]}
        for checkpoint in contract["checkpoint"]:
            self.assertEqual(pinned[checkpoint["path"]], checkpoint)
        for layer, original in zip(contract["layers"], fixture["layers"]):
            self.assertEqual(layer["scales"], original["scales"])
            self.assertEqual(layer["scales"],
                             {"x_exp": -11, "w_exp": -16, "bias_exp": -27, "y_exp": -27})
            selection = layer["scale_selection"]
            x_exp = exporter.choose_scale_exp(selection["x_bound"])
            w_exp = exporter.choose_scale_exp(selection["w_maxabs"])
            exporter.validate_static_scales(layer["layer_id"], x_exp, w_exp,
                                            selection["x_bound"], selection["w_maxabs"])
            with self.assertRaisesRegex(ValueError, "scales differ"):
                exporter.validate_static_scales(layer["layer_id"], x_exp + 1, w_exp,
                                                selection["x_bound"], selection["w_maxabs"])
        with self.assertRaises(AttributeError):
            fixed.Fixed16Scales(-11, -16).x_exp = 0


class InferenceInputTests(unittest.TestCase):
    def test_canonical_loader_records_actual_repository_module_identity(self):
        module, identity = exporter.load_canonical_model()
        path = ROOT / "model/fixed16_acc48.py"
        self.assertEqual(Path(module.__file__).resolve(), path)
        self.assertEqual(identity, {"module_name": module.__name__, "file": str(path),
                                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        self.assertEqual(module.encode_scalar(0.5, 16, 0), 0)

    def test_external_model_name_cannot_replace_canonical_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            source, data, output = (parent / name for name in ("source", "data", "output"))
            for directory in (source, data, output):
                directory.mkdir()
            marker = parent / "external-model-loaded"
            (source / "model.py").write_text(
                "from pathlib import Path\nPath({!r}).write_text('loaded')\n"
                "raise RuntimeError('EXTERNAL_MODEL_IMPORTED')\n".format(str(marker)))
            (source / "kws_streaming.py").write_text(
                "raise RuntimeError('UPSTREAM_IMPORT_REACHED')\n")
            inventory = data / "source-files.json"
            inventory.write_text("[]\n")
            (data / "preparation.json").write_text(json.dumps({
                "status": "PASS", "archive_sha256":
                "af14739ee7dc311471de98f5f9d2c9191b18aedfe957f4a6ff791c709868ff58",
                "inventory": {"sha256": evaluator.digest(inventory)}}))
            fake_tf = SimpleNamespace(config=SimpleNamespace(threading=mock.Mock()))
            args = SimpleNamespace(source=source, output=output, data=data)
            for name, run in (("export", lambda: exporter.run_export(source, output, None)),
                              ("evaluate", lambda: evaluator.evaluate(args, {}))):
                with self.subTest(entry_point=name), mock.patch.dict(sys.modules), \
                        mock.patch.object(sys, "path", list(sys.path)), \
                        mock.patch.object(exporter, "source_inventory", return_value={}), \
                        mock.patch.object(exporter, "load_inference_dependencies", return_value=(None, fake_tf)):
                    for key in list(sys.modules):
                        if key == "model" or key.startswith("model.") or key.startswith("kws_streaming"):
                            del sys.modules[key]
                    with self.assertRaisesRegex(RuntimeError, "UPSTREAM_IMPORT_REACHED"):
                        run()
                    self.assertFalse(marker.exists())

    def test_external_source_hash_length_and_path_guards(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            path = source / "LICENSE.txt"
            path.write_bytes(b"pinned-source\n")
            manifest = source / "source.json"
            record = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "bytes": path.stat().st_size}
            data = {"status": "PASS", "commit": exporter.COMMIT, "files": [record]}
            manifest.write_text(json.dumps(data))
            with mock.patch.object(exporter, "SOURCE_MANIFEST", manifest):
                verified = exporter.source_inventory(source)
                self.assertEqual(verified["files"], [record])
                path.write_bytes(b"wrong-source!\n")
                with self.assertRaisesRegex(ValueError, "differ from pinned provenance"):
                    exporter.source_inventory(source)
                path.unlink()
                with self.assertRaisesRegex(exporter.MissingInferenceInput, "missing pinned"):
                    exporter.source_inventory(source)
                record["path"] = "../escape"
                manifest.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, "unsafe source manifest path"):
                    exporter.source_inventory(source)

    def test_server_python_requires_separate_legacy_inference_environment(self):
        with mock.patch.object(sys, "version_info", (3, 6, 8)):
            with self.assertRaisesRegex(exporter.MissingInferenceInput, "Python 3.8.20"):
                exporter.load_inference_dependencies()

    def test_missing_sources_write_blocked_reports_and_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            for name, report_name in (("export_kwt.py", "manifest.json"),
                                      ("evaluate_kwt_dataset.py", "result.json")):
                output = parent / name
                command = [sys.executable, str(ROOT / "tools/model" / name),
                           "--source", str(parent / "missing-source"), "--output", str(output)]
                if name == "evaluate_kwt_dataset.py":
                    command.extend(["--data", str(parent / "missing-data")])
                result = subprocess.run(command, cwd=temporary, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                report = json.loads((output / report_name).read_text())
                self.assertEqual(report["status"], "BLOCKED")
                self.assertFalse(report["inference_executed"])
                self.assertFalse(report["evaluation_completed"])
                self.assertIn("missing pinned KWT source", report["error"])

    def test_completed_failed_precision_gate_exits_nonzero(self):
        report = {"status": "FAIL", "evaluation_completed": True,
                  "dataset": {"evaluated_samples": 1}, "max_layer_nrmse": 0.04,
                  "max_sample_layer_nrmse": 0.04}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            with mock.patch.object(evaluator, "evaluate", return_value=report):
                with mock.patch("builtins.print"):
                    result = evaluator.main(["--source", temporary, "--data", temporary,
                                             "--output", str(output)])
            self.assertEqual(result, 1)
            written = json.loads((output / "result.json").read_text())
            self.assertEqual(written["status"], "FAIL")
            self.assertEqual(written["exit_code"], 1)

    def test_inference_aggregation_matches_canonical_energy_rule(self):
        result = evaluator.aggregate([1.0, 1.0], [1.0, 10000.0], 2)
        self.assertAlmostEqual(result["nrmse"], (2.0 / 10001.0) ** 0.5)
        self.assertGreater(abs(result["nrmse"] - (1.0 + 0.01) / 2), 0.4)
        for arguments in (([], [], 0), ([1.0], [], 1), ([float("nan")], [0.0], 1)):
            with self.assertRaises(ValueError):
                evaluator.aggregate(*arguments)


if __name__ == "__main__":
    unittest.main(verbosity=2)
