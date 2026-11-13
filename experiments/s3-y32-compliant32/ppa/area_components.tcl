# Read-only, disjoint accelerator leaf classification. No compile/SDC mutation.
set xu_component_in [open leaf-inventory.tsv r]
set xu_header [gets $xu_component_in]
if {$xu_header ne "instance\treference\tarea_library_units\tclassification\tcharged_scope"} {
  error {unexpected leaf inventory header}
}
set xu_groups [dict create]
set xu_charged_sum 0.0
set xu_charged_count 0
while {[gets $xu_component_in xu_line] >= 0} {
  set xu_cols [split $xu_line \t]
  if {[llength $xu_cols] != 5} {error "bad leaf row: $xu_line"}
  lassign $xu_cols xu_inst xu_ref xu_area xu_category xu_scope
  if {$xu_scope eq {none}} {continue}
  set xu_component $xu_scope
  if {$xu_scope eq {dma}} {
    set xu_dma_prefix ${charge_dma}
    set xu_rel [string range $xu_inst [string length $xu_dma_prefix] end]
    if {[string match {u_core/weights/*} $xu_rel]} {set xu_component weights}
    if {[string match {u_core/bias/*} $xu_rel]} {set xu_component bias}
    if {[string match {u_core/xs_*/*} $xu_rel]} {
      if {$sysbus32_expected_x_macros == 16} {set xu_component x_physical_sram_buffers} else {set xu_component x_double_buffers}
    }
    if {[string match {u_core/engines_*/*} $xu_rel]} {set xu_component engines_64pe}
    if {$xu_component eq {dma} && [string match {u_core/*} $xu_rel]} {set xu_component core_fifo_and_control}
    if {$xu_component eq {dma}} {set xu_component dma32_frontend_and_scheduler}
  }
  set xu_key [list $xu_component $xu_category]
  if {![dict exists $xu_groups $xu_key]} {dict set xu_groups $xu_key [list 0 0.0]}
  lassign [dict get $xu_groups $xu_key] xu_n xu_a
  dict set xu_groups $xu_key [list [expr {$xu_n+1}] [expr {$xu_a+$xu_area}]]
  incr xu_charged_count
  set xu_charged_sum [expr {$xu_charged_sum+$xu_area}]
}
close $xu_component_in
set xu_component_out [open area-components.tsv w]
puts $xu_component_out "disjoint_component\tclassification\tleaf_count\tarea_library_units"
foreach xu_key [lsort [dict keys $xu_groups]] {
  lassign $xu_key xu_name xu_category
  lassign [dict get $xu_groups $xu_key] xu_n xu_a
  puts $xu_component_out "$xu_name\t$xu_category\t$xu_n\t[format %.9f $xu_a]"
}
puts $xu_component_out "TOTAL_CHARGED\tall_charged\t$xu_charged_count\t[format %.9f $xu_charged_sum]"
close $xu_component_out
if {abs($xu_charged_sum-($charged_logic_area+$charged_sram_area)) > 0.001} {
  error {disjoint component area does not reconcile with charged leaf total}
}
