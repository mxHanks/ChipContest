#!/usr/bin/env python3
"""Read remaining DRC pin connectivity without changing the candidate or SDC."""
import fcntl
import json
import re
import runpy
from pathlib import Path
from run_formality import PINNED, SOURCE, check, sha
from run_paired_eco import libraries
from run_timing_followup import CLOCK, COMPAT_SHA, PT, REPORT, ROOT, execute, pt_body, tcl_value

MAPPED_SHA = "f73b4518be9e6670bc8ed3bcf38623e1411ba55b1256ac6aae5b5c636c60a7a3"
CONNECT = r'''
update_timing -full
set f [open pin-connectivity.tsv w]
foreach name $probe_pins {
    set p [get_pins $name]
    if {[sizeof_collection $p] != 1} {error "Missing DRC pin $name"}
    set nets [get_nets -of_objects $p]
    set inputs 0
    set leaves 0
    if {[sizeof_collection $nets]} {
        set connected [all_connected -leaf $nets]
        set leaves [sizeof_collection $connected]
        set inputs [sizeof_collection [filter_collection $connected {direction == in}]]
    }
    puts $f "$name\t[get_attribute [get_cells -of_objects $p] ref_name]\t$inputs\t$leaves"
}
close $f
redirect -file sample-networks.rpt {
    foreach name [lrange $probe_pins 0 2] {
        report_net -connections -verbose [get_nets -of_objects [get_pins $name]]
    }
}
'''


def main():
    base = ROOT / "timing-electrical-resume-r1"
    result = json.loads((base / "result.json").read_text())
    mapped = base / "dc-electrical/mapped.v"
    if result["mapped_sha256"] != MAPPED_SHA or len(result["scenarios"]) != 4:
        raise RuntimeError("Need the completed four-scenario candidate")
    check(mapped, MAPPED_SHA)
    check(CLOCK / "constraints-pt-add.sdc", COMPAT_SHA)
    check(PT, "afdcfa7071f86d229ed3b4481f67adefd1c51bb0288b7e7d370213a43b70c9ef")
    for name, digest in PINNED.items():
        check(SOURCE / name, digest)
    ss, ff = libraries()
    heavy = runpy.run_path(str(SOURCE / "run_once.py"))["heavy_jobs"]
    out = ROOT / "drc-connectivity-r1"
    record = dict(mapped_sha256=MAPPED_SHA, constraints_sha256=COMPAT_SHA, corners={})
    with (ROOT / "eda.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out.mkdir(mode=0o700)
        for tag, libs, kinds in (("ss", ss, ("min_capacitance", "max_capacitance")),
                                 ("ff", ff, ("max_transition",))):
            categories = {}
            for kind in kinds:
                text = (base / (tag + "-envelope") / (kind + ".rpt")).read_text()
                pins = re.findall(r"^\s+(\S+/\S+)\s+(?:[-+]?\d+\.\d+\s+){3}\(VIOLATED\)", text, re.M)
                if len(pins) != result["scenarios"][tag + "-envelope"]["drc"][kind]:
                    raise RuntimeError("DRC pin list does not match original report")
                categories[kind] = pins
            pins = sorted(set(p for values in categories.values() for p in values))
            body = pt_body(mapped, libs).partition(REPORT)[0]
            body += "\nset probe_pins [list " + " ".join(tcl_value(p) for p in pins) + "]\n" + CONNECT
            native = execute(out, tag, PT, body, heavy, 300)
            rows = [line.split("\t") for line in (native / "pin-connectivity.tsv").read_text().splitlines()]
            if len(rows) != len(pins) or any(len(r) != 4 for r in rows):
                raise RuntimeError("Incomplete connectivity capture")
            record["corners"][tag] = dict(categories=categories, pins=len(rows),
                no_input_leaf_connections=sum(int(r[2]) == 0 for r in rows),
                receipt_sha256=sha(native / "receipt.json"), table_sha256=sha(native / "pin-connectivity.tsv"))
        check(mapped, MAPPED_SHA)
        (out / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print("DRC_CONNECTIVITY_CAPTURED", flush=True)


if __name__ == "__main__":
    main()
