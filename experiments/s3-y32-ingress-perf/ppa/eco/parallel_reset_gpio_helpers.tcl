# Exact current-map endpoints. No timing exceptions or clock/IO contract changes.
set ::rg_wrapper {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper}
proc rg_rows {} {
  set w $::rg_wrapper
  return [list \
    [list $w/bootrom_deglitch/T_8_reg/D 0 aon DQV0_12TR40] \
    [list $w/dwakeup_deglitch/T_8_reg/D 0 aon DQV0_12TR40] \
    [list $w/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN 2 pmu DSNQV0_12TR40] \
    [list $w/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN 2 pmu DSNQNV0_12TR40] \
    [list $w/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN 2 reset_catch DRNQV0_12TR40] \
    [list $w/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN 2 reset_catch DRNQV0_12TR40] \
    [list $w/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN 2 reset_catch DRNQV0_12TR40]]
}
proc rg_rows_validate {} {
  set data [dict create]; set async [dict create]
  foreach_in_collection p [all_registers -data_pins] {dict set data [get_object_name $p] 1}
  foreach_in_collection p [all_registers -async_pins] {dict set async [get_object_name $p] 1}
  foreach row [rg_rows] {
    lassign $row name mode family ref
    set p [eco_pin $name]; set c [get_cells [eco_parent $name]]
    eco_require [expr {[get_attribute $c ref_name] eq $ref && ![get_attribute $c is_hierarchical]}] "endpoint cell identity changed: $name"
    eco_require [expr {[get_attribute $p direction] eq {in}}] "endpoint not input: $name"
    if {$mode == 2} {eco_require [dict exists $async $name] "not native async pin: $name"} else {eco_require [dict exists $data $name] "not native data pin: $name"}
  }
}
proc rg_selected {} {
  set rows {}
  foreach row [rg_rows] {
    if {$::rg_selection eq {all} || [lindex $row 2] eq $::rg_selection} {lappend rows $row}
  }
  eco_require [expr {[llength $rows] > 0}] {empty explicit target selection}
  return $rows
}
proc rg_external_paths {row delay phase} {
  # A numeric watchdog/LF path must not stand in for the ERST/HF external context.
  lassign $row name mode family ref
  if {$family eq {aon}} {
    if {[string match */bootrom_deglitch/* $name]} {set source io_pads_bootrom_n_i_ival} else {set source io_pads_aon_pmu_dwakeup_n_i_ival}
  } else {set source io_pads_aon_erst_n_i_ival}
  set port [get_ports -quiet $source]
  eco_require [expr {[sizeof_collection $port] == 1}] "exact external source port missing: $source"
  set p [eco_pin $name]; set count 0; set minimum {}
  foreach edge {rise fall} {
    set selector [list -from $port -${edge}_to $p -delay_type $delay -slack_lesser_than 1000000000]
    if {$mode == 2} {lappend selector -group **async_default**}
    foreach cap {64 256 1024 4096 8192} {
      set paths [eval [concat [list get_timing_paths] $selector [list -nworst $cap -max_paths $cap]]]
      set found [sizeof_collection $paths]
      if {$found < $cap} {break}
    }
    eco_require [expr {$found < 8192}] "external-context query saturated: $source -> $name"
    set edge_min {}
    foreach_in_collection path $paths {
      set slack [get_attribute $path slack]
      eco_require [expr {[string is double -strict $slack] && $slack == $slack && abs($slack) < 1e8}] {external context slack is nonfinite/unknown}
      eco_require [expr {[get_object_name [get_attribute $path endpoint]] eq $name && [get_object_name [get_attribute $path startpoint]] eq $source}] {external context query escaped exact source/endpoint}
      eco_require [expr {[get_object_name [get_attribute $path endpoint_clock]] eq {xu_lfextclk}}] {external context capture clock changed}
      if {$edge_min eq {} || $slack < $edge_min} {set edge_min $slack}
      if {$minimum eq {} || $slack < $minimum} {set minimum $slack}
      incr count
    }
    if {$edge_min eq {}} {set edge_min UNKNOWN}
    puts $::rg_external_log "$phase\t$name\t$source\t$delay\t$edge\t$found\t$edge_min"
    flush $::rg_external_log
  }
  eco_require [expr {$count > 0}] "no tested $delay external-context paths: $source -> $name; not a zero-slack result"
  return $minimum
}
proc rg_begin_logs {} {
  eco_begin_logs
  set ::rg_external_log [eco_open external-context-paths.tsv]
  puts $::rg_external_log "phase\tendpoint\texact_source\tdelay\ttransition\tpaths_returned\tminimum_slack_ns"
}
proc rg_close_logs {} {close $::rg_external_log; eco_close_logs}
proc rg_measure {row delay phase {allow_unknown 0}} {
  lassign $row name mode family ref
  set code [catch {eco_paths [eco_pin $name] $delay $mode $phase} result opts]
  if {$code} {
    if {$allow_unknown && [string match {no tested max paths to *; not a zero-slack result} $result]} {return UNKNOWN}
    return -options $opts $result
  }
  set code [catch {rg_external_paths $row $delay $phase} external opts]
  if {$code} {
    if {$allow_unknown && [string match {no tested max external-context paths: *; not a zero-slack result} $external]} {return UNKNOWN}
    return -options $opts $external
  }
  if {$external < $result} {set result $external}
  return $result
}
proc rg_gpio {stem} {
  set p [get_ports -quiet {io_pads_gpioA_o_oval[27]}]
  eco_require [expr {[sizeof_collection $p] == 1}] {exact GPIO A27 port missing}
  foreach delay {min max} {
    eco_capture ${stem}-gpio-${delay}.rpt [list report_timing -to $p -delay_type $delay -slack_lesser_than 1000000000 -nworst 8 -max_paths 32 -path_type full_clock_expanded -significant_digits 8 -nets -input_pins -transition_time -capacitance]
  }
}
proc rg_diagnose {} {
  set f [eco_open target-topology.tsv]
  puts $f "endpoint\tfamily\tkind\tlocal_net\tlocal_owner\tlocal_pin_members\tmin_slack_ns\tmax_slack_ns"
  set i 0
  foreach row [rg_rows] {
    lassign $row name mode family ref
    set p [eco_pin $name]; set nets [get_nets -of_objects $p]
    eco_require [expr {[sizeof_collection $nets] == 1}] "nonunique local net: $name"
    set net [get_object_name $nets]
    set min [rg_measure $row min diagnostic_min]
    set max [rg_measure $row max diagnostic_max 1]
    puts $f "$name\t$family\t[expr {$mode == 2 ? {removal} : {hold}}]\t$net\t[eco_parent $net]\t[sizeof_collection [get_pins -of_objects $nets]]\t$min\t$max"
    eco_connections [format diagnostic-target-%04d $i] $nets
    foreach delay {min max} {
      eco_capture [format diagnostic-target-%04d-%s.rpt $i $delay] [list report_timing -to $p -delay_type $delay -slack_lesser_than 1000000000 -nworst 16 -max_paths 128 -path_type full_clock_expanded -significant_digits 8 -nets -input_pins -transition_time -capacitance]
    }
    incr i
  }
  close $f
}
proc rg_assert_reference_clocks {} {
  set expected [dict create]; set f [open $::eco_reference_clocks r]
  eco_require [expr {[gets $f] eq "pin\tclocks"}] {invalid seed clock-association header}
  while {[gets $f line] >= 0} {
    set fields [split $line \t]
    eco_require [expr {[llength $fields] == 2}] {invalid seed clock-association row}
    dict set expected [lindex $fields 0] [lindex $fields 1]
  }
  close $f
  set actual [eco_clocks]
  eco_require [expr {[dict size $expected] == [dict size $actual]}] {original clock endpoint count changed}
  dict for {pin clocks} $expected {
    eco_require [expr {[dict exists $actual $pin] && [dict get $actual $pin] eq $clocks}] "original clock association changed: $pin"
  }
  eco_assert_clocks $actual
}
proc rg_waveform_settings {} {
  set f [eco_open waveform-settings.tsv]; puts $f "variable\tbefore\tafter"
  foreach {name value} $::rg_waveform_settings {
    eco_require [regexp {^timing_[A-Za-z0-9_]*(waveform|expand)[A-Za-z0-9_]*$} $name] {only native waveform-expansion variables accepted}
    set old [get_app_var $name]
    eco_require [expr {[string is integer -strict $old] && [string is integer -strict $value] && $value > $old && $value <= 2000000}] "only bounded increases of existing integer expansion controls accepted: $name"
    set_app_var $name $value
    eco_require [expr {[get_app_var $name] == $value}] "native expansion setting failed: $name"
    puts $f "$name\t$old\t[get_app_var $name]"
  }
  close $f
}
