if {[catch {
set_app_var link_path [list * {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db}]
read_verilog {/home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-score-resume-20261103/terminal122/full-soc-timing-combined-20261105-116/mapped.v}
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
set xu_unknown [open unknown-queries.tsv w]
xu_row $xu_unknown {scope field status detail}
set xu_collections [open collection-observations.tsv w]
xu_row $xu_collections {scope attribute count status names}
proc xu_names {value} {
 if {[sizeof_collection $value]==0} {return {}}
 return [get_object_name $value]
}
proc xu_collection {object attribute value} {
 global xu_collections
 set n [sizeof_collection $value]
 set names [xu_names $value]
 set status NONEMPTY
 if {$n==0} {set status EMPTY_COLLECTION}
 xu_row $xu_collections [list [get_object_name $object] $attribute $n $status $names]
 return $names
}
proc xu_nets {pin} {
 # Native pin.net is a collection. Literal constants may have no net object;
 # preserve emptiness rather than call get_nets on an unmatched selection.
 set ns [get_attribute -quiet $pin net]
 xu_collection $pin net $ns
 return $ns
}
proc xu_attr {object attribute collection} {
 global xu_unknown
 if {[catch {get_attribute -quiet $object $attribute} value]} {
  xu_row $xu_unknown [list [get_object_name $object] $attribute QUERY_ERROR $value]
  return QUERY_ERROR
 }
 if {$collection} {
  if {[catch {xu_collection $object $attribute $value} names]} {
   xu_row $xu_unknown [list [get_object_name $object] $attribute COLLECTION_NAME_ERROR $names]
   return COLLECTION_NAME_ERROR
  }
  return $names
 }
 if {$value eq {} && [regexp {^(max|min)_(rise|fall)_(arrival|slack)$} $attribute]} {
  xu_row $xu_unknown [list [get_object_name $object] $attribute ABSENT_NATIVE_ATTRIBUTE NOT_INFERRED]
  return ABSENT_NATIVE_ATTRIBUTE
 }
 return $value
}
proc xu_capture {name command} {
 global xu_unknown
 if {[catch {redirect -file $name {uplevel #0 $command}} message]} {
  xu_row $xu_unknown [list $name command QUERY_ERROR $message]
  set f [open ${name}.unavailable.txt w]; puts $f $message; close $f
 }
}
proc xu_pin {name} {
 set p [get_pins -quiet $name]
 if {[sizeof_collection $p]!=1 || [get_object_name $p] ne $name} {error "exact pin identity missing: $name"}
 return $p
}
proc xu_arcs {f owner arcs fromfield tofield attributes} {
 set index 0
 foreach_in_collection arc $arcs {
  set values [list $owner $index]; incr index
  foreach field $attributes {
   set collection [expr {$field eq $fromfield || $field eq $tofield}]
   lappend values [xu_attr $arc $field $collection]
  }
  xu_row $f $values
 }
}
proc xu_connections {f tag pin} {
 set ns [xu_nets $pin]
 foreach_in_collection net $ns {
  foreach_in_collection object [all_connected -leaf $net] {
   xu_row $f [list $tag [get_object_name $pin] [get_object_name $net] [get_object_name $object] [get_attribute $object object_class] [get_attribute $object direction]]
  }
 }
}
proc xu_fanin {pin} {
 puts [xu_names [all_fanin -flat -startpoints_only -to $pin]]
}
proc xu_structural_consumers {f tag start} {
 # Structural all_connected traversal; never stops at timing-disabled arcs.
 # Sequential cells terminate the trace; every combination output is followed.
 set front [list [get_object_name $start]]; set visited [dict create]; set count 0
 while {[llength $front]>0} {
  set next {}
  foreach name $front {
   if {[dict exists $visited $name]} {continue}
   dict set visited $name 1
   incr count
   if {$count>4096} {error {bounded reset consumer traversal exceeded4096 outputs}}
   set p [xu_pin $name]
   foreach_in_collection net [xu_nets $p] {
    foreach_in_collection object [all_connected -leaf $net] {
     set on [get_object_name $object]; set class [get_attribute $object object_class]
     set direction [get_attribute $object direction]
     if {$on eq $name} {continue}
     if {$class eq "port"} {xu_row $f [list $tag $name [get_object_name $net] $on $class $direction PORT_ENDPOINT]; continue}
     if {$class ne "pin" || $direction ne "in"} {error {unexpected reset Q leaf connection}}
     set c [get_cells -of_objects $object]
     if {[sizeof_collection $c]!=1 || [get_attribute $c is_hierarchical]} {error {reset Q consumer is not exact leaf}}
     set sequential [get_attribute $c is_sequential]
     if {![string is boolean -strict $sequential]} {error {reset Q consumer sequential classification unknown}}
     xu_row $f [list $tag $name [get_object_name $net] $on [get_attribute $c ref_name] $direction $sequential]
     if {!$sequential} {
      foreach_in_collection op [get_pins -of_objects $c -filter {direction == out}] {lappend next [get_object_name $op]}
     }
    }
   }
  }
  set front $next
 }
}
redirect -file coverage-initial.rpt {report_analysis_coverage -status_details untested}
redirect -file check-timing-initial.rpt {check_timing -verbose}
redirect -file clocks.rpt {report_clock -attributes}
redirect -file exceptions-initial.rpt {report_exceptions}
redirect -file case-initial.rpt {report_case_analysis -all}
xu_capture period-all-status.rpt {report_analysis_coverage -check_type min_period -status_details {met violated untested}}
set mf [open macro-mode-pins.tsv w]
xu_row $mf {macro pin constant_value user_case_value clocks nets}
set af [open macro-clock-arcs.tsv w]
xu_row $af [list owner index from_pin to_pin sense when sdf_cond is_disabled is_user_disabled is_db_inherited_disabled delay_min delay_max delay_min_rise delay_max_rise delay_min_fall delay_max_fall]
set lf [open macro-lib-clock-arcs.tsv w]
xu_row $lf [list owner index from_lib_pin to_lib_pin sense when sdf_cond is_disabled is_user_disabled]
set seenlibs [dict create]
set macrocount 0
foreach_in_collection c $xu_all_macros {
 incr macrocount
 set name [get_object_name $c]
 foreach pinname {RET1N EMA[2] EMA[1] EMA[0] EMAW[1] EMAW[0] CEN CLK} {
  set p [xu_pin ${name}/$pinname]
  if {[get_attribute $p direction] ne "in"} {error {macro mode/clock pin direction differs}}
  xu_row $mf [list $name $pinname [xu_attr $p constant_value 0] [xu_attr $p user_case_value 0] [xu_attr $p clocks 1] [xu_names [xu_nets $p]]]
 }
 set clk [xu_pin ${name}/CLK]
 set arcs [get_timing_arcs -from $clk -to $clk]
 if {[sizeof_collection $arcs]<32} {xu_row $xu_unknown [list $name CLK_SELF_ARCS COUNT_BELOW32 [sizeof_collection $arcs]]}
 xu_arcs $af $name $arcs from_pin to_pin [list from_pin to_pin sense when sdf_cond is_disabled is_user_disabled is_db_inherited_disabled delay_min delay_max delay_min_rise delay_max_rise delay_min_fall delay_max_fall]
 set lc [get_lib_cells -of_objects $c]
 if {[sizeof_collection $lc]!=1} {error {macro actual library cell missing/ambiguous}}
 set ln [get_object_name $lc]
 if {![dict exists $seenlibs $ln]} {
  dict set seenlibs $ln 1
  set lp [get_lib_pins -quiet ${ln}/CLK]
  if {[sizeof_collection $lp]!=1} {error {macro actual library CLK missing}}
  set arcs [get_lib_timing_arcs -from $lp -to $lp]
  xu_arcs $lf $ln $arcs from_lib_pin to_lib_pin [list from_lib_pin to_lib_pin sense when sdf_cond is_disabled is_user_disabled]
 }
}
if {$macrocount!=336} {error {must visit exact336 actual macros}}
close $mf
close $af
close $lf
set pf [open reset-pin-properties.tsv w]
xu_row $pf {index pin attribute value}
set nf [open reset-leaf-connections.tsv w]
xu_row $nf {index pin net connected class direction}
set cf [open reset-q-consumers.tsv w]
xu_row $cf {index driver net consumer ref_or_class direction sequential_or_endpoint}
set rf [open reset-design-arcs.tsv w]
xu_row $rf [list owner index from_pin to_pin sense when sdf_cond is_disabled is_user_disabled is_db_inherited_disabled delay_min delay_max delay_min_rise delay_max_rise delay_min_fall delay_max_fall]
set rlf [open reset-lib-arcs.tsv w]
xu_row $rlf [list owner index from_lib_pin to_lib_pin sense when sdf_cond is_disabled is_user_disabled]
set tf [open reset-timing-paths.tsv w]
xu_row $tf {index source_kind check count worst_slack status}
set hf [get_ports -quiet {io_pads_aon_erst_n_i_ival}]
set wdog [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/wdog/AsyncResetRegVec_6_1/reg_0/q_reg/Q}]
if {[sizeof_collection $hf]!=1} {error {exact external reset port missing}}
xu_capture external-reset-port.rpt [list report_attribute -application $hf]
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DSNQV0_12TR40}} {error {exact116 reset endpoint identity differs}}
set actual_outputs [get_pins -of_objects $c -filter {direction == out}]
if {[sizeof_collection $actual_outputs]!=1 || [get_object_name $actual_outputs] ne {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/Q}} {error {same116 exact reset output pin differs}}
foreach pn {D CK Q SDN} {
 set p [xu_pin [format {%s/%s} {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg} $pn]]
 xu_row $pf [list 0 [get_object_name $p] {constant_value} [xu_attr $p {constant_value} 0]]
 xu_row $pf [list 0 [get_object_name $p] {case_value} [xu_attr $p {case_value} 0]]
 xu_row $pf [list 0 [get_object_name $p] {user_case_value} [xu_attr $p {user_case_value} 0]]
 xu_row $pf [list 0 [get_object_name $p] {clocks} [xu_attr $p {clocks} 1]]
 xu_row $pf [list 0 [get_object_name $p] {launch_clocks} [xu_attr $p {launch_clocks} 1]]
 xu_row $pf [list 0 [get_object_name $p] {constrained_launch_clocks} [xu_attr $p {constrained_launch_clocks} 1]]
 xu_row $pf [list 0 [get_object_name $p] {dynamic_clocks} [xu_attr $p {dynamic_clocks} 1]]
 xu_row $pf [list 0 [get_object_name $p] {is_async_pin} [xu_attr $p {is_async_pin} 0]]
 xu_row $pf [list 0 [get_object_name $p] {is_clock_pin} [xu_attr $p {is_clock_pin} 0]]
 xu_row $pf [list 0 [get_object_name $p] {max_rise_arrival} [xu_attr $p {max_rise_arrival} 0]]
 xu_row $pf [list 0 [get_object_name $p] {max_fall_arrival} [xu_attr $p {max_fall_arrival} 0]]
 xu_row $pf [list 0 [get_object_name $p] {min_rise_arrival} [xu_attr $p {min_rise_arrival} 0]]
 xu_row $pf [list 0 [get_object_name $p] {min_fall_arrival} [xu_attr $p {min_fall_arrival} 0]]
 xu_row $pf [list 0 [get_object_name $p] {max_rise_slack} [xu_attr $p {max_rise_slack} 0]]
 xu_row $pf [list 0 [get_object_name $p] {max_fall_slack} [xu_attr $p {max_fall_slack} 0]]
 xu_row $pf [list 0 [get_object_name $p] {min_rise_slack} [xu_attr $p {min_rise_slack} 0]]
 xu_row $pf [list 0 [get_object_name $p] {min_fall_slack} [xu_attr $p {min_fall_slack} 0]]
 xu_row $pf [list 0 [get_object_name $p] {disable_timing} [xu_attr $p {disable_timing} 0]]
 xu_connections $nf 0 $p
}
xu_structural_consumers $cf 0 [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/Q}]
xu_arcs $rf {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg} [get_timing_arcs -of_objects $c] from_pin to_pin [list from_pin to_pin sense when sdf_cond is_disabled is_user_disabled is_db_inherited_disabled delay_min delay_max delay_min_rise delay_max_rise delay_min_fall delay_max_fall]
xu_arcs $rlf {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg} [get_lib_timing_arcs -of_objects [get_lib_cells -of_objects $c]] from_lib_pin to_lib_pin [list from_lib_pin to_lib_pin sense when sdf_cond is_disabled is_user_disabled]
xu_capture reset-0-disabled.rpt [list report_disable_timing $c]
set p [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN}]
xu_capture reset-0-fanin.rpt [list xu_fanin $p]
puts {XU132_PATH_BEGIN hf_reset-0-recovery}
set paths [get_timing_paths -from $hf -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 0 HF_RESET recovery $n $slack $status]
xu_capture hf_reset-0-recovery.rpt [list report_timing -from $hf -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END hf_reset-0-recovery}
puts {XU132_PATH_BEGIN hf_reset-0-removal}
set paths [get_timing_paths -from $hf -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 0 HF_RESET removal $n $slack $status]
xu_capture hf_reset-0-removal.rpt [list report_timing -from $hf -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END hf_reset-0-removal}
puts {XU132_PATH_BEGIN any_endpoint_source-0-recovery}
set paths [get_timing_paths -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 0 ANY_ENDPOINT_SOURCE recovery $n $slack $status]
xu_capture any_endpoint_source-0-recovery.rpt [list report_timing -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END any_endpoint_source-0-recovery}
puts {XU132_PATH_BEGIN any_endpoint_source-0-removal}
set paths [get_timing_paths -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 0 ANY_ENDPOINT_SOURCE removal $n $slack $status]
xu_capture any_endpoint_source-0-removal.rpt [list report_timing -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END any_endpoint_source-0-removal}
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DSNQNV0_12TR40}} {error {exact116 reset endpoint identity differs}}
set actual_outputs [get_pins -of_objects $c -filter {direction == out}]
if {[sizeof_collection $actual_outputs]!=1 || [get_object_name $actual_outputs] ne {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/QN}} {error {same116 exact reset output pin differs}}
foreach pn {D CK QN SDN} {
 set p [xu_pin [format {%s/%s} {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg} $pn]]
 xu_row $pf [list 1 [get_object_name $p] {constant_value} [xu_attr $p {constant_value} 0]]
 xu_row $pf [list 1 [get_object_name $p] {case_value} [xu_attr $p {case_value} 0]]
 xu_row $pf [list 1 [get_object_name $p] {user_case_value} [xu_attr $p {user_case_value} 0]]
 xu_row $pf [list 1 [get_object_name $p] {clocks} [xu_attr $p {clocks} 1]]
 xu_row $pf [list 1 [get_object_name $p] {launch_clocks} [xu_attr $p {launch_clocks} 1]]
 xu_row $pf [list 1 [get_object_name $p] {constrained_launch_clocks} [xu_attr $p {constrained_launch_clocks} 1]]
 xu_row $pf [list 1 [get_object_name $p] {dynamic_clocks} [xu_attr $p {dynamic_clocks} 1]]
 xu_row $pf [list 1 [get_object_name $p] {is_async_pin} [xu_attr $p {is_async_pin} 0]]
 xu_row $pf [list 1 [get_object_name $p] {is_clock_pin} [xu_attr $p {is_clock_pin} 0]]
 xu_row $pf [list 1 [get_object_name $p] {max_rise_arrival} [xu_attr $p {max_rise_arrival} 0]]
 xu_row $pf [list 1 [get_object_name $p] {max_fall_arrival} [xu_attr $p {max_fall_arrival} 0]]
 xu_row $pf [list 1 [get_object_name $p] {min_rise_arrival} [xu_attr $p {min_rise_arrival} 0]]
 xu_row $pf [list 1 [get_object_name $p] {min_fall_arrival} [xu_attr $p {min_fall_arrival} 0]]
 xu_row $pf [list 1 [get_object_name $p] {max_rise_slack} [xu_attr $p {max_rise_slack} 0]]
 xu_row $pf [list 1 [get_object_name $p] {max_fall_slack} [xu_attr $p {max_fall_slack} 0]]
 xu_row $pf [list 1 [get_object_name $p] {min_rise_slack} [xu_attr $p {min_rise_slack} 0]]
 xu_row $pf [list 1 [get_object_name $p] {min_fall_slack} [xu_attr $p {min_fall_slack} 0]]
 xu_row $pf [list 1 [get_object_name $p] {disable_timing} [xu_attr $p {disable_timing} 0]]
 xu_connections $nf 1 $p
}
xu_arcs $rf {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg} [get_timing_arcs -of_objects $c] from_pin to_pin [list from_pin to_pin sense when sdf_cond is_disabled is_user_disabled is_db_inherited_disabled delay_min delay_max delay_min_rise delay_max_rise delay_min_fall delay_max_fall]
xu_arcs $rlf {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg} [get_lib_timing_arcs -of_objects [get_lib_cells -of_objects $c]] from_lib_pin to_lib_pin [list from_lib_pin to_lib_pin sense when sdf_cond is_disabled is_user_disabled]
xu_capture reset-1-disabled.rpt [list report_disable_timing $c]
set p [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN}]
xu_capture reset-1-fanin.rpt [list xu_fanin $p]
puts {XU132_PATH_BEGIN hf_reset-1-recovery}
set paths [get_timing_paths -from $hf -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 1 HF_RESET recovery $n $slack $status]
xu_capture hf_reset-1-recovery.rpt [list report_timing -from $hf -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END hf_reset-1-recovery}
puts {XU132_PATH_BEGIN hf_reset-1-removal}
set paths [get_timing_paths -from $hf -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 1 HF_RESET removal $n $slack $status]
xu_capture hf_reset-1-removal.rpt [list report_timing -from $hf -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END hf_reset-1-removal}
puts {XU132_PATH_BEGIN any_endpoint_source-1-recovery}
set paths [get_timing_paths -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 1 ANY_ENDPOINT_SOURCE recovery $n $slack $status]
xu_capture any_endpoint_source-1-recovery.rpt [list report_timing -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END any_endpoint_source-1-recovery}
puts {XU132_PATH_BEGIN any_endpoint_source-1-removal}
set paths [get_timing_paths -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 1 ANY_ENDPOINT_SOURCE removal $n $slack $status]
xu_capture any_endpoint_source-1-removal.rpt [list report_timing -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END any_endpoint_source-1-removal}
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DRNQV0_12TR40}} {error {exact116 reset endpoint identity differs}}
set actual_outputs [get_pins -of_objects $c -filter {direction == out}]
if {[sizeof_collection $actual_outputs]!=1 || [get_object_name $actual_outputs] ne {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/Q}} {error {same116 exact reset output pin differs}}
foreach pn {D CK Q RDN} {
 set p [xu_pin [format {%s/%s} {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg} $pn]]
 xu_row $pf [list 2 [get_object_name $p] {constant_value} [xu_attr $p {constant_value} 0]]
 xu_row $pf [list 2 [get_object_name $p] {case_value} [xu_attr $p {case_value} 0]]
 xu_row $pf [list 2 [get_object_name $p] {user_case_value} [xu_attr $p {user_case_value} 0]]
 xu_row $pf [list 2 [get_object_name $p] {clocks} [xu_attr $p {clocks} 1]]
 xu_row $pf [list 2 [get_object_name $p] {launch_clocks} [xu_attr $p {launch_clocks} 1]]
 xu_row $pf [list 2 [get_object_name $p] {constrained_launch_clocks} [xu_attr $p {constrained_launch_clocks} 1]]
 xu_row $pf [list 2 [get_object_name $p] {dynamic_clocks} [xu_attr $p {dynamic_clocks} 1]]
 xu_row $pf [list 2 [get_object_name $p] {is_async_pin} [xu_attr $p {is_async_pin} 0]]
 xu_row $pf [list 2 [get_object_name $p] {is_clock_pin} [xu_attr $p {is_clock_pin} 0]]
 xu_row $pf [list 2 [get_object_name $p] {max_rise_arrival} [xu_attr $p {max_rise_arrival} 0]]
 xu_row $pf [list 2 [get_object_name $p] {max_fall_arrival} [xu_attr $p {max_fall_arrival} 0]]
 xu_row $pf [list 2 [get_object_name $p] {min_rise_arrival} [xu_attr $p {min_rise_arrival} 0]]
 xu_row $pf [list 2 [get_object_name $p] {min_fall_arrival} [xu_attr $p {min_fall_arrival} 0]]
 xu_row $pf [list 2 [get_object_name $p] {max_rise_slack} [xu_attr $p {max_rise_slack} 0]]
 xu_row $pf [list 2 [get_object_name $p] {max_fall_slack} [xu_attr $p {max_fall_slack} 0]]
 xu_row $pf [list 2 [get_object_name $p] {min_rise_slack} [xu_attr $p {min_rise_slack} 0]]
 xu_row $pf [list 2 [get_object_name $p] {min_fall_slack} [xu_attr $p {min_fall_slack} 0]]
 xu_row $pf [list 2 [get_object_name $p] {disable_timing} [xu_attr $p {disable_timing} 0]]
 xu_connections $nf 2 $p
}
xu_arcs $rf {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg} [get_timing_arcs -of_objects $c] from_pin to_pin [list from_pin to_pin sense when sdf_cond is_disabled is_user_disabled is_db_inherited_disabled delay_min delay_max delay_min_rise delay_max_rise delay_min_fall delay_max_fall]
xu_arcs $rlf {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg} [get_lib_timing_arcs -of_objects [get_lib_cells -of_objects $c]] from_lib_pin to_lib_pin [list from_lib_pin to_lib_pin sense when sdf_cond is_disabled is_user_disabled]
xu_capture reset-2-disabled.rpt [list report_disable_timing $c]
set p [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}]
xu_capture reset-2-fanin.rpt [list xu_fanin $p]
puts {XU132_PATH_BEGIN hf_reset-2-recovery}
set paths [get_timing_paths -from $hf -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 2 HF_RESET recovery $n $slack $status]
xu_capture hf_reset-2-recovery.rpt [list report_timing -from $hf -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END hf_reset-2-recovery}
puts {XU132_PATH_BEGIN hf_reset-2-removal}
set paths [get_timing_paths -from $hf -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 2 HF_RESET removal $n $slack $status]
xu_capture hf_reset-2-removal.rpt [list report_timing -from $hf -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END hf_reset-2-removal}
puts {XU132_PATH_BEGIN any_endpoint_source-2-recovery}
set paths [get_timing_paths -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 2 ANY_ENDPOINT_SOURCE recovery $n $slack $status]
xu_capture any_endpoint_source-2-recovery.rpt [list report_timing -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END any_endpoint_source-2-recovery}
puts {XU132_PATH_BEGIN any_endpoint_source-2-removal}
set paths [get_timing_paths -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 2 ANY_ENDPOINT_SOURCE removal $n $slack $status]
xu_capture any_endpoint_source-2-removal.rpt [list report_timing -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END any_endpoint_source-2-removal}
puts {XU132_PATH_BEGIN lf_watchdog-2-recovery}
set paths [get_timing_paths -from $wdog -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 2 LF_WATCHDOG recovery $n $slack $status]
xu_capture lf_watchdog-2-recovery.rpt [list report_timing -from $wdog -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END lf_watchdog-2-recovery}
puts {XU132_PATH_BEGIN lf_watchdog-2-removal}
set paths [get_timing_paths -from $wdog -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 2 LF_WATCHDOG removal $n $slack $status]
xu_capture lf_watchdog-2-removal.rpt [list report_timing -from $wdog -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END lf_watchdog-2-removal}
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DRNQV0_12TR40}} {error {exact116 reset endpoint identity differs}}
set actual_outputs [get_pins -of_objects $c -filter {direction == out}]
if {[sizeof_collection $actual_outputs]!=1 || [get_object_name $actual_outputs] ne {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/Q}} {error {same116 exact reset output pin differs}}
foreach pn {D CK Q RDN} {
 set p [xu_pin [format {%s/%s} {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg} $pn]]
 xu_row $pf [list 3 [get_object_name $p] {constant_value} [xu_attr $p {constant_value} 0]]
 xu_row $pf [list 3 [get_object_name $p] {case_value} [xu_attr $p {case_value} 0]]
 xu_row $pf [list 3 [get_object_name $p] {user_case_value} [xu_attr $p {user_case_value} 0]]
 xu_row $pf [list 3 [get_object_name $p] {clocks} [xu_attr $p {clocks} 1]]
 xu_row $pf [list 3 [get_object_name $p] {launch_clocks} [xu_attr $p {launch_clocks} 1]]
 xu_row $pf [list 3 [get_object_name $p] {constrained_launch_clocks} [xu_attr $p {constrained_launch_clocks} 1]]
 xu_row $pf [list 3 [get_object_name $p] {dynamic_clocks} [xu_attr $p {dynamic_clocks} 1]]
 xu_row $pf [list 3 [get_object_name $p] {is_async_pin} [xu_attr $p {is_async_pin} 0]]
 xu_row $pf [list 3 [get_object_name $p] {is_clock_pin} [xu_attr $p {is_clock_pin} 0]]
 xu_row $pf [list 3 [get_object_name $p] {max_rise_arrival} [xu_attr $p {max_rise_arrival} 0]]
 xu_row $pf [list 3 [get_object_name $p] {max_fall_arrival} [xu_attr $p {max_fall_arrival} 0]]
 xu_row $pf [list 3 [get_object_name $p] {min_rise_arrival} [xu_attr $p {min_rise_arrival} 0]]
 xu_row $pf [list 3 [get_object_name $p] {min_fall_arrival} [xu_attr $p {min_fall_arrival} 0]]
 xu_row $pf [list 3 [get_object_name $p] {max_rise_slack} [xu_attr $p {max_rise_slack} 0]]
 xu_row $pf [list 3 [get_object_name $p] {max_fall_slack} [xu_attr $p {max_fall_slack} 0]]
 xu_row $pf [list 3 [get_object_name $p] {min_rise_slack} [xu_attr $p {min_rise_slack} 0]]
 xu_row $pf [list 3 [get_object_name $p] {min_fall_slack} [xu_attr $p {min_fall_slack} 0]]
 xu_row $pf [list 3 [get_object_name $p] {disable_timing} [xu_attr $p {disable_timing} 0]]
 xu_connections $nf 3 $p
}
xu_arcs $rf {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg} [get_timing_arcs -of_objects $c] from_pin to_pin [list from_pin to_pin sense when sdf_cond is_disabled is_user_disabled is_db_inherited_disabled delay_min delay_max delay_min_rise delay_max_rise delay_min_fall delay_max_fall]
xu_arcs $rlf {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg} [get_lib_timing_arcs -of_objects [get_lib_cells -of_objects $c]] from_lib_pin to_lib_pin [list from_lib_pin to_lib_pin sense when sdf_cond is_disabled is_user_disabled]
xu_capture reset-3-disabled.rpt [list report_disable_timing $c]
set p [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}]
xu_capture reset-3-fanin.rpt [list xu_fanin $p]
puts {XU132_PATH_BEGIN hf_reset-3-recovery}
set paths [get_timing_paths -from $hf -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 3 HF_RESET recovery $n $slack $status]
xu_capture hf_reset-3-recovery.rpt [list report_timing -from $hf -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END hf_reset-3-recovery}
puts {XU132_PATH_BEGIN hf_reset-3-removal}
set paths [get_timing_paths -from $hf -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 3 HF_RESET removal $n $slack $status]
xu_capture hf_reset-3-removal.rpt [list report_timing -from $hf -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END hf_reset-3-removal}
puts {XU132_PATH_BEGIN any_endpoint_source-3-recovery}
set paths [get_timing_paths -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 3 ANY_ENDPOINT_SOURCE recovery $n $slack $status]
xu_capture any_endpoint_source-3-recovery.rpt [list report_timing -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END any_endpoint_source-3-recovery}
puts {XU132_PATH_BEGIN any_endpoint_source-3-removal}
set paths [get_timing_paths -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 3 ANY_ENDPOINT_SOURCE removal $n $slack $status]
xu_capture any_endpoint_source-3-removal.rpt [list report_timing -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END any_endpoint_source-3-removal}
puts {XU132_PATH_BEGIN lf_watchdog-3-recovery}
set paths [get_timing_paths -from $wdog -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 3 LF_WATCHDOG recovery $n $slack $status]
xu_capture lf_watchdog-3-recovery.rpt [list report_timing -from $wdog -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END lf_watchdog-3-recovery}
puts {XU132_PATH_BEGIN lf_watchdog-3-removal}
set paths [get_timing_paths -from $wdog -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 3 LF_WATCHDOG removal $n $slack $status]
xu_capture lf_watchdog-3-removal.rpt [list report_timing -from $wdog -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END lf_watchdog-3-removal}
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DRNQV0_12TR40}} {error {exact116 reset endpoint identity differs}}
set actual_outputs [get_pins -of_objects $c -filter {direction == out}]
if {[sizeof_collection $actual_outputs]!=1 || [get_object_name $actual_outputs] ne {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/Q}} {error {same116 exact reset output pin differs}}
foreach pn {D CK Q RDN} {
 set p [xu_pin [format {%s/%s} {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg} $pn]]
 xu_row $pf [list 4 [get_object_name $p] {constant_value} [xu_attr $p {constant_value} 0]]
 xu_row $pf [list 4 [get_object_name $p] {case_value} [xu_attr $p {case_value} 0]]
 xu_row $pf [list 4 [get_object_name $p] {user_case_value} [xu_attr $p {user_case_value} 0]]
 xu_row $pf [list 4 [get_object_name $p] {clocks} [xu_attr $p {clocks} 1]]
 xu_row $pf [list 4 [get_object_name $p] {launch_clocks} [xu_attr $p {launch_clocks} 1]]
 xu_row $pf [list 4 [get_object_name $p] {constrained_launch_clocks} [xu_attr $p {constrained_launch_clocks} 1]]
 xu_row $pf [list 4 [get_object_name $p] {dynamic_clocks} [xu_attr $p {dynamic_clocks} 1]]
 xu_row $pf [list 4 [get_object_name $p] {is_async_pin} [xu_attr $p {is_async_pin} 0]]
 xu_row $pf [list 4 [get_object_name $p] {is_clock_pin} [xu_attr $p {is_clock_pin} 0]]
 xu_row $pf [list 4 [get_object_name $p] {max_rise_arrival} [xu_attr $p {max_rise_arrival} 0]]
 xu_row $pf [list 4 [get_object_name $p] {max_fall_arrival} [xu_attr $p {max_fall_arrival} 0]]
 xu_row $pf [list 4 [get_object_name $p] {min_rise_arrival} [xu_attr $p {min_rise_arrival} 0]]
 xu_row $pf [list 4 [get_object_name $p] {min_fall_arrival} [xu_attr $p {min_fall_arrival} 0]]
 xu_row $pf [list 4 [get_object_name $p] {max_rise_slack} [xu_attr $p {max_rise_slack} 0]]
 xu_row $pf [list 4 [get_object_name $p] {max_fall_slack} [xu_attr $p {max_fall_slack} 0]]
 xu_row $pf [list 4 [get_object_name $p] {min_rise_slack} [xu_attr $p {min_rise_slack} 0]]
 xu_row $pf [list 4 [get_object_name $p] {min_fall_slack} [xu_attr $p {min_fall_slack} 0]]
 xu_row $pf [list 4 [get_object_name $p] {disable_timing} [xu_attr $p {disable_timing} 0]]
 xu_connections $nf 4 $p
}
xu_structural_consumers $cf 4 [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/Q}]
xu_arcs $rf {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg} [get_timing_arcs -of_objects $c] from_pin to_pin [list from_pin to_pin sense when sdf_cond is_disabled is_user_disabled is_db_inherited_disabled delay_min delay_max delay_min_rise delay_max_rise delay_min_fall delay_max_fall]
xu_arcs $rlf {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg} [get_lib_timing_arcs -of_objects [get_lib_cells -of_objects $c]] from_lib_pin to_lib_pin [list from_lib_pin to_lib_pin sense when sdf_cond is_disabled is_user_disabled]
xu_capture reset-4-disabled.rpt [list report_disable_timing $c]
set p [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}]
xu_capture reset-4-fanin.rpt [list xu_fanin $p]
puts {XU132_PATH_BEGIN hf_reset-4-recovery}
set paths [get_timing_paths -from $hf -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 4 HF_RESET recovery $n $slack $status]
xu_capture hf_reset-4-recovery.rpt [list report_timing -from $hf -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END hf_reset-4-recovery}
puts {XU132_PATH_BEGIN hf_reset-4-removal}
set paths [get_timing_paths -from $hf -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 4 HF_RESET removal $n $slack $status]
xu_capture hf_reset-4-removal.rpt [list report_timing -from $hf -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END hf_reset-4-removal}
puts {XU132_PATH_BEGIN any_endpoint_source-4-recovery}
set paths [get_timing_paths -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 4 ANY_ENDPOINT_SOURCE recovery $n $slack $status]
xu_capture any_endpoint_source-4-recovery.rpt [list report_timing -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END any_endpoint_source-4-recovery}
puts {XU132_PATH_BEGIN any_endpoint_source-4-removal}
set paths [get_timing_paths -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 4 ANY_ENDPOINT_SOURCE removal $n $slack $status]
xu_capture any_endpoint_source-4-removal.rpt [list report_timing -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END any_endpoint_source-4-removal}
puts {XU132_PATH_BEGIN lf_watchdog-4-recovery}
set paths [get_timing_paths -from $wdog -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 4 LF_WATCHDOG recovery $n $slack $status]
xu_capture lf_watchdog-4-recovery.rpt [list report_timing -from $wdog -to $p -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END lf_watchdog-4-recovery}
puts {XU132_PATH_BEGIN lf_watchdog-4-removal}
set paths [get_timing_paths -from $wdog -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 1]
set n [sizeof_collection $paths]
set slack UNKNOWN
set status NO_PATH_UNKNOWN
if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}
xu_row $tf [list 4 LF_WATCHDOG removal $n $slack $status]
xu_capture lf_watchdog-4-removal.rpt [list report_timing -from $wdog -to $p -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
puts {XU132_PATH_END lf_watchdog-4-removal}
xu_capture stage-0-min.rpt [list report_timing -from [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/Q}] -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/D}] -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_capture stage-0-max.rpt [list report_timing -from [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/Q}] -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/D}] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_capture stage-1-min.rpt [list report_timing -from [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/Q}] -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/D}] -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_capture stage-1-max.rpt [list report_timing -from [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/Q}] -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/D}] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_capture stage-2-min.rpt [list report_timing -from [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/Q}] -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/D}] -delay_type min -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_capture stage-2-max.rpt [list report_timing -from [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/Q}] -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/D}] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
close $pf
close $nf
close $cf
close $rf
close $rlf
close $tf
set xu_report_original [get_app_var timing_report_unconstrained_paths]
set df [open report-display-policy.tsv w]
xu_row $df {field value}
xu_row $df [list original $xu_report_original]
set xu_display_rc [catch {
set_app_var timing_report_unconstrained_paths true
xu_capture unconstrained-hf-0-recovery.rpt [list report_timing -from $hf -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN}] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_capture unconstrained-hf-1-recovery.rpt [list report_timing -from $hf -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN}] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_capture unconstrained-hf-2-recovery.rpt [list report_timing -from $hf -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_capture unconstrained-hf-3-recovery.rpt [list report_timing -from $hf -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
xu_capture unconstrained-hf-4-recovery.rpt [list report_timing -from $hf -to [xu_pin {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded]
} xu_display_error]
set_app_var timing_report_unconstrained_paths $xu_report_original
set xu_restored [get_app_var timing_report_unconstrained_paths]
xu_row $df [list restored $xu_restored]
close $df
if {$xu_restored ne $xu_report_original} {error {report display value not restored}}
if {$xu_display_rc} {error $xu_display_error}
redirect -file coverage-final.rpt {report_analysis_coverage -status_details untested}
redirect -file exceptions-final.rpt {report_exceptions}
redirect -file case-final.rpt {report_case_analysis -all}
close $xu_unknown
close $xu_collections

} xu_error xu_options]} {
puts stderr "XU_FATAL: $xu_error"
if {[dict exists $xu_options -errorinfo]} {puts stderr [dict get $xu_options -errorinfo]}
exit 1
}
puts {XU_COVERAGE132_SAME116_READ_ONLY_DIAGNOSTIC_DONE_NOT_QUALIFIED}
exit 0
