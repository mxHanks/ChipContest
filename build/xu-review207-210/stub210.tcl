# Independent compatibility checks. Native collections are mocked here; this
# verifies Tcl control flow only and never stands in for actual PrimeTime.
set mock_names [dict create p1 {top/dp_gt0.vec_31_dfflr/qout_r_reg[0]/CK} p2 top/reset/RDN p3 top/io/E q1 top/out/Q c1 hf c2 pll c3 lf badclock rogue owner {top/dp_gt0.vec_31_dfflr/qout_r_reg[0]} lc lib/DRNQV0 lpCK lib/DRNQV0/CK lpD lib/DRNQV0/D]
set mock_classes [dict create p1 pin p2 pin p3 port q1 pin c1 clock c2 clock c3 clock badclock clock owner cell lc lib_cell lpCK lib_pin lpD lib_pin]
set mock_collections [dict create _all {c1 c2 c3} _both {p1 p2} _single p1 _clocks12 {c1 c2} _clocks23 {c2 c3} _invalidclock {badclock} _nonclock {q1} _owner owner _libcell lc _libpins {lpD lpCK}]
set mock_pin_clocks [dict create p1 _clocks12 p2 _clocks23 p3 {}]
set mock_attr_reads {}
set mock_throw 0
set mock_diagnostic {}
set mock_pending_diagnostic {}
proc members {collection} {
  global mock_collections mock_names
  if {$collection eq {}} {return {}}
  if {[dict exists $mock_collections $collection]} {return [dict get $mock_collections $collection]}
  foreach x $collection {if {![dict exists $mock_names $x]} {error "unknown mock handle: $x"}}
  return $collection
}
proc foreach_in_collection {var collection script} {
  upvar 1 $var value
  foreach item [members $collection] {set value $item;uplevel 1 $script}
}
proc sizeof_collection {collection} {return [llength [members $collection]]}
proc all_clocks {} {return _all}
proc get_clocks {args} {error {unsupported API must never be called}}
proc get_object_name {collection} {
  global mock_names
  set result {}
  foreach item [members $collection] {lappend result [dict get $mock_names $item]}
  if {[llength $result] == 1} {return [lindex $result 0]}
  return $result
}
proc get_attribute {args} {
  global mock_classes mock_pin_clocks mock_attr_reads mock_throw mock_diagnostic mock_pending_diagnostic
  if {[lindex $args 0] eq {-quiet}} {set args [lrange $args 1 end]}
  lassign $args object attr
  if {[sizeof_collection $object] != 1} {error {multi-object attribute read forbidden}}
  set key [lindex [members $object] 0]
  if {$attr eq {object_class}} {return [dict get $mock_classes $key]}
  if {$attr eq {clocks}} {
    lappend mock_attr_reads $key
    if {$mock_throw} {error {unsupported attribute}}
    set mock_pending_diagnostic $mock_diagnostic
    return [dict get $mock_pin_clocks $key]
  }
  error "unexpected attribute $attr"
}
proc redirect {args} {
  global mock_pending_diagnostic
  if {[llength $args] != 3 || [lindex $args 0] ne {-variable}} {error {unexpected redirect}}
  upvar 1 [lindex $args 1] diag
  set mock_pending_diagnostic {}
  set rc [catch {uplevel 1 [lindex $args 2]} msg options]
  set diag $mock_pending_diagnostic
  return -options $options $msg
}
proc add_to_collection {left right} {return [lsort -unique [concat [members $left] [members $right]]]}
proc get_cells {args} {
  if {$args ne {-quiet -of_objects p1}} {error "unexpected owner query $args"}
  return _owner
}
proc get_lib_cells {args} {
  if {$args ne {-of_objects _owner}} {error "design-pin lib lookup is forbidden: $args"}
  return _libcell
}
proc get_lib_pins {args} {
  if {$args ne {-of_objects _libcell}} {error "design-pin lib lookup is forbidden: $args"}
  return _libpins
}
proc must {condition message} {if {![uplevel 1 [list expr $condition]]} {error $message}}
proc fail_expected {script pattern} {
  set rc [catch {uplevel 1 $script} msg]
  if {!$rc || ![string match $pattern $msg]} {error "expected failure $pattern, actual rc=$rc: $msg"}
}
if {[llength $argv] != 1} {error {pass the compat207.tcl path}}
source [lindex $argv 0]
set result [xu207_pin_clocks _both]
must {[get_object_name $result] eq {hf pll lf}} {multi-pin clocks union lost overlap or ordering}
must {$mock_attr_reads eq {p1 p2}} {pin clocks attributes were not read one pin at a time}
set result [xu207_pin_clocks p3]
must {$result eq {}} {empty pin clocks became a fabricated clock}
set result [xu207_pin_clocks {}]
must {$result eq {}} {empty pin collection became a fabricated clock}
set result [xu207_pin_clocks {p1 p1}]
must {[sizeof_collection $result] == 2} {duplicate clock union is not unique}
set mock_throw 1
fail_expected {xu207_pin_clocks p1} {*attribute query failed*}
set mock_throw 0
set saved [dict get $mock_pin_clocks p1]
dict set mock_pin_clocks p1 {unknown_handle}
fail_expected {xu207_pin_clocks p1} {*not a nonempty collection*}
dict set mock_pin_clocks p1 _invalidclock
fail_expected {xu207_pin_clocks p1} {*non-native/unregistered clock*}
dict set mock_pin_clocks p1 _nonclock
fail_expected {xu207_pin_clocks p1} {*non-native/unregistered clock*}
dict set mock_pin_clocks p1 $saved
fail_expected {xu207_pin_clocks owner} {*nonpin/nonport*}
set mock_diagnostic {Warning: optional metadata warning}
set result [xu207_pin_clocks p3]
must {$result eq {}} {warning/empty produced a clock}
set mock_diagnostic {Error: unsupported native attribute (ATTR-1)}
fail_expected {xu207_pin_clocks p1} {*emitted Error*}
set mock_diagnostic {}
set result [xu207_libpin p1]
must {[get_object_name $result] eq {lib/DRNQV0/CK}} {library-pin mapping was not exact}
dict set mock_names lpCK {lib/DRNQV0/not_CK}
fail_expected {xu207_libpin p1} {*absent/ambiguous*}
close $xu207_clock_map
close $xu207_lib_map
set f [open pin-clocks207.tsv r];set rows [read $f];close $f
must {[string first {ABSENT_OR_EMPTY} $rows] >= 0} {empty metadata sentinel absent}
must {[string first {INVALID_CLOCK_OBJECT} $rows] >= 0} {bad clock diagnostics absent}
must {[string first {NATIVE_CLOCK_COLLECTION} $rows] >= 0} {native clock mapping absent}
must {[string first {UNAVAILABLE} $rows] >= 0} {unsupported metadata diagnostics absent}
puts {XU210_TCL_STUB_PASSED_15_CASES_NOT_NATIVE_QUALIFICATION}
