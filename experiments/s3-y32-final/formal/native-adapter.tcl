# Native adapter bound to three actual R-2020.09-SP5 documentation/attribute probes.
# API signatures are reviewed; runtime object/list/report shapes are validated
# and fail closed. This file alone is not a native equivalence result.
set ::final_fm_native_adapter_pending 0
proc final_fm_hex {value} {
 binary scan [encoding convertto utf-8 $value] H* result
 return $result
}
proc final_fm_row {kind args} {
 if {![info exists ::final_fm_stream]} {error {Native collector stream was not initialized}}
 set row [list $kind]
 foreach field $args {lappend row [final_fm_hex $field]}
 puts $::final_fm_stream [join $row "\t"]
 flush $::final_fm_stream
}
proc final_fm_validate_report {path} {
 if {![file isfile $path] || [file size $path]==0} {error "Missing/empty native report $path"}
 set h [open $path r];set text [read $h];close $h
 if {[regexp -line {^(Error:|Fatal:)} $text]} {error "Native report printed an error despite Tcl return status: $path"}
 return $text
}
proc final_fm_report {role phase command path {append 0}} {
 set ::final_fm_redirected_command $command
 if {$append} {
  redirect -append -file $path {set ::final_fm_last_report_result [uplevel #0 $::final_fm_redirected_command]}
 } else {
  redirect -file $path {set ::final_fm_last_report_result [uplevel #0 $::final_fm_redirected_command]}
 }
 final_fm_validate_report $path
 if {$role ne "extra"} {final_fm_row REPORT $role $phase $command}
 return $::final_fm_last_report_result
}
proc final_fm_configure_resources {maximum_cores report_dir} {
 if {$maximum_cores!=2} {error {Only the authorized max2core configuration is allowed}}
 if {[file exists coverage-native.tsv]} {error {Refuse collector overwrite}}
 set ::final_fm_stream [open coverage-native.tsv w]
 final_fm_row META schema final374-fm-native-tsv-v1
 set_host_options -max_cores 2
 final_fm_report resources setup {report_host_options} [file join $report_dir resources.rpt]
 set text [final_fm_validate_report [file join $report_dir resources.rpt]]
 if {![regexp -line {^[ \t]*max_cores:[ \t]*2[ \t]*$} $text]} {error {Native resource report did not confirm max_cores:2}}
 final_fm_row RESOURCE max_cores 2
}
proc final_fm_assumption_snapshot {phase report_dir} {
 set path [file join $report_dir assumptions.rpt]
 set h [open $path a]
 puts $h "NATIVE_TCL_VARIABLE_INVENTORY phase=$phase"
 set variables {synopsys_auto_setup hdlin_unresolved_modules verification_timeout_limit verification_set_undriven_signals verification_verify_directly_undriven_output hdlin_ignore_parallel_case hdlin_ignore_full_case hdlin_error_on_mismatch_message hdlin_ignore_embedded_configuration signature_analysis_allow_subset_match svf_ignore_unqualified_fsm_information upf_assume_related_supply_default_primary upf_use_additional_db_attributes hdlin_enable_verilog_configurations_array_n_block svf_checkpoint_auto_setup_commands verification_clock_gate_hold_mode hdlin_dyn_array_bnd_check hdlin_optimize_enum_types hdlin_infer_enumerated_types}
 foreach name $variables {
  if {[info exists ::$name]} {set value [set ::$name]} else {set value {<NOT_INSTANTIATED>}}
  puts $h [list $name $value]
  final_fm_row ASSUMPTION $phase $name $value
 }
 close $h
 final_fm_row REPORT assumptions $phase TCL_VARIABLE_INVENTORY
}
proc final_fm_configure_assumptions {report_dir} {
 # Documented in the current native synopsys_auto_setup/hdlin/timeout manuals.
 # Every resulting assumption/dont_verify/constant still requires review.
 set ::synopsys_auto_setup true
 set ::hdlin_unresolved_modules error
 set ::verification_timeout_limit 2:0:0
 final_fm_assumption_snapshot setup $report_dir
}
proc final_fm_pair_list {category command role report_dir} {
 set data [final_fm_report $role verified $command [file join $report_dir ${role}.rpt] 1]
 final_fm_row QUERY $category $command $data
 foreach pair $data {
  if {[llength $pair]!=2} {error "Native pair-list shape differs for $category: $pair"}
  set ref [lindex $pair 0];set impl [lindex $pair 1]
  if {![string match {r:/*} $ref] || ![string match {i:/*} $impl]} {error "Native container/name format differs for $category: $pair"}
  final_fm_row PAIR $category $ref $impl
 }
 final_fm_row COUNT $category [llength $data]
 return $data
}
proc final_fm_single_list {category container command role report_dir} {
 set data [final_fm_report $role verified $command [file join $report_dir ${role}.rpt] 1]
 final_fm_row QUERY $category $command $data
 foreach object $data {
  if {![string match ${container}:/* $object]} {error "Native object/name format differs for $category: $object"}
  final_fm_row SINGLE $category $container $object
 }
 final_fm_row COUNT $category [llength $data]
 return $data
}
proc final_fm_inventory {container report_dir} {
 if {$container ni {r i}} {error {Unknown native container}}
 current_design ${container}:/WORK/xu_soc_sysbus32_ppa_top
 set cells [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}]
 set names {}
 foreach_in_collection cell $cells {
  set name [get_attribute $cell full_name]
  set reference [get_attribute $cell ref_name]
  if {![string match ${container}:/WORK/xu_soc_sysbus32_ppa_top/* $name] || $reference ne "RAMSP1024X16"} {error {Native SRAM object metadata differs}}
  lappend names $name
  final_fm_row MACRO $container $name $reference
  set pins [get_pins -of_objects $cell]
  foreach_in_collection pin $pins {
   set pin_name [get_attribute $pin full_name]
   set direction [get_attribute $pin direction]
   if {$direction ni {in out inout}} {error "Native pin direction unavailable: $pin_name -> $direction"}
   final_fm_row PIN $container $name $pin_name $direction
  }
 }
 set ::final_fm_macro_names($container) $names
 final_fm_row COUNT inventory_${container} [llength $names]
}
proc final_fm_collect {phase report_dir} {
 final_fm_assumption_snapshot $phase $report_dir
 if {$phase eq "linked"} {
  final_fm_inventory r $report_dir
  final_fm_inventory i $report_dir
  final_fm_report black_boxes linked {report_black_boxes} [file join $report_dir black_boxes.rpt]
  final_fm_report extra linked {report_black_boxes -unresolved} [file join $report_dir unresolved-black-boxes.rpt]
  return
 }
 if {$phase eq "matched" || $phase eq "verified"} {
  foreach spec {{unmatched {report_unmatched_points}} {matched {report_matched_points}} {constants {report_constants}} {dont_verify {report_dont_verify_points}} {guidance {report_guidance -summary}} {black_boxes {report_black_boxes}}} {
   set role [lindex $spec 0];set command [lindex $spec 1]
   final_fm_report $role $phase $command [file join $report_dir ${role}.rpt]
  }
  final_fm_report extra $phase {report_black_boxes -unresolved} [file join $report_dir unresolved-black-boxes.rpt]
 }
 if {$phase eq "verified"} {
  foreach spec {{failing {report_failing_points}} {aborted {report_aborted_points}} {unverified {report_unverified_points}} {hdlin_mismatches {report_hdlin_mismatches -verbose}} {unread {report_not_compared_points}}} {
   set role [lindex $spec 0];set command [lindex $spec 1]
   final_fm_report $role verified $command [file join $report_dir ${role}.rpt]
  }
  foreach spec {
   {passing {report_passing_points -list} matched}
   {passing_pgpin {report_passing_points -point_type PGPin -list} matched}
   {matched_pgpin {report_matched_points -point_type PGPin -list} matched}
   {matched {report_matched_points -list} matched}
   {bbox {report_matched_points -point_type bbox -list} black_boxes}
   {bbox_input {report_matched_points -point_type bbox_input -list} black_boxes}
   {bbox_output {report_matched_points -point_type bbox_output -list} black_boxes}
   {const {report_matched_points -status const -list} constants}
   {dont_verify {report_matched_points -status dont_verify -list} dont_verify}
   {unread {report_not_compared_points -status unread -list} unread}
   {not_compared {report_not_compared_points -list} unread}
   {cuts {report_passing_points -point_type cut -list} matched}
   {matched_cuts {report_matched_points -point_type cut -list} matched}
   {failing {report_failing_points -list} failing}
   {aborted {report_aborted_points -list} aborted}
   {unverified {report_unverified_points -list} unverified}
  } {final_fm_pair_list [lindex $spec 0] [lindex $spec 1] [lindex $spec 2] $report_dir}
  foreach container {r i} option {-reference -implementation} {
   final_fm_single_list unmatched_${container} $container [list report_unmatched_points $option -list] unmatched $report_dir
   final_fm_single_list primary_${container} $container [list report_unmatched_points $option -point_type input -list] unmatched $report_dir
   final_fm_single_list bbox_output_${container} $container [list report_unmatched_points $option -point_type bbox_output -list] unmatched $report_dir
   final_fm_single_list match_unread_${container} $container [list report_unmatched_points $option -status unread -list] unread $report_dir
   final_fm_single_list const_${container} $container [list report_unmatched_points $option -status const -list] constants $report_dir
   final_fm_single_list dont_verify_${container} $container [list report_unmatched_points $option -status dont_verify -list] dont_verify $report_dir
  }
  set ids [find_svf_operation -status unaccepted]
  final_fm_row QUERY guidance_unaccepted {find_svf_operation -status unaccepted} $ids
  foreach id $ids {
   if {![string is integer -strict $id]} {error {Native SVF ID list shape differs}}
   final_fm_row SINGLE guidance_unaccepted operation $id
  }
  final_fm_row COUNT guidance_unaccepted [llength $ids]
  if {[llength $ids]>0} {final_fm_report guidance verified [list report_svf_operation $ids] [file join $report_dir guidance.rpt] 1}
  final_fm_row COMPLETE verified
  close $::final_fm_stream
  unset ::final_fm_stream
 }
}
proc final_fm_assert_boundaries {report_dir expected_count expected_cell} {
 if {$expected_count!=374 || $expected_cell ne "RAMSP1024X16"} {error {Unexpected native macro contract}}
 foreach container {r i} {
  if {![info exists ::final_fm_macro_names($container)] || [llength $::final_fm_macro_names($container)]!=$expected_count} {
   error "Native full-top physical macro inventory differs for $container; inspect raw evidence, do not mask as374"
  }
 }
 # Pair and pin details are exported by the final verified queries. Any other
 # opaque/unresolved instance is rejected by the offline raw-report crosscheck,
 # and can never become an accepted equivalence result.
 set text [final_fm_validate_report [file join $report_dir black_boxes.rpt]]
 set actual {}
 foreach line [split $text "\n"] {
  if {[regexp {^[ \t]*([ri]:/WORK/xu_soc_sysbus32_ppa_top/[^ \t]+)[ \t]*$} $line unused name]} {lappend actual $name}
 }
 set expected [concat $::final_fm_macro_names(r) $::final_fm_macro_names(i)]
 if {[lsort -unique $actual] ne [lsort -unique $expected]} {error {Native black-box instance report differs from all actual SRAM instances; no unknown opaque logic is allowed}}
 set unresolved [final_fm_validate_report [file join $report_dir unresolved-black-boxes.rpt]]
 if {[regexp -line {^[ \t]*[ri]:/[^ \t]+[ \t]*$} $unresolved]} {error {Unresolved native black-box objects are present}}
}
