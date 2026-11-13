# Current-map hierarchy-local noninverting clock segmentation probe/tree.
# The runner must bind the source map, exact DC function proof, original SDC,
# and ::eco_clock_plan_file/SHA. A static plan is not native timing evidence.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]

proc eco_clock_root_loads {} {
  current_instance
  set root [eco_pin $::eco_clock_root]
  set net [get_nets -of_objects $root]
  eco_require [expr {[sizeof_collection $net] == 1}] {ambiguous current-map clock root net}
  return [get_pins -leaf -of_objects $net -filter {direction == in}]
}
proc eco_clock_number {object attribute} {
  set value [get_attribute $object $attribute]
  eco_require [expr {[string is double -strict $value] && $value == $value && abs($value) < 1e8 && $value >= 0}] "invalid native clock metric: $attribute=$value"
  return $value
}
proc eco_clock_metrics {phase} {
  current_instance
  set pin [eco_pin $::eco_clock_root]
  set count [sizeof_collection [eco_clock_root_loads]]
  # Ideal clock nets have no electrical-DRC actual-cap attribute in this PT
  # version. They still occur as data on the fully timed GPIO diagnostic path.
  # Query the real path-point API and prove its attributes exist before use.
  # No missing pin attribute is converted to zero or a synthetic load.
  eco_capture ${phase}-native-timing-point-attributes.rpt {list_attributes -application -class timing_point}
  set f [open [file join $::eco_out ${phase}-native-timing-point-attributes.rpt] r]
  set attributes [read $f]; close $f
  foreach attribute {object transition} {
    set pattern [format {(^|\n)[ \t]*%s[ \t]+timing_point([ \t]|\r?\n)} $attribute]
    eco_require [regexp $pattern $attributes] "native timing_point lacks required attribute: $attribute"
  }
  eco_capture ${phase}-native-net-attributes.rpt {list_attributes -application -class net}
  set f [open [file join $::eco_out ${phase}-native-net-attributes.rpt] r]
  set attributes [read $f]; close $f
  eco_require [regexp {(^|\n)[ \t]*total_capacitance_max[ \t]+net([ \t]|\r?\n)} $attributes] {native net lacks total_capacitance_max}
  set cap [eco_clock_number [get_nets -of_objects $pin] total_capacitance_max]
  set output [get_ports -quiet {io_pads_gpioA_o_oval[27]}]
  eco_require [expr {[sizeof_collection $output] == 1}] {exact diagnostic GPIO output missing}
  set paths [get_timing_paths -through $pin -to $output -delay_type max -max_paths 1 -nworst 1]
  eco_require [expr {[sizeof_collection $paths] == 1}] {clock root has no tested diagnostic output path}
  set found 0
  foreach_in_collection point [get_attribute $paths points] {
    if {[get_object_name [get_attribute $point object]] eq $::eco_clock_root} {
      incr found
      set slew [eco_clock_number $point transition]
    }
  }
  eco_require [expr {$found == 1 && $cap > 0 && $slew > 0}] {clock root timing point is absent/ambiguous or has no finite physical load/slew}
  eco_capture ${phase}-clock-root-diagnostic-path.rpt [list report_timing -through $pin -to $output -delay_type max -max_paths 1 -nworst 1 -path_type full_clock_expanded -significant_digits 8 -nets -input_pins -transition_time -capacitance]
  puts $::eco_clock_metric_log "$phase\t$count\t$cap\t$slew\tnative_net_total_capacitance_max_and_GPIO_path_point_transition"
  flush $::eco_clock_metric_log
  return [list $count $cap $slew]
}
proc eco_clock_names {collection} {return [lsort [get_object_name $collection]]}
proc eco_clock_insert_group {group} {
  set id [dict get $group id]; set owner [dict get $group owner]
  set names [dict get $group loads]; set kinds [dict get $group load_kinds]
  eco_require [expr {[llength $names] >= 1 && [llength $names] <= 32 && [llength $names] == [llength [lsort -unique $names]] && [llength $names] == [llength $kinds]}] "invalid bounded current-map group: $id"
  set oldname {}; set pins {}; set expected_names {}
  foreach name $names kind $kinds {
    current_instance
    set pin [eco_pin $name]
    eco_require [expr {[get_attribute $pin direction] eq {in}}] "clock group contains non-load: $name"
    eco_require [expr {[eco_parent [eco_parent $name]] eq $owner}] "clock group crosses immediate owner: $name"
    if {$kind eq {leaf}} {
      set port [file tail $name]
      eco_require [expr {$port in {CK CLK EN A2}}] "unexpected original clock leaf port: $name"
    } elseif {$kind eq {new_buffer_input}} {
      eco_require [expr {[file tail $name] eq {I} && [string match XU_ECO_clock_* [file tail [eco_parent $name]]]}] {aggregation contains an unplanned buffer input}
    } else {eco_require [expr {$kind eq {hier_input}}] "unknown clock plan load kind: $kind"}
    set net [get_nets -of_objects $pin]
    eco_require [expr {[sizeof_collection $net] == 1}] "clock target does not have one local segment: $name"
    set local [get_object_name $net]
    eco_require [expr {[eco_parent $local] eq $owner && [file tail $local] in [dict get $group allowed_local_net_aliases]}] "native local segment not in this owner's mapped aliases: $name $local"
    if {$oldname eq {}} {set oldname $local} else {eco_require [expr {$oldname eq $local}] "same-owner group is NOT one native segment: $id"}
    lappend expected_names $name
  }
  current_instance
  set oldnet [get_nets -quiet $oldname]
  eco_require [expr {[sizeof_collection $oldnet] == 1}] {old local net disappeared before insertion}
  set oldmembers [eco_clock_names [get_pins -of_objects $oldnet]]
  eco_connections clock-${id}-before $oldnet
  eco_require [expr {$::eco_inserted < $::eco_max_buffers}] {bounded clock buffer budget exhausted}
  set buffer [eco_buffer]; set area [get_attribute $buffer area]
  eco_require [expr {$::eco_added_area+$area <= $::eco_max_added_area}] {bounded clock raw-area budget exhausted}
  eco_context $owner
  set relative {}
  foreach name $names {lappend relative [string range $name [expr {[string length $owner]+($owner ne {})}] end]}
  set pins [get_pins -quiet $relative]
  eco_require [expr {[eco_clock_names $pins] eq [lsort $names]}] {scoped group names differ}
  set cname [dict get $group new_cell_name]; set nname ${cname}_NET
  eco_require [expr {[string match XU_ECO_clock_* $cname] && [sizeof_collection [get_cells -quiet $cname]] == 0 && [sizeof_collection [get_nets -quiet $nname]] == 0}] {clock ECO names are invalid/already used}
  set new [insert_buffer -new_cell_names $cname -new_net_names $nname $pins $buffer]
  eco_require [expr {[sizeof_collection $new] == 1}] "native grouping inserted other than ONE buffer: $id"
  set fullname [get_object_name $new]
  eco_require [expr {[eco_parent $fullname] eq $owner && [get_attribute $new ref_name] eq $::eco_buffer_reference}] {inserted clock buffer identity/owner differs}
  current_instance
  set output [eco_pin ${fullname}/Z]; set input [eco_pin ${fullname}/I]
  set newnet [get_nets -of_objects $output]
  eco_require [expr {[sizeof_collection $newnet] == 1 && [get_object_name $newnet] ne $oldname}] {clock buffer has no distinct output net}
  eco_require [expr {[get_object_name [get_nets -of_objects $input]] eq $oldname}] {clock buffer input moved off original local segment}
  set actualnew [eco_clock_names [get_pins -of_objects $newnet]]
  set expectednew [lsort [concat $expected_names [list ${fullname}/Z]]]
  eco_require [expr {$actualnew eq $expectednew}] "new local clock net membership differs: $id"
  set expectedold {}
  foreach name $oldmembers {if {$name ni $expected_names} {lappend expectedold $name}}
  lappend expectedold ${fullname}/I
  set actualold [eco_clock_names [get_pins -of_objects [get_nets $oldname]]]
  eco_require [expr {$actualold eq [lsort $expectedold]}] "unselected old local segment membership changed: $id"
  foreach name $names {eco_require [expr {[get_object_name [get_nets -of_objects [eco_pin $name]]] eq [get_object_name $newnet]}] "clock group load failed to move: $name"}
  set actual [get_attribute [get_cells $fullname] area]
  incr ::eco_inserted; set ::eco_added_area [expr {$::eco_added_area+$actual}]
  puts $::eco_insert_log "$fullname\t$::eco_buffer_reference\t[join $names ,]\t$oldname\t$actual"
  puts $::eco_clock_group_log "$id\t$owner\t$oldname\t$fullname\t[llength $names]\t[dict get $group phase]"
  flush $::eco_insert_log; flush $::eco_clock_group_log
  eco_connections clock-${id}-after-new $newnet
  eco_connections clock-${id}-after-old [get_nets $oldname]
  return $fullname
}

set failed [catch {
  eco_config
  set ::eco_mode clock
  eco_require [expr {[info exists ::eco_clock_stage] && $::eco_clock_stage in {probe tree}}] {explicit API-probe or whole-tree stage required}
  eco_require [expr {[info exists ::eco_clock_plan_file] && [info exists ::eco_clock_plan_sha]}] {runner must bind explicit current-map clock plan}
  eco_sha $::eco_clock_plan_file $::eco_clock_plan_sha
  source $::eco_clock_plan_file
  if {$::eco_clock_stage eq {probe}} {
    eco_require [expr {[llength $::eco_clock_groups] == 1 && [dict get [lindex $::eco_clock_groups 0] id] eq {probe4_core} && $::eco_clock_expected_final_root_fanout == 21589}] {API probe must be exactly the reviewed four-load group}
  } else {
    # Four unused hierarchy clock inputs have no native leaf loads. The r7
    # sealed plan omits those boundaries; every created output must be loaded.
    eco_require [expr {[llength $::eco_clock_groups] == 1560 && $::eco_clock_expected_final_root_fanout == 18}] {whole tree must retain reviewed bounded topology}
  }
  eco_require [expr {$::eco_clock_plan_schema eq {ingress1064-hierarchy-local-clock-tree-static-plan-v1} && $::eco_clock_plan_mapped_sha eq {882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e}}] {wrong current-map clock plan}
  eco_require [info exists ::eco_mapped_sha] {runner must bind exact baseline or completed seed mapped bytes}
  eco_sha $::eco_mapped $::eco_mapped_sha
  eco_load_pt $::eco_mapped
  foreach command {insert_buffer get_pins get_nets report_net} {eco_capture native-man-${command}.rpt [list man $command]}
  eco_native_proof
  set clocks [eco_clocks]; set before [eco_snapshot before]
  eco_begin_logs
  set ::eco_clock_metric_log [eco_open clock-root-metrics.tsv]
  puts $::eco_clock_metric_log "phase\tflattened_sink_count\tnative_max_capacitance\tnative_max_transition_ns\tmeasurement_source"
  set ::eco_clock_group_log [eco_open clock-group-ledger.tsv]
  puts $::eco_clock_group_log "group\towner\told_local_net\tnew_buffer\trequested_load_count\tphase"
  update_timing -full
  set metrics_before [eco_clock_metrics before]
  eco_require [expr {[lindex $metrics_before 0] == 21592}] {not the original1064 native clock load topology}
  eco_reports before
  foreach group $::eco_clock_groups {eco_clock_insert_group $group}
  update_timing -full
  set metrics_after [eco_clock_metrics after]
  eco_require [expr {[lindex $metrics_after 0] == $::eco_clock_expected_final_root_fanout}] {actual clock root fanout differs from structurally predicted cut}
  if {$::eco_clock_stage eq {tree}} {
    eco_require [expr {[lindex $metrics_after 1] < [lindex $metrics_before 1] && [lindex $metrics_after 2] <= [lindex $metrics_before 2]}] {native whole-tree root capacitance/slew did not improve after segmentation}
  } else {
    # A four-load API probe establishes one-owner/one-net grouping. Its measured
    # load/slew can rise when the new input costs more than the four removed
    # loads. It is discarded, never DC-persisted or claimed as an optimization.
    # The whole tree starts afresh from the same seed and must improve both.
    set f [eco_open FOUR_LOAD_API_SCOPE_ONLY_NOT_ELECTRICAL_IMPROVEMENT.txt]
    puts $f "measured_before=$metrics_before measured_after=$metrics_after"
    close $f
  }
  eco_assert_clocks $clocks
  eco_delta $before [eco_snapshot after]
  # Verify the final flattened electrical load at every added clock output;
  # hierarchy port count alone can conceal a still-huge fanout below a boundary.
  set f [eco_open inserted-clock-flat-fanout.tsv]
  puts $f "buffer\tflattened_sink_count"
  foreach group $::eco_clock_groups {
    set owner [dict get $group owner]; set cname [dict get $group new_cell_name]
    set fullname [expr {$owner eq {} ? $cname : "$owner/$cname"}]
    set output [eco_pin ${fullname}/Z]
    set loads [get_pins -leaf -of_objects [get_nets -of_objects $output] -filter {direction == in}]
    set count [sizeof_collection $loads]
    puts $f "$fullname\t$count"
    # The isolated 4-leaf probe has exactly4 output loads. Whole tree32 bound.
    eco_require [expr {$count >= 1 && $count <= 32}] "inserted clock output still has >32 actual leaf loads: $fullname $count"
  }
  close $f
  eco_reports after
  eco_export changes
  eco_close_logs
  close $::eco_clock_metric_log; close $::eco_clock_group_log
  eco_finish CLOCK_SEGMENTATION_COLLECTED_NOT_TIMING_CLOSURE.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
