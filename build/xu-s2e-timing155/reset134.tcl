
set xu_before_cells [sizeof_collection [get_cells -hierarchical -filter {is_hierarchical == false}]]
set xu_parent_counts [dict create]
foreach_in_collection h [get_cells -hierarchical -filter {is_hierarchical == true}] {dict incr xu_parent_counts [get_attribute $h ref_name]}
set xu_original_driver [dict create]
set f [open reset-preflight.tsv w]
puts $f "reset_pin\tref\tleaf_connections\tunique_owner_ref\toriginal_driver"
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg}]
set p [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN}]
set owner [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DSNQV0_12TR40} || [sizeof_collection $p]!=1 || [get_attribute $p direction] ne "in" || [sizeof_collection $owner]!=1} {error {exact reset endpoint identity changed}}
set owner_ref [get_attribute $owner ref_name]
if {![dict exists $xu_parent_counts $owner_ref] || [dict get $xu_parent_counts $owner_ref]!=1} {error {reset owner design is shared}}
set n [get_nets -of_objects $p]
if {[sizeof_collection $n]!=1} {error {reset endpoint net missing or ambiguous}}
set con [all_connected -leaf $n]
set drivers {}
foreach_in_collection o $con {
 if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend drivers [get_object_name $o]}
}
if {[llength $drivers]!=1} {error {reset endpoint original driver ambiguous}}
dict set xu_original_driver [get_object_name $p] [lindex $drivers 0]
puts $f [join [list [get_object_name $p] [get_attribute $c ref_name] [get_object_name $con] $owner_ref [lindex $drivers 0]] "\t"]
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg}]
set p [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN}]
set owner [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DSNQNV0_12TR40} || [sizeof_collection $p]!=1 || [get_attribute $p direction] ne "in" || [sizeof_collection $owner]!=1} {error {exact reset endpoint identity changed}}
set owner_ref [get_attribute $owner ref_name]
if {![dict exists $xu_parent_counts $owner_ref] || [dict get $xu_parent_counts $owner_ref]!=1} {error {reset owner design is shared}}
set n [get_nets -of_objects $p]
if {[sizeof_collection $n]!=1} {error {reset endpoint net missing or ambiguous}}
set con [all_connected -leaf $n]
set drivers {}
foreach_in_collection o $con {
 if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend drivers [get_object_name $o]}
}
if {[llength $drivers]!=1} {error {reset endpoint original driver ambiguous}}
dict set xu_original_driver [get_object_name $p] [lindex $drivers 0]
puts $f [join [list [get_object_name $p] [get_attribute $c ref_name] [get_object_name $con] $owner_ref [lindex $drivers 0]] "\t"]
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg}]
set p [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}]
set owner [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DRNQV0_12TR40} || [sizeof_collection $p]!=1 || [get_attribute $p direction] ne "in" || [sizeof_collection $owner]!=1} {error {exact reset endpoint identity changed}}
set owner_ref [get_attribute $owner ref_name]
if {![dict exists $xu_parent_counts $owner_ref] || [dict get $xu_parent_counts $owner_ref]!=1} {error {reset owner design is shared}}
set n [get_nets -of_objects $p]
if {[sizeof_collection $n]!=1} {error {reset endpoint net missing or ambiguous}}
set con [all_connected -leaf $n]
set drivers {}
foreach_in_collection o $con {
 if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend drivers [get_object_name $o]}
}
if {[llength $drivers]!=1} {error {reset endpoint original driver ambiguous}}
dict set xu_original_driver [get_object_name $p] [lindex $drivers 0]
puts $f [join [list [get_object_name $p] [get_attribute $c ref_name] [get_object_name $con] $owner_ref [lindex $drivers 0]] "\t"]
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg}]
set p [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}]
set owner [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DRNQV0_12TR40} || [sizeof_collection $p]!=1 || [get_attribute $p direction] ne "in" || [sizeof_collection $owner]!=1} {error {exact reset endpoint identity changed}}
set owner_ref [get_attribute $owner ref_name]
if {![dict exists $xu_parent_counts $owner_ref] || [dict get $xu_parent_counts $owner_ref]!=1} {error {reset owner design is shared}}
set n [get_nets -of_objects $p]
if {[sizeof_collection $n]!=1} {error {reset endpoint net missing or ambiguous}}
set con [all_connected -leaf $n]
set drivers {}
foreach_in_collection o $con {
 if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend drivers [get_object_name $o]}
}
if {[llength $drivers]!=1} {error {reset endpoint original driver ambiguous}}
dict set xu_original_driver [get_object_name $p] [lindex $drivers 0]
puts $f [join [list [get_object_name $p] [get_attribute $c ref_name] [get_object_name $con] $owner_ref [lindex $drivers 0]] "\t"]
set c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg}]
set p [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}]
set owner [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2}]
if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DRNQV0_12TR40} || [sizeof_collection $p]!=1 || [get_attribute $p direction] ne "in" || [sizeof_collection $owner]!=1} {error {exact reset endpoint identity changed}}
set owner_ref [get_attribute $owner ref_name]
if {![dict exists $xu_parent_counts $owner_ref] || [dict get $xu_parent_counts $owner_ref]!=1} {error {reset owner design is shared}}
set n [get_nets -of_objects $p]
if {[sizeof_collection $n]!=1} {error {reset endpoint net missing or ambiguous}}
set con [all_connected -leaf $n]
set drivers {}
foreach_in_collection o $con {
 if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend drivers [get_object_name $o]}
}
if {[llength $drivers]!=1} {error {reset endpoint original driver ambiguous}}
dict set xu_original_driver [get_object_name $p] [lindex $drivers 0]
puts $f [join [list [get_object_name $p] [get_attribute $c ref_name] [get_object_name $con] $owner_ref [lindex $drivers 0]] "\t"]
close $f
set lc [get_lib_cells -quiet {scc40nll_vhsc40_rvt_ss_v0p99_125c_basic/CLKINV0_12TR40}]
if {[sizeof_collection $lc]!=1} {error {actual library candidate missing}}

# Actual55 stopped here: an unset DC dont_use attribute returns the empty
# string, which is not a Tcl boolean. Preserve the raw value; do not invent
# or set a library attribute. The exact same DB and fresh own posthold PT false palette
# record are frozen by the Python preflight, and native insertion must accept.
set xu_dont_use [get_attribute -quiet $lc dont_use]
set xu_dont_use_basis dc_explicit_false
if {$xu_dont_use eq ""} {
 set xu_dont_use_basis dc_absent_with_fresh_own_PT_palette_false_native_validation_required
} elseif {![string is boolean -strict $xu_dont_use]} {
 error {DC dont_use attribute is not a valid boolean}
} elseif {$xu_dont_use} {
 error {actual library candidate prohibited in DC}
}
set f [open reset-library-preflight.tsv w]
puts $f "libcell\tdc_dont_use_raw\tacceptance_basis"
puts $f [join [list [get_object_name $lc] $xu_dont_use $xu_dont_use_basis] "\t"]
close $f
set li [get_lib_pins -of_objects $lc -filter {direction == in}]
set lo [get_lib_pins -of_objects $lc -filter {direction == out}]
if {[sizeof_collection $li]!=1 || [sizeof_collection $lo]!=1 || [get_object_name $li] ne "scc40nll_vhsc40_rvt_ss_v0p99_125c_basic/CLKINV0_12TR40/I" || [get_object_name $lo] ne "scc40nll_vhsc40_rvt_ss_v0p99_125c_basic/CLKINV0_12TR40/ZN"} {error {actual library topology changed}}
# insert_buffer -inverter_pair performs the native inverter-function check.
# A name or absent PT function attribute is never taken as a logic proof.
set f [open inserted-reset-cells.tsv w]
puts $f "endpoint\tcell\tref"
current_instance {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu}
set p [get_pins -quiet {erst_reset_r_reg/SDN}]
if {[sizeof_collection $p]!=1} {error {scoped exact reset pin missing}}
set added [insert_buffer -inverter_pair -no_of_cells 4 -new_cell_names {xu_reset134_0} -new_net_names {xu_reset134_net_0} $p $lc]
if {[sizeof_collection $added]!=8} {error {native inverter-pair insertion failed}}
current_instance
set names [get_object_name $added]
foreach_in_collection c $added {if {[get_attribute $c ref_name] ne {CLKINV0_12TR40}} {error {inserted cell identity differs}};puts $f [join [list {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN} [get_object_name $c] [get_attribute $c ref_name]] "\t"]}
set cursor [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN}]
set seen {}
for {set k 0} {$k<8} {incr k} {
 set n [get_nets -of_objects $cursor]
 if {[sizeof_collection $n]!=1} {error {new reset chain net missing}}
 set con [all_connected -leaf $n]
 if {[sizeof_collection $con]!=2} {error {new reset buffer branch gained another receiver}}
 set dp {}
 foreach_in_collection o $con {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}
 if {[llength $dp]!=1} {error {new reset chain driver ambiguous}}
 set driver [get_pins -quiet [lindex $dp 0]]
 set c [get_cells -of_objects $driver]
 set cn [get_object_name $c]
 if {[lsearch -exact $names $cn]<0 || [lsearch -exact $seen $cn]>=0 || [get_attribute $c ref_name] ne "CLKINV0_12TR40"} {error {new reset chain topology differs}}
 lappend seen $cn
 set cursor [get_pins -of_objects $c -filter {direction == in}]
 if {[sizeof_collection $cursor]!=1} {error {new reset buffer input differs}}
}
if {[lsort $seen] ne [lsort $names]} {error {inserted reset chain has unvisited cells}}
set dp {}
foreach_in_collection o [all_connected -leaf [get_nets -of_objects $cursor]] {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}
if {$dp ne [list [dict get $xu_original_driver {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN}]]} {error {reset chain did not retain original driver}}
current_instance {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu}
set p [get_pins -quiet {erst_reset_r_r_reg/SDN}]
if {[sizeof_collection $p]!=1} {error {scoped exact reset pin missing}}
set added [insert_buffer -inverter_pair -no_of_cells 4 -new_cell_names {xu_reset134_1} -new_net_names {xu_reset134_net_1} $p $lc]
if {[sizeof_collection $added]!=8} {error {native inverter-pair insertion failed}}
current_instance
set names [get_object_name $added]
foreach_in_collection c $added {if {[get_attribute $c ref_name] ne {CLKINV0_12TR40}} {error {inserted cell identity differs}};puts $f [join [list {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN} [get_object_name $c] [get_attribute $c ref_name]] "\t"]}
set cursor [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN}]
set seen {}
for {set k 0} {$k<8} {incr k} {
 set n [get_nets -of_objects $cursor]
 if {[sizeof_collection $n]!=1} {error {new reset chain net missing}}
 set con [all_connected -leaf $n]
 if {[sizeof_collection $con]!=2} {error {new reset buffer branch gained another receiver}}
 set dp {}
 foreach_in_collection o $con {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}
 if {[llength $dp]!=1} {error {new reset chain driver ambiguous}}
 set driver [get_pins -quiet [lindex $dp 0]]
 set c [get_cells -of_objects $driver]
 set cn [get_object_name $c]
 if {[lsearch -exact $names $cn]<0 || [lsearch -exact $seen $cn]>=0 || [get_attribute $c ref_name] ne "CLKINV0_12TR40"} {error {new reset chain topology differs}}
 lappend seen $cn
 set cursor [get_pins -of_objects $c -filter {direction == in}]
 if {[sizeof_collection $cursor]!=1} {error {new reset buffer input differs}}
}
if {[lsort $seen] ne [lsort $names]} {error {inserted reset chain has unvisited cells}}
set dp {}
foreach_in_collection o [all_connected -leaf [get_nets -of_objects $cursor]] {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}
if {$dp ne [list [dict get $xu_original_driver {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN}]]} {error {reset chain did not retain original driver}}
current_instance {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0}
set p [get_pins -quiet {q_reg/RDN}]
if {[sizeof_collection $p]!=1} {error {scoped exact reset pin missing}}
set added [insert_buffer -inverter_pair -no_of_cells 4 -new_cell_names {xu_reset134_2} -new_net_names {xu_reset134_net_2} $p $lc]
if {[sizeof_collection $added]!=8} {error {native inverter-pair insertion failed}}
current_instance
set names [get_object_name $added]
foreach_in_collection c $added {if {[get_attribute $c ref_name] ne {CLKINV0_12TR40}} {error {inserted cell identity differs}};puts $f [join [list {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN} [get_object_name $c] [get_attribute $c ref_name]] "\t"]}
set cursor [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}]
set seen {}
for {set k 0} {$k<8} {incr k} {
 set n [get_nets -of_objects $cursor]
 if {[sizeof_collection $n]!=1} {error {new reset chain net missing}}
 set con [all_connected -leaf $n]
 if {[sizeof_collection $con]!=2} {error {new reset buffer branch gained another receiver}}
 set dp {}
 foreach_in_collection o $con {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}
 if {[llength $dp]!=1} {error {new reset chain driver ambiguous}}
 set driver [get_pins -quiet [lindex $dp 0]]
 set c [get_cells -of_objects $driver]
 set cn [get_object_name $c]
 if {[lsearch -exact $names $cn]<0 || [lsearch -exact $seen $cn]>=0 || [get_attribute $c ref_name] ne "CLKINV0_12TR40"} {error {new reset chain topology differs}}
 lappend seen $cn
 set cursor [get_pins -of_objects $c -filter {direction == in}]
 if {[sizeof_collection $cursor]!=1} {error {new reset buffer input differs}}
}
if {[lsort $seen] ne [lsort $names]} {error {inserted reset chain has unvisited cells}}
set dp {}
foreach_in_collection o [all_connected -leaf [get_nets -of_objects $cursor]] {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}
if {$dp ne [list [dict get $xu_original_driver {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}]]} {error {reset chain did not retain original driver}}
current_instance {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1}
set p [get_pins -quiet {q_reg/RDN}]
if {[sizeof_collection $p]!=1} {error {scoped exact reset pin missing}}
set added [insert_buffer -inverter_pair -no_of_cells 4 -new_cell_names {xu_reset134_3} -new_net_names {xu_reset134_net_3} $p $lc]
if {[sizeof_collection $added]!=8} {error {native inverter-pair insertion failed}}
current_instance
set names [get_object_name $added]
foreach_in_collection c $added {if {[get_attribute $c ref_name] ne {CLKINV0_12TR40}} {error {inserted cell identity differs}};puts $f [join [list {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN} [get_object_name $c] [get_attribute $c ref_name]] "\t"]}
set cursor [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}]
set seen {}
for {set k 0} {$k<8} {incr k} {
 set n [get_nets -of_objects $cursor]
 if {[sizeof_collection $n]!=1} {error {new reset chain net missing}}
 set con [all_connected -leaf $n]
 if {[sizeof_collection $con]!=2} {error {new reset buffer branch gained another receiver}}
 set dp {}
 foreach_in_collection o $con {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}
 if {[llength $dp]!=1} {error {new reset chain driver ambiguous}}
 set driver [get_pins -quiet [lindex $dp 0]]
 set c [get_cells -of_objects $driver]
 set cn [get_object_name $c]
 if {[lsearch -exact $names $cn]<0 || [lsearch -exact $seen $cn]>=0 || [get_attribute $c ref_name] ne "CLKINV0_12TR40"} {error {new reset chain topology differs}}
 lappend seen $cn
 set cursor [get_pins -of_objects $c -filter {direction == in}]
 if {[sizeof_collection $cursor]!=1} {error {new reset buffer input differs}}
}
if {[lsort $seen] ne [lsort $names]} {error {inserted reset chain has unvisited cells}}
set dp {}
foreach_in_collection o [all_connected -leaf [get_nets -of_objects $cursor]] {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}
if {$dp ne [list [dict get $xu_original_driver {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}]]} {error {reset chain did not retain original driver}}
current_instance {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2}
set p [get_pins -quiet {q_reg/RDN}]
if {[sizeof_collection $p]!=1} {error {scoped exact reset pin missing}}
set added [insert_buffer -inverter_pair -no_of_cells 4 -new_cell_names {xu_reset134_4} -new_net_names {xu_reset134_net_4} $p $lc]
if {[sizeof_collection $added]!=8} {error {native inverter-pair insertion failed}}
current_instance
set names [get_object_name $added]
foreach_in_collection c $added {if {[get_attribute $c ref_name] ne {CLKINV0_12TR40}} {error {inserted cell identity differs}};puts $f [join [list {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN} [get_object_name $c] [get_attribute $c ref_name]] "\t"]}
set cursor [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}]
set seen {}
for {set k 0} {$k<8} {incr k} {
 set n [get_nets -of_objects $cursor]
 if {[sizeof_collection $n]!=1} {error {new reset chain net missing}}
 set con [all_connected -leaf $n]
 if {[sizeof_collection $con]!=2} {error {new reset buffer branch gained another receiver}}
 set dp {}
 foreach_in_collection o $con {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}
 if {[llength $dp]!=1} {error {new reset chain driver ambiguous}}
 set driver [get_pins -quiet [lindex $dp 0]]
 set c [get_cells -of_objects $driver]
 set cn [get_object_name $c]
 if {[lsearch -exact $names $cn]<0 || [lsearch -exact $seen $cn]>=0 || [get_attribute $c ref_name] ne "CLKINV0_12TR40"} {error {new reset chain topology differs}}
 lappend seen $cn
 set cursor [get_pins -of_objects $c -filter {direction == in}]
 if {[sizeof_collection $cursor]!=1} {error {new reset buffer input differs}}
}
if {[lsort $seen] ne [lsort $names]} {error {inserted reset chain has unvisited cells}}
set dp {}
foreach_in_collection o [all_connected -leaf [get_nets -of_objects $cursor]] {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}
if {$dp ne [list [dict get $xu_original_driver {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}]]} {error {reset chain did not retain original driver}}
close $f
if {[sizeof_collection [get_cells -hierarchical -filter {is_hierarchical == false}]]!=$xu_before_cells+40} {error {unexpected reset insertion cell count}}
