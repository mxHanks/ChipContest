#!/usr/bin/env python3
"""RAM-preserving Yosys structure inspection; never a physical PPA claim."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
MARKER = "KWT_STRUCTURAL_COMPLETE"


def record(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size}


def lower_casts(source):
    """Known initialized index values only; preserve signed 32-bit binary result."""
    allowed = {"load_addr", "block_index", "emit_lane", "k_issue"}
    matches = re.findall(r"\bint'\((\w+)\)", source)
    if not set(matches) <= allowed:
        raise ValueError("unexpected int-cast operand; source adaptation requires review")
    # 32'(x) preserves x's signedness while extending/truncating to 32 bits.
    # $signed then sets the result signed, matching the signed int'(x) result.
    lowered = re.sub(r"\bint'\((\w+)\)", r"$signed(32'(\1))", source)
    if re.search(r"\bint\s*'", lowered):
        raise ValueError("unsupported complex int cast; refusing heuristic rewrite")
    return lowered, {"rule": "int'(known_index) -> $signed(32'(known_index))",
                     "replacements": len(matches), "operands": sorted(set(matches)),
                     "reason": "Yosys 0.33 rejects int' cast syntax; signed 32-bit binary result preserved",
                     "four_state_equivalence": "NOT_PROVEN; Icarus int' and sized casts differ on X/Z operands; structural synthesis scope is initialized binary indices"}


def integer(value):
    if isinstance(value, int):
        return value
    if not value or set(value) - set("01"):
        raise ValueError("unknown-valued structural parameter")
    return int(value, 2)


def summarize(netlist, top):
    if set(netlist["modules"]) != {top}:
        raise ValueError("unexpected hierarchy; require one fully elaborated top")
    module = netlist["modules"][top]
    cells = module["cells"]
    types = Counter(cell["type"] for cell in cells.values())
    memories, multipliers, adders, registers = [], [], [], []
    for name, cell in cells.items():
        typ, params = cell["type"], cell["parameters"]
        if typ == "$mem_v2":
            width, size = integer(params["WIDTH"]), integer(params["SIZE"])
            rd, wr = integer(params["RD_PORTS"]), integer(params["WR_PORTS"])
            memories.append({"name": name, "width": width, "words": size,
                             "bits": width*size, "read_ports": rd, "write_ports": wr,
                             "read_clock_enable_mask": integer(params["RD_CLK_ENABLE"]),
                             "write_clock_enable_mask": integer(params["WR_CLK_ENABLE"]),
                             "requires_bank_partition_or_multiport_mapping": rd > 1 or wr > 1})
        elif typ in ("$mul", "$add"):
            item = {"name": name, "a_width": integer(params["A_WIDTH"]),
                    "b_width": integer(params["B_WIDTH"]), "y_width": integer(params["Y_WIDTH"]),
                    "a_signed": bool(integer(params["A_SIGNED"])),
                    "b_signed": bool(integer(params["B_SIGNED"]))}
            (multipliers if typ == "$mul" else adders).append(item)
        elif typ.startswith(("$dff", "$adff", "$sdff")):
            registers.append({"name": name, "type": typ, "width": integer(params["WIDTH"])})
    warnings = []
    for memory in memories:
        if memory["requires_bank_partition_or_multiport_mapping"]:
            warnings.append(f"{memory['name']} collected as {memory['read_ports']}R/{memory['write_ports']}W memory; logical banks must be separated before single-port SRAM mapping")
        if memory["read_clock_enable_mask"] != (1 << memory["read_ports"])-1:
            warnings.append(f"{memory['name']} has asynchronous/unmerged read ports; inspect memory_dff log")
    return {"cell_types": dict(sorted(types.items())), "cells": len(cells),
            "memories": memories, "memory_bits": sum(m["bits"] for m in memories),
            "multipliers": multipliers, "adders": adders,
            "registers_excluding_memory_read_flops": registers,
            "register_bits_excluding_memory_read_flops": sum(r["width"] for r in registers),
            "mapping_warnings": warnings,
            "scope": "RTLIL structure before cell/memory technology mapping; counts are not mm2, MHz or mW"}


def run_command(command, cwd, log, timeout):
    start = time.monotonic()
    with log.open("w") as stream:
        process = subprocess.Popen(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        timed_out = False
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
    return {"argv": command, "cwd": str(cwd), "exit_code": code, "timed_out": timed_out,
            "elapsed_seconds": round(time.monotonic()-start, 6), "log": record(log)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("baseline", "opt", "banked", "probe"), default="opt")
    parser.add_argument("--lanes", type=int, default=8)
    parser.add_argument("--pipe-mul", type=int, choices=(0, 1), default=1)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.lanes < 1 or args.lanes > 256 or 256 % args.lanes or args.timeout <= 0:
        parser.error("LANES must divide 256 and timeout must be positive")
    if args.variant == "probe" and args.lanes != 2:
        parser.error("probe uses --lanes 2 (only two observed outputs)")
    tool = ROOT / ".tools/bin/yosys"
    if not tool.is_file():
        parser.error("run bash scripts/setup/bootstrap_synth.sh --download first")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = args.output_dir or ROOT / "artifacts/runs" / (stamp+"-structure-"+uuid.uuid4().hex[:8])
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    top = {"baseline": "kwt_linear_engine", "opt": "kwt_linear_engine_opt", "banked": "kwt_linear_engine_banked",
           "probe": "probe_banked_memory"}[args.variant]
    source = ROOT / ("scripts/synth/probe_banked_memory.sv" if args.variant == "probe" else "src/rtl/"+top+".sv")
    result = {"schema": "kwt-structural-synthesis-v1", "status": "FAIL", "run_directory": str(out),
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "RAM-preserving structural synthesis, not gate-level equivalence or physical PPA",
              "configuration": {"variant": args.variant, "top": top, "lanes": args.lanes,
                                "pipe_mul": args.pipe_mul if args.variant in ("opt", "banked") else 0},
              "physical_timing": "NOT_RUN", "physical_area": "NOT_RUN", "physical_power": "NOT_RUN",
              "sram_macro_mapping": "NOT_RUN", "gate_equivalence": "NOT_RUN", "soc": "NOT_RUN",
              "inputs": [], "commands": []}
    try:
        result["inputs"] = [record(source), record(Path(__file__)),
                            record(ROOT/"scripts/setup/bootstrap_synth.sh"), record(tool),
                            record(ROOT/".tools/synth/usr/bin/yosys"),
                            record(ROOT/".tools/synth/usr/bin/yosys-abc")]
        lowered, adaptation = lower_casts(source.read_text())
        derived = out / "input.sv"
        derived.write_text(lowered)
        result["source_adaptation"] = dict(adaptation, derived=record(derived))
        script = out / "run.ys"
        params = f"chparam -set LANES {args.lanes}"
        if args.variant in ("opt", "banked"):
            params += f" -set PIPE_MUL {args.pipe_mul}"
        script.write_text("\n".join(["read_verilog -sv -defer input.sv", params+" "+top,
            "hierarchy -check -top "+top, "proc", "opt", "memory_dff", "memory_collect",
            "opt_clean", "check -assert", "stat -width", "tee -o stats.json stat -json",
            "write_json netlist.json", "log "+MARKER, ""]))
        result["script"] = record(script)
        lock_path = ROOT / ".tools/synth/structural.lock"
        with lock_path.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("another structural synthesis owns project lock") from exc
            version = run_command([str(tool), "-V"], out, out/"version.log", 15)
            result["commands"].append(version)
            if version["exit_code"] != 0 or version["timed_out"]:
                raise RuntimeError("Yosys version probe failed")
            run = run_command([str(tool), "-Q", "-s", "run.ys"], out, out/"synthesis.log", args.timeout)
            result["commands"].append(run)
        log = (out/"synthesis.log").read_text()
        result["completion_marker_count"] = len(re.findall(r"^"+MARKER+r"$", log, re.M))
        if run["exit_code"] != 0 or run["timed_out"] or result["completion_marker_count"] != 1:
            raise RuntimeError("structural synthesis failed, timed out, or lacks unique completion marker")
        result["structure"] = summarize(json.loads((out/"netlist.json").read_text()), top)
        if args.variant != "probe" and result["structure"]["memory_bits"] != 373760:
            raise RuntimeError("unexpected retained payload memory bits; inspect possible memory-to-register expansion")
        if args.variant == "probe" and result["structure"]["memory_bits"] != 512:
            raise RuntimeError("probe memory size differs from 2x16x16 bits")
        result["outputs"] = [record(out/"netlist.json"), record(out/"stats.json")]
        # Re-read source/tool bytes at completion so a concurrent edit cannot
        # make the evidence appear to describe another source revision.
        for item in result["inputs"]:
            if record(item["path"])["sha256"] != item["sha256"]:
                raise RuntimeError("input changed while synthesis was running: "+item["path"])
        result["status"] = "PASS"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    (out/"result.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"status": result["status"], "report": str(out/"result.json"),
                      "scope": result["scope"], "error": result.get("error")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
