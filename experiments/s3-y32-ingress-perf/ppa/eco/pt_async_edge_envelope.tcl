# Numeric edge-envelope experiment. Original SDC retained; unknown is never Met.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
source [file join $::env(XU_ECO_PACKAGE) parallel_reset_gpio_helpers.tcl]
proc edge_rows {} {return [lrange [rg_rows] 0 3]}
proc edge_finite {v} {return [expr {[string is double -strict $v] && $v==$v && abs($v)<1e8}]}
proc edge_source {row} {
  set n [lindex $row 0]
  if {[lindex $row 2] eq {aon}} {
    if {[string match */bootrom_deglitch/* $n]} {return io_pads_bootrom_n_i_ival}
    return io_pads_aon_pmu_dwakeup_n_i_ival
  }
  return io_pads_aon_erst_n_i_ival
}
proc edge_arrivals {row phase} {
  set name [lindex $row 0];set source [edge_source $row]
  set old [get_app_var timing_report_unconstrained_paths]
  eco_require [expr {$old in {true false 0 1}}] {native unconstrained report switch not Boolean}
  set_app_var timing_report_unconstrained_paths true
  set result [dict create]
  set failed [catch {
    foreach edge {rise fall} {
      set pin [eco_pin $name];set from [get_ports -quiet $source]
      eco_require [expr {[sizeof_collection $from]==1}] {exact external source missing}
      set paths [get_timing_paths -from $from -${edge}_to $pin -delay_type max -max_paths 64 -nworst 64]
      set count [sizeof_collection $paths]
      eco_require [expr {$count>0 && $count<64}] "no complete unconstrained max arrival proof for $name $edge; no edit accepted"
      set maximum {};set known 0;set unknown 0
      foreach_in_collection path $paths {
        eco_require [expr {[get_object_name [get_attribute $path startpoint]] eq $source && [get_object_name [get_attribute $path endpoint]] eq $name}] {arrival query escaped exact source/end}
        set arrival [get_attribute $path arrival]
        eco_require [edge_finite $arrival] "nonfinite actual max arrival for $name $edge"
        if {$maximum eq {} || $arrival>$maximum} {set maximum $arrival}
        set slack [get_attribute $path slack]
        if {[edge_finite $slack]} {incr known} else {incr unknown;set slack UNKNOWN}
        puts $::edge_arrival_log "$phase\t$name\t$source\t$edge\t$arrival\t$slack\t[get_object_name [get_attribute $path startpoint_clock]]\t[get_object_name [get_attribute $path endpoint_clock]]"
      }
      dict set result $edge $maximum
    }
  } reason opts]
  set_app_var timing_report_unconstrained_paths $old
  if {$failed} {return -options $opts $reason}
  flush $::edge_arrival_log
  return $result
}
proc edge_measure {row phase} {
  set min [rg_measure $row min $phase]
  set max [rg_measure $row max $phase 1]
  eco_require [edge_finite $min] {missing actual constrained minimum}
  if {$max ne {UNKNOWN}} {eco_require [expr {[edge_finite $max] && $max>=$::eco_setup_margin}] "known max margin insufficient: [lindex $row 0] $max"}
  puts $::edge_status_log "$phase\t[lindex $row 0]\t$min\t$max\tASYNC_EDGE_ENVELOPE_ONLY_UNKNOWN_NOT_PROMOTED"
  flush $::edge_status_log
  return [list $min $max [edge_arrivals $row $phase]]
}
proc edge_bound {row arrivals} {
  set name [lindex $row 0]
  foreach edge {rise fall} {
    set initial [dict get $::edge_baseline $name $edge]
    set actual [dict get $arrivals $edge]
    eco_require [expr {$actual>=0 && $actual<=$initial+0.5}] "max propagation exceeds baseline+0.5ns upper envelope: $name $edge $initial $actual"
  }
}
set failed [catch {
  eco_config
  eco_require [expr {$::rg_stage in {diagnose edit reload}}] {only explicit async numeric diagnostic/edit/reload supported}
  eco_require [expr {$::rg_selection eq {all}}] {this separate experiment measures all exact4 receivers}
  rg_waveform_settings
  eco_load_pt $::eco_mapped
  eco_native_proof
  rg_rows_validate
  set clocks [eco_clocks]
  eco_capture native-unconstrained-report-switch.rpt {printvar timing_report_unconstrained_paths}
  eco_capture native-unconstrained-report-switch-man.rpt {man timing_report_unconstrained_paths}
  set ::edge_arrival_log [eco_open edge-arrivals.tsv]
  puts $::edge_arrival_log "phase\tendpoint\texact_source\ttransition\tactual_arrival_ns\tconstrained_slack_or_UNKNOWN\tstart_clock\tend_clock"
  set ::edge_status_log [eco_open edge-status.tsv]
  puts $::edge_status_log "phase\tendpoint\tconstrained_min_ns\tconstrained_max_or_UNKNOWN\tqualification"
  rg_begin_logs
  set ::edge_baseline [dict create]
  if {$::rg_stage eq {reload}} {
    set f [open $::edge_baseline_reference r]
    eco_require [expr {[gets $f] eq "endpoint\trise_arrival_ns\tfall_arrival_ns"}] {invalid actual baseline arrival header}
    while {[gets $f line]>=0} {lassign [split $line \t] n r fval;eco_require [expr {![dict exists $::edge_baseline $n] && [edge_finite $r] && [edge_finite $fval]}] {invalid/duplicate numeric arrival baseline};dict set ::edge_baseline $n [dict create rise $r fall $fval]}
    close $f
    eco_require [expr {[dict size $::edge_baseline]==4}] {need exact4 original actual max-arrival baselines}
  }
  set before [eco_snapshot before]
  eco_reports before
  set summary [eco_open endpoint-summary.tsv]
  puts $summary "endpoint\tbefore_min_ns\tbefore_max_or_UNKNOWN\tafter_min_ns\tafter_max_or_UNKNOWN\tinsertions\tqualification"
  # Collect both actual max propagation polarities before the first insertion.
  set initial [dict create]
  set topology [eco_open target-topology.tsv]
  puts $topology "endpoint\treference\tlocal_net\tconstrained_min_ns\tconstrained_max_or_UNKNOWN"
  foreach row [edge_rows] {
    set name [lindex $row 0];set measured [edge_measure $row before]
    puts $topology "$name\t[lindex $row 3]\t[get_object_name [get_nets -of_objects [eco_pin $name]]]\t[lindex $measured 0]\t[lindex $measured 1]"
    dict set initial $name $measured
    if {$::rg_stage ne {reload}} {dict set ::edge_baseline $name [lindex $measured 2]} else {edge_bound $row [lindex $measured 2]}
  }
  close $topology
  if {$::rg_stage ne {reload}} {
    set f [eco_open edge-baseline-arrivals.tsv];puts $f "endpoint\trise_arrival_ns\tfall_arrival_ns"
    foreach row [edge_rows] {set n [lindex $row 0];puts $f "$n\t[dict get $::edge_baseline $n rise]\t[dict get $::edge_baseline $n fall]"};close $f
  }
  if {$::rg_stage eq {edit}} {
    # Every decision uses a complete STA update. A later endpoint can change
    # shared upstream electrical load, so revisit all four after each sweep.
    # Counts are cumulative across sweeps; neither local nor global bounds reset.
    set counts [dict create]
    foreach row [edge_rows] {dict set counts [lindex $row 0] 0}
    set converged 0
    set sweeps [eco_open full-update-sweeps.tsv]
    puts $sweeps "sweep\tendpoint\tfull_min_ns\tknown_max_or_UNKNOWN\tcumulative_endpoint_buffers\ttotal_buffers"
    for {set sweep 0} {$sweep < 32} {incr sweep} {
      update_timing -full
      foreach row [edge_rows] {
        set name [lindex $row 0]
        # Do not reuse the pre-edit initial dictionary after another endpoint
        # has changed a potentially shared upstream segment.
        lassign [edge_measure $row full_sweep_${sweep}_before] min max arrivals
        edge_bound $row $arrivals
        while {$min < $::eco_hold_margin} {
          set count [dict get $counts $name]
          eco_require [expr {$count < 8}] "async edge cumulative per-pin budget exhausted: $name"
          eco_require [expr {$::eco_inserted < 32 && $::eco_inserted < $::eco_max_buffers}] {async edge cumulative total buffer budget exhausted}
          eco_insert $name
          dict incr counts $name
          # eco_insert intentionally uses incremental updates for other flows;
          # this four-endpoint envelope experiment requires the full solution.
          update_timing -full
          lassign [edge_measure $row full_sweep_${sweep}_insert] min max arrivals
          edge_bound $row $arrivals
        }
      }
      update_timing -full
      set deficient {}
      foreach row [edge_rows] {
        set name [lindex $row 0]
        lassign [edge_measure $row full_sweep_${sweep}_verify] min max arrivals
        edge_bound $row $arrivals
        puts $sweeps "$sweep\t$name\t$min\t$max\t[dict get $counts $name]\t$::eco_inserted"
        if {$min < $::eco_hold_margin} {lappend deficient $name}
      }
      flush $sweeps
      if {[llength $deficient] == 0} {set converged 1;break}
      # The next sweep may repair a previously completed endpoint, still under
      # its original cumulative8-per-pin and32-total physical-cell budgets.
    }
    close $sweeps
    eco_require $converged {async edge full-update iteration did not converge within32 bounded sweeps}
    # Keep the final independent full update and all original max-arrival,
    # known-max and exact-clock guards. Passing local sweeps alone never exports.
    update_timing -full
    foreach row [edge_rows] {
      set name [lindex $row 0]
      lassign [edge_measure $row final] min max arrivals
      eco_require [expr {$min >= 0.03 && $min >= $::eco_hold_margin}] "final constrained min margin lost after full update: $name $min"
      edge_bound $row $arrivals
      lassign [dict get $initial $name] original_min original_max ignored_arrivals
      puts $summary "$name\t$original_min\t$original_max\t$min\t$max\t[dict get $counts $name]\tASYNC_EDGE_ENVELOPE_ONLY"
    }
    eco_assert_clocks $clocks
    eco_delta $before [eco_snapshot after]
    eco_reports after
    eco_export changes
    set marker RESET_EDIT_COLLECTED_NOT_TIMING_CLOSURE.txt
  } elseif {$::rg_stage eq {reload}} {
    foreach row [edge_rows] {lassign [dict get $initial [lindex $row 0]] min max arrivals;eco_require [expr {$min>=0.03}] {persisted edge min margin lost};edge_bound $row $arrivals}
    rg_assert_reference_clocks
    eco_reports persisted
    set marker RESET_RELOAD_COLLECTED_NOT_TIMING_CLOSURE.txt
  } else {
    eco_assert_clocks $clocks
    eco_reports diagnostic
    set marker RESET_DIAGNOSIS_COLLECTED_NOT_TIMING_CLOSURE.txt
  }
  close $summary;close $::edge_arrival_log;close $::edge_status_log
  rg_close_logs
  eco_finish $marker
} reason opts]
if {$failed} {eco_failure $reason $opts}
exit 0
