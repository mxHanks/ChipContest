if {[catch {
set synopsys_auto_setup true
set hdlin_unresolved_modules black_box
read_db -technology_library {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db}
read_db -technology_library {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db}
read_sverilog -r {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/BiasBankCache.sv /storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/DotProductEngine.sv /storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/LinearCachedCore.sv /storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/LinearComputeCore.sv /storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/MacController.sv /storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/MacPE.sv /storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/MacPEArray.sv /storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/Sram1024x16.sv /storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/WeightBank.sv /storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/WeightBankArray.sv /storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/XRowBuffer.sv /storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/accel_icb_slave.v /storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/xu-sram-adapter.sv}
set_top r:/WORK/accel_icb_slave
read_verilog -i {/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/candidate-ss-02/mapped.v}
set_top i:/WORK/accel_icb_slave
match
report_unmatched_points > unmatched.rpt
if {[verify]} {
 puts "XU_FORMALITY_PASS"
 exit 0
} else {
 report_failing_points > failing.rpt
 puts "XU_FORMALITY_FAIL"
 exit 1
}
} xu_error]} {puts stderr "XU_FORMALITY_SCRIPT_ERROR $xu_error"; exit 1}
