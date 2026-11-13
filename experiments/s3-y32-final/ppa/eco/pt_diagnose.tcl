# Read-only THIS-map endpoint/local-clock-segment diagnosis, no physical edits.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
set failed [catch {
  eco_config
  eco_load_pt $::eco_mapped
  eco_native_proof
  set clocks [eco_clocks]
  eco_assert_clocks $clocks
  lassign [eco_plan_targets] targets protected
  eco_diagnose_clock_roots
  eco_begin_logs
  set f [eco_open target-topology.tsv]
  puts $f "endpoint\tfamily\tkind\tlocal_net\tlocal_owner\tlocal_pin_members\tmin_slack_ns\tmax_slack_ns"
  set index 0
  foreach row $targets {
    lassign $row name gating family
    set pin [eco_pin $name]
    set nets [get_nets -of_objects $pin]
    eco_require [expr {[sizeof_collection $nets] == 1}] "target needs one local segment: $name"
    set net [get_object_name $nets]
    set min [eco_paths $pin min $gating diagnostic_min]
    set max [eco_paths $pin max $gating diagnostic_max]
    puts $f "$name\t$family\t[expr {$gating ? {clock_gating_hold} : {hold}}]\t$net\t[eco_parent $net]\t[sizeof_collection [get_pins -of_objects $nets]]\t$min\t$max"
    eco_connections [format diagnostic-target-%04d $index] $nets
    incr index
  }
  close $f
  eco_assert_protected $protected
  eco_close_logs
  eco_reports diagnostic
  eco_finish DIAGNOSTIC_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
