// Read-only activity observer. No signal here drives DUT, endpoint or stimulus.
// The C++ driver arms on the HF falling edge BEFORE the clear acceptance.
wire [63:0] activity_gpio_first_fs /* verilator public_flat_rd */ = gpio_first_data_fs;
wire [31:0] activity_gpio_first_cycle /* verilator public_flat_rd */ = gpio_first_data;
wire activity_hf_clk /* verilator public_flat_rd */ = clk;
wire activity_arm /* verilator public_flat_rd */ = startup_complete &&
  shared_mem_rst_n && !warmup_active && `DMA.cfg_cmd_valid &&
  !`DMA.cfg_cmd_read && `DMA.cfg_cmd_addr[8:0] == 9'h104 &&
  `DMA.cfg_cmd_wdata == 32'd1;
wire [31:0] activity_layer /* verilator public_flat_rd */ = layer;
wire [31:0] activity_call /* verilator public_flat_rd */ = call_index;
longint unsigned activity_clear_fs /* verilator public_flat_rd */ = 0;
longint unsigned activity_last_y_fs /* verilator public_flat_rd */ = 0;
integer activity_clear_cycle /* verilator public_flat_rd */ = -1;
integer activity_last_y_cycle /* verilator public_flat_rd */ = -1;
integer activity_clear_seq /* verilator public_flat_rd */ = 0;
integer activity_end_seq /* verilator public_flat_rd */ = 0;
integer activity_y_responses = 0;
reg activity_y_pending = 0;
always @(posedge shared_mem_clk) begin
  if (startup_complete && shared_mem_rst_n && !warmup_active) begin
    if (`DMA.cfg_cmd_valid && `DMA.cfg_cmd_ready && !`DMA.cfg_cmd_read &&
        `DMA.cfg_cmd_addr[8:0] == 9'h104 && `DMA.cfg_cmd_wdata == 32'd1) begin
      activity_clear_fs <= longint'($realtime / 1fs);
      activity_clear_cycle <= cycles;
      activity_clear_seq <= call_index;
      activity_y_responses <= 0;
      activity_y_pending <= 0;
    end else begin
      // Response first, then a possible next command, matches the original
      // independent monitor and does not assume no same-cycle replacement.
      if (`DMA.mem_rsp_valid && `DMA.mem_rsp_ready && activity_y_pending) begin
        activity_y_responses <= activity_y_responses + 1;
        activity_y_pending <= 0;
        if (activity_y_responses == 25343) begin
          activity_last_y_fs <= longint'($realtime / 1fs);
          activity_last_y_cycle <= cycles;
          activity_end_seq <= call_index;
        end
      end
      if (`DMA.mem_cmd_valid && `DMA.mem_cmd_ready)
        activity_y_pending <= !`DMA.mem_cmd_read &&
          `DMA.mem_cmd_addr >= BASE + YOFF &&
          `DMA.mem_cmd_addr < BASE + YOFF + 25344 * 4;
    end
  end
end
