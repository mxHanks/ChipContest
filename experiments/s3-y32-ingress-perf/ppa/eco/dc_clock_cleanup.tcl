# Defines one exact identity-buffer removal operation; audited dc_apply handles
# source DDC load, original hierarchy contract, own SVF, map and area reports.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
proc clock_cleanup_visibility {name wave ledger} {
  set output [eco_pin ${name}/Z]
  set true_inputs {};set top_ports {};set hierarchy {}
  set segment [get_nets -of_objects $output]
  eco_require [expr {[sizeof_collection $segment]==1}] {cleanup output needs one exact local net}
  foreach_in_collection object [all_connected -leaf $segment] {
    set class [get_attribute $object object_class];set full [get_object_name $object]
    if {$class eq {port}} {lappend top_ports $full;continue}
    eco_require [expr {$class eq {pin}}] {cleanup native visibility returned unknown object class}
    set parent [get_cells -quiet [eco_parent $full]]
    eco_require [expr {[sizeof_collection $parent]==1}] {cleanup connected pin parent ambiguous}
    if {[get_attribute $parent is_hierarchical]} {lappend hierarchy $full;continue}
    if {[get_attribute $object direction] ne {out}} {lappend true_inputs $full}
  }
  puts $ledger "$wave\t$name\t[llength $true_inputs]\t[llength $top_ports]\t[join [lsort $hierarchy] ,]"
  flush $ledger
  # -leaf traverses hierarchy. Boundary pins returned by this DC build are
  # classified explicitly; only characterized NONhierarchical leaves count.
  eco_require [expr {[llength $true_inputs]==0 && [llength $top_ports]==0}] "planned added clock buffer is observable in seed: $name"
}
proc clock_cleanup_apply {} {
  eco_capture cleanup-all-connected-man.rpt {man all_connected}
  set mf [open [file join $::eco_out cleanup-all-connected-man.rpt] r];set manual [read $mf];close $mf
  eco_require [expr {[string first {-leaf} $manual]>=0}] {native all_connected does not document recursive -leaf}
  eco_require [expr {[llength $::clock_cleanup_waves]>=1 && [llength $::clock_cleanup_waves]<=64 && [llength [lindex $::clock_cleanup_waves 0]]==34}] {invalid exact34 cleanup waves}
  set lib [get_lib_cells -quiet */BUFV2_12TR40]
  eco_require [expr {[sizeof_collection $lib]==1 && ![get_attribute $lib is_sequential]}] {native identity buffer library missing}
  set ip [get_lib_pins -of_objects $lib -filter {direction == in}];set op [get_lib_pins -of_objects $lib -filter {direction == out}]
  eco_require [expr {[sizeof_collection $ip]==1 && [sizeof_collection $op]==1 && [file tail [get_object_name $ip]] eq {I} && [file tail [get_object_name $op]] eq {Z}}] {cleanup buffer not native exact unary I/Z}
  eco_require [expr {[string map [list {(} {} {)} {} { } {} {"} {}] [get_attribute $op function]] eq {I}}] {cleanup buffer function not native-proven identity}
  set ledger [eco_open clock-cleanup-visibility.tsv];puts $ledger "wave\tbuffer\ttrue_leaf_input_count\ttop_port_count\tignored_hierarchical_boundary_pins"
  set deleted [eco_open clock-cleanup-deleted.tsv];puts $deleted "wave\tinstance\treference"
  set removed {};set wave 0
  foreach names $::clock_cleanup_waves {
    foreach name $names {
      eco_require [expr {$name in $::clock_cleanup_allowed && [regexp {/XU_ECO_clock_g[0-9][0-9][0-9][0-9]$} $name] && $name ni $removed}] {cleanup target outside exact added-clock whitelist}
      set cell [get_cells -quiet $name]
      eco_require [expr {[sizeof_collection $cell]==1 && [get_object_name $cell] eq $name && ![get_attribute $cell is_hierarchical] && [get_attribute $cell ref_name] eq {BUFV2_12TR40}}] {cleanup target missing/changed/original leaf}
      clock_cleanup_visibility $name $wave $ledger
    }
    # Complete the whole native visibility wave before its first mutation.
    foreach name $names {remove_cell [get_cells $name];lappend removed $name;puts $deleted "$wave\t$name\tBUFV2_12TR40"}
    flush $deleted;incr wave
  }
  close $ledger;close $deleted
  eco_require [expr {[lsort $removed] eq [lsort $::clock_cleanup_removed]}] {cleanup removed count/names differ from static source proof}
  eco_require [expr {[lsort [get_object_name [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}]]] eq [lsort $::clock_cleanup_macros]}] {cleanup altered original353 SRAM instances}
}
source [file join $::env(XU_ECO_PACKAGE) dc_apply.tcl]
