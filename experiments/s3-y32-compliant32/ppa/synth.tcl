# New SYSBUS32 candidate; independent source identity and same-library compile policy.
# Reference SDC is provisional. No timing closure or 2.25mm2 qualification claimed.
# Historical guarded flows and all validated RTL remain unchanged.
# libraries.tcl is created by run_once.py from explicit server .db paths/hashes.
source source/ppa/hierarchy_contract.tcl
proc dma_reject_unresolved {} {
  foreach_in_collection design [get_designs *] {
    set bb [get_attribute $design is_black_box]
    if {[string is true -strict $bb]} {error "unresolved design: [get_object_name $design]"}
    if {$bb ne "" && ![string is false -strict $bb]} {error "unexpected blackbox status: [get_object_name $design]: $bb"}
  }
}
set failure [catch {
  source libraries.tcl
  set_host_options -max_cores 2
  set include_paths [list source/rtl/core source/rtl/perips source/rtl/perips/apb_i2c]
  set_app_var search_path [concat $search_path $include_paths]
  define_design_lib WORK -path ./WORK
  set_svf default.svf
  set f [open rtl.f r]
  set sources [split [string trim [read $f]] \n]
  close $f
  if {![analyze -format sverilog -define $sysbus32_production_defines $sources]} {error {DC analyze failed}}
  elaborate xu_soc_sysbus32_ppa_top
  current_design xu_soc_sysbus32_ppa_top
  if {![link]} {error {DC link failed}}
  if {[sizeof_collection [current_design]] != 1} {error {missing current design}}
  dma_reject_unresolved
  sysbus32_check_hierarchy
  check_design > precheck.rpt
  set XU_CLOCK_MODE envelope
  set XU_PLL_DIV 0
  source source/contracts/reference-full-soc.sdc
  foreach pair {{xu_hfextclk 6.666666667} {xu_lfextclk 30517.578125} {xu_jtag_tck 100.0}} {
    set clock [get_clocks -quiet [lindex $pair 0]]
    if {[sizeof_collection $clock] != 1} {error "missing clock: $pair"}
    if {abs([get_attribute $clock period]-[lindex $pair 1])>0.000001} {error "wrong clock period: $pair"}
  }
  if {[sizeof_collection [get_clocks -quiet xu_plldiv_envelope]] != 1} {error {divider envelope clock missing}}
  set_boundary_optimization [get_cells -hierarchical -filter {is_hierarchical == true}] false
  set_dont_touch [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}] true
  set_fix_hold [all_clocks]
  compile_ultra -no_autoungroup
  if {![link]} {error {mapped DC link failed}}
  dma_reject_unresolved
  sysbus32_check_hierarchy
  set leaf_file [open leaf-inventory.tsv w]
  puts $leaf_file "instance\treference\tarea_library_units\tclassification\tcharged_scope"
  set std_count 0
  set macro_count 0
  set const_count 0
  set charged_logic_area 0.0
  set charged_sram_area 0.0
  set charged_logic_count 0
  set charged_sram_count 0
  set charge_dma {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_xu_matrix_dma/}
  set charge_ingress {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_xu_systembus_ingress/}
  set charge_nice {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_cpu_top/u_e203_cpu/u_e203_nice_core/}
  set std_area 0.0
  set macro_area 0.0
  foreach_in_collection cell [get_cells -quiet -hierarchical -filter {is_hierarchical == false}] {
    set ref [get_attribute $cell ref_name]
    if {$ref eq {**logic_0**} || $ref eq {**logic_1**}} {
      incr const_count
      puts $leaf_file "[get_object_name $cell]\t$ref\t0\tnative_constant\tnone"
    } else {
      if {![string is true -strict [get_attribute $cell is_mapped]]} {error "unmapped leaf: [get_object_name $cell] $ref"}
      set area [get_attribute $cell area]
      if {![string is double -strict $area] || $area<=0} {error "missing/nonpositive area: [get_object_name $cell] $ref $area"}
      if {$ref eq {RAMSP1024X16}} {incr macro_count; set macro_area [expr {$macro_area+$area}]; set category SRAM} else {
        incr std_count; set std_area [expr {$std_area+$area}]; set category standard_cell
      }
      set instance [get_object_name $cell]
      set scope none
      set scope_hits 0
      if {[string first $charge_dma $instance] == 0} {set scope dma; incr scope_hits}
      if {[string first $charge_ingress $instance] == 0} {set scope systembus32_ingress; incr scope_hits}
      if {[string first $charge_nice $instance] == 0} {set scope cpu_nice_interface; incr scope_hits}
      if {[string first {u_shared/} $instance] == 0 && $ref ne {RAMSP1024X16}} {set scope endpoint_logic; incr scope_hits}
      if {$scope_hits > 1} {error "overlapping charged leaf scope: $instance"}
      if {$scope ne {none}} {
        if {$ref eq {RAMSP1024X16}} {
          incr charged_sram_count
          set charged_sram_area [expr {$charged_sram_area+$area}]
        } else {
          incr charged_logic_count
          set charged_logic_area [expr {$charged_logic_area+$area}]
        }
      }
      puts $leaf_file "$instance\t$ref\t$area\t$category\t$scope"
    }
  }
  close $leaf_file
  set f [open leaf-area-summary.txt w]
  puts $f "STANDARD_CELL_COUNT=$std_count\nSTANDARD_CELL_AREA=$std_area\nSRAM_COUNT=$macro_count\nSRAM_AREA=$macro_area\nNATIVE_CONSTANT_COUNT=$const_count"
  if {$charged_sram_count != $sysbus32_expected_internal_macros} {error "wrong charged SRAM count: $charged_sram_count"}
  puts $f "CHARGED_STANDARD_CELL_COUNT=$charged_logic_count\nCHARGED_STANDARD_CELL_AREA=$charged_logic_area"
  puts $f "CHARGED_SRAM_COUNT=$charged_sram_count\nCHARGED_SRAM_AREA=$charged_sram_area"
  puts $f "CHARGED_TOTAL_AREA_LIBRARY_UNITS=[expr {$charged_logic_area+$charged_sram_area}]"
  puts $f "AREA_DIMENSION=UNVERIFIED_DO_NOT_DECLARE_MM2_OR_CONTEST_PASS"
  puts $f "STATUS=SERVER_SYNTHESIS_ONLY_NOT_QUALIFIED"
  close $f
  # A separate conservative upper bound includes EVERY full-SoC standard cell,
  # so undiscovered/inherited interface logic cannot escape this bound. Only
  # the320 reused CPU/shared SRAMs are excluded; all internal macros remain.
  if {$macro_count-$sysbus32_expected_internal_macros != 320} {error {upper-bound reused SRAM count mismatch}}
  set f [open area-upper-bound.tsv w]
  puts $f "component\tleaf_count\tarea_library_units\tofficial_area_mm2"
  puts $f "ALL_FULL_SOC_STANDARD_CELLS\t$std_count\t$std_area\tUNRESOLVED_UNIT_CONVERSION"
  puts $f "ALL_INTERNAL_RAMSP1024X16\t$sysbus32_expected_internal_macros\t$charged_sram_area\tUNRESOLVED_OFFICIAL_MACRO_TABLE"
  puts $f "EXCLUDED_REUSED_CPU_SHARED_RAMSP1024X16\t320\tNOT_INCLUDED\tNOT_INCLUDED"
  puts $f "CONSERVATIVE_UPPER_BOUND_RAW_SUM\t[expr {$std_count+$sysbus32_expected_internal_macros}]\t[expr {$std_area+$charged_sram_area}]\tUNKNOWN_NOT_A_CONTEST_SCORE"
  close $f
  check_design > postcheck.rpt
  report_units > dc-units.rpt
  report_area -hierarchy > area.rpt
  report_reference -hierarchy > references.rpt
  report_qor > qor.rpt
  report_clock > clocks.rpt
  report_timing -delay_type max -max_paths 50 -significant_digits 8 > dc-setup.rpt
  report_timing -delay_type min -max_paths 50 -significant_digits 8 > dc-hold.rpt
  report_constraint -all_violators > dc-violations.rpt
  write -format verilog -hierarchy -output mapped.v
  write -format ddc -hierarchy -output mapped.ddc
  write_sdc mapped.sdc
  source area_components.tcl
  set XU_CLOCK_REVIEW_DIR dc-clock-reports
  source source/contracts/reference-clock-review.tcl
  set f [open SYNTHESIS_COMPLETE_NOT_QUALIFIED.txt w]
  puts $f "SYSBUS32_SERVER_SYNTH_COMPLETE_UNQUALIFIED"
  puts $f "No mapped functional equivalence, standalone STA or formal contest qualification claimed."
  close $f
  puts "SYSBUS32_SERVER_SYNTH_COMPLETE_UNQUALIFIED"
} reason options]
if {$failure} {
  set f [open SYNTHESIS_FAILED.txt w]
  puts $f $reason
  if {[dict exists $options -errorinfo]} {puts $f [dict get $options -errorinfo]}
  close $f
  puts stderr "SYSBUS32_SERVER_SYNTH_FAILED: $reason"
  exit 1
}
exit 0
