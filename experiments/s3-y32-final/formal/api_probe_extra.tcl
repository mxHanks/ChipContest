# Supplement to r1 documentation only; no design/library read or verification.
set final_fm_missing 0
foreach final_fm_name {report_passing_points report_not_compared_points current_design current_instance query_objects list_attributes help_attributes find_svf_operation report_svf_operation redirect} {
 foreach final_fm_kind {help man} {
  puts "XU_FINAL374_FM_API_BEGIN\t$final_fm_kind\t$final_fm_name"
  set final_fm_exists [expr {[llength [info commands $final_fm_name]]>0}]
  set final_fm_rc [catch {uplevel #0 [list $final_fm_kind $final_fm_name]} final_fm_output]
  if {$final_fm_output ne ""} {puts $final_fm_output}
  puts "XU_FINAL374_FM_API_END\t$final_fm_kind\t$final_fm_name\t$final_fm_exists\t$final_fm_rc"
  if {!$final_fm_exists || $final_fm_rc != 0} {incr final_fm_missing}
 }
}
foreach final_fm_name {cell_attributes pin_attributes} {
 puts "XU_FINAL374_FM_API_BEGIN\ttopic\t$final_fm_name"
 set final_fm_rc [catch {uplevel #0 [list man $final_fm_name]} final_fm_output]
 if {$final_fm_output ne ""} {puts $final_fm_output}
 puts "XU_FINAL374_FM_API_END\ttopic\t$final_fm_name\t1\t$final_fm_rc"
 if {$final_fm_rc != 0} {incr final_fm_missing}
}
puts "XU_FINAL374_FM_API_DOCUMENTATION_COLLECTED\tmissing=$final_fm_missing"
exit 0
