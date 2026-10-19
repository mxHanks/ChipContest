#!/usr/bin/env python3
"""Evaluate isolated FFN1 quantization on the pinned KWT validation split.

This is a development evaluation in the recorded TensorFlow 2.4.0 fallback.
It does not feed quantized outputs through later transformer layers and is not
an official 600-task, RTL, SoC, timing, area or power acceptance result.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
END_MARKER = "KWT_DATASET_EVALUATION_COMPLETED"
FLOOR = 1e-8


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                    allow_nan=False) + "\n")


def quantize_float32(values, bits, exponent):
    """Exact RNE+saturation for finite float32 and bounded power-of-two scales.

    Conversion to binary64 is exact. Scaling float32 by 2**[-64,64] remains
    normal binary64, retaining every input significand bit. np.rint therefore
    sees the exact scaled value; clipping precedes the int64 cast. The bounded
    domain is intentional and checked rather than assumed for arbitrary input.
    """
    import numpy as np
    if values.dtype != np.dtype("float32") or not np.isfinite(values).all():
        raise ValueError("quantizer requires finite float32 tensors")
    if type(bits) is not int or bits not in (16, 40):
        raise ValueError("quantizer supports signed16/signed40 only")
    if type(exponent) is not int or not -64 <= exponent <= 64:
        raise ValueError("quantizer scale exponent must be an integer in [-64,64]")
    scaled = np.ldexp(values.astype(np.float64), -exponent)
    rounded = np.rint(scaled)
    low, high = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    clips = int(np.count_nonzero((rounded < low) | (rounded > high)))
    return np.clip(rounded, low, high).astype(np.int64), clips


def integer_linear(x, weights, bias):
    """Int64 is exact: all legal partial sums have magnitude below 2**40."""
    import numpy as np
    if x.ndim != 3 or x.shape[1:] != (99, 64) or x.shape[0] == 0:
        raise ValueError("X must be a nonempty batch of [99,64]")
    for name, value, shape, bits in (("X", x, x.shape, 16),
                                     ("W", weights, (64, 256), 16),
                                     ("bias", bias, (256,), 40)):
        if value.shape != shape or value.dtype != np.dtype("int64"):
            raise ValueError(name + " shape/dtype mismatch")
        if np.any(value < -(1 << (bits - 1))) or np.any(value > (1 << (bits - 1)) - 1):
            raise ValueError(name + " exceeds signed input range")
    result = np.matmul(x, weights) + bias
    if np.any(result < -(1 << 47)) or np.any(result >= (1 << 47)):
        raise ValueError("output exceeds signed48")
    return result


def error_sums(decoded, reference):
    import numpy as np
    if decoded.ndim != 3 or decoded.shape != reference.shape or decoded.shape[1:] != (99, 256):
        raise ValueError("error tensors must have equal [batch,99,256] shapes")
    if not np.isfinite(decoded).all() or not np.isfinite(reference).all():
        raise ValueError("error tensors must be finite")
    ref = reference.astype(np.float64)
    difference = decoded.astype(np.float64) - ref
    sse = np.sum(difference * difference, axis=(1, 2), dtype=np.float64)
    energy = np.sum(ref * ref, axis=(1, 2), dtype=np.float64)
    count = 99 * 256
    nrmse = np.sqrt(sse / count) / np.maximum(np.sqrt(energy / count), FLOOR)
    return {"sse": sse, "reference_energy": energy, "nrmse": nrmse,
            "peak_absolute_error": np.max(np.abs(difference), axis=(1, 2)),
            "peak_reference": np.max(np.abs(ref), axis=(1, 2))}


def aggregate(sse, energy, sample_count):
    if type(sample_count) is not int or sample_count <= 0:
        raise ValueError("sample count must be positive")
    if len(sse) != sample_count or len(energy) != sample_count:
        raise ValueError("incomplete per-sample sums")
    if any(not math.isfinite(v) or v < 0 for v in list(sse) + list(energy)):
        raise ValueError("sums must be finite and nonnegative")
    total_sse, total_energy = math.fsum(sse), math.fsum(energy)
    count = sample_count * 99 * 256
    return {"sum_error_sq": total_sse, "sum_reference_sq": total_energy,
            "count": count, "samples": sample_count,
            "nrmse": math.sqrt(total_sse / count) / max(math.sqrt(total_energy / count), FLOOR)}


def file_record(path, root):
    return {"path": str(path.relative_to(root)), "sha256": digest(path), "bytes": path.stat().st_size}


def evaluate(args, report):
    for key, value in (("TF_NUM_INTRAOP_THREADS", "2"), ("TF_NUM_INTEROP_THREADS", "1"),
                       ("OMP_NUM_THREADS", "2"), ("CUDA_VISIBLE_DEVICES", "-1")):
        os.environ[key] = value
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).parent))
    import export_kwt as exporter
    source, output, data = args.source, args.output, args.data
    provenance = exporter.source_inventory(source)
    implementation_paths = (Path(__file__).resolve(), ROOT / "scripts/model/export_kwt.py",
                            ROOT / "model/fixed16_acc48.py")
    implementations = [file_record(p, ROOT) for p in implementation_paths]
    preparation_path, inventory_path = data / "preparation.json", data / "source-files.json"
    preparation = json.loads(preparation_path.read_text())
    inventory_sha = digest(inventory_path)
    if (preparation.get("status") != "PASS" or preparation.get("archive_sha256") !=
            "af14739ee7dc311471de98f5f9d2c9191b18aedfe957f4a6ff791c709868ff58" or
            preparation["inventory"]["sha256"] != inventory_sha):
        raise ValueError("dataset preparation/inventory is unverified")
    inventory = {r["path"]: r for r in json.loads(inventory_path.read_text())}
    preparation_sha = digest(preparation_path)

    import numpy as np
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    if tf.__version__ != "2.4.0" or np.__version__ != "1.19.5":
        raise ValueError("requires recorded TF 2.4.0/NumPy 1.19.5 fallback")
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(source))
    from model import fixed16_acc48 as fixed
    from kws_streaming.models import models
    from kws_streaming.models.transformer_utils import KWSTransformer
    from kws_streaming.data import input_data

    model_dir = source / exporter.MODEL_SUBDIR
    flags = json.loads((model_dir / "flags.json").read_text())
    exporter.validate_flags(flags)
    for key, value in (("distill_teacher_json", ""), ("prenorm", False), ("approximate_gelu", False)):
        flags.setdefault(key, value)
    flags.update(training=False, train=0, batch_size=args.batch_size, use_spec_augment=0,
                 use_spec_cutout=0, sp_time_shift_ms=0.0, sp_resample=0.0,
                 time_shift_ms=0.0, resample=0.0, volume_resample=0.0,
                 background_frequency=0.0, background_volume=0.0, data_url="", data_dir=str(data))
    namespace = SimpleNamespace(**flags)
    glob_calls = []
    replay = json.loads(args.replay_sampling.read_text()) if args.replay_sampling else None
    original_glob = input_data.gfile.Glob

    def capture_glob(pattern):
        actual = list(original_glob(pattern))
        relative_pattern = str(Path(pattern).relative_to(data))
        relative_actual = [str(Path(p).resolve().relative_to(data)) for p in actual]
        if len(set(relative_actual)) != len(relative_actual):
            raise ValueError("duplicate dataset glob entry")
        # Replays preserve the original exact enumeration order. A new/deleted
        # file is rejected rather than quietly changing the sampled unknowns.
        if replay is not None:
            index = len(glob_calls)
            if index >= len(replay["glob_calls"]):
                raise ValueError("unexpected replay glob call")
            recorded = replay["glob_calls"][index]
            if recorded["pattern"] != relative_pattern or sorted(recorded["files"]) != sorted(relative_actual):
                raise ValueError("replay glob membership/pattern differs")
            relative_actual = recorded["files"]
            actual = [str(data / p) for p in relative_actual]
        if any(p not in inventory for p in relative_actual):
            raise ValueError("glob file absent from official archive inventory")
        glob_calls.append({"pattern": relative_pattern, "files": relative_actual})
        return actual

    input_data.gfile.Glob = capture_glob
    try:
        processor = input_data.AudioProcessor(namespace)
    finally:
        input_data.gfile.Glob = original_glob
    if replay is not None and len(glob_calls) != len(replay["glob_calls"]):
        raise ValueError("incomplete replay glob calls")
    entries = []
    for index, item in enumerate(processor.data_index["validation"]):
        relative = str(Path(item["file"]).resolve().relative_to(data))
        silence = item["label"] == input_data.SILENCE_LABEL
        entries.append({"index": index, "label": item["label"],
                        "label_index": int(processor.word_to_index[item["label"]]),
                        "file": relative, "file_sha256": inventory[relative]["sha256"],
                        "input_kind": "exact_zero_16000_no_wav_decode" if silence else "upstream_decode_wav"})
        if not silence and input_data.which_set(item["file"], flags["validation_percentage"],
                                                flags["testing_percentage"]) != "validation":
            raise ValueError("non-silence validation item belongs to another split")
    if not entries:
        raise ValueError("empty validation split")
    sampling = {"schema": "kwt_original_sampling_v1", "glob_calls": glob_calls,
                "validation": entries, "partition_sizes": {k: len(v) for k, v in processor.data_index.items()},
                "words_list": processor.words_list, "random_seed": input_data.RANDOM_SEED,
                "sampling": "unmodified AudioProcessor builds validation/testing/training in original random-stream order",
                "silence_semantics": "pinned get_data leaves silence output and label at initialized zero; placeholder WAV is not decoded"}
    if replay is not None and entries != replay["validation"]:
        raise ValueError("replayed validation sequence differs")
    write_json(output / "sampling.json", sampling)
    count = min(args.limit or len(entries), len(entries))
    selected = entries[:count]
    # Background WAVs are loaded by the original constructor even though no
    # background augmentation is applied in validation. Bind those bytes too.
    consumed_paths = {e["file"] for e in entries}
    consumed_paths.update(p for c in glob_calls for p in c["files"] if p.startswith("_background_noise_/"))
    consumed = []
    for relative in sorted(consumed_paths):
        path = data / relative
        if digest(path) != inventory[relative]["sha256"] or path.stat().st_size != inventory[relative]["bytes"]:
            raise ValueError("dataset bytes changed: " + relative)
        consumed.append(inventory[relative])
    write_json(output / "consumed-source-files.json", consumed)
    report.update(source=provenance, implementation=implementations,
                  environment=exporter.environment_record(), inference_flags=flags,
                  dataset={"source_directory": str(data), "preparation_sha256": preparation_sha,
                           "inventory_sha256": inventory_sha, "sampling": file_record(output / "sampling.json", output),
                           "consumed_files": file_record(output / "consumed-source-files.json", output),
                           "full_validation_samples": len(entries), "evaluated_samples": count,
                           "label_counts": dict(Counter(e["label_index"] for e in selected)),
                           "replay_manifest_sha256": digest(args.replay_sampling) if replay else None},
                  scope="full original validation split, isolated FFN1 error" if count == len(entries) else
                        "development prefix of original validation split, isolated FFN1 error")
    reader = tf.train.load_checkpoint(str(model_dir / "best_weights"))
    layer_keys = exporter.select_checkpoint_layers(reader.get_variable_to_shape_map())
    warning_capture = exporter.WarningCapture()
    tf.get_logger().addHandler(warning_capture)
    try:
        model = models.MODELS["kws_transformer"](namespace)
        status = model.load_weights(str(model_dir / "best_weights"))
        status.assert_existing_objects_matched()
        status.expect_partial()
        report["restoration"] = exporter.verify_all_model_values(model, reader, tf, np, output)
    finally:
        tf.get_logger().removeHandler(warning_capture)
    report["restoration"]["upstream_object_graph_warnings"] = warning_capture.messages
    transformers = [layer for layer in model.layers if isinstance(layer, KWSTransformer)]
    if len(transformers) != 1 or len(transformers[0].enc_layers) != 12:
        raise ValueError("requires one 12-layer transformer")
    transformer = transformers[0]
    parameters, layer_reports = [], []
    for layer_id, keys in enumerate(layer_keys):
        block = transformer.enc_layers[layer_id]
        w, bias, gamma, beta = tf.keras.backend.batch_get_value([
            block.ffn.layers[0].kernel, block.ffn.layers[0].bias, block.layernorm1.gamma, block.layernorm1.beta])
        for name, value in (("kernel", w), ("bias", bias), ("gamma", gamma), ("beta", beta)):
            if not np.array_equal(value, reader.get_tensor(keys[name])):
                raise ValueError("FFN/LN parameter identity mismatch")
        x_bound, w_bound = exporter.layernorm_bound(gamma, beta), float(np.max(np.abs(w)))
        scales = fixed.Fixed16Scales(exporter.choose_scale_exp(x_bound), exporter.choose_scale_exp(w_bound))
        wi, wclip = quantize_float32(w, 16, scales.w_exp)
        bi, bclip = quantize_float32(bias, 40, scales.y_exp)
        if wclip or bclip:
            raise ValueError("parameter-only scales clip W/bias")
        parameters.append((w, bias, wi, bi, scales))
        layer_reports.append({"layer_id": layer_id, "checkpoint_keys": keys,
                              "scales": {"x_exp": scales.x_exp, "w_exp": scales.w_exp, "y_exp": scales.y_exp},
                              "scale_selection": {"sample_independent": True, "x_bound": x_bound, "w_bound": w_bound},
                              "weight_clips": wclip, "bias_clips": bclip})
    captured, originals = {}, []
    audio = tf.compat.v1.placeholder(tf.float32, shape=(args.batch_size, 16000), name="evaluation_waveform")
    for layer_id, block in enumerate(transformer.enc_layers):
        dense, original_call = block.ffn.layers[0], block.ffn.layers[0].call
        def capture(inputs, *positional, _id=layer_id, _call=original_call, **keywords):
            result = _call(inputs, *positional, **keywords)
            if _id in captured:
                raise ValueError("FFN1 called multiple times during graph construction")
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
            raise ValueError("expected single classifier output")
        logits = logits[0]
    if set(captured) != set(range(12)):
        raise ValueError("missing FFN1 hook")
    fetches = [value for i in range(12) for value in captured[i]] + [logits]
    session = tf.compat.v1.keras.backend.get_session()
    graph_ops = len(session.graph.get_operations())
    all_sse, all_energy, all_sample_nrmse = [[] for _ in range(12)], [[] for _ in range(12)], [[] for _ in range(12)]
    clips, max_errors, max_references = [0] * 12, [0.0] * 12, [0.0] * 12
    stream_hashes = [{key: hashlib.sha256() for key in ("x_float32", "reference_float32", "integer_output_int64")}
                     for _ in range(12)]
    canonical, correct, zero_samples = [], 0, 0
    loop_start = time.monotonic()
    print("KWT_DATASET_STARTED " + json.dumps({"samples": count, "full_split": len(entries),
                                                "batch_size": args.batch_size}), flush=True)
    with (output / "samples.jsonl").open("w") as sample_log:
        for offset in range(0, count, args.batch_size):
            take = min(args.batch_size, count - offset)
            batch, labels = processor.get_data(take, offset, namespace, 0, 0, 0, "validation", 0, 0, session)
            if batch.shape != (take, 16000) or not np.isfinite(batch).all() or np.max(np.abs(batch)) > 1:
                raise ValueError("invalid preprocessed waveform batch")
            padded = np.zeros((args.batch_size, 16000), dtype=np.float32)
            padded[:take] = batch
            records = []
            for local, entry in enumerate(selected[offset:offset + take]):
                if int(labels[local]) != entry["label_index"]:
                    raise ValueError("upstream label differs from sampled entry")
                if entry["input_kind"] == "exact_zero_16000_no_wav_decode":
                    if np.any(padded[local]) or labels[local] != 0:
                        raise ValueError("silence semantics changed")
                    zero_samples += 1
                records.append({"sample_index": offset + local, "label_index": int(labels[local]),
                                "waveform_float32_sha256": hashlib.sha256(padded[local].tobytes(order="C")).hexdigest(),
                                "layers": []})
            tensors = session.run(fetches, feed_dict={audio: padded})
            prediction = tensors[-1][:take]
            if prediction.shape != (take, 12) or not np.isfinite(prediction).all():
                raise ValueError("invalid reference classifier output")
            correct += int(np.count_nonzero(np.argmax(prediction, axis=1) == labels))
            for layer_id, (w, bias, wi, bi, scales) in enumerate(parameters):
                x, reference = tensors[2 * layer_id][:take], tensors[2 * layer_id + 1][:take]
                if x.shape != (take, 99, 64) or reference.shape != (take, 99, 256) or reference.dtype != np.float32:
                    raise ValueError("wrong FFN1 tensor shape/type")
                xi, xclip = quantize_float32(x, 16, scales.x_exp)
                yi = integer_linear(xi, wi, bi)
                if offset == 0:
                    expected_x, expected_w, expected_b = fixed.quantize_linear_inputs(
                        x[0].tolist(), w.tolist(), bias.tolist(), scales)
                    expected_y = fixed.linear99x64x256(expected_x, expected_w, expected_b)
                    for name, actual, expected in (("x", xi[0], expected_x), ("w", wi, expected_w),
                                                    ("bias", bi, expected_b), ("y", yi[0], expected_y)):
                        if not np.array_equal(actual, np.asarray(expected, dtype=np.int64)):
                            raise ValueError("canonical integer comparison failed: " + name)
                    canonical.append({"layer_id": layer_id, "status": "PASS", "output_values_compared": 99 * 256})
                decoded = np.ldexp(yi.astype(np.float64), scales.y_exp)
                sums = error_sums(decoded, reference)
                for key, value in (("x_float32", x), ("reference_float32", reference), ("integer_output_int64", yi)):
                    stream_hashes[layer_id][key].update(value.tobytes(order="C"))
                clips[layer_id] += xclip
                max_errors[layer_id] = max(max_errors[layer_id], float(np.max(sums["peak_absolute_error"])))
                max_references[layer_id] = max(max_references[layer_id], float(np.max(sums["peak_reference"])))
                all_sse[layer_id].extend(sums["sse"].tolist())
                all_energy[layer_id].extend(sums["reference_energy"].tolist())
                all_sample_nrmse[layer_id].extend(sums["nrmse"].tolist())
                for local, record in enumerate(records):
                    record["layers"].append({"layer_id": layer_id, **{k: float(v[local]) for k, v in sums.items()}})
            for record in records:
                sample_log.write(json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n")
            sample_log.flush()
            done = offset + take
            if offset == 0 or done == count or (offset // args.batch_size + 1) % 10 == 0:
                elapsed = time.monotonic() - loop_start
                print("KWT_DATASET_PROGRESS " + json.dumps({"samples": done, "total": count,
                      "elapsed_seconds": round(elapsed, 3), "estimated_remaining_seconds": round(elapsed * (count - done) / done, 1)}), flush=True)
    if len(session.graph.get_operations()) != graph_ops:
        raise ValueError("inference graph grew across batches")
    for layer_id, item in enumerate(layer_reports):
        item.update(aggregate(all_sse[layer_id], all_energy[layer_id], count))
        worst = max(range(count), key=lambda i: all_sample_nrmse[layer_id][i])
        item.update(x_clips=clips[layer_id], max_sample_nrmse=all_sample_nrmse[layer_id][worst],
                    worst_sample_index=worst, peak_absolute_error=max_errors[layer_id],
                    peak_reference=max_references[layer_id],
                    tensor_stream_sha256={k: v.hexdigest() for k, v in stream_hashes[layer_id].items()})
    if any(clips):
        raise ValueError("parameter-only X scales clipped validation data")
    if len(canonical) != 12 or sum(item["output_values_compared"] for item in canonical) != 304128:
        raise ValueError("incomplete canonical cross-check")
    if exporter.source_inventory(source) != provenance:
        raise ValueError("pinned source/checkpoint changed during evaluation")
    if [file_record(p, ROOT) for p in implementation_paths] != implementations:
        raise ValueError("evaluator/reference implementation changed during evaluation")
    if digest(inventory_path) != inventory_sha or digest(preparation_path) != preparation_sha:
        raise ValueError("dataset preparation/inventory changed during evaluation")
    for record in consumed:
        if digest(data / record["path"]) != record["sha256"]:
            raise ValueError("consumed WAV changed during evaluation")
    max_nrmse = max(item["nrmse"] for item in layer_reports)
    max_sample = max(item["max_sample_nrmse"] for item in layer_reports)
    gate = "PASS" if max_nrmse <= 0.03 and max_sample <= 0.03 else "FAIL"
    report.update(status=gate, evaluation_completed=True, format=fixed.FORMAT_ID, layers=layer_reports,
                  canonical_crosscheck={"status": "PASS", "sample_index": 0, "layers": canonical},
                  samples=file_record(output / "samples.jsonl", output),
                  input_rehash="PASS", graph_operations=graph_ops, graph_reused=True,
                  silence_zero_samples=zero_samples, reference_classifier_accuracy=correct / count,
                  reference_classifier_correct=correct, max_layer_nrmse=max_nrmse,
                  max_sample_layer_nrmse=max_sample,
                  development_3_percent_gate=gate,
                  numerical_loop_seconds=time.monotonic() - loop_start,
                  official_600_task_acceptance="NOT_RUN", rtl_full_validation="NOT_RUN", soc_ppa="NOT_RUN",
                  end_marker=END_MARKER)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "vendor/kwt1-237e4097")
    parser.add_argument("--data", type=Path, default=ROOT / "data/speech-commands-v0.02")
    parser.add_argument("--output", type=Path, required=True, help="New directory only")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=0, help="0 evaluates the complete validation split")
    parser.add_argument("--replay-sampling", type=Path, help="Replay a previous sampling.json enumeration")
    args = parser.parse_args(argv)
    if not 1 <= args.batch_size <= 64 or args.limit < 0:
        parser.error("batch-size must be 1..64 and limit must be nonnegative")
    for key in ("source", "data", "output"):
        setattr(args, key, getattr(args, key).resolve())
    if args.replay_sampling:
        args.replay_sampling = args.replay_sampling.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = {"schema": "kwt_validation_ffn_v1", "status": "FAIL",
              "created_utc": datetime.now(timezone.utc).isoformat(), "command": [sys.executable, *sys.argv],
              "limitations": ["TensorFlow 2.4.0 is a recorded fallback, not exact upstream 2.4.0rc1 certification.",
                              "Each FFN1 receives the real FP32 model activation independently; quantization is not propagated across layers.",
                              "Development validation does not replace official 600 tasks, full RTL replay, SoC or specified-process PPA."]}
    try:
        report = evaluate(args, report)
        exit_code = 0 if report["status"] == "PASS" else 1
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
        traceback.print_exc()
        exit_code = 1
    report["elapsed_seconds"] = time.monotonic() - started
    report["exit_code"] = exit_code
    write_json(args.output / "result.json", report)
    if report.get("evaluation_completed"):
        print(END_MARKER + " " + json.dumps({"status": report["status"], "output": str(args.output),
              "samples": report["dataset"]["evaluated_samples"], "max_layer_nrmse": report["max_layer_nrmse"],
              "max_sample_layer_nrmse": report["max_sample_layer_nrmse"], "elapsed_seconds": report["elapsed_seconds"]}), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
