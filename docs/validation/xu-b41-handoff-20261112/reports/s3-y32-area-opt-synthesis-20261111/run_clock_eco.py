#!/usr/bin/env python3
"""Repair the selected B clock root in an isolated PrimeTime run."""
import fcntl
import json
import os
from pathlib import Path
import runpy
import socket
import subprocess
import time

from run_formality import PINNED, SOURCE, check, limits, sha

TEMPLATE = SOURCE.parents[1] / "candidate-ppa-chain-r1/pt-b-r4/baseline.tcl"
PT = Path("/eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell")
LC = Path("/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5")
ANCHOR = "  update_timing -full\n"
MARKER = "XU_B41_CLOCK_ECO_REPORTS_COMPLETE"
ECO = r"""
  set root_driver {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_hclkgen/u_e203_subsys_gfcm/U8/Z}
  set root_pin [get_pins -quiet $root_driver]
  if {[sizeof_collection $root_pin] != 1 || [get_attribute $root_pin direction] ne {out}} {
    error {Expected the GFCM output driver from the original worst path}
  }
  set segments [lsort -unique -decreasing [get_object_name [get_nets -segments -of_objects $root_pin]]]
  if {[llength $segments] == 0} {error {No GFCM net segments}}
  set lib [get_lib_cells -quiet */BUFV4_12TR40]
  if {[sizeof_collection $lib] != 1} {error {Clock buffer reference not unique}}
  set bf [get_object_name $lib]
  set log [open clock-tree.tsv w]
  puts $log "segment\tlevel\tinserted_cell\tloads"
  set inserted 0
  foreach n $segments {
    set scope [join [lrange [split $n /] 0 end-1] /]
    set loads {}
    set net [get_nets -quiet $n]
    if {[sizeof_collection $net] != 1} {error "Clock segment changed: $n"}
    foreach_in_collection pin [get_pins -of_objects $net] {
      set pn [get_object_name $pin]
      if {[get_attribute $pin direction] eq {in} && [join [lrange [split $pn /] 0 end-2] /] eq $scope} {
        lappend loads $pn
      }
    }
    set level 0
    while {[llength $loads] > 16} {
      set next {}
      set loads [lsort -unique $loads]
      for {set j 0} {$j < [llength $loads]} {incr j 16} {
        set chunk [lrange $loads $j [expr {$j+15}]]
        set pins [get_pins -quiet $chunk]
        if {[sizeof_collection $pins] != [llength $chunk]} {error "Clock sink lookup mismatch: $n"}
        set cells [insert_buffer $pins $bf]
        if {[sizeof_collection $cells] != 1} {error "Nonlocal clock grouping: $n"}
        set ip [get_pins -of_objects $cells -filter {direction == in}]
        if {[sizeof_collection $ip] != 1} {error "Inserted cell has unexpected input pins"}
        lappend next [get_object_name $ip]
        puts $log "$n\t$level\t[get_object_name $cells]\t[llength $chunk]"
        incr inserted
      }
      if {[llength $next] >= [llength $loads]} {error {Clock fanout did not decrease}}
      set loads $next
      incr level
      if {$level > 5} {error {Clock tree exceeds planned depth}}
    }
  }
  close $log
  if {$inserted < 1} {error {Clock root had no modified branch}}
  puts "XU_B41_CLOCK_BUFFERS_INSERTED $inserted"
  update_timing -full
  set f [open slack.tsv w]
  foreach mode {max min} {
    set path [get_timing_paths -delay_type $mode -max_paths 1 -slack_lesser_than 1e9]
    if {[sizeof_collection $path] != 1} {error "No $mode timing path"}
    puts $f "$mode\t[get_attribute $path slack]"
  }
  close $f
  write_changes -format dctcl -output clock-dc.tcl
  write_changes -output clock-pt.tcl
  xu_capture clocks.rpt {report_clock -attributes} 1
  xu_capture check_timing.rpt {check_timing -verbose} 1
  xu_capture coverage.rpt {report_analysis_coverage -status_details {untested violated} -sort_by slack} 1
  xu_capture setup.rpt {report_timing -delay_type max -max_paths 20 -path_type full_clock_expanded -significant_digits 8 -nets -transition_time -capacitance} 1
  xu_capture hold.rpt {report_timing -delay_type min -max_paths 50 -path_type full_clock_expanded -significant_digits 8 -nets -transition_time -capacitance} 1
  xu_capture all_violators.rpt {report_constraint -all_violators -verbose -significant_digits 8} 1
  xu_capture recovery.rpt {report_constraint -recovery -all_violators -verbose} 1
  xu_capture removal.rpt {report_constraint -removal -all_violators -verbose} 1
  xu_capture gating_hold.rpt {report_constraint -clock_gating_hold -all_violators -verbose} 1
  xu_capture max_cap.rpt {report_constraint -max_capacitance -all_violators -verbose} 1
  xu_capture max_trans.rpt {report_constraint -max_transition -all_violators -verbose} 1
  if {[llength $xu_required_failures]} {error "Required reports failed: $xu_required_failures"}
} reason options]
if {$xu_error} {
  puts stderr "XU_B41_CLOCK_ECO_ERROR: $reason"
  if {[dict exists $options -errorinfo]} {puts stderr [dict get $options -errorinfo]}
  exit 1
}
puts {XU_B41_CLOCK_ECO_REPORTS_COMPLETE}
exit 0
"""


def main():
    if socket.gethostname().split(".")[0] != "RDserver04" or Path.home().name != "s4_23usr":
        raise RuntimeError("Run on the team's competition server")
    root = Path(__file__).resolve().parent
    out = root / "pt-clock-root-r1"
    out.mkdir(mode=0o700)
    for name, digest in PINNED.items():
        check(SOURCE / name, digest)
    check(TEMPLATE, "14d5518b98a9cd31a24576361be2c36f8f2947335b0fee96daf05e2b60367434")
    check(PT, "afdcfa7071f86d229ed3b4481f67adefd1c51bb0288b7e7d370213a43b70c9ef")
    check(LC / "bin/lc_shell", "15bb8615ae34742544f2149daa47c645d41fd0080372b0a453e7bd19ed083166")
    tcl = out / "clock-root.tcl"
    prefix, sep, _ = TEMPLATE.read_text().partition(ANCHOR)
    if not sep:
        raise RuntimeError("Missing original constrained timing-update point")
    tcl.write_text(prefix + sep + ECO)
    tool_environment = dict(os.environ, XU_BASELINE_ROOT=str(SOURCE),
                            XU_MAPPED_SHA256=PINNED["mapped.v"], SYNOPSYS_LC_ROOT=str(LC))
    command = ["timeout", "-k", "30s", "1200s", "nice", "-n", "10", str(PT), "-f", str(tcl)]
    heavy_jobs = runpy.run_path(str(SOURCE / "run_once.py"))["heavy_jobs"]
    with (root / "eda.lock").open("a") as lock:
        print("WAITING_FOR_OWN_EDA_SLOT", flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        active = heavy_jobs()
        if active:
            raise RuntimeError("Same-account EDA slot occupied: " + str(active))
        started = time.time()
        with (out / "native.log").open("xb") as log:
            proc = subprocess.Popen(command, cwd=str(out), env=tool_environment, stdout=log,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, preexec_fn=limits)
            (out / "pid").write_text(str(proc.pid) + "\n")
            status = proc.wait()
    check(SOURCE / "mapped.v", PINNED["mapped.v"])
    outputs = {}
    for name in ("clock-tree.tsv", "clock-dc.tcl", "clock-pt.tcl", "slack.tsv", "native.log"):
        if (out / name).is_file():
            outputs[name] = sha(out / name)
    success = status == 0 and MARKER in (out / "native.log").read_text(errors="replace").splitlines()
    summary = dict(status="PT_CLOCK_ECO_CAPTURED" if success else "PT_CLOCK_ECO_FAILED",
                   native_exit=status, elapsed_seconds=round(time.time()-started, 3),
                   input_netlist_sha256=PINNED["mapped.v"], command=command,
                   script_sha256=sha(tcl), output_sha256=outputs,
                   constraint_scope="Original SS envelope, original ideal clocks and I/O constraints")
    (out / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(summary["status"], status, out, flush=True)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
