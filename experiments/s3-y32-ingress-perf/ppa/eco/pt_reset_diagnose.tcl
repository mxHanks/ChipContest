# Read-only reset diagnostics. No insertion, deletion, replay or constraints edit.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
proc reset_finite {value} {return [expr {[string is double -strict $value] && $value==$value && abs($value)<1e8}]}
proc reset_number_or_unknown {object attribute} {
  set value [get_attribute $object $attribute]
  if {![reset_finite $value]} {return UNKNOWN}
  return $value
}
proc reset_reference_clocks {} {
  set actual [eco_clocks];set expected [dict create]
  set f [open $::reset_reference_clocks r]
  eco_require [expr {[gets $f] eq "pin\tclocks"}] {invalid seed original clock association header}
  while {[gets $f line]>=0} {
    set fields [split $line \t]
    eco_require [expr {[llength $fields]==2 && ![dict exists $expected [lindex $fields 0]]}] {invalid seed original clock association row}
    dict set expected [lindex $fields 0] [lindex $fields 1]
  }
  close $f
  eco_require [expr {[dict size $expected]==[dict size $actual]}] {seed clock endpoint count differs}
  dict for {pin clocks} $expected {eco_require [expr {[dict exists $actual $pin] && [dict get $actual $pin] eq $clocks}] "seed clock association differs: $pin"}
}
proc reset_paths {row pin delay} {
  set name [dict get $row pin];set total 0;set invalid 0;set worst UNKNOWN
  # An unrestricted native selector also captures tested port/no-launch-clock
  # paths; the exact original clocks are queried separately. Empty contexts are
  # explicitly recorded and never become slack=0 or evidence of a tested check.
  set selectors [linsert [lsort [get_object_name [get_clocks *]]] 0 ALL_NATIVE_STARTPOINTS]
  foreach edge {rise fall} {
    foreach launch $selectors {
      set selection [list -${edge}_to $pin -delay_type $delay -group **async_default** -slack_lesser_than 1000000000]
      if {$launch ne {ALL_NATIVE_STARTPOINTS}} {lappend selection -from [get_clocks $launch]}
      set caps {}
      foreach cap {64 256 1024 4096} {if {$cap<$::reset_max_paths_per_query} {lappend caps $cap}}
      lappend caps $::reset_max_paths_per_query
      incr ::reset_query_count
      foreach cap $caps {
        set paths [eval [concat [list get_timing_paths] $selection [list -nworst $cap -max_paths $cap]]]
        set found [sizeof_collection $paths]
        puts $::reset_query_log "$::reset_query_count\t$name\t$delay\t$edge\t$launch\t$cap\t$found"
        flush $::reset_query_log
        if {$found<$cap} {break}
      }
      if {$found>=$::reset_max_paths_per_query} {
        eco_capture reset-query-capped-${::reset_query_count}.rpt [concat [list report_timing] $selection [list -max_paths 128 -nworst 128 -path_type full_clock_expanded -significant_digits 8 -nets -input_pins -transition_time -capacitance]]
        error "reset receiver query is saturated, not complete: $name $delay $edge $launch"
      }
      if {$found==0} {
        puts $::reset_path_log "[join [dict get $row net_ids] ,]\t$name\t$delay\t$edge\t$launch\tUNKNOWN\tUNKNOWN\tUNKNOWN\tUNKNOWN\tNO_NATIVE_TESTED_PATH_CONTEXT"
      }
      foreach_in_collection path $paths {
        eco_require [expr {[get_object_name [get_attribute $path endpoint]] eq $name}] {reset path query escaped exact receiving pin}
        set slack [reset_number_or_unknown $path slack];set arrival [reset_number_or_unknown $path arrival]
        set capture [get_attribute $path endpoint_clock];set group [get_attribute $path path_group]
        set status NATIVE_TESTED_PATH
        if {$slack eq {UNKNOWN} || $arrival eq {UNKNOWN} || [sizeof_collection $capture]!=1 || [get_object_name $group] ne {**async_default**}} {
          set status UNKNOWN_NATIVE_CHECK_CONTEXT;incr invalid
        } else {
          incr total
          if {$worst eq {UNKNOWN} || $slack<$worst} {set worst $slack}
          foreach netid [dict get $row net_ids] {
            set key [list $netid $delay $edge $launch [get_object_name $capture]]
            if {![dict exists $::reset_spread $key]} {dict set ::reset_spread $key [dict create minimum $arrival maximum $arrival pins [dict create]]}
            set state [dict get $::reset_spread $key]
            if {$arrival<[dict get $state minimum]} {dict set state minimum $arrival}
            if {$arrival>[dict get $state maximum]} {dict set state maximum $arrival}
            dict set state pins $name 1;dict set ::reset_spread $key $state
          }
        }
        puts $::reset_path_log "[join [dict get $row net_ids] ,]\t$name\t$delay\t$edge\t$launch\t[get_object_name $capture]\t[get_object_name [get_attribute $path startpoint]]\t$slack\t$arrival\t$status"
      }
      flush $::reset_path_log
    }
  }
  return [list $total $worst $invalid]
}
set failed [catch {
  eco_config
  eco_sha $::eco_mapped $::eco_mapped_sha
  eco_sha $::reset_plan_file $::reset_plan_sha
  source $::reset_plan_file
  eco_require [expr {$::reset_diagnostic_schema eq {ingress1064-reset-receiver-diagnostic-plan-v1} && $::reset_origin_map_sha eq {882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e} && !$::reset_mutation_authorized}] {only original1064 read-only reset diagnostics supported}
  eco_require [expr {[llength $::reset_roots]==17 && [llength $::reset_receivers]==1477 && $::reset_max_receivers>=1477}] {reset diagnostic catalogue/budget differs}
  eco_load_pt $::eco_mapped
  eco_native_proof
  if {[info exists ::reset_reference_clocks]} {reset_reference_clocks}
  eco_capture native-timing-path-attributes.rpt {list_attributes -application -class timing_path}
  eco_capture native-pin-attributes.rpt {list_attributes -application -class pin}
  foreach command {get_timing_paths all_registers report_timing report_analysis_coverage} {eco_capture native-man-${command}.rpt [list man $command]}
  set before [eco_snapshot before];set clocks [eco_clocks]
  eco_begin_logs
  set async [dict create]
  foreach_in_collection pin [all_registers -async_pins] {dict set async [get_object_name $pin] 1}
  set native_members [eco_open reset-native-electrical-members.tsv]
  puts $native_members "net_id\tdriver\tlocal_net\tleaf_pin\tdirection\treference\tnative_async_receiver"
  set root_metrics [eco_open reset-root-metrics.tsv]
  puts $root_metrics "net_id\tdriver\toriginal_static_electrical_sink_count\tnative_electrical_sink_count\tnative_max_capacitance\tnative_max_transition_ns\ttopology_status"
  foreach row $::reset_roots {
    set name [dict get $row driver];set pin [eco_pin $name]
    eco_require [expr {[get_attribute $pin direction] eq {out} && [get_attribute [get_cells [eco_parent $name]] ref_name] eq [dict get $row reference]}] {reset root identity differs; rebind the current integrated map}
    set net [get_nets -of_objects $pin];eco_require [expr {[sizeof_collection $net]==1}] {reset root requires one exact local segment}
    set loads [get_pins -leaf -of_objects $net -filter {direction == in}];set count [sizeof_collection $loads]
    set status NATIVE_ROOT_MATCHES_STATIC_COUNT
    if {$count!=[dict get $row original_electrical_sink_count]} {set status NATIVE_ROOT_DIFFERS_REBIND_REQUIRED_NO_MUTATION}
    puts $root_metrics "[dict get $row net_id]\t$name\t[dict get $row original_electrical_sink_count]\t$count\t[reset_number_or_unknown $pin drc_actual_max_capacitance]\t[reset_number_or_unknown $pin actual_transition_max]\t$status"
    foreach_in_collection load $loads {
      set lname [get_object_name $load]
      puts $native_members "[dict get $row net_id]\t$name\t[get_object_name $net]\t$lname\t[get_attribute $load direction]\t[get_attribute [get_cells [eco_parent $lname]] ref_name]\t[dict exists $async $lname]"
    }
    eco_connections reset-[dict get $row net_id]-local $net
    eco_capture reset-[dict get $row net_id]-net.rpt [list report_net -connections $net]
  }
  close $native_members;close $root_metrics
  set ::reset_query_count 0;set ::reset_spread [dict create]
  set ::reset_query_log [eco_open reset-query-attempts.tsv]
  puts $::reset_query_log "query\tpin\tdelay\ttransition\tlaunch_selector\tquery_cap\tnative_paths"
  set ::reset_path_log [eco_open reset-native-paths.tsv]
  puts $::reset_path_log "net_ids\tpin\tdelay\ttransition\tlaunch_selector\tcapture_clock\tstartpoint\tslack_ns\tarrival_ns\tstatus"
  set summary [eco_open reset-receiver-summary.tsv]
  puts $summary "net_ids\tpin\treference\tstatus\tremoval_min_paths\tremoval_min_slack_ns\trecovery_max_paths\trecovery_max_slack_ns\tinvalid_contexts\tmutation_authorized"
  set metrics [eco_open reset-receiver-metrics.tsv]
  puts $metrics "net_ids\tpin\tnative_max_pin_capacitance\tnative_max_transition_ns\tmin_rise_arrival_ns\tmax_rise_arrival_ns\tmin_fall_arrival_ns\tmax_fall_arrival_ns"
  foreach row $::reset_receivers {
    set name [dict get $row pin];set ids [join [dict get $row net_ids] ,];set pins [get_pins -quiet $name]
    if {[sizeof_collection $pins]!=1 || [get_object_name $pins] ne $name || ![dict exists $async $name]} {
      puts $summary "$ids\t$name\t[dict get $row reference]\tEXCLUDED_MISSING_NATIVE_ASYNC_RECEIVER\t0\tUNKNOWN\t0\tUNKNOWN\tUNKNOWN\t0";continue
    }
    set pin [eco_pin $name];set cell [get_cells [eco_parent $name]];set ref [get_attribute $cell ref_name]
    set lib [get_lib_cells -quiet */$ref]
    if {$ref ne [dict get $row reference] || [get_attribute $cell is_hierarchical] || [sizeof_collection $lib]!=1 || ![get_attribute $lib is_sequential] || [get_attribute $pin direction] ne {in}} {
      puts $summary "$ids\t$name\t$ref\tEXCLUDED_NATIVE_RECEIVER_IDENTITY_DIFFERS\t0\tUNKNOWN\t0\tUNKNOWN\tUNKNOWN\t0";continue
    }
    set values {}
    foreach attribute {pin_capacitance_max actual_transition_max min_rise_arrival max_rise_arrival min_fall_arrival max_fall_arrival} {lappend values [reset_number_or_unknown $pin $attribute]}
    puts $metrics "$ids\t$name\t[join $values \t]"
    lassign [reset_paths $row $pin min] nmin smin imin
    lassign [reset_paths $row $pin max] nmax smax imax
    set status NATIVE_MIN_MAX_KNOWN_WITH_MARGIN_NOT_RESET_AUTHORIZATION
    if {$nmin==0 || $nmax==0 || $imin+$imax>0} {
      set status EXCLUDED_RECOVERY_OR_REMOVAL_UNKNOWN
    } elseif {$smin<$::reset_required_margin || $smax<$::reset_required_margin} {
      set status EXCLUDED_INSUFFICIENT_RECOVERY_OR_REMOVAL_MARGIN
    } elseif {{UNKNOWN} in $values} {set status EXCLUDED_ASSERTION_RELEASE_OR_ELECTRICAL_METRIC_UNKNOWN}
    puts $summary "$ids\t$name\t$ref\t$status\t$nmin\t$smin\t$nmax\t$smax\t[expr {$imin+$imax}]\t0"
    flush $summary
  }
  close $summary;close $metrics;close $::reset_query_log;close $::reset_path_log
  set spread [eco_open reset-release-context-spread.tsv]
  puts $spread "net_id\tdelay\ttransition\tlaunch_selector\tcapture_clock\tnative_receiver_count\tminimum_arrival_ns\tmaximum_arrival_ns\tspread_ns\tqualification"
  dict for {key state} $::reset_spread {
    puts $spread "[join $key \t]\t[dict size [dict get $state pins]]\t[dict get $state minimum]\t[dict get $state maximum]\t[expr {[dict get $state maximum]-[dict get $state minimum]}]\tNATIVE_CONTEXT_ENVELOPE_NOT_RELEASE_CYCLE_OR_PULSE_PROOF"
  }
  close $spread
  eco_reports reset-diagnostic
  eco_delta $before [eco_snapshot after]
  eco_assert_clocks $clocks
  eco_close_logs
  set f [eco_open RESET_EDITS_NOT_AUTHORIZED.txt]
  puts $f {DIAGNOSTICS_ONLY. Unknown or missing per-receiver checks are excluded. Native max/min margin alone does not establish assertion pulse, release cycle alignment, physical RDC/MTBF or external pulse contract. No reset edit, DC replay, SVF or closure is produced.}
  close $f
  eco_finish RESET_DIAGNOSTIC_COLLECTION_COMPLETE_NOT_AUTHORIZED.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
