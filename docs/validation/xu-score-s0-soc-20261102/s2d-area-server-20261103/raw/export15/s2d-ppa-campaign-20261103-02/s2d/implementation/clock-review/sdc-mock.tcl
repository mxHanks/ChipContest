
proc get_ports {args} {
  set result {}
  foreach q [lindex $args end] {
    if {[lsearch -exact $::ports $q] >= 0} { lappend result $q }
  }
  return $result
}
proc get_pins {args} {
  set q [lindex $args end]
  if {$q eq $::missing} { return {} }
  if {[lsearch -exact $::pins $q] >= 0} { return [list $q] }
  return {}
}
proc all_inputs {} { return $::inputs }
proc all_outputs {} { return $::outputs }
proc sizeof_collection {c} { return [llength $c] }
proc remove_from_collection {a b} {
  set result {}
  foreach q $a { if {[lsearch -exact $b $q] < 0} { lappend result $q } }
  return $result
}
proc create_clock {args} {
  set name [lindex $args [expr {[lsearch -exact $args -name]+1}]]
  dict set ::clocks $name $args
}
proc create_generated_clock {args} { set ::generated $args }
proc all_clocks {} { return [dict keys $::clocks] }
proc set_case_analysis {value pins} { foreach p $pins { dict set ::cases $p $value } }
foreach command {set_clock_uncertainty set_clock_transition set_clock_gating_check
                 set_input_delay set_output_delay set_input_transition set_load set_propagated_clock} {
  proc $command {args} {}
}

set inputs [list {hfextclk} {lfextclk} {io_pads_jtag_TCK_i_ival} {io_pads_jtag_TMS_i_ival} {io_pads_jtag_TDI_i_ival} {io_pads_gpioA_i_ival} {io_pads_gpioB_i_ival} {io_pads_qspi0_dq_0_i_ival} {io_pads_qspi0_dq_1_i_ival} {io_pads_qspi0_dq_2_i_ival} {io_pads_qspi0_dq_3_i_ival} {io_pads_aon_erst_n_i_ival} {io_pads_dbgmode0_n_i_ival} {io_pads_dbgmode1_n_i_ival} {io_pads_dbgmode2_n_i_ival} {io_pads_bootrom_n_i_ival} {io_pads_aon_pmu_dwakeup_n_i_ival}]
set outputs [list {hfxoscen} {lfxoscen} {io_pads_jtag_TDO_o_oval} {io_pads_jtag_TDO_o_oe} {io_pads_gpioA_o_oval} {io_pads_gpioA_o_oe} {io_pads_gpioB_o_oval} {io_pads_gpioB_o_oe} {io_pads_qspi0_sck_o_oval} {io_pads_qspi0_cs_0_o_oval} {io_pads_qspi0_dq_0_o_oval} {io_pads_qspi0_dq_0_o_oe} {io_pads_qspi0_dq_1_o_oval} {io_pads_qspi0_dq_1_o_oe} {io_pads_qspi0_dq_2_o_oval} {io_pads_qspi0_dq_2_o_oe} {io_pads_qspi0_dq_3_o_oval} {io_pads_qspi0_dq_3_o_oe} {io_pads_aon_pmu_padrst_o_oval} {io_pads_aon_pmu_vddpaden_o_oval}]
set ports [concat $inputs $outputs]
set pins [list {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_hclkgen/u_e203_subsys_pllclkdiv/clk} {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_hclkgen/u_e203_subsys_pllclkdiv/clkout} {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_sirv_hclkgen_regs/pllbypass} {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_sirv_hclkgen_regs/plloutdivby1} {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_sirv_hclkgen_regs/plloutdiv[0]} {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_sirv_hclkgen_regs/plloutdiv[1]} {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_sirv_hclkgen_regs/plloutdiv[2]} {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_sirv_hclkgen_regs/plloutdiv[3]} {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_sirv_hclkgen_regs/plloutdiv[4]} {u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_sirv_hclkgen_regs/plloutdiv[5]}]
set missing {}
set sdc {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/ChipContest-ppa-tools-20261103-03/tools/ppa/xu_full_soc.sdc}

foreach mode {envelope reset_bypass divider} {
  for {set divisor 0} {$divisor < 64} {incr divisor} {
    set XU_CLOCK_MODE $mode
    set XU_PLL_DIV $divisor
    set clocks {}; set cases {}; set generated {}
    source $sdc
    if {[dict size $clocks] != 3} { error "primary clocks missing" }
    set expected [expr {$mode eq "envelope" ? 0 : 8}]
    if {[dict size $cases] != $expected} { error "unexpected case-analysis scope" }
    if {$mode eq "divider"} {
      set edges [lindex $generated [expr {[lsearch -exact $generated -edges]+1}]]
      if {$edges ne [list 1 2 [expr {4*($divisor+1)+1}]]} { error "wrong pulse edges" }
    }
  }
}
set XU_CLOCK_MODE envelope
set missing [lindex $pins 1]
if {![catch {source $sdc} message] || ![string match {*expected one pin*} $message]} {
  error "missing clock pin did not fail closed"
}
set f [open {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/ChipContest-ppa-tools-20261103-03/tools/ppa/xu_full_soc_clock_review.tcl}]
set review [read $f]; close $f
if {![info complete $review]} { error "review Tcl is incomplete" }
puts "XU_SDC_MOCK_PASS 192_mode_divisor_combinations; missing_pin_rejected; review_Tcl_complete"
