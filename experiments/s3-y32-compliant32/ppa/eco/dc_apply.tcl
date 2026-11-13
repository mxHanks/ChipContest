# Replay ONLY native-exported physical identity-buffer ECO. No compile/optimize.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
set failed [catch {
  eco_config
  eco_libraries dc
  read_ddc $::eco_ddc
  current_design xu_soc_sysbus32_ppa_top
  eco_require [link] {DC baseline link failed}
  source [file join $::eco_baseline source ppa hierarchy_contract.tcl]
  sysbus32_check_hierarchy
  eco_require [expr {$::sysbus32_expected_total_macros == 353}] {only353 macro selected profile allowed}
  eco_sha $::eco_changes $::eco_changes_sha
  redirect -file apply-changes.rpt [list source $::eco_changes]
  current_instance
  eco_require [link] {post-ECO DC link failed}
  sysbus32_check_hierarchy
  check_design > check-design.rpt
  report_area -hierarchy > area.rpt
  report_reference -hierarchy > references.rpt
  report_units > units.rpt
  set f [eco_open leaf-inventory.tsv]
  puts $f "instance\treference\tarea_library_units\tclassification"
  set standard_area 0.0; set internal_area 0.0; set macro_count 0; set internal_count 0
  set core {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_xu_matrix_dma/u_core/}
  foreach_in_collection cell [get_cells -hierarchical -filter {is_hierarchical == false}] {
    set ref [get_attribute $cell ref_name]; set name [get_object_name $cell]
    if {$ref in {**logic_0** **logic_1**}} {puts $f "$name\t$ref\t0\tnative_constant"; continue}
    eco_require [string is true -strict [get_attribute $cell is_mapped]] "unmapped leaf: $name"
    set area [get_attribute $cell area]
    eco_require [expr {[string is double -strict $area] && $area > 0}] "invalid mapped area: $name"
    if {$ref eq {RAMSP1024X16}} {
      incr macro_count; set classification SRAM
      if {[string first $core $name] == 0} {incr internal_count; set internal_area [expr {$internal_area+$area}]}
    } else {set classification standard_cell; set standard_area [expr {$standard_area+$area}]}
    puts $f "$name\t$ref\t$area\t$classification"
  }
  close $f
  eco_require [expr {$macro_count == 353 && $internal_count == 33}] {post-ECO macro accounting differs}
  set f [eco_open area-upper-bound.tsv]
  puts $f "component\tarea_library_units\tofficial_area_mm2"
  puts $f "ALL_FULL_SOC_STANDARD_CELLS\t$standard_area\tUNVERIFIED_UNIT_CONVERSION"
  puts $f "ALL_33_INTERNAL_SRAM\t$internal_area\tUNRESOLVED_OFFICIAL_MACRO_TABLE"
  puts $f "CONSERVATIVE_UPPER_BOUND\t[expr {$standard_area+$internal_area}]\tNOT_A_CONTEST_SCORE"
  close $f
  write -format verilog -hierarchy -output mapped.v
  write -format ddc -hierarchy -output mapped.ddc
  write_sdc mapped.sdc
  eco_finish DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
