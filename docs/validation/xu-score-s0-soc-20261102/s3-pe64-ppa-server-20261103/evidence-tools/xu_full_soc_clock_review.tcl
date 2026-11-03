# Run AFTER source xu_full_soc.sdc and, in PT, update_timing. Report collection
# only: this file does not change timing exceptions or announce timing closure.
if {![info exists XU_CLOCK_REVIEW_DIR]} { set XU_CLOCK_REVIEW_DIR reports/xu-clock-review }
file mkdir $XU_CLOCK_REVIEW_DIR
set xu_review_failures {}
proc xu_clock_capture {filename command required} {
    global XU_CLOCK_REVIEW_DIR xu_review_failures
    set target [file join $XU_CLOCK_REVIEW_DIR $filename]
    if {[catch {redirect -file $target $command} result]} {
        set f [open ${target}.unavailable.txt w]
        puts $f "COMMAND: $command\nERROR: $result\nRequired for final signoff: $required"
        close $f
        lappend xu_review_failures [list $filename $required $result]
    }
}
xu_clock_capture check_timing.rpt {check_timing -verbose} yes
xu_clock_capture clocks.rpt {report_clock -attributes} yes
xu_clock_capture setup.rpt {report_timing -delay_type max -max_paths 50 -nworst 1 -path_type full} yes
xu_clock_capture hold.rpt {report_timing -delay_type min -max_paths 50 -nworst 1 -path_type full} yes
xu_clock_capture constraints.rpt {report_constraint -all_violators -verbose} yes
xu_clock_capture exceptions.rpt {report_exceptions -verbose} yes
xu_clock_capture case_analysis.rpt {report_case_analysis -all} yes
# These reports are supported by PT; if unavailable in DC, retain that fact
# explicitly and obtain the reports at the PT stage. Do not discard warnings.
xu_clock_capture analysis_coverage.rpt {report_analysis_coverage -status_details untested} PT
xu_clock_capture recovery.rpt {report_constraint -recovery -verbose} PT
xu_clock_capture removal.rpt {report_constraint -removal -verbose} PT
xu_clock_capture gating_setup.rpt {report_constraint -clock_gating_setup -verbose} PT
xu_clock_capture gating_hold.rpt {report_constraint -clock_gating_hold -verbose} PT
xu_clock_capture pulse_width.rpt {report_constraint -min_pulse_width -verbose} PT
xu_clock_capture async_pin_max.rpt {report_timing -delay_type max -to [all_registers -async_pins] -max_paths 50 -path_type full} PT
xu_clock_capture async_pin_min.rpt {report_timing -delay_type min -to [all_registers -async_pins] -max_paths 50 -path_type full} PT

set xu_f [open [file join $XU_CLOCK_REVIEW_DIR clock_endpoints.tsv] w]
puts $xu_f "kind\tpin\tclocks"
set xu_no_clock 0
set xu_clock_pin_count 0
foreach_in_collection xu_pin [all_registers -clock_pins] {
    incr xu_clock_pin_count
    # PT T-2022.03 get_clocks selects names only; clocks is a pin attribute.
    set xu_pinclks [get_attribute $xu_pin clocks]
    if {[sizeof_collection $xu_pinclks] == 0} { incr xu_no_clock }
    puts $xu_f "register\t[get_object_name $xu_pin]\t[get_object_name $xu_pinclks]"
}
foreach_in_collection xu_cell [get_cells -quiet -hierarchical -filter {ref_name =~ RAMSP*}] {
    set xu_pin [get_pins -quiet [format {%s/CLK} [get_object_name $xu_cell]]]
    if {[sizeof_collection $xu_pin] != 1} {
        puts $xu_f "SRAM_MISSING_CLK\t[get_object_name $xu_cell]\t"
        incr xu_no_clock
    } else {
        set xu_pinclks [get_attribute $xu_pin clocks]
        if {[sizeof_collection $xu_pinclks] == 0} { incr xu_no_clock }
        puts $xu_f "SRAM\t[get_object_name $xu_pin]\t[get_object_name $xu_pinclks]"
    }
}
close $xu_f
set xu_f [open [file join $XU_CLOCK_REVIEW_DIR review_status.txt] w]
puts $xu_f "MODE=$XU_CLOCK_MODE\nPLL_DIV=$XU_PLL_DIV\nREGISTER_CLOCK_PINS=$xu_clock_pin_count\nNO_CLOCK_ENDPOINTS=$xu_no_clock"
puts $xu_f "REPORT_COMMAND_FAILURES=$xu_review_failures"
puts $xu_f "STATUS=REVIEW_REQUIRED; this collector does not parse reports or certify timing"
close $xu_f
if {$xu_no_clock != 0 || [llength $xu_review_failures] != 0} {
    puts "xu clock review: unresolved endpoints/reports; inspect $XU_CLOCK_REVIEW_DIR/review_status.txt"
}
