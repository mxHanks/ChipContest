# Query compatibility only. Native pin/clock/library objects remain unmodified.
set xu207_clock_map [open pin-clocks207.tsv w]
puts $xu207_clock_map "request\tpin_handle\tpin_name\tpin_class\tattribute_status\traw_attribute\tclock_handle\tclock_name\tclock_class\tdiagnostics"
set xu207_lib_map [open pin-lib207.tsv w]
puts $xu207_lib_map "pin_handle\tpin_name\towner_handle\towner_name\tlibcell_handle\tlibcell_name\tlibpin_handle\tlibpin_name"
set xu207_requests 0
set xu207_known_clocks [dict create]
foreach_in_collection c [all_clocks] {
  set n [get_object_name $c]
  if {[dict exists $xu207_known_clocks $n]} {error "XU207 duplicate native clock name: $n"}
  if {[get_attribute $c object_class] ne {clock}} {error "XU207 all_clocks returned nonclock: $n"}
  dict set xu207_known_clocks $n $c
}
proc xu207_row {fd values} {
  set clean {}
  foreach value $values {lappend clean [string map [list "\t" { } "\n" { | } "\r" { }] $value]}
  puts $fd [join $clean "\t"]
  flush $fd
}
proc xu207_pin_clocks {pins} {
  global xu207_clock_map xu207_requests xu207_known_clocks
  incr xu207_requests
  set result {};set seen [dict create]
  # A clocks attribute is read from one native pin/port at a time. In
  # particular, never reinterpret a multi-pin attribute list as one handle.
  foreach_in_collection p $pins {
    set name [get_object_name $p];set class [get_attribute $p object_class]
    if {$class ni {pin port}} {error "XU207 clocks requested on nonpin/nonport: $name"}
    set value {};set diagnostics {}
    set rc [catch {redirect -variable diagnostics {set value [get_attribute -quiet $p clocks]}} msg]
    if {[regexp {(^|\n)Error:} $diagnostics]} {
      xu207_row $xu207_clock_map [list $xu207_requests $p $name $class FAILED_NATIVE_DIAGNOSTICS $value {} {} {} "$diagnostics | $msg"]
      error "XU207 native clocks attribute emitted Error for $name"
    }
    if {$rc} {
      xu207_row $xu207_clock_map [list $xu207_requests $p $name $class UNAVAILABLE $value {} {} {} "$diagnostics | $msg"]
      error "XU207 native clocks attribute query failed for $name: $msg"
    }
    if {$value eq {}} {
      xu207_row $xu207_clock_map [list $xu207_requests $p $name $class ABSENT_OR_EMPTY {} {} {} {} "$diagnostics | $msg"]
      continue
    }
    if {[catch {sizeof_collection $value} count] || $count < 1} {
      xu207_row $xu207_clock_map [list $xu207_requests $p $name $class INVALID_COLLECTION $value {} {} {} "$diagnostics | $msg"]
      error "XU207 native clocks attribute is not a nonempty collection: $name"
    }
    foreach_in_collection c $value {
      set cname [get_object_name $c];set cclass [get_attribute $c object_class]
      if {$cclass ne {clock} || ![dict exists $xu207_known_clocks $cname]} {
        xu207_row $xu207_clock_map [list $xu207_requests $p $name $class INVALID_CLOCK_OBJECT $value $c $cname $cclass "$diagnostics | $msg"]
        error "XU207 pin clocks attribute has non-native/unregistered clock: $name/$cname"
      }
      xu207_row $xu207_clock_map [list $xu207_requests $p $name $class NATIVE_CLOCK_COLLECTION $value $c $cname $cclass "$diagnostics | $msg"]
      if {![dict exists $seen $cname]} {
        dict set seen $cname 1
        set result [add_to_collection $result $c]
      }
    }
  }
  return $result
}
proc xu207_libpin {pin} {
  global xu207_lib_map
  if {[sizeof_collection $pin] != 1 || [get_attribute $pin object_class] ne {pin}} {error {XU207 libpin requires exactly one design pin}}
  set owner [get_cells -quiet -of_objects $pin]
  if {[sizeof_collection $owner] != 1} {error {XU207 libpin owner absent/ambiguous}}
  # Both get_lib_cells -of_objects design-cell (actual130/132) and
  # get_lib_pins -of_objects lib-cell (actual177) already ran natively.
  set lc [get_lib_cells -of_objects $owner]
  if {[sizeof_collection $lc] != 1} {error {XU207 native owner library cell absent/ambiguous}}
  set pn [get_object_name $pin];set on [get_object_name $owner];set ln [get_object_name $lc]
  if {[string first "$on/" $pn] != 0} {error {XU207 exact design pin is not below its native owner}}
  set leaf [string range $pn [expr {[string length $on]+1}] end]
  set want "$ln/$leaf";set result {};set count 0
  foreach_in_collection lp [get_lib_pins -of_objects $lc] {
    if {[get_object_name $lp] eq $want} {incr count;set result $lp}
  }
  if {$count != 1} {error "XU207 exact native library pin absent/ambiguous: $pn -> $want"}
  xu207_row $xu207_lib_map [list $pin $pn $owner $on $lc $ln $result [get_object_name $result]]
  return $result
}
