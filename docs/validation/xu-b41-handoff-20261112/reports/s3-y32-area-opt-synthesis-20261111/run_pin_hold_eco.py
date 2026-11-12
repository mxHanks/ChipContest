#!/usr/bin/env python3
"""Add local delay only at measured residual input and output endpoints."""
import fcntl
import json
import re
import runpy

from run_formality import PINNED, SOURCE, check, sha
from run_paired_eco import libraries
from run_timing_followup import CLOCK, COMPAT_SHA, DC, PT, ROOT
from run_timing_followup import dc_body, execute, pt_body

DUAL = ROOT / "timing-dual-r2"
EXPECTED = "24de75106e74b3f0f4a83c36cea7e5f9e32eccdc520c2636ba8366fa8cb5cc6a"
PIN_HOLD = r"""
proc endpoint_slack {obj mode} {
    set p [get_timing_paths -to $obj -delay_type $mode -max_paths 1 -slack_lesser_than 1e9]
    if {[sizeof_collection $p] == 0} {return 1e6}
    return [get_attribute $p slack]
}
set lib [get_lib_cells -quiet */BUFV2_12TR40]
if {[sizeof_collection $lib] != 1} {error {Expected a unique BUFV2}}
set ref [get_object_name $lib]
set f [open local-hold.tsv w]
puts $f "endpoint\tinitial_min_ns\tfinal_min_ns\tinitial_max_ns\tfinal_max_ns\tinserted"
set seen {}
set targets {}
set violations [get_timing_paths -delay_type min -max_paths 80 -nworst 1 -slack_lesser_than 0]
foreach_in_collection path $violations {
    set ep [get_attribute $path endpoint]
    set name [get_object_name $ep]
    if {$name in $seen} {continue}
    lappend seen $name
    set group [get_object_name [get_attribute $path path_group]]
    set direction [get_attribute $ep direction]
    set input_data [regexp {/(u_tim[0-3]/u_in_stage/r_ls_clk_sync_reg\[0\]|u_e203_subsys_gfcm/clk1_sync_r_reg\[2\])/D$} $name]
    set gate_data [expr {$group eq {**clock_gating_default**} && [regexp {/(u_pllclkdiv_clkgate|u_clk1_clkgate|u_itcm_clkgate)/U2/A[12]$} $name]}]
    set pad [regexp {^io_pads_gpioA_o_oval\[(26|29|30|31)\]$} $name]
    if {!(($direction eq {in} && ($input_data || $gate_data)) || ($direction eq {out} && $pad))} {
        puts "XU_B41_RESIDUAL_UNMODIFIED $name $direction $group"
        continue
    }
    append_to_collection targets $ep
}
foreach_in_collection ep $targets {
    set name [get_object_name $ep]
    set start_min [endpoint_slack $ep min]
    set start_max [endpoint_slack $ep max]
    set hold $start_min
    set setup $start_max
    set n 0
    while {$hold < 0.010 && $n < 10} {
        if {[catch {insert_buffer $ep $ref} buf] || [sizeof_collection $buf] != 1} {
            error "Could not add single local delay at $name: $buf"
        }
        update_timing
        set new_min [endpoint_slack $ep min]
        set new_max [endpoint_slack $ep max]
        if {$new_min <= $hold || $new_min > 1000 || $new_max < min(-0.000001,$start_max)} {
            remove_buffer $buf
            update_timing
            break
        }
        set hold $new_min
        set setup $new_max
        incr n
    }
    puts $f "$name\t$start_min\t$hold\t$start_max\t$setup\t$n"
}
close $f
metrics after
write_changes -format dctcl -output pin-hold-dc.tcl
"""
DRC = r"""
foreach typ {max_capacitance min_capacitance max_transition} {
    redirect -file "$typ.rpt" [list report_constraint -all_violators -significant_digits 8 -$typ]
}
"""


def main():
    for name, digest in PINNED.items():
        check(SOURCE / name, digest)
    check(CLOCK / "constraints-pt-add.sdc", COMPAT_SHA)
    check(PT, "afdcfa7071f86d229ed3b4481f67adefd1c51bb0288b7e7d370213a43b70c9ef")
    check(DC, "23a4101c711fdb4747a57e6f9524d4989eb76a2b3120f0fa9766f4b25ae8e6d2")
    ref = json.loads((DUAL / "result.json").read_text())
    if ref["mapped_sha256"] != EXPECTED:
        raise RuntimeError("Unexpected dual-corner candidate")
    start = DUAL / "dc-dual"
    check(start / "mapped.v", EXPECTED)
    check(start / "mapped.ddc", ref["ddc_sha256"])
    execution = json.loads((SOURCE / "execution.json").read_text())
    check(SOURCE / "libraries.tcl", execution["outputs"]["libraries.tcl"]["sha256"])
    ss, ff = libraries()
    out = ROOT / "timing-pin-hold-r1"
    out.mkdir(mode=0o700)
    heavy_jobs = runpy.run_path(str(SOURCE / "run_once.py"))["heavy_jobs"]
    with (ROOT / "eda.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = start
        for tag, libs in (("ff", ff), ("ss", ss)):
            pt = execute(out, f"pt-{tag}-pins", PT,
                         pt_body(result / "mapped.v", libs) + PIN_HOLD, heavy_jobs, 650)
            count = sum(int(row.split("\t")[-1]) for row in
                        (pt / "local-hold.tsv").read_text().splitlines()[1:])
            if count == 0:
                continue
            changes = pt / "pin-hold-dc.tcl"
            if not re.search(r"(?m)^\s*insert_buffer\b", changes.read_text()):
                raise RuntimeError("Pin trial did not write expected ECO")
            result = execute(out, f"dc-{tag}-pins", DC, dc_body(result / "mapped.ddc", changes, 0),
                             heavy_jobs, 600)
        if result == start:
            raise RuntimeError("No targeted repairs were retained")
        mapped = result / "mapped.v"
        digest = sha(mapped)
        slack = {}
        for mode in ("envelope", "reset_bypass"):
            for tag, libs in (("ss", ss), ("ff", ff)):
                check(mapped, digest)
                name = f"{tag}-{mode}"
                review = execute(out, name, PT, pt_body(mapped, libs, mode=mode) + DRC, heavy_jobs, 500)
                slack[name] = dict(line.split() for line in (review / "before-slack.tsv").read_text().splitlines())
        check(mapped, digest)
        receipt = dict(mapped_sha256=digest, ddc_sha256=sha(result / "mapped.ddc"),
                       path=str(result.relative_to(ROOT)), slack_ns=slack, original_dual=EXPECTED)
        (out / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("LOCAL_HOLD_EVIDENCE_CAPTURED", digest, result, flush=True)


if __name__ == "__main__":
    main()
