# xu full-SoC digital timing contract. Time is ns; capacitance follows the library.
# Source after elaborating/linking xu_soc_ppa_top, before compile (and again in PT).
# Keep the named HCLKGEN/divider and register-bank boundaries when synthesizing.
# Defaults are a conservative frequency envelope, NOT an STA pass certificate.
# See docs/xu-full-soc-clock-review.md for assumptions, modes and outstanding checks.

if {![info exists XU_CLOCK_MODE]} { set XU_CLOCK_MODE envelope }
if {![info exists XU_PLL_DIV]} { set XU_PLL_DIV 0 }
if {![info exists XU_PROPAGATE_CLOCKS]} { set XU_PROPAGATE_CLOCKS 0 }
if {![info exists XU_IO_MAX_NS]} { set XU_IO_MAX_NS 0.5 }
if {![info exists XU_IO_MIN_NS]} { set XU_IO_MIN_NS 0.0 }
if {![info exists XU_JTAG_IO_MAX_NS]} { set XU_JTAG_IO_MAX_NS 5.0 }
if {![info exists XU_OUTPUT_LOAD]} { set XU_OUTPUT_LOAD 0.01 }

proc xu_require_one {kind name} {
    if {$kind eq "port"} { set obj [get_ports -quiet $name] } else {
        set obj [get_pins -quiet $name]
    }
    if {[sizeof_collection $obj] != 1} {
        error "xu_full_soc.sdc: expected one $kind $name; preserve hierarchy/check top"
    }
    return $obj
}
if {$XU_CLOCK_MODE ni {envelope reset_bypass divider}} {
    error "XU_CLOCK_MODE must be envelope, reset_bypass, or divider"
}
if {![string is integer -strict $XU_PLL_DIV] || $XU_PLL_DIV < 0 || $XU_PLL_DIV > 63} {
    error "XU_PLL_DIV must be an integer in 0..63"
}
if {$XU_IO_MIN_NS > $XU_IO_MAX_NS} { error "xu I/O min exceeds max" }

set xu_hf [xu_require_one port hfextclk]
set xu_lf [xu_require_one port lfextclk]
set xu_tck [xu_require_one port io_pads_jtag_TCK_i_ival]
create_clock -name xu_hfextclk -period 6.666666667 -waveform {0 3.3333333335} $xu_hf
create_clock -name xu_lfextclk -period 30517.578125 -waveform {0 15258.7890625} $xu_lf
# 10 MHz is the explicit engineering JTAG assumption, not a contest requirement.
create_clock -name xu_jtag_tck -period 100.0 -waveform {0 50.0} $xu_tck

set xu_main u_soc/u_e203_subsys_top/u_e203_subsys_main
set xu_hclkgen ${xu_main}/u_e203_subsys_hclkgen
set xu_hclkregs ${xu_main}/u_e203_subsys_perips/u_sirv_hclkgen_regs
set xu_div_source [xu_require_one pin ${xu_hclkgen}/u_e203_subsys_pllclkdiv/clk]
set xu_div_target [xu_require_one pin ${xu_hclkgen}/u_e203_subsys_pllclkdiv/clkout]

if {$XU_CLOCK_MODE eq "envelope"} {
    # Every real output pulse is a subset of source pulses: analyze the output
    # at the fastest 150 MHz, with the real 50% source high pulse. No register
    # value is assumed, and the clock-control logic remains timed. This can
    # overconstrain slower programmed states; it never grants a longer cycle.
    create_generated_clock -add -name xu_plldiv_envelope -master_clock xu_hfextclk \
        -source $xu_div_source -divide_by 1 $xu_div_target
} else {
    # These are sirv_hclkgen_regs register OUTPUT pins. Case values express a
    # static operational mode; they do not prove reset/startup/mode-transition
    # timing. Always retain the envelope run alongside a static-mode run.
    set xu_bypass [xu_require_one pin ${xu_hclkregs}/pllbypass]
    set xu_divby1 [xu_require_one pin ${xu_hclkregs}/plloutdivby1]
    set_case_analysis [expr {$XU_CLOCK_MODE eq "reset_bypass" ? 1 : 0}] $xu_bypass
    set_case_analysis [expr {$XU_CLOCK_MODE eq "reset_bypass" ? 1 : 0}] $xu_divby1
    for {set xu_bit 0} {$xu_bit < 6} {incr xu_bit} {
        set xu_bitpin [xu_require_one pin [format {%s/plloutdiv[%d]} $xu_hclkregs $xu_bit]]
        set xu_value [expr {$XU_CLOCK_MODE eq "reset_bypass" ? 0 : (($XU_PLL_DIV >> $xu_bit) & 1)}]
        set_case_analysis $xu_value $xu_bitpin
    }
    if {$XU_CLOCK_MODE eq "divider"} {
        # RTL is pulse swallowing, not a 50% toggle divider. N=2*(div+1),
        # output high time=Tsource/2, period=N*Tsource. Source edge indices
        # 1,2,2*N+1 preserve the short high pulse needed for pulse-width checks.
        create_generated_clock -add -name xu_plldiv_static -master_clock xu_hfextclk \
            -source $xu_div_source -edges [list 1 2 [expr {4*($XU_PLL_DIV+1)+1}]] $xu_div_target
    } else {
        create_generated_clock -add -name xu_plldiv_by1 -master_clock xu_hfextclk \
            -source $xu_div_source -divide_by 1 $xu_div_target
    }
}

# PLL RTL is assign-through in both preprocessing branches. It is deliberately
# NOT modeled as an analog frequency multiplier. Mux and latch/AND clock gates
# propagate these clocks; the endpoint SRAM is clocked directly by hfextclk.
set_clock_uncertainty 0.1 [all_clocks]
set_clock_transition 0.1 [all_clocks]
set_clock_gating_check -setup 0.1 -hold 0.1 [all_clocks]

# Provisional external digital I/O contract, not board/datasheet signoff.
# Retain reset, wakeup, straps and peripheral I/O in timing. Referencing an
# asynchronous pad to a clock does not establish CDC safety or reset release.
set xu_clock_ports [get_ports {hfextclk lfextclk io_pads_jtag_TCK_i_ival}]
set xu_jtag_inputs [get_ports {io_pads_jtag_TMS_i_ival io_pads_jtag_TDI_i_ival}]
set xu_other_inputs [remove_from_collection [all_inputs] $xu_clock_ports]
set xu_other_inputs [remove_from_collection $xu_other_inputs $xu_jtag_inputs]
set_input_delay -max $XU_IO_MAX_NS -clock xu_hfextclk $xu_other_inputs
set_input_delay -min $XU_IO_MIN_NS -clock xu_hfextclk $xu_other_inputs
set_input_delay -max $XU_JTAG_IO_MAX_NS -clock xu_jtag_tck $xu_jtag_inputs
set_input_delay -min $XU_IO_MIN_NS -clock xu_jtag_tck $xu_jtag_inputs
set_input_transition 0.1 [remove_from_collection [all_inputs] $xu_clock_ports]

set xu_jtag_outputs [get_ports {io_pads_jtag_TDO_o_oval io_pads_jtag_TDO_o_oe}]
set xu_other_outputs [remove_from_collection [all_outputs] $xu_jtag_outputs]
set_output_delay -max $XU_IO_MAX_NS -clock xu_hfextclk $xu_other_outputs
set_output_delay -min $XU_IO_MIN_NS -clock xu_hfextclk $xu_other_outputs
set_output_delay -max $XU_JTAG_IO_MAX_NS -clock xu_jtag_tck $xu_jtag_outputs
set_output_delay -min $XU_IO_MIN_NS -clock xu_jtag_tck $xu_jtag_outputs
set_load $XU_OUTPUT_LOAD [all_outputs]
if {$XU_PROPAGATE_CLOCKS} { set_propagated_clock [all_clocks] }

# Intentionally no false paths, multicycle paths, asynchronous/exclusive clock
# groups, reset idealization or case analysis on reset/peripheral/gate enables.
# Unrelated domains are left visible until individual CDC/reset paths are
# reviewed; an envelope STA violation cannot be waived by a static-mode pass.

# Team LF input contract v1 overlay, applied after the exact original SDC.
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
