#!/usr/bin/env python3
"""Validate a completed native fabric log and seal its local identities."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    out = args.directory.resolve()
    log = (out / "run.log").read_text()
    required = ["GEOMETRY_PASS macros=256 bits=4194304", "MASK_ERROR_PASS",
                "Y_PUBLIC_READBACK_PASS words=25344", "SHARED64_PROTOCOL_PASS"]
    failures = [f"missing {marker}" for marker in required if marker not in log]
    if re.search(r"%Fatal|%Error|Aborting", log):
        failures.append("native simulation failed")
    metrics = []
    for line in log.splitlines():
        if line.startswith("METRIC "):
            fields = {key: int(value) for key, value in
                      re.findall(r"(\w+)=(\d+)", line)}
            metrics.append(fields)
            expected = 4352 if fields["kind"] == 0 else 15840
            if any(fields[key] != expected for key in ("beats", "accepted", "retired")):
                failures.append("stream request/response accounting mismatch")
            if not fields["interval_sum"] < fields["cycles"] <= (
                    fields["interval_sum"] + fields["latency_max"] + 1):
                failures.append("stream duration contradicts accepted intervals/latency")
            fields["cycles_per_64bit_beat"] = fields["cycles"] / expected
            fields["cycles_per_effective_32bit_word"] = fields["cycles"] / (2 * expected)
            if not fields["contention"] and not fields["backpressure"]:
                if fields["cycles"] * 4 > expected * 5:
                    failures.append("uncontended service exceeds 1.25 cycles/beat")
                if fields["interval_min"] != 1 or fields["interval_max"] != 2 or fields["latency_max"] != 1:
                    failures.append("unexpected uncontended accept/response timing")
            elif fields["cpu_accepted"] != expected:
                failures.append("bounded CPU contention stream incomplete")
    if len(metrics) != 4:
        failures.append("expected four measured streams")
    sources = list((out / "source").glob("*.sv"))
    if len(sources) != 4:
        failures.append("expected four sealed source files")
    result = {
        "status": "PASS" if not failures else "FAIL",
        "scope": "Local functional arbiter + explicit 256-macro shared endpoint; no PPA or CPU throughput claim",
        "macro_model": "generic functional RAMSP1024X16, not organizer timing model",
        "metrics": metrics,
        "failures": failures,
        "identity": {str(path.relative_to(root)): sha(path) for path in
                     sources + [out / "run.log", out / "build.log", out / "obj/Vtb_shared64"]},
        "verilator": subprocess.check_output(["verilator", "--version"], text=True).strip(),
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "metrics": metrics, "failures": failures}, indent=2))
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
