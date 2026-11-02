set_app_var link_path [list * {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db}]
read_verilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/candidate-ss-02/mapped.v}
if {![link_design accel_icb_slave]} {exit 1}
read_sdc {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/candidate-ss-02/mapped.sdc}
update_timing
report_units > units.rpt
check_timing -verbose > check-timing.rpt
report_analysis_coverage > analysis-coverage.rpt
report_timing -delay_type max -slack_lesser_than 1000 -max_paths 5 -significant_digits 8 > setup-exact.rpt
report_timing -delay_type min -slack_lesser_than 1000 -max_paths 5 -significant_digits 8 > hold-exact.rpt
set xu_max [get_timing_paths -delay_type max -slack_lesser_than 1000 -max_paths 1]
set xu_min [get_timing_paths -delay_type min -slack_lesser_than 1000 -max_paths 1]
puts "XU_SETUP_SLACK_NS [get_attribute $xu_max slack]"
puts "XU_HOLD_SLACK_NS [get_attribute $xu_min slack]"
puts "XU_SRAM_MACRO_COUNT [sizeof_collection [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}]]"
puts "XU_EXACT_AUDIT_PASS"
exit 0
