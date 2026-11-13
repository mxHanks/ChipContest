# Optional topology collection / ONE four-load non-reset fanout probe.
# No automatic full electrical ECO, no reset edits, no resizing/library changes.
# Runner binds this script, ::eco_electrical_plan_file/SHA and exact source map.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]

proc electrical_leaf_loads {name} {
  current_instance
  set driver [eco_pin $name]
  eco_require [expr {[get_attribute $driver direction] eq {out}}] {electrical root must be exact driver output}
  set net [get_nets -of_objects $driver]
  eco_require [expr {[sizeof_collection $net] == 1}] {electrical driver needs one local segment}
  return [get_pins -leaf -of_objects $net -filter {direction == in}]
}
proc electrical_number {pin attribute} {
  set value [get_attribute $pin $attribute]
  eco_require [expr {[string is double -strict $value] && $value == $value && abs($value)<1e8}] "missing/nonfinite native electrical metric $attribute"
  return $value
}
proc electrical_metric {phase row} {
  current_instance
  set driver [eco_pin [dict get $row driver]]
  set owner [eco_parent [get_object_name $driver]]
  eco_require [expr {[get_attribute [get_cells $owner] ref_name] eq [dict get $row reference]}] {electrical root native reference differs}
  set count [sizeof_collection [electrical_leaf_loads [dict get $row driver]]]
  set cap [electrical_number $driver drc_actual_max_capacitance]
  set slew [electrical_number $driver actual_transition_max]
  puts $::electrical_metric_log "$phase\t[dict get $row net_id]\t[dict get $row driver]\t$count\t$cap\t$slew\t[dict get $row asynchronous_reset_net]"
  flush $::electrical_metric_log
  return [list $count $cap $slew]
}
proc electrical_probe_insert {group} {
  set owner [dict get $group owner];set names [dict get $group loads]
  eco_require [expr {[llength $names]==4 && [llength [lsort -unique $names]]==4 && [dict get $group net_id] eq {e000}}] {only explicit current-map4-load result-control probe permitted}
  set oldname {};set relative {}
  foreach name $names {
    set pin [eco_pin $name]
    eco_require [expr {[get_attribute $pin direction] eq {in} && [eco_parent [eco_parent $name]] eq $owner && [file tail $name] eq {A2}}] {probe must select four direct AO32 A2 control loads}
    eco_require [expr {[get_attribute [get_cells [eco_parent $name]] ref_name] eq {AO32V1_12TR40}}] {probe original leaf reference differs}
    set net [get_nets -of_objects $pin]
    eco_require [expr {[sizeof_collection $net]==1}] {probe target has multiple local nets}
    set netname [get_object_name $net]
    eco_require [expr {[eco_parent $netname] eq $owner && [file tail $netname] in [dict get $group allowed_local_net_aliases]}] {electrical probe escaped mapped local segment aliases}
    if {$oldname eq {}} {set oldname $netname} else {eco_require [expr {$oldname eq $netname}] {electrical probe targets do not share ONE native local segment}}
    lappend relative [string range $name [expr {[string length $owner]+($owner ne {})}] end]
  }
  current_instance
  set oldnet [get_nets $oldname]
  set oldmembers [lsort [get_object_name [get_pins -of_objects $oldnet]]]
  eco_connections electrical-probe-before $oldnet
  eco_context $owner
  set pins [get_pins -quiet $relative]
  eco_require [expr {[lsort [get_object_name $pins]] eq [lsort $names]}] {scoped electrical probe targets differ}
  set cname [dict get $group new_cell_name];set nname ${cname}_NET
  eco_require [expr {$cname eq {XU_ECO_electrical_probe4} && [sizeof_collection [get_cells -quiet $cname]]==0 && [sizeof_collection [get_nets -quiet $nname]]==0}] {electrical probe names already used}
  set cell [eco_buffer]
  eco_require [expr {$::eco_max_buffers>=1 && [get_attribute $cell area] <= $::eco_max_added_area}] {electrical probe buffer/area budget insufficient}
  set new [insert_buffer -new_cell_names $cname -new_net_names $nname $pins $cell]
  eco_require [expr {[sizeof_collection $new]==1}] {native electrical group did not insert exactly ONE buffer}
  set fullname [get_object_name $new]
  eco_require [expr {[eco_parent $fullname] eq $owner && [get_attribute $new ref_name] eq $::eco_buffer_reference}] {electrical probe inserted unexpected reference/owner}
  current_instance
  set newnet [get_nets -of_objects [eco_pin ${fullname}/Z]]
  eco_require [expr {[sizeof_collection $newnet]==1 && [get_object_name $newnet] ne $oldname}] {electrical probe output not on distinct net}
  eco_require [expr {[get_object_name [get_nets -of_objects [eco_pin ${fullname}/I]]] eq $oldname}] {probe buffer input not on original local segment}
  set expectedold {}
  foreach name $oldmembers {if {$name ni $names} {lappend expectedold $name}}
  lappend expectedold ${fullname}/I
  eco_require [expr {[lsort [get_object_name [get_pins -of_objects [get_nets $oldname]]]] eq [lsort $expectedold]}] {unselected old electrical net member changed}
  eco_require [expr {[lsort [get_object_name [get_pins -of_objects $newnet]]] eq [lsort [concat $names [list ${fullname}/Z]]]}] {electrical probe new net membership differs}
  set ::eco_inserted 1;set ::eco_added_area [get_attribute $new area]
  puts $::eco_insert_log "$fullname\t$::eco_buffer_reference\t[join $names ,]\t$oldname\t$::eco_added_area"
  eco_connections electrical-probe-after-old [get_nets $oldname]
  eco_connections electrical-probe-after-new $newnet
}

set failed [catch {
  eco_config
  eco_require [expr {[info exists ::eco_electrical_action] && $::eco_electrical_action in {topology probe}}] {runner must explicitly select topology or single nonreset probe}
  eco_require [expr {[info exists ::eco_electrical_plan_file] && [info exists ::eco_electrical_plan_sha] && [info exists ::eco_mapped_sha]}] {missing explicit native map/plan bindings}
  eco_sha $::eco_mapped $::eco_mapped_sha
  eco_sha $::eco_electrical_plan_file $::eco_electrical_plan_sha
  source $::eco_electrical_plan_file
  eco_require [expr {$::eco_electrical_schema eq {ingress1064-hierarchy-local-electrical-static-plan-v1} && $::eco_electrical_origin_map_sha eq {882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e}}] {electrical plan is not original1064 fixed-map origin}
  eco_load_pt $::eco_mapped
  foreach command {insert_buffer get_pins get_nets report_net} {eco_capture native-man-${command}.rpt [list man $command]}
  eco_native_proof
  set clocks [eco_clocks];set before [eco_snapshot before]
  eco_begin_logs
  set ::electrical_metric_log [eco_open electrical-metrics.tsv]
  puts $::electrical_metric_log "phase\tnet_id\tdriver\tflattened_sink_count\tnative_max_capacitance\tnative_max_transition_ns\tasynchronous_reset_net"
  update_timing -full
  set probe_row {}
  foreach row $::eco_electrical_roots {
    set name [dict get $row driver];set id [dict get $row net_id]
    set metrics [electrical_metric before $row]
    eco_require [expr {[lindex $metrics 0]==[dict get $row expected_sink_count]}] "native electrical fanout differs from mapped catalogue: $name"
    set net [get_nets -of_objects [eco_pin $name]]
    eco_connections electrical-${id}-local $net
    eco_capture electrical-${id}-net.rpt [list report_net -connections $net]
    if {$id eq {e000}} {set probe_row $row;set probe_before $metrics}
  }
  eco_reports before
  if {$::eco_electrical_action eq {probe}} {
    eco_require [expr {$probe_row ne {} && ![dict get $probe_row asynchronous_reset_net]}] {probe must be explicit nonreset control net}
    electrical_probe_insert $::eco_electrical_probe_group
    update_timing -full
    set after [electrical_metric after $probe_row]
    eco_require [expr {[lindex $after 0]==[lindex $probe_before 0]-3 && [lindex $after 1]<[lindex $probe_before 1] && [lindex $after 2]<=[lindex $probe_before 2]}] {native electrical root fanout/capacitance/slew did not improve by the expected group cut}
    eco_delta $before [eco_snapshot after]
    eco_reports after
    eco_export changes
  }
  eco_assert_clocks $clocks
  eco_close_logs;close $::electrical_metric_log
  eco_finish ELECTRICAL_TOPOLOGY_OR_SINGLE_PROBE_COLLECTED_NOT_CLOSURE.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
