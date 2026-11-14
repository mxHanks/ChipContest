# Team LF input contract v1, ns. Source AFTER xu_full_soc.sdc.
# See docs/s3-y32-async-input-contract.md and the v1 validation report.
# This is an external stimulus obligation, not an official contest specification.
# BOOTROM is fixed at startup (>=8 LF samples before ERST_N release) and in run.
# DWAKEUP_N changes 1..2ns after LF falling, with >=4T and >=4 samples per level.
# ERST_N may assert asynchronously; release is 1..2ns after LF falling, after
# >=8T and >=8 valid samples low. No release while LF is stopped.
# Only ERST_N rising is remodeled; its falling (assertion) retains the baseline
# HF reference for diagnostic continuity, not as a restriction on async assertion.
# No timing exception or disabling command is introduced.
set xu_lf_v1_clock [get_clocks -quiet xu_lfextclk]
if {[sizeof_collection $xu_lf_v1_clock] != 1 ||
    abs([get_attribute $xu_lf_v1_clock period] - 30517.578125) > 0.000001} {
    error {LF contract v1 requires the original 32.768 kHz clock}
}
set xu_lf_v1_data [get_ports -quiet {io_pads_bootrom_n_i_ival io_pads_aon_pmu_dwakeup_n_i_ival}]
set xu_lf_v1_reset [get_ports -quiet io_pads_aon_erst_n_i_ival]
if {[sizeof_collection $xu_lf_v1_data] != 2 || [sizeof_collection $xu_lf_v1_reset] != 1} {
    error {LF contract v1 requires exactly the three named input pads}
}
remove_input_delay $xu_lf_v1_data
set_input_delay -clock xu_lfextclk -clock_fall -min 1.0 $xu_lf_v1_data
set_input_delay -clock xu_lfextclk -clock_fall -max 2.0 $xu_lf_v1_data
remove_input_delay -rise $xu_lf_v1_reset
set_input_delay -clock xu_lfextclk -clock_fall -rise -add_delay -min 1.0 $xu_lf_v1_reset
set_input_delay -clock xu_lfextclk -clock_fall -rise -add_delay -max 2.0 $xu_lf_v1_reset
