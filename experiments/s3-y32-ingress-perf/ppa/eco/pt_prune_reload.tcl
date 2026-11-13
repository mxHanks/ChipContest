# Fresh PT after exact dead-cone DC pruning. Original periods/SDC unchanged.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
set failed [catch {
  eco_config
  eco_load_pt $::eco_mapped
  eco_native_proof
  eco_snapshot persisted
  eco_sha $::eco_prune_deleted $::eco_prune_deleted_sha
  set f [open $::eco_prune_deleted r]
  eco_require [expr {[string map [list {\t} "\t"] [gets $f]] eq "wave\tinstance\treference\tis_sequential"}] {invalid proven deletion ledger header}
  set deleted [dict create]; set deleted_state [dict create]
  while {[gets $f line] >= 0} {
    set fields [split $line \t]
    eco_require [expr {[llength $fields] == 4}] {invalid deletion ledger row}
    lassign $fields wave name ref sequential
    eco_require [expr {![dict exists $deleted $name] && ![string match RAMSP* $ref] && $sequential in {true false}}] {duplicate/SRAM/unclassified deletion}
    dict set deleted $name $ref
    if {$sequential eq {true}} {dict set deleted_state $name 1}
    eco_require [expr {[sizeof_collection [get_cells -quiet $name]] == 0}] "deleted leaf remains after DC persistence: $name"
  }
  close $f
  eco_require [expr {[dict size $deleted] == 1796 && [dict size $deleted_state] == 36}] {persisted deletion whitelist count differs}
  set f [open $::eco_reference_clocks r]
  eco_require [expr {[string map [list {\t} "\t"] [gets $f]] eq "pin\tclocks"}] {invalid seed clock-association header}
  set expected [dict create]
  while {[gets $f line] >= 0} {
    set line [string map [list {\t} "\t"] $line]
    set fields [split $line \t]
    eco_require [expr {[llength $fields] == 2 && ![dict exists $expected [lindex $fields 0]]}] {invalid/duplicate seed clock row}
    dict set expected [lindex $fields 0] [lindex $fields 1]
  }
  close $f
  set actual [eco_clocks]
  set kept [eco_open retained-clock-association.tsv]; puts $kept "pin\tclocks"
  set gone [eco_open removed-clock-association.tsv]; puts $gone "pin\tclocks\tproven_deleted_parent"
  set removed_clocks 0; set removed_parents [dict create]
  dict for {pin clocks} $expected {
    if {[dict exists $actual $pin]} {
      eco_require [expr {[dict get $actual $pin] eq $clocks}] "retained seed clock association changed: $pin"
      puts $kept "$pin\t$clocks"
    } else {
      set parent [eco_parent $pin]
      eco_require [dict exists $deleted_state $parent] "clock pin disappeared outside exact dead-state whitelist: $pin"
      eco_require [expr {![string match */CLK $pin] || [dict get $deleted $parent] ne {RAMSP1024X16}}] {SRAM CLK loss forbidden}
      dict set removed_parents $parent 1
      incr removed_clocks
      puts $gone "$pin\t$clocks\t$parent"
    }
  }
  close $kept; close $gone
  eco_require [expr {[dict size $removed_parents] == 36}] {each exact deleted state leaf must explain its original clock pin}
  eco_require [expr {[dict size $actual] == [dict size $expected] - $removed_clocks}] {unexpected new/lost retained register clock pin}
  dict for {pin clocks} $actual {eco_require [dict exists $expected $pin] "unexpected clock endpoint added: $pin"}
  set macros [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}]
  eco_require [expr {[sizeof_collection $macros] == 353}] {all353 SRAM leaves must survive}
  foreach_in_collection macro $macros {
    set pin [get_object_name $macro]/CLK
    eco_require [expr {[dict exists $expected $pin] && [dict exists $actual $pin] && [dict get $expected $pin] eq [dict get $actual $pin]}] "SRAM CLK association changed/lost: $pin"
  }
  eco_assert_clocks $actual
  eco_reports persisted
  eco_finish PRUNE_RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
