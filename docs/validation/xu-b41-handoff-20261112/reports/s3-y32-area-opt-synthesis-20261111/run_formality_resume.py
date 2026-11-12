#!/usr/bin/env python3
"""Resume the saved RTL-to-dual Formality session in its own result directory."""
import fcntl
import json
from pathlib import Path
import runpy
import socket

from run_formality import FM, PINNED, SOURCE, check, sha
from run_timing_followup import ROOT, execute, tcl_value

DUAL_SHA = "24de75106e74b3f0f4a83c36cea7e5f9e32eccdc520c2636ba8366fa8cb5cc6a"
FSS_SHA = "309286b5b81c5683d183ef3112acf064c1987a9875a8235e33622a9cb8d3633d"
RECEIPT_SHA = "341b81e2c648db476641fb7b613ee6aa90b988dd52f52d2fd32e2d3c2f16ca40"


def main():
    if socket.gethostname().split(".")[0] != "RDserver04" or Path.home().name != "s4_23usr":
        raise RuntimeError("Run on the team's competition server")
    prior = ROOT / "fm-dc-dual-from-rtl"
    checkpoint = prior / "formality_auto.fss"
    mapped = ROOT / "timing-dual-r2/dc-dual/mapped.v"
    check(checkpoint, FSS_SHA)
    check(prior / "result.json", RECEIPT_SHA)
    receipt = json.loads((prior / "result.json").read_text())
    if receipt["native_exit"] != 124 or receipt["implementation_sha256"] != DUAL_SHA:
        raise RuntimeError("Unexpected prior Formality result")
    check(prior / "native.log", receipt["log_sha256"])
    check(mapped, DUAL_SHA)
    for name, digest in PINNED.items():
        check(SOURCE / name, digest)
    first = json.loads((ROOT / "fm-original/result.json").read_text())
    check(FM, first["tool_sha256"])
    for library in first["libraries"]:
        check(Path(library["path"]), library["sha256"])

    body = "\n".join([
        "restore_session " + tcl_value(checkpoint),
        "set_host_options -max_cores 2",
        "set_app_var verification_timeout_limit 00:35:00",
        "set verdict [verify]",
        "report_black_boxes",
        "report_unmatched_points",
        "report_failing_points",
        "report_aborted_points",
        "report_unverified_points",
        "if {!$verdict} {error {Resumed RTL equivalence remains unverified}}",
    ])
    heavy_jobs = runpy.run_path(str(SOURCE / "run_once.py"))["heavy_jobs"]
    with (ROOT / "eda.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out = execute(ROOT, "fm-dc-dual-rtl-resume-r1", FM, body, heavy_jobs, 2400)
    check(checkpoint, FSS_SHA)
    check(mapped, DUAL_SHA)
    if "Verification SUCCEEDED" not in (out / "native.log").read_text(errors="replace"):
        raise RuntimeError("Missing successful Formality verification")
    result = dict(status="VERIFIED_REVIEW_SCOPE", comparison="RTL to dual",
                  implementation_sha256=DUAL_SHA, restored_checkpoint_sha256=FSS_SHA,
                  prior_receipt_sha256=RECEIPT_SHA, native_receipt_sha256=sha(out / "receipt.json"))
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("B41_RTL_DUAL_RESUME_VERIFIED", DUAL_SHA, flush=True)


if __name__ == "__main__":
    main()
