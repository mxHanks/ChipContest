source [file join $::env(XU_ECO_PACKAGE) common.tcl]
source [file join $::env(XU_ECO_PACKAGE) parallel_reset_gpio_helpers.tcl]
set failed [catch {
  eco_config
  rg_waveform_settings
  eco_load_pt $::eco_mapped
  eco_native_proof
  rg_rows_validate
  set clocks [eco_clocks]
  if {$::rg_stage eq {discover}} {
    eco_capture waveform-discovery.rpt {printvar *waveform*}
    eco_capture expansion-discovery.rpt {printvar *expand*}
    # Official native message documentation; no guessed app variable is set.
    eco_capture pte052-manual.rpt {man PTE-052}
    eco_assert_clocks $clocks
    eco_reports diagnostic
    rg_gpio diagnostic
    eco_finish RESET_DISCOVERY_COLLECTED_NOT_TIMING_CLOSURE.txt
  } elseif {$::rg_stage eq {diagnose}} {
    rg_begin_logs
    rg_diagnose
    rg_close_logs
    eco_assert_clocks $clocks
    eco_reports diagnostic
    rg_gpio diagnostic
    eco_finish RESET_DIAGNOSIS_COLLECTED_NOT_TIMING_CLOSURE.txt
  } elseif {$::rg_stage eq {edit}} {
    set before [eco_snapshot before]
    eco_reports before
    rg_gpio before
    set wf [open [file join $::eco_out before-check_timing.rpt] r]
    set clock_check [read $wf]; close $wf
    eco_require [expr {![regexp {periods were not expandable|Failed clocks set} $clock_check]}] {HF/LF clock expansion remains unresolved; delay ECO is refused before any insertion}
    rg_begin_logs
    set initial [dict create]
    # Preflight ALL selected max paths before the first physical mutation.
    foreach row [rg_selected] {
      set min [rg_measure $row min before_min]
      set max [rg_measure $row max before_max]
      eco_require [expr {$max >= $::eco_setup_margin}] "setup/recovery has insufficient numeric margin; no delay ECO accepted: [lindex $row 0] $max"
      dict set initial [lindex $row 0] [list $min $max]
    }
    set f [eco_open endpoint-summary.tsv]
    puts $f "endpoint\tfamily\tbefore_min_ns\tbefore_max_ns\tafter_min_ns\tafter_max_ns\tinsertions"
    foreach row [rg_selected] {
      lassign $row name mode family ref
      lassign [dict get $initial $name] original_min original_max
      set min $original_min; set max $original_max; set added 0
      while {$min < $::eco_hold_margin} {
        eco_require [expr {$added < $::eco_max_per_pin}] "per-endpoint buffer budget exhausted: $name"
        eco_insert $name
        incr added
        set min [rg_measure $row min after_min]
        set max [rg_measure $row max after_max]
        eco_require [expr {$max >= $::eco_setup_margin}] "setup/recovery margin lost: $name"
      }
      puts $f "$name\t$family\t$original_min\t$original_max\t$min\t$max\t$added"
      flush $f
    }
    close $f
    update_timing -full
    # Full update must still satisfy both min and max; incremental results alone are insufficient.
    foreach row [rg_selected] {
      eco_require [expr {[rg_measure $row min final_min] >= $::eco_hold_margin && [rg_measure $row max final_max] >= $::eco_setup_margin}] "target margin lost after full update: [lindex $row 0]"
    }
    eco_assert_clocks $clocks
    eco_delta $before [eco_snapshot after]
    eco_reports after
    rg_gpio after
    eco_export changes
    rg_close_logs
    eco_finish RESET_EDIT_COLLECTED_NOT_TIMING_CLOSURE.txt
  } elseif {$::rg_stage eq {reload}} {
    rg_begin_logs
    rg_diagnose
    foreach row [rg_selected] {
      eco_require [expr {[rg_measure $row min reload_min] >= $::eco_hold_margin && [rg_measure $row max reload_max] >= $::eco_setup_margin}] "persisted target margin failed: [lindex $row 0]"
    }
    rg_close_logs
    rg_assert_reference_clocks
    eco_reports persisted
    rg_gpio persisted
    eco_finish RESET_RELOAD_COLLECTED_NOT_TIMING_CLOSURE.txt
  } else {error {unsupported reset/GPIO stage}}
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
