# Fresh process loads DC-persisted ECO mapped.v under the unchanged original SDC.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
set failed [catch {
  eco_config
  eco_load_pt $::eco_mapped
  eco_native_proof
  set snapshot [eco_snapshot persisted]
  set actual [eco_clocks]
  set f [open $::eco_reference_clocks r]
  eco_require [expr {[gets $f] eq "pin\tclocks"}] {invalid original clock-association header}
  set expected [dict create]
  while {[gets $f line] >= 0} {
    set fields [split $line \t]
    eco_require [expr {[llength $fields] == 2}] {invalid original clock-association row}
    dict set expected [lindex $fields 0] [lindex $fields 1]
  }
  close $f
  eco_require [expr {[dict size $expected] == [dict size $actual]}] {persisted original clock endpoint count changed}
  dict for {pin clocks} $expected {
    eco_require [expr {[dict exists $actual $pin] && [dict get $actual $pin] eq $clocks}] "persisted original clock association changed: $pin"
  }
  eco_assert_clocks $actual
  eco_reports persisted
  # No zero-violation verdict is inferred here. Full reports require review,
  # including every untested reason, cross-clock contract and design-rule limit.
  eco_finish RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
