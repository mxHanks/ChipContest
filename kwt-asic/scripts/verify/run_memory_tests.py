#!/usr/bin/env python3
"""Four-state SRAM backend/banking/shared-memory contract regression.

This is functional evidence only. No official SRAM pin/timing/PPA model is used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("kwt_memory_common", ROOT / "scripts/verify/run_checks.py")
COMMON = importlib.util.module_from_spec(spec)
spec.loader.exec_module(COMMON)


def record(path):
    result = COMMON.record(path)
    path = Path(path).resolve()
    if path.is_relative_to(ROOT):
        result["project_relative_path"] = path.relative_to(ROOT).as_posix()
    return result


def completion(command, text, marker):
    return COMMON.completion_error(command, text, marker if isinstance(marker, list) else [marker])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="new, non-existing evidence directory")
    args = parser.parse_args(argv)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-sram-unit-" + uuid.uuid4().hex[:8]
    out = args.output.resolve() if args.output else ROOT / "artifacts/runs" / run_id
    out.mkdir(parents=True, exist_ok=False)
    primitive = [ROOT / "src/rtl/memory/kwt_sram_1rw.sv", ROOT / "src/rtl/memory/kwt_sram_1rw_blackbox.sv"]
    sources = [*primitive, ROOT / "src/rtl/memory/kwt_sram_bank.sv",
               ROOT / "sim/tb_kwt_sram_1rw.sv", ROOT / "sim/tb_kwt_sram_init.sv",
               ROOT / "sim/vectors/sram-init-8.mem", ROOT / "sim/tb_kwt_sram_bank.sv",
               ROOT / "sim/kwt_shared512_checked_model.sv", ROOT / "sim/tb_kwt_shared512_checked.sv",
               ROOT / "scripts/verify/run_checks.py", Path(__file__)]
    result = {"schema": "kwt-sram-contract-v1", "run_id": run_id, "status": "FAIL", "scope": "functional four-state simulation only",
              "started_utc": COMMON.utc_now(), "output": str(out), "inputs": [], "tools": {},
              "cases": [], "equivalence": [], "official_sram": "BLOCKED", "official_sram_reason": "official model/pins/timing not supplied",
              "official_ppa": "NOT_RUN", "synthesis": "NOT_RUN", "commands": []}
    binaries = {}
    normal_outputs = {}

    def command(argv, name):
        item = COMMON.run_command(argv, ROOT, out / (name + ".log"), 60, 1)
        result["commands"].append(item)
        return item, COMMON.log_text(item)

    def build(top, name, files, params=None):
        target = out / (name + ".vvp")
        argv = [shutil.which("iverilog"), "-g2012", "-s", top, "-o", target]
        for key, value in (params or {}).items():
            argv.append(f"-P{top}.{key}={value}")
        argv += files
        item, text = command(argv, name + "-compile")
        if item.get("exit_code") != 0 or item.get("timed_out"):
            raise RuntimeError(f"compile failed: {name}; see {item.get('log')}")
        binaries[name] = record(target)
        return target

    def positive(name, binary, marker, extra=None):
        item, text = command([shutil.which("vvp"), binary, *(extra or [])], name)
        error = completion(item, text, marker)
        result["cases"].append({"name": name, "status": "FAIL" if error else "PASS", "expected": "clean complete marker", "command": item,
                                "marker": marker, **({"error": error} if error else {})})
        if error:
            raise RuntimeError(name + ": " + error)
        return text

    def negative(name, binary, diagnostic, extra=None):
        item, text = command([shutil.which("vvp"), binary, *(extra or [])], name)
        diagnostics = [diagnostic] if isinstance(diagnostic, str) else diagnostic
        ok = item.get("exit_code") not in (None, 0) and not item.get("timed_out") and any(d in text for d in diagnostics) and "EXPECTED_DIAGNOSTIC_NOT_TRIGGERED" not in text
        result["cases"].append({"name": name, "status": "PASS" if ok else "FAIL", "expected": "rejected illegal operation", "expected_diagnostic": diagnostic, "command": item})
        if not ok:
            raise RuntimeError(name + ": expected fatal diagnostic was not observed")

    try:
        missing = [str(p) for p in sources if not p.is_file()]
        if missing:
            result["status"] = "BLOCKED"
            raise RuntimeError("missing files: " + ", ".join(missing))
        result["inputs"] = [record(p) for p in sources]
        for tool in ("iverilog", "vvp"):
            result["tools"][tool] = COMMON.tool_info(tool, out, 1)
        if not all(shutil.which(t) for t in ("iverilog", "vvp")):
            result["status"] = "BLOCKED"
            raise RuntimeError("iverilog/vvp required; source env/activate.sh")
        for backend in (0, 2):
            for width, depth in ((16, 1), (16, 5), (16, 128), (16, 1024), (16, 4096), (40, 32), (41, 512)):
                name = f"unit-b{backend}-w{width}-d{depth}"
                binary = build("tb_kwt_sram_1rw", name, [*primitive, ROOT / "sim/tb_kwt_sram_1rw.sv"], {"BACKEND": backend, "WIDTH": width, "DEPTH": depth})
                text = positive(name, binary, rf"^PASS KWT_SRAM_UNIT width={width} depth={depth} checks=[1-9][0-9]* signature=[0-9a-f]{{16}}$")
                normal_outputs[backend, width, depth] = re.search(r"^PASS KWT_SRAM_UNIT .*", text, re.M).group(0)
            diag = {1: "KWT_SRAM_SINGLE_PORT_CONFLICT", 2: "KWT_SRAM_SINGLE_PORT_CONFLICT", 3: "KWT_SRAM_UNINITIALIZED_READ",
                    4: "KWT_SRAM_READ_ADDRESS_INVALID", 5: "KWT_SRAM_WRITE_ADDRESS_INVALID", 6: "KWT_SRAM_UNKNOWN_ENABLE",
                    7: "KWT_SRAM_READ_ADDRESS_INVALID", 8: "KWT_SRAM_UNKNOWN_WRITE_DATA", 9: "KWT_SRAM_WRITE_ADDRESS_INVALID"}
            binary = out / f"unit-b{backend}-w16-d5.vvp"
            for number, diagnostic in diag.items():
                negative(f"illegal-b{backend}-{number}", binary, diagnostic, [f"+ERROR_CASE={number}"])
            name = f"init-b{backend}"
            binary = build("tb_kwt_sram_init", name, [*primitive, ROOT / "sim/tb_kwt_sram_init.sv"], {"BACKEND": backend})
            positive(name, binary, r"^PASS KWT_SRAM_INIT words=8$")
            for kind in ("missing", "short", "unknown"):
                fixture = out / (kind + ".mem")
                if kind == "short":
                    fixture.write_text("1200\n")
                elif kind == "unknown":
                    fixture.write_text("1200\n1201\nxxxx\n1203\n1204\n1205\n1206\n1207\n")
                negative_binary = build("tb_kwt_sram_init", name + "-" + kind,
                                        [*primitive, ROOT / "sim/tb_kwt_sram_init.sv"],
                                        {"BACKEND": backend, "INIT_FILE": json.dumps(str(fixture))})
                negative(name + "-" + kind, negative_binary, "KWT_SRAM_INIT_FILE_MISSING" if kind == "missing" else "KWT_SRAM_INIT_INCOMPLETE_OR_UNKNOWN")
            for width, depth in ((16, 3136), (41, 3200), (40, 32), (16, 4224)):
                name = f"bank-b{backend}-w{width}-d{depth}"
                binary = build("tb_kwt_sram_bank", name, [*primitive, ROOT / "src/rtl/memory/kwt_sram_bank.sv", ROOT / "sim/tb_kwt_sram_bank.sv"],
                               {"BACKEND": backend, "WIDTH": width, "DEPTH": depth})
                positive(name, binary, [rf"^PASS KWT_SRAM_BANK backend={backend} width={width} depth={depth} checks=[1-9][0-9]*$",
                                        rf"^PASS KWT_SRAM_BANK_WIDTH_COVERAGE width={width} bits_both={width}$"])
            binary = out / f"bank-b{backend}-w41-d3200.vvp"
            for number in range(1,9):
                diagnostic = ("KWT_SRAM_BANK_UNKNOWN_ENABLE" if number <= 4 else
                              "KWT_SRAM_BANK simultaneous read/write forbidden" if number == 5 else
                              "KWT_SRAM_BANK address out of logical range" if number in (6,7) else
                              ["KWT_SRAM_BANK unknown address", "KWT_SRAM_UNKNOWN_ENABLE"])
                # X address comparisons propagate X into primitive enables;
                # either layer can diagnose first at the same clock edge.
                negative(f"bank-illegal-b{backend}-{number}", binary, diagnostic, [f"+ERROR_CASE={number}"])
        for width, depth in ((16, 1), (16, 5), (16, 128), (16, 1024), (16, 4096), (40, 32), (41, 512)):
            a, b = normal_outputs[0, width, depth], normal_outputs[2, width, depth]
            status = "PASS" if a == b else "FAIL"
            result["equivalence"].append({"width": width, "depth": depth, "status": status, "matching_output": a,
                                          "scope": "same requests, valid/hold/reset checks and read-data signature; independent top baseline checked separately"})
            if status != "PASS":
                raise RuntimeError("behavior/FF response signature mismatch")
        binary = build("tb_kwt_shared512_checked", "shared512", [ROOT / "sim/kwt_shared512_checked_model.sv", ROOT / "sim/tb_kwt_shared512_checked.sv"])
        positive("shared512", binary, r"^PASS KWT_SHARED512_CHECKED checks=[1-9][0-9]*$")
        binary = build("tb_kwt_sram_1rw", "blackbox-functional-refusal", [*primitive, ROOT / "sim/tb_kwt_sram_1rw.sv"], {"BACKEND": 1})
        negative("blackbox-functional-refusal", binary, "KWT_SRAM_BLACKBOX_IS_NOT_A_FUNCTIONAL_MODEL")
        # Official mode cannot accidentally compile without a real supplied adapter.
        official, text = command([shutil.which("iverilog"), "-g2012", "-s", "tb_kwt_sram_1rw", "-Ptb_kwt_sram_1rw.BACKEND=3", "-o", out / "official-unavailable.vvp", *primitive, ROOT / "sim/tb_kwt_sram_1rw.sv"], "official-unavailable-compile")
        ok = official.get("exit_code") not in (None, 0) and not official.get("timed_out") and "kwt_official_sram_adapter" in text
        result["cases"].append({"name": "official-unavailable", "status": "PASS" if ok else "FAIL", "expected": "missing adapter rejected", "command": official})
        if not ok:
            raise RuntimeError("OFFICIAL backend did not reject missing adapter")
        if [record(p) for p in sources] != result["inputs"]:
            raise RuntimeError("input source changed during regression")
        result["status"] = "PASS"
    except Exception as exc:
        result["error"] = str(exc)
    result["binaries"] = binaries
    result["finished_utc"] = COMMON.utc_now()
    result["coverage"] = {"positive_cases": sum(c["expected"] == "clean complete marker" for c in result["cases"]),
                          "negative_cases": sum(c["expected"] != "clean complete marker" for c in result["cases"]),
                          "reset_policy": "invalidate response only; retain payload and written bitmap", "read_latency_cycles": 1,
                          "write_read_collision": "all simultaneous read/write requests forbidden, including different addresses",
                          "ports": "1RW only; no dual-port assumption", "init_policy": "complete DEPTH-word known HEX image or explicit writes"}
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "result": str(out / "result.json"), "cases": len(result["cases"]),
                      "equivalence": len(result["equivalence"]), **({"error": result["error"]} if "error" in result else {})}, indent=2))
    return 0 if result["status"] == "PASS" else 2 if result["status"] == "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
