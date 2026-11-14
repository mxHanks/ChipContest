# Read-only, empty-design discovery for the exact native PT clock-limit issue.
# No RTL, library, clock, IO constraint, exception or analysis setting is changed.
set_host_options -max_cores 2
set status [open discovery-status.tsv {WRONLY CREAT EXCL}]
puts $status "kind\tname\treturncode\tmessage"
foreach pattern {*period* *cycle* *common* *base* *clock* *resolution* *precision* *ratio*} {
  set stem [string map {* {} ? _ / _} $pattern]
  set code [catch {redirect -file variables-${stem}.rpt [list printvar $pattern]} reason]
  puts $status "variables\t$pattern\t$code\t[string map {\n { } \t { }} $reason]"
}
foreach topic {get_app_var report_analysis_coverage get_timing_paths report_timing create_clock write_sdc report_default_significant_digits PTE-052} {
  set code [catch {redirect -file manual-${topic}.rpt [list man $topic]} reason]
  puts $status "manual\t$topic\t$code\t[string map {\n { } \t { }} $reason]"
}
# get_app_var -list/-details are confirmed by this exact version's native man.
set registered [open registered-clock-controls.tsv {WRONLY CREAT EXCL}]
puts $registered "name\tdetails"
foreach name [lsort [get_app_var -list *]] {
  if {[regexp -nocase {expand|normaliz|clock|common.*period|cycle|resolution|precision} $name]} {
    set code [catch {get_app_var -details $name} details]
    puts $registered "$name\t$code\t[string map {\n { } \t { }} $details]"
  }
}
close $registered
foreach topic {timing_max_normalization_cycles timing_path_arrival_required_attribute_include_clock_edge} {
  set code [catch {redirect -file manual-${topic}.rpt [list man $topic]} reason]
  puts $status "manual\t$topic\t$code\t[string map {\n { } \t { }} $reason]"
}
close $status
redirect -file host-usage.rpt {report_host_usage -verbose}
set done [open UNKNOWN4_DISCOVERY_COMPLETE.txt {WRONLY CREAT EXCL}]
puts $done {READ_ONLY_NATIVE_API_DISCOVERY_NOT_TIMING_CLOSURE}
close $done
exit 0
