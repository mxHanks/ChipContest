# xu read-only audit proposal. Do not source into the archived baseline session.
# Source the original 150 MHz envelope SDC in a fresh linked PT session first.
# This changes only proven first-D asynchronous sampling checks; it does not
# declare qualification. Root runner must archive exceptions and new coverage.

proc xu_audit_one {kind name} {
    if {$kind eq "port"} {
        set obj [get_ports -quiet $name]
    } else {
        set obj [get_pins -quiet $name]
    }
    if {[sizeof_collection $obj] != 1} {
        error "xu scope audit expected one $kind: $name"
    }
    return $obj
}
set xu_audit_main u_soc/u_e203_subsys_top/u_e203_subsys_main
set xu_audit_perips ${xu_audit_main}/u_e203_subsys_perips
set xu_audit_aon u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper

# 64 exact pad -> first synchronizer D boundaries; never -to whole cells.
foreach xu_bank {A B} {
    for {set xu_b 0} {$xu_b < 32} {incr xu_b} {
        set xu_src [xu_audit_one port [format {io_pads_gpio%s_i_ival[%d]} $xu_bank $xu_b]]
        set xu_dst [xu_audit_one pin [format {%s/u_perips_apb_gpio%s/r_gpio_sync0_reg[%d]/D} $xu_audit_perips $xu_bank $xu_b]]
        set_false_path -from $xu_src -to $xu_dst
    }
}

# 4 exact LF -> PWM first-D boundaries. Stages [1]/[2] remain timed.
foreach xu_tim {0 1 2 3} {
    set xu_src [xu_audit_one port lfextclk]
    set xu_dst [xu_audit_one pin [format {%s/u_perips_apb_pwm/u_tim%d/u_in_stage/r_ls_clk_sync_reg[0]/D} $xu_audit_perips $xu_tim]]
    set_false_path -from $xu_src -to $xu_dst
}

# 2 raw asynchronous pads -> deglitch first-D boundaries. Missing/optimized
# mapped cells are an audit stop; do not silently widen matching or skip them.
foreach xu_pair {
    {io_pads_bootrom_n_i_ival bootrom_deglitch}
    {io_pads_aon_pmu_dwakeup_n_i_ival dwakeup_deglitch}
} {
    set xu_src [xu_audit_one port [lindex $xu_pair 0]]
    set xu_dst [xu_audit_one pin ${xu_audit_aon}/[lindex $xu_pair 1]/T_8_reg/D]
    set_false_path -from $xu_src -to $xu_dst
}

# Optional generated-output-clock experiment. Disabled by default because PT
# classification and mux-mode coverage must be inspected, not presumed.
# No false path to these ports, output-delay deletion, or mode case is applied.
if {[info exists XU_AUDIT_FORWARD_CLOCK_EXPERIMENT] && $XU_AUDIT_FORWARD_CLOCK_EXPERIMENT} {
    foreach xu_spec {
        {xu_fwd_jtag xu_jtag_tck io_pads_jtag_TCK_i_ival 26}
        {xu_fwd_lf xu_lfextclk lfextclk 29}
        {xu_fwd_hf xu_hfextclk hfextclk 30}
        {xu_fwd_pll xu_hfextclk hfextclk 31}
    } {
        create_generated_clock -add -name [lindex $xu_spec 0] \
            -master_clock [lindex $xu_spec 1] \
            -source [xu_audit_one port [lindex $xu_spec 2]] -combinational \
            [xu_audit_one port [format {io_pads_gpioA_o_oval[%d]} [lindex $xu_spec 3]]]
    }
    set xu_fwd_core_src [xu_audit_one pin ${xu_audit_main}/u_e203_cpu_top/inspect_core_clk]
    set xu_fwd_core_dst [xu_audit_one port {io_pads_gpioA_o_oval[27]}]
    foreach xu_master {xu_hfextclk xu_plldiv_envelope} {
        create_generated_clock -add -name xu_fwd_core_${xu_master} \
            -master_clock $xu_master -source $xu_fwd_core_src -combinational \
            $xu_fwd_core_dst
    }
}

# Preserve every raw reset pin, gate, SRAM data pin, and UART latch check.
update_timing
