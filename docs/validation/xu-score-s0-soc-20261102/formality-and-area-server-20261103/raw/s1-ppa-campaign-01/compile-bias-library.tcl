if {[catch {
read_lib {/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP128X16/lib/RAMSP128X16_ss_0p99v_0p99v_125c.lib}
write_lib {RAMSP128X16_ss_0p99v_0p99v_125c} -format db -output {/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s1-ppa-campaign-01/xu-ramsp128x16-ss-0p99v-125c.db}
puts "XU_BIAS_LIBRARY_COMPILED"
} e]} {puts stderr "XU_BIAS_LC_ERROR $e";exit 1}
exit 0
