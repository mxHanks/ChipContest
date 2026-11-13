# Documentation-only probe. Never reads a design/library or starts match/verify.
# Retain complete stdout and the Tcl file SHA, launcher SHA/version and exit code.
set final_fm_requests [list \
  set_host_options report_host_options read_db read_sverilog read_verilog \
  set_top set_svf match verify report_unmatched_points report_failing_points \
  report_black_boxes report_matched_points report_aborted_points \
  report_unverified_points report_dont_verify_points report_constants \
  report_hdlin_mismatches report_guidance get_cells get_designs get_pins \
  get_attribute get_object_name sizeof_collection foreach_in_collection]
set final_fm_variables [list synopsys_auto_setup hdlin_unresolved_modules \
  verification_timeout_limit verification_set_undriven_signals \
  verification_verify_directly_undriven_output hdlin_ignore_parallel_case \
  hdlin_ignore_full_case hdlin_error_on_mismatch_message]
set final_fm_missing 0
foreach final_fm_name $final_fm_requests {
  foreach final_fm_kind {help man} {
    set final_fm_exists [expr {[llength [info commands $final_fm_name]] > 0}]
    puts "XU_FINAL374_FM_API_BEGIN\t$final_fm_kind\t$final_fm_name"
    if {[llength [info commands $final_fm_kind]] == 0} {
      set final_fm_rc 1
      set final_fm_output "Documentation command not supported: $final_fm_kind"
    } else {
      set final_fm_rc [catch {uplevel #0 [list $final_fm_kind $final_fm_name]} final_fm_output]
    }
    if {$final_fm_output ne ""} {puts $final_fm_output}
    puts "XU_FINAL374_FM_API_END\t$final_fm_kind\t$final_fm_name\t$final_fm_exists\t$final_fm_rc"
    if {!$final_fm_exists || $final_fm_rc != 0} {incr final_fm_missing}
  }
}
foreach final_fm_name $final_fm_variables {
  puts "XU_FINAL374_FM_API_BEGIN\tvariable\t$final_fm_name"
  if {[info exists $final_fm_name]} {puts "ACTUAL_VALUE=[set $final_fm_name]"} else {puts {ACTUAL_VALUE=<not instantiated>}}
  set final_fm_rc [catch {uplevel #0 [list man $final_fm_name]} final_fm_output]
  if {$final_fm_output ne ""} {puts $final_fm_output}
  puts "XU_FINAL374_FM_API_END\tvariable\t$final_fm_name\t1\t$final_fm_rc"
  if {$final_fm_rc != 0} {incr final_fm_missing}
}
puts "XU_FINAL374_FM_API_DOCUMENTATION_COLLECTED\tmissing=$final_fm_missing"
# Unsupported candidate APIs are evidence; they never become empty passing reports.
exit 0
