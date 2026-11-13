# Read-only new SYSBUS32 PrimeTime collection using old B native-proven commands.
# Original mapped netlist/library/SDC untouched. No compile or ECO.
# Only a new output-local SDC copy adds PT-required -add to generated-clock calls.
# Root runs this in a NEW output directory via the authorized server runner.
# A completed collection is not timing closure or formal qualification.
set xu_failures {}
set xu_required_failures {}
set xu_out [pwd]
set xu_reports [file join $xu_out reports]
file mkdir $xu_reports
proc xu_sha256 {path expected} {
  if {![file isfile $path]} {error "missing pinned input: $path"}
  set got [lindex [exec sha256sum -- $path] 0]
  if {$got ne $expected} {error "input SHA256 drift: $path expected=$expected got=$got"}
  return $got
}
proc xu_capture {name command required} {
  global xu_reports xu_failures xu_required_failures
  set path [file join $xu_reports $name]
  if {[catch {redirect -file $path $command} reason options]} {
    set f [open ${path}.unavailable.txt w]
    puts $f "COMMAND=$command\nREQUIRED=$required\nERROR=$reason"
    if {[dict exists $options -errorinfo]} {puts $f [dict get $options -errorinfo]}
    close $f
    lappend xu_failures [list $name $required $reason]
    if {$required} {lappend xu_required_failures $name}
    return 0
  }
  return 1
}
set xu_error [catch {
  if {![info exists ::env(XU_BASELINE_ROOT)] || ![info exists ::env(XU_MAPPED_SHA256)]} {
    error {runner must provide verified current DC root and mapped.v output SHA256}
  }
  set xu_root [file normalize $::env(XU_BASELINE_ROOT)]
  set_host_options -max_cores 2
  set xu_mapped_sha [xu_sha256 [file join $xu_root mapped.v] $::env(XU_MAPPED_SHA256)]
  set xu_sdc_sha [xu_sha256 [file join $xu_root source contracts reference-full-soc.sdc] c15ede0fc2c65771f87e2d6aee763b4ea0d53934868ca807b4785c36182fce7c]
  # libraries.tcl is a DC-generated two-list file. Read it through an isolated
  # loader: do not ask PT to execute DC-only target_library/set_app_var settings.
  set xu_loader [interp create -safe]
  interp eval $xu_loader {
    set xu_library_lists [dict create]
    proc set_app_var {name value} {
      if {$name ni {target_library link_library}} {error "unexpected library variable: $name"}
      dict set ::xu_library_lists $name $value
    }
  }
  set xu_f [open [file join $xu_root libraries.tcl] r]
  set xu_library_text [read $xu_f]; close $xu_f
  interp eval $xu_loader $xu_library_text
  set xu_lists [interp eval $xu_loader {set xu_library_lists}]
  interp delete $xu_loader
  set xu_link [dict get $xu_lists link_library]
  set xu_targets [dict get $xu_lists target_library]
  if {[llength $xu_link] != 3 || [lindex $xu_link 0] ne "*" || [llength $xu_targets] != 1 || [lindex $xu_link 1] ne [lindex $xu_targets 0]} {
    error {original library lists have unexpected shape}
  }
  set xu_std [lindex $xu_link 1]
  set xu_ram [lindex $xu_link 2]
  xu_sha256 $xu_std f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723
  xu_sha256 $xu_ram c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f
  set_app_var link_path $xu_link
  read_verilog [file join $xu_root mapped.v]
  current_design xu_soc_sysbus32_ppa_top
  if {![link_design xu_soc_sysbus32_ppa_top]} {error {baseline PT link failed}}
  if {[sizeof_collection [current_design]] != 1} {error {missing linked baseline design}}
  source [file join $xu_root source ppa hierarchy_contract.tcl]
  sysbus32_check_hierarchy
  set xu_ram_cells [get_cells -quiet -hierarchical -filter {ref_name == RAMSP1024X16}]
  if {[sizeof_collection $xu_ram_cells] != $sysbus32_expected_total_macros} {error {PT SRAM count does not match sealed profile}}
  # Original constraints, same default envelope, no added timing exceptions.
  set XU_CLOCK_MODE envelope
  set XU_PLL_DIV 0
  set XU_PROPAGATE_CLOCKS 0
  # Native R1 failed CMD-003: PT requires -add when -master_clock is given.
  # Fresh replay has no prior explicitly created clocks. This is the first
  # generated-clock declaration; -add changes no source/master/period/edge.
  # Original SDC stays byte-identical. Only this output-local copy is sourced.
  if {[sizeof_collection [get_clocks -quiet *]] != 0} {error {unexpected clocks before original-SDC replay}}
  set xu_f [open [file join $xu_root source contracts reference-full-soc.sdc] rb]
  set xu_sdc_original [read $xu_f]; close $xu_f
  set xu_sdc_from {create_generated_clock -name }
  set xu_sdc_to {create_generated_clock -add -name }
  if {[regexp -all {create_generated_clock -name } $xu_sdc_original] != 3} {error {unexpected original generated-clock declaration count}}
  set xu_sdc_compat [string map [list $xu_sdc_from $xu_sdc_to] $xu_sdc_original]
  set xu_sdc_compat_path [file join $xu_out constraints-pt-add.sdc]
  set xu_f [open $xu_sdc_compat_path {WRONLY CREAT EXCL}]
  fconfigure $xu_f -translation binary
  puts -nonewline $xu_f $xu_sdc_compat
  close $xu_f
  set xu_sdc_compat_sha [xu_sha256 $xu_sdc_compat_path 404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98]
  set xu_f [open [file join $xu_out sdc-portability-receipt.txt] {WRONLY CREAT EXCL}]
  puts $xu_f "ORIGINAL_SDC_SHA256=$xu_sdc_sha\nCOMPAT_SDC_SHA256=$xu_sdc_compat_sha"
  puts $xu_f {TRANSFORM=exact three occurrences: create_generated_clock -name -> create_generated_clock -add -name}
  puts $xu_f {NATIVE_R1_ERROR=Cannot specify -master_clock without -add (CMD-003)}
  puts $xu_f {FIRST_DECLARATION=No clocks exist before sourcing the new SDC copy; this is not a replacement/relaxation of an existing generated clock.}
  puts $xu_f {NO_PERIOD_EDGE_SOURCE_MASTER_IO_UNCERTAINTY_OR_PATH_EXCEPTION_CHANGE=1}
  puts $xu_f {STATUS=COMMAND_PORTABILITY_ONLY_NOT_TIMING_FIX}
  close $xu_f
  source $xu_sdc_compat_path
  if {[sizeof_collection [get_clocks -quiet *]] != 4} {error {unexpected clock count after original-SDC compatibility replay}}
  foreach xu_pair {{xu_hfextclk 6.666666667} {xu_lfextclk 30517.578125} {xu_jtag_tck 100.0}} {
    set xu_clock [get_clocks -quiet [lindex $xu_pair 0]]
    if {[sizeof_collection $xu_clock] != 1} {error "missing primary clock: $xu_pair"}
    if {abs([get_attribute $xu_clock period]-[lindex $xu_pair 1])>0.000001} {error "wrong primary period: $xu_pair"}
  }
  if {[sizeof_collection [get_clocks -quiet xu_plldiv_envelope]] != 1} {error {missing baseline divider envelope}}
  update_timing -full
  xu_capture units.rpt {report_units} 1
  xu_capture clocks.rpt {report_clock -attributes} 1
  xu_capture check_timing.rpt {check_timing -verbose} 1
  xu_capture coverage.rpt {report_analysis_coverage -status_details {untested violated}} 1
  xu_capture setup.rpt {report_timing -slack_lesser_than 1000000000 -delay_type max -max_paths 50 -nworst 1 -path_type full_clock_expanded -significant_digits 8 -nets -input_pins -transition_time -capacitance} 1
  xu_capture hold.rpt {report_timing -slack_lesser_than 1000000000 -delay_type min -max_paths 50 -nworst 1 -path_type full_clock_expanded -significant_digits 8 -nets -input_pins -transition_time -capacitance} 1
  xu_capture all_violators.rpt {report_constraint -all_violators -verbose} 1
  xu_capture recovery.rpt {report_constraint -recovery -all_violators -verbose} 1
  xu_capture removal.rpt {report_constraint -removal -all_violators -verbose} 1
  xu_capture clock_gating_setup.rpt {report_constraint -clock_gating_setup -all_violators -verbose} 1
  xu_capture clock_gating_hold.rpt {report_constraint -clock_gating_hold -all_violators -verbose} 1
  xu_capture min_pulse_width.rpt {report_constraint -min_pulse_width -all_violators -verbose} 1
  xu_capture exceptions.rpt {report_exceptions} 1
  xu_capture case_analysis.rpt {report_case_analysis -all} 1
  xu_capture disable_timing.rpt {report_disable_timing} 1
  # Extra reports are observational only; tool support is recorded explicitly.
  xu_capture parasitic_annotation.rpt {report_annotated_parasitics -check} 0
  # Native R2 proved this optional command absent. Do not invoke it again.
  set xu_f [open [file join $xu_reports operating_conditions.rpt.unavailable.txt] w]
  puts $xu_f {COMMAND=report_operating_conditions}
  puts $xu_f {STATUS=KNOWN_UNAVAILABLE_IN_PT_T_2022_03_SP5_1_FROM_NATIVE_R2}
  puts $xu_f {Required PVT identity remains pinned by the exact two DB SHA256s; path reports show the active library/operating condition.}
  close $xu_f
  xu_capture designs.rpt {report_design} 0
  xu_capture async_pin_max.rpt {report_timing -slack_lesser_than 1000000000 -delay_type max -to [all_registers -async_pins] -max_paths 50 -path_type full_clock_expanded -significant_digits 8} 1
  xu_capture async_pin_min.rpt {report_timing -slack_lesser_than 1000000000 -delay_type min -to [all_registers -async_pins] -max_paths 50 -path_type full_clock_expanded -significant_digits 8} 1
  # Every current clock group is independently visible, including JTAG/LF.
  foreach_in_collection xu_group [get_path_groups *] {
    set xu_group_name [get_object_name $xu_group]
    set xu_safe_name [string map {/ _ " " _ \[ _ \] _} $xu_group_name]
    xu_capture group-${xu_safe_name}-setup.rpt [list report_timing -slack_lesser_than 1000000000 -group $xu_group_name -delay_type max -max_paths 20 -nworst 1 -path_type full_clock_expanded -significant_digits 8] 1
    xu_capture group-${xu_safe_name}-hold.rpt [list report_timing -slack_lesser_than 1000000000 -group $xu_group_name -delay_type min -max_paths 20 -nworst 1 -path_type full_clock_expanded -significant_digits 8] 1
  }
  # Deliberately omit broad -from/-to register Cartesian scope queries.
  # DC proved this extra collector unbounded; global/group/coverage reports
  # remain and expose all native violations. No timing path is cut or changed.
  foreach xu_name {dma-register-setup.rpt dma-register-hold.rpt} {
    set xu_f [open [file join $xu_reports ${xu_name}.unavailable.txt] w]
    puts $xu_f {STATUS=OMITTED_BROAD_SCOPE_QUERY; global/group timing and full analysis coverage retained. Accelerator-specific path attribution requires bounded follow-up; this is not a timing waiver.}
    close $xu_f
  }
  # Native PT R3 already established the pin clocks attribute contract.
  # Recheck the native attribute inventory, omitting repeated manual dumps.
  if {![xu_capture native-pin-attributes.rpt {list_attributes -application -class pin} 1]} {
    error {native PT pin-attribute inventory unavailable}
  }
  set xu_f [open [file join $xu_reports native-pin-attributes.rpt] r]
  set xu_pin_attributes [read $xu_f]; close $xu_f
  if {![regexp {(^|\n)[ \t]*clocks[ \t]+pin[ \t]+collection([ \t]|\r?\n)} $xu_pin_attributes]} {
    error {native PT inventory does not prove pin clocks is a collection attribute}
  }
  # PT R2 rejected get_clocks -of_objects. Query only the attribute proven above;
  # no zero/default fallback can turn a failed association query into coverage.
  set xu_pins [all_registers -clock_pins]
  set xu_no_clock 0
  set xu_multi_clock 0
  set xu_f [open [file join $xu_reports clock_endpoints.tsv] w]
  puts $xu_f "kind\tpin\tclock_count\tclocks"
  foreach_in_collection xu_pin $xu_pins {
    set xu_clocks [get_attribute $xu_pin clocks]
    set xu_n [sizeof_collection $xu_clocks]
    if {$xu_n == 0} {incr xu_no_clock}
    if {$xu_n > 1} {incr xu_multi_clock}
    puts $xu_f "register\t[get_object_name $xu_pin]\t$xu_n\t[get_object_name $xu_clocks]"
  }
  set xu_sram_no_clock 0
  foreach_in_collection xu_cell $xu_ram_cells {
    set xu_pin [get_pins -quiet [format {%s/CLK} [get_object_name $xu_cell]]]
    if {[sizeof_collection $xu_pin] != 1} {error "missing SRAM CLK pin: [get_object_name $xu_cell]"}
    set xu_clocks [get_attribute $xu_pin clocks]
    set xu_n [sizeof_collection $xu_clocks]
    if {$xu_n == 0} {incr xu_sram_no_clock}
    puts $xu_f "SRAM\t[get_object_name $xu_pin]\t$xu_n\t[get_object_name $xu_clocks]"
  }
  close $xu_f
  set xu_f [open [file join $xu_out pt-status.txt] w]
  puts $xu_f "MODE=READ_PINNED_MAPPED_VERILOG_ORIGINAL_SDC_WITH_EXPLICIT_PT_ADD_PORTABILITY"
  puts $xu_f "MAPPED_V_SHA256=$xu_mapped_sha\nORIGINAL_CONSTRAINTS_SHA256=$xu_sdc_sha\nPT_ADD_CONSTRAINTS_SHA256=$xu_sdc_compat_sha"
  puts $xu_f "STD_LIBRARY=$xu_std\nSRAM_LIBRARY=$xu_ram"
  puts $xu_f "CLOCK_MODE=$XU_CLOCK_MODE\nPLL_DIV=$XU_PLL_DIV\nPROPAGATED_CLOCKS=$XU_PROPAGATE_CLOCKS"
  puts $xu_f {CLOCK_ASSOCIATION_METHOD=native-listed pin clocks collection attribute}
  puts $xu_f "REGISTER_CLOCK_PIN_COUNT=[sizeof_collection $xu_pins]\nREGISTER_NO_CLOCK_COUNT=$xu_no_clock\nREGISTER_MULTI_CLOCK_COUNT=$xu_multi_clock"
  puts $xu_f "SRAM_COUNT=[sizeof_collection $xu_ram_cells]\nSRAM_NO_CLOCK_COUNT=$xu_sram_no_clock"
  puts $xu_f "REPORT_COMMAND_FAILURES=$xu_failures\nREQUIRED_REPORT_FAILURES=$xu_required_failures"
  puts $xu_f "STATUS=SYSBUS32_REPORTS_COLLECTED_REVIEW_REQUIRED_NOT_QUALIFIED"
  puts $xu_f {NO_PARASITIC_FILE_OR_CTS_PROVIDED=1}
  puts $xu_f {THIS_SCRIPT_DOES_NOT_PARSE_TIMING_SLACK_OR_CERTIFY_CLOSURE=1}
  close $xu_f
  if {[llength $xu_required_failures] != 0} {error "required baseline report commands failed: $xu_required_failures"}
  set xu_f [open [file join $xu_out SYSBUS32_PT_COLLECTION_COMPLETE_NOT_QUALIFIED.txt] w]
  puts $xu_f {Native baseline PrimeTime report collection completed; timing closure, coverage completeness and qualification require independent report review.}
  close $xu_f
} xu_reason xu_options]
if {$xu_error} {
  set xu_f [open [file join $xu_out SYSBUS32_PT_COLLECTION_FAILED.txt] w]
  puts $xu_f $xu_reason
  if {[dict exists $xu_options -errorinfo]} {puts $xu_f [dict get $xu_options -errorinfo]}
  puts $xu_f "REPORT_COMMAND_FAILURES=$xu_failures\nREQUIRED_REPORT_FAILURES=$xu_required_failures"
  close $xu_f
  puts stderr "SYSBUS32_PT_COLLECTION_FAILED: $xu_reason"
  exit 1
}
puts {SYSBUS32_PT_COLLECTION_COMPLETE_NOT_QUALIFIED}
exit 0
