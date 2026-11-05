# xu all60 private source observations

**Every target9c16 binding remains pending.** The category below is source-only lookup strategy, not mapped proof.

| Original macro.path | Candidate/source strategy | Width × lanes | Original TB lines | Source evidence |
|---|---|---:|---|---|
| `ACCEL.bias_index_reg` | `bias_index_reg`; mapped_private_state_or_equivalent_endpoint_needed | 3 × 1 | 414,416,684 | `rtl/e203/perips/accel_icb_slave.v`:115,249,350,353,357,502,507,514 |
| `ACCEL.bias_regs` | `u_linear_compute_core.io_bias_{0..7}`; existing_core_port_alias | 40 × 8 | 352 | `rtl/e203/perips/accel_icb_slave.v`:116,200,201,202,203,204,205,206,207,261,353,357 |
| `ACCEL.busy` | `busy`; literal_wrapper_combinational_expression | 1 × 1 | 333,539 | `rtl/e203/perips/accel_icb_slave.v`:133,138,325,328,465,466,519,525,532 |
| `ACCEL.cache_addr_reg` | `u_linear_compute_core.io_cacheWriteAddr`; existing_core_port_alias | 8 × 1 | 409,411 | `rtl/e203/perips/accel_icb_slave.v`:120,185,188,252,366,572 |
| `ACCEL.cache_enable` | `u_linear_compute_core.io_cacheEnable`; existing_core_port_alias | 1 × 1 | 213,268,333 | `rtl/e203/perips/accel_icb_slave.v`:119,138,183,251,364,569 |
| `ACCEL.compute_start` | `u_linear_compute_core.io_computeStart`; existing_core_port_alias | 1 × 1 | 275,613,623 | `rtl/e203/perips/accel_icb_slave.v`:76,181 |
| `ACCEL.core_done` | `u_linear_compute_core.io_done`; existing_core_port_alias | 1 × 1 | 281,559,625 | `rtl/e203/perips/accel_icb_slave.v`:141,209,272 |
| `ACCEL.core_start` | `u_linear_compute_core.io_start`; existing_core_port_alias | 1 × 1 | 334 | `rtl/e203/perips/accel_icb_slave.v`:131,139,163,254,265,467 |
| `ACCEL.manual_busy` | `manual_busy`; mapped_private_state_or_equivalent_endpoint_needed | 1 × 1 | 612 | `rtl/e203/perips/accel_icb_slave.v`:132,133,255,273,468 |
| `ACCEL.row_active` | `u_linear_compute_core.io_rowActive`; existing_core_port_alias | 1 × 1 | 143,147,156,270,275,301,347,559,613,618,623,650,700 | `rtl/e203/perips/accel_icb_slave.v`:76,85,123,125,133,166,272,388 |
| `ACCEL.row_count` | `u_linear_compute_core.io_rowCount`; existing_core_port_alias | 2 × 1 | 143,147,153,154,270,347,618,650,701 | `rtl/e203/perips/accel_icb_slave.v`:77,139,169,387 |
| `ACCEL.row_group` | `u_linear_compute_core.io_rowGroup`; existing_core_port_alias | 5 × 1 | 290,302 | `rtl/e203/perips/accel_icb_slave.v`:79,172,387 |
| `ACCEL.row_pop` | `u_linear_compute_core.io_rowPop`; existing_core_port_alias | 1 × 1 | 300,615 | `rtl/e203/perips/accel_icb_slave.v`:84,165,308,453 |
| `ACCEL.row_produced` | `u_linear_compute_core.io_rowProduced`; existing_core_port_alias | 6 × 1 | 144,148,153,154,348,651,701 | `rtl/e203/perips/accel_icb_slave.v`:78,170,386,388 |
| `ACCEL.row_result` | `u_linear_compute_core.io_rowResult_{0..7}`; existing_core_port_alias | 48 × 8 | 291,296,297 | `rtl/e203/perips/accel_icb_slave.v`:80,173,174,175,176,177,178,179,180,312,313 |
| `ACCEL.row_retired` | `u_linear_compute_core.io_rowRetired`; existing_core_port_alias | 6 × 1 | 144,148,153,154,348,651,701 | `rtl/e203/perips/accel_icb_slave.v`:78,171,386 |
| `ACCEL.row_running` | `u_linear_compute_core.io_rowRunning`; existing_core_port_alias | 1 × 1 | 144,147,347,612,616,618,650 | `rtl/e203/perips/accel_icb_slave.v`:76,167,387 |
| `ACCEL.row_start` | `u_linear_compute_core.io_rowStart`; existing_core_port_alias | 1 × 1 | 156,265,540 | `rtl/e203/perips/accel_icb_slave.v`:81,85,123,125,133,138,164,256,266,448 |
| `ACCEL.row_start_accept` | `row_start_accept`; literal_wrapper_combinational_expression | 1 × 1 | 265,540 | `rtl/e203/perips/accel_icb_slave.v`:136,448 |
| `ACCEL.row_valid` | `u_linear_compute_core.io_rowValid`; existing_core_port_alias | 1 × 1 | 289,302 | `rtl/e203/perips/accel_icb_slave.v`:76,168,308,388,453 |
| `ACCEL.stream_cursor` | `stream_cursor`; mapped_private_state_or_equivalent_endpoint_needed | 15 × 1 | 184,204 | `rtl/e203/perips/accel_icb_slave.v`:98,232,291,292,553 |
| `ACCEL.stream_error` | `stream_error`; mapped_private_state_or_equivalent_endpoint_needed | 1 × 1 | 350 | `rtl/e203/perips/accel_icb_slave.v`:94,228,378,521,527,540,562 |
| `ACCEL.stream_is_w` | `stream_is_w`; mapped_private_state_or_equivalent_endpoint_needed | 1 × 1 | 183,203 | `rtl/e203/perips/accel_icb_slave.v`:93,191,192,193,195,196,197,198,227,284,290,544 |
| `ACCEL.stream_pair` | `stream_pair`; mapped_private_state_or_equivalent_endpoint_needed | 1 × 1 | 183,203 | `rtl/e203/perips/accel_icb_slave.v`:99,233,280,291,292,546 |
| `ACCEL.stream_pending` | `stream_pending`; mapped_private_state_or_equivalent_endpoint_needed | 1 × 1 | 183,203,268,342,651 | `rtl/e203/perips/accel_icb_slave.v`:92,156,191,192,193,195,196,197,198,226,279,289 |
| `ACCEL.stream_second` | `stream_second`; mapped_private_state_or_equivalent_endpoint_needed | 1 × 1 | 185,205 | `rtl/e203/perips/accel_icb_slave.v`:100,234,280,287,548 |
| `ACCEL.u_linear_compute_core.core.engine.peArray.io_enable` | `u_linear_compute_core.core.engine.peArray.io_enable`; existing_nested_module_port | 1 × 1 | 621 | `rtl/e203/perips/MacPEArray.sv`:6,38,48,58,68,78,88,98,108 |
| `ACCEL.u_linear_compute_core.core.io_group` | `u_linear_compute_core.core.io_group`; existing_nested_module_port | 5 × 1 | 277 | `rtl/e203/perips/LinearCachedCore.sv`:6,52,86 |
| `ACCEL.u_linear_compute_core.head` | `u_linear_compute_core.head`; mapped_private_state_or_equivalent_endpoint_needed | 1 × 1 | 149,349 | `rtl/e203/perips/LinearAutoGroupCore.sv`:124,156,175,221,309,310,311,312,313,314,315,316 |
| `ACCEL.u_linear_compute_core.io_cacheWriteAddr` | `u_linear_compute_core.io_cacheWriteAddr`; existing_nested_module_port | 8 × 1 | 211 | `rtl/e203/perips/LinearAutoGroupCore.sv`:77,278 |
| `ACCEL.u_linear_compute_core.io_cacheWriteData` | `u_linear_compute_core.io_cacheWriteData`; existing_nested_module_port | 40 × 1 | 212,222 | `rtl/e203/perips/LinearAutoGroupCore.sv`:78,279 |
| `ACCEL.u_linear_compute_core.io_cacheWriteEnable` | `u_linear_compute_core.io_cacheWriteEnable`; existing_nested_module_port | 1 × 1 | 142 | `rtl/e203/perips/LinearAutoGroupCore.sv`:76,277 |
| `ACCEL.u_linear_compute_core.io_cacheWriteMask` | `u_linear_compute_core.io_cacheWriteMask`; existing_nested_module_port | 5 × 1 | 213,216 | `rtl/e203/perips/LinearAutoGroupCore.sv`:79,280 |
| `ACCEL.u_linear_compute_core.io_wLoadAddr` | `u_linear_compute_core.io_wLoadAddr`; existing_nested_module_port | 11 × 1 | 167,171,172,173 | `rtl/e203/perips/LinearAutoGroupCore.sv`:56,255 |
| `ACCEL.u_linear_compute_core.io_wLoadBank` | `u_linear_compute_core.io_wLoadBank`; existing_nested_module_port | 3 × 1 | 166,170,174 | `rtl/e203/perips/LinearAutoGroupCore.sv`:55,254 |
| `ACCEL.u_linear_compute_core.io_wLoadData` | `u_linear_compute_core.io_wLoadData`; existing_nested_module_port | 16 × 1 | 168,176,181 | `rtl/e203/perips/LinearAutoGroupCore.sv`:57,256 |
| `ACCEL.u_linear_compute_core.io_wLoadWen` | `u_linear_compute_core.io_wLoadWen`; existing_nested_module_port | 1 × 1 | 140,269 | `rtl/e203/perips/LinearAutoGroupCore.sv`:54,253 |
| `ACCEL.u_linear_compute_core.io_xLoadAddr` | `u_linear_compute_core.io_xLoadAddr`; existing_nested_module_port | 6 × 1 | 191,194 | `rtl/e203/perips/LinearAutoGroupCore.sv`:52,251 |
| `ACCEL.u_linear_compute_core.io_xLoadData` | `u_linear_compute_core.io_xLoadData`; existing_nested_module_port | 16 × 1 | 192,196,201 | `rtl/e203/perips/LinearAutoGroupCore.sv`:53,252 |
| `ACCEL.u_linear_compute_core.io_xLoadWen` | `u_linear_compute_core.io_xLoadWen`; existing_nested_module_port | 1 × 1 | 141,269 | `rtl/e203/perips/LinearAutoGroupCore.sv`:51,250 |
| `ACCEL.u_linear_compute_core.tail` | `u_linear_compute_core.tail`; mapped_private_state_or_equivalent_endpoint_needed | 1 × 1 | 149,349 | `rtl/e203/perips/LinearAutoGroupCore.sv`:125,157,176,178,190,222 |
| `ACCEL.w_addr_reg` | `w_addr_reg`; mapped_private_state_or_equivalent_endpoint_needed | 11 × 1 | 387,389,678 | `rtl/e203/perips/accel_icb_slave.v`:111,197,245,344,494 |
| `ACCEL.w_bank_reg` | `w_bank_reg`; mapped_private_state_or_equivalent_endpoint_needed | 3 × 1 | 387,389,678 | `rtl/e203/perips/accel_icb_slave.v`:110,196,244,341,491 |
| `ACCEL.w_cursor` | `w_cursor`; mapped_private_state_or_equivalent_endpoint_needed | 15 × 1 | 350,680,682 | `rtl/e203/perips/accel_icb_slave.v`:90,224,291,374,522,534,537,549,552,555 |
| `ACCEL.w_load_wen` | `w_load_wen`; mapped_private_state_or_equivalent_endpoint_needed | 1 × 1 | 342 | `rtl/e203/perips/accel_icb_slave.v`:113,139,195,247,269,498 |
| `ACCEL.x_addr_reg` | `x_addr_reg`; mapped_private_state_or_equivalent_endpoint_needed | 6 × 1 | 396,398,679 | `rtl/e203/perips/accel_icb_slave.v`:106,192,240,335,483 |
| `ACCEL.x_cursor` | `x_cursor`; mapped_private_state_or_equivalent_endpoint_needed | 7 × 1 | 350,681,683 | `rtl/e203/perips/accel_icb_slave.v`:91,225,292,376,528,536,538,552,555 |
| `ACCEL.x_load_wen` | `x_load_wen`; mapped_private_state_or_equivalent_endpoint_needed | 1 × 1 | 342 | `rtl/e203/perips/accel_icb_slave.v`:108,139,191,242,268,487 |
| `EXU.u_e203_exu_commit.alu_cmt_i_pc` | `u_e203_exu_commit.alu_cmt_i_pc`; existing_commit_input_port | 32 × 1 | 1737 | `rtl/e203/core/e203_exu_commit.v`:60,175,241 |
| `EXU.u_e203_exu_commit.alu_cmt_i_valid` | `u_e203_exu_commit.alu_cmt_i_valid`; existing_commit_input_port | 1 × 1 | 1737 | `rtl/e203/core/e203_exu_commit.v`:58,167,235,317 |
| `EXU.u_e203_exu_regfile.rf_r` | `u_e203_exu_regfile.regfile[3].rfno0.rf_dffl.qout`; existing_rf3_dff_output_candidate | 32 × 1 | 1738,1739 | `rtl/e203/core/e203_exu_regfile.v`:45,64,79,81,88,89,91,92,93,94,95,96 |
| `XU_HCLK.pll_ASLEEP` | `pll_ASLEEP`; existing_hclkgen_input_port | 1 × 1 | 13 | `rtl/e203/subsys/e203_subsys_hclkgen.v`:39,56 |
| `XU_HCLK.pll_M` | `pll_M`; existing_hclkgen_input_port | 8 × 1 | 14 | `rtl/e203/subsys/e203_subsys_hclkgen.v`:41,61 |
| `XU_HCLK.pll_N` | `pll_N`; existing_hclkgen_input_port | 5 × 1 | 14 | `rtl/e203/subsys/e203_subsys_hclkgen.v`:42,62 |
| `XU_HCLK.pll_OD` | `pll_OD`; existing_hclkgen_input_port | 2 × 1 | 14 | `rtl/e203/subsys/e203_subsys_hclkgen.v`:40,60 |
| `XU_HCLK.pll_RESET` | `pll_RESET`; existing_hclkgen_input_port | 1 × 1 | 13 | `rtl/e203/subsys/e203_subsys_hclkgen.v`:38,59 |
| `XU_HCLK.pllbypass` | `pllbypass`; existing_hclkgen_input_port | 1 × 1 | 12 | `rtl/e203/subsys/e203_subsys_hclkgen.v`:37,104 |
| `XU_HCLK.plloutdiv` | `plloutdiv`; existing_hclkgen_input_port | 6 × 1 | 12,13 | `rtl/e203/subsys/e203_subsys_hclkgen.v`:44,93 |
| `XU_HCLK.plloutdivby1` | `plloutdivby1`; existing_hclkgen_input_port | 1 × 1 | 12 | `rtl/e203/subsys/e203_subsys_hclkgen.v`:43,92 |
| `XU_HCLK.test_mode` | `test_mode`; existing_hclkgen_input_port | 1 × 1 | 12 | `rtl/e203/subsys/e203_subsys_hclkgen.v`:32,72,81,90,101,110 |
