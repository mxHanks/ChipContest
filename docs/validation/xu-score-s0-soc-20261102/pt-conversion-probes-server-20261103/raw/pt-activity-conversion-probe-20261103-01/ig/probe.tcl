if {[catch {
set_app_var power_enable_analysis true
set_app_var power_analysis_mode averaged
set_app_var link_path [list * {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db} {/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db}]
redirect -file tool-version.rpt {puts $sh_product_version}
read_verilog {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/full-soc-campaign-03-ppa/ppa-ss-01/mapped.v}
if {![link_design {xu_soc_ppa_top}]} {error {PT power link failed}}

redirect -file units.rpt {report_units}
redirect -file read-saif.rpt {if {![read_saif {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/pt-activity-conversion-probe-20261103-01/ig/synthetic.saif} -strip_path {probe/dut} -report_inconsistent_annotation inconsistent.rpt]} {error {synthetic SAIF read failed}}}
set xu_f [open pins.tsv {WRONLY CREAT EXCL}]
puts $xu_f "phase\tdesired_name\treported_name\ttoggle_rate\ttoggle_source\tglitch_rate\tglitch_source\tstatic_probability\tstatic_source"
set xu_p [get_pins -quiet {u_shared/storage/macro_storage.depth_bank[0].width_lane[0].macro/A[0]}]
if {[sizeof_collection $xu_p] != 1} {error {actual probe pin absent}}
set xu_name [get_object_name $xu_p]
set xu_a [get_switching_activity -toggle_rate -glitch_rate -static_probability $xu_p]
if {[llength $xu_a] != 1 || [llength [lindex $xu_a 0]] != 7} {error {unexpected actual query tuple}}
set xu_row [linsert [lindex $xu_a 0] 0 before $xu_name]
foreach xu_field $xu_row {if {[regexp {[\t\r\n]} $xu_field]} {error {TSV control in actual query}}}
puts $xu_f [join $xu_row "\t"]
close $xu_f
puts {XU_ACTIVITY_CONVERSION_EXPORTED_REVIEW_PENDING}

puts {XU_ACTIVITY_CONVERSION_PROBE_COMPLETE}
} xu_error]} {
  puts stderr "XU_FATAL: $xu_error"
  exit 1
}
exit 0
