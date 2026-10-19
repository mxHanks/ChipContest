#!/usr/bin/env python3
"""Double-row engine experiment with strict bit agreement and scoped cycle evidence.

Standalone from the frozen migration runners. Compare runs with --compare PATH...
Only --stalls none gives a deterministic throughput comparison. Neither simulation
cycles nor RTL memory enables establish SoC timing, SRAM energy, area, or power.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_linear as LINEAR
import run_exported_linear as EXPORTED
import run_engine_benchmark as BASE
COMMON = LINEAR.COMMON
OUTPUTS = 99 * 256
LOAD_WORDS = 6336 + 16384 + 256
SCHEMA = "kwt-rowpair-benchmark-v1"
TASK_KEYS = ("task", "outputs", "core_cycles", "load_words", "load_cycles", "output_stalls",
             "x_reads", "w_reads", "b_reads", "window_cycles", "result_reads", "result_writes", "overlap_cycles", "buffer_wait_cycles")
SUITE_KEYS = ("tasks", "outputs", "reset_interrupts", "illegal_load_cases", "input_bubbles",
              "output_stall_cycles", "stable_output_checks", "busy_load_rejections", "testbench_window_cycles")


def generate_range_vectors(out, tasks, model):
    """Both universal signed41 endpoints; every output also exercises sign extension."""
    vector_dir = out / "vectors"
    vector_dir.mkdir()
    manifest = {"format": "fixed16_acc48_v1", "scope": "universal signed41 accumulation boundaries", "tasks": tasks, "cases": []}
    for task in range(tasks):
        xv, wv, bv = (-32768, -32768, (1 << 39)-1) if task % 2 == 0 else (-32768, 32767, -(1 << 39))
        x, w, bias = [[xv]*64 for _ in range(99)], [[wv]*256 for _ in range(64)], [bv]*256
        golden = model.linear99x64x256(x, w, bias)
        endpoint = bv + 64*xv*wv
        if any(v != endpoint for row in golden for v in row):
            raise ValueError("canonical model disagrees with independent universal endpoint")
        files = []
        for role, values, bits in (("x", (v for row in x for v in row),16), ("w", (v for row in w for v in row),16), ("b",bias,40), ("y", (v for row in golden for v in row),48)):
            path = vector_dir / f"task_{task:02d}_{role}.mem"
            image = model.write_hex_mem(path, values, bits)
            files.append(dict(LINEAR.file_record(path),role=role,bits=bits,count=image["count"]))
        manifest["cases"].append({"task":task,"category":"signed41_max" if task%2==0 else "signed41_min", "endpoint":endpoint, "files":files})
    path = vector_dir / "manifest.json"
    path.write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest, LINEAR.file_record(path)


def expected_metrics(config):
    if config["engine"] != "rowpair" or config["lanes"] != 8 or config["pipe_mul"] not in (0, 1) or config["result_buffers"] not in (1, 2):
        raise ValueError("invalid rowpair configuration")
    # 50 pairs, 32 tiles per pair; final snapshot flush takes 16 (tail 8) clocks.
    # A pair handover costs one clock; final synchronous output takes 258 clocks.
    # Two buffers hide all earlier emissions; one buffer serializes them.
    tile = 66 + config["pipe_mul"]
    return {"core_cycles_without_stalls": (50 * 32 * tile + 49 * 17 + 8 + 258 if config["result_buffers"] == 2 else 50 * 32 * tile + 49 * 531 + 8 + 258),
            "x_reads": 99 * 32 * 64, "w_reads": 50 * 256 * 64,
            "b_reads": 50 * 256}


def check_completion(command, output, config):
    error = COMMON.completion_error(command, output, [])
    if error:
        return error, None
    expected = expected_metrics(config)
    task_pattern = r"^PASS ROWPAIR_BENCH_TASK " + " ".join(key + r"=(\d+)" for key in TASK_KEYS) + "$"
    matches = re.findall(task_pattern, output, re.M)
    if len(matches) != config["tasks"]:
        return "missing or duplicate task completion markers", None
    tasks = [dict(zip(TASK_KEYS, map(int, match))) for match in matches]
    for index, task in enumerate(tasks):
        if task["task"] != index or task["outputs"] != OUTPUTS or task["load_words"] != LOAD_WORDS:
            return "task order/output/load conservation mismatch", None
        if task["load_cycles"] < LOAD_WORDS or task["window_cycles"] < task["load_cycles"] + task["core_cycles"]:
            return "load/window cycles inconsistent", None
        if any(task[key] != expected[key] for key in ("x_reads", "w_reads", "b_reads")):
            return "observed memory read-enable count differs from architecture", None
        if not expected["core_cycles_without_stalls"] <= task["core_cycles"] <= expected["core_cycles_without_stalls"] + task["output_stalls"]:
            return "core cycles outside measured backpressure bounds", None
        if config["stalls"] == "none" and task["core_cycles"] != expected["core_cycles_without_stalls"]:
            return "no-stall cycles do not match controller schedule", None
        if config["stalls"] == "none" and task["output_stalls"] != 0:
            return "unexpected stalls in no-stall benchmark", None
        if task["result_reads"] != OUTPUTS or task["result_writes"] != OUTPUTS:
            return "result-buffer word conservation mismatch", None
        if config["result_buffers"] == 2 and task["overlap_cycles"] <= 0:
            return "missing compute/writeback overlap", None
        if config["stalls"] == "random" and task["buffer_wait_cycles"] <= 0:
            return "missing queue-exhaustion backpressure coverage", None
        if config["stalls"] == "random" and task["output_stalls"] <= 0:
            return "missing per-task output backpressure coverage", None
    suite_pattern = (r"^PASS ROWPAIR_BENCH_SUITE tasks=(\d+) outputs=(\d+) resets=(\d+) illegal=(\d+) "
                     r"input_bubbles=(\d+) stalls=(\d+) stable=(\d+) busy_load_rejections=(\d+) full_window_cycles=(\d+)$")
    suites = re.findall(suite_pattern, output, re.M)
    if len(suites) != 1:
        return "missing or duplicate complete-suite marker", None
    suite = dict(zip(SUITE_KEYS, map(int, suites[0])))
    if (suite["tasks"] != config["tasks"] or suite["outputs"] != config["tasks"] * OUTPUTS
            or suite["reset_interrupts"] != 3 or suite["illegal_load_cases"] != 3
            or suite["busy_load_rejections"] <= 0
            or suite["testbench_window_cycles"] < sum(t["window_cycles"] for t in tasks)):
        return "suite conservation/protocol/reset coverage mismatch", None
    stalls = sum(t["output_stalls"] for t in tasks)
    if suite["output_stall_cycles"] != stalls or suite["stable_output_checks"] != stalls:
        return "stall/stability accounting mismatch", None
    if config["stalls"] == "none" and (suite["input_bubbles"] or stalls):
        return "no-stall suite contains random bubbles or stalls", None
    if config["stalls"] == "random" and (suite["input_bubbles"] <= 0 or stalls <= 0):
        return "random suite lacks input/output backpressure coverage", None
    return None, {"per_task": tasks, "suite": suite, "expected": expected,
                  "timing_scope": "RTL load/start/output testbench only; no E203, bus, host, or official writeback timing",
                  "memory_scope": "observed RTL read enables in 16-bit X/W and 40-bit bias words; not SRAM energy"}


def assert_record_unchanged(record):
    path = Path(record["path"])
    actual = LINEAR.file_record(path)
    if actual["sha256"] != record["sha256"] or actual["size_bytes"] != record["size_bytes"]:
        raise ValueError("evidence/input changed: " + str(path))


def vector_identity(records):
    """Ignore temporary paths; bind ordered word images to compare the same work."""
    return hashlib.sha256(json.dumps([r["sha256"] for r in records], separators=(",", ":")).encode()).hexdigest()


def comparison_report(paths):
    """Revalidate logs and bound inputs instead of trusting a PASS string."""
    entries = []
    for path in paths:
        path = Path(path).resolve()
        result = json.loads(path.read_text())
        if result.get("schema") not in (SCHEMA, BASE.SCHEMA) or result.get("status") != "PASS":
            raise ValueError("comparison needs successful engine benchmark: " + str(path))
        records = [*result["inputs"], *result["replayed_vectors"], *result.get("provenance", [])]
        records += [command["log"] for command in result["commands"]]
        for record in records:
            assert_record_unchanged(record)
        if result["workload_sha256"] != vector_identity(result["replayed_vectors"]):
            raise ValueError("workload identity mismatch")
        command = result["commands"][-1]
        checker = check_completion if result["schema"] == SCHEMA else BASE.check_completion
        error, coverage = checker(command, COMMON.log_text(command), result["configuration"])
        if error or coverage != result["rtl"]["coverage"]:
            raise ValueError("result is not supported by original complete simulation log: " + str(error))
        tasks = coverage["per_task"]
        config = result["configuration"]
        entries.append({"result": LINEAR.file_record(path), "engine": config["engine"], "lanes": config["lanes"],
                        "pipe_mul": config["pipe_mul"], "result_buffers": config.get("result_buffers"), "stalls": config["stalls"], "tasks": config["tasks"],
                        "seed": config["seed"], "simulator": result["simulator"], "workload_sha256": result["workload_sha256"],
                        "core_cycles_total": sum(t["core_cycles"] for t in tasks),
                        "load_cycles_total": sum(t["load_cycles"] for t in tasks),
                        "testbench_window_cycles_total": sum(t["window_cycles"] for t in tasks),
                        "output_stalls_total": sum(t["output_stalls"] for t in tasks),
                        "x_read_words_total": sum(t["x_reads"] for t in tasks),
                        "w_read_words_total": sum(t["w_reads"] for t in tasks),
                        "bias_read_words_total": sum(t["b_reads"] for t in tasks)})
    keys = ("stalls", "tasks", "seed", "workload_sha256")
    if any(any(entry[key] != entries[0][key] for key in keys) for entry in entries):
        raise ValueError("comparison requires identical word images, tasks, seed, and stall policy")
    baseline = entries[0]
    for entry in entries:
        entry["relative_to_first_core_cycle_ratio"] = baseline["core_cycles_total"] / entry["core_cycles_total"]
    return {"schema": "kwt-engine-comparison-v1", "status": "PASS", "created_utc": COMMON.utc_now(),
            "scope": "same-workload RTL simulation; cycle ratio is not SoC speedup or frequency gain",
            "comparison_kind": "deterministic no-stall" if baseline["stalls"] == "none" else "seeded backpressure (different elapsed cycles can alter stall schedule)",
            "soc": "NOT_RUN", "timing": "NOT_RUN", "area": "NOT_RUN", "power": "NOT_RUN", "runs": entries}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.set_defaults(engine="rowpair", lanes=8)
    parser.add_argument("--result-buffers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--pipe-mul", type=int, choices=(0, 1), default=None)
    parser.add_argument("--tasks", type=int, choices=range(2, 33), default=12)
    parser.add_argument("--stalls", choices=("none", "random"), default="none")
    parser.add_argument("--vectors", choices=("synthetic", "kwt-silence", "range"), default="synthetic")
    parser.add_argument("--vectors-dir", type=lambda p: Path(p).resolve())
    parser.add_argument("--source-root", type=lambda p: Path(p).resolve(), default=ROOT / "vendor/kwt1-237e4097")
    parser.add_argument("--simulator", choices=("verilator", "iverilog"), default="verilator")
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--vcd", action="store_true", help="trace first completed task's core/start/output window only")
    parser.add_argument("--compile-timeout", type=int, default=180)
    parser.add_argument("--sim-timeout", type=int, default=240)
    parser.add_argument("--compare", type=Path, nargs="+", help="verify and compare existing result.json files instead of simulating")
    args = parser.parse_args(argv)
    if min(args.compile_timeout, args.sim_timeout) <= 0 or not 0 <= args.seed <= 0x7fffffff:
        parser.error("timeouts must be positive; seed must fit nonnegative signed32")
    pipe_mul = (0 if args.engine == "baseline" else 1) if args.pipe_mul is None else args.pipe_mul
    if args.engine == "baseline" and pipe_mul:
        parser.error("baseline has no multiplier pipeline; use --pipe-mul 0")
    if (args.vectors_dir or args.vectors == "kwt-silence") and args.tasks > 12:
        parser.error("an exported KWT fixture contains only 12 layers")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-rowpair-bench-" + uuid.uuid4().hex[:8]
    out = ROOT / "artifacts/runs" / run_id
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    if args.compare:
        try:
            report = comparison_report(args.compare)
        except Exception as exc:
            report = {"schema": "kwt-engine-comparison-v1", "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
        (out / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"status": report["status"], "output": str(out / "comparison.json"), "error": report.get("error")}))
        return 0 if report["status"] == "PASS" else 1
    config = {"format": "fixed16_acc48_v1", "shape": {"x": [99, 64], "w": [64, 256], "y": [99, 256]},
              "engine": args.engine, "lanes": args.lanes, "pipe_mul": pipe_mul, "stalls": args.stalls,
              "tasks": args.tasks, "seed": args.seed, "compile_jobs": 2, "macs": 16, "rows_per_tile": 2, "result_buffers": args.result_buffers}
    source = ROOT / "src/rtl/kwt_linear_engine_rowpair.sv"
    sources = [source, ROOT / "sim/tb_rowpair_benchmark.sv"]
    model_path = ROOT / "model/fixed16_acc48.py"
    inputs = [Path(__file__), ROOT / "scripts/verify/run_linear.py", ROOT / "scripts/verify/run_exported_linear.py",
              ROOT / "scripts/verify/run_checks.py", ROOT / "scripts/verify/run_engine_benchmark.py", model_path, *sources]
    result = {"schema": SCHEMA, "status": "FAIL", "run_id": run_id, "started_utc": COMMON.utc_now(),
              "output": str(out), "configuration": config, "simulator": args.simulator,
              "logic_semantics": "four-state" if args.simulator == "iverilog" else "two-state",
              "scope": "full-shape synthetic arithmetic and engine protocol only", "python_version": sys.version,
              "official_precision": "NOT_RUN", "validation_dataset_precision": "NOT_RUN", "soc": "NOT_RUN",
              "synthesis": "NOT_RUN", "timing": "NOT_RUN", "area": "NOT_RUN", "power": "NOT_RUN",
              "inputs": [], "provenance": [], "replayed_vectors": [], "tools": {}, "commands": [],
              "vectors": {"status": "NOT_RUN"}, "rtl": {"status": "NOT_RUN"}}
    try:
        missing = [str(p) for p in inputs if not p.is_file()]
        if missing:
            result.update(status="BLOCKED", error="missing required source: " + ", ".join(missing))
        else:
            result["inputs"] = [LINEAR.file_record(p) for p in inputs]
            config_path = out / "config.json"
            config_path.write_text(json.dumps(config, indent=2) + "\n")
            result["config_file"] = LINEAR.file_record(config_path)
            model = LINEAR.load_module("kwt_benchmark_numeric_model", model_path)
            if args.vectors_dir or args.vectors == "kwt-silence":
                vector_root = args.vectors_dir or ROOT / "sim/vectors/kwt-silence-v1"
                manifest, provenance, images = EXPORTED.validate_export(vector_root, model, source_root=args.source_root)
                result["provenance"] = provenance
                result["vectors"] = {"status": "PASS", "kind": manifest["input"]["kind"], "verified_layers": 12,
                                     "golden_words_recomputed": 12 * OUTPUTS, "manifest": provenance[0]}
                result["scope"] = "real checkpoint weights with one waveform/synthetic silence smoke; not dataset precision"
                (out / "vectors").mkdir()
                for task, image in enumerate(images[:args.tasks]):
                    for role in ("x", "w", "bias", "y"):
                        target = out / "vectors" / f"task_{task:02d}_{'b' if role == 'bias' else role}.mem"
                        target.write_bytes(image[role])
                        result["replayed_vectors"].append(LINEAR.file_record(target))
            else:
                manifest, record = (generate_range_vectors(out, args.tasks, model) if args.vectors == "range" else LINEAR.generate_vectors(out, args.tasks, args.seed, model))
                result["vectors"] = {"status": "PASS", "kind": "synthetic integer matrices", "manifest": record,
                                     "categories": [case["category"] for case in manifest["cases"]]}
                result["replayed_vectors"] = [file for case in manifest["cases"] for file in case["files"]]
            result["workload_sha256"] = vector_identity(result["replayed_vectors"])
            needed = ["iverilog", "vvp"] if args.simulator == "iverilog" else ["verilator", "make", "g++"]
            for name in needed:
                result["tools"][name] = COMMON.tool_info(name, out, 2)
            if not all(shutil.which(name) for name in needed):
                result.update(status="BLOCKED", error="missing simulator/build dependency", rtl={"status": "BLOCKED"})
            else:
                macros = (["-DBENCH_OPT", "-DBENCH_BANKED"] if args.engine == "banked" else ["-DBENCH_OPT"] if args.engine == "opt" else [])
                if args.simulator == "verilator":
                    binary = out / "obj/simulation"
                    compile_argv = [shutil.which("verilator"), "--binary", "--timing", "--assert", "-Wno-fatal",
                                    "--top-module", "tb_rowpair_benchmark", "--Mdir", str(out / "obj"), "-o", "simulation",
                                    "-j", "2", "--threads", "1", f"-GRESULT_BUFFERS={args.result_buffers}", f"-GPIPE_MUL={pipe_mul}", *macros]
                    if args.vcd:
                        compile_argv += ["--trace", "--trace-depth", "2", "--trace-max-array", "32"]
                    compile_argv += list(map(str, sources))
                    run_argv = [str(binary)]
                else:
                    binary = out / "simulation.vvp"
                    compile_argv = [shutil.which("iverilog"), "-g2012", "-s", "tb_rowpair_benchmark", "-o", str(binary),
                                    f"-Ptb_rowpair_benchmark.RESULT_BUFFERS={args.result_buffers}", f"-Ptb_rowpair_benchmark.PIPE_MUL={pipe_mul}",
                                    *macros, *map(str, sources)]
                    run_argv = [shutil.which("vvp"), str(binary)]
                command = COMMON.run_command(compile_argv, out, out / "compile.log", args.compile_timeout, 2)
                result["commands"].append(command)
                result["rtl"] = {"status": "FAIL"}
                if command.get("exit_code") != 0 or command["timed_out"] or not binary.is_file():
                    result["error"] = "compilation failed/timed out; inspect compile.log"
                else:
                    result["binary"] = LINEAR.file_record(binary)
                    run_argv += [f"+VECTORS={out / 'vectors'}", f"+TASKS={args.tasks}", f"+SEED={args.seed}",
                                 f"+RANDOM_STALLS={int(args.stalls == 'random')}"]
                    if args.vcd:
                        run_argv += [f"+VCD={out / 'core-task0.vcd'}"]
                    command = COMMON.run_command(run_argv, out, out / "run.log", args.sim_timeout, 2)
                    result["commands"].append(command)
                    error, coverage = check_completion(command, COMMON.log_text(command), config)
                    if error:
                        result["error"] = error
                    else:
                        result.update(status="PASS", rtl={"status": "PASS", "coverage": coverage})
                    if args.vcd:
                        trace = out / "core-task0.vcd"
                        if not trace.is_file() or trace.stat().st_size == 0:
                            result.update(status="FAIL", error="requested VCD missing or empty")
                        else:
                            result["activity_trace"] = {**LINEAR.file_record(trace), "scope": "first completed task core/start/output only, no full SoC window"}
            for record in [*result["inputs"], *result["provenance"], *result["replayed_vectors"]]:
                assert_record_unchanged(record)
    except Exception as exc:
        result.update(status="FAIL", error=f"{type(exc).__name__}: {exc}")
    finally:
        result.update(finished_utc=COMMON.utc_now(), elapsed_seconds=round(time.monotonic()-started, 3))
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "scope", "output", "elapsed_seconds")}, ensure_ascii=False))
    if result.get("error"):
        print(result["error"], file=sys.stderr)
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
