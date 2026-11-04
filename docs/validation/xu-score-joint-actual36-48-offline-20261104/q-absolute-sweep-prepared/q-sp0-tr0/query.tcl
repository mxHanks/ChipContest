if {[catch {
set xu_q_self_script [file normalize [info script]]]
set xu_q_frozen_inputs [list [list {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db} {f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723}] [list {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db} {c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f}] [list {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/pt-joint-state-condition-20261103-48/single-macro.v} {c071aac630721664423ee26571e3b22b284b87259d63aa89ac7110af149cb958}] [list {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/pt-joint-state-condition-20261103-48/query.tcl} {cd386f439e515adb2e6e24b40e483534cc61496621c93b489b4086fae0fbf169}] [list {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/pt-joint-state-condition-20261103-48/measured-joint-projection.json} {ed32512cb0b5acb91f7ad6af6766da240577da9a7e805789d16e44d01ebf104d}]]

proc xu_q_sha {path} {
  if {![file isfile $path]} {error "missing regular input $path"}
  set answer [exec /usr/bin/sha256sum -- $path]
  if {![regexp {^([0-9a-f]{64})[ \t]} $answer -> sha]} {error {invalid sha256sum output}}
  return [list [file size $path] $sha]
}
proc xu_q_snapshot {phase} {
  set f [open "input-sha-$phase.tsv" {WRONLY CREAT EXCL}]
  puts $f "phase\tpath\tbytes\tsha256\texpected_sha256"
  set result [list]
  foreach spec [concat $::xu_q_frozen_inputs [list [list $::xu_q_self_script {}]]] {
    lassign $spec path expected
    lassign [xu_q_sha $path] bytes sha
    puts $f [join [list $phase $path $bytes $sha $expected] "\t"]
    if {$expected ne {} && $sha ne $expected} {close $f;error "frozen input SHA differs $path"}
    lappend result [list $path $bytes $sha]
  }
  close $f
  return $result
}
proc xu_q_activity {phase} {
  set f [open "all-macro-pin-activity-$phase.tsv" {WRONLY CREAT EXCL}]
  puts $f "case\tphase\tpin\tstatic_probability_raw\ttoggle_glitch_raw"
  set pins [get_pins -quiet -of_objects [get_cells m]]
  if {[sizeof_collection $pins] != 67} {error {fixture does not have 67 signal pins}}
  foreach_in_collection pin $pins {
    set name [get_object_name $pin]
    set sp [get_switching_activity -static_probability $pin]
    set tr [get_switching_activity -toggle_rate -glitch_rate $pin]
    foreach value [list $name $sp $tr] {
      if {[regexp {[\t\r\n]} $value]} {error {TSV control in activity query}}
    }
    puts $f [join [list $::xu_q_case $phase $name $sp $tr] "\t"]
  }
  close $f
  redirect -file "coverage-$phase.rpt" {report_switching_activity -list_not_annotated}
}
proc xu_q_request {phase} {
  foreach name $::xu_q_targets {
    puts $::xu_q_request_f [join [list $::xu_q_case $phase $name $::xu_q_requested_sp $::xu_q_requested_tr HYPOTHETICAL_ABSOLUTE_Q_SIDE_EFFECT_ONLY] "\t"]
  }
}
set xu_q_before [xu_q_snapshot before]
set_app_var power_enable_analysis true
set_app_var power_analysis_mode averaged
set_app_var link_path [list * {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db}]
redirect -file version.rpt {puts $sh_product_version}
read_verilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/pt-joint-state-condition-20261103-48/single-macro.v}
if {![link_design {xu_joint_pt_top}]} {error {actual SRAM fixture link failed}}
if {[sizeof_collection [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}]] != 1} {error {fixture actual macro count differs}}
redirect -file units.rpt {report_units}
set xu_actual_lib_cell [get_object_name [get_lib_cells -of_objects [get_cells m]]]
if {$xu_actual_lib_cell ne {RAMSP1024X16_ss_0p99v_0p99v_125c/RAMSP1024X16}} {error {actual linked SRAM library cell differs}}
redirect -file actual-library-cell.rpt {puts $xu_actual_lib_cell;report_lib [lindex [split $xu_actual_lib_cell /] 0]}
set_input_transition 0.05 [all_inputs]
set_load 0.01 [all_outputs]
set xu_f [open conditional-queries.tsv {WRONLY CREAT EXCL}]
puts $xu_f "phase	arc_id	kind	pin	condition	direction	annotation_policy	raw_query"
proc xu_query {phase id kind pin condition direction policy} {
  if {$kind eq "leakage"} {set obj [get_cells -quiet m]} else {set obj [get_pins -quiet "m/$pin"]}
  if {[sizeof_collection $obj] != 1} {error {exact fixture object not found}}
  set command [list get_switching_activity]
  if {$kind eq "leakage"} {lappend command -state_condition $condition -static_probability} else {
    if {$condition ne "default"} {lappend command -state_condition $condition}
    lappend command -toggle_rate -glitch_rate
    if {$direction ne "both" && $condition ne "default"} {lappend command -$direction}
  }
  lappend command $obj
  set answer [eval $command]
  foreach item [list $phase $id $kind $pin $condition $direction $policy $answer] {if {[regexp {[	
]} $item]} {error {TSV control in query}}}
  puts $::xu_f [join [list $phase $id $kind $pin $condition $direction $policy $answer] "	"]
}
set_switching_activity -state_condition {!RET1N} -static_probability 0.4942748091603053435114504 [get_cells m]
set_switching_activity -state_condition {default} -static_probability 0.5057251908396946564885496 [get_cells m]
set_switching_activity -toggle_rate 0 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/A[0]}]
set_switching_activity -toggle_rate 0 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/A[1]}]
set_switching_activity -toggle_rate 0 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/A[2]}]
set_switching_activity -toggle_rate 0 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/A[3]}]
set_switching_activity -toggle_rate 0 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/A[4]}]
set_switching_activity -toggle_rate 0 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/A[5]}]
set_switching_activity -toggle_rate 0 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/A[6]}]
set_switching_activity -toggle_rate 0 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/A[7]}]
set_switching_activity -toggle_rate 0 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/A[8]}]
set_switching_activity -toggle_rate 0 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/A[9]}]
set_switching_activity -toggle_rate 5 -glitch_rate 0 -period 524 -rise_ratio 0.4 [get_pins {m/CEN}]
set_switching_activity -state_condition {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & !EMA[0]} -toggle_rate 7 -glitch_rate 0 -period 524 -rise_ratio 0.5714285714285714285714286 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & EMA[0]} -toggle_rate 7 -glitch_rate 0 -period 524 -rise_ratio 0.5714285714285714285714286 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & !EMA[0]} -toggle_rate 7 -glitch_rate 0 -period 524 -rise_ratio 0.5714285714285714285714286 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & EMA[0]} -toggle_rate 7 -glitch_rate 0 -period 524 -rise_ratio 0.5714285714285714285714286 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & !EMA[0]} -toggle_rate 7 -glitch_rate 0 -period 524 -rise_ratio 0.5714285714285714285714286 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & EMA[0]} -toggle_rate 7 -glitch_rate 0 -period 524 -rise_ratio 0.5714285714285714285714286 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & !EMA[0]} -toggle_rate 7 -glitch_rate 0 -period 524 -rise_ratio 0.5714285714285714285714286 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & EMA[0]} -toggle_rate 7 -glitch_rate 0 -period 524 -rise_ratio 0.5714285714285714285714286 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/CLK}]
set_switching_activity -state_condition {!RET1N} -toggle_rate 255 -glitch_rate 0 -period 524 -rise_ratio 0.5019607843137254901960784 [get_pins {m/CLK}]
set_switching_activity -state_condition {RET1N & CEN} -toggle_rate 128 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/CLK}]
set_switching_activity -state_condition {WEN[10] & GWEN} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/D[10]}]
set_switching_activity -state_condition {WEN[11] & GWEN} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 0 [get_pins {m/D[11]}]
set_switching_activity -state_condition {WEN[12] & GWEN} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/D[12]}]
set_switching_activity -state_condition {WEN[13] & GWEN} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 0 [get_pins {m/D[13]}]
set_switching_activity -state_condition {WEN[14] & GWEN} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/D[14]}]
set_switching_activity -state_condition {WEN[15] & GWEN} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 0 [get_pins {m/D[15]}]
set_switching_activity -state_condition {WEN[1] & GWEN} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 0 [get_pins {m/D[1]}]
set_switching_activity -state_condition {WEN[2] & GWEN} -toggle_rate 2 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/D[2]}]
set_switching_activity -state_condition {WEN[3] & GWEN} -toggle_rate 2 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/D[3]}]
set_switching_activity -state_condition {WEN[4] & GWEN} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/D[4]}]
set_switching_activity -state_condition {WEN[6] & GWEN} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 1 [get_pins {m/D[6]}]
set_switching_activity -state_condition {WEN[7] & GWEN} -toggle_rate 1 -glitch_rate 0 -period 524 -rise_ratio 0 [get_pins {m/D[7]}]
set_switching_activity -toggle_rate 11 -glitch_rate 0 -period 524 -rise_ratio 0.4545454545454545454545455 [get_pins {m/GWEN}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[0]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[10]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[11]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[12]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[13]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[14]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[15]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[1]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[2]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[3]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[4]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[5]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[6]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[7]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[8]}]
set_switching_activity -toggle_rate 4 -glitch_rate 0 -period 524 -rise_ratio 0.5 [get_pins {m/WEN[9]}]
set xu_q_case {q-sp0-tr0}
set xu_q_requested_sp {0}
set xu_q_requested_tr {0}
set xu_q_targets [list]
for {set i 0} {$i < 16} {incr i} {
  set name [format {m/Q[%d]} $i]
  set pin [get_pins -quiet $name]
  if {[sizeof_collection $pin] != 1 || [get_object_name $pin] ne $name} {error {exact Q pin not found}}
  lappend xu_q_targets $name
  set_switching_activity -static_probability 0 -toggle_rate 0 -glitch_rate 0 -period 524 -rise_ratio 0.5 $pin
}
set xu_q_request_f [open q-absolute-request.tsv {WRONLY CREAT EXCL}]
puts $xu_q_request_f "case\tphase\tpin\trequested_static_probability\trequested_toggle_rate\tpolicy"
xu_q_request before
xu_query {before_update} {0} {leakage} {-} {!RET1N} {both} {MEASURED_KNOWN_LEAKAGE_DWELL}
xu_query {before_update} {1} {leakage} {-} {default} {both} {MEASURED_KNOWN_LEAKAGE_DWELL}
xu_query {before_update} {2} {internal} {A[0]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {3} {internal} {A[1]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {4} {internal} {A[2]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {5} {internal} {A[3]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {6} {internal} {A[4]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {7} {internal} {A[5]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {8} {internal} {A[6]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {9} {internal} {A[7]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {10} {internal} {A[8]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {11} {internal} {A[9]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {12} {internal} {CEN} {default} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {13} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & !EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {13} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & !EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {13} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & !EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {14} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {14} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {14} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {15} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & !EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {15} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & !EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {15} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & !EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {16} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {16} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {16} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {17} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & !EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {17} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & !EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {17} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & !EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {18} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {18} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {18} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {19} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & !EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {19} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & !EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {19} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & !EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {20} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {20} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {20} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {21} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {21} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {21} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {22} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {22} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {22} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {23} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {23} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {23} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {24} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {24} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {24} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {25} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {25} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {25} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {26} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {26} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {26} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {27} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {27} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {27} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {28} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {28} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {28} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {29} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {29} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {29} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {30} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {30} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {30} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {31} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {31} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {31} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {32} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {32} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {32} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {33} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {33} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {33} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {34} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {34} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {34} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {35} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {35} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {35} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {36} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {36} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {36} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {37} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {37} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {37} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {38} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {38} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {38} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {39} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {39} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {39} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {40} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {40} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {40} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {41} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {41} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {41} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {42} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {42} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {42} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {43} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {43} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {43} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {44} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {44} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {44} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {45} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {45} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {45} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {46} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {46} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {46} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {47} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {47} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {47} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {48} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {48} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {48} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {49} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {49} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {49} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {50} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {50} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {50} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {51} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {51} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {51} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {52} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {52} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {52} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {53} {internal} {CLK} {!RET1N} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {53} {internal} {CLK} {!RET1N} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {53} {internal} {CLK} {!RET1N} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {54} {internal} {CLK} {RET1N & CEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {54} {internal} {CLK} {RET1N & CEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {54} {internal} {CLK} {RET1N & CEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {55} {internal} {D[0]} {!WEN[0] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {55} {internal} {D[0]} {!WEN[0] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {55} {internal} {D[0]} {!WEN[0] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {56} {internal} {D[0]} {WEN[0] & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {56} {internal} {D[0]} {WEN[0] & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {56} {internal} {D[0]} {WEN[0] & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {57} {internal} {D[10]} {!WEN[10] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {57} {internal} {D[10]} {!WEN[10] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {57} {internal} {D[10]} {!WEN[10] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {58} {internal} {D[10]} {WEN[10] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {58} {internal} {D[10]} {WEN[10] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {58} {internal} {D[10]} {WEN[10] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {59} {internal} {D[11]} {!WEN[11] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {59} {internal} {D[11]} {!WEN[11] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {59} {internal} {D[11]} {!WEN[11] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {60} {internal} {D[11]} {WEN[11] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {60} {internal} {D[11]} {WEN[11] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {60} {internal} {D[11]} {WEN[11] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {61} {internal} {D[12]} {!WEN[12] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {61} {internal} {D[12]} {!WEN[12] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {61} {internal} {D[12]} {!WEN[12] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {62} {internal} {D[12]} {WEN[12] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {62} {internal} {D[12]} {WEN[12] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {62} {internal} {D[12]} {WEN[12] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {63} {internal} {D[13]} {!WEN[13] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {63} {internal} {D[13]} {!WEN[13] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {63} {internal} {D[13]} {!WEN[13] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {64} {internal} {D[13]} {WEN[13] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {64} {internal} {D[13]} {WEN[13] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {64} {internal} {D[13]} {WEN[13] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {65} {internal} {D[14]} {!WEN[14] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {65} {internal} {D[14]} {!WEN[14] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {65} {internal} {D[14]} {!WEN[14] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {66} {internal} {D[14]} {WEN[14] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {66} {internal} {D[14]} {WEN[14] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {66} {internal} {D[14]} {WEN[14] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {67} {internal} {D[15]} {!WEN[15] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {67} {internal} {D[15]} {!WEN[15] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {67} {internal} {D[15]} {!WEN[15] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {68} {internal} {D[15]} {WEN[15] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {68} {internal} {D[15]} {WEN[15] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {68} {internal} {D[15]} {WEN[15] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {69} {internal} {D[1]} {!WEN[1] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {69} {internal} {D[1]} {!WEN[1] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {69} {internal} {D[1]} {!WEN[1] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {70} {internal} {D[1]} {WEN[1] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {70} {internal} {D[1]} {WEN[1] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {70} {internal} {D[1]} {WEN[1] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {71} {internal} {D[2]} {!WEN[2] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {71} {internal} {D[2]} {!WEN[2] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {71} {internal} {D[2]} {!WEN[2] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {72} {internal} {D[2]} {WEN[2] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {72} {internal} {D[2]} {WEN[2] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {72} {internal} {D[2]} {WEN[2] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {73} {internal} {D[3]} {!WEN[3] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {73} {internal} {D[3]} {!WEN[3] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {73} {internal} {D[3]} {!WEN[3] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {74} {internal} {D[3]} {WEN[3] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {74} {internal} {D[3]} {WEN[3] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {74} {internal} {D[3]} {WEN[3] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {75} {internal} {D[4]} {!WEN[4] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {75} {internal} {D[4]} {!WEN[4] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {75} {internal} {D[4]} {!WEN[4] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {76} {internal} {D[4]} {WEN[4] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {76} {internal} {D[4]} {WEN[4] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {76} {internal} {D[4]} {WEN[4] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {77} {internal} {D[5]} {!WEN[5] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {77} {internal} {D[5]} {!WEN[5] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {77} {internal} {D[5]} {!WEN[5] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {78} {internal} {D[5]} {WEN[5] & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {78} {internal} {D[5]} {WEN[5] & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {78} {internal} {D[5]} {WEN[5] & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {79} {internal} {D[6]} {!WEN[6] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {79} {internal} {D[6]} {!WEN[6] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {79} {internal} {D[6]} {!WEN[6] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {80} {internal} {D[6]} {WEN[6] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {80} {internal} {D[6]} {WEN[6] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {80} {internal} {D[6]} {WEN[6] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {81} {internal} {D[7]} {!WEN[7] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {81} {internal} {D[7]} {!WEN[7] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {81} {internal} {D[7]} {!WEN[7] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {82} {internal} {D[7]} {WEN[7] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {82} {internal} {D[7]} {WEN[7] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {82} {internal} {D[7]} {WEN[7] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {83} {internal} {D[8]} {!WEN[8] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {83} {internal} {D[8]} {!WEN[8] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {83} {internal} {D[8]} {!WEN[8] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {84} {internal} {D[8]} {WEN[8] & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {84} {internal} {D[8]} {WEN[8] & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {84} {internal} {D[8]} {WEN[8] & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {85} {internal} {D[9]} {!WEN[9] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {85} {internal} {D[9]} {!WEN[9] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {85} {internal} {D[9]} {!WEN[9] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {86} {internal} {D[9]} {WEN[9] & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {86} {internal} {D[9]} {WEN[9] & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {86} {internal} {D[9]} {WEN[9] & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {87} {internal} {GWEN} {default} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {before_update} {88} {internal} {RET1N} {CEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {88} {internal} {RET1N} {CEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {88} {internal} {RET1N} {CEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {89} {internal} {WEN[0]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {90} {internal} {WEN[10]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {91} {internal} {WEN[11]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {92} {internal} {WEN[12]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {93} {internal} {WEN[13]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {94} {internal} {WEN[14]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {95} {internal} {WEN[15]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {96} {internal} {WEN[1]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {97} {internal} {WEN[2]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {98} {internal} {WEN[3]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {99} {internal} {WEN[4]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {100} {internal} {WEN[5]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {101} {internal} {WEN[6]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {102} {internal} {WEN[7]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {103} {internal} {WEN[8]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {104} {internal} {WEN[9]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {before_update} {105} {internal} {Q[0]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {105} {internal} {Q[0]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {105} {internal} {Q[0]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {106} {internal} {Q[10]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {106} {internal} {Q[10]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {106} {internal} {Q[10]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {107} {internal} {Q[11]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {107} {internal} {Q[11]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {107} {internal} {Q[11]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {108} {internal} {Q[12]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {108} {internal} {Q[12]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {108} {internal} {Q[12]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {109} {internal} {Q[13]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {109} {internal} {Q[13]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {109} {internal} {Q[13]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {110} {internal} {Q[14]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {110} {internal} {Q[14]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {110} {internal} {Q[14]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {111} {internal} {Q[15]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {111} {internal} {Q[15]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {111} {internal} {Q[15]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {112} {internal} {Q[1]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {112} {internal} {Q[1]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {112} {internal} {Q[1]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {113} {internal} {Q[2]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {113} {internal} {Q[2]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {113} {internal} {Q[2]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {114} {internal} {Q[3]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {114} {internal} {Q[3]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {114} {internal} {Q[3]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {115} {internal} {Q[4]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {115} {internal} {Q[4]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {115} {internal} {Q[4]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {116} {internal} {Q[5]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {116} {internal} {Q[5]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {116} {internal} {Q[5]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {117} {internal} {Q[6]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {117} {internal} {Q[6]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {117} {internal} {Q[6]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {118} {internal} {Q[7]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {118} {internal} {Q[7]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {118} {internal} {Q[7]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {119} {internal} {Q[8]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {119} {internal} {Q[8]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {119} {internal} {Q[8]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {120} {internal} {Q[9]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {120} {internal} {Q[9]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {before_update} {120} {internal} {Q[9]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_q_activity before
redirect -file update-power.rpt {update_power}
redirect -file fixture-power-diagnostic-only.rpt {report_power -verbose}
if {[catch {redirect -file macro-power-diagnostic-only.rpt {
  puts {XU_Q_ABSOLUTE_FIXTURE_MACRO_ONLY_NOT_MEASURED_ZERO_OR_SOC_ENERGY}
  report_power -cell_power -nosplit -include_lib_cells [get_cells m]
}} xu_q_macro_report_error]} {
  set f [open macro-report-unavailable.rpt {WRONLY CREAT EXCL}]
  puts $f $xu_q_macro_report_error
  close $f
}
set f [open macro-power-attributes.rpt {WRONLY CREAT EXCL}]
puts $f {XU_Q_ABSOLUTE_MACRO_ATTRIBUTES_OPTIONAL_NOT_ENERGY_QUALIFIED}
foreach attribute {internal_power switching_power leakage_power total_power} {
  set status AVAILABLE
  if {[catch {get_attribute -quiet [get_cells m] $attribute} value]} {set status UNAVAILABLE}
  puts $f [list $attribute $status $value]
}
close $f
xu_query {after_update} {0} {leakage} {-} {!RET1N} {both} {MEASURED_KNOWN_LEAKAGE_DWELL}
xu_query {after_update} {1} {leakage} {-} {default} {both} {MEASURED_KNOWN_LEAKAGE_DWELL}
xu_query {after_update} {2} {internal} {A[0]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {3} {internal} {A[1]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {4} {internal} {A[2]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {5} {internal} {A[3]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {6} {internal} {A[4]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {7} {internal} {A[5]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {8} {internal} {A[6]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {9} {internal} {A[7]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {10} {internal} {A[8]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {11} {internal} {A[9]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {12} {internal} {CEN} {default} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {13} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & !EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {13} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & !EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {13} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & !EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {14} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {14} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {14} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {15} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & !EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {15} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & !EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {15} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & !EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {16} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {16} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {16} {internal} {CLK} {RET1N & !CEN & GWEN & !EMA[2] & EMA[1] & EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {17} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & !EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {17} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & !EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {17} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & !EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {18} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {18} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {18} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & !EMA[1] & EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {19} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & !EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {19} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & !EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {19} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & !EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {20} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & EMA[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {20} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & EMA[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {20} {internal} {CLK} {RET1N & !CEN & GWEN & EMA[2] & EMA[1] & EMA[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {21} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {21} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {21} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {22} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {22} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {22} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {23} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {23} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {23} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {24} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {24} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {24} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {25} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {25} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {25} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {26} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {26} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {26} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {27} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {27} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {27} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {28} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {28} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {28} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {29} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {29} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {29} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {30} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {30} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {30} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {31} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {31} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {31} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {32} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {32} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {32} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {33} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {33} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {33} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {34} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {34} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {34} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {35} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {35} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {35} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {36} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {36} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {36} {internal} {CLK} {RET1N & !CEN & !GWEN & !EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {37} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {37} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {37} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {38} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {38} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {38} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {39} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {39} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {39} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {40} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {40} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {40} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {41} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {41} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {41} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {42} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {42} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {42} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {43} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {43} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {43} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {44} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {44} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {44} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & !EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {45} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {45} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {45} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {46} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {46} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {46} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {47} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {47} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {47} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {48} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {48} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {48} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & !EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {49} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {49} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {49} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {50} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {50} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {50} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & !EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {51} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {51} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {51} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & !EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {52} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {52} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {52} {internal} {CLK} {RET1N & !CEN & !GWEN & EMA[2] & EMA[1] & EMA[0] & EMAW[1] & EMAW[0]} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {53} {internal} {CLK} {!RET1N} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {53} {internal} {CLK} {!RET1N} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {53} {internal} {CLK} {!RET1N} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {54} {internal} {CLK} {RET1N & CEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {54} {internal} {CLK} {RET1N & CEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {54} {internal} {CLK} {RET1N & CEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {55} {internal} {D[0]} {!WEN[0] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {55} {internal} {D[0]} {!WEN[0] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {55} {internal} {D[0]} {!WEN[0] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {56} {internal} {D[0]} {WEN[0] & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {56} {internal} {D[0]} {WEN[0] & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {56} {internal} {D[0]} {WEN[0] & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {57} {internal} {D[10]} {!WEN[10] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {57} {internal} {D[10]} {!WEN[10] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {57} {internal} {D[10]} {!WEN[10] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {58} {internal} {D[10]} {WEN[10] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {58} {internal} {D[10]} {WEN[10] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {58} {internal} {D[10]} {WEN[10] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {59} {internal} {D[11]} {!WEN[11] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {59} {internal} {D[11]} {!WEN[11] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {59} {internal} {D[11]} {!WEN[11] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {60} {internal} {D[11]} {WEN[11] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {60} {internal} {D[11]} {WEN[11] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {60} {internal} {D[11]} {WEN[11] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {61} {internal} {D[12]} {!WEN[12] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {61} {internal} {D[12]} {!WEN[12] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {61} {internal} {D[12]} {!WEN[12] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {62} {internal} {D[12]} {WEN[12] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {62} {internal} {D[12]} {WEN[12] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {62} {internal} {D[12]} {WEN[12] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {63} {internal} {D[13]} {!WEN[13] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {63} {internal} {D[13]} {!WEN[13] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {63} {internal} {D[13]} {!WEN[13] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {64} {internal} {D[13]} {WEN[13] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {64} {internal} {D[13]} {WEN[13] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {64} {internal} {D[13]} {WEN[13] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {65} {internal} {D[14]} {!WEN[14] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {65} {internal} {D[14]} {!WEN[14] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {65} {internal} {D[14]} {!WEN[14] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {66} {internal} {D[14]} {WEN[14] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {66} {internal} {D[14]} {WEN[14] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {66} {internal} {D[14]} {WEN[14] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {67} {internal} {D[15]} {!WEN[15] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {67} {internal} {D[15]} {!WEN[15] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {67} {internal} {D[15]} {!WEN[15] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {68} {internal} {D[15]} {WEN[15] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {68} {internal} {D[15]} {WEN[15] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {68} {internal} {D[15]} {WEN[15] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {69} {internal} {D[1]} {!WEN[1] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {69} {internal} {D[1]} {!WEN[1] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {69} {internal} {D[1]} {!WEN[1] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {70} {internal} {D[1]} {WEN[1] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {70} {internal} {D[1]} {WEN[1] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {70} {internal} {D[1]} {WEN[1] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {71} {internal} {D[2]} {!WEN[2] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {71} {internal} {D[2]} {!WEN[2] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {71} {internal} {D[2]} {!WEN[2] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {72} {internal} {D[2]} {WEN[2] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {72} {internal} {D[2]} {WEN[2] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {72} {internal} {D[2]} {WEN[2] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {73} {internal} {D[3]} {!WEN[3] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {73} {internal} {D[3]} {!WEN[3] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {73} {internal} {D[3]} {!WEN[3] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {74} {internal} {D[3]} {WEN[3] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {74} {internal} {D[3]} {WEN[3] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {74} {internal} {D[3]} {WEN[3] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {75} {internal} {D[4]} {!WEN[4] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {75} {internal} {D[4]} {!WEN[4] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {75} {internal} {D[4]} {!WEN[4] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {76} {internal} {D[4]} {WEN[4] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {76} {internal} {D[4]} {WEN[4] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {76} {internal} {D[4]} {WEN[4] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {77} {internal} {D[5]} {!WEN[5] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {77} {internal} {D[5]} {!WEN[5] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {77} {internal} {D[5]} {!WEN[5] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {78} {internal} {D[5]} {WEN[5] & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {78} {internal} {D[5]} {WEN[5] & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {78} {internal} {D[5]} {WEN[5] & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {79} {internal} {D[6]} {!WEN[6] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {79} {internal} {D[6]} {!WEN[6] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {79} {internal} {D[6]} {!WEN[6] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {80} {internal} {D[6]} {WEN[6] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {80} {internal} {D[6]} {WEN[6] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {80} {internal} {D[6]} {WEN[6] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {81} {internal} {D[7]} {!WEN[7] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {81} {internal} {D[7]} {!WEN[7] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {81} {internal} {D[7]} {!WEN[7] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {82} {internal} {D[7]} {WEN[7] & GWEN} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {82} {internal} {D[7]} {WEN[7] & GWEN} {rise} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {82} {internal} {D[7]} {WEN[7] & GWEN} {fall} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {83} {internal} {D[8]} {!WEN[8] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {83} {internal} {D[8]} {!WEN[8] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {83} {internal} {D[8]} {!WEN[8] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {84} {internal} {D[8]} {WEN[8] & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {84} {internal} {D[8]} {WEN[8] & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {84} {internal} {D[8]} {WEN[8] & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {85} {internal} {D[9]} {!WEN[9] & !GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {85} {internal} {D[9]} {!WEN[9] & !GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {85} {internal} {D[9]} {!WEN[9] & !GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {86} {internal} {D[9]} {WEN[9] & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {86} {internal} {D[9]} {WEN[9] & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {86} {internal} {D[9]} {WEN[9] & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {87} {internal} {GWEN} {default} {both} {DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL}
xu_query {after_update} {88} {internal} {RET1N} {CEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {88} {internal} {RET1N} {CEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {88} {internal} {RET1N} {CEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {89} {internal} {WEN[0]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {90} {internal} {WEN[10]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {91} {internal} {WEN[11]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {92} {internal} {WEN[12]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {93} {internal} {WEN[13]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {94} {internal} {WEN[14]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {95} {internal} {WEN[15]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {96} {internal} {WEN[1]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {97} {internal} {WEN[2]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {98} {internal} {WEN[3]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {99} {internal} {WEN[4]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {100} {internal} {WEN[5]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {101} {internal} {WEN[6]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {102} {internal} {WEN[7]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {103} {internal} {WEN[8]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {104} {internal} {WEN[9]} {default} {both} {MEASURED_KNOWN_STABLE_BINARY_ACTIVITY}
xu_query {after_update} {105} {internal} {Q[0]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {105} {internal} {Q[0]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {105} {internal} {Q[0]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {106} {internal} {Q[10]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {106} {internal} {Q[10]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {106} {internal} {Q[10]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {107} {internal} {Q[11]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {107} {internal} {Q[11]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {107} {internal} {Q[11]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {108} {internal} {Q[12]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {108} {internal} {Q[12]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {108} {internal} {Q[12]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {109} {internal} {Q[13]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {109} {internal} {Q[13]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {109} {internal} {Q[13]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {110} {internal} {Q[14]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {110} {internal} {Q[14]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {110} {internal} {Q[14]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {111} {internal} {Q[15]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {111} {internal} {Q[15]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {111} {internal} {Q[15]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {112} {internal} {Q[1]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {112} {internal} {Q[1]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {112} {internal} {Q[1]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {113} {internal} {Q[2]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {113} {internal} {Q[2]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {113} {internal} {Q[2]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {114} {internal} {Q[3]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {114} {internal} {Q[3]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {114} {internal} {Q[3]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {115} {internal} {Q[4]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {115} {internal} {Q[4]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {115} {internal} {Q[4]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {116} {internal} {Q[5]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {116} {internal} {Q[5]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {116} {internal} {Q[5]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {117} {internal} {Q[6]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {117} {internal} {Q[6]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {117} {internal} {Q[6]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {118} {internal} {Q[7]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {118} {internal} {Q[7]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {118} {internal} {Q[7]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {119} {internal} {Q[8]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {119} {internal} {Q[8]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {119} {internal} {Q[8]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {120} {internal} {Q[9]} {RET1N & GWEN} {both} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {120} {internal} {Q[9]} {RET1N & GWEN} {rise} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_query {after_update} {120} {internal} {Q[9]} {RET1N & GWEN} {fall} {UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED}
xu_q_activity after
xu_q_request after
close $xu_q_request_f
close $xu_f
set xu_q_after [xu_q_snapshot after]
if {$xu_q_before ne $xu_q_after} {error {input identity changed during fixture run}}
puts {XU_Q_ABSOLUTE_SWEEP_CASE_DONE_NOT_ZERO_Q_OR_ENERGY_QUALIFIED}
} xu_q_error]} {puts stderr "XU_Q_ABSOLUTE_SWEEP_REJECT $xu_q_error";exit 2}
exit
