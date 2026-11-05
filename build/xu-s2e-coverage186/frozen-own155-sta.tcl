if {[catch {
set_app_var link_path [list * {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db}]
read_verilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s2e-own-timing-repair-20261105-155/final/mapped.v}
if {![link_design xu_soc_ppa_top]} {error {PT link failed}}
set XU_CLOCK_MODE envelope
set XU_PLL_DIV 0
source {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s2e-ppa-campaign-20261104-89/ppa/constraints.sdc}
set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1
source {/storage2/2026contest/server4/s4_23usr/Desktop/xu-ts16.tcl}
# Exact post-elaboration macro groups; overlapping matches and missing/extra cells fail.
set xu_seen [dict create]
set xu_cells [get_cells -quiet -hierarchical -filter {full_name =~ u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_cpu_top/u_e203_srams/u_e203_itcm_ram/* && ref_name == RAMSP1024X16 && is_hierarchical == false}]
if {[sizeof_collection $xu_cells] != 32} {error {wrong macro count: itcm}}
foreach_in_collection xu_c $xu_cells {
  set xu_n [get_object_name $xu_c]
  if {[dict exists $xu_seen $xu_n]} {error "overlapping SRAM group: $xu_n"}
  dict set xu_seen $xu_n 1
  if {[get_attribute $xu_c ref_name] != {RAMSP1024X16}} {error "wrong SRAM reference: $xu_n"}
}
puts "XU_SRAM_GROUP itcm count=32 macro_ref=RAMSP1024X16 logical_bits=524288 physical_bits=524288 padding_bits=0"
set xu_cells [get_cells -quiet -hierarchical -filter {full_name =~ u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_cpu_top/u_e203_srams/u_e203_dtcm_ram/* && ref_name == RAMSP1024X16 && is_hierarchical == false}]
if {[sizeof_collection $xu_cells] != 32} {error {wrong macro count: dtcm}}
foreach_in_collection xu_c $xu_cells {
  set xu_n [get_object_name $xu_c]
  if {[dict exists $xu_seen $xu_n]} {error "overlapping SRAM group: $xu_n"}
  dict set xu_seen $xu_n 1
  if {[get_attribute $xu_c ref_name] != {RAMSP1024X16}} {error "wrong SRAM reference: $xu_n"}
}
puts "XU_SRAM_GROUP dtcm count=32 macro_ref=RAMSP1024X16 logical_bits=524288 physical_bits=524288 padding_bits=0"
set xu_cells [get_cells -quiet -hierarchical -filter {full_name =~ u_shared/storage/* && ref_name == RAMSP1024X16 && is_hierarchical == false}]
if {[sizeof_collection $xu_cells] != 256} {error {wrong macro count: shared}}
foreach_in_collection xu_c $xu_cells {
  set xu_n [get_object_name $xu_c]
  if {[dict exists $xu_seen $xu_n]} {error "overlapping SRAM group: $xu_n"}
  dict set xu_seen $xu_n 1
  if {[get_attribute $xu_c ref_name] != {RAMSP1024X16}} {error "wrong SRAM reference: $xu_n"}
}
puts "XU_SRAM_GROUP shared count=256 macro_ref=RAMSP1024X16 logical_bits=4194304 physical_bits=4194304 padding_bits=0"
set xu_cells [get_cells -quiet -hierarchical -filter {full_name =~ u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave/* && ref_name == RAMSP1024X16 && is_hierarchical == false}]
if {[sizeof_collection $xu_cells] != 16} {error {wrong macro count: accelerator_weights}}
foreach_in_collection xu_c $xu_cells {
  set xu_n [get_object_name $xu_c]
  if {[dict exists $xu_seen $xu_n]} {error "overlapping SRAM group: $xu_n"}
  dict set xu_seen $xu_n 1
  if {[get_attribute $xu_c ref_name] != {RAMSP1024X16}} {error "wrong SRAM reference: $xu_n"}
}
puts "XU_SRAM_GROUP accelerator_weights count=16 macro_ref=RAMSP1024X16 logical_bits=262144 physical_bits=262144 padding_bits=0"
# RAMSP is the explicit technology SRAM namespace; reject every extra leaf/reference.
set xu_allowed_refs [list {RAMSP1024X16}]
set xu_all_macros [get_cells -quiet -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}]
if {[sizeof_collection $xu_all_macros] != 336 || [dict size $xu_seen] != 336} {error {full-SoC SRAM total must be exactly 336}}
foreach_in_collection xu_c $xu_all_macros {
  if {[lsearch -exact $xu_allowed_refs [get_attribute $xu_c ref_name]] < 0} {error {unexpected SRAM reference}}
  if {![dict exists $xu_seen [get_object_name $xu_c]]} {error {ungrouped/unaccounted SRAM macro}}
}
if {[sizeof_collection [get_cells -quiet -hierarchical -filter {full_name == u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave && ref_name =~ accel_icb_slave*}]] != 1} {error {missing/wrong accelerator}}
if {[sizeof_collection [get_cells -quiet -hierarchical -filter {full_name == u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_cpu_top && ref_name =~ e203_cpu_top*}]] != 1} {error {missing/wrong cpu}}
if {[sizeof_collection [get_cells -quiet -hierarchical -filter {full_name == u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_sirv_ppi_fab && ref_name =~ sirv_icb1to16_bus*}]] != 1} {error {missing/wrong interconnect}}

set inv [get_lib_cells -quiet {scc40nll_vhsc40_rvt_ss_v0p99_125c_basic/CLKINV0_12TR40}]
if {[sizeof_collection $inv]!=1 || [get_attribute $inv dont_use] ne "false"} {error {fresh PT reset library permission differs}}
set f [open reset-library.tsv w]
puts $f "libcell\tdont_use\tlibpin\tdirection"
foreach_in_collection p [get_lib_pins -of_objects $inv] {puts $f [join [list [get_object_name $inv] [get_attribute $inv dont_use] [get_object_name $p] [get_attribute $p direction]] "\t"]}
close $f
redirect -file units.rpt {report_units}
redirect -file check-timing.rpt {check_timing -verbose}
redirect -file setup.rpt {report_timing -delay_type max -slack_lesser_than 1000000 -max_paths 100 -significant_digits 12}
redirect -file hold.rpt {report_timing -delay_type min -slack_lesser_than 1000000 -max_paths 100 -significant_digits 12}
redirect -file constraints.rpt {report_constraint -all_violators -verbose -significant_digits 12}
redirect -file exceptions.rpt {report_exceptions}
redirect -file analysis-coverage.rpt {report_analysis_coverage -status_details untested}
redirect -file clocks.rpt {report_clock -attributes}
set f [open timing-slack.tsv w]
puts $f "delay_type\tpath_count\tworst_slack"
foreach type {max min} {set paths [get_timing_paths -delay_type $type -slack_lesser_than 1000000 -max_paths 1];if {[sizeof_collection $paths]!=1} {error {global timing path missing}};puts $f [join [list $type 1 [get_attribute $paths slack]] "\t"]}
close $f
set f [open reset-paths.tsv w]
puts $f "index\tsource_kind\tcheck\tcount\tworst_slack\tstatus"
set src [get_ports -quiet {io_pads_aon_erst_n_i_ival}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 0 HF_RESET recovery $n $slack $status] "\t"]
redirect -file reset-0-hf_reset-recovery.rpt {report_timing -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_ports -quiet {io_pads_aon_erst_n_i_ival}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 0 HF_RESET removal $n $slack $status] "\t"]
redirect -file reset-0-hf_reset-removal.rpt {report_timing -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_ports -quiet {io_pads_aon_erst_n_i_ival}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 1 HF_RESET recovery $n $slack $status] "\t"]
redirect -file reset-1-hf_reset-recovery.rpt {report_timing -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_ports -quiet {io_pads_aon_erst_n_i_ival}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 1 HF_RESET removal $n $slack $status] "\t"]
redirect -file reset-1-hf_reset-removal.rpt {report_timing -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_ports -quiet {io_pads_aon_erst_n_i_ival}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 2 HF_RESET recovery $n $slack $status] "\t"]
redirect -file reset-2-hf_reset-recovery.rpt {report_timing -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_ports -quiet {io_pads_aon_erst_n_i_ival}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 2 HF_RESET removal $n $slack $status] "\t"]
redirect -file reset-2-hf_reset-removal.rpt {report_timing -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/wdog/AsyncResetRegVec_6_1/reg_0/q_reg/Q}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 2 LF_WATCHDOG recovery $n $slack $status] "\t"]
redirect -file reset-2-lf_watchdog-recovery.rpt {report_timing -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/wdog/AsyncResetRegVec_6_1/reg_0/q_reg/Q}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 2 LF_WATCHDOG removal $n $slack $status] "\t"]
redirect -file reset-2-lf_watchdog-removal.rpt {report_timing -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_ports -quiet {io_pads_aon_erst_n_i_ival}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 3 HF_RESET recovery $n $slack $status] "\t"]
redirect -file reset-3-hf_reset-recovery.rpt {report_timing -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_ports -quiet {io_pads_aon_erst_n_i_ival}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 3 HF_RESET removal $n $slack $status] "\t"]
redirect -file reset-3-hf_reset-removal.rpt {report_timing -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/wdog/AsyncResetRegVec_6_1/reg_0/q_reg/Q}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 3 LF_WATCHDOG recovery $n $slack $status] "\t"]
redirect -file reset-3-lf_watchdog-recovery.rpt {report_timing -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/wdog/AsyncResetRegVec_6_1/reg_0/q_reg/Q}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 3 LF_WATCHDOG removal $n $slack $status] "\t"]
redirect -file reset-3-lf_watchdog-removal.rpt {report_timing -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_ports -quiet {io_pads_aon_erst_n_i_ival}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 4 HF_RESET recovery $n $slack $status] "\t"]
redirect -file reset-4-hf_reset-recovery.rpt {report_timing -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_ports -quiet {io_pads_aon_erst_n_i_ival}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 4 HF_RESET removal $n $slack $status] "\t"]
redirect -file reset-4-hf_reset-removal.rpt {report_timing -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/wdog/AsyncResetRegVec_6_1/reg_0/q_reg/Q}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 4 LF_WATCHDOG recovery $n $slack $status] "\t"]
redirect -file reset-4-lf_watchdog-recovery.rpt {report_timing -from $src -to $dst -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
set src [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/wdog/AsyncResetRegVec_6_1/reg_0/q_reg/Q}]
set dst [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}]
if {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}
set p [get_timing_paths -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
puts $f [join [list 4 LF_WATCHDOG removal $n $slack $status] "\t"]
redirect -file reset-4-lf_watchdog-removal.rpt {report_timing -from $src -to $dst -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}
close $f

puts {XU_S2E_TIMING134_PT_DONE_NOT_QUALIFIED}
} xu_error]} {
  puts stderr "XU_FATAL: $xu_error"
  exit 1
}
exit 0
