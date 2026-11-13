source [file join $::env(XU_ECO_PACKAGE) common.tcl]
set failed [catch {
  eco_config
  eco_require [expr {$::eco_mode in {bias gating bias-gating}}] {invalid bounded delay experiment}
  eco_load_pt $::eco_mapped
  eco_native_proof
  set before [eco_snapshot before]
  set clocks [eco_clocks]
  set protected [dict create]
  set targets {}
  if {$::eco_mode in {bias bias-gating}} {
    foreach name [eco_bias_targets] {lappend targets [list $name 0]}
  }
  if {$::eco_mode in {gating bias-gating}} {
    lassign [eco_gate_targets] names protected
    foreach name $names {lappend targets [list $name 1]}
  }
  eco_reports before
  eco_begin_logs
  set f [eco_open endpoint-summary.tsv]
  puts $f "endpoint\tfamily\tbefore_min_ns\tbefore_max_ns\tafter_min_ns\tafter_max_ns\tinsertions"
  foreach row $targets {
    lassign $row name gating
    set pin [eco_pin $name]
    set original_min [eco_paths $pin min $gating]
    set original_max [eco_paths $pin max $gating]
    # A pre-existing endpoint setup failure cannot be repaired with extra delay.
    eco_require [expr {$original_max >= $::eco_setup_margin}] "target setup margin insufficient before hold edit: $name"
    set min $original_min; set max $original_max; set added 0
    while {$min < $::eco_hold_margin} {
      eco_require [expr {$added < $::eco_max_per_pin}] "per-pin buffer budget exhausted at $name"
      eco_insert $name
      incr added
      set min [eco_paths [eco_pin $name] min $gating]
      set max [eco_paths [eco_pin $name] max $gating]
      eco_require [expr {$max >= $::eco_setup_margin}] "setup regressed below experiment margin at $name"
      eco_assert_protected $protected
    }
    puts $f "$name\t[expr {$gating ? {gating_enable} : {bias_D}}]\t$original_min\t$original_max\t$min\t$max\t$added"
    flush $f
  }
  close $f
  eco_assert_clocks $clocks
  eco_delta $before [eco_snapshot after]
  eco_reports after
  eco_export changes
  eco_close_logs
  eco_finish EDIT_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
