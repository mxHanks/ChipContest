# Bounded physical-cell ECO helpers. Native API/topology must pass one-buffer probe first.
proc eco_require {ok message} {if {!$ok} {error $message}}
proc eco_sha {path expected} {
  eco_require [file isfile $path] "missing input: $path"
  set actual [lindex [exec sha256sum -- $path] 0]
  eco_require [expr {$actual eq $expected}] "SHA256 mismatch: $path"
  return $actual
}
proc eco_open {name} {return [open [file join $::eco_out $name] {WRONLY CREAT EXCL}]}
proc eco_parent {name} {
  set i [string last / $name]
  if {$i < 0} {return {}}
  return [string range $name 0 [expr {$i-1}]]
}
proc eco_context {owner} {current_instance; if {$owner ne {}} {current_instance $owner}}
proc eco_pin {name} {
  current_instance
  set pin [get_pins -quiet $name]
  eco_require [expr {[sizeof_collection $pin] == 1 && [get_object_name $pin] eq $name}] "nonunique exact pin: $name"
  return $pin
}
proc eco_capture {name command} {
  # Required commands fail; unsupported APIs never become zero/slack=PASS.
  redirect -file [file join $::eco_out $name] $command
}
proc eco_config {} {
  eco_require [info exists ::env(XU_ECO_PACKAGE)] {runner must provide sealed ECO package}
  eco_require [info exists ::env(XU_ECO_CONFIG)] {runner must provide sealed stage configuration}
  source $::env(XU_ECO_CONFIG)
  set ::eco_out [pwd]
  foreach {path digest} $::eco_bindings {eco_sha $path $digest}
  set_host_options -max_cores 2
}
proc eco_libraries {tool} {
  foreach {path digest} $::eco_library_bindings {eco_sha $path $digest}
  if {$tool eq {pt}} {set_app_var link_path $::eco_link_libraries} else {
    set_app_var target_library [list [lindex $::eco_link_libraries 1]]
    set_app_var link_library $::eco_link_libraries
  }
}
proc eco_constraints {} {
  # Same source SDC; only the three native-proven PT -add portability substitutions.
  eco_require [expr {[sizeof_collection [get_clocks -quiet *]] == 0}] {clock state must be empty before original SDC}
  set source [file join $::eco_baseline source contracts reference-full-soc.sdc]
  eco_sha $source c15ede0fc2c65771f87e2d6aee763b4ea0d53934868ca807b4785c36182fce7c
  set f [open $source rb]; set raw [read $f]; close $f
  eco_require [expr {[regexp -all {create_generated_clock -name } $raw] == 3}] {original generated-clock count changed}
  set path [file join $::eco_out original-constraints-pt-add.sdc]
  set f [open $path {WRONLY CREAT EXCL}]; fconfigure $f -translation binary
  puts -nonewline $f [string map {{create_generated_clock -name } {create_generated_clock -add -name }} $raw]; close $f
  eco_sha $path 404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98
  set ::XU_CLOCK_MODE envelope; set ::XU_PLL_DIV 0; set ::XU_PROPAGATE_CLOCKS 0
  uplevel #0 [list source $path]
  foreach pair {{xu_hfextclk 6.666666667} {xu_lfextclk 30517.578125} {xu_jtag_tck 100.0}} {
    set clock [get_clocks -quiet [lindex $pair 0]]
    eco_require [expr {[sizeof_collection $clock] == 1}] "missing clock: $pair"
    eco_require [expr {abs([get_attribute $clock period]-[lindex $pair 1]) < 0.000001}] "clock period changed: $pair"
  }
  eco_require [expr {[sizeof_collection [get_clocks -quiet xu_plldiv_envelope]] == 1}] {missing divider envelope}
  eco_require [expr {[sizeof_collection [get_clocks -quiet *]] == 4}] {original four-clock set changed}
}
proc eco_load_pt {mapped} {
  eco_libraries pt
  read_verilog $mapped
  current_design xu_soc_sysbus32_ppa_top
  eco_require [link_design xu_soc_sysbus32_ppa_top] {PT link failed}
  uplevel #0 [list source [file join $::eco_baseline source ppa hierarchy_contract.tcl]]
  sysbus32_check_hierarchy
  eco_require [expr {$::sysbus32_expected_total_macros == 353 && $::sysbus32_expected_internal_macros == 33}] {ECO only accepts selected353 profile}
  eco_constraints
  update_timing -full
}
proc eco_buffer {} {
  set cell [get_lib_cells -quiet */$::eco_buffer_reference]
  eco_require [expr {[sizeof_collection $cell] == 1}] {buffer library cell missing/ambiguous}
  eco_require [expr {![get_attribute $cell is_sequential]}] {buffer must be combinational}
  set ip [get_lib_pins -of_objects $cell -filter {direction == in}]
  set op [get_lib_pins -of_objects $cell -filter {direction == out}]
  eco_require [expr {[sizeof_collection $ip] == 1 && [sizeof_collection $op] == 1}] {buffer must be unary}
  set input [file tail [get_object_name $ip]]
  set output [file tail [get_object_name $op]]
  set function [get_attribute $op function]
  eco_require [expr {$input eq {I} && $output eq {Z} && [string map [list {(} {} {)} {} { } {} {"} {}] $function] eq $input}] {unproven noninverting I/Z buffer}
  set area [get_attribute $cell area]
  eco_require [expr {[string is double -strict $area] && $area > 0}] {invalid characterized buffer area}
  return $cell
}
proc eco_snapshot {stem} {
  current_instance
  set cells [dict create]; set nets [dict create]
  set f [eco_open ${stem}-cells.tsv]; puts $f "instance\treference\tis_hierarchical\tarea"
  foreach_in_collection cell [get_cells -hierarchical *] {
    set name [get_object_name $cell]; set ref [get_attribute $cell ref_name]
    set hier [get_attribute $cell is_hierarchical]
    set area [get_attribute $cell area]
    puts $f "$name\t$ref\t$hier\t$area"
    if {!$hier} {dict set cells $name $ref}
  }
  close $f
  set f [eco_open ${stem}-nets.tsv]; puts $f {net}
  foreach_in_collection net [get_nets -hierarchical *] {set name [get_object_name $net]; dict set nets $name 1; puts $f $name}
  close $f
  return [list $cells $nets]
}
proc eco_connections {label net} {
  # Complete membership of every touched local segment, before/after each edit.
  set f [eco_open ${label}-connections.tsv]; puts $f "net\tpin\tdirection"
  foreach_in_collection pin [get_pins -of_objects $net] {
    puts $f "[get_object_name $net]\t[get_object_name $pin]\t[get_attribute $pin direction]"
  }
  close $f
}
proc eco_clocks {} {
  current_instance
  set result [dict create]
  set pins [all_registers -clock_pins]
  foreach_in_collection macro [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}] {
    append_to_collection pins [eco_pin [get_object_name $macro]/CLK]
  }
  foreach_in_collection pin $pins {dict set result [get_object_name $pin] [lsort [get_object_name [get_attribute $pin clocks]]]}
  return $result
}
proc eco_assert_clocks {before} {
  set after [eco_clocks]
  eco_require [expr {[dict size $after] == [dict size $before]}] {original register/SRAM clock endpoint count changed}
  dict for {pin clocks} $before {
    eco_require [expr {[dict exists $after $pin] && [dict get $after $pin] eq $clocks}] "original register/SRAM clock association changed: $pin"
  }
  set f [eco_open original-clock-association.tsv]; puts $f "pin\tclocks"
  dict for {pin clocks} $after {puts $f "$pin\t$clocks"}
  close $f
}
proc eco_paths {pin delay {gating 0}} {
  current_instance
  set result {}; set count 0
  foreach edge {rise fall} {
    # Each launch-clock and target transition is queried explicitly. Capture
    # clocks and path group are retained in endpoint-paths.tsv, never guessed.
    foreach_in_collection clock [get_clocks *] {
      set cmd [list get_timing_paths -from $clock -${edge}_to $pin -delay_type $delay -slack_lesser_than 1000000000 -nworst 64 -max_paths 64]
      if {$gating} {lappend cmd -group **clock_gating_default**}
      set paths [eval $cmd]
      eco_require [expr {[sizeof_collection $paths] < 64}] {endpoint query hit cap; expand/review actual contexts before repair}
      foreach_in_collection path $paths {
        set slack [get_attribute $path slack]
        eco_require [expr {[string is double -strict $slack] && $slack == $slack && abs($slack) < 1e8}] {nonfinite/unknown slack}
        set endpoint [get_object_name [get_attribute $path endpoint]]
        eco_require [expr {$endpoint eq [get_object_name $pin]}] {timing query escaped exact endpoint}
        puts $::eco_path_log "[get_object_name $pin]\t$delay\t$edge\t[get_object_name $clock]\t[get_object_name [get_attribute $path endpoint_clock]]\t[get_object_name [get_attribute $path path_group]]\t$slack"
        if {$result eq {} || $slack < $result} {set result $slack}
        incr count
      }
    }
  }
  eco_require [expr {$count > 0}] "no tested $delay paths to [get_object_name $pin]; not a zero-slack result"
  return $result
}
proc eco_insert {target} {
  # Exactly ONE load on ONE local segment. Never buffer a driver/clock branch.
  current_instance
  set pin [eco_pin $target]
  eco_require [expr {[get_attribute $pin direction] eq {in}}] {target must be an input load}
  set parent [eco_parent $target]; set owner [eco_parent $parent]
  set oldnet [get_nets -of_objects $pin]
  eco_require [expr {[sizeof_collection $oldnet] == 1}] {target must have one local net}
  set netname [get_object_name $oldnet]
  eco_require [expr {[eco_parent $netname] eq $owner}] {target local-net owner mismatch}
  eco_connections [format {insert-%04d-before} $::eco_inserted] $oldnet
  eco_require [expr {$::eco_inserted < $::eco_max_buffers}] {bounded cell budget exhausted}
  set buffer [eco_buffer]
  set area [get_attribute $buffer area]
  eco_require [expr {$::eco_added_area+$area <= $::eco_max_added_area}] {bounded raw-area experiment budget exhausted}
  eco_context $owner
  set relative [string range $target [expr {[string length $owner]+($owner ne {})}] end]
  set localpin [get_pins -quiet $relative]
  eco_require [expr {[sizeof_collection $localpin] == 1 && [get_object_name $localpin] eq $target}] {scoped target changed}
  set cname [format XU_ECO_%s_%04d $::eco_mode $::eco_inserted]
  set nname ${cname}_NET
  eco_require [expr {[sizeof_collection [get_cells -quiet $cname]] == 0 && [sizeof_collection [get_nets -quiet $nname]] == 0}] {ECO names already exist}
  set new [insert_buffer -new_cell_names $cname -new_net_names $nname $localpin $buffer]
  eco_require [expr {[sizeof_collection $new] == 1}] {single-load insertion did not return exactly one buffer}
  set fullname [get_object_name $new]
  eco_require [expr {[eco_parent $fullname] eq $owner && [get_attribute $new ref_name] eq $::eco_buffer_reference}] {unexpected inserted cell identity/owner}
  current_instance
  set actual [get_attribute [get_cells $fullname] area]
  eco_require [expr {[string is double -strict $actual] && $actual > 0}] {inserted buffer missing actual area}
  incr ::eco_inserted; set ::eco_added_area [expr {$::eco_added_area+$actual}]
  puts $::eco_insert_log "$fullname\t$::eco_buffer_reference\t$target\t$netname\t$actual"
  flush $::eco_insert_log
  set targetnet [get_nets -of_objects [eco_pin $target]]
  eco_require [expr {[sizeof_collection $targetnet] == 1 && [get_object_name $targetnet] ne $netname}] {target did not move to new net}
  eco_connections [format {insert-%04d-after-new} [expr {$::eco_inserted-1}]] $targetnet
  eco_connections [format {insert-%04d-after-old} [expr {$::eco_inserted-1}]] [get_nets $netname]
  update_timing -full
  return $fullname
}
proc eco_export {stem} {
  # Verified manual syntax. There is intentionally no PT full-Verilog writer.
  foreach format {dctcl ptsh text} {
    set path [file join $::eco_out ${stem}.${format}]
    eco_require [expr {![file exists $path]}] {refuse ECO export overwrite}
    write_changes -format $format -output $path
    eco_require [file isfile $path] "ECO exporter produced no file: $format"
  }
}
proc eco_reports {stem} {
  foreach {name command} {
    coverage {report_analysis_coverage -status_details {untested violated}}
    setup {report_timing -delay_type max -slack_lesser_than 1000000000 -max_paths 100 -nworst 1 -path_type full_clock_expanded -significant_digits 8 -nets -input_pins -transition_time -capacitance}
    hold {report_timing -delay_type min -slack_lesser_than 1000000000 -max_paths 100 -nworst 1 -path_type full_clock_expanded -significant_digits 8 -nets -input_pins -transition_time -capacitance}
    all_violators {report_constraint -all_violators -verbose -significant_digits 8}
    recovery {report_constraint -recovery -all_violators -verbose}
    removal {report_constraint -removal -all_violators -verbose}
    gating_setup {report_constraint -clock_gating_setup -all_violators -verbose}
    gating_hold {report_constraint -clock_gating_hold -all_violators -verbose}
    min_pulse_width {report_constraint -min_pulse_width -all_violators -verbose}
    exceptions {report_exceptions}
    case_analysis {report_case_analysis -all}
    disabled_timing {report_disable_timing}
    check_timing {check_timing -verbose}
    clocks {report_clock -attributes}
    units {report_units}
  } {eco_capture ${stem}-${name}.rpt $command}
  foreach_in_collection group [get_path_groups *] {
    set name [get_object_name $group]; set safe [string map {/ _ * ALL} $name]
    foreach delay {min max} {eco_capture ${stem}-group-${safe}-${delay}.rpt [list report_timing -group $name -delay_type $delay -slack_lesser_than 1000000000 -max_paths 20 -nworst 1 -path_type full_clock_expanded -significant_digits 8]}
  }
}
proc eco_finish {marker} {set f [eco_open $marker]; puts $f {COLLECTED_NOT_TIMING_CLOSURE_NOT_QUALIFIED}; close $f}

proc eco_native_proof {} {
  # Exact characterized identity function, bound by the runner to this native run.
  set cell [eco_buffer]
  set f [eco_open buffer-functions.tsv]
  puts $f "library_cell\treference\tpin\tdirection\tfunction\tis_sequential"
  foreach_in_collection pin [get_lib_pins -of_objects $cell] {
    set direction [get_attribute $pin direction]
    set function {-}
    if {$direction eq {out}} {set function [get_attribute $pin function]}
    puts $f "[get_object_name $cell]\t$::eco_buffer_reference\t[file tail [get_object_name $pin]]\t$direction\t$function\t[get_attribute $cell is_sequential]"
  }
  close $f
  set f [eco_open leaf-pin-directions.tsv]
  puts $f "reference\tlibrary_cell\tpin\tdirection"
  set seen [dict create]
  foreach_in_collection leaf [get_cells -hierarchical -filter {is_hierarchical == false}] {
    set ref [get_attribute $leaf ref_name]
    if {[dict exists $seen $ref] || $ref in {**logic_0** **logic_1**}} {continue}
    dict set seen $ref 1
    set lib [get_lib_cells -quiet */$ref]
    eco_require [expr {[sizeof_collection $lib] == 1}] "missing/ambiguous original leaf library definition: $ref"
    foreach_in_collection pin [get_lib_pins -of_objects $lib] {
      puts $f "$ref\t[get_object_name $lib]\t[file tail [get_object_name $pin]]\t[get_attribute $pin direction]"
    }
  }
  close $f
}
proc eco_delta {before after} {
  lassign $before oldcells oldnets; lassign $after newcells newnets
  set f [eco_open cell-delta.tsv]; puts $f "change\tinstance\treference"
  dict for {name ref} $oldcells {
    eco_require [expr {[dict exists $newcells $name] && [dict get $newcells $name] eq $ref}] "original mapped leaf deleted/renamed/resized: $name"
  }
  set added 0
  dict for {name ref} $newcells {
    if {![dict exists $oldcells $name]} {
      eco_require [expr {$ref eq $::eco_buffer_reference && [string match */XU_ECO_* $name]}] "unexpected added leaf: $name $ref"
      puts $f "added\t$name\t$ref"; incr added
    }
  }
  close $f
  eco_require [expr {$added == $::eco_inserted}] {added leaf count does not match insertion ledger}
  set f [eco_open net-delta.tsv]; puts $f "change\tnet"
  dict for {name ignored} $oldnets {eco_require [dict exists $newnets $name] "original net removed/renamed: $name"}
  dict for {name ignored} $newnets {if {![dict exists $oldnets $name]} {puts $f "added\t$name"}}
  close $f
}
proc eco_bias_targets {} {
  set macro [get_cells -quiet -hierarchical -filter {full_name =~ */u_xu_matrix_dma/u_core/bias/memory/* && ref_name == RAMSP1024X16}]
  eco_require [expr {[sizeof_collection $macro] == 1}] {selected candidate must have one actual bias SRAM macro}
  set result {}
  for {set bit 0} {$bit < 16} {incr bit} {
    set name [format {%s/D[%d]} [get_object_name $macro] $bit]
    set pin [eco_pin $name]
    eco_require [expr {[get_attribute $pin direction] eq {in}}] {bias D target is not input}
    lappend result $name
  }
  return $result
}
proc eco_gate_targets {} {
  # Catalog names are diagnostic anchors, not evidence. Require the new mapped
  # native input and exact associated clock/load/latch connectivity first.
  set f [open [file join $::env(XU_ECO_PACKAGE) gate-anchors.txt] r]
  set names [split [string trim [read $f]] \n]; close $f
  set targets {}; set protected [dict create]
  foreach name $names {
    set pin [eco_pin $name]
    eco_require [expr {[get_attribute $pin direction] eq {in}}] {gate target is not an input}
    set cell [get_cells [eco_parent $name]]
    set ref [get_attribute $cell ref_name]
    eco_require [string match AND2* $ref] "gate AND cell changed; native diagnosis required: $name $ref"
    set clock [eco_pin [eco_parent $name]/A2]
    set gateparent [eco_parent [eco_parent $name]]
    set latch [eco_pin ${gateparent}/enb_reg/EN]
    foreach member [list $clock $latch] {
      set net [get_nets -of_objects $member]
      eco_require [expr {[sizeof_collection $net] == 1}] {protected gate pin is not one local net}
      dict set protected [get_object_name $member] [get_object_name $net]
    }
    # Require actual A2 clock and latch enable share their local clock segment.
    eco_require [expr {[dict get $protected [get_object_name $clock]] eq [dict get $protected [get_object_name $latch]]}] "gate A2/latch EN clock connectivity changed: $name"
    lappend targets $name
  }
  eco_require [expr {[llength $targets] == 15}] {old catalog anchors no longer match all 15 gate enable pins}
  return [list $targets $protected]
}
proc eco_assert_protected {protected} {
  dict for {name net} $protected {
    set actual [get_nets -of_objects [eco_pin $name]]
    eco_require [expr {[sizeof_collection $actual] == 1 && [get_object_name $actual] eq $net}] "protected clock/latch connectivity changed: $name"
  }
}
proc eco_begin_logs {} {
  set ::eco_inserted 0; set ::eco_added_area 0.0
  set ::eco_insert_log [eco_open insertions.tsv]
  puts $::eco_insert_log "instance\treference\tload_pin\told_net\tarea"
  set ::eco_path_log [eco_open endpoint-paths.tsv]
  puts $::eco_path_log "endpoint\tdelay\ttransition\tlaunch_clock\tcapture_clock\tpath_group\tslack_ns"
}
proc eco_close_logs {} {close $::eco_insert_log; close $::eco_path_log}
proc eco_failure {reason options} {
  catch {eco_close_logs}
  set f [open ECO_FAILED.txt w]; puts $f $reason
  if {[dict exists $options -errorinfo]} {puts $f [dict get $options -errorinfo]}
  close $f
  puts stderr "ECO_FAILED: $reason"
  exit 1
}
