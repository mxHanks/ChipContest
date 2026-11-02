set_host_options -max_cores 2
set_app_var target_library [list {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db}]
set_app_var link_library [list * {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db}]
set_app_var synthetic_library [list dw_foundation.sldb]
if {[catch {
if {![analyze -format sverilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/XRowBuffer.sv}]} {error {analysis failed: XRowBuffer.sv}}
if {![analyze -format sverilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/WeightBankArray.sv}]} {error {analysis failed: WeightBankArray.sv}}
if {![analyze -format sverilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/WeightBank.sv}]} {error {analysis failed: WeightBank.sv}}
if {![analyze -format sverilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/Sram1024x16.sv}]} {error {analysis failed: Sram1024x16.sv}}
if {![analyze -format sverilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/LinearComputeCore.sv}]} {error {analysis failed: LinearComputeCore.sv}}
if {![analyze -format sverilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/DotProductEngine.sv}]} {error {analysis failed: DotProductEngine.sv}}
if {![analyze -format sverilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/MacController.sv}]} {error {analysis failed: MacController.sv}}
if {![analyze -format sverilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/MacPEArray.sv}]} {error {analysis failed: MacPEArray.sv}}
if {![analyze -format sverilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/MacPE.sv}]} {error {analysis failed: MacPE.sv}}
if {![analyze -format sverilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/BiasBankCache.sv}]} {error {analysis failed: BiasBankCache.sv}}
if {![analyze -format sverilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/LinearCachedCore.sv}]} {error {analysis failed: LinearCachedCore.sv}}
if {![analyze -format sverilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/accel_icb_slave.v}]} {error {analysis failed: accel_icb_slave.v}}
if {![analyze -format sverilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/xu-sram-adapter.sv}]} {error {analysis failed: xu-sram-adapter.sv}}
if {![elaborate accel_icb_slave]} {error {elaboration failed}}
current_design accel_icb_slave
if {![link]} {error {link failed}}
check_design > precheck.rpt
source constraints.sdc
report_units > units.rpt
compile
check_design > postcheck.rpt
check_timing > check-timing.rpt
report_area -hierarchy > area.rpt
report_reference -hierarchy > references.rpt
report_timing -delay_type max -max_paths 10 > setup.rpt
report_timing -delay_type min -max_paths 10 > hold.rpt
report_constraint -all_violators > violations.rpt
report_qor > qor.rpt
write -format verilog -hierarchy -output mapped.v
write -format ddc -hierarchy -output mapped.ddc
write_sdc mapped.sdc
puts "XU_DC_BASELINE_PASS"
} message]} {puts stderr "XU_DC_BASELINE_FAIL $message"; exit 1}
exit 0
