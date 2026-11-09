# NEW candidate-specific, unqualified full digital SoC synthesis.
# Historical guarded flows and all validated RTL remain unchanged.
# libraries.tcl is created by run_once.py from explicit server .db paths/hashes.
proc dma_require_count {label filter expected} {
  set objects [get_cells -quiet -hierarchical -filter $filter]
  set actual [sizeof_collection $objects]
  puts "DMA_SYNTH_COUNT $label actual=$actual expected=$expected"
  if {$actual != $expected} {error "wrong instance count for $label: $actual, expected $expected"}
  return $objects
}
proc dma_check_hierarchy {} {
  set main {u_soc/u_e203_subsys_top/u_e203_subsys_main}
  dma_require_count cpu "full_name == ${main}/u_e203_cpu_top && ref_name =~ e203_cpu_top*" 1
  dma_require_count peripheral_dma "full_name == ${main}/u_e203_subsys_perips/u_xu_matrix_dma && ref_name =~ xu_matrix_dma*" 1
  dma_require_count arbiter "full_name == ${main}/u_xu_dma_shared_arb && ref_name =~ xu_dma_shared_arb*" 1
  dma_require_count original_peripheral_fabric "full_name == ${main}/u_e203_subsys_perips/u_sirv_ppi_fab && ref_name =~ sirv_icb1to16_bus*" 1
  dma_require_count old_accelerator "full_name == ${main}/u_e203_subsys_perips/u_accel_icb_slave" 0
  set core ${main}/u_e203_subsys_perips/u_xu_matrix_dma/u_core
  dma_require_count rowpair_core "full_name == $core && ref_name =~ LinearRowPairDmaCore*" 1
  dma_require_count engine0 "full_name == $core/engines_0 && ref_name =~ DotProductEngine*" 1
  dma_require_count engine1 "full_name == $core/engines_1 && ref_name =~ DotProductEngine*" 1
  set groups [list \
    [list itcm "full_name =~ ${main}/u_e203_cpu_top/u_e203_srams/u_e203_itcm_ram/* && ref_name == RAMSP1024X16" 32] \
    [list dtcm "full_name =~ ${main}/u_e203_cpu_top/u_e203_srams/u_e203_dtcm_ram/* && ref_name == RAMSP1024X16" 32] \
    [list shared {full_name =~ u_shared/storage/* && ref_name == RAMSP1024X16} 256] \
    [list weights "full_name =~ $core/weights/* && ref_name == RAMSP1024X16" 16] \
    [list bias "full_name =~ $core/bias/memory/* && ref_name == RAMSP1024X16" 1]]
  set seen [dict create]
  foreach group $groups {
    set cells [dma_require_count [lindex $group 0] [lindex $group 1] [lindex $group 2]]
    foreach_in_collection cell $cells {
      set name [get_object_name $cell]
      if {[dict exists $seen $name]} {error "overlapping SRAM groups: $name"}
      dict set seen $name 1
    }
  }
  dma_require_count all_ramsp {ref_name == RAMSP1024X16} 337
  if {[dict size $seen] != 337} {error {not every SRAM macro is uniquely accounted for}}
}
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
  if {![analyze -format sverilog -define [list SYNTHESIS DISABLE_SV_ASSERTION=1 XU_MATRIX_DMA] $sources]} {error {DC analyze failed}}
  elaborate xu_soc_ppa_top
  current_design xu_soc_ppa_top
  if {![link]} {error {DC link failed}}
  if {[sizeof_collection [current_design]] != 1} {error {missing current design}}
  dma_reject_unresolved
  dma_check_hierarchy
  check_design > precheck.rpt
  set XU_CLOCK_MODE envelope
  set XU_PLL_DIV 0
  source constraints.sdc
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
  dma_check_hierarchy
  set leaf_file [open leaf-inventory.tsv w]
  puts $leaf_file "instance\treference\tarea_library_units\tclassification"
  set std_count 0
  set macro_count 0
  set const_count 0
  set std_area 0.0
  set macro_area 0.0
  foreach_in_collection cell [get_cells -quiet -hierarchical -filter {is_hierarchical == false}] {
    set ref [get_attribute $cell ref_name]
    if {$ref eq {**logic_0**} || $ref eq {**logic_1**}} {
      incr const_count
      puts $leaf_file "[get_object_name $cell]\t$ref\t0\tnative_constant"
    } else {
      if {![string is true -strict [get_attribute $cell is_mapped]]} {error "unmapped leaf: [get_object_name $cell] $ref"}
      set area [get_attribute $cell area]
      if {![string is double -strict $area] || $area<=0} {error "missing/nonpositive area: [get_object_name $cell] $ref $area"}
      if {$ref eq {RAMSP1024X16}} {incr macro_count; set macro_area [expr {$macro_area+$area}]; set category SRAM} else {
        incr std_count; set std_area [expr {$std_area+$area}]; set category standard_cell
      }
      puts $leaf_file "[get_object_name $cell]\t$ref\t$area\t$category"
    }
  }
  close $leaf_file
  set f [open leaf-area-summary.txt w]
  puts $f "STANDARD_CELL_COUNT=$std_count\nSTANDARD_CELL_AREA=$std_area\nSRAM_COUNT=$macro_count\nSRAM_AREA=$macro_area\nNATIVE_CONSTANT_COUNT=$const_count"
  puts $f "STATUS=SERVER_SYNTHESIS_ONLY_NOT_QUALIFIED"
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
  set XU_CLOCK_REVIEW_DIR dc-clock-reports
  source clock-review.tcl
  set f [open SYNTHESIS_COMPLETE_NOT_QUALIFIED.txt w]
  puts $f "DMA_SERVER_SYNTH_COMPLETE_UNQUALIFIED"
  puts $f "No mapped functional equivalence, standalone STA or formal contest qualification claimed."
  close $f
  puts "DMA_SERVER_SYNTH_COMPLETE_UNQUALIFIED"
} reason options]
if {$failure} {
  set f [open SYNTHESIS_FAILED.txt w]
  puts $f $reason
  if {[dict exists $options -errorinfo]} {puts $f [dict get $options -errorinfo]}
  close $f
  puts stderr "DMA_SERVER_SYNTH_FAILED: $reason"
  exit 1
}
exit 0
