#!/usr/bin/env python3
"""Apply measured clock changes, try FF hold repair, and recheck both corners."""
import fcntl
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import time

from run_formality import PINNED, SOURCE, TOP, check, limits, sha
from run_clock_eco import LC, PT

ROOT = Path(__file__).resolve().parent
DC = Path("/eda/synopsys/dc/dc_2022.03-SP5-5/bin/dc_shell")
CLOCK = ROOT / "pt-clock-root-r1"
FF_PINNED = {
    "scc40nll_vhsc40_rvt_ff_v1p21_-40c_basic.db":
        "4b7e337898e43f7309872fab438e09d2d928d4b120fcd64fb5f04481d2ea6a72",
    "xu-ramsp1024x16-ff-1p21v-m40c.db":
        "48221d84faa3b50b305a5c3f9e311e926a0dc6e67380cb8316436a76e059d310",
}
COMPAT_SHA = "404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98"
MARKER = "XU_B41_STEP_COMPLETE"
AREA = r"""
set main {u_soc/u_e203_subsys_top/u_e203_subsys_main/}
set charged 0.0
set soc 0.0
set macros 0
set internal 0
foreach_in_collection c [get_cells -hierarchical -filter {is_hierarchical == false}] {
  set ref [get_attribute $c ref_name]
  if {$ref eq {**logic_0**} || $ref eq {**logic_1**}} {continue}
  set a [get_attribute $c area]
  if {![string is double -strict $a] || $a <= 0} {error "Missing leaf area for [get_object_name $c]"}
  set n [get_object_name $c]
  set soc [expr {$soc+$a}]
  if {$ref eq {RAMSP1024X16}} {incr macros}
  if {[string first ${main}u_e203_subsys_perips/u_xu_matrix_dma/ $n] == 0 ||
      [string first ${main}u_xu_dma_shared_arb/ $n] == 0 ||
      ([string first {u_shared/} $n] == 0 && $ref ne {RAMSP1024X16})} {
    set charged [expr {$charged+$a}]
    if {$ref eq {RAMSP1024X16}} {incr internal}
  }
}
if {$macros != 337 || $internal != 17} {error "Unexpected SRAM inventory $macros $internal"}
set f [open area.tsv w]
puts $f "scored_native_library_units\t$charged\nsoc_native_library_units\t$soc\nmacro_count\t$macros\ninternal_macro_count\t$internal"
close $f
"""
REPORT = r"""
proc metrics {label} {
  update_timing -full
  set f [open "$label-slack.tsv" w]
  foreach mode {max min} {
    set p [get_timing_paths -delay_type $mode -max_paths 1 -slack_lesser_than 1e9]
    if {[sizeof_collection $p] != 1} {error "No $mode path"}
    puts $f "$mode\t[get_attribute $p slack]"
    redirect -file "$label-$mode.rpt" [list report_timing -delay_type $mode -max_paths 20 -significant_digits 8 -path_type full_clock_expanded]
  }
  close $f
  redirect -file "$label-coverage.rpt" {report_analysis_coverage -status_details {untested violated}}
  redirect -file "$label-violators.rpt" {report_constraint -all_violators -significant_digits 8}
  redirect -file "$label-check_timing.rpt" {check_timing -verbose}
  redirect -file "$label-clocks.rpt" {report_clock -attributes}
}
"""


def tcl_value(value):
    return "{" + str(value) + "}"


def execute(out, name, tool, body, heavy_jobs, timeout):
    here = out / name
    here.mkdir(mode=0o700)
    if heavy_jobs():
        raise RuntimeError("Same-account EDA slot occupied")
    script = here / "run.tcl"
    script.write_text(
        "set failure [catch {\nset_host_options -max_cores 2\n" + body
        + "\n} reason details]\n"
        + 'if {$failure} {puts stderr $reason; puts stderr [dict get $details -errorinfo]; exit 1}\n'
        + "puts {" + MARKER + "}\nexit 0\n"
    )
    command = ["timeout", "-k", "30s", str(timeout) + "s", "nice", "-n", "10", str(tool), "-f", str(script)]
    with (here / "native.log").open("xb") as log:
        started = time.time()
        print("START", name, flush=True)
        job = subprocess.Popen(command, cwd=str(here), stdout=log, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, preexec_fn=limits,
                               env=dict(os.environ, SYNOPSYS_LC_ROOT=str(LC)))
        (here / "pid").write_text(str(job.pid) + "\n")
        status = job.wait()
    text = (here / "native.log").read_text(errors="replace")
    passed = status == 0 and MARKER in text.splitlines() and not re.search(r"^Error:", text, re.M)
    (here / "receipt.json").write_text(json.dumps(dict(native_exit=status, complete=passed,
        seconds=round(time.time()-started, 3), command=command, script=sha(script),
        log=sha(here / "native.log")), indent=2) + "\n")
    if not passed:
        raise RuntimeError("Native step did not complete: " + name)
    print("DONE", name, flush=True)
    return here


def dc_body(ddc, changes, min_buffers):
    return "\n".join([
        "set_app_var sh_continue_on_error false",
        "source " + tcl_value(SOURCE / "libraries.tcl"),
        "set_svf eco.svf",
        "read_ddc " + tcl_value(ddc),
        "current_design " + TOP,
        "if {![link]} {error {DC link failed before ECO}}",
        "set oldbuf [sizeof_collection [get_cells -hierarchical -filter {ref_name == BUFV4_12TR40}]]",
        "source " + tcl_value(changes),
        "current_design " + TOP,
        "if {![link]} {error {DC link failed after ECO}}",
        "set newbuf [sizeof_collection [get_cells -hierarchical -filter {ref_name == BUFV4_12TR40}]]",
        "if {$newbuf-$oldbuf < " + str(min_buffers) + "} {error {Missing clock buffers after apply}}",
        AREA,
        "write -format verilog -hierarchy -output mapped.v",
        "write -format ddc -hierarchy -output mapped.ddc",
        "write_sdc mapped.sdc",
        "report_area -hierarchy > area.rpt",
    ])


def pt_body(mapped, libraries, repair=False, mode="envelope"):
    sdc = CLOCK / "constraints-pt-add.sdc"
    return "\n".join([
        "set_app_var link_path [list * " + " ".join(tcl_value(p) for p in libraries) + "]",
        "read_verilog " + tcl_value(mapped),
        "current_design " + TOP,
        "if {![link_design " + TOP + "]} {error {PT link failed}}",
        "if {[sizeof_collection [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}]] != 337} {error {Unexpected SRAM count}}",
        "set XU_CLOCK_MODE " + mode,
        "set XU_PLL_DIV 0",
        "set XU_PROPAGATE_CLOCKS 0",
        "source " + tcl_value(sdc),
        REPORT,
        "metrics before",
    ] + ([
        "redirect -file hold-command.rpt {fix_eco_timing -type hold -methods insert_buffer "
        "-buffer_list {BUFV2_12TR40 BUFV4_12TR40} -setup_margin 0.02 -hold_margin 0.01 "
        "-physical_mode none -timeout 420}",
        "metrics after",
        "write_changes -format dctcl -output hold-dc.tcl",
    ] if repair else []))


def main():
    for name, digest in PINNED.items():
        check(SOURCE / name, digest)
    check(SOURCE / "mapped.ddc", "6d4aa6358bc16cf090080c2b302f9f92c2015826c7957758445f3410582437a3")
    check(CLOCK / "constraints-pt-add.sdc", COMPAT_SHA)
    check(DC, "23a4101c711fdb4747a57e6f9524d4989eb76a2b3120f0fa9766f4b25ae8e6d2")
    check(PT, "afdcfa7071f86d229ed3b4481f67adefd1c51bb0288b7e7d370213a43b70c9ef")
    execution = json.loads((SOURCE / "execution.json").read_text())
    check(SOURCE / "libraries.tcl", execution["outputs"]["libraries.tcl"]["sha256"])
    ss = [Path(item["path"]) for item in execution["libraries"]]
    for path, item in zip(ss, execution["libraries"]):
        check(path, item["sha256"])
    r7_ff = Path.home() / "Desktop/xu-group-y-prelim-20261110/dc/pt-ff.tcl"
    ff = [Path(p) for p in re.findall(r"\{([^{}]+\.db)\}", r7_ff.read_text())]
    if len(ff) != 2 or {p.name for p in ff} != set(FF_PINNED):
        raise RuntimeError("Unexpected R7 FF library inventory")
    for p in ff:
        check(p, FF_PINNED[p.name])
    clock_result = json.loads((CLOCK / "result.json").read_text())
    if clock_result["status"] != "PT_CLOCK_ECO_CAPTURED":
        raise RuntimeError("Need completed clock-only PT evidence")
    for name in ("clock-dc.tcl", "clock-tree.tsv", "slack.tsv"):
        check(CLOCK / name, clock_result["output_sha256"][name])
    clock_slack = dict(line.split() for line in (CLOCK / "slack.tsv").read_text().splitlines())
    if float(clock_slack["max"]) <= -10.11695099:
        raise RuntimeError("Clock change did not improve original setup")
    num_buf = len((CLOCK / "clock-tree.tsv").read_text().splitlines()) - 1
    out = ROOT / "timing-followup-r1"
    out.mkdir(mode=0o700)
    heavy_jobs = runpy.run_path(str(SOURCE / "run_once.py"))["heavy_jobs"]
    with (ROOT / "eda.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        clock = execute(out, "dc-clock", DC, dc_body(SOURCE / "mapped.ddc", CLOCK / "clock-dc.tcl", num_buf), heavy_jobs, 420)
        execute(out, "ss-clock", PT, pt_body(clock / "mapped.v", ss), heavy_jobs, 420)
        ff_run = execute(out, "ff-hold", PT, pt_body(clock / "mapped.v", ff, repair=True), heavy_jobs, 900)
        changes = ff_run / "hold-dc.tcl"
        if not re.search(r"(?m)^\s*insert_buffer\b", changes.read_text()):
            raise RuntimeError("Hold optimizer wrote no buffer edits")
        candidate = execute(out, "dc-hold", DC, dc_body(clock / "mapped.ddc", changes, 0), heavy_jobs, 600)
        for tag, libs in (("ss", ss), ("ff", ff)):
            execute(out, tag + "-final", PT, pt_body(candidate / "mapped.v", libs), heavy_jobs, 600)
    check(SOURCE / "mapped.v", PINNED["mapped.v"])
    print("CANDIDATE", sha(candidate / "mapped.v"), candidate, flush=True)


if __name__ == "__main__":
    main()
