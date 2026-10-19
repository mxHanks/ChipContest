#!/usr/bin/env python3
"""Run bounded migration checks; FPT reference success is never KWT acceptance."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "vendor/fpt-r1"
DEFAULT_GROUPS = ["reset_edges", "async_fifo", "slot_bank", "service_observer",
                  "service_counter_adapter"]
MARKERS = {
    "qk_service_behavior": r"^PASS: CATS-R4 32-lane FP32 accumulator context isolation and score commit$",
    "qk_scheduler_protocol": r"^PASS: CATS-R4 R16/32-lane QK scheduler jobs=6144 valid_macs=33816576$",
    "banked_owner": r"^PASS: CATS_R4_IF_V2 Q/KV ownership, 32 slabs, N\+2/II1$",
    "slot_bank": r"^PASS cats_r4_slot_bank collision/owner/backpressure$",
    "async_fifo": r"^CATS-R4 async FIFO test: PASS$",
    "reset_edges": r"^PASS RESET_SYNC_EDGES stages=3 hold=16 half=5 checks=[1-9][0-9]* assertions=13 stopped_clock=1$",
    "bank_bridge_behavior": r"^PASS: CATS-R4 AXI/core bank bridge descriptors, counters, and readback$",
    "service_observer": r"^PASS CORE_SERVICE_OBSERVER scenarios=7 clusters=4 rows_per_cluster=2$",
    "service_counter_adapter": r"^PASS CORE_SERVICE_COUNTER_ADAPTER scenarios=9 clusters=4 rows_per_cluster=2$",
}
FAILURE = re.compile(r"(?:^|\n)\s*(?:%Error\b|FATAL\b|ERROR\b|FAIL\b)|\b(?:Aborting|Assertion failed)\b", re.I)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def record(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size}


def aggregate(items):
    statuses = [x["status"] for x in items]
    return next((s for s in ("FAIL", "BLOCKED", "PASS") if s in statuses), "NOT_RUN")


def completion_error(command, output, required_markers):
    """Exit zero / $finish alone cannot prove the requested scenario completed."""
    if command.get("timed_out"):
        return "wall-clock timeout"
    if command.get("exit_code") != 0:
        return "command did not exit successfully"
    if FAILURE.search(output):
        return "failure diagnostic in simulation log"
    for marker in required_markers:
        if not re.search(marker, output, re.M):
            return "missing complete-scenario marker: " + marker
    return None


def child_limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run_command(argv, cwd, log, timeout, jobs):
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", MAKEFLAGS=f"-j{jobs}")
    result = {"argv": list(map(str, argv)), "cwd": str(cwd), "started_utc": utc_now(),
              "timeout_seconds": timeout, "timed_out": False}
    start = time.monotonic()
    try:
        with Path(log).open("x", encoding="utf-8") as stream:
            process = subprocess.Popen(result["argv"], cwd=cwd, env=env,
                                       stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True, preexec_fn=child_limits)
            try:
                result["exit_code"] = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                result["timed_out"] = True
                # Terminate compiler descendants as well as the launcher.
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                result["exit_code"] = process.wait()
    except OSError as exc:
        result.update(exit_code=None, error=str(exc))
    result.update(finished_utc=utc_now(), elapsed_seconds=round(time.monotonic() - start, 3))
    if Path(log).exists():
        result["log"] = record(log)
    return result


def log_text(command):
    return Path(command["log"]["path"]).read_text(errors="replace") if "log" in command else ""


def tool_info(name, run_dir, jobs):
    path = shutil.which(name)
    if not path:
        return {"status": "BLOCKED", "reason": "not found on PATH"}
    flag = "-V" if name in ("iverilog", "vvp") else "--version"
    safe_name = re.sub(r"[^A-Za-z0-9_.+-]", "_", name)
    command = run_command([path, flag], ROOT, run_dir / f"version-{safe_name}.log", 15, jobs)
    return {"status": "PASS" if command.get("exit_code") == 0 else "FAIL",
            "executable": record(path), "version": log_text(command).strip(), "command": command}


def static_check(out, args):
    command = run_command([sys.executable, BUNDLE / "tools/verify_bundle.py"], ROOT,
                          out / "static.log", args.host_timeout, args.jobs)
    result = {"status": "FAIL", "scope": "import integrity, declared dependencies and Python syntax",
              "command": command}
    try:
        details = json.loads(log_text(command))
        result["details"] = details
        if command.get("exit_code") == 0 and not command["timed_out"] and details.get("status") == "PASS":
            result["status"] = "PASS"
    except (ValueError, TypeError) as exc:
        result["error"] = str(exc)
    return result


def host_check(out, args):
    result = {"status": "BLOCKED", "scope": "FPT numeric helpers and fake-MMIO C reader only"}
    if not shutil.which(args.cc):
        result["reason"] = "C compiler not found: " + args.cc
        return result
    command = run_command([sys.executable, BUNDLE / "tools/run_host_checks.py", "--output",
                           out / "host", "--cc", args.cc], ROOT, out / "host.log",
                          args.host_timeout, args.jobs)
    result.update(command=command, status="FAIL")
    detail_path = out / "host/result.json"
    try:
        details = json.loads(detail_path.read_text())
        result.update(details=details, result_file=record(detail_path))
        c_log = out / "host/run.log"
        if (command.get("exit_code") == 0 and not command["timed_out"]
                and details.get("status") == "PASS" and c_log.is_file()
                and "PASS CORE_SERVICE_COHERENCE cases=16" in c_log.read_text()
                and all(c.get("exit_code") == 0 for c in details["commands"])):
            result["status"] = "PASS"
    except (OSError, ValueError, KeyError) as exc:
        result["error"] = str(exc)
    return result


def scenarios(group_name, vectors):
    if group_name == "qk_request_buffer_behavior":
        return [{"name": f"clear_{clear}", "parameters": {"CLEAR_IN_FLIGHT": clear},
                 "markers": [rf"^PASS QK_REQUEST_BUFFER clear={clear} cleared=\d+ pushed=[1-9]\d* popped=[1-9]\d* max=[1-9]\d* simultaneous=[1-9]\d*$",
                             r"^PASS: CATS-R4 integrated scheduler/FP32 service/score FIFO$"]}
                for clear in (0, 1)]
    if group_name == "fp32_reference_vectors":
        if not vectors:
            raise ValueError("requires --vectors with non-empty four-column FP32 hexadecimal vectors")
        lines = vectors.read_text().splitlines()
        if not lines or not all(re.fullmatch(r"[0-9a-fA-F]{8}(?: [0-9a-fA-F]{8}){3}", line) for line in lines):
            raise ValueError("vectors must contain non-empty four-column FP32 hexadecimal records")
        return [{"name": "vectors", "plusargs": [f"+VECTORS={vectors}"],
                 "markers": [rf"^PASS FP32 reference vectors={len(lines)} operations={2 * len(lines)} with stalled outputs$"],
                 "vectors": record(vectors)}]
    result = [{"name": "default", "markers": [MARKERS[group_name]]}]
    if group_name == "service_observer":
        result.append({"name": "completed_overflow", "plusargs": ["+completed_overflow_only"],
                       "markers": [r"^PASS CORE_SERVICE_COMPLETED_OVERFLOW cycles64=28$"]})
    if group_name == "service_counter_adapter":
        result.append({"name": "registered_producers", "plusargs": ["+registered_producers_only"],
                       "markers": [r"^PASS CORE_SERVICE_REGISTERED_PRODUCERS delayed_edges=1 source_span=18 captured=18$"]})
    return result


def choose_simulator(requested, group_name):
    # Retain four-state coverage for reset/CDC. Packed-array groups use Verilator first.
    preferred = ("iverilog", "verilator") if group_name in ("reset_edges", "async_fifo") else ("verilator", "iverilog")
    for name in preferred if requested == "auto" else (requested,):
        dependencies = ("iverilog", "vvp") if name == "iverilog" else ("verilator", "make", "g++")
        if all(shutil.which(dep) for dep in dependencies):
            return name
    return None


def rtl_group(group, out, args):
    result = {"name": group["name"], "top": group["top"], "status": "BLOCKED",
              "scope": "FPT reference unit simulation; not KWT implementation acceptance",
              "sources": [record(BUNDLE / source) for source in group["sources"]],
              "filelist": record(BUNDLE / group["filelist"]), "scenarios": []}
    simulator = choose_simulator(args.simulator, group["name"])
    if not simulator:
        result["reason"] = "requested simulator or its build/runtime dependencies unavailable"
        return result
    result["simulator"] = simulator
    result["logic_semantics"] = "four-state" if simulator == "iverilog" else "two-state"
    try:
        cases = scenarios(group["name"], args.vectors)
    except (ValueError, OSError, KeyError) as exc:
        result["reason"] = str(exc)
        return result
    for case in cases:
        case_out = out / "rtl" / group["name"] / case["name"]
        case_out.mkdir(parents=True, exist_ok=False)
        item = dict(case, status="FAIL", commands=[])
        sources = [str(BUNDLE / name) for name in group["sources"]]
        parameters = case.get("parameters", {})
        if simulator == "iverilog":
            binary = case_out / "simulation.vvp"
            compile_argv = [shutil.which("iverilog"), "-g2012", "-s", group["top"], "-o", str(binary)]
            compile_argv += [f"-P{group['top']}.{key}={value}" for key, value in parameters.items()]
            run_argv = [shutil.which("vvp"), str(binary)]
        else:
            binary = case_out / "obj/simulation"
            compile_argv = [shutil.which("verilator"), "--binary", "--timing", "--assert", "-Wno-fatal",
                            "--top-module", group["top"], "--Mdir", str(case_out / "obj"),
                            "-o", "simulation", "-j", str(args.jobs), "--threads", "1"]
            compile_argv += [f"-G{key}={value}" for key, value in parameters.items()]
            run_argv = [str(binary)]
        compile_result = run_command(compile_argv + sources, case_out, case_out / "compile.log",
                                     args.compile_timeout, args.jobs)
        item["commands"].append(compile_result)
        if compile_result.get("exit_code") != 0 or compile_result["timed_out"] or not binary.is_file():
            item["reason"] = "compile failed, timed out or produced no executable; inspect compile.log"
        else:
            item["binary"] = record(binary)
            command = run_command(run_argv + case.get("plusargs", []), case_out, case_out / "run.log",
                                  args.sim_timeout, args.jobs)
            item["commands"].append(command)
            error = completion_error(command, log_text(command), case["markers"])
            item["status"] = "FAIL" if error else "PASS"
            if error:
                item["reason"] = error
        result["scenarios"].append(item)
    result["status"] = aggregate(result["scenarios"])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=("static", "host", "rtl"), default="host")
    parser.add_argument("--groups", nargs="+", help="metadata group names; default: small reusable local units")
    parser.add_argument("--simulator", choices=("auto", "iverilog", "verilator"), default="auto")
    parser.add_argument("--vectors", type=lambda p: Path(p).resolve(), help="input for fp32_reference_vectors")
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--host-timeout", type=int, default=120)
    parser.add_argument("--compile-timeout", type=int, default=180)
    parser.add_argument("--sim-timeout", type=int, default=60)
    args = parser.parse_args(argv)
    if min(args.host_timeout, args.compile_timeout, args.sim_timeout) <= 0:
        parser.error("timeouts must be positive")
    if args.groups and args.tier != "rtl":
        parser.error("--groups requires --tier rtl")
    metadata_path = BUNDLE / "metadata/dependencies.json"
    metadata = json.loads(metadata_path.read_text())
    selected = args.groups or DEFAULT_GROUPS
    unknown = set(selected) - {g["name"] for g in metadata["groups"]}
    if unknown:
        parser.error("unknown RTL groups: " + ", ".join(sorted(unknown)))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex[:8]
    out = ROOT / "artifacts/runs" / run_id
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    result = {"schema": "migration-checks-v1", "run_id": run_id, "tier": args.tier,
              "started_utc": utc_now(), "status": "FAIL", "output": str(out),
              "scope": "imported FPT reference integrity and reuse checks only",
              "kwt_functional": "NOT_RUN", "kwt_precision": "NOT_RUN", "kwt_soc": "NOT_RUN",
              "synthesis": "NOT_RUN", "timing": "NOT_RUN", "power": "NOT_RUN",
              "resource_limits": {"parallel_groups": 1, "compile_jobs": args.jobs, "simulation_threads": 1},
              "inputs": [record(Path(__file__)), record(BUNDLE / "SHA256SUMS"), record(metadata_path),
                         record(BUNDLE / "tools/verify_bundle.py"), record(BUNDLE / "tools/run_host_checks.py")],
              "python": {"executable": record(sys.executable), "version": sys.version}, "tools": {},
              "static": {"status": "NOT_RUN"}, "host": {"status": "NOT_RUN"},
              "rtl": [{"name": g["name"], "status": "NOT_RUN", "reason": "not selected"} for g in metadata["groups"]]}
    try:
        tool_names = [args.cc] if args.tier in ("host", "rtl") else []
        if args.tier == "rtl":
            tool_names += ["iverilog", "vvp", "verilator", "g++", "make"]
        for name in dict.fromkeys(tool_names):
            # A compiler may be passed as an absolute path; use a safe log filename.
            result["tools"][name] = tool_info(name, out, args.jobs)
        result["static"] = static_check(out, args)
        if args.tier in ("host", "rtl"):
            result["host"] = (host_check(out, args) if result["static"]["status"] == "PASS" else
                              {"status": "BLOCKED", "reason": "source integrity check failed"})
        if args.tier == "rtl":
            for index, group in enumerate(metadata["groups"]):
                if group["name"] not in selected:
                    continue
                result["rtl"][index] = (rtl_group(group, out, args) if result["static"]["status"] == "PASS" else
                                         {"name": group["name"], "status": "BLOCKED", "reason": "source integrity check failed"})
        result["status"] = aggregate([result["static"], result["host"], *result["rtl"]])
    except Exception as exc:
        result.update(status="FAIL", error=f"{type(exc).__name__}: {exc}")
    finally:
        result.update(finished_utc=utc_now(), elapsed_seconds=round(time.monotonic() - start, 3))
        (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "scope", "kwt_functional", "output", "elapsed_seconds")}, ensure_ascii=False))
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}.get(result["status"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
