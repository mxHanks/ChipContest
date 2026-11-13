# Numeric edge-envelope experiment. Original SDC retained; unknown is never Met.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
source [file join $::env(XU_ECO_PACKAGE) parallel_reset_gpio_helpers.tcl]
proc edge_rows {} {return [lrange [rg_rows] 4 6]}
proc edge_finite {v} {return [expr {[string is double -strict $v] && $v==$v && abs($v)<1e8}]}
proc edge_source {row} {
  set n [lindex $row 0]
  if {[lindex $row 2] eq {aon}} {
    if {[string match */bootrom_deglitch/* $n]} {return io_pads_bootrom_n_i_ival}
    return io_pads_aon_pmu_dwakeup_n_i_ival
  }
  return io_pads_aon_erst_n_i_ival
}
# Native per-arc max delays form a conservative propagation upper bound.
# The original required-time/unknown checks are never replaced by this bound.
proc arc_object {name} {
  if {$name eq {io_pads_aon_erst_n_i_ival}} {
    set obj [get_ports -quiet $name]
    eco_require [expr {[sizeof_collection $obj]==1}] {exact ERST source missing}
    return $obj
  }
  return [eco_pin $name]
}
proc arc_step {from to cell values phase endpoint} {
  set arcs [get_timing_arcs -from [arc_object $from] -to [arc_object $to] -filter "is_cellarc == $cell && is_disabled == false"]
  set count [sizeof_collection $arcs]
  eco_require [expr {$count>=1 && $count<=8}] "missing/ambiguous enabled native arc: $from -> $to"
  set output [dict create]
  foreach_in_collection arc $arcs {
    eco_require [expr {[get_object_name [get_attribute $arc from_pin]] eq $from && [get_object_name [get_attribute $arc to_pin]] eq $to}] {native arc escaped exact from/to}
    set sense [get_attribute $arc sense]
    # Native T-2022 returns empty sense/user-disabled on physical net arcs.
    # Enabled is_disabled=false plus an exact driver/load net arc is required;
    # a wire preserves polarity. Empty cell-arc sense remains an error.
    if {!$cell && $sense eq {}} {set sense positive_unate}
    eco_require [expr {$sense in {positive_unate negative_unate non_unate}}] "unknown native timing sense: $sense"
    foreach edge {rise fall} {
      set delay [get_attribute $arc delay_max_${edge}]
      eco_require [expr {[edge_finite $delay] && $delay>=0}] "unknown/negative native max arc delay: $from $to $edge $delay"
      if {$sense eq {positive_unate}} {set arrival [dict get $values $edge]} elseif {$sense eq {negative_unate}} {
        set other [expr {$edge eq {rise}?{fall}:{rise}}];set arrival [dict get $values $other]
      } else {set arrival [expr {max([dict get $values rise],[dict get $values fall])}]}
      set value [expr {$arrival+$delay}]
      if {![dict exists $output $edge] || $value>[dict get $output $edge]} {dict set output $edge $value}
      puts $::arc_log "$phase\t$endpoint\t$from\t$to\t$cell\t$sense\t$edge\t$delay\t$value\tNATIVE_ARC_SUM_UPPER_BOUND_REQUIRED_UNKNOWN_RETAINED"
    }
    if {$phase eq {before} && $::rg_stage eq {diagnose}} {
      eco_capture [format arc-delay-%04d.rpt $::arc_report_count] [list report_delay_calculation -max -of_objects $arc -nosplit]
      incr ::arc_report_count
    }
  }
  return $output
}
proc edge_arrivals {row phase} {
  set target [lindex $row 0];set w $::rg_wrapper
  set owner [eco_parent [eco_parent $target]]
  set inv [expr {[string match */reg_2 $owner]?{U3}:{U2}}]
  set invname $owner/$inv;set invout $invname/ZN
  eco_require [expr {[get_attribute [get_cells $w/U10] ref_name] eq {NAND2BV0_12TR40} && [get_attribute [get_cells $invname] ref_name] eq {CLKINV0_12TR40}}] {original ERST/NAND/inverter topology changed}
  # Traverse only the exact RDN tail and our single-load identity additions.
  set tail {};set sink $target;set reached 0
  for {set step 0} {$step<=8} {incr step} {
    set arcs [get_timing_arcs -to [eco_pin $sink] -filter {is_cellarc == false && is_disabled == false}]
    if {[sizeof_collection $arcs]!=1} {
      set f [eco_open native-tail-arc-diagnostic.tsv]
      puts $f "query\tcount\tfrom\tto\tis_cellarc\tis_disabled\tis_user_disabled\tsense\trise_max\tfall_max"
      foreach query {to_pin of_net} {
        if {$query eq {to_pin}} {set raw [get_timing_arcs -to [eco_pin $sink]]} else {set raw [get_timing_arcs -of_objects [get_nets -of_objects [eco_pin $sink]]]}
        puts $f "$query\t[sizeof_collection $raw]"
        foreach_in_collection arc $raw {
          set values [list $query [sizeof_collection $raw] [get_object_name [get_attribute $arc from_pin]] [get_object_name [get_attribute $arc to_pin]]]
          foreach attribute {is_cellarc is_disabled is_user_disabled sense delay_max_rise delay_max_fall} {lappend values [get_attribute $arc $attribute]}
          puts $f [join $values \t]
        }
      }
      close $f
    }
    eco_require [expr {[sizeof_collection $arcs]==1}] "RDN tail must have one enabled native net arc: $sink"
    set from [get_object_name [get_attribute $arcs from_pin]]
    set actual_to [get_object_name [get_attribute $arcs to_pin]]
    eco_require [expr {$actual_to eq $sink}] {tail net arc escaped exact sink}
    set tail [linsert $tail 0 [list $from $sink false]]
    if {$from eq $invout} {set reached 1;break}
    set parent [eco_parent $from]
    eco_require [expr {[eco_parent $parent] eq $owner && [string match XU_ECO_catch_arc_* [file tail $parent]] && [file tail $from] eq {Z} && [get_attribute [get_cells $parent] ref_name] eq {BUFV2_12TR40}}] {tail crossed unreviewed driver/buffer/owner}
    set tail [linsert $tail 0 [list $parent/I $parent/Z true]]
    set sink $parent/I
  }
  eco_require $reached {RDN tail did not reach exact original inverter within8buffers}
  # Original SHA-pinned SDC assigns ERST maximum IO delay0.5ns. Each arc adds
  # native per-transition max delay, including net arcs across hierarchy.
  set values [dict create rise 0.5 fall 0.5]
  set prefix [list [list io_pads_aon_erst_n_i_ival $w/U10/B1 false] [list $w/U10/B1 $w/U10/ZN true] [list $w/U10/ZN $invname/I false] [list $invname/I $invout true]]
  foreach item [concat $prefix $tail] {lassign $item from to cell;set values [arc_step $from $to $cell $values $phase $target]}
  foreach edge {rise fall} {puts $::edge_arrival_log "$phase\t$target\tio_pads_aon_erst_n_i_ival\t$edge\t[dict get $values $edge]\tUNKNOWN\tARC_SUM_UPPER_BOUND\tNOT_TIMING_QUALIFIED"}
  flush $::arc_log;flush $::edge_arrival_log
  return $values
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
  eco_require [expr {$::rg_selection eq {all}}] {this separate experiment measures all exact3 receivers}
  rg_waveform_settings
  eco_load_pt $::eco_mapped
  eco_native_proof
  rg_rows_validate
  set clocks [eco_clocks]
  eco_capture native-unconstrained-report-switch.rpt {printvar timing_report_unconstrained_paths}
  eco_capture native-unconstrained-report-switch-man.rpt {man timing_report_unconstrained_paths}
  set ::arc_log [eco_open native-arc-delays.tsv]
  puts $::arc_log "phase\tendpoint\tfrom\tto\tis_cellarc\tsense\ttransition\tnative_delay_ns\tarrival_upper_ns\tqualification"
  set ::arc_report_count 0
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
    eco_require [expr {[dict size $::edge_baseline]==3}] {need exact3 original actual max-arrival baselines}
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
    # shared upstream electrical load, so revisit all three after each sweep.
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
          eco_require [expr {$::eco_inserted < 24 && $::eco_inserted < $::eco_max_buffers}] {async edge cumulative total buffer budget exhausted}
          eco_insert $name
          dict incr counts $name
          # eco_insert intentionally uses incremental updates for other flows;
          # this three-endpoint envelope experiment requires the full solution.
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
      # its original cumulative8-per-pin and24-total physical-cell budgets.
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
  close $summary;close $::edge_arrival_log;close $::edge_status_log;close $::arc_log
  rg_close_logs
  eco_finish $marker
} reason opts]
if {$failed} {eco_failure $reason $opts}
exit 0
