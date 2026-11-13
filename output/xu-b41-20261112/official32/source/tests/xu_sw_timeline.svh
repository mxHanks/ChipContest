// Passive timing and CPU-operation observer. It never drives DUT signals.
integer xu_sw_call=0, xu_sw_cfg_begin=-1, xu_sw_clear_discovered=-1;
integer xu_sw_compute_first=-1, xu_sw_compute_last=-1, xu_sw_discovered=-1;
integer xu_sw_report_accept=-1, xu_sw_report_retire=-1;
integer xu_sw_clear_reads=0, xu_sw_compute_reads=0;
integer xu_sw_retired_begin=0, xu_sw_retired_report=0;
integer xu_sw_itcm_total=0, xu_sw_itcm_begin=0, xu_sw_itcm_report=0;
reg xu_sw_cfg_read=0, xu_sw_report_pending=0;
reg [6:0] xu_sw_cfg_offset=0;

always @(posedge `CPU.u_e203_srams.clk_itcm_ram)
  if (`CPU.u_e203_srams.itcm_ram_cs) xu_sw_itcm_total <= xu_sw_itcm_total+1;

always @(posedge shared_mem_clk) begin
  if (!shared_mem_rst_n) begin
    xu_sw_cfg_read=0; xu_sw_report_pending=0;
  end else if (startup_complete) begin
    if (xu_sw_call!=call_index) begin
      xu_sw_call=call_index;
      xu_sw_cfg_begin=-1; xu_sw_clear_discovered=-1;
      xu_sw_compute_first=-1; xu_sw_compute_last=-1; xu_sw_discovered=-1;
      xu_sw_report_accept=-1; xu_sw_report_retire=-1;
      xu_sw_clear_reads=0; xu_sw_compute_reads=0;
      xu_sw_retired_begin=0; xu_sw_retired_report=0;
      xu_sw_itcm_begin=0; xu_sw_itcm_report=0;
    end
    if (`DMA.cfg_rsp_valid && `DMA.cfg_rsp_ready) begin
      if (xu_sw_cfg_read && xu_sw_cfg_offset==7'h08 && !`DMA.cfg_rsp_err &&
          !`DMA.cfg_rsp_rdata[0] && !`DMA.cfg_rsp_rdata[2]) begin
        if (`DMA.cfg_rsp_rdata[3] && xu_sw_clear_discovered<0)
          xu_sw_clear_discovered=cycles;
        if (`DMA.cfg_rsp_rdata[1] && start_seen && xu_sw_discovered<0)
          xu_sw_discovered=cycles;
      end
      xu_sw_cfg_read=0;
    end
    if (`DMA.cfg_cmd_valid && `DMA.cfg_cmd_ready) begin
      xu_sw_cfg_read=`DMA.cfg_cmd_read;
      xu_sw_cfg_offset=`DMA.cfg_cmd_addr[6:0];
      if (`DMA.cfg_cmd_read && xu_sw_cfg_offset==7'h08) begin
        if (start_seen) xu_sw_compute_reads=xu_sw_compute_reads+1;
        else xu_sw_clear_reads=xu_sw_clear_reads+1;
      end
      if (!`DMA.cfg_cmd_read && xu_sw_cfg_offset==7'h04 && `DMA.cfg_cmd_wdata==1) begin
        xu_sw_retired_begin=`EXU.u_e203_exu_csr.minstret_r;
        xu_sw_itcm_begin=xu_sw_itcm_total;
      end
      if (!`DMA.cfg_cmd_read && xu_sw_cfg_offset==7'h10 && xu_sw_cfg_begin<0)
        xu_sw_cfg_begin=cycles;
    end
    if (`DMA.core_mac_step) begin
      if (xu_sw_compute_first<0) xu_sw_compute_first=cycles;
      xu_sw_compute_last=cycles;
    end
    if (rsp_valid && rsp_ready && xu_sw_report_pending) begin
      xu_sw_report_retire=cycles;
      xu_sw_report_pending=0;
    end
    if (cmd_valid && cmd_ready && cmd_is32 && !cmd_read && cmd_addr==BASE+HOST+4) begin
      xu_sw_report_accept=cycles;
      xu_sw_report_pending=1;
      xu_sw_retired_report=`EXU.u_e203_exu_csr.minstret_r;
      xu_sw_itcm_report=xu_sw_itcm_total;
    end
  end
end

task xu_sw_report;
  begin
    if (xu_sw_cfg_begin<0 || xu_sw_clear_discovered<0 || xu_sw_compute_first<0 ||
        xu_sw_compute_last<xu_sw_compute_first || xu_sw_discovered<done_cycle ||
        xu_sw_report_accept<xu_sw_discovered || xu_sw_report_retire<xu_sw_report_accept)
      $fatal(1,"XU_SW64 incomplete or unordered software timing");
    $display("XU_SW64 call=%0d layer=%0d warmup=%0d config_begin=%0d clear_discovered=%0d compute_first=%0d compute_last=%0d discovered=%0d report_accept=%0d report_retire=%0d retired=%0d itcm_accesses=%0d clear_reads=%0d compute_reads=%0d",
      call_index,layer,warmup_active,xu_sw_cfg_begin,xu_sw_clear_discovered,
      xu_sw_compute_first,xu_sw_compute_last,xu_sw_discovered,
      xu_sw_report_accept,xu_sw_report_retire,xu_sw_retired_report-xu_sw_retired_begin,
      xu_sw_itcm_report-xu_sw_itcm_begin,xu_sw_clear_reads,xu_sw_compute_reads);
  end
endtask
