if {[catch {
file mkdir private-manuals
set f [open docs-index.tsv w]
puts $f "command\tcatch_rc\tmessage"
set rc [catch {redirect -file {private-manuals/man-get_timing_arcs.txt} {man get_timing_arcs}} msg]
puts $f [join [list {get_timing_arcs} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-get_lib_timing_arcs.txt} {man get_lib_timing_arcs}} msg]
puts $f [join [list {get_lib_timing_arcs} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-report_analysis_coverage.txt} {man report_analysis_coverage}} msg]
puts $f [join [list {report_analysis_coverage} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-report_timing.txt} {man report_timing}} msg]
puts $f [join [list {report_timing} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-get_timing_paths.txt} {man get_timing_paths}} msg]
puts $f [join [list {get_timing_paths} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-report_disable_timing.txt} {man report_disable_timing}} msg]
puts $f [join [list {report_disable_timing} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-all_fanin.txt} {man all_fanin}} msg]
puts $f [join [list {all_fanin} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-report_case_analysis.txt} {man report_case_analysis}} msg]
puts $f [join [list {report_case_analysis} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-report_clock.txt} {man report_clock}} msg]
puts $f [join [list {report_clock} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-get_app_var.txt} {man get_app_var}} msg]
puts $f [join [list {get_app_var} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-timing_report_unconstrained_paths.txt} {man timing_report_unconstrained_paths}} msg]
puts $f [join [list {timing_report_unconstrained_paths} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-PTE-052.txt} {man PTE-052}} msg]
puts $f [join [list {PTE-052} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-get_attribute.txt} {man get_attribute}} msg]
puts $f [join [list {get_attribute} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-get_object_name.txt} {man get_object_name}} msg]
puts $f [join [list {get_object_name} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-get_pins.txt} {man get_pins}} msg]
puts $f [join [list {get_pins} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-get_cells.txt} {man get_cells}} msg]
puts $f [join [list {get_cells} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-get_nets.txt} {man get_nets}} msg]
puts $f [join [list {get_nets} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-all_connected.txt} {man all_connected}} msg]
puts $f [join [list {all_connected} $rc $msg] "\t"]
set rc [catch {redirect -file {private-manuals/man-sizeof_collection.txt} {man sizeof_collection}} msg]
puts $f [join [list {sizeof_collection} $rc $msg] "\t"]
close $f
redirect -file {attributes-pin.txt} {list_attributes -application -class pin}
redirect -file {attributes-port.txt} {list_attributes -application -class port}
redirect -file {attributes-cell.txt} {list_attributes -application -class cell}
redirect -file {attributes-clock.txt} {list_attributes -application -class clock}
redirect -file {attributes-timing_arc.txt} {list_attributes -application -class timing_arc}
redirect -file {attributes-lib_timing_arc.txt} {list_attributes -application -class lib_timing_arc}

} xu_error xu_options]} {
puts stderr "XU_FATAL: $xu_error"
if {[dict exists $xu_options -errorinfo]} {puts stderr [dict get $xu_options -errorinfo]}
exit 1
}
puts {XU_COVERAGE132_INSTALLED_DOCS_DONE_NOT_QUALIFIED}
exit 0
