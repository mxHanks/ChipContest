if {[catch {
set_app_var link_path [list * {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s1-ppa-campaign-01/xu-ramsp128x16-ss-0p99v-125c.db}]
read_verilog mapped.v
if {![link_design {xu_soc_ppa_top}]} {error {PT link failed}}
source constraints.sdc
foreach xu_pair {{xu_hfextclk 6.666666667} {xu_lfextclk 30517.578125} {xu_jtag_tck 100.0}} {
  set xu_clock [get_clocks -quiet [lindex $xu_pair 0]]
  if {[sizeof_collection $xu_clock] != 1} {error "missing primary clock $xu_pair"}
  if {abs([get_attribute $xu_clock period]-[lindex $xu_pair 1]) > 0.000001} {error "wrong clock period $xu_pair"}
}
if {[sizeof_collection [get_clocks -quiet xu_plldiv_envelope]] != 1} {error {default conservative divider clock is missing}}
set_propagated_clock [all_clocks]
update_timing
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
set xu_cells [get_cells -quiet -hierarchical -filter {full_name =~ u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave/u_linear_compute_core/core/banks_* && ref_name == RAMSP128X16 && is_hierarchical == false}]
if {[sizeof_collection $xu_cells] != 128} {error {wrong macro count: accelerator_weights}}
foreach_in_collection xu_c $xu_cells {
  set xu_n [get_object_name $xu_c]
  if {[dict exists $xu_seen $xu_n]} {error "overlapping SRAM group: $xu_n"}
  dict set xu_seen $xu_n 1
  if {[get_attribute $xu_c ref_name] != {RAMSP128X16}} {error "wrong SRAM reference: $xu_n"}
}
puts "XU_SRAM_GROUP accelerator_weights count=128 macro_ref=RAMSP128X16 logical_bits=262144 physical_bits=262144 padding_bits=0"
# RAMSP is the explicit technology SRAM namespace; reject every extra leaf/reference.
set xu_allowed_refs [list {RAMSP1024X16} {RAMSP128X16}]
set xu_all_macros [get_cells -quiet -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}]
if {[sizeof_collection $xu_all_macros] != 448 || [dict size $xu_seen] != 448} {error {full-SoC SRAM total must be exactly 448}}
foreach_in_collection xu_c $xu_all_macros {
  if {[lsearch -exact $xu_allowed_refs [get_attribute $xu_c ref_name]] < 0} {error {unexpected SRAM reference}}
  if {![dict exists $xu_seen [get_object_name $xu_c]]} {error {ungrouped/unaccounted SRAM macro}}
}
if {[sizeof_collection [get_cells -quiet -hierarchical -filter {full_name == u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave && ref_name =~ xu_pe32_bank128_icb_slave*}]] != 1} {error {missing/wrong accelerator}}
if {[sizeof_collection [get_cells -quiet -hierarchical -filter {full_name == u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_cpu_top && ref_name =~ e203_cpu_top*}]] != 1} {error {missing/wrong cpu}}
if {[sizeof_collection [get_cells -quiet -hierarchical -filter {full_name == u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_sirv_ppi_fab && ref_name =~ sirv_icb1to16_bus*}]] != 1} {error {missing/wrong interconnect}}
check_timing -verbose > check-timing.rpt
report_units > units.rpt
report_clock > pt-clocks.rpt
report_analysis_coverage -status_details untested > analysis-coverage.rpt
report_timing -delay_type max -max_paths 50 -significant_digits 8 > setup.rpt
report_timing -delay_type min -max_paths 50 -significant_digits 8 > hold.rpt
report_constraint -all_violators > violations.rpt
set XU_CLOCK_MODE envelope
set XU_PLL_DIV 0
set XU_CLOCK_REVIEW_DIR clock-reports
source clock-review.tcl
set xu_f [open timing-slack.tsv w]
puts $xu_f "delay_type\tpath_count\tworst_slack"
foreach xu_type {max min} {
set xu_paths [get_timing_paths -delay_type $xu_type -max_paths 1]
if {[sizeof_collection $xu_paths] != 1} {error "no $xu_type timing path"}
puts $xu_f "$xu_type\t[sizeof_collection $xu_paths]\t[get_attribute $xu_paths slack]"
}
close $xu_f

puts {XU_SOC_STA_COMPLETE_NOT_QUALIFIED}
} xu_error]} {
  puts stderr "XU_FATAL: $xu_error"
  exit 1
}
exit 0
