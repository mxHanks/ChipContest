#!/usr/bin/env python3
"""Verify the timed ITCM ECO against the already matched B41 dual netlist."""
import fcntl
import json
from pathlib import Path
import runpy

from run_formality import FM, PINNED, SOURCE, TOP, check, sha
from run_pin_hold_eco import EXPECTED as DUAL_SHA
from run_timing_followup import CLOCK, COMPAT_SHA, ROOT, execute, tcl_value


def main():
    target_run = ROOT / "timing-gate-targeted-r2"
    timing = json.loads((target_run / "result.json").read_text())
    if timing["status"] != "IDEAL_TIMING_REVIEW" or timing["constraints_sha256"] != COMPAT_SHA:
        raise RuntimeError("Expected a four-scenario timing candidate under the original constraints")
    if set(timing["slack_ns"]) != {"ss-envelope", "ff-envelope", "ss-reset_bypass", "ff-reset_bypass"}:
        raise RuntimeError("Timing scenarios differ")
    for name, slack in timing["slack_ns"].items():
        native = json.loads((target_run / name / "receipt.json").read_text())
        observed = dict(line.split() for line in (target_run / name / "before-slack.tsv").read_text().splitlines())
        if (not native["complete"] or native["native_exit"] or observed != slack or
                set(slack) != {"min", "max"} or not all(float(s) >= 0 for s in slack.values())):
            raise RuntimeError("Unqualified timing receipt: " + name)
        check(target_run / name / "native.log", native["log"])
    check(CLOCK / "constraints-pt-add.sdc", COMPAT_SHA)
    target = target_run / "dc-gate/mapped.v"
    reference = ROOT / "timing-dual-r2/dc-dual/mapped.v"
    check(target, timing["mapped_sha256"])
    check(reference, DUAL_SHA)
    prior = ROOT / "fm-dc-dual-from-mapped"
    precedent = json.loads((prior / "result.json").read_text())
    if (precedent["status"] != "VERIFIED_REVIEW_SCOPE" or precedent["native_exit"] != 0 or
            precedent["implementation_sha256"] != DUAL_SHA or
            precedent["base_mapped_sha256"] != PINNED["mapped.v"]):
        raise RuntimeError("Dual reference equivalence receipt differs")
    check(prior / "native.log", precedent["log_sha256"])
    check(SOURCE / "execution.json", PINNED["execution.json"])
    first = json.loads((ROOT / "fm-original/result.json").read_text())
    check(FM, first["tool_sha256"])
    libraries = [Path(lib["path"]) for lib in first["libraries"]]
    for path, lib in zip(libraries, first["libraries"]):
        check(path, lib["sha256"])
    body = ["set synopsys_auto_setup true"]
    body.extend("read_db -technology_library " + tcl_value(path) for path in reversed(libraries))
    body += [
        "read_verilog -container r " + tcl_value(reference),
        "set_top r:/WORK/" + TOP,
        "read_verilog -container i " + tcl_value(target),
        "set_top i:/WORK/" + TOP,
        "set_app_var verification_timeout_limit 00:04:00",
        "match",
        "set verdict [verify]",
        "report_black_boxes",
        "report_unmatched_points",
        "report_failing_points",
        "report_aborted_points",
        "report_unverified_points",
        "if {!$verdict} {error {ITCM ECO is not equivalent}}",
    ]
    heavy_jobs = runpy.run_path(str(SOURCE / "run_once.py"))["heavy_jobs"]
    with (ROOT / "eda.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out = execute(ROOT, "fm-gate-targeted-r2-from-dual", FM, "\n".join(body), heavy_jobs, 420)
    if "Verification SUCCEEDED" not in (out / "native.log").read_text(errors="replace"):
        raise RuntimeError("Missing successful Formality verification")
    check(target, timing["mapped_sha256"])
    check(reference, DUAL_SHA)
    result = dict(status="VERIFIED_REVIEW_SCOPE", comparison="dual mapped to ITCM ECO mapped",
                  reference_sha256=DUAL_SHA, implementation_sha256=timing["mapped_sha256"],
                  timing_receipt_sha256=sha(target_run / "result.json"),
                  native_receipt_sha256=sha(out / "receipt.json"))
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("B41_GATE_MAPPED_EQUIVALENT", timing["mapped_sha256"], flush=True)


if __name__ == "__main__":
    main()
