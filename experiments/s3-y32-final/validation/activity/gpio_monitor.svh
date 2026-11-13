// Read-only activity observer. No signal here drives DUT, endpoint or stimulus.
// The C++ driver arms on the HF falling edge BEFORE the clear acceptance.
wire [63:0] activity_gpio_first_fs /* verilator public_flat_rd */ = gpio_first_data_fs;
wire [31:0] activity_gpio_first_cycle /* verilator public_flat_rd */ = gpio_first_data;
wire activity_capture_enabled /* verilator public_flat_rd */ = startup_complete && shared_mem_rst_n && !warmup_active;
wire activity_hf_clk /* verilator public_flat_rd */ = clk;
wire activity_arm /* verilator public_flat_rd */ = startup_complete &&
  shared_mem_rst_n && !warmup_active && `DMA.cfg_cmd_valid && `DMA.cfg_cmd_ready &&
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
reg activity_is_y[0:3];
integer activity_owner_read=0,activity_owner_write=0,activity_owner_count=0;
always @(posedge shared_mem_clk) begin
  if (startup_complete && shared_mem_rst_n && !warmup_active) begin
    if (`DMA.cfg_cmd_valid && `DMA.cfg_cmd_ready && !`DMA.cfg_cmd_read &&
        `DMA.cfg_cmd_addr[8:0] == 9'h104 && `DMA.cfg_cmd_wdata == 32'd1) begin
      activity_clear_fs <= longint'($realtime / 1fs);
      activity_clear_cycle <= cycles;
      activity_clear_seq <= call_index;
      activity_y_responses <= 0;
      activity_owner_read=0;activity_owner_write=0;activity_owner_count=0;
      for(integer a=0;a<4;a++)activity_is_y[a]=0;
    end else begin
      // This metadata-only ledger is independent of the DUT and timestamps
      // accepted Y write responses; up to four owners may be outstanding.
      if (`DMA.mem_rsp_valid && `DMA.mem_rsp_ready) begin
        if(activity_owner_count<1)$fatal(1,"activity orphan response");
        if(activity_is_y[activity_owner_read])begin
          activity_y_responses <= activity_y_responses + 1;
          if(activity_y_responses==25343)begin
            activity_last_y_fs <= longint'($realtime / 1fs);
            activity_last_y_cycle <= cycles;
            activity_end_seq <= call_index;
          end
        end
        activity_is_y[activity_owner_read]=0;
        activity_owner_read=(activity_owner_read+1)%4;activity_owner_count=activity_owner_count-1;
      end
      if (`DMA.mem_cmd_valid && `DMA.mem_cmd_ready)begin
        if(activity_owner_count>=4)$fatal(1,"activity metadata owner overflow");
        activity_is_y[activity_owner_write]= !`DMA.mem_cmd_read &&
          `DMA.mem_cmd_addr >= BASE + YOFF && `DMA.mem_cmd_addr < BASE + YOFF + 25344 * 4;
        activity_owner_write=(activity_owner_write+1)%4;activity_owner_count=activity_owner_count+1;
      end
    end
  end
end
