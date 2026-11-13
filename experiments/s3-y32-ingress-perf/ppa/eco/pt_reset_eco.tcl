# Bounded reset distribution candidate; original source/SDC/libraries fixed.
# Existing unknown/no_clock and pulse contracts remain unqualified.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
# Reuse only the sealed read-only native query and receiver identity helpers.
set f [open [file join $::env(XU_ECO_PACKAGE) pt_reset_diagnose.tcl] r]
set helpers [read $f];close $f
set split [string first {set failed [catch} $helpers]
eco_require [expr {$split>0}] {reset native diagnostic helper boundary missing}
eval [string range $helpers 0 [expr {$split-1}]]
proc reset_eco_names {objects} {return [lsort [get_object_name $objects]]}
proc reset_eco_root_metric {phase row} {
  current_instance
  set name [dict get $row driver];set pin [eco_pin $name]
  eco_require [expr {[get_attribute $pin direction] eq {out} && [get_attribute [get_cells [eco_parent $name]] ref_name] eq [dict get $row reference]}] {reset root original identity differs}
  set net [get_nets -of_objects $pin];eco_require [expr {[sizeof_collection $net]==1}] {reset root local segment ambiguous}
  set count [sizeof_collection [get_pins -leaf -of_objects $net -filter {direction == in}]]
  set cap [reset_number_or_unknown $pin drc_actual_max_capacitance];set slew [reset_number_or_unknown $pin actual_transition_max]
  eco_require [expr {$cap ne {UNKNOWN} && $slew ne {UNKNOWN} && $cap>=0 && $slew>=0}] {native reset root cap/slew unknown}
  puts $::reset_eco_metric_log "$phase\t[dict get $row net_id]\t$name\t$count\t$cap\t$slew"
  return [list $count $cap $slew]
}
proc reset_eco_insert {group} {
  set id [dict get $group id];set owner [dict get $group owner];set names [dict get $group loads];set kinds [dict get $group load_kinds]
  eco_require [expr {[llength $names]>=1 && [llength $names]<=16 && [llength $names]==[llength [lsort -unique $names]] && [llength $names]==[llength $kinds]}] {reset group exceeds16 or repeats load}
  set oldname {}
  foreach name $names kind $kinds {
    set pin [eco_pin $name]
    eco_require [expr {[get_attribute $pin direction] eq {in} && [eco_parent [eco_parent $name]] eq $owner && ![dict exists $::reset_eco_clock_pins $name]}] {reset load crosses owner or targets native clock}
    if {$kind eq {leaf}} {eco_require [expr {[file tail $name] ni {CK CLK EN}}] {reset group contains clock port}}
    if {$kind eq {new_buffer_input}} {eco_require [expr {[file tail $name] eq {I} && [string match XU_ECO_reset_* [file tail [eco_parent $name]]]}] {unplanned reset aggregation input}}
    eco_require [expr {$kind in {leaf hier_input new_buffer_input}}] {unknown reset load kind}
    set net [get_nets -of_objects $pin];eco_require [expr {[sizeof_collection $net]==1}] {reset target needs one local segment}
    set local [get_object_name $net]
    eco_require [expr {[eco_parent $local] eq $owner && [file tail $local] in [dict get $group allowed_local_net_aliases]}] {reset local segment differs from mapped aliases}
    if {$oldname eq {}} {set oldname $local} else {eco_require [expr {$oldname eq $local}] {reset group is not one actual local segment}}
  }
  set oldmembers [reset_eco_names [get_pins -of_objects [get_nets $oldname]]]
  eco_connections reset-${id}-before [get_nets $oldname]
  eco_require [expr {$::eco_inserted<$::eco_max_buffers}] {reset buffer budget exhausted}
  set buffer [eco_buffer];set area [get_attribute $buffer area]
  eco_require [expr {$::eco_added_area+$area<=$::eco_max_added_area}] {reset raw-area budget exhausted}
  eco_context $owner;set relative {}
  foreach name $names {lappend relative [string range $name [expr {[string length $owner]+($owner ne {})}] end]}
  set pins [get_pins -quiet $relative]
  eco_require [expr {[reset_eco_names $pins] eq [lsort $names]}] {scoped reset loads differ}
  set cname [dict get $group new_cell_name];set nname ${cname}_NET
  eco_require [expr {[string match XU_ECO_reset_* $cname] && [sizeof_collection [get_cells -quiet $cname]]==0 && [sizeof_collection [get_nets -quiet $nname]]==0}] {reset ECO name already exists}
  set new [insert_buffer -new_cell_names $cname -new_net_names $nname $pins $buffer]
  eco_require [expr {[sizeof_collection $new]==1}] {reset group inserted other than one buffer}
  set fullname [get_object_name $new]
  eco_require [expr {[eco_parent $fullname] eq $owner && [get_attribute $new ref_name] eq $::eco_buffer_reference}] {new reset identity/owner differs}
  current_instance
  set newnet [get_nets -of_objects [eco_pin ${fullname}/Z]]
  eco_require [expr {[sizeof_collection $newnet]==1 && [get_object_name $newnet] ne $oldname && [get_object_name [get_nets -of_objects [eco_pin ${fullname}/I]]] eq $oldname}] {reset buffer input/output segments differ}
  eco_require [expr {[reset_eco_names [get_pins -of_objects $newnet]] eq [lsort [concat $names [list ${fullname}/Z]]]}] {new reset local membership differs}
  set expectedold {}
  foreach pin $oldmembers {if {$pin ni $names} {lappend expectedold $pin}}
  lappend expectedold ${fullname}/I
  eco_require [expr {[reset_eco_names [get_pins -of_objects [get_nets $oldname]]] eq [lsort $expectedold]}] {unselected old reset member changed}
  foreach name $names {eco_require [expr {[get_object_name [get_nets -of_objects [eco_pin $name]]] eq [get_object_name $newnet]}] {selected reset target did not move}}
  incr ::eco_inserted;set ::eco_added_area [expr {$::eco_added_area+[get_attribute $new area]}]
  puts $::eco_insert_log "$fullname\t$::eco_buffer_reference\t[join $names ,]\t$oldname\t[get_attribute $new area]"
  puts $::reset_eco_group_log "$id\t$owner\t$oldname\t$fullname\t[llength $names]"
  eco_connections reset-${id}-after-new $newnet
  eco_connections reset-${id}-after-old [get_nets $oldname]
}
proc reset_eco_inserted_metrics {} {
  set f [eco_open reset-inserted-metrics.tsv];puts $f "buffer\tnet_id\tactual_leaf_loads\tnative_max_capacitance\tnative_max_transition_ns"
  foreach group $::reset_eco_groups {
    set owner [dict get $group owner];set cname [dict get $group new_cell_name];set full [expr {$owner eq {}?$cname:"$owner/$cname"}]
    set pin [eco_pin ${full}/Z];set net [get_nets -of_objects $pin]
    eco_require [expr {[sizeof_collection $net]==1 && [get_attribute [get_cells $full] ref_name] eq $::eco_buffer_reference}] {persisted reset buffer reference/net differs}
    set names [dict get $group loads]
    eco_require [expr {[reset_eco_names [get_pins -of_objects $net]] eq [lsort [concat $names [list ${full}/Z]]]}] {persisted reset local net membership differs}
    set count [sizeof_collection [get_pins -leaf -of_objects $net -filter {direction == in}]]
    eco_require [expr {$count>=1 && $count<=16}] {inserted reset output must have1..16actualleafloads}
    puts $f "$full\t[dict get $group net_id]\t$count\t[reset_number_or_unknown $pin drc_actual_max_capacitance]\t[reset_number_or_unknown $pin actual_transition_max]"
  }
  close $f
}
proc reset_eco_representatives {phase} {
  # Root-constrained worst async contexts only: bounded17roots, never1477 scans.
  set f [eco_open ${phase}-reset-root-paths.tsv]
  puts $f "net_id\tdriver\tdelay\ttransition\tlaunch_clock\tcapture_clock\tendpoint\tpath_count_limit\treturned_count\tslack_ns\tarrival_ns\tstatus"
  foreach row $::reset_eco_roots {
    set driver [eco_pin [dict get $row driver]]
    foreach delay {min max} {
      foreach edge {rise fall} {
        foreach_in_collection clock [get_clocks *] {
          set command [list get_timing_paths -${edge}_through $driver -group **async_default** -delay_type $delay -from $clock -nworst 64 -max_paths 64 -slack_lesser_than 1000000000]
          set paths [eval $command];set count [sizeof_collection $paths]
          if {$count==0} {
            puts $f "[dict get $row net_id]\t[dict get $row driver]\t$delay\t$edge\t[get_object_name $clock]\tUNKNOWN\tUNKNOWN\t64\t0\tUNKNOWN\tUNKNOWN\tNO_NATIVE_TESTED_CONTEXT_RETAINED_NOT_MET"
          }
          foreach_in_collection path $paths {
            set slack [reset_number_or_unknown $path slack];set arrival [reset_number_or_unknown $path arrival]
            set endpoint [get_object_name [get_attribute $path endpoint]];set capture [get_attribute $path endpoint_clock]
            set status NATIVE_WORST_ASYNC_CONTEXT_WITH_MARGIN
            eco_require [expr {[dict exists $::reset_eco_async_pins $endpoint] && [sizeof_collection $capture]==1 && $slack ne {UNKNOWN} && $arrival ne {UNKNOWN}}] {returned reset async context has unknown check identity/metric}
            eco_require [expr {$slack>=$::reset_required_margin}] "native worst reset recovery/removal context below required margin: $endpoint $delay $slack"
            if {$count==64} {set status NATIVE_WORST64_CONTEXT_CAPPED_NOT_EXHAUSTIVE_COVERAGE_IS_GLOBAL_GUARD}
            puts $f "[dict get $row net_id]\t[dict get $row driver]\t$delay\t$edge\t[get_object_name $clock]\t[get_object_name $capture]\t$endpoint\t64\t$count\t$slack\t$arrival\t$status"
          }
        }
      }
    }
  }
  close $f
}

set failed [catch {
  eco_config
  eco_sha $::eco_mapped $::eco_mapped_sha;eco_sha $::reset_eco_plan_file $::reset_eco_plan_sha
  source $::reset_eco_plan_file
  eco_require [expr {$::reset_eco_action in {probe split reload} && [llength $::reset_eco_roots]==17}] {only exact17distributionresetroots supported}
  eco_load_pt $::eco_mapped;eco_native_proof
  set ::reset_eco_clock_pins [dict create];set ::reset_eco_async_pins [dict create]
  foreach_in_collection pin [all_registers -clock_pins] {dict set ::reset_eco_clock_pins [get_object_name $pin] 1}
  foreach_in_collection pin [all_registers -async_pins] {dict set ::reset_eco_async_pins [get_object_name $pin] 1}
  foreach_in_collection macro [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}] {dict set ::reset_eco_clock_pins [get_object_name $macro]/CLK 1}
  set ::reset_reference_clocks $::reset_eco_reference_clocks;reset_reference_clocks
  set clocks [eco_clocks]
  set ::reset_eco_metric_log [eco_open reset-root-metrics.tsv];puts $::reset_eco_metric_log "phase\tnet_id\tdriver\tactual_leaf_loads\tnative_max_capacitance\tnative_max_transition_ns"
  if {$::reset_eco_action eq {reload}} {
    foreach row $::reset_eco_roots {
      set metrics [reset_eco_root_metric persisted $row]
      eco_require [expr {[lindex $metrics 0]==[dict get $row predicted_final_root_sink_count]}] {persisted reset root cut differs}
    }
    reset_eco_inserted_metrics;reset_eco_representatives persisted
    eco_reports persisted;eco_snapshot persisted;eco_assert_clocks $clocks
    close $::reset_eco_metric_log
    set f [eco_open RESET_PHYSICAL_PULSE_SIGNOFF_UNRESOLVED.txt];puts $f {Engineering reset electrical candidate only. Existing unknown/no_clock remain untested. External assertion pulse, physical PVT/OCV skew and release-cycle/RDC signoff are not established.};close $f
    eco_finish RESET_ECO_RELOAD_COMPLETE_NOT_QUALIFIED.txt
  } else {
    set before [eco_snapshot before];set original [dict create]
    foreach row $::reset_eco_roots {
      set metrics [reset_eco_root_metric before $row]
      eco_require [expr {[lindex $metrics 0]==[dict get $row original_flattened_sink_count]}] {seed reset root actual fanout differs from reviewed map}
      dict set original [dict get $row net_id] $metrics
    }
    reset_eco_representatives before
    eco_reports before;eco_begin_logs
    set ::reset_eco_group_log [eco_open reset-group-ledger.tsv];puts $::reset_eco_group_log "group\towner\told_net\tbuffer\trequested_loads"
    foreach group $::reset_eco_groups {reset_eco_insert $group}
    update_timing -full
    foreach row $::reset_eco_roots {
      set id [dict get $row net_id];set metrics [reset_eco_root_metric after $row];set old [dict get $original $id]
      if {$::reset_eco_action eq {split}} {
        eco_require [expr {[lindex $metrics 0]==[dict get $row predicted_final_root_sink_count] && [lindex $metrics 1]<[lindex $old 1] && [lindex $metrics 2]<=[lindex $old 2]}] {full reset root cut/cap/slew improvement failed}
      } elseif {$id eq $::reset_eco_probe_root} {
        eco_require [expr {[lindex $metrics 0]==[lindex $old 0]-3}] {fourleaf reset scopeprobe rootfanout mustdrop3}
      } else {eco_require [expr {[lindex $metrics 0]==[lindex $old 0]}] {unselected reset scopeprobe root topology changed}}
    }
    reset_eco_inserted_metrics;reset_eco_representatives after
    eco_delta $before [eco_snapshot after];eco_reports after;eco_export changes;eco_assert_clocks $clocks
    eco_close_logs;close $::reset_eco_group_log;close $::reset_eco_metric_log
    set f [eco_open RESET_PHYSICAL_PULSE_SIGNOFF_UNRESOLVED.txt];puts $f {Engineering reset electrical candidate only. Existing unknown/no_clock remain untested. External assertion pulse, physical PVT/OCV skew and release-cycle/RDC signoff are not established.};close $f
    eco_finish RESET_ECO_EDIT_COMPLETE_NOT_QUALIFIED.txt
  }
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
