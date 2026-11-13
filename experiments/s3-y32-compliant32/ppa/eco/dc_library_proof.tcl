# Read-only native characterization query, not synthesis or ECO.
source [file join $::env(XU_ECO_PACKAGE) common.tcl]
set failed [catch {
  eco_config
  eco_libraries dc
  read_ddc $::eco_ddc
  current_design xu_soc_sysbus32_ppa_top
  eco_require [link] {DC library proof link failed}
  set ::eco_query_function_in_dc 1
  set cell [eco_buffer]
  set f [eco_open dc-library-proof.tsv]
  puts $f "library_cell\treference\tpin\tdirection\tfunction\tis_sequential"
  foreach_in_collection pin [get_lib_pins -of_objects $cell] {
    set direction [get_attribute $pin direction]
    set function {-}
    if {$direction eq {out}} {set function [get_attribute $pin function]}
    puts $f "[get_object_name $cell]\t$::eco_buffer_reference\t[file tail [get_object_name $pin]]\t$direction\t$function\t[get_attribute $cell is_sequential]"
  }
  close $f
  eco_finish DC_LIBRARY_FUNCTION_PROOF_COMPLETE.txt
} reason options]
if {$failed} {eco_failure $reason $options}
exit 0
