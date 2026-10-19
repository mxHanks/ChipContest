#!/usr/bin/env python3
"""Full-shape synthetic bit-exact KWT linear RTL regression, not model accuracy."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import re
import shutil
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
ROWS, INNER, COLS = 99, 64, 256
OUTPUTS = ROWS * COLS


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


COMMON = load_module("kwt_checks_common", ROOT / "scripts/verify/run_checks.py")


def file_record(path):
    result = COMMON.record(path)
    path = Path(path).resolve()
    if path.is_relative_to(ROOT):
        result["project_relative_path"] = path.relative_to(ROOT).as_posix()
    return result


def generate_case(task, seed):
    """Full matrices with explicit zero/extreme/cancellation/indexing coverage."""
    rng = random.Random(seed + task * 100003)
    kind = task % 6
    extreme = [-32768, 32767, -1, 0, 1, 16384, -16384]
    x = [[rng.randrange(-32768, 32768) for _ in range(INNER)] for _ in range(ROWS)]
    w = [[rng.randrange(-32768, 32768) for _ in range(COLS)] for _ in range(INNER)]
    bias = [rng.randrange(-(1 << 39), 1 << 39) for _ in range(COLS)]
    for c, value in enumerate([-(1 << 39), (1 << 39)-1, -1, 0, 1, -(1 << 32), 1 << 32]):
        bias[c] = value
    if kind == 0:
        x = [[extreme[(r+k+task) % len(extreme)] for k in range(INNER)] for r in range(ROWS)]
        w = [[extreme[(k+3*c+task) % len(extreme)] for c in range(COLS)] for k in range(INNER)]
        # Worst-case full dot products, plus mixed-sign ones in other columns.
        x[0] = [-32768] * INNER
        for k in range(INNER):
            w[k][0], w[k][1] = -32768, 32767
    elif kind == 1:
        x = [[0] * INNER for _ in range(ROWS)]
    elif kind == 2:
        w = [[0] * COLS for _ in range(INNER)]
    elif kind == 3:
        x = [[(r+1)*(1 if (r+task) % 2 else -1) if k == r % INNER else 0
              for k in range(INNER)] for r in range(ROWS)]
        w = [[((k * COLS + c + task) % 65536)-32768 for c in range(COLS)] for k in range(INNER)]
    elif kind == 5:
        # Every adjacent nonzero product pair cancels exactly. Alternating X
        # and W signs together would instead make all products the same sign.
        x = [[(-32768 if r % 2 == 0 else 32767) for _ in range(INNER)] for r in range(ROWS)]
        w = [[((c+task) % 32768) * (-1 if k % 2 else 1) for c in range(COLS)] for k in range(INNER)]
    return x, w, bias, ["extremes", "zero_x_bias", "zero_w_bias", "row_column_index", "random", "cancellation"][kind]


def generate_vectors(out, tasks, seed, model):
    vector_dir = out / "vectors"
    vector_dir.mkdir()
    manifest = {"format": "fixed16_acc48_v1", "scope": "synthetic integer functional vectors",
                "seed": seed, "tasks": tasks, "shape": {"x": [ROWS, INNER], "w": [INNER, COLS], "y": [ROWS, COLS]},
                "layout": "row-major W[k][column]", "cases": []}
    for task in range(tasks):
        x, w, bias, category = generate_case(task, seed)
        golden = model.linear99x64x256(x, w, bias)
        # A differently ordered, dot-product oracle checks every golden word.
        # Neither oracle reads RTL internals or the simulator's output.
        columns = list(zip(*w))
        for r, row in enumerate(x):
            for c, column in enumerate(columns):
                independent = bias[c] + sum(a*b for a, b in zip(row, column))
                if golden[r][c] != independent:
                    raise ValueError(f"software golden disagreement task={task} row={r} column={c}")
                if category == "cancellation" and independent != bias[c]:
                    raise ValueError(f"cancellation vector did not cancel task={task} row={r} column={c}")
        files = []
        for name, data, bits in (("x", (v for row in x for v in row), 16),
                                 ("w", (v for row in w for v in row), 16),
                                 ("b", bias, 40),
                                 ("y", (v for row in golden for v in row), 48)):
            path = vector_dir / f"task_{task:02d}_{name}.mem"
            image = model.write_hex_mem(path, data, bits)
            files.append(dict(file_record(path), bits=bits, count=image["count"], role=name))
        manifest["cases"].append({"task": task, "category": category, "files": files})
    manifest_path = vector_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest, file_record(manifest_path)


def check_completion(command, output, tasks):
    errors = COMMON.completion_error(command, output, [])
    if errors:
        return errors, None
    task_matches = re.findall(r"^PASS KWT_LINEAR_TASK task=(\d+) outputs=(\d+) core_cycles=(\d+)$", output, re.M)
    if len(task_matches) != tasks:
        return "missing or duplicate task completion markers", None
    for expected, (task, outputs, cycles) in enumerate(task_matches):
        if int(task) != expected or int(outputs) != OUTPUTS or int(cycles) < 231264:
            return "incorrect task order, output count or core cycle count", None
    suite = re.findall(r"^PASS KWT_LINEAR_SUITE tasks=(\d+) outputs=(\d+) resets=(\d+) illegal=(\d+) input_bubbles=(\d+) stalls=(\d+) stable=(\d+) busy_load_rejections=(\d+) full_window_cycles=(\d+)$", output, re.M)
    if len(suite) != 1:
        return "missing or duplicate complete-suite marker", None
    counts = list(map(int, suite[0]))
    if counts[:4] != [tasks, tasks*OUTPUTS, 1, 3] or min(counts[4:]) <= 0:
        return "suite coverage/count mismatch", None
    coverage = dict(zip(("tasks", "outputs", "reset_interrupts", "illegal_load_cases", "input_bubbles",
                         "output_stall_cycles", "stable_output_checks", "busy_load_rejections", "testbench_window_cycles"), counts))
    coverage["per_task_core_cycles"] = [int(values[2]) for values in task_matches]
    coverage["timing_scope"] = "testbench load/start/output/verification window; excludes E203/bus and is not contest timing"
    return None, coverage


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, choices=range(2, 33), default=12)
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--simulator", choices=("verilator", "iverilog"), default="verilator")
    parser.add_argument("--compile-timeout", type=int, default=180)
    parser.add_argument("--sim-timeout", type=int, default=180)
    args = parser.parse_args(argv)
    if min(args.compile_timeout, args.sim_timeout) <= 0:
        parser.error("timeouts must be positive")
    if not 0 <= args.seed <= 0x7fffffff:
        parser.error("seed must fit a nonnegative signed 32-bit integer")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-linear-" + uuid.uuid4().hex[:8]
    out = ROOT / "artifacts/runs" / run_id
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    model_path = ROOT / "model/fixed16_acc48.py"
    sources = [ROOT / "src/rtl/kwt_linear_engine.sv", ROOT / "sim/tb_kwt_linear_engine.sv"]
    inputs = [Path(__file__), ROOT / "scripts/verify/run_checks.py", model_path, *sources]
    result = {"schema": "kwt-linear-checks-v1", "status": "FAIL", "run_id": run_id,
              "scope": "new-KWT fixed16_acc48_v1 full-shape synthetic RTL bit agreement and protocol",
              "started_utc": COMMON.utc_now(), "output": str(out),
              "configuration": {"format": "fixed16_acc48_v1", "rows": ROWS, "inner": INNER, "cols": COLS,
                                "lanes": 8, "tasks": args.tasks, "seed": args.seed, "compile_jobs": 2},
              "simulator": args.simulator, "logic_semantics": "four-state" if args.simulator == "iverilog" else "two-state",
              "real_kwt_accuracy": "NOT_RUN", "actual_12_layer_parameters": "NOT_RUN", "soc": "NOT_RUN",
              "synthesis": "NOT_RUN", "timing": "NOT_RUN", "area": "NOT_RUN", "power": "NOT_RUN",
              "tools": {}, "commands": [], "inputs": [], "vectors": {"status": "NOT_RUN"},
              "rtl": {"status": "NOT_RUN"}, "python_version": sys.version}
    try:
        missing = [str(p) for p in inputs if not p.is_file()]
        if missing:
            result.update(status="BLOCKED", error="missing source/model: " + ", ".join(missing))
            return_code = 2
        else:
            result["inputs"] = [file_record(p) for p in inputs]
            config_path = out / "config.json"
            config_path.write_text(json.dumps(result["configuration"], sort_keys=True, indent=2) + "\n")
            result["config_file"] = file_record(config_path)
            model = load_module("kwt_fixed16_model", model_path)
            vector_start = time.monotonic()
            manifest, manifest_record = generate_vectors(out, args.tasks, args.seed, model)
            result["vectors"] = {"status": "PASS", "manifest": manifest_record, "cases": manifest["cases"],
                                 "elapsed_seconds": round(time.monotonic()-vector_start, 3),
                                 "golden_check": "entire model output checked with independent dot-product ordering"}
            needed = ["iverilog", "vvp"] if args.simulator == "iverilog" else ["verilator", "make", "g++"]
            for tool in needed:
                result["tools"][tool] = COMMON.tool_info(tool, out, 2)
            if not all(shutil.which(tool) for tool in needed):
                result.update(status="BLOCKED", error="simulator/build dependencies missing")
                result["rtl"] = {"status": "BLOCKED"}
            else:
                if args.simulator == "verilator":
                    binary = out / "obj/simulation"
                    compile_argv = [shutil.which("verilator"), "--binary", "--timing", "--assert", "-Wno-fatal",
                                    "--top-module", "tb_kwt_linear_engine", "--Mdir", str(out / "obj"),
                                    "-o", "simulation", "-j", "2", "--threads", "1", *map(str, sources)]
                    run_argv = [str(binary)]
                else:
                    binary = out / "simulation.vvp"
                    compile_argv = [shutil.which("iverilog"), "-g2012", "-s", "tb_kwt_linear_engine", "-o", str(binary), *map(str, sources)]
                    run_argv = [shutil.which("vvp"), str(binary)]
                command = COMMON.run_command(compile_argv, out, out / "compile.log", args.compile_timeout, 2)
                result["commands"].append(command)
                result["rtl"] = {"status": "FAIL"}
                if command.get("exit_code") != 0 or command["timed_out"] or not binary.is_file():
                    result["error"] = "compilation failed/timed out; see compile.log"
                else:
                    result["binary"] = file_record(binary)
                    command = COMMON.run_command(run_argv + [f"+VECTORS={out / 'vectors'}", f"+TASKS={args.tasks}", f"+SEED={args.seed}"],
                                                 out, out / "run.log", args.sim_timeout, 2)
                    result["commands"].append(command)
                    error, coverage = check_completion(command, COMMON.log_text(command), args.tasks)
                    if error:
                        result["error"] = error
                    else:
                        result["rtl"] = {"status": "PASS", "coverage": coverage}
                        result["status"] = "PASS"
            # Bind evidence to the exact bytes used, and detect edits during a run.
            changed = [item["path"] for item in result["inputs"]
                       if file_record(item["path"])["sha256"] != item["sha256"]]
            for case in result["vectors"].get("cases", []):
                changed += [item["path"] for item in case["files"]
                            if file_record(item["path"])["sha256"] != item["sha256"]]
            if changed:
                result.update(status="FAIL", error="inputs changed during run", changed_inputs=changed)
            return_code = {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[result["status"]]
    except Exception as exc:
        result.update(status="FAIL", error=f"{type(exc).__name__}: {exc}")
        return_code = 1
    finally:
        result.update(finished_utc=COMMON.utc_now(), elapsed_seconds=round(time.monotonic()-start, 3))
        (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "scope", "output", "elapsed_seconds")}, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
