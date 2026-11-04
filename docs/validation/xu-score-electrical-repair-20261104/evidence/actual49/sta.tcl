if {[catch {
set_app_var link_path [list * {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db}]
read_verilog mapped.v
if {![link_design xu_soc_ppa_top]} {error {PT link failed}}
set XU_CLOCK_MODE envelope
set XU_PLL_DIV 0
source {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/full-soc-pt-compatible-05/constraints.sdc}
set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1
source {/storage2/2026contest/server4/s4_23usr/Desktop/xu-ts16.tcl}
# Exact post-elaboration macro groups; overlapping matches and missing/extra cells fail.
set xu_seen [dict create]
set xu_cells [get_cells -quiet -hierarchical -filter {full_name =~ u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_cpu_top/u_e203_srams/u_e203_itcm_ram/* && ref_name == RAMSP1024X16 && is_hierarchical == false}]
if {[sizeof_collection $xu_cells] != 32} {error {wrong macro count: itcm}}
foreach_in_collection xu_c $xu_cells {
  set xu_n [get_object_name $xu_c]
  if {[dict exists $xu_seen $xu_n]} {error "overlapping SRAM group: $xu_n"}
  dict set xu_seen $xu_n 1
  if {[get_attribute $xu_c ref_name] != {RAMSP1024X16}} {error "wrong SRAM reference: $xu_n"}
}
puts "XU_SRAM_GROUP itcm count=32 macro_ref=RAMSP1024X16 logical_bits=524288 physical_bits=524288 padding_bits=0"
set xu_cells [get_cells -quiet -hierarchical -filter {full_name =~ u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_cpu_top/u_e203_srams/u_e203_dtcm_ram/* && ref_name == RAMSP1024X16 && is_hierarchical == false}]
if {[sizeof_collection $xu_cells] != 32} {error {wrong macro count: dtcm}}
foreach_in_collection xu_c $xu_cells {
  set xu_n [get_object_name $xu_c]
  if {[dict exists $xu_seen $xu_n]} {error "overlapping SRAM group: $xu_n"}
  dict set xu_seen $xu_n 1
  if {[get_attribute $xu_c ref_name] != {RAMSP1024X16}} {error "wrong SRAM reference: $xu_n"}
}
puts "XU_SRAM_GROUP dtcm count=32 macro_ref=RAMSP1024X16 logical_bits=524288 physical_bits=524288 padding_bits=0"
set xu_cells [get_cells -quiet -hierarchical -filter {full_name =~ u_shared/storage/* && ref_name == RAMSP1024X16 && is_hierarchical == false}]
if {[sizeof_collection $xu_cells] != 256} {error {wrong macro count: shared}}
foreach_in_collection xu_c $xu_cells {
  set xu_n [get_object_name $xu_c]
  if {[dict exists $xu_seen $xu_n]} {error "overlapping SRAM group: $xu_n"}
  dict set xu_seen $xu_n 1
  if {[get_attribute $xu_c ref_name] != {RAMSP1024X16}} {error "wrong SRAM reference: $xu_n"}
}
puts "XU_SRAM_GROUP shared count=256 macro_ref=RAMSP1024X16 logical_bits=4194304 physical_bits=4194304 padding_bits=0"
set xu_cells [get_cells -quiet -hierarchical -filter {full_name =~ u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave/* && ref_name == RAMSP1024X16 && is_hierarchical == false}]
if {[sizeof_collection $xu_cells] != 16} {error {wrong macro count: accelerator_weights}}
foreach_in_collection xu_c $xu_cells {
  set xu_n [get_object_name $xu_c]
  if {[dict exists $xu_seen $xu_n]} {error "overlapping SRAM group: $xu_n"}
  dict set xu_seen $xu_n 1
  if {[get_attribute $xu_c ref_name] != {RAMSP1024X16}} {error "wrong SRAM reference: $xu_n"}
}
puts "XU_SRAM_GROUP accelerator_weights count=16 macro_ref=RAMSP1024X16 logical_bits=262144 physical_bits=262144 padding_bits=0"
# RAMSP is the explicit technology SRAM namespace; reject every extra leaf/reference.
set xu_allowed_refs [list {RAMSP1024X16}]
set xu_all_macros [get_cells -quiet -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}]
if {[sizeof_collection $xu_all_macros] != 336 || [dict size $xu_seen] != 336} {error {full-SoC SRAM total must be exactly 336}}
foreach_in_collection xu_c $xu_all_macros {
  if {[lsearch -exact $xu_allowed_refs [get_attribute $xu_c ref_name]] < 0} {error {unexpected SRAM reference}}
  if {![dict exists $xu_seen [get_object_name $xu_c]]} {error {ungrouped/unaccounted SRAM macro}}
}
if {[sizeof_collection [get_cells -quiet -hierarchical -filter {full_name == u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave && ref_name =~ accel_icb_slave*}]] != 1} {error {missing/wrong accelerator}}
if {[sizeof_collection [get_cells -quiet -hierarchical -filter {full_name == u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_cpu_top && ref_name =~ e203_cpu_top*}]] != 1} {error {missing/wrong cpu}}
if {[sizeof_collection [get_cells -quiet -hierarchical -filter {full_name == u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_sirv_ppi_fab && ref_name =~ sirv_icb1to16_bus*}]] != 1} {error {missing/wrong interconnect}}
redirect -file units.rpt {report_units}
redirect -file check-timing.rpt {check_timing -verbose}
redirect -file setup.rpt {report_timing -delay_type max -max_paths 50 -significant_digits 8}
redirect -file hold.rpt {report_timing -delay_type min -max_paths 50 -significant_digits 8}
redirect -file constraints.rpt {report_constraint -all_violators -verbose -significant_digits 8}
redirect -file exceptions.rpt {report_exceptions}
redirect -file analysis-coverage.rpt {report_analysis_coverage -status_details untested}
redirect -file clocks.rpt {report_clock -attributes}
set f [open timing-slack.tsv w]
puts $f "delay_type\tpath_count\tworst_slack"
foreach type {max min} {set paths [get_timing_paths -delay_type $type -max_paths 1];if {[sizeof_collection $paths]!=1} {error {timing path missing}};puts $f "$type\t[sizeof_collection $paths]\t[get_attribute $paths slack]"}
close $f

puts {XU_FULL_SOC_CAP_SIZE_REPAIR_PT_DONE_NOT_QUALIFIED}
} xu_error]} {
  puts stderr "XU_FATAL: $xu_error"
  exit 1
}
exit 0
