set_app_var link_path [list * {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db}]
if {[catch {set_app_var power_enable_analysis true} message]} {puts "XU_PT_POWER_ENABLE_FAIL $message"}
if {[catch {
read_verilog mapped.v
if {![link_design accel_icb_slave]} {error {link_design failed}}
read_sdc mapped.sdc
update_timing
check_timing -verbose > pt-check-timing.rpt
report_timing -delay_type max -slack_lesser_than 1000 -max_paths 10 > pt-setup.rpt
report_timing -delay_type min -slack_lesser_than 1000 -max_paths 10 > pt-hold.rpt
report_constraint -all_violators > pt-violations.rpt
report_units > pt-units.rpt
man read_vcd > pt-man-read-vcd.txt
man read_saif > pt-man-read-saif.txt
puts "XU_PT_STA_PASS"
} message]} {puts stderr "XU_PT_STA_FAIL $message"; exit 1}
if {[catch {
set_app_var power_analysis_mode averaged
update_power
report_power -hierarchy > pt-vectorless-power-capability.rpt
report_switching_activity > pt-switching-activity.rpt
puts "XU_PT_POWER_API_PASS_VECTORLESS_ONLY"
} message]} {puts "XU_PT_POWER_API_FAIL $message"}
exit 0
