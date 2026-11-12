#!/usr/bin/env python3
"""Repair hold using the SS setup and FF hold libraries, then audit the export."""
import fcntl
import json
from pathlib import Path
import re
import runpy

from run_formality import PINNED, SOURCE, check, sha
from run_timing_followup import CLOCK, COMPAT_SHA, DC, FF_PINNED, PT, ROOT
from run_timing_followup import dc_body, execute, pt_body, tcl_value

CLOCK_EXPORT = ROOT / "timing-followup-r1/dc-clock"
CLOCK_SHA = {
    "mapped.v": "0ca9a39bc1d13a2bee10487b20f462da0795e59c222d7e76419c9aff2de3124f",
    "mapped.ddc": "31fa8b17c637eb7ce61eb7d256a3b90ed41c63325e24a57a1a8438b87a7f3b0d",
}

REPAIR = r"""
redirect -file linked-libraries.rpt {list_libs}
set min_path [get_timing_paths -delay_type min -max_paths 1 -slack_lesser_than 1e9]
set max_path [get_timing_paths -delay_type max -max_paths 1 -slack_lesser_than 1e9]
set hold [get_attribute $min_path slack]
set setup [get_attribute $max_path slack]
if {abs($hold - (-0.153242)) > 0.005 || abs($setup) > 0.001} {
    error "Paired timing did not reproduce the known envelope WNS: setup $setup hold $hold"
}
redirect -file hold-command.rpt {
    fix_eco_timing -type hold -methods {insert_buffer_at_load_pins insert_buffer} \
        -buffer_list {BUFV2_12TR40 BUFV4_12TR40} -setup_margin 0.005 \
        -hold_margin 0.010 -physical_mode none -timeout 540
}
metrics after
write_changes -format dctcl -output paired-dc.tcl
write_changes -output paired-pt.tcl
"""


def libraries():
    execution = json.loads((SOURCE / "execution.json").read_text())
    ordered = {item["role"]: item for item in execution["libraries"]}
    ss = [Path(ordered[role]["path"]) for role in ("standard_cell", "sram")]
    for p, role in zip(ss, ("standard_cell", "sram")):
        check(p, ordered[role]["sha256"])
    r7_ff = Path.home() / "Desktop/xu-group-y-prelim-20261110/dc/pt-ff.tcl"
    by_name = {Path(s).name: Path(s) for s in re.findall(r"\{([^{}]+\.db)\}", r7_ff.read_text())}
    ff = [by_name[name] for name in FF_PINNED]
    for p in ff:
        check(p, FF_PINNED[p.name])
    return ss, ff


def main():
    for name, digest in PINNED.items():
        check(SOURCE / name, digest)
    for name, digest in CLOCK_SHA.items():
        check(CLOCK_EXPORT / name, digest)
    check(CLOCK / "constraints-pt-add.sdc", COMPAT_SHA)
    check(PT, "afdcfa7071f86d229ed3b4481f67adefd1c51bb0288b7e7d370213a43b70c9ef")
    check(DC, "23a4101c711fdb4747a57e6f9524d4989eb76a2b3120f0fa9766f4b25ae8e6d2")
    ss, ff = libraries()
    execution = json.loads((SOURCE / "execution.json").read_text())
    check(SOURCE / "libraries.tcl", execution["outputs"]["libraries.tcl"]["sha256"])
    out = ROOT / "timing-paired-r1"
    out.mkdir(mode=0o700)
    heavy_jobs = runpy.run_path(str(SOURCE / "run_once.py"))["heavy_jobs"]
    paired = "".join(
        f"set_min_library {tcl_value(late)} -min_version {tcl_value(early)}\n"
        for late, early in zip(ss, ff)
    )
    with (ROOT / "eda.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run = execute(out, "pt-paired", PT,
                      paired + pt_body(CLOCK_EXPORT / "mapped.v", ss) + REPAIR, heavy_jobs, 1050)
        changes = run / "paired-dc.tcl"
        if not re.search(r"(?m)^\s*insert_buffer\b", changes.read_text()):
            raise RuntimeError("Paired optimizer wrote no buffer edits")
        mapped = execute(out, "dc-paired", DC, dc_body(CLOCK_EXPORT / "mapped.ddc", changes, 0), heavy_jobs, 600)
        target = mapped / "mapped.v"
        target_sha = sha(target)
        for mode in ("envelope", "reset_bypass"):
            for tag, lib in (("ss", ss), ("ff", ff)):
                check(target, target_sha)
                execute(out, f"{tag}-{mode}", PT, pt_body(target, lib, mode=mode), heavy_jobs, 500)
        check(target, target_sha)
        summary = {
            "mapped_sha256": target_sha,
            "ddc_sha256": sha(mapped / "mapped.ddc"),
            "changes_sha256": sha(changes),
            "ss_libraries": {str(p): sha(p) for p in ss},
            "ff_libraries": {str(p): sha(p) for p in ff},
            "constraint_sha256": COMPAT_SHA,
            "slack_ns": {
                f"{tag}-{mode}": dict(line.split() for line in
                    (out / f"{tag}-{mode}/before-slack.tsv").read_text().splitlines())
                for mode in ("envelope", "reset_bypass") for tag in ("ss", "ff")
            },
        }
        (out / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("PAIRED_EVIDENCE_CAPTURED", target_sha, flush=True)


if __name__ == "__main__":
    main()
