# New32 structural contract only. Source after elaboration/link, before and
# after compile, and on the newly generated netlist in PT. No timing edits.
source [file join [file dirname [info script]] geometry-profile.tcl]
proc sysbus32_require_count {label filter expected} {
  set objects [get_cells -quiet -hierarchical -filter $filter]
  set actual [sizeof_collection $objects]
  puts "SYSBUS32_COUNT $label actual=$actual expected=$expected"
  if {$actual != $expected} {error "SYSBUS32 wrong instance count $label: $actual != $expected"}
  return $objects
}
proc sysbus32_check_hierarchy {} {
  global sysbus32_expected_total_macros sysbus32_expected_x_macros sysbus32_expected_internal_macros
  set main {u_soc/u_e203_subsys_top/u_e203_subsys_main}
  set dma ${main}/u_e203_subsys_perips/u_xu_matrix_dma
  set core ${dma}/u_core
  sysbus32_require_count cpu "full_name == ${main}/u_e203_cpu_top && ref_name =~ e203_cpu_top*" 1
  sysbus32_require_count dma32 "full_name == $dma && ref_name =~ xu_matrix_dma_sysbus32*" 1
  sysbus32_require_count ingress32 "full_name == ${main}/u_xu_systembus_ingress && ref_name =~ xu_systembus_ingress32*" 1
  sysbus32_require_count original_mems "full_name == ${main}/u_e203_subsys_mems && ref_name =~ e203_subsys_mems*" 1
  sysbus32_require_count original_mem_fab "full_name == ${main}/u_e203_subsys_mems/u_sirv_mem_fab && ref_name =~ sirv_icb1to8_bus*" 1
  sysbus32_require_count original_peripheral_fabric "full_name == ${main}/u_e203_subsys_perips/u_sirv_ppi_fab && ref_name =~ sirv_icb1to16_bus*" 1
  sysbus32_require_count old_accelerator "full_name == ${main}/u_e203_subsys_perips/u_accel_icb_slave" 0
  sysbus32_require_count downstream_arbiter "full_name == ${main}/u_xu_dma_shared_arb" 0
  sysbus32_require_count forbidden_wide {ref_name =~ xu_matrix_dma64* || ref_name =~ xu_dma64_shared_arb* || ref_name =~ xu_shared_icb_sram64* || ref_name =~ xu_dma_shared_arb*} 0
  sysbus32_require_count tile_core "full_name == $core && ref_name =~ LinearTileDmaCore*" 1
  sysbus32_require_count tile_engines "full_name =~ $core/engines_* && ref_name =~ DotProductEngine*" 8
  sysbus32_require_count tile_pes "full_name =~ $core/* && ref_name =~ MacPE* && ref_name !~ MacPEArray*" 64
  sysbus32_require_count endpoint "full_name == u_shared && ref_name =~ xu_shared_icb_sram* && ref_name !~ xu_shared_icb_sram64*" 1
  set groups [list \
    [list itcm "full_name =~ ${main}/u_e203_cpu_top/u_e203_srams/u_e203_itcm_ram/* && ref_name == RAMSP1024X16" 32] \
    [list dtcm "full_name =~ ${main}/u_e203_cpu_top/u_e203_srams/u_e203_dtcm_ram/* && ref_name == RAMSP1024X16" 32] \
    [list shared {full_name =~ u_shared/storage/* && ref_name == RAMSP1024X16} 256] \
    [list weights "full_name =~ $core/weights/* && ref_name == RAMSP1024X16" 16] \
    [list bias "full_name =~ $core/bias/memory/* && ref_name == RAMSP1024X16" 1] \
    [list x "full_name =~ $core/xs_*/* && ref_name == RAMSP1024X16" $sysbus32_expected_x_macros]]
  set seen [dict create]
  foreach group $groups {
    set cells [sysbus32_require_count [lindex $group 0] [lindex $group 1] [lindex $group 2]]
    foreach_in_collection cell $cells {
      set name [get_object_name $cell]
      if {[dict exists $seen $name]} {error "SYSBUS32 overlapping SRAM scopes: $name"}
      dict set seen $name 1
    }
  }
  sysbus32_require_count all_ramsp {ref_name == RAMSP1024X16} $sysbus32_expected_total_macros
  sysbus32_require_count internal_ramsp "full_name =~ $core/* && ref_name == RAMSP1024X16" $sysbus32_expected_internal_macros
  sysbus32_require_count x_macro_rows "full_name =~ $core/xs_* && ref_name =~ TileXMacroRowBuffer*" $sysbus32_expected_x_macros
  sysbus32_require_count x_register_rows "full_name =~ $core/xs_* && ref_name =~ TileXRowBuffer*" [expr {16-$sysbus32_expected_x_macros}]
  if {[dict size $seen] != $sysbus32_expected_total_macros} {error {SYSBUS32 every macro must be uniquely accounted for}}
  puts {SYSBUS32_GEOMETRY_VERIFIED_NOT_TIMING_OR_AREA_QUALIFICATION}
}
