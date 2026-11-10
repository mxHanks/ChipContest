# Read-only hierarchy contract for a future same-source DC/PT job.
# This file launches no EDA process and performs no compile/optimization.
# Source only after xu_soc_dma64_ppa_top has elaborated/linked; rerun after mapping.
proc p4k_require_count {label filter expected} {
  set objects [get_cells -quiet -hierarchical -filter $filter]
  set actual [sizeof_collection $objects]
  puts "P4K_COUNT $label actual=$actual expected=$expected"
  if {$actual != $expected} {error "P4K wrong instance count for $label: $actual != $expected"}
  return $objects
}
proc p4k_check_hierarchy {} {
  set main {u_soc/u_e203_subsys_top/u_e203_subsys_main}
  set dma ${main}/u_e203_subsys_perips/u_xu_matrix_dma
  set core ${dma}/u_core
  p4k_require_count cpu "full_name == ${main}/u_e203_cpu_top && ref_name =~ e203_cpu_top*" 1
  p4k_require_count dma64 "full_name == $dma && ref_name =~ xu_matrix_dma64*" 1
  p4k_require_count arbiter64 "full_name == ${main}/u_xu_dma_shared_arb && ref_name =~ xu_dma64_shared_arb*" 1
  p4k_require_count original_peripheral_fabric "full_name == ${main}/u_e203_subsys_perips/u_sirv_ppi_fab && ref_name =~ sirv_icb1to16_bus*" 1
  p4k_require_count old_accelerator "full_name == ${main}/u_e203_subsys_perips/u_accel_icb_slave" 0
  p4k_require_count tile_core "full_name == $core && ref_name =~ LinearTileDmaCore*" 1
  p4k_require_count tile_engines "full_name =~ $core/engines_* && ref_name =~ DotProductEngine*" 8
  p4k_require_count tile_pes "full_name =~ $core/* && ref_name =~ MacPE* && ref_name !~ MacPEArray*" 64
  p4k_require_count endpoint "full_name == u_shared && ref_name =~ xu_shared_icb_sram64*" 1
  set groups [list \
    [list itcm "full_name =~ ${main}/u_e203_cpu_top/u_e203_srams/u_e203_itcm_ram/* && ref_name == RAMSP1024X16" 32] \
    [list dtcm "full_name =~ ${main}/u_e203_cpu_top/u_e203_srams/u_e203_dtcm_ram/* && ref_name == RAMSP1024X16" 32] \
    [list shared {full_name =~ u_shared/banks* && ref_name == RAMSP1024X16} 256] \
    [list weights "full_name =~ $core/weights/* && ref_name == RAMSP1024X16" 16] \
    [list bias "full_name =~ $core/bias/memory/* && ref_name == RAMSP1024X16" 1]]
  set seen [dict create]
  foreach group $groups {
    set cells [p4k_require_count [lindex $group 0] [lindex $group 1] [lindex $group 2]]
    foreach_in_collection cell $cells {
      set name [get_object_name $cell]
      if {[dict exists $seen $name]} {error "P4K overlapping SRAM scopes: $name"}
      dict set seen $name 1
    }
  }
  p4k_require_count all_ramsp {ref_name == RAMSP1024X16} 337
  if {[dict size $seen] != 337} {error {P4K every SRAM macro must be uniquely accounted for}}
  puts {P4K_GEOMETRY_VERIFIED_NOT_TIMING_OR_AREA_QUALIFICATION}
}
