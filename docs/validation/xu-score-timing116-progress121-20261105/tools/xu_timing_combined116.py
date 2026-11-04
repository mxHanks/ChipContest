#!/usr/bin/env python3
"""Independent bounded dead-cone cleanup plus reset delay on exact actual95.

No historical directory, source RTL, DB or timing constraint is written. Native
DC/PT/FM are mandatory. A completed diagnostic is never timing qualification.
Python 3.6 compatible; launch with the separate frozen-hash launcher.
"""
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import time
import traceback

B = Path.home() / 'Desktop/xu-score-optimization-20261102'
PARENT_NAME = 'full-soc-unloaded-cell-cleanup-20261104-95'
OUT_NAME = 'full-soc-timing-combined-20261105-116'
SDC_SHA = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
SCOPE_SHA = '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e'
DB_SHAS = {'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723',
           'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'}
PRODUCER_SHA = 'bc4070bdbd7ac6ae48f7ead1599a3a1a143b9872a7c4a9ef76aad3b677b25040'
FM49_SHA = '9d1664ecad99d038cacd6db017a9b79f480f788d7c946dc3df0590d7c652ba06'
STAGES = [
 ('full-soc-cap-size-repair-20261103-49', '3d9f222369a19b48eeec69ab63405d6aea579aa3f99d2b7a16ef2458f8cbaf28', '5df0b568d1751d19388edb33d244f8b19051a9fa7c77b24a2e023bf1e2ee4b4c'),
 ('full-soc-unloaded-cell-cleanup-20261103-50', '7aea258d2d83d6c8d10815f8a612b16948ab3e0e5e8ea8674b90652b47e76ad7', '9b7265e703ea62487c5b5c39c66adf245e720ac02f1066063cfd0eb4753f460c'),
 ('full-soc-unloaded-cell-cleanup-20261104-63', 'b321edb63b16b5b9c1afd2d02b8633cf4f524b76f13bf2c67cd103ce9a62d323', '58af01a6448a6dc79ff7afb488ffd9588114d32706d1b8fd3f10ff6ae09173f2'),
 ('full-soc-unloaded-cell-cleanup-20261104-73', '56c44be592b6c958c6675670363dcdfc2550e4218c2bbfa62f7b5ecdb55ca825', 'fdf52301282ad5cd9854b1f28aa23073c4818ff1d72b6cb8f854ce44e8117ff3'),
 ('full-soc-unloaded-cell-cleanup-20261104-79', 'cffb46c1d14be40ba41650075255e4a4e21af98283f5881b3e2fd25246fd1f5b', '5a1e30ca4c9f14a8eabb349575a9f3069038c15ec38577edeacf0c9613cfa048'),
 (PARENT_NAME, '3d65d7a3c4753961a331bd9a69121c93cd504639cd409c6dfca5784e44779aca', 'a38717c9f775148c54f748343c77da9cf3bf593fec72e5bfc706ee5f3043ce59')]
BASE = 'u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/'
ENDPOINTS = [(BASE + 'u_sirv_aon/u_sirv_pmu/erst_reset_r_reg', 'SDN', 'DSNQV0_12TR40'),
             (BASE + 'u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg', 'SDN', 'DSNQNV0_12TR40')]
ENDPOINTS += [(BASE + 'aonrst_catch/reset_n_catch_reg/reg_%d/q_reg' % i,
               'RDN', 'DRNQV0_12TR40') for i in range(3)]
LIB = 'scc40nll_vhsc40_rvt_ss_v0p99_125c_basic/CLKINV0_12TR40'
# Populated by the local handoff builder from the inspected original61 function.
RESET_TCL = '\nset xu_before_cells [sizeof_collection [get_cells -hierarchical -filter {is_hierarchical == false}]]\nset xu_parent_counts [dict create]\nforeach_in_collection h [get_cells -hierarchical -filter {is_hierarchical == true}] {dict incr xu_parent_counts [get_attribute $h ref_name]}\nset xu_original_driver [dict create]\nset f [open reset-preflight.tsv w]\nputs $f "reset_pin\\tref\\tleaf_connections\\tunique_owner_ref\\toriginal_driver"\nset c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg}]\nset p [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN}]\nset owner [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu}]\nif {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DSNQV0_12TR40} || [sizeof_collection $p]!=1 || [get_attribute $p direction] ne "in" || [sizeof_collection $owner]!=1} {error {exact reset endpoint identity changed}}\nset owner_ref [get_attribute $owner ref_name]\nif {![dict exists $xu_parent_counts $owner_ref] || [dict get $xu_parent_counts $owner_ref]!=1} {error {reset owner design is shared}}\nset n [get_nets -of_objects $p]\nif {[sizeof_collection $n]!=1} {error {reset endpoint net missing or ambiguous}}\nset con [all_connected -leaf $n]\nset drivers {}\nforeach_in_collection o $con {\n if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend drivers [get_object_name $o]}\n}\nif {[llength $drivers]!=1} {error {reset endpoint original driver ambiguous}}\ndict set xu_original_driver [get_object_name $p] [lindex $drivers 0]\nputs $f [join [list [get_object_name $p] [get_attribute $c ref_name] [get_object_name $con] $owner_ref [lindex $drivers 0]] "\\t"]\nset c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg}]\nset p [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN}]\nset owner [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu}]\nif {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DSNQNV0_12TR40} || [sizeof_collection $p]!=1 || [get_attribute $p direction] ne "in" || [sizeof_collection $owner]!=1} {error {exact reset endpoint identity changed}}\nset owner_ref [get_attribute $owner ref_name]\nif {![dict exists $xu_parent_counts $owner_ref] || [dict get $xu_parent_counts $owner_ref]!=1} {error {reset owner design is shared}}\nset n [get_nets -of_objects $p]\nif {[sizeof_collection $n]!=1} {error {reset endpoint net missing or ambiguous}}\nset con [all_connected -leaf $n]\nset drivers {}\nforeach_in_collection o $con {\n if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend drivers [get_object_name $o]}\n}\nif {[llength $drivers]!=1} {error {reset endpoint original driver ambiguous}}\ndict set xu_original_driver [get_object_name $p] [lindex $drivers 0]\nputs $f [join [list [get_object_name $p] [get_attribute $c ref_name] [get_object_name $con] $owner_ref [lindex $drivers 0]] "\\t"]\nset c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg}]\nset p [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}]\nset owner [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0}]\nif {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DRNQV0_12TR40} || [sizeof_collection $p]!=1 || [get_attribute $p direction] ne "in" || [sizeof_collection $owner]!=1} {error {exact reset endpoint identity changed}}\nset owner_ref [get_attribute $owner ref_name]\nif {![dict exists $xu_parent_counts $owner_ref] || [dict get $xu_parent_counts $owner_ref]!=1} {error {reset owner design is shared}}\nset n [get_nets -of_objects $p]\nif {[sizeof_collection $n]!=1} {error {reset endpoint net missing or ambiguous}}\nset con [all_connected -leaf $n]\nset drivers {}\nforeach_in_collection o $con {\n if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend drivers [get_object_name $o]}\n}\nif {[llength $drivers]!=1} {error {reset endpoint original driver ambiguous}}\ndict set xu_original_driver [get_object_name $p] [lindex $drivers 0]\nputs $f [join [list [get_object_name $p] [get_attribute $c ref_name] [get_object_name $con] $owner_ref [lindex $drivers 0]] "\\t"]\nset c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg}]\nset p [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}]\nset owner [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1}]\nif {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DRNQV0_12TR40} || [sizeof_collection $p]!=1 || [get_attribute $p direction] ne "in" || [sizeof_collection $owner]!=1} {error {exact reset endpoint identity changed}}\nset owner_ref [get_attribute $owner ref_name]\nif {![dict exists $xu_parent_counts $owner_ref] || [dict get $xu_parent_counts $owner_ref]!=1} {error {reset owner design is shared}}\nset n [get_nets -of_objects $p]\nif {[sizeof_collection $n]!=1} {error {reset endpoint net missing or ambiguous}}\nset con [all_connected -leaf $n]\nset drivers {}\nforeach_in_collection o $con {\n if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend drivers [get_object_name $o]}\n}\nif {[llength $drivers]!=1} {error {reset endpoint original driver ambiguous}}\ndict set xu_original_driver [get_object_name $p] [lindex $drivers 0]\nputs $f [join [list [get_object_name $p] [get_attribute $c ref_name] [get_object_name $con] $owner_ref [lindex $drivers 0]] "\\t"]\nset c [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg}]\nset p [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}]\nset owner [get_cells -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2}]\nif {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {DRNQV0_12TR40} || [sizeof_collection $p]!=1 || [get_attribute $p direction] ne "in" || [sizeof_collection $owner]!=1} {error {exact reset endpoint identity changed}}\nset owner_ref [get_attribute $owner ref_name]\nif {![dict exists $xu_parent_counts $owner_ref] || [dict get $xu_parent_counts $owner_ref]!=1} {error {reset owner design is shared}}\nset n [get_nets -of_objects $p]\nif {[sizeof_collection $n]!=1} {error {reset endpoint net missing or ambiguous}}\nset con [all_connected -leaf $n]\nset drivers {}\nforeach_in_collection o $con {\n if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend drivers [get_object_name $o]}\n}\nif {[llength $drivers]!=1} {error {reset endpoint original driver ambiguous}}\ndict set xu_original_driver [get_object_name $p] [lindex $drivers 0]\nputs $f [join [list [get_object_name $p] [get_attribute $c ref_name] [get_object_name $con] $owner_ref [lindex $drivers 0]] "\\t"]\nclose $f\nset lc [get_lib_cells -quiet {scc40nll_vhsc40_rvt_ss_v0p99_125c_basic/CLKINV0_12TR40}]\nif {[sizeof_collection $lc]!=1} {error {actual library candidate missing}}\n\n# Actual55 stopped here: an unset DC dont_use attribute returns the empty\n# string, which is not a Tcl boolean. Preserve the raw value; do not invent\n# or set a library attribute. The exact same DB and actual41 false palette\n# record are frozen by the Python preflight, and native insertion must accept.\nset xu_dont_use [get_attribute -quiet $lc dont_use]\nset xu_dont_use_basis dc_explicit_false\nif {$xu_dont_use eq ""} {\n set xu_dont_use_basis dc_absent_with_frozen_PT_palette_false_native_validation_required\n} elseif {![string is boolean -strict $xu_dont_use]} {\n error {DC dont_use attribute is not a valid boolean}\n} elseif {$xu_dont_use} {\n error {actual library candidate prohibited in DC}\n}\nset f [open reset-library-preflight.tsv w]\nputs $f "libcell\\tdc_dont_use_raw\\tacceptance_basis"\nputs $f [join [list [get_object_name $lc] $xu_dont_use $xu_dont_use_basis] "\\t"]\nclose $f\nset li [get_lib_pins -of_objects $lc -filter {direction == in}]\nset lo [get_lib_pins -of_objects $lc -filter {direction == out}]\nif {[sizeof_collection $li]!=1 || [sizeof_collection $lo]!=1 || [get_object_name $li] ne "scc40nll_vhsc40_rvt_ss_v0p99_125c_basic/CLKINV0_12TR40/I" || [get_object_name $lo] ne "scc40nll_vhsc40_rvt_ss_v0p99_125c_basic/CLKINV0_12TR40/ZN"} {error {actual library topology changed}}\n# insert_buffer -inverter_pair performs the native inverter-function check.\n# A name or absent PT function attribute is never taken as a logic proof.\nset f [open inserted-reset-cells.tsv w]\nputs $f "endpoint\\tcell\\tref"\ncurrent_instance {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu}\nset p [get_pins -quiet {erst_reset_r_reg/SDN}]\nif {[sizeof_collection $p]!=1} {error {scoped exact reset pin missing}}\nset added [insert_buffer -inverter_pair -no_of_cells 4 -new_cell_names {xu_reset116_0} -new_net_names {xu_reset116_net_0} $p $lc]\nif {[sizeof_collection $added]!=8} {error {native inverter-pair insertion failed}}\ncurrent_instance\nset names [get_object_name $added]\nforeach_in_collection c $added {if {[get_attribute $c ref_name] ne {CLKINV0_12TR40}} {error {inserted cell identity differs}};puts $f [join [list {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN} [get_object_name $c] [get_attribute $c ref_name]] "\\t"]}\nset cursor [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN}]\nset seen {}\nfor {set k 0} {$k<8} {incr k} {\n set n [get_nets -of_objects $cursor]\n if {[sizeof_collection $n]!=1} {error {new reset chain net missing}}\n set con [all_connected -leaf $n]\n if {[sizeof_collection $con]!=2} {error {new reset buffer branch gained another receiver}}\n set dp {}\n foreach_in_collection o $con {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}\n if {[llength $dp]!=1} {error {new reset chain driver ambiguous}}\n set driver [get_pins -quiet [lindex $dp 0]]\n set c [get_cells -of_objects $driver]\n set cn [get_object_name $c]\n if {[lsearch -exact $names $cn]<0 || [lsearch -exact $seen $cn]>=0 || [get_attribute $c ref_name] ne "CLKINV0_12TR40"} {error {new reset chain topology differs}}\n lappend seen $cn\n set cursor [get_pins -of_objects $c -filter {direction == in}]\n if {[sizeof_collection $cursor]!=1} {error {new reset buffer input differs}}\n}\nif {[lsort $seen] ne [lsort $names]} {error {inserted reset chain has unvisited cells}}\nset dp {}\nforeach_in_collection o [all_connected -leaf [get_nets -of_objects $cursor]] {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}\nif {$dp ne [list [dict get $xu_original_driver {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN}]]} {error {reset chain did not retain original driver}}\ncurrent_instance {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu}\nset p [get_pins -quiet {erst_reset_r_r_reg/SDN}]\nif {[sizeof_collection $p]!=1} {error {scoped exact reset pin missing}}\nset added [insert_buffer -inverter_pair -no_of_cells 4 -new_cell_names {xu_reset116_1} -new_net_names {xu_reset116_net_1} $p $lc]\nif {[sizeof_collection $added]!=8} {error {native inverter-pair insertion failed}}\ncurrent_instance\nset names [get_object_name $added]\nforeach_in_collection c $added {if {[get_attribute $c ref_name] ne {CLKINV0_12TR40}} {error {inserted cell identity differs}};puts $f [join [list {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN} [get_object_name $c] [get_attribute $c ref_name]] "\\t"]}\nset cursor [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN}]\nset seen {}\nfor {set k 0} {$k<8} {incr k} {\n set n [get_nets -of_objects $cursor]\n if {[sizeof_collection $n]!=1} {error {new reset chain net missing}}\n set con [all_connected -leaf $n]\n if {[sizeof_collection $con]!=2} {error {new reset buffer branch gained another receiver}}\n set dp {}\n foreach_in_collection o $con {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}\n if {[llength $dp]!=1} {error {new reset chain driver ambiguous}}\n set driver [get_pins -quiet [lindex $dp 0]]\n set c [get_cells -of_objects $driver]\n set cn [get_object_name $c]\n if {[lsearch -exact $names $cn]<0 || [lsearch -exact $seen $cn]>=0 || [get_attribute $c ref_name] ne "CLKINV0_12TR40"} {error {new reset chain topology differs}}\n lappend seen $cn\n set cursor [get_pins -of_objects $c -filter {direction == in}]\n if {[sizeof_collection $cursor]!=1} {error {new reset buffer input differs}}\n}\nif {[lsort $seen] ne [lsort $names]} {error {inserted reset chain has unvisited cells}}\nset dp {}\nforeach_in_collection o [all_connected -leaf [get_nets -of_objects $cursor]] {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}\nif {$dp ne [list [dict get $xu_original_driver {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN}]]} {error {reset chain did not retain original driver}}\ncurrent_instance {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0}\nset p [get_pins -quiet {q_reg/RDN}]\nif {[sizeof_collection $p]!=1} {error {scoped exact reset pin missing}}\nset added [insert_buffer -inverter_pair -no_of_cells 4 -new_cell_names {xu_reset116_2} -new_net_names {xu_reset116_net_2} $p $lc]\nif {[sizeof_collection $added]!=8} {error {native inverter-pair insertion failed}}\ncurrent_instance\nset names [get_object_name $added]\nforeach_in_collection c $added {if {[get_attribute $c ref_name] ne {CLKINV0_12TR40}} {error {inserted cell identity differs}};puts $f [join [list {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN} [get_object_name $c] [get_attribute $c ref_name]] "\\t"]}\nset cursor [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}]\nset seen {}\nfor {set k 0} {$k<8} {incr k} {\n set n [get_nets -of_objects $cursor]\n if {[sizeof_collection $n]!=1} {error {new reset chain net missing}}\n set con [all_connected -leaf $n]\n if {[sizeof_collection $con]!=2} {error {new reset buffer branch gained another receiver}}\n set dp {}\n foreach_in_collection o $con {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}\n if {[llength $dp]!=1} {error {new reset chain driver ambiguous}}\n set driver [get_pins -quiet [lindex $dp 0]]\n set c [get_cells -of_objects $driver]\n set cn [get_object_name $c]\n if {[lsearch -exact $names $cn]<0 || [lsearch -exact $seen $cn]>=0 || [get_attribute $c ref_name] ne "CLKINV0_12TR40"} {error {new reset chain topology differs}}\n lappend seen $cn\n set cursor [get_pins -of_objects $c -filter {direction == in}]\n if {[sizeof_collection $cursor]!=1} {error {new reset buffer input differs}}\n}\nif {[lsort $seen] ne [lsort $names]} {error {inserted reset chain has unvisited cells}}\nset dp {}\nforeach_in_collection o [all_connected -leaf [get_nets -of_objects $cursor]] {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}\nif {$dp ne [list [dict get $xu_original_driver {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN}]]} {error {reset chain did not retain original driver}}\ncurrent_instance {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1}\nset p [get_pins -quiet {q_reg/RDN}]\nif {[sizeof_collection $p]!=1} {error {scoped exact reset pin missing}}\nset added [insert_buffer -inverter_pair -no_of_cells 4 -new_cell_names {xu_reset116_3} -new_net_names {xu_reset116_net_3} $p $lc]\nif {[sizeof_collection $added]!=8} {error {native inverter-pair insertion failed}}\ncurrent_instance\nset names [get_object_name $added]\nforeach_in_collection c $added {if {[get_attribute $c ref_name] ne {CLKINV0_12TR40}} {error {inserted cell identity differs}};puts $f [join [list {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN} [get_object_name $c] [get_attribute $c ref_name]] "\\t"]}\nset cursor [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}]\nset seen {}\nfor {set k 0} {$k<8} {incr k} {\n set n [get_nets -of_objects $cursor]\n if {[sizeof_collection $n]!=1} {error {new reset chain net missing}}\n set con [all_connected -leaf $n]\n if {[sizeof_collection $con]!=2} {error {new reset buffer branch gained another receiver}}\n set dp {}\n foreach_in_collection o $con {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}\n if {[llength $dp]!=1} {error {new reset chain driver ambiguous}}\n set driver [get_pins -quiet [lindex $dp 0]]\n set c [get_cells -of_objects $driver]\n set cn [get_object_name $c]\n if {[lsearch -exact $names $cn]<0 || [lsearch -exact $seen $cn]>=0 || [get_attribute $c ref_name] ne "CLKINV0_12TR40"} {error {new reset chain topology differs}}\n lappend seen $cn\n set cursor [get_pins -of_objects $c -filter {direction == in}]\n if {[sizeof_collection $cursor]!=1} {error {new reset buffer input differs}}\n}\nif {[lsort $seen] ne [lsort $names]} {error {inserted reset chain has unvisited cells}}\nset dp {}\nforeach_in_collection o [all_connected -leaf [get_nets -of_objects $cursor]] {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}\nif {$dp ne [list [dict get $xu_original_driver {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN}]]} {error {reset chain did not retain original driver}}\ncurrent_instance {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2}\nset p [get_pins -quiet {q_reg/RDN}]\nif {[sizeof_collection $p]!=1} {error {scoped exact reset pin missing}}\nset added [insert_buffer -inverter_pair -no_of_cells 4 -new_cell_names {xu_reset116_4} -new_net_names {xu_reset116_net_4} $p $lc]\nif {[sizeof_collection $added]!=8} {error {native inverter-pair insertion failed}}\ncurrent_instance\nset names [get_object_name $added]\nforeach_in_collection c $added {if {[get_attribute $c ref_name] ne {CLKINV0_12TR40}} {error {inserted cell identity differs}};puts $f [join [list {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN} [get_object_name $c] [get_attribute $c ref_name]] "\\t"]}\nset cursor [get_pins -quiet {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}]\nset seen {}\nfor {set k 0} {$k<8} {incr k} {\n set n [get_nets -of_objects $cursor]\n if {[sizeof_collection $n]!=1} {error {new reset chain net missing}}\n set con [all_connected -leaf $n]\n if {[sizeof_collection $con]!=2} {error {new reset buffer branch gained another receiver}}\n set dp {}\n foreach_in_collection o $con {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}\n if {[llength $dp]!=1} {error {new reset chain driver ambiguous}}\n set driver [get_pins -quiet [lindex $dp 0]]\n set c [get_cells -of_objects $driver]\n set cn [get_object_name $c]\n if {[lsearch -exact $names $cn]<0 || [lsearch -exact $seen $cn]>=0 || [get_attribute $c ref_name] ne "CLKINV0_12TR40"} {error {new reset chain topology differs}}\n lappend seen $cn\n set cursor [get_pins -of_objects $c -filter {direction == in}]\n if {[sizeof_collection $cursor]!=1} {error {new reset buffer input differs}}\n}\nif {[lsort $seen] ne [lsort $names]} {error {inserted reset chain has unvisited cells}}\nset dp {}\nforeach_in_collection o [all_connected -leaf [get_nets -of_objects $cursor]] {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}\nif {$dp ne [list [dict get $xu_original_driver {u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN}]]} {error {reset chain did not retain original driver}}\nclose $f\nif {[sizeof_collection [get_cells -hierarchical -filter {is_hierarchical == false}]]!=$xu_before_cells+40} {error {unexpected reset insertion cell count}}\n'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for data in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()


def ident(path):
    path = Path(path)
    before = path.stat()
    digest = sha(path)
    after = path.stat()
    need((before.st_size, before.st_mtime_ns, before.st_ino) ==
         (after.st_size, after.st_mtime_ns, after.st_ino), 'input changed during hash')
    # Preserve the exact absolute path spelling in original169 receipts. A
    # read-only symlink alias must not change the historical receipt dictionary.
    return dict(path=str(path), bytes=before.st_size, sha256=digest)


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def dump(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def q(value):
    value = str(value)
    need(not any(c in value for c in '{}\t\r\n'), 'unquotable Tcl value')
    return '{' + value + '}'


def receipt(path, expected):
    actual = ident(path)
    need(actual['bytes'] == expected['bytes'] and actual['sha256'] == expected['sha256'],
         'original receipt differs: ' + str(path))
    return actual


def rows(path):
    csv.field_size_limit(16 * 1024 * 1024)
    with Path(path).open() as source:
        return list(csv.DictReader(source, delimiter='\t'))


def plan_from_reports(parent):
    parent = Path(parent)
    need(sha(parent / 'state.json') == STAGES[-1][1], 'exact actual95 state differs')
    state = load(parent / 'state.json')
    need(state['status'] == 'EXECUTED_NOT_QUALIFIED' and
         state['mapped_netlist_sha256'] == STAGES[-1][2], 'actual95 mapped receipt differs')
    for name in ('constraints.rpt', 'analysis-coverage.rpt', 'hold.rpt'):
        receipt(parent / name, state['reports'][name])
    for name in ('post-cleanup-upstream.tsv', 'removed-cells.tsv', 'removal-preflight.tsv'):
        receipt(parent / name, state['audits'][name])
    upstream = rows(parent / 'post-cleanup-upstream.tsv')
    need(len(upstream) == 44 and len({r['driver'] for r in upstream}) == 44,
         'actual95 exact44 upstream rows differ')
    candidates = sorted((r for r in upstream if r['source_only'] == '1'), key=lambda r: r['driver'])
    need(len(candidates) == 17 and all(r['net_count'] == '1' and
         r['leaf_connections'] == r['driver'] for r in candidates), 'exact17 source-only proof differs')
    cap = []
    for block in (parent / 'constraints.rpt').read_text().split('    Pin: ')[1:]:
        kinds = re.findall(r'^\s*(?:-\s*)?(max_capacitance|min_capacitance)\s+', block, re.M)
        need(kinds == ['min_capacitance'], 'actual95 electrical kind differs')
        cap.append(block.splitlines()[0])
    need(len(cap) == 17 and set(cap) == {r['driver'] for r in candidates},
         'actual95 min-cap set differs from source-only set')
    reset_blocks = (parent / 'hold.rpt').read_text().split('  Startpoint: ')[1:]
    found = {}
    need(len(reset_blocks) == 5, 'actual95 exact5 hold failure blocks differ')
    for block in reset_blocks:
        need(block.splitlines()[0].strip() == 'io_pads_aon_erst_n_i_ival' and
             'removal check against rising-edge clock xu_lfextclk' in block,
             'actual95 reset source/check differs')
        ep = re.search(r'^  Endpoint: (\S+)', block, re.M)
        pins = re.findall(r'^  (\S+/(?:RDN|SDN)) \((\S+)\)', block, re.M)
        need(ep is not None and len(pins) == 1, 'actual95 reset endpoint ambiguous')
        found[ep.group(1)] = pins[0]
    need(found == {c: (c + '/' + p, r) for c, p, r in ENDPOINTS},
         'actual95 exact5 reset sinks differ')
    return state, candidates


def cleanup_tcl(candidates):
    initial = ' '.join(q(r['driver']) for r in candidates)
    references = ' '.join(q(r['driver']) + ' ' + q(r['owner_ref']) for r in candidates)
    return r'''
set xu116_first [list @INITIAL@]
set xu116_first_refs [dict create @REFERENCES@]
set xu116_front $xu116_first
set xu116_parent_counts [dict create]
foreach_in_collection h [get_cells -hierarchical -filter {is_hierarchical == true}] {dict incr xu116_parent_counts [get_attribute $h ref_name]}
set xu116_total 0
set xu116_removed {}
set xu116_before [sizeof_collection [get_cells -hierarchical -filter {is_hierarchical == false}]]
set xf [open cleanup-rounds.tsv w]
set pf [open cleanup-preflight.tsv w]
set rf [open removed-cells.tsv w]
puts $xf "round\tfrontier\tremoved\tupstream"
puts $pf "round\tcell\tref\tis_sequential\toutput\tleaf_connections\towner_instance_count"
puts $rf "round\tcell\tref"
set xu116_converged 0
for {set wave 0} {$wave<16} {incr wave} {
 set planned [dict create]
 set upstream [dict create]
 foreach name [lsort -unique $xu116_front] {
  set p [get_pins -quiet $name]
  if {[sizeof_collection $p]!=1 || [get_attribute $p direction] ne "out"} {error {116 frontier exact output missing}}
  set c [get_cells -of_objects $p]
  if {[sizeof_collection $c]!=1 || [get_attribute $c is_hierarchical]} {error {116 candidate is not exact leaf}}
  set cn [get_object_name $c]
  set ref [get_attribute $c ref_name]
  if {$wave==0 && $ref ne [dict get $xu116_first_refs $name]} {error {116 initial17 native ref differs}}
  set unloaded 1
  set outputs [get_pins -of_objects $c -filter {direction == out}]
  if {[sizeof_collection $outputs]<1} {error {116 candidate output set empty}}
  foreach_in_collection op $outputs {
   set nets [get_nets -of_objects $op]
   if {[sizeof_collection $nets]!=1} {error {116 candidate output net missing/ambiguous}}
   set con [all_connected -leaf $nets]
   if {[sizeof_collection $con]!=1 || [get_object_name $con] ne [get_object_name $op]} {set unloaded 0}
  }
  if {!$unloaded} {
   if {$wave==0} {error {116 initial17 output gained receiver}}
   continue
  }
  if {[dict exists $planned $cn]} {continue}
  if {[lsearch -exact $xu116_removed $cn]>=0} {error {116 candidate already removed}}
  if {[sizeof_collection [get_pins -of_objects $c -filter {direction == inout}]]!=0} {error {116 inout deletion forbidden}}
  set seq [get_attribute -quiet $c is_sequential]
  if {![string is boolean -strict $seq] || $seq} {error {116 sequential/unknown classification deletion forbidden}}
  set owner [get_cells -quiet [file dirname $cn]]
  if {[sizeof_collection $owner]!=1} {error {116 exact owner missing}}
  set oref [get_attribute $owner ref_name]
  if {![dict exists $xu116_parent_counts $oref] || [dict get $xu116_parent_counts $oref]!=1} {error {116 shared owner deletion forbidden}}
  foreach_in_collection op $outputs {
   set con [all_connected -leaf [get_nets -of_objects $op]]
   if {[get_attribute $con object_class] ne "pin" || [get_attribute $con direction] ne "out"} {error {116 output terminal class differs}}
   puts $pf [join [list $wave $cn $ref $seq [get_object_name $op] [get_object_name $con] [dict get $xu116_parent_counts $oref]] "\t"]
  }
  foreach_in_collection ip [get_pins -of_objects $c -filter {direction == in}] {
   foreach_in_collection n [get_nets -of_objects $ip] {
    foreach_in_collection d [all_connected -leaf $n] {
     if {[get_attribute $d object_class] eq "pin" && [get_attribute $d direction] eq "out"} {dict set upstream [get_object_name $d] 1}
    }
   }
  }
  dict set planned $cn $ref
 }
 if {$wave==0 && [dict size $planned]!=17} {error {116 first wave must delete exact17 cells}}
 if {$xu116_total+[dict size $planned]>1024} {error {116 bounded total deletion exceeded}}
 # The entire wave has passed before its first mutation.
 foreach cn [lsort [dict keys $planned]] {
  set c [get_cells -quiet $cn]
  remove_cell $c
  if {[sizeof_collection [get_cells -quiet $cn]]!=0} {error {116 native cell deletion failed}}
  lappend xu116_removed $cn
  puts $rf [join [list $wave $cn [dict get $planned $cn]] "\t"]
 }
 incr xu116_total [dict size $planned]
 if {[sizeof_collection [get_cells -hierarchical -filter {is_hierarchical == false}]]!=$xu116_before-$xu116_total} {error {116 unexpected cell-count mutation}}
 puts $xf [join [list $wave [llength $xu116_front] [dict size $planned] [dict size $upstream]] "\t"]
 if {[dict size $planned]==0 || [dict size $upstream]==0} {set xu116_converged 1;break}
 set xu116_front [dict keys $upstream]
}
close $xf
close $pf
close $rf
if {!$xu116_converged} {error {116 bounded16 waves exhausted without fixed point}}
''' .replace('@INITIAL@', initial).replace('@REFERENCES@', references)


def validate_run(directory, state):
    need(state['status'] == 'EXECUTED_NOT_QUALIFIED' and len(state['runs']) == 2,
         'ancestor is not completed DC/PT: ' + str(directory))
    for label, run in zip(('dc', 'pt'), state['runs']):
        need(run['tool'] == label + '_shell' and not run['returncode'] and
             not run['errors'] and run['marker_count'] == 1, 'ancestor native run failed')
        need(sha(directory / (label + '.log')) == run['log_sha256'] and
             sha(directory / ('repair.tcl' if label == 'dc' else 'sta.tcl')) == run['script_sha256'],
             'ancestor native log/script differs')


def run_native(out, state, label, binary, script, marker, env):
    command = [binary, '-f', script]
    started = time.time()
    state['phase'] = label
    state['native_command'] = command
    dump(out / 'state.json', state)
    try:
        with (out / (label + '.log')).open('xb') as stream:
            process = subprocess.run(command, cwd=str(out), stdin=subprocess.DEVNULL,
                stdout=stream, stderr=subprocess.STDOUT, env=env, timeout=21600 if label != 'fm' else 4200)
    except BaseException as error:
        state['runs'].append(dict(label=label, command=command, status='PROCESS_EXCEPTION',
                                 error=type(error).__name__ + ': ' + str(error)))
        dump(out / 'state.json', state)
        raise
    text = (out / (label + '.log')).read_text(errors='replace')
    errors = [s for s in text.splitlines() if re.match(r'^\s*(?:Error:|Error-|XU_FATAL:|XU_FULL_SOC_FORMALITY_FAIL|XU_FULL_SOC_FORMALITY_SCRIPT_ERROR)', s)]
    count = sum(line.strip() == marker for line in text.splitlines())
    record = dict(label=label, command=command, returncode=process.returncode,
                  marker_count=count, errors=errors, started_epoch=started,
                  finished_epoch=time.time(), log=ident(out / (label + '.log')),
                  script=ident(out / script))
    state['runs'].append(record)
    dump(out / 'state.json', state)
    need(process.returncode == 0 and not errors and count == 1, label + ' native run failed')
    if label == 'fm':
        need(sum(line.strip() == 'Verification SUCCEEDED' for line in text.splitlines()) == 1,
             'FM native full verification success absent')


def main():
    out = B / OUT_NAME
    out.mkdir(exist_ok=False)
    state = dict(status='RUNNING_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
        pid=os.getpid(), started_epoch=time.time(), runs=[],
        scope='Same final baseline mapped: bounded exact95 dead-cone cleanup plus 5x4 inverter pairs; full own FM and PT; no new constraints or waivers',
        limits=['Baseline method experiment, not S2e mapped qualification.',
                'Reset path absence remains UNKNOWN, not safe slack.',
                'Existing reset/RDC, UART, conditional pulse and coverage obligations remain.',
                'No full-SoC energy or contest score is inferred.'])
    inputs = []
    dump(out / 'state.json', state)
    try:
        parent = B / PARENT_NAME
        parent_state, candidates = plan_from_reports(parent)
        need(sha(parent / 'mapped.v') == STAGES[-1][2], 'actual95 mapped bytes differ')
        sdc = B / 'full-soc-pt-compatible-05/constraints.sdc'
        scope = Path.home() / 'Desktop/xu-ts16.tcl'
        need(sha(sdc) == SDC_SHA and sha(scope) == SCOPE_SHA, 'original constraints/scope differ')
        producer = B / 'ChipContest-clear-alias-20261103/tools/scripts/xu_soc_ppa.py'
        need(sha(producer) == PRODUCER_SHA, 'original producer differs')
        spec = importlib.util.spec_from_file_location('xu_frozen_ppa116', str(producer))
        ppa = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ppa)
        impl_path = B / 'clear-power-campaign-20261103-01/implementation/implementation.json'
        need(sha(impl_path) == '193de595283f3e33dfefe9bbec23301e5758e6feb61f014ab38818e82d43cd4d', 'original implementation differs')
        impl = load(impl_path)
        libs = [Path(x['path']) for x in impl['libraries']]
        target = [Path(x['path']) for x in impl['libraries'] if x['role'] == 'standard_cell']
        need(len(libs) == 2 and len(target) == 1 and {sha(p) for p in libs} == DB_SHAS,
             'exact original two SS libraries differ')
        inputs = [Path(__file__).resolve(), producer, impl_path, sdc, scope] + libs
        manuals = [('remove_cell.txt', '3ca9f9c21a64ecc388004669b6b52d45cb6115fd010e3356187d5e2ab0b0ab82'),
                   ('insert_buffer.txt', '777ce2124be6bdcfa10755b912218bb61564f4090d778aefb2725fa0279fc96c')]
        for name, digest in manuals:
            path = B / 'dc-electrical-docs-20261103-40' / name
            need(sha(path) == digest, 'installed native command document differs')
            inputs.append(path)
        palette = B / 'full-soc-cap-cell-palette-20261103-41/library-palette.tsv'
        need(sha(palette) == '10eaa10e2485bba64be08d078907016eed2ff13f73799efeecfd5a4afc6e29d1', 'native palette differs')
        selected = [r for r in rows(palette) if r['libcell'] == LIB]
        need(len(selected) == 2 and all(r['dont_use'] == 'false' for r in selected) and
             {(r['libpin'].rsplit('/', 1)[-1], r['direction']) for r in selected} == {('I', 'in'), ('ZN', 'out')},
             'native inverter palette topology differs')
        inputs.append(palette)
        original_fm = B / 'full-soc-electrical-formality-20261104-54-49'
        need(sha(original_fm / 'state.json') == FM49_SHA, 'original full FM49 receipt differs')
        f = load(original_fm / 'state.json')
        need(f['status'] == 'VERIFIED_REVIEW_PENDING_NOT_QUALIFIED' and f['returncode'] == 0 and
             f['frozen_before'] == f['frozen_after'] and len(f['frozen_before']) == 169,
             'original complete169-input FM49 proof missing')
        for name, expected in f['frozen_before'].items():
            need(ident(name) == expected, 'original FM49 frozen169 input differs: ' + name)
            inputs.append(Path(name))
        for key, name in [('log', 'fm.log'), ('script', 'verify.tcl')]:
            need(ident(original_fm / name) == f[key], 'original FM49 output differs')
            inputs.append(original_fm / name)
        fl = (original_fm / 'fm.log').read_text(errors='replace').splitlines()
        need(sum(s.strip() == 'Verification SUCCEEDED' for s in fl) == 1 and
             sum(s.strip() == 'XU_FULL_SOC_FORMALITY_PASS' for s in fl) == 1,
             'original FM49 native success markers differ')
        inputs.append(original_fm / 'state.json')
        previous = None
        for name, state_sha, mapped_sha in STAGES:
            directory = B / name
            need(sha(directory / 'state.json') == state_sha and sha(directory / 'mapped.v') == mapped_sha,
                 'frozen ancestor state/mapped differs: ' + name)
            edit = load(directory / 'state.json')
            need(edit['mapped_netlist_sha256'] == mapped_sha, 'ancestor mapped receipt differs')
            validate_run(directory, edit)
            if previous is not None:
                old_name, old_state_sha, old_mapped_sha = previous
                need(edit['input_sha256'].get(str(B / old_name / 'mapped.v')) == old_mapped_sha and
                     edit['input_sha256'].get(str(B / old_name / 'state.json')) == old_state_sha,
                     'full cleanup ancestry differs')
            for filename, digest in edit['input_sha256'].items():
                need(sha(filename) == digest, 'frozen ancestor input differs: ' + filename)
                inputs.append(Path(filename))
            inputs += [directory / x for x in ('state.json', 'mapped.v', 'repair.svf', 'repair.tcl', 'sta.tcl', 'dc.log', 'pt.log')]
            previous = (name, state_sha, mapped_sha)
        inputs += [parent / x for x in ('constraints.rpt', 'analysis-coverage.rpt', 'post-cleanup-upstream.tsv', 'hold.rpt', 'removed-cells.tsv', 'removal-preflight.tsv')]
        chain = [B / 'full-soc-campaign-03-ppa/ppa-ss-01/default.svf',
                 B / 'full-soc-hold-repair-20261103-08/repair.svf',
                 B / 'full-soc-gating-margin-repair-20261103-09/repair.svf']
        chain += [B / n / 'repair.svf' for n, _, _ in STAGES]
        need(f['svf_chain'] == [str(p) for p in chain[:4]], 'original FM49 SVF chain differs')
        source = 'set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource ' + q(sdc) + '\nset XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource ' + q(scope) + '\n'
        dc = 'set_host_options -max_cores 2\nset_app_var target_library [list ' + ' '.join(q(p) for p in target) + ']\nset_app_var link_library [list * ' + ' '.join(q(p) for p in libs) + ']\nset_svf repair.svf\nread_verilog ' + q(parent / 'mapped.v') + '\ncurrent_design xu_soc_ppa_top\nif {![link]} {error {DC link failed}}\n' + source
        need(isinstance(RESET_TCL, str) and 'xu_reset116_' in RESET_TCL and 'xu_reset61_' not in RESET_TCL,
             'inspected reset fragment not embedded')
        dc += 'set_dont_touch [get_cells -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}] true\n' + cleanup_tcl(candidates) + RESET_TCL + ppa.memory_checks(impl)
        dc += 'report_constraint -all_violators -verbose > dc-all-constraints.rpt\nreport_units > dc-units.rpt\nreport_area -hierarchy > area.rpt\nreport_qor > qor.rpt\nreport_timing -delay_type max -max_paths 50 > dc-setup.rpt\nreport_timing -delay_type min -max_paths 50 > dc-hold.rpt\nwrite -format verilog -hierarchy -output mapped.v\nwrite -format ddc -hierarchy -output mapped.ddc\nwrite_sdc mapped.sdc\n'
        dump(out / 'cleanup-plan.json', dict(initial_exact17=candidates, maximum_waves=16,
             maximum_removed_cells=1024, upstream_only=True, sequential_removal=False,
             pairs_per_reset_sink=4, reset_sinks=ENDPOINTS, qualification='NOT_QUALIFIED'))
        (out / 'repair.tcl').write_text(ppa.guarded_tcl(dc, 'XU_COMBINED116_DC_DONE_NOT_QUALIFIED'))
        pt = 'set_app_var link_path [list * ' + ' '.join(q(p) for p in libs) + ']\nread_verilog mapped.v\nif {![link_design xu_soc_ppa_top]} {error {PT link failed}}\n' + source + ppa.memory_checks(impl)
        pt += 'redirect -file units.rpt {report_units}\nredirect -file check-timing.rpt {check_timing -verbose}\nredirect -file setup.rpt {report_timing -delay_type max -slack_lesser_than 1000000 -max_paths 50 -significant_digits 8}\nredirect -file hold.rpt {report_timing -delay_type min -slack_lesser_than 1000000 -max_paths 50 -significant_digits 8}\nredirect -file constraints.rpt {report_constraint -all_violators -verbose -significant_digits 8}\nredirect -file exceptions.rpt {report_exceptions}\nredirect -file analysis-coverage.rpt {report_analysis_coverage -status_details untested}\nredirect -file clocks.rpt {report_clock -attributes}\n'
        pt += 'set f [open timing-slack.tsv w]\nputs $f "delay_type\\tpath_count\\tworst_slack"\nforeach type {max min} {set paths [get_timing_paths -delay_type $type -slack_lesser_than 1000000 -max_paths 1];if {[sizeof_collection $paths]!=1} {error {global timing path missing}};puts $f [join [list $type [sizeof_collection $paths] [get_attribute $paths slack]] "\\t"]}\nclose $f\nset f [open reset-paths.tsv w]\nputs $f "index\\tsource_kind\\tcheck\\tcount\\tworst_slack\\tstatus"\n'
        for i, (cell, pin, _) in enumerate(ENDPOINTS):
            for source_kind, src in [('HF_RESET', '[get_ports {io_pads_aon_erst_n_i_ival}]')] + ([('LF_WATCHDOG', '[get_pins ' + q(BASE + 'u_sirv_aon/wdog/AsyncResetRegVec_6_1/reg_0/q_reg/Q') + ']')] if i >= 2 else []):
                for kind, delay in [('recovery', 'max'), ('removal', 'min')]:
                    stem = 'reset-%s-%d-%s' % (source_kind.lower(), i, kind)
                    pt += 'set src ' + src + '\nset dst [get_pins -quiet ' + q(cell + '/' + pin) + ']\nif {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query selector differs}}\n'
                    pt += 'set paths [get_timing_paths -from $src -to $dst -delay_type ' + delay + ' -slack_lesser_than 1000000 -max_paths 1]\nset n [sizeof_collection $paths]\nset slack UNKNOWN\nset status NO_PATH_UNKNOWN\nif {$n>0} {set slack [get_attribute $paths slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}\n'
                    pt += 'puts $f [join [list ' + str(i) + ' ' + source_kind + ' ' + kind + ' $n $slack $status] "\\t"]\nredirect -file ' + stem + '.rpt {report_timing -from $src -to $dst -delay_type ' + delay + ' -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8}\n'
        pt += 'close $f\n'
        (out / 'sta.tcl').write_text(ppa.guarded_tcl(pt, 'XU_COMBINED116_PT_DIAGNOSTIC_DONE_NOT_QUALIFIED'))
        verify = (original_fm / 'verify.tcl').read_text()
        old_svf = 'set_svf [list ' + ' '.join(q(p) for p in chain[:4]) + ']'
        old_net = 'read_verilog -i ' + q(B / STAGES[0][0] / 'mapped.v')
        need(verify.count(old_svf) == verify.count(old_net) == 1, 'original full FM49 template differs')
        chain.append(out / 'repair.svf')
        verify = verify.replace(old_svf, 'set_svf [list ' + ' '.join(q(p) for p in chain) + ']').replace(old_net, 'read_verilog -i ' + q(out / 'mapped.v'))
        (out / 'verify.tcl').write_text(verify)
        inputs += [out / x for x in ('cleanup-plan.json', 'repair.tcl', 'sta.tcl', 'verify.tcl')]
        inputs = list(dict.fromkeys(inputs))
        state['frozen_before'] = {str(p): ident(p) for p in inputs}
        state['svf_chain'] = [str(p) for p in chain]
        state['parent_mapped'] = ident(parent / 'mapped.v')
        dump(out / 'state.json', state)
        env = os.environ.copy()
        env['SYNOPSYS_LC_ROOT'] = '/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'
        env['PATH'] = env['SYNOPSYS_LC_ROOT'] + '/bin:' + env.get('PATH', '')
        dc_bin = '/eda/synopsys/dc/dc_2022.03-SP5-5/bin/dc_shell'
        pt_bin = '/eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell'
        fm_bin = '/eda/synopsys/fm/fm_2020.09-SP5/bin/fm_shell'
        run_native(out, state, 'dc', dc_bin, 'repair.tcl', 'XU_COMBINED116_DC_DONE_NOT_QUALIFIED', env)
        state['final_mapped'] = ident(out / 'mapped.v')
        state['final_svf'] = ident(out / 'repair.svf')
        dump(out / 'state.json', state)
        run_native(out, state, 'pt', pt_bin, 'sta.tcl', 'XU_COMBINED116_PT_DIAGNOSTIC_DONE_NOT_QUALIFIED', env)
        need(ident(out / 'mapped.v') == state['final_mapped'] and
             ident(out / 'repair.svf') == state['final_svf'], 'DC output changed during PT')
        run_native(out, state, 'fm', fm_bin, 'verify.tcl', 'XU_FULL_SOC_FORMALITY_PASS', env)
        need(ident(out / 'mapped.v') == state['final_mapped'] and
             ident(out / 'repair.svf') == state['final_svf'], 'same final target changed during FM')
        state['frozen_after'] = {str(p): ident(p) for p in inputs}
        need(state['frozen_before'] == state['frozen_after'], 'an original/chain input changed')
        state['reports'] = {p.name: ident(p) for p in out.glob('*.rpt')}
        state['audits'] = {p.name: ident(p) for p in out.glob('*.tsv')}
        state['status'] = 'EXECUTED_SAME_MAPPED_DC_PT_AND_FULL_FM_NOT_QUALIFIED'
        state['timing'] = (out / 'timing-slack.tsv').read_text()
        state['reset_paths'] = (out / 'reset-paths.tsv').read_text()
    except BaseException as error:
        state.update(status='FAILED_NOT_QUALIFIED', error=type(error).__name__ + ': ' + str(error),
                     traceback=traceback.format_exc())
        raise
    finally:
        if 'frozen_before' in state:
            observed, observation_errors = {}, []
            for filename in state['frozen_before']:
                try:
                    observed[filename] = ident(filename)
                except BaseException as error:
                    observation_errors.append(filename + ': ' + type(error).__name__ + ': ' + str(error))
            state['frozen_after'] = observed
            state['frozen_after_observation_errors'] = observation_errors
            state['frozen_inputs_unchanged'] = observed == state['frozen_before'] and not observation_errors
            if not state['frozen_inputs_unchanged']:
                state['status'] = 'FAILED_NOT_QUALIFIED'
                state['frozen_input_error'] = 'Original or chain input differs after execution; original failure, if any, retained.'
        state['finished_epoch'] = time.time()
        dump(out / 'state.json', state)
    print(state['status'], flush=True)


if __name__ == '__main__':
    main()
