#!/usr/bin/env python3
"""Repair max capacitance and slew with both independent corners active."""
import fcntl
import json
import re
import runpy

from run_formality import PINNED, SOURCE, check, sha
from run_paired_eco import libraries
from run_pin_hold_eco import DRC
from run_timing_followup import CLOCK, COMPAT_SHA, DC, PT, REPORT, ROOT
from run_timing_followup import dc_body, execute, pt_body, tcl_value

CANDIDATE = "9849303f264d97f2f6735353d89a35fbe143b0897f589e94352d23ae517aa87b"
DRC_TYPES = ("max_capacitance", "min_capacitance", "max_transition")
ECO = r"""
set_app_var multi_scenario_working_directory ./scenarios
set_app_var multi_scenario_merged_error_log ./worker-messages.log
set_host_options -name local_corners -num_processes 2 -max_cores 1
start_hosts -min_hosts 2
current_session {ss ff}
current_scenario -all
if {[sizeof_collection [current_scenario]] != 2} {error {Both independent corners must be active}}
remote_execute {update_timing -full; report_global_timing}
foreach kind {max_capacitance max_transition} {
    redirect -file "$kind-eco.rpt" [list fix_eco_drc -type $kind \
        -methods {size_cell insert_buffer} -buffer_list {BUFV2_12TR40 BUFV4_12TR40 BUFV8_12TR40 BUFV12_12TR40} \
        -setup_margin 0.0 -hold_margin 0.0 -verbose]
}
if {[sizeof_collection [current_scenario]] != 2} {error {A corner was lost during ECO}}
report_global_timing
write_changes -format dctcl -output electrical-dc.tcl
stop_hosts
"""


def violations(directory):
    return {kind: (directory / (kind + ".rpt")).read_text().count("(VIOLATED)")
            for kind in DRC_TYPES}


def main():
    base = ROOT / "timing-gate-targeted-r2"
    timed = json.loads((base / "result.json").read_text())
    if timed["status"] != "IDEAL_TIMING_REVIEW" or timed["mapped_sha256"] != CANDIDATE:
        raise RuntimeError("Expected the verified four-scenario timing candidate")
    start = base / "dc-gate"
    check(start / "mapped.v", CANDIDATE)
    check(start / "mapped.ddc", timed["ddc_sha256"])
    for name, digest in PINNED.items():
        check(SOURCE / name, digest)
    check(CLOCK / "constraints-pt-add.sdc", COMPAT_SHA)
    check(PT, "afdcfa7071f86d229ed3b4481f67adefd1c51bb0288b7e7d370213a43b70c9ef")
    check(DC, "23a4101c711fdb4747a57e6f9524d4989eb76a2b3120f0fa9766f4b25ae8e6d2")
    ss, ff = libraries()
    heavy_jobs = runpy.run_path(str(SOURCE / "run_once.py"))["heavy_jobs"]
    out = ROOT / "timing-electrical-r1"
    record = dict(original_mapped_sha256=CANDIDATE, constraints_sha256=COMPAT_SHA, scenarios={})
    with (ROOT / "eda.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out.mkdir(mode=0o700)
        launch = out / "local_dmsa.sh"
        launch.write_text("#!/bin/sh\nulimit -v 7340032 || exit 1\nexec " + str(PT) + ' -multi_scenario "$@"\n')
        launch.chmod(0o700)
        scenario_cmds = []
        for tag, libs in (("ss", ss), ("ff", ff)):
            scenario = out / (tag + ".tcl")
            body = pt_body(start / "mapped.v", libs).partition(REPORT)[0]
            scenario.write_text(body)
            scenario_cmds.append(f"create_scenario -name {tag} -specific_data {tcl_value(scenario)}")
        native = execute(out, "pt-electrical", launch, "\n".join(scenario_cmds) + ECO, heavy_jobs, 1000)
        changes = native / "electrical-dc.tcl"
        edits = [line for line in changes.read_text().splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
        if any(not re.match(r"^\s*(current_instance|insert_buffer|size_cell)\b", line) for line in edits):
            raise RuntimeError("Unexpected command in the ECO edit list")
        record["change_sha256"] = sha(changes)
        record["status"] = "NO_CELL_EDITS"
        if any(re.match(r"^\s*(insert_buffer|size_cell)\b", line) for line in edits):
            dc = execute(out, "dc-electrical", DC, dc_body(start / "mapped.ddc", changes, 0), heavy_jobs, 600)
            mapped = dc / "mapped.v"
            digest = sha(mapped)
            record.update(mapped_sha256=digest, ddc_sha256=sha(dc / "mapped.ddc"),
                          path=str(dc.relative_to(ROOT)))
            for mode in ("envelope", "reset_bypass"):
                for tag, libs in (("ss", ss), ("ff", ff)):
                    check(mapped, digest)
                    name = f"{tag}-{mode}"
                    review = execute(out, name, PT, pt_body(mapped, libs, mode=mode) + DRC,
                                     heavy_jobs, 500)
                    record["scenarios"][name] = dict(
                        slack_ns=dict(line.split() for line in (review / "before-slack.tsv").read_text().splitlines()),
                        original_drc=violations(base / name), drc=violations(review))
                if any(float(s) < 0 for v in record["scenarios"].values() for s in v["slack_ns"].values()):
                    break
            check(mapped, digest)
            record["status"] = "TIMING_REGRESSION" if len(record["scenarios"]) < 4 or any(
                float(s) < 0 for v in record["scenarios"].values() for s in v["slack_ns"].values()
            ) else "IDEAL_TIMING_AND_ELECTRICAL_REVIEW"
        check(start / "mapped.v", CANDIDATE)
        (out / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print("B41_ELECTRICAL_CAPTURED", record["status"], flush=True)


if __name__ == "__main__":
    main()
