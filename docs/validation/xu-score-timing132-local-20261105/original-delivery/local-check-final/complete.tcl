foreach p $argv {set f [open $p];set s [read $f];close $f;if {![info complete $s]} {error "incomplete Tcl"};puts COMPLETE}
