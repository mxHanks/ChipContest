# Same mapped design / libraries. Original and revised contract in one process.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
set failed [catch {
  source $::env(XU_ECO_CONFIG)
  set ::eco_out [pwd]
  set ::eco_required_report_names {}
  foreach {path digest} $::eco_bindings {eco_sha $path $digest}
  set_host_options -max_cores 8
  eco_capture host-options.rpt {report_host_usage -verbose}
  foreach topic {set_input_delay remove_input_delay} {
    eco_capture manual-${topic}.rpt [list man $topic]
  }
  eco_load_pt $::eco_mapped
  set before_clocks [eco_clocks]
  eco_capture original-coverage.rpt {report_analysis_coverage -status_details {met untested violated}}
  eco_capture original-clocks.rpt {report_clock -attributes}
  eco_capture original-constraints.rpt {report_constraint -all_violators -verbose -significant_digits 8}
  eco_capture original-ports.rpt {report_port -input_delay}
  source $::lf_contract_overlay
  update_timing -full
  eco_assert_clocks $before_clocks
  eco_reports revised
  eco_capture revised-coverage-all.rpt {report_analysis_coverage -status_details {met untested violated}}
  eco_capture revised-ports.rpt {report_port -input_delay}
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
      set command [list report_timing -from [get_ports $port] -to [get_pins $pin] -delay_type $delay -slack_lesser_than 1000000000 -max_paths 4 -nworst 4 -path_type full_clock_expanded -significant_digits 8]
      if {$i >= 2} {set command [list report_timing -rise_from [get_ports $port] -to [get_pins $pin] -delay_type $delay -slack_lesser_than 1000000000 -max_paths 4 -nworst 4 -path_type full_clock_expanded -significant_digits 8]}
      eco_capture revised-target-${i}-${delay}.rpt $command
    }
    incr i
  }
  write_sdc revised-export.sdc
  eco_finish LF_CONTRACT_COLLECTION_COMPLETE.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
