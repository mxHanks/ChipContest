#!/usr/bin/env python3
"""Compare explicit effective X/W widths using one audited FP32 inference stream.

The frozen evaluator remains the 16/16 control. Narrow candidates observe its
FP32 tensors through checked callbacks; its model, sampling and source are not
modified. Software error/Python bounds are not physical PPA results.
"""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
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
END_MARKER = "KWT_PRECISION_SWEEP_COMPLETED"
CANDIDATES = ((16, 16), (14, 12), (12, 12), (12, 10), (12, 8), (10, 8), (8, 8))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def scale_exponent(bound, bits):
    if type(bits) is not int or not 2 <= bits <= 16:
        raise ValueError("effective width must be 2..16")
    if not math.isfinite(bound) or bound < 0:
        raise ValueError("bound must be finite and nonnegative")
    if bound == 0:
        return 0
    exact = Fraction.from_float(float(bound))
    peak = (1 << (bits - 1)) - 1
    exponent = math.ceil(math.log2(bound) - math.log2(peak))
    capacity = lambda e: peak * (Fraction(1 << e) if e >= 0 else Fraction(1, 1 << -e))
    while capacity(exponent) < exact:
        exponent += 1
    while capacity(exponent - 1) >= exact:
        exponent -= 1
    return exponent


def encode(values, bits, exponent):
    import numpy as np
    if values.dtype != np.float32 or not np.isfinite(values).all():
        raise ValueError("encoding requires finite float32")
    if type(bits) is not int or bits not in tuple(range(2, 17)) + (40,):
        raise ValueError("invalid width")
    if type(exponent) is not int or not -64 <= exponent <= 64:
        raise ValueError("invalid exponent")
    rounded = np.rint(np.ldexp(values.astype(np.float64), -exponent))
    low, high = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    clips = int(np.count_nonzero((rounded < low) | (rounded > high)))
    result = np.clip(rounded, low, high).astype(np.int64)
    if np.any(result < low) or np.any(result > high):
        raise ValueError("encoded tensor exceeds declared effective width")
    return result, clips


def required_signed_bits(low, high):
    if type(low) is not int or type(high) is not int or low > high:
        raise ValueError("invalid integer interval")
    bits = 2
    while low < -(1 << (bits - 1)) or high > (1 << (bits - 1)) - 1:
        bits += 1
    return bits


def accumulator_bound(x_bits, w_bits, bias_low, bias_high):
    """Exact full-domain interval, including all partial 0..64 MAC sums."""
    if not (type(x_bits) is int and type(w_bits) is int and 2 <= x_bits <= 16 and 2 <= w_bits <= 16):
        raise ValueError("invalid operand widths")
    if type(bias_low) is not int or type(bias_high) is not int or bias_low > bias_high:
        raise ValueError("invalid bias interval")
    xlo, xhi = -(1 << (x_bits - 1)), (1 << (x_bits - 1)) - 1
    wlo, whi = -(1 << (w_bits - 1)), (1 << (w_bits - 1)) - 1
    products = (xlo * wlo, xlo * whi, xhi * wlo, xhi * whi)
    low = bias_low + 64 * min(products)
    high = bias_high + 64 * max(products)
    return {"minimum": low, "maximum": high, "signed_bits": required_signed_bits(low, high),
            "includes_all_partial_sums": True, "terms": 64}


def precision_score_proxy(nrmse):
    if not math.isfinite(nrmse) or nrmse < 0:
        raise ValueError("invalid NRMSE")
    return max(0.0, 10.0 - nrmse / 0.003)


class Observer:
    def __init__(self, base, exporter, fixed, np, source, directory):
        self.base, self.exporter, self.fixed, self.np = base, exporter, fixed, np
        self.source, self.directory = source, directory
        self.original_quantize, self.original_errors = base.quantize_float32, base.error_sums
        self.parameters, self.current_x = None, None
        self.w_calls = self.b_calls = self.layer_calls = self.offset = 0
        self.batch_records = None
        self.results = {}
        for xb, wb in CANDIDATES:
            name = "%d_%d" % (xb, wb)
            self.results[name] = {"x_bits": xb, "w_bits": wb, "layers": [], "canonical": [],
                                  "metrics": (directory / (name + "-samples.jsonl")).open("w"),
                                  "sse": [[] for _ in range(12)], "energy": [[] for _ in range(12)],
                                  "nrmse": [[] for _ in range(12)], "peak": [0.0] * 12,
                                  "x_clips": [0] * 12, "output_streams": [hashlib.sha256() for _ in range(12)],
                                  "observed_low": [0] * 12, "observed_high": [0] * 12}

    def close(self):
        for candidate in self.results.values():
            candidate["metrics"].close()

    def load_parameters(self):
        import tensorflow as tf
        reader = tf.train.load_checkpoint(str(self.source / self.exporter.MODEL_SUBDIR / "best_weights"))
        self.parameters = []
        for layer_id, keys in enumerate(self.exporter.select_checkpoint_layers(reader.get_variable_to_shape_map())):
            w, bias = reader.get_tensor(keys["kernel"]), reader.get_tensor(keys["bias"])
            gamma, beta = reader.get_tensor(keys["gamma"]), reader.get_tensor(keys["beta"])
            x_bound = self.exporter.layernorm_bound(gamma, beta)
            w_bound = float(self.np.max(self.np.abs(w)))
            self.parameters.append((w, bias, x_bound, w_bound))
            for candidate in self.results.values():
                xexp, wexp = scale_exponent(x_bound, candidate["x_bits"]), scale_exponent(w_bound, candidate["w_bits"])
                wi, wclip = encode(w, candidate["w_bits"], wexp)
                bi, bclip = encode(bias, 40, xexp + wexp)
                item = {"layer_id": layer_id, "x_exp": xexp, "w_exp": wexp, "y_exp": xexp + wexp,
                        "x_parameter_bound": x_bound, "w_parameter_bound": w_bound,
                        "w_clips": wclip, "bias_clips": bclip, "wi": wi, "bi": bi,
                        "bias_minimum": int(self.np.min(bi)), "bias_maximum": int(self.np.max(bi))}
                candidate["layers"].append(item)

    def quantize(self, values, bits, exponent):
        result = self.original_quantize(values, bits, exponent)
        if self.parameters is None:
            self.load_parameters()
        if values.shape == (64, 256) and bits == 16:
            if self.w_calls >= 12 or self.w_calls != self.b_calls:
                raise ValueError("unexpected parameter observation order")
            if not self.np.array_equal(values, self.parameters[self.w_calls][0]):
                raise ValueError("observed W differs from checkpoint")
            self.w_calls += 1
        elif values.shape == (256,) and bits == 40:
            if self.b_calls >= 12 or self.w_calls != self.b_calls + 1:
                raise ValueError("unexpected bias observation order")
            if not self.np.array_equal(values, self.parameters[self.b_calls][1]):
                raise ValueError("observed bias differs from checkpoint")
            self.b_calls += 1
        elif values.ndim == 3 and values.shape[1:] == (99, 64) and bits == 16:
            if self.current_x is not None or self.w_calls != 12 or self.b_calls != 12:
                raise ValueError("unexpected X observation order")
            self.current_x = values
        else:
            raise ValueError("unrecognized control quantization event")
        return result

    def errors(self, decoded_control, reference):
        control_sums = self.original_errors(decoded_control, reference)
        if self.current_x is None:
            raise ValueError("reference received without X")
        x, self.current_x = self.current_x, None
        layer_id = self.layer_calls % 12
        take = x.shape[0]
        if reference.shape != (take, 99, 256):
            raise ValueError("reference/X shape disagreement")
        for name, candidate in self.results.items():
            p = candidate["layers"][layer_id]
            xi, clips = encode(x, candidate["x_bits"], p["x_exp"])
            yi = self.base.integer_linear(xi, p["wi"], p["bi"])
            decoded = self.np.ldexp(yi.astype(self.np.float64), p["y_exp"])
            if name == "16_16" and not self.np.array_equal(decoded, decoded_control):
                raise ValueError("16/16 observer differs from audited control")
            sums = self.original_errors(decoded, reference)
            if name == "16_16" and any(not self.np.array_equal(sums[k], control_sums[k]) for k in sums):
                raise ValueError("16/16 error observer differs from control")
            if self.offset == 0:
                w, bias = self.parameters[layer_id][:2]
                # The canonical implementation's int16 containers accept all
                # these effective-width values. Explicit width checks prevent
                # a narrower candidate silently retaining an out-of-range code.
                scales = self.fixed.Fixed16Scales(p["x_exp"], p["w_exp"])
                qx, qw, qb = self.fixed.quantize_linear_inputs(x[0].tolist(), w.tolist(), bias.tolist(), scales)
                qy = self.fixed.linear99x64x256(qx, qw, qb)
                for actual, expected in ((xi[0], qx), (p["wi"], qw), (p["bi"], qb), (yi[0], qy)):
                    if not self.np.array_equal(actual, self.np.asarray(expected, dtype=self.np.int64)):
                        raise ValueError("candidate differs from canonical encoding/arithmetic")
                candidate["canonical"].append({"layer_id": layer_id, "status": "PASS", "outputs": 25344})
            candidate["sse"][layer_id].extend(sums["sse"].tolist())
            candidate["energy"][layer_id].extend(sums["reference_energy"].tolist())
            candidate["nrmse"][layer_id].extend(sums["nrmse"].tolist())
            candidate["peak"][layer_id] = max(candidate["peak"][layer_id], float(self.np.max(sums["peak_absolute_error"])))
            candidate["x_clips"][layer_id] += clips
            candidate["output_streams"][layer_id].update(yi.tobytes(order="C"))
            candidate["observed_low"][layer_id] = min(candidate["observed_low"][layer_id], int(self.np.min(yi)))
            candidate["observed_high"][layer_id] = max(candidate["observed_high"][layer_id], int(self.np.max(yi)))
            candidate["metrics"].write(json.dumps({"offset": self.offset, "count": take, "layer_id": layer_id,
                "x_clips": clips, **{k: v.tolist() for k, v in sums.items()}}, separators=(",", ":"), allow_nan=False) + "\n")
        self.layer_calls += 1
        if layer_id == 11:
            self.offset += take
            for candidate in self.results.values():
                candidate["metrics"].flush()
        return control_sums

    def finish(self, expected_samples):
        if self.offset != expected_samples or self.current_x is not None or self.layer_calls % 12:
            raise ValueError("incomplete observer stream")
        reports = []
        for name, candidate in self.results.items():
            layers = []
            for i, item in enumerate(candidate["layers"]):
                row = {k: v for k, v in item.items() if k not in ("wi", "bi")}
                row.update(self.base.aggregate(candidate["sse"][i], candidate["energy"][i], expected_samples))
                worst = max(range(expected_samples), key=lambda j: candidate["nrmse"][i][j])
                row.update(max_sample_nrmse=candidate["nrmse"][i][worst], worst_sample_index=worst,
                           peak_absolute_error=candidate["peak"][i], x_clips=candidate["x_clips"][i],
                           integer_output_stream_sha256=candidate["output_streams"][i].hexdigest(),
                           observed_integer_minimum=candidate["observed_low"][i],
                           observed_integer_maximum=candidate["observed_high"][i])
                layers.append(row)
            max_layer = max(r["nrmse"] for r in layers)
            max_sample = max(r["max_sample_nrmse"] for r in layers)
            clips = sum(r["x_clips"] + r["w_clips"] + r["bias_clips"] for r in layers)
            bias_low = min(r["bias_minimum"] for r in layers)
            bias_high = max(r["bias_maximum"] for r in layers)
            bias_bits = required_signed_bits(bias_low, bias_high)
            reports.append({"candidate": name, "effective_x_bits": candidate["x_bits"],
                            "effective_w_bits": candidate["w_bits"], "bias_bits": 40,
                            "arithmetic_container": "int16 X/W, signed40 bias, exact signed48 output; proposed effective widths only",
                            "layers": layers, "max_layer_nrmse": max_layer, "max_sample_layer_nrmse": max_sample,
                            "clipping_counts_total": clips,
                            "development_3_percent_gate": "PASS" if max_layer <= 0.03 and max_sample <= 0.03 and clips == 0 else "FAIL",
                            "development_precision_score_proxy": precision_score_proxy(max_layer),
                            "precision_score_proxy_scope": "10 - max_layer_nrmse/0.003, clamped at 0; development proxy, not official score",
                            "canonical_first_sample": candidate["canonical"],
                            "generic_bias40_accumulator_bound": accumulator_bound(candidate["x_bits"], candidate["w_bits"], -(1 << 39), (1 << 39) - 1),
                            "checkpoint_bias_bound": {"minimum": bias_low, "maximum": bias_high, "minimum_signed_bits": bias_bits},
                            "checkpoint_restricted_accumulator_bound": accumulator_bound(candidate["x_bits"], candidate["w_bits"], bias_low, bias_high),
                            "proposed_reduced_bias_contract_accumulator_bound": accumulator_bound(candidate["x_bits"], candidate["w_bits"], -(1 << (bias_bits - 1)), (1 << (bias_bits - 1)) - 1),
                            "narrow_bound_condition": "Only valid if hardware rejects biases outside the stated restricted/new bias range; current arbitrary signed40 contract cannot use this narrower accumulator.",
                            "metrics": {"path": name + "-samples.jsonl", "sha256": sha(self.directory / (name + "-samples.jsonl"))}})
        return reports


def run(args):
    for key, value in (("TF_NUM_INTRAOP_THREADS", "2"), ("TF_NUM_INTEROP_THREADS", "1"),
                       ("OMP_NUM_THREADS", "2"), ("CUDA_VISIBLE_DEVICES", "-1")):
        os.environ[key] = value
    sys.dont_write_bytecode = True
    import numpy as np
    import evaluate_kwt_dataset as base
    import export_kwt as exporter
    sys.path.insert(0, str(ROOT))
    from model import fixed16_acc48 as fixed
    inputs = [Path(__file__).resolve(), Path(base.__file__).resolve(), Path(exporter.__file__).resolve(),
              Path(fixed.__file__).resolve(), args.sampling, args.control_result]
    input_records = [{"path": str(p), "sha256": sha(p)} for p in inputs]
    observer = Observer(base, exporter, fixed, np, args.source, args.output)
    control_dir = args.output / "control"
    control_dir.mkdir()
    started = time.monotonic()
    base.quantize_float32, base.error_sums = observer.quantize, observer.errors
    try:
        control = base.evaluate(SimpleNamespace(source=args.source, output=control_dir, data=args.data,
            batch_size=args.batch_size, limit=args.limit, replay_sampling=args.sampling),
            {"schema": "kwt_precision_sweep_control_v1", "status": "FAIL"})
    finally:
        base.quantize_float32, base.error_sums = observer.original_quantize, observer.original_errors
        observer.close()
    write_json(control_dir / "result.json", control)
    if control["status"] != "PASS":
        raise ValueError("audited 16/16 control did not pass")
    previous = json.loads(args.control_result.read_text())
    if previous["status"] != "PASS" or previous["format"] != "fixed16_acc48_v1":
        raise ValueError("reference control report is not a passed fixed16 evaluation")
    count = control["dataset"]["evaluated_samples"]
    # Stronger than merely comparing rounded aggregate numbers: every input SHA
    # and every sample/layer metric must match the frozen earlier evaluation.
    current_samples = (control_dir / control["samples"]["path"]).read_text().splitlines()
    prior_samples_path = args.control_result.parent / previous["samples"]["path"]
    prior_samples_sha = sha(prior_samples_path)
    if prior_samples_sha != previous["samples"]["sha256"]:
        raise ValueError("frozen control sample file SHA mismatch")
    prior_samples = prior_samples_path.read_text().splitlines()
    if len(current_samples) != count or current_samples != prior_samples[:count]:
        raise ValueError("16/16 control samples differ from frozen evaluation")
    if control["dataset"]["sampling"]["sha256"] != previous["dataset"]["sampling"]["sha256"]:
        raise ValueError("sampling changed from frozen control")
    candidates = observer.finish(count)
    if count == previous["dataset"]["evaluated_samples"]:
        for i, layer in enumerate(control["layers"]):
            for key in ("sum_error_sq", "sum_reference_sq", "nrmse", "max_sample_nrmse", "tensor_stream_sha256"):
                if layer[key] != previous["layers"][i][key]:
                    raise ValueError("full control statistic/hash differs: " + key)
    if any(sha(p) != r["sha256"] for p, r in zip(inputs, input_records)) or sha(prior_samples_path) != prior_samples_sha:
        raise ValueError("sweep source/control inputs changed during evaluation")
    return {"schema": "kwt_precision_sweep_v1", "status": "PASS",
            "scope": "software precision sweep completed; individual candidate gates may FAIL",
            "samples": count, "full_validation_samples": control["dataset"]["full_validation_samples"],
            "fp32_inference_passes": 1, "candidate_order": [r["candidate"] for r in candidates],
            "control_comparison": {"status": "PASS", "exact_sample_records_compared": count,
                                   "frozen_result": str(args.control_result), "frozen_samples_sha256": prior_samples_sha},
            "candidates": candidates, "inputs": input_records,
            "control_report": {"path": "control/result.json", "sha256": sha(control_dir / "result.json")},
            "environment": control["environment"], "source": control["source"], "dataset": control["dataset"],
            "implementation": control["implementation"], "elapsed_numerical_seconds": time.monotonic() - started,
            "formal_precision": "NOT_RUN", "rtl_candidates": "NOT_RUN", "specified_process_ppa": "NOT_RUN",
            "limitations": ["Uses TF2.4.0 fallback rather than official rc1 certification.",
                            "FP32 activations are evaluated independently; this does not measure quantized full-network classification accuracy.",
                            "Development score proxies do not predict official score or award.",
                            "Software passing widths do not establish area, speed or power; no RTL widths are changed."],
            "end_marker": END_MARKER}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "vendor/kwt1-237e4097")
    parser.add_argument("--data", type=Path, default=ROOT / "data/speech-commands-v0.02")
    parser.add_argument("--sampling", type=Path, required=True)
    parser.add_argument("--control-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)
    if not 1 <= args.batch_size <= 64 or args.limit < 0:
        parser.error("batch-size must be 1..64 and limit nonnegative")
    for key in ("source", "data", "sampling", "control_result", "output"):
        setattr(args, key, getattr(args, key).resolve())
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    try:
        report, code = run(args), 0
    except Exception as exc:
        report, code = {"schema": "kwt_precision_sweep_v1", "status": "FAIL", "error": str(exc),
                        "error_type": type(exc).__name__, "traceback": traceback.format_exc()}, 1
        traceback.print_exc()
    report.update(command=[sys.executable, *sys.argv], exit_code=code,
                  created_utc=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic() - started)
    write_json(args.output / "result.json", report)
    if code == 0:
        print(END_MARKER + " " + json.dumps({"status": report["status"], "samples": report["samples"],
              "candidates": [{k: r[k] for k in ("candidate", "max_layer_nrmse", "max_sample_layer_nrmse",
                             "development_3_percent_gate", "development_precision_score_proxy")} for r in report["candidates"]],
              "elapsed_seconds": report["elapsed_seconds"]}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
