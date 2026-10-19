#!/usr/bin/env python3
"""Restore pinned KWT-1 and export the 12 real FFN inputs for a smoke waveform.

Run with the dedicated .venv-kwt interpreter. This is not a Speech Commands
validation-set accuracy run. Scales depend on checkpoint parameters only.
"""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.metadata
import json
import logging
import math
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
import traceback
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "237e4097afd4f6851e0b82f0a8d65c2dfe8eae30"
MODEL_SUBDIR = "models_data_v2_12_labels/kwt1"
SHAPE = {"x": [99, 64], "w": [64, 256], "bias": [256], "y": [99, 256]}
END_MARKER = "KWT_EXPORT_COMPLETED"
SUFFIX = "/.ATTRIBUTES/VARIABLE_VALUE"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def object_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def choose_scale_exp(bound):
    """Smallest integer e with bound <= 32767*2**e; zero uses e=0."""
    bound = float(bound)
    if not math.isfinite(bound) or bound < 0:
        raise ValueError("bound must be finite and nonnegative")
    if bound == 0:
        return 0
    exponent = math.ceil(math.log2(bound) - math.log2(32767))
    # Fraction comparisons eliminate floating log boundary/underflow mistakes.
    exact_bound = Fraction.from_float(bound)

    def capacity(e):
        return 32767 * (Fraction(2**e) if e >= 0 else Fraction(1, 2**-e))

    while capacity(exponent) < exact_bound:
        exponent += 1
    while capacity(exponent - 1) >= exact_bound:
        exponent -= 1
    return exponent


def layernorm_bound(gamma, beta):
    """A parameter-only PostNorm bound, independent of the exported sample."""
    gamma, beta = list(gamma), list(beta)
    if len(gamma) != 64 or len(beta) != 64:
        raise ValueError("LayerNorm gamma/beta must each have 64 elements")
    values = [float(v) for v in gamma + beta]
    if not all(math.isfinite(v) for v in values):
        raise ValueError("nonfinite LayerNorm parameters")
    return 8.0 * max(abs(float(v)) for v in gamma) + max(abs(float(v)) for v in beta)


def select_checkpoint_layers(shapes):
    """Find exact FFN1/LN1 keys; optimizer slots never qualify."""
    pattern = re.compile(r"^(.*)/enc_layers/(\d+)/ffn/layer_with_weights-0/kernel" +
                         re.escape(SUFFIX) + r"$")
    result = {}
    for key in shapes:
        match = pattern.fullmatch(key)
        if not match:
            continue
        prefix, layer_text = match.groups()
        layer_id = int(layer_text)
        if layer_id in result or not 0 <= layer_id < 12:
            raise ValueError("duplicate or unsupported encoder layer")
        base = prefix + "/enc_layers/" + layer_text
        keys = {"kernel": key,
                "bias": base + "/ffn/layer_with_weights-0/bias" + SUFFIX,
                "gamma": base + "/layernorm1/gamma" + SUFFIX,
                "beta": base + "/layernorm1/beta" + SUFFIX}
        expected = {"kernel": [64, 256], "bias": [256], "gamma": [64], "beta": [64]}
        for name, candidate in keys.items():
            if candidate not in shapes or list(shapes[candidate]) != expected[name]:
                raise ValueError("missing or wrong shape: " + candidate)
        result[layer_id] = keys
    if set(result) != set(range(12)):
        raise ValueError("checkpoint must contain exactly 12 FFN1 layers")
    return [result[i] for i in range(12)]


def source_inventory(source):
    """Verify every downloaded source/checkpoint against the existing pinned manifest."""
    provenance = ROOT / "docs/runs/kwt-source-manifest.json"
    manifest = json.loads(provenance.read_text())
    if manifest.get("status") != "PASS" or manifest.get("commit") != COMMIT:
        raise ValueError("missing verified fixed-commit source manifest")
    records = []
    for record in manifest["files"]:
        marker = COMMIT + "/"
        if marker not in record["path"]:
            raise ValueError("unexpected path in source manifest")
        relative = record["path"].split(marker, 1)[1]
        relpath = Path(relative)
        if relpath.is_absolute() or ".." in relpath.parts:
            raise ValueError("unsafe source manifest path")
        path = source / relpath
        digest = sha256(path)
        if digest != record["sha256"]:
            raise ValueError("source bytes differ from pinned provenance: " + relative)
        records.append({"path": relative, "sha256": digest, "bytes": path.stat().st_size})
    if not records:
        raise ValueError("empty source inventory")
    return {"commit": COMMIT, "source_directory": str(source),
            "provenance_manifest_sha256": sha256(provenance),
            "files": records, "inventory_sha256": object_sha256(records),
            "checkpoint": [r for r in records if "/best_weights." in r["path"]]}


def environment_record():
    packages = sorted((d.metadata["Name"], d.version)
                      for d in importlib.metadata.distributions())
    details = {"python": platform.python_version(), "executable": sys.executable,
               "executable_sha256": sha256(Path(sys.executable).resolve()),
               "packages": packages,
               "thread_limits": {k: os.environ[k] for k in
                   ("TF_NUM_INTRAOP_THREADS", "TF_NUM_INTEROP_THREADS", "OMP_NUM_THREADS")},
               "upstream_requested_tensorflow": "2.4.0rc1",
               "tensorflow_fallback": "tensorflow-cpu 2.4.0 release; rc1 unavailable from PyPI",
               "fallback_limit": "Not a claim of byte-identical execution to TensorFlow 2.4.0rc1"}
    details["identity_sha256"] = object_sha256(details)
    return details


def artifact(path, output):
    return {"path": str(Path(path).relative_to(output)), "sha256": sha256(path),
            "bytes": Path(path).stat().st_size}


def clipping_count(values, bits, exponent):
    lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    scale = Fraction(2**exponent) if exponent >= 0 else Fraction(1, 2**-exponent)
    return sum(not lo <= round(Fraction.from_float(float(v)) / scale) <= hi
               for v in values)


def validate_flags(flags):
    requirements = {"num_layers": 12, "d_model": 64, "mlp_dim": 256,
                    "heads": 1, "attention_type": "time", "label_count": 12,
                    "sample_rate": 16000, "desired_samples": 16000,
                    "spectrogram_length": 98, "dct_num_features": 40,
                    "preprocess": "raw", "feature_type": "mfcc_tf"}
    for name, expected in requirements.items():
        if flags.get(name) != expected:
            raise ValueError("unsupported upstream flag: " + name)
    if flags.get("prenorm", False) or flags.get("distill_teacher_json", ""):
        raise ValueError("export requires PostNorm, non-distilled KWT-1")


class WarningCapture(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def verify_all_model_values(model, reader, tf, np, output):
    """Require the entire model's restored parameter set to equal the checkpoint."""
    original = {name for name in reader.get_variable_to_shape_map()
                if name.startswith("layer_with_weights-") and "/.OPTIMIZER_SLOT/" not in name}
    with tempfile.TemporaryDirectory(prefix="restore-proof-", dir=str(output)) as temporary:
        prefix = str(Path(temporary) / "model")
        model.save_weights(prefix)
        saved = tf.train.load_checkpoint(prefix)
        restored = {name for name in saved.get_variable_to_shape_map()
                    if name.startswith("layer_with_weights-") and "/.OPTIMIZER_SLOT/" not in name}
        if restored != original or len(restored) != len(model.weights):
            raise ValueError("restored model parameter keys do not exactly match checkpoint")
        checked = []
        for name in sorted(original):
            before, after = reader.get_tensor(name), saved.get_tensor(name)
            if before.dtype != after.dtype or not np.array_equal(before, after):
                raise ValueError("restored parameter differs from checkpoint: " + name)
            if not np.isfinite(after).all():
                raise ValueError("nonfinite checkpoint parameter: " + name)
            checked.append({"key": name, "shape": list(after.shape),
                            "dtype": str(after.dtype),
                            "raw_value_sha256": hashlib.sha256(after.tobytes(order="C")).hexdigest()})
    return {"status": "PASS", "method": "assert_existing_objects_matched plus exact full-model resave comparison",
            "model_variables": len(checked), "parameters": checked,
            "parameter_set_sha256": object_sha256(checked),
            "ignored": "checkpoint optimizer state and optimizer slots only"}


def run_export(source, output, waveform):
    # Set limits before TensorFlow/NumPy import. This process never uses a GPU.
    for key, value in (("TF_NUM_INTRAOP_THREADS", "2"), ("TF_NUM_INTEROP_THREADS", "1"),
                       ("OMP_NUM_THREADS", "2"), ("CUDA_VISIBLE_DEVICES", "-1")):
        os.environ[key] = value
    sys.dont_write_bytecode = True
    provenance = source_inventory(source)
    import numpy as np
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    if tf.__version__ != "2.4.0" or np.__version__ != "1.19.5":
        raise ValueError("export requires recorded fallback TF 2.4.0 / NumPy 1.19.5 environment")
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(source))
    from model import fixed16_acc48 as fixed
    # Registry-first is the upstream-supported import order; direct importing
    # kws_transformer produces its utils -> models -> kws_transformer cycle.
    from kws_streaming.models import models
    from kws_streaming.models.transformer_utils import KWSTransformer
    from kws_streaming.layers.speech_features import SpeechFeatures

    model_dir = source / MODEL_SUBDIR
    original_flags = json.loads((model_dir / "flags.json").read_text())
    validate_flags(original_flags)
    flags = dict(original_flags)
    for key, value in (("distill_teacher_json", ""), ("prenorm", False), ("approximate_gelu", False)):
        flags.setdefault(key, value)
    flags.update(training=False, train=0, batch_size=1, use_spec_augment=0,
                 use_spec_cutout=0, sp_time_shift_ms=0.0, sp_resample=0.0,
                 time_shift_ms=0.0, resample=0.0, volume_resample=0.0,
                 background_frequency=0.0, background_volume=0.0)
    reader = tf.train.load_checkpoint(str(model_dir / "best_weights"))
    shapes = reader.get_variable_to_shape_map()
    layer_keys = select_checkpoint_layers(shapes)
    inventory = [{"name": name, "shape": list(shapes[name]),
                  "dtype": reader.get_variable_to_dtype_map()[name].name}
                 for name in sorted(shapes)]
    (output / "checkpoint-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    warning_capture = WarningCapture()
    tf.get_logger().addHandler(warning_capture)
    try:
        model = models.MODELS["kws_transformer"](SimpleNamespace(**flags))
        status = model.load_weights(str(model_dir / "best_weights"))
        status.assert_existing_objects_matched()
        status.expect_partial()  # Only checkpoint optimizer state may remain unused.
        restoration = verify_all_model_values(model, reader, tf, np, output)
    finally:
        tf.get_logger().removeHandler(warning_capture)
    restoration["upstream_object_graph_warnings"] = warning_capture.messages
    restoration["warning_resolution"] = (
        "Dense/GELU trackable alias warnings retained; every model parameter key and value "
        "was independently compared to the original checkpoint before inference")
    transformers = [layer for layer in model.layers if isinstance(layer, KWSTransformer)]
    feature_layers = [layer for layer in model.layers if isinstance(layer, SpeechFeatures)]
    if len(transformers) != 1 or len(feature_layers) != 1:
        raise ValueError("expected exactly one upstream transformer and feature layer")
    transformer = transformers[0]
    if len(transformer.enc_layers) != 12:
        raise ValueError("upstream model did not build 12 encoder layers")

    if waveform is None:
        samples = np.zeros(16000, dtype=np.float32)
        input_record = {"kind": "synthetic_zero_silence_smoke", "origin": "16000 exact zero samples",
                        "dataset_split": "none; not a dataset/calibration/validation/test sample"}
    else:
        loaded = np.load(str(waveform), allow_pickle=False)
        if loaded.shape not in ((16000,), (1, 16000)) or loaded.dtype.kind != "f":
            raise ValueError("waveform must be one floating-point 16000-sample mono .npy")
        samples = np.asarray(loaded, dtype=np.float32).reshape(16000)
        input_record = {"kind": "user_supplied_waveform_smoke", "origin": str(waveform),
                        "original_file_sha256": sha256(waveform),
                        "dataset_split": "unspecified; smoke only; never used to select scales"}
    if not np.isfinite(samples).all() or np.max(np.abs(samples)) > 1.0:
        raise ValueError("waveform must be finite and within normalized [-1,1]")
    np.save(str(output / "waveform.npy"), samples, allow_pickle=False)
    input_record.update(sample_rate=16000, channels=1, samples=16000,
                        waveform=artifact(output / "waveform.npy", output))
    audio = tf.convert_to_tensor(samples.reshape(1, 16000))
    # The upstream registry imports input_data, which selects TF v1 graph mode.
    # Use the active Keras session rather than assuming eager .numpy() support.
    features = tf.keras.backend.get_value(feature_layers[0](audio, training=False))
    if features.shape != (1, 98, 40) or not np.isfinite(features).all():
        raise ValueError("upstream MFCC output must be finite [1,98,40]")
    np.save(str(output / "mfcc.npy"), features[0], allow_pickle=False)

    # Hooks observe the actual upstream Dense invocation; they call the original
    # implementation unchanged and are removed immediately after one inference.
    captured, originals = {}, []
    for layer_id, block in enumerate(transformer.enc_layers):
        dense = block.ffn.layers[0]
        original_call = dense.call

        def capture(inputs, *args, _id=layer_id, _call=original_call, **kwargs):
            result = _call(inputs, *args, **kwargs)
            if _id in captured:
                raise ValueError("FFN1 was called more than once during one inference")
            captured[_id] = (inputs, result)
            return result

        originals.append((dense, original_call))
        dense.call = capture
    try:
        logits = model(audio, training=False)
    finally:
        for dense, original_call in originals:
            dense.call = original_call
    if isinstance(logits, (list, tuple)):
        if len(logits) != 1:
            raise ValueError("expected one non-distilled classifier output")
        logits = logits[0]
    logits = tf.keras.backend.get_value(logits)
    if logits.shape != (1, 12) or not np.isfinite(logits).all() or set(captured) != set(range(12)):
        raise ValueError("incomplete or nonfinite full-model inference")
    np.save(str(output / "logits.npy"), logits, allow_pickle=False)

    layers, statistics = [], fixed.LayerNRMSE()
    for layer_id, keys in enumerate(layer_keys):
        block = transformer.enc_layers[layer_id]
        x, reference = tf.keras.backend.batch_get_value(list(captured[layer_id]))
        x, reference = x[0], reference[0]
        w, bias, gamma, beta = tf.keras.backend.batch_get_value([
            block.ffn.layers[0].kernel, block.ffn.layers[0].bias,
            block.layernorm1.gamma, block.layernorm1.beta])
        for name, value in (("kernel", w), ("bias", bias), ("gamma", gamma), ("beta", beta)):
            if not np.array_equal(value, reader.get_tensor(keys[name])):
                raise ValueError("FFN/LN parameter identity mismatch: " + keys[name])
        for name, value in (("x", x), ("w", w), ("bias", bias), ("y", reference)):
            if list(value.shape) != SHAPE[name] or not np.isfinite(value).all():
                raise ValueError("bad layer tensor shape/finiteness: " + name)
        x_bound = layernorm_bound(gamma, beta)
        w_bound = float(np.max(np.abs(w)))
        scales = fixed.Fixed16Scales(choose_scale_exp(x_bound), choose_scale_exp(w_bound))
        xi, wi, bi = fixed.quantize_linear_inputs(x.tolist(), w.tolist(), bias.tolist(), scales)
        yi = fixed.linear99x64x256(xi, wi, bi)
        decoded = fixed.decode_output(yi, scales)
        statistics.update(layer_id, decoded, reference.tolist())
        clipping = {"x": clipping_count(x.flat, 16, scales.x_exp),
                    "w": clipping_count(w.flat, 16, scales.w_exp),
                    "bias": clipping_count(bias.flat, 40, scales.y_exp)}
        if any(clipping.values()):
            raise ValueError("parameter-only candidate scales clipped an exported tensor")
        directory = output / ("layer_%02d" % layer_id)
        directory.mkdir()
        files = {}
        for name, values, bits in (("x", (v for row in xi for v in row), 16),
                                   ("w", (v for row in wi for v in row), 16),
                                   ("bias", bi, 40), ("y", (v for row in yi for v in row), 48)):
            record = fixed.write_hex_mem(directory / (name + ".mem"), values, bits)
            record["path"] = str(Path(record["path"]).relative_to(output))
            files[name] = record
        np.savez(str(directory / "tensors.npz"), x_float=x, w_float=w, bias_float=bias,
                 y_float=reference, gamma=gamma, beta=beta, x_integer=np.asarray(xi, dtype=np.int16),
                 w_integer=np.asarray(wi, dtype=np.int16), bias_integer=np.asarray(bi, dtype=np.int64),
                 y_integer=np.asarray(yi, dtype=np.int64), y_decoded=np.asarray(decoded, dtype=np.float64))
        layer_report = {"layer_id": layer_id, "files": files, "checkpoint_keys": keys,
                        "shape": SHAPE, "float_tensors": artifact(directory / "tensors.npz", output),
                        "scales": {"x_exp": scales.x_exp, "w_exp": scales.w_exp,
                                   "bias_exp": scales.y_exp, "y_exp": scales.y_exp},
                        "scale_selection": {"x_bound": x_bound, "w_maxabs": w_bound,
                            "method": "x: sqrt(64)*maxabs(LN1.gamma)+maxabs(LN1.beta); w: maxabs(W); smallest signed16-safe power-of-two scale",
                            "sample_independent": True}, "clipping_counts": clipping,
                        "nrmse": statistics.report(require_all_layers=False)["layers"][str(layer_id)]}
        layers.append(layer_report)
        print("KWT_LAYER_EXPORTED " + json.dumps({"layer_id": layer_id, "scales": layer_report["scales"],
               "clipping_counts": clipping, "nrmse": layer_report["nrmse"]["nrmse"]}), flush=True)

    report = {"schema": "kwt_ffn_export_v1", "status": "PASS", "format": fixed.FORMAT_ID,
              "scope": "one-waveform real-checkpoint inference and integer export smoke; not validation-set or official 600-sample accuracy",
              "created_utc": datetime.now(timezone.utc).isoformat(), "source": provenance,
              "environment": environment_record(), "shape": SHAPE, "input": input_record,
              "checkpoint_inventory": artifact(output / "checkpoint-inventory.json", output),
              "restoration": restoration, "inference_flags": flags,
              "mfcc": artifact(output / "mfcc.npy", output), "logits": artifact(output / "logits.npy", output),
              "layers": layers, "nrmse": statistics.report(),
              "implementation": [{"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
                  for path in (Path(__file__).resolve(), ROOT / "model/fixed16_acc48.py")],
              "end_marker": END_MARKER,
              "limitations": ["Single smoke waveform does not establish 3% accuracy across validation data or official samples.",
                              "TensorFlow 2.4.0 release is an explicitly recorded fallback from requested 2.4.0rc1.",
                              "No RTL, SoC, PPA, or complete competition timing claim is made by this exporter."]}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "vendor/kwt1-237e4097")
    parser.add_argument("--output", type=Path, required=True, help="New output directory; existing directories are rejected")
    parser.add_argument("--waveform", type=Path, help="Optional normalized float .npy, 16000 samples at 16 kHz")
    args = parser.parse_args(argv)
    source, output = args.source.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    try:
        report = run_export(source, output, args.waveform.resolve() if args.waveform else None)
    except Exception as exc:
        report = {"schema": "kwt_ffn_export_v1", "status": "FAIL",
                  "error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        traceback.print_exc()
        return 1
    (output / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(END_MARKER + " " + json.dumps({"status": report["status"], "output": str(output),
          "max_layer_nrmse": report["nrmse"]["max_layer_nrmse"], "scope": report["scope"]}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
