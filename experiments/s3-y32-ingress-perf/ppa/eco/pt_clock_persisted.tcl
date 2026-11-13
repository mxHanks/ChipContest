# Read-only sidecar for the FINAL DC-persisted repaired map. No netlist edits.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
proc clock_persist_number {object attribute} {
  set value [get_attribute $object $attribute]
  eco_require [expr {[string is double -strict $value] && $value==$value && $value>=0 && abs($value)<1e8}] "missing/nonfinite native clock metric $attribute"
  return $value
}
proc clock_persist_sinks {driver} {
  current_instance
  set pin [eco_pin $driver]
  eco_require [expr {[get_attribute $pin direction] eq {out}}] {clock diagnostic driver is not output}
  set net [get_nets -of_objects $pin]
  eco_require [expr {[sizeof_collection $net]==1}] {clock diagnostic driver lacks one local net}
  return [lsort [get_object_name [get_pins -leaf -of_objects $net -filter {direction == in}]]]
}
set failed [catch {
  eco_config
  eco_require [expr {[info exists ::clock_persist_contract_file] && [info exists ::clock_persist_contract_sha]}] {runner must pin exact final-map clock contract}
  eco_sha $::clock_persist_contract_file $::clock_persist_contract_sha
  source $::clock_persist_contract_file
  eco_sha $::eco_mapped $::clock_persist_source_map_sha
  eco_load_pt $::eco_mapped
  eco_capture native-net-attributes.rpt {list_attributes -application -class net}
  eco_capture native-timing-point-attributes.rpt {list_attributes -application -class timing_point}
  set f [open [file join $::eco_out native-net-attributes.rpt] r];set raw [read $f];close $f
  eco_require [regexp {(^|\n)[ \t]*total_capacitance_max[ \t]+net([ \t]|\r?\n)} $raw] {native net total_capacitance_max unavailable}
  set f [open [file join $::eco_out native-timing-point-attributes.rpt] r];set raw [read $f];close $f
  foreach attribute {object transition} {
    set pattern [format {(^|\n)[ \t]*%s[ \t]+timing_point([ \t]|\r?\n)} $attribute]
    eco_require [regexp $pattern $raw] "native timing_point $attribute unavailable"
  }
  set actual [eco_clocks]
  set f [open $::eco_reference_clocks r]
  eco_require [expr {[string map [list {\t} "\t"] [gets $f]] eq "pin\tclocks"}] {invalid final reload reference clock header}
  set expected [dict create]
  while {[gets $f line]>=0} {
    set fields [split [string map [list {\t} "\t"] $line] \t]
    eco_require [expr {[llength $fields]==2 && ![dict exists $expected [lindex $fields 0]]}] {duplicate/invalid final reload reference clock row}
    dict set expected [lindex $fields 0] [lsort [lindex $fields 1]]
  }
  close $f
  eco_require [expr {[dict size $actual]==[dict size $expected]}] {final persisted clock endpoint count differs from completed reload}
  dict for {pin clocks} $actual {eco_require [expr {[dict exists $expected $pin] && [dict get $expected $pin] eq $clocks}] "final persisted clock association differs: $pin"}
  eco_assert_clocks $actual
  set macros [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}]
  eco_require [expr {[sizeof_collection $macros]==353 && [lsort [get_object_name $macros]] eq [lsort $::clock_persist_macros]}] {original353 SRAM macro instance set changed}
  set f [eco_open persisted-clock-sram-association.tsv];puts $f "macro\tclock_pin\tclocks"
  foreach_in_collection macro $macros {
    set name [get_object_name $macro];set pin ${name}/CLK
    eco_require [expr {[dict exists $actual $pin] && [dict exists $::clock_persist_original_macro_clocks $pin] && [dict get $actual $pin] eq [lsort [dict get $::clock_persist_original_macro_clocks $pin]]}] "original SRAM clock association changed: $pin"
    puts $f "$name\t$pin\t[dict get $actual $pin]"
  }
  close $f
  set planned [dict create]
  set f [eco_open persisted-clock-output-fanout.tsv];puts $f "buffer\treference\tstatic_expected_leaf_sinks\tnative_actual_leaf_sinks"
  set members [eco_open persisted-clock-output-members.tsv];puts $members "buffer\tleaf_sink"
  foreach row $::clock_persist_buffers {
    set name [dict get $row instance]
    eco_require [expr {![dict exists $planned $name]}] {duplicate planned persisted buffer}
    dict set planned $name 1
    set cell [get_cells -quiet $name]
    eco_require [expr {[sizeof_collection $cell]==1 && [get_object_name $cell] eq $name && [get_attribute $cell ref_name] eq [dict get $row reference]}] "persisted clock buffer missing/reference changed: $name"
    set sinks [clock_persist_sinks ${name}/Z]
    eco_require [expr {[llength $sinks]>=1 && [llength $sinks]<=32 && $sinks eq [lsort [dict get $row sinks]]}] "native persisted clock buffer membership differs or outside1..32: $name"
    puts $f "$name\t[dict get $row reference]\t[llength [dict get $row sinks]]\t[llength $sinks]"
    foreach sink $sinks {puts $members "$name\t$sink"}
  }
  close $f;close $members
  set actual_buffers [dict create]
  foreach_in_collection cell [get_cells -hierarchical -filter {is_hierarchical == false}] {
    set name [get_object_name $cell]
    if {[regexp {/XU_ECO_clock_g[0-9][0-9][0-9][0-9]$} $name]} {
      eco_require [dict exists $planned $name] "unexpected clock buffer outside r7 minus explicit cleanup ledger: $name"
      dict set actual_buffers $name 1
    }
  }
  eco_require [expr {[dict size $actual_buffers]==[dict size $planned]}] {clock buffer native inventory differs}
  foreach name $::clock_persist_removed {eco_require [expr {[sizeof_collection [get_cells -quiet $name]]==0}] "explicitly pruned clock buffer still exists: $name"}
  set root [eco_pin $::clock_persist_root]
  set root_sinks [clock_persist_sinks $::clock_persist_root]
  eco_require [expr {$root_sinks eq [lsort $::clock_persist_root_sinks] && [llength $root_sinks]>=1 && [llength $root_sinks]<=32}] {native persisted root leaf membership differs from cleaned-map recomputation}
  set cap [clock_persist_number [get_nets -of_objects $root] total_capacitance_max]
  set output [get_ports -quiet {io_pads_gpioA_o_oval[27]}]
  eco_require [expr {[sizeof_collection $output]==1}] {exact GPIO diagnostic output missing}
  set paths [get_timing_paths -through $root -to $output -delay_type max -max_paths 1 -nworst 1]
  eco_require [expr {[sizeof_collection $paths]==1}] {final root GPIO max path is not tested/unique}
  set found 0
  foreach_in_collection point [get_attribute $paths points] {
    if {[get_object_name [get_attribute $point object]] eq $::clock_persist_root} {incr found;set slew [clock_persist_number $point transition]}
  }
  eco_require [expr {$found==1 && $cap>0 && $slew>0}] {persisted GPIO root point lacks physical load/slew}
  # Same map/library/SDC, allowing only numeric report precision and a reduction
  # from explicit dead-clock-buffer cleanup. No generic pin-DRC substitute.
  eco_require [expr {$cap<=$::clock_persist_ref_cap+0.000001 && $slew<=$::clock_persist_ref_slew+0.000001}] {persisted root capacitance/slew regressed versus actual native r7 tree}
  set f [eco_open persisted-clock-root-metrics.tsv]
  puts $f "driver\tflattened_sink_count\tnative_total_capacitance_max\tGPIO_path_point_transition_ns\tancestor_tree_capacitance\tancestor_tree_transition_ns"
  puts $f "$::clock_persist_root\t[llength $root_sinks]\t$cap\t$slew\t$::clock_persist_ref_cap\t$::clock_persist_ref_slew"
  close $f
  eco_capture persisted-clock-root-GPIO-path.rpt [list report_timing -through $root -to $output -delay_type max -max_paths 1 -nworst 1 -path_type full_clock_expanded -significant_digits 8 -nets -input_pins -transition_time -capacitance]
  eco_reports persisted
  eco_finish PERSISTED_CLOCK_DIAGNOSTICS_COMPLETE_NOT_TIMING_CLOSURE.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
