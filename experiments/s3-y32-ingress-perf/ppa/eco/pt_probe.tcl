source [file join $::env(XU_ECO_PACKAGE) common.tcl]
set failed [catch {
  eco_config
  set ::eco_mode probe
  eco_load_pt $::eco_mapped
  foreach command {insert_buffer write_changes get_timing_paths update_timing get_lib_pins get_attribute current_instance} {
    eco_capture native-man-${command}.rpt [list man $command]
  }
  eco_capture native-pin-attributes.rpt {list_attributes -application -class pin}
  set f [open native-pin-attributes.rpt r]; set attributes [read $f]; close $f
  eco_require [regexp {(^|\n)[ \t]*clocks[ \t]+pin[ \t]+collection([ \t]|\r?\n)} $attributes] {native pin clocks attribute is not a collection}
  eco_native_proof
  set before [eco_snapshot before]
  set clocks [eco_clocks]
  lassign [eco_plan_targets] targets protected
  eco_require [expr {[llength $targets] > 0}] {explicit current-map hold target required for mutation probe}
  lassign [lindex $targets 0] target gating family
  eco_begin_logs
  foreach delay {min max} {eco_paths [eco_pin $target] $delay $gating before_$delay}
  eco_insert $target
  foreach delay {min max} {eco_paths [eco_pin $target] $delay $gating after_$delay}
  eco_assert_protected $protected
  eco_assert_clocks $clocks
  set after [eco_snapshot after]
  eco_delta $before $after
  eco_export changes
  eco_close_logs
  eco_finish API_PROBE_COMPLETE_NOT_TIMING_CLOSURE.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
