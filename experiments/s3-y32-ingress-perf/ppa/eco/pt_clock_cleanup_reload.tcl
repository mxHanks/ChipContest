# Fresh read-only PT on DC-persisted clock cleanup; unchanged original SDC/DB.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
proc cleanup_real_leaf_sinks {name} {
  set net [get_nets -of_objects [eco_pin $name]]
  eco_require [expr {[sizeof_collection $net]==1}] {cleanup output lacks one local net}
  set sinks {}
  foreach_in_collection pin [get_pins -leaf -of_objects $net -filter {direction == in}] {
    set pn [get_object_name $pin];set cell [get_cells -quiet [eco_parent $pn]]
    eco_require [expr {[sizeof_collection $cell]==1}] {cleanup sink parent ambiguous}
    if {![get_attribute $cell is_hierarchical]} {lappend sinks $pn}
  }
  return [lsort $sinks]
}
set failed [catch {
  eco_config
  eco_sha $::clock_cleanup_plan_file $::clock_cleanup_plan_sha
  source $::clock_cleanup_plan_file
  eco_load_pt $::eco_mapped
  set actual [eco_clocks]
  set f [open $::eco_reference_clocks r]
  eco_require [expr {[string map [list {\t} "\t"] [gets $f]] eq "pin\tclocks"}] {invalid current seed clock header}
  set expected [dict create]
  while {[gets $f line]>=0} {
    set fields [split [string map [list {\t} "\t"] $line] \t]
    eco_require [expr {[llength $fields]==2 && ![dict exists $expected [lindex $fields 0]]}] {invalid duplicate seed clock row}
    dict set expected [lindex $fields 0] [lsort [lindex $fields 1]]
  }
  close $f
  eco_require [expr {[dict size $actual]==[dict size $expected]}] {cleanup changed current clock endpoint count}
  dict for {pin clocks} $actual {eco_require [expr {[dict exists $expected $pin] && [dict get $expected $pin] eq $clocks}] "cleanup clock association changed: $pin"}
  eco_assert_clocks $actual
  set macros [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}]
  eco_require [expr {[sizeof_collection $macros]==353 && [lsort [get_object_name $macros]] eq [lsort $::clock_cleanup_macros]}] {cleanup353 original SRAM set changed}
  foreach_in_collection cell $macros {set pin [get_object_name $cell]/CLK;eco_require [expr {[dict exists $actual $pin] && [dict get $actual $pin] eq [dict get $expected $pin]}] {cleanup SRAM CLK changed}}
  foreach name $::clock_cleanup_removed {eco_require [expr {[sizeof_collection [get_cells -quiet $name]]==0}] {deleted added buffer persists}}
  set retained [dict create];set f [eco_open clock-cleanup-final-fanout.tsv];puts $f "buffer\ttrue_leaf_sink_count"
  foreach row $::clock_cleanup_remaining {
    set name [dict get $row instance];set cell [get_cells -quiet $name]
    eco_require [expr {[sizeof_collection $cell]==1 && [get_attribute $cell ref_name] eq {BUFV2_12TR40}}] {retained clock buffer missing/reference changed}
    set sinks [cleanup_real_leaf_sinks ${name}/Z]
    eco_require [expr {[llength $sinks]>=1 && [llength $sinks]<=32 && $sinks eq [lsort [dict get $row sinks]]}] "cleanup native retained buffer leaf membership differs: $name"
    puts $f "$name\t[llength $sinks]";dict set retained $name 1
  }
  close $f
  set seen 0
  foreach_in_collection cell [get_cells -hierarchical -filter {is_hierarchical == false}] {
    set name [get_object_name $cell]
    if {[regexp {/XU_ECO_clock_g[0-9][0-9][0-9][0-9]$} $name]} {incr seen;eco_require [dict exists $retained $name] {unexpected retained clock buffer}}
  }
  eco_require [expr {$seen==[dict size $retained]}] {clock cleanup retained inventory mismatch}
  set roots [cleanup_real_leaf_sinks $::clock_cleanup_root]
  eco_require [expr {[llength $roots]>=1 && [llength $roots]<=32 && $roots eq [lsort $::clock_cleanup_root_sinks]}] {cleanup native root membership differs/outside32}
  set f [eco_open clock-cleanup-root-fanout.tsv];puts $f "driver\ttrue_leaf_sink_count";puts $f "$::clock_cleanup_root\t[llength $roots]";close $f
  eco_reports persisted
  eco_finish CLOCK_CLEANUP_RELOAD_COMPLETE_NOT_TIMING_CLOSURE.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
