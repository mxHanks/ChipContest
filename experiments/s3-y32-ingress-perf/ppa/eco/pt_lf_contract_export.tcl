# Bounded fresh-process validation of the exported v1 SDC and explicit paths.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
set failed [catch {
  source $::env(XU_ECO_CONFIG)
  set ::eco_out [pwd]; set ::eco_required_report_names {}
  foreach {path digest} $::eco_bindings {eco_sha $path $digest}
  eco_sha $::lf_contract_exported $::lf_contract_exported_sha
  set_host_options -max_cores 8
  eco_capture host-options.rpt {report_host_usage -verbose}
  eco_libraries pt
  read_verilog $::eco_mapped
  current_design xu_soc_sysbus32_ppa_top
  eco_require [link_design xu_soc_sysbus32_ppa_top] {PT link failed}
  source [file join $::eco_baseline source ppa hierarchy_contract.tcl]
  sysbus32_check_hierarchy
  read_sdc $::lf_contract_exported
  update_timing -full
  eco_capture exported-coverage.rpt {report_analysis_coverage -status_details {untested violated}}
  eco_capture exported-clocks.rpt {report_clock -attributes}
  eco_capture exported-ports.rpt {report_port -input_delay}
  eco_capture exported-all_violators.rpt {report_constraint -all_violators -verbose -significant_digits 8}
  set root u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper
  set targets [list \
    [list io_pads_bootrom_n_i_ival $root/bootrom_deglitch/T_8_reg/D] \
    [list io_pads_aon_pmu_dwakeup_n_i_ival $root/dwakeup_deglitch/T_8_reg/D] \
    [list io_pads_aon_erst_n_i_ival $root/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN] \
    [list io_pads_aon_erst_n_i_ival $root/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN] \
    [list io_pads_aon_erst_n_i_ival $root/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN] \
    [list io_pads_aon_erst_n_i_ival $root/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN] \
    [list io_pads_aon_erst_n_i_ival $root/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN]]
  set i 0
  foreach pair $targets {
    lassign $pair port pin
    eco_pin $pin
    foreach delay {min max} {
      set selector [list -from [get_ports $port]]
      if {$i >= 2} {set selector [list -rise_from [get_ports $port]]}
      set command [concat [list report_timing] $selector [list -to [get_pins $pin] -delay_type $delay -slack_lesser_than 1000000000 -max_paths 4 -nworst 4 -path_type full_clock_expanded -significant_digits 8]]
      eco_capture exported-target-${i}-${delay}.rpt $command
    }
    incr i
  }
  eco_finish LF_CONTRACT_EXPORT_COLLECTION_COMPLETE.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
