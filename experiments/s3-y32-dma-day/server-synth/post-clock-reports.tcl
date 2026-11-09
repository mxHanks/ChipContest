# Read-only report recovery from the completed mapped DDC. No compile command.
set failure [catch {
  set root $::env(HOME)/Desktop/xu-dma-synth-20261109-r3/candidate
  source $root/libraries.tcl
  set_host_options -max_cores 2
  read_ddc $root/mapped.ddc
  current_design xu_soc_ppa_top
  if {![link]} {error {post-report link failed}}
  source $root/mapped.sdc
  report_units > units.rpt
  report_clock > clocks.rpt
  check_timing > check_timing.rpt
  check_design > check_design.rpt
  report_constraint -all_violators > violations.rpt
  report_timing -group xu_plldiv_envelope -delay_type max -max_paths 20 -significant_digits 8 > divider-setup.rpt
  report_timing -group xu_plldiv_envelope -delay_type min -max_paths 20 -significant_digits 8 > divider-hold.rpt
  set pins [all_registers -clock_pins]
  set f [open register-clock-pins.txt w]
  foreach_in_collection pin $pins {puts $f [get_object_name $pin]}
  close $f
  set macros [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}]
  if {[sizeof_collection $macros] != 337} {error {wrong post-report SRAM count}}
  set f [open sram-clock-pins.txt w]
  set missing 0
  foreach_in_collection cell $macros {
    set clockpin [get_pins -quiet [format {%s/CLK} [get_object_name $cell]]]
    if {[sizeof_collection $clockpin] != 1} {incr missing}
    puts $f [get_object_name $clockpin]
  }
  close $f
  set f [open scope.txt w]
  puts $f "MODE=READ_MAPPED_DDC_REPORTS_ONLY"
  puts $f "REGISTER_CLOCK_PIN_COUNT=[sizeof_collection $pins]"
  puts $f "SRAM_COUNT=[sizeof_collection $macros]"
  puts $f "SRAM_MISSING_CLK_PIN_COUNT=$missing"
  puts $f "CLOCK_ASSOCIATION_NOT_INFERRED_FROM_PIN_PRESENCE=1"
  close $f
  help check_timing > help-check-timing.txt
  help get_clocks > help-get-clocks.txt
  list_attributes -application -class design > design-attributes.txt
  list_attributes -application -class pin > pin-attributes.txt
  set f [open REPORT_RECOVERY_COMPLETE_NOT_QUALIFIED.txt w]
  puts $f {Native reports collected without remapping. Timing closure and qualification remain unverified.}
  close $f
} reason options]
if {$failure} {
  set f [open REPORT_RECOVERY_FAILED.txt w]; puts $f $reason; close $f
  puts stderr "REPORT_RECOVERY_FAILED: $reason"
  exit 1
}
exit 0
