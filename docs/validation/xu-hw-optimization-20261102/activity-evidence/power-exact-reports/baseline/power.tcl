set_app_var link_path [list * {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db}]
set_app_var power_enable_analysis true
set_app_var power_analysis_mode averaged
read_verilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/baseline-ss-01/mapped.v}
if {![link_design accel_icb_slave]} {exit 1}
read_sdc {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/baseline-ss-01/mapped.sdc}
update_timing
report_units > units.rpt
if {![read_vcd -rtl -strip_path {tb_accel_soc/dut/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave} -time {43596.67 14072130.0} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/activity-02/baseline/activity-150MHz.vcd.gz}]} {error {read_vcd failed}}
report_switching_activity > activity-before-propagation.rpt
update_power
report_switching_activity > activity-after-propagation.rpt
report_power -hierarchy > power-hierarchy.rpt
report_power -verbose -significant_digits 8 > power-exact.rpt
report_analysis_coverage > timing-analysis-coverage.rpt
puts "XU_ACTIVITY_POWER_PASS"
exit 0
