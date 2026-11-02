set_host_options -max_cores 2
set_app_var target_library [list {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db}]
set_app_var link_library [list * {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db}]
read_ddc {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/candidate-ss-02/mapped.ddc}
current_design accel_icb_slave
link
set_fix_hold [get_clocks xu_clk]
compile -incremental_mapping -only_hold_time
report_area -hierarchy > area.rpt
report_constraint -all_violators > violations.rpt
report_timing -delay_type min -max_paths 5 > hold.rpt
report_timing -delay_type max -max_paths 5 > setup.rpt
write -format verilog -hierarchy -output mapped.v
write -format ddc -hierarchy -output mapped.ddc
write_sdc mapped.sdc
puts "XU_HOLD_REPAIR_DC_PASS"
exit 0
