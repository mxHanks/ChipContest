if {[catch {
set_app_var link_path [list * {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db}]
read_verilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/full-soc-timing-combined-20261105-116/mapped.v}
if {![link_design xu_soc_ppa_top]} {error {PT link failed}}
set XU_CLOCK_MODE envelope
set XU_PLL_DIV 0
source {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/full-soc-pt-compatible-05/constraints.sdc}
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

proc xu_row {f values} {
 set clean {}
 foreach value $values {lappend clean [string map [list "\\" "\\\\" "\t" "\\t" "\r" "\\r" "\n" "\\n"] $value]}
 puts $f [join $clean "\t"]
 flush $f
}
proc xu_pin {name} {
 set p [get_pins -quiet $name]
 if {[sizeof_collection $p]!=1 || [get_object_name $p] ne $name} {error "exact pin identity missing: $name"}
 return $p
}
proc xu_arc_rows {f owner arcs} {
 set index 0
 foreach_in_collection arc $arcs {
  # Native timing_arc has no full_name. Only name the from/to pin collections.
  set from [get_attribute $arc from_pin]
  set to [get_attribute $arc to_pin]
  if {[sizeof_collection $from]!=1 || [sizeof_collection $to]!=1} {error {arc endpoints not exact}}
  set fn [get_object_name $from]; set tn [get_object_name $to]
  set scope [join [list $owner $index $fn $tn] {|}]
  set values [list $owner $index $fn $tn $scope]
  foreach field {sense when sdf_cond is_disabled is_user_disabled is_db_inherited_disabled} {
   lappend values [get_attribute $arc $field]
  }
  xu_row $f $values
  incr index
 }
}
redirect -file coverage-initial.rpt {report_analysis_coverage -status_details untested}
redirect -file exceptions-initial.rpt {report_exceptions}
redirect -file case-initial.rpt {report_case_analysis -all}
redirect -file clocks-initial.rpt {report_clock -attributes}
set hf [get_ports -quiet {io_pads_aon_erst_n_i_ival}]
if {[sizeof_collection $hf]!=1 || [get_object_name $hf] ne {io_pads_aon_erst_n_i_ival}} {error {exact HF reset port missing}}
set af [open reset-ck-async-arcs.tsv w]
xu_row $af {owner index from_pin to_pin scope sense when sdf_cond is_disabled is_user_disabled is_db_inherited_disabled}
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DSNQV0_12TR40}} {error {same116 cell differs}}
set outputs [get_pins -of_objects $c -filter {direction == out}]
if {[sizeof_collection $outputs]!=1 || [get_object_name $outputs] ne {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/Q}} {error {same116 output differs}}
xu_arc_rows $af {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg} [get_timing_arcs -from [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/CK}] -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN}]]
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DSNQNV0_12TR40}} {error {same116 cell differs}}
set outputs [get_pins -of_objects $c -filter {direction == out}]
if {[sizeof_collection $outputs]!=1 || [get_object_name $outputs] ne {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/QN}} {error {same116 output differs}}
xu_arc_rows $af {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg} [get_timing_arcs -from [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/CK}] -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN}]]
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DRNQV0_12TR40}} {error {same116 cell differs}}
set outputs [get_pins -of_objects $c -filter {direction == out}]
if {[sizeof_collection $outputs]!=1 || [get_object_name $outputs] ne {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/Q}} {error {same116 output differs}}
xu_arc_rows $af {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg} [get_timing_arcs -from [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/CK}] -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}]]
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DRNQV0_12TR40}} {error {same116 cell differs}}
set outputs [get_pins -of_objects $c -filter {direction == out}]
if {[sizeof_collection $outputs]!=1 || [get_object_name $outputs] ne {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/Q}} {error {same116 output differs}}
xu_arc_rows $af {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg} [get_timing_arcs -from [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/CK}] -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}]]
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DRNQV0_12TR40}} {error {same116 cell differs}}
set outputs [get_pins -of_objects $c -filter {direction == out}]
if {[sizeof_collection $outputs]!=1 || [get_object_name $outputs] ne {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/Q}} {error {same116 output differs}}
xu_arc_rows $af {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg} [get_timing_arcs -from [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/CK}] -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}]]
close $af
set qf [open query-commands.tsv w]
xu_row $qf {index source_kind variant report command native_invocation}
set df [open report-display-policy.tsv w]
xu_row $df {field value}
set xu_report_original [get_app_var timing_report_unconstrained_paths]
xu_row $df [list original $xu_report_original]
set xu_display_rc [catch {
set_app_var timing_report_unconstrained_paths true
set xu_display_active [get_app_var timing_report_unconstrained_paths]
xu_row $df [list active $xu_display_active]
if {$xu_display_active ne "true"} {error {DISPLAY not true}}
set xu_to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN}]
puts {XU142_REPORT_BEGIN hf_reset-0-original132_filtered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_row $qf [list 0 HF_RESET original132_filtered {hf_reset-0-original132_filtered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded] $xu_command]
redirect -file {hf_reset-0-original132_filtered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-0-original132_filtered.rpt}
puts {XU142_REPORT_BEGIN hf_reset-0-matched_filtered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -exceptions all -slack_lesser_than 1000000]
xu_row $qf [list 0 HF_RESET matched_filtered {hf_reset-0-matched_filtered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -exceptions all -slack_lesser_than 1000000] $xu_command]
redirect -file {hf_reset-0-matched_filtered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-0-matched_filtered.rpt}
puts {XU142_REPORT_BEGIN hf_reset-0-unfiltered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -exceptions all]
xu_row $qf [list 0 HF_RESET unfiltered {hf_reset-0-unfiltered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -exceptions all] $xu_command]
redirect -file {hf_reset-0-unfiltered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-0-unfiltered.rpt}
set xu_to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN}]
puts {XU142_REPORT_BEGIN hf_reset-1-original132_filtered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_row $qf [list 1 HF_RESET original132_filtered {hf_reset-1-original132_filtered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded] $xu_command]
redirect -file {hf_reset-1-original132_filtered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-1-original132_filtered.rpt}
puts {XU142_REPORT_BEGIN hf_reset-1-matched_filtered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -exceptions all -slack_lesser_than 1000000]
xu_row $qf [list 1 HF_RESET matched_filtered {hf_reset-1-matched_filtered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -exceptions all -slack_lesser_than 1000000] $xu_command]
redirect -file {hf_reset-1-matched_filtered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-1-matched_filtered.rpt}
puts {XU142_REPORT_BEGIN hf_reset-1-unfiltered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -exceptions all]
xu_row $qf [list 1 HF_RESET unfiltered {hf_reset-1-unfiltered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -exceptions all] $xu_command]
redirect -file {hf_reset-1-unfiltered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-1-unfiltered.rpt}
set xu_to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}]
puts {XU142_REPORT_BEGIN hf_reset-2-original132_filtered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_row $qf [list 2 HF_RESET original132_filtered {hf_reset-2-original132_filtered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded] $xu_command]
redirect -file {hf_reset-2-original132_filtered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-2-original132_filtered.rpt}
puts {XU142_REPORT_BEGIN hf_reset-2-matched_filtered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -exceptions all -slack_lesser_than 1000000]
xu_row $qf [list 2 HF_RESET matched_filtered {hf_reset-2-matched_filtered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -exceptions all -slack_lesser_than 1000000] $xu_command]
redirect -file {hf_reset-2-matched_filtered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-2-matched_filtered.rpt}
puts {XU142_REPORT_BEGIN hf_reset-2-unfiltered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -exceptions all]
xu_row $qf [list 2 HF_RESET unfiltered {hf_reset-2-unfiltered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -exceptions all] $xu_command]
redirect -file {hf_reset-2-unfiltered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-2-unfiltered.rpt}
set xu_to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}]
puts {XU142_REPORT_BEGIN hf_reset-3-original132_filtered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_row $qf [list 3 HF_RESET original132_filtered {hf_reset-3-original132_filtered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded] $xu_command]
redirect -file {hf_reset-3-original132_filtered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-3-original132_filtered.rpt}
puts {XU142_REPORT_BEGIN hf_reset-3-matched_filtered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -exceptions all -slack_lesser_than 1000000]
xu_row $qf [list 3 HF_RESET matched_filtered {hf_reset-3-matched_filtered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -exceptions all -slack_lesser_than 1000000] $xu_command]
redirect -file {hf_reset-3-matched_filtered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-3-matched_filtered.rpt}
puts {XU142_REPORT_BEGIN hf_reset-3-unfiltered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -exceptions all]
xu_row $qf [list 3 HF_RESET unfiltered {hf_reset-3-unfiltered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -exceptions all] $xu_command]
redirect -file {hf_reset-3-unfiltered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-3-unfiltered.rpt}
set xu_to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}]
puts {XU142_REPORT_BEGIN hf_reset-4-original132_filtered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_row $qf [list 4 HF_RESET original132_filtered {hf_reset-4-original132_filtered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded] $xu_command]
redirect -file {hf_reset-4-original132_filtered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-4-original132_filtered.rpt}
puts {XU142_REPORT_BEGIN hf_reset-4-matched_filtered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -exceptions all -slack_lesser_than 1000000]
xu_row $qf [list 4 HF_RESET matched_filtered {hf_reset-4-matched_filtered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -exceptions all -slack_lesser_than 1000000] $xu_command]
redirect -file {hf_reset-4-matched_filtered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-4-matched_filtered.rpt}
puts {XU142_REPORT_BEGIN hf_reset-4-unfiltered.rpt}
set xu_command [list report_timing -from $hf -to $xu_to -delay_type max -exceptions all]
xu_row $qf [list 4 HF_RESET unfiltered {hf_reset-4-unfiltered.rpt} [list report_timing -from [get_object_name $hf] -to [get_object_name $xu_to] -delay_type max -exceptions all] $xu_command]
redirect -file {hf_reset-4-unfiltered.rpt} $xu_command
puts {XU142_REPORT_END hf_reset-4-unfiltered.rpt}
set xu_to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN}]
puts {XU142_REPORT_BEGIN any_endpoint_source-0-original132_filtered.rpt}
set xu_command [list report_timing -to $xu_to -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_row $qf [list 0 ANY_ENDPOINT_SOURCE original132_filtered {any_endpoint_source-0-original132_filtered.rpt} [list report_timing -to [get_object_name $xu_to] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded] $xu_command]
redirect -file {any_endpoint_source-0-original132_filtered.rpt} $xu_command
puts {XU142_REPORT_END any_endpoint_source-0-original132_filtered.rpt}
puts {XU142_REPORT_BEGIN any_endpoint_source-0-matched_filtered.rpt}
set xu_command [list report_timing -to $xu_to -delay_type max -exceptions all -slack_lesser_than 1000000]
xu_row $qf [list 0 ANY_ENDPOINT_SOURCE matched_filtered {any_endpoint_source-0-matched_filtered.rpt} [list report_timing -to [get_object_name $xu_to] -delay_type max -exceptions all -slack_lesser_than 1000000] $xu_command]
redirect -file {any_endpoint_source-0-matched_filtered.rpt} $xu_command
puts {XU142_REPORT_END any_endpoint_source-0-matched_filtered.rpt}
puts {XU142_REPORT_BEGIN any_endpoint_source-0-unfiltered.rpt}
set xu_command [list report_timing -to $xu_to -delay_type max -exceptions all]
xu_row $qf [list 0 ANY_ENDPOINT_SOURCE unfiltered {any_endpoint_source-0-unfiltered.rpt} [list report_timing -to [get_object_name $xu_to] -delay_type max -exceptions all] $xu_command]
redirect -file {any_endpoint_source-0-unfiltered.rpt} $xu_command
puts {XU142_REPORT_END any_endpoint_source-0-unfiltered.rpt}
set xu_to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN}]
puts {XU142_REPORT_BEGIN any_endpoint_source-1-original132_filtered.rpt}
set xu_command [list report_timing -to $xu_to -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_row $qf [list 1 ANY_ENDPOINT_SOURCE original132_filtered {any_endpoint_source-1-original132_filtered.rpt} [list report_timing -to [get_object_name $xu_to] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded] $xu_command]
redirect -file {any_endpoint_source-1-original132_filtered.rpt} $xu_command
puts {XU142_REPORT_END any_endpoint_source-1-original132_filtered.rpt}
puts {XU142_REPORT_BEGIN any_endpoint_source-1-matched_filtered.rpt}
set xu_command [list report_timing -to $xu_to -delay_type max -exceptions all -slack_lesser_than 1000000]
xu_row $qf [list 1 ANY_ENDPOINT_SOURCE matched_filtered {any_endpoint_source-1-matched_filtered.rpt} [list report_timing -to [get_object_name $xu_to] -delay_type max -exceptions all -slack_lesser_than 1000000] $xu_command]
redirect -file {any_endpoint_source-1-matched_filtered.rpt} $xu_command
puts {XU142_REPORT_END any_endpoint_source-1-matched_filtered.rpt}
puts {XU142_REPORT_BEGIN any_endpoint_source-1-unfiltered.rpt}
set xu_command [list report_timing -to $xu_to -delay_type max -exceptions all]
xu_row $qf [list 1 ANY_ENDPOINT_SOURCE unfiltered {any_endpoint_source-1-unfiltered.rpt} [list report_timing -to [get_object_name $xu_to] -delay_type max -exceptions all] $xu_command]
redirect -file {any_endpoint_source-1-unfiltered.rpt} $xu_command
puts {XU142_REPORT_END any_endpoint_source-1-unfiltered.rpt}
} xu_display_error xu_display_options]
set_app_var timing_report_unconstrained_paths $xu_report_original
set xu_restored [get_app_var timing_report_unconstrained_paths]
xu_row $df [list restored $xu_restored]
close $df
close $qf
if {$xu_restored ne $xu_report_original} {error {DISPLAY not restored}}
if {$xu_display_rc} {return -options $xu_display_options $xu_display_error}
redirect -file coverage-final.rpt {report_analysis_coverage -status_details untested}
redirect -file exceptions-final.rpt {report_exceptions}
redirect -file case-final.rpt {report_case_analysis -all}
redirect -file clocks-final.rpt {report_clock -attributes}

} xu_error xu_options]} {
puts stderr "XU_FATAL: $xu_error"
if {[dict exists $xu_options -errorinfo]} {puts stderr [dict get $xu_options -errorinfo]}
exit 1
}
puts {XU_RDC142_SAME116_READ_ONLY_VISIBILITY_DONE_NOT_QUALIFIED}
exit 0
