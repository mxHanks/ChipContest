// Passive startup-init audit. No DUT assignment, force, waiver or X coercion.
`define S3_DTCM dut.u_soc.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top.u_e203_cpu.u_e203_dtcm_ctrl
`define S3_RAW dut.u_soc.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top.u_e203_srams.u_e203_dtcm_ram.u_e203_dtcm_gnrl_ram.u_sirv_sim_ram
`define S3_RF dut.u_soc.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top.u_e203_cpu.u_e203_core.u_e203_exu.u_e203_exu_regfile
  integer s3_dtcm_commands=0,s3_dtcm_responses=0,s3_dtcm_writes=0,s3_dtcm_reads=0;
  integer s3_dtcm_unknown_writes=0,s3_dtcm_unknown_reads=0,s3_dtcm_head=0,s3_dtcm_tail=0,s3_dtcm_pending=0;
  integer s3_dtcm_ram_writes=0,s3_dtcm_ram_reads=0,s3_dtcm_byte,s3_dtcm_unknown_bits;
  reg s3_dtcm_read_queue[0:15];
  reg [11:0] s3_callee_seen=0;
  integer s3_callee_index;
  always @(posedge `S3_DTCM.clk_dtcm_ram) if (`S3_DTCM.rst_n===1'b1) begin
    if (`S3_DTCM.dtcm_ram_cs!==1'b0) begin
      if (`S3_DTCM.dtcm_ram_cs!==1'b1 || (^`S3_DTCM.dtcm_ram_addr)===1'bx ||
          (`S3_DTCM.dtcm_ram_we!==1'b0 && `S3_DTCM.dtcm_ram_we!==1'b1) ||
          (^`S3_DTCM.dtcm_ram_wem)===1'bx)
        $fatal(1,"S3_DTCM_UNKNOWN_CONTROL sampled active RAM control");
      if (`S3_DTCM.dtcm_ram_we) begin
        s3_dtcm_ram_writes=s3_dtcm_ram_writes+1;
        s3_dtcm_unknown_bits=0;
        for(s3_dtcm_byte=0;s3_dtcm_byte<32;s3_dtcm_byte=s3_dtcm_byte+1)
          if(`S3_DTCM.dtcm_ram_wem[s3_dtcm_byte/8] &&
             (`S3_DTCM.dtcm_ram_din[s3_dtcm_byte]!==1'b0 && `S3_DTCM.dtcm_ram_din[s3_dtcm_byte]!==1'b1))
            s3_dtcm_unknown_bits=s3_dtcm_unknown_bits+1;
        $display("S3_DTCM_SAMPLED_WRITE tick_fs=%0.0f address=%h mask=%h data=%h unknown_effective_bits=%0d",
          $realtime*1000000.0,`S3_DTCM.dtcm_ram_addr,`S3_DTCM.dtcm_ram_wem,`S3_DTCM.dtcm_ram_din,s3_dtcm_unknown_bits);
        if(s3_dtcm_unknown_bits) begin
          s3_dtcm_unknown_writes=s3_dtcm_unknown_writes+1;
          $fatal(1,"S3_DTCM_ACTIVE_UNKNOWN_WRITE sampled enabled data bits");
        end
      end else s3_dtcm_ram_reads=s3_dtcm_ram_reads+1;
    end
  end
  // RF writes also occur while the separately gated DTCM controller is idle.
  always @(posedge `S3_RF.clk) if (`S3_RF.rst_n===1'b1) begin
    if(`S3_RF.wbck_dest_wen===1'b1) begin
      s3_callee_index=-1;
      if(`S3_RF.wbck_dest_idx==8)s3_callee_index=0;
      else if(`S3_RF.wbck_dest_idx==9)s3_callee_index=1;
      else if(`S3_RF.wbck_dest_idx>=18 && `S3_RF.wbck_dest_idx<=27)s3_callee_index=`S3_RF.wbck_dest_idx-16;
      if(s3_callee_index>=0) begin
        if((^`S3_RF.wbck_dest_dat)===1'bx)$fatal(1,"S3_CALLEE_UNKNOWN_WRITEBACK");
        if(!s3_callee_seen[s3_callee_index]) begin
          s3_callee_seen[s3_callee_index]=1;
          $display("S3_CALLEE_FIRST_DEFINED index=%0d tick_fs=%0.0f value=%h",s3_callee_index,$realtime*1000000.0,`S3_RF.wbck_dest_dat);
        end
      end
    end
  end
  always @(posedge `S3_DTCM.clk) if (`S3_DTCM.rst_n===1'b1) begin
    // Retire before accepting a same-edge replacement command.
    if(`S3_DTCM.lsu2dtcm_icb_rsp_valid && `S3_DTCM.lsu2dtcm_icb_rsp_ready) begin
      if(s3_dtcm_pending==0 || `S3_DTCM.lsu2dtcm_icb_rsp_err!==1'b0 ||
         `S3_DTCM.sram_icb_rsp_read!==s3_dtcm_read_queue[s3_dtcm_head])
        $fatal(1,"S3_DTCM_RESPONSE_CONSERVATION");
      if(s3_dtcm_read_queue[s3_dtcm_head]) begin
        if((^`S3_RAW.raw_data)===1'bx) begin
          s3_dtcm_unknown_reads=s3_dtcm_unknown_reads+1;
          $fatal(1,"S3_DTCM_ACTIVE_UNKNOWN_READ raw data at actual read-response use");
        end
        if(`S3_DTCM.lsu2dtcm_icb_rsp_rdata!==`S3_RAW.raw_data)
          $fatal(1,"S3_DTCM_RAW_RESPONSE_DIFFERS no reliance on FORCE_X2ZERO");
        $display("S3_DTCM_KNOWN_READ_RESPONSE tick_fs=%0.0f raw=%h data=%h",$realtime*1000000.0,`S3_RAW.raw_data,`S3_DTCM.lsu2dtcm_icb_rsp_rdata);
      end
      s3_dtcm_head=(s3_dtcm_head+1)%16;s3_dtcm_pending=s3_dtcm_pending-1;s3_dtcm_responses=s3_dtcm_responses+1;
    end
    if(`S3_DTCM.lsu2dtcm_icb_cmd_valid && `S3_DTCM.lsu2dtcm_icb_cmd_ready) begin
      if(s3_dtcm_pending==16 || (^`S3_DTCM.lsu2dtcm_icb_cmd_addr)===1'bx ||
         (`S3_DTCM.lsu2dtcm_icb_cmd_read!==1'b0 && `S3_DTCM.lsu2dtcm_icb_cmd_read!==1'b1))
        $fatal(1,"S3_DTCM_COMMAND_CONTROL");
      s3_dtcm_read_queue[s3_dtcm_tail]=`S3_DTCM.lsu2dtcm_icb_cmd_read;
      s3_dtcm_tail=(s3_dtcm_tail+1)%16;s3_dtcm_pending=s3_dtcm_pending+1;s3_dtcm_commands=s3_dtcm_commands+1;
      if(`S3_DTCM.lsu2dtcm_icb_cmd_read)s3_dtcm_reads=s3_dtcm_reads+1;
      else s3_dtcm_writes=s3_dtcm_writes+1;
    end
  end
  final begin
    $display("S3_DTCM_UNKNOWN_AUDIT_SUMMARY commands=%0d responses=%0d writes=%0d reads=%0d ram_writes=%0d ram_reads=%0d unknown_writes=%0d unknown_reads=%0d pending=%0d callee_seen=%h scope=reset_through_post_payload_epilogue generic_non_ppa=1",
      s3_dtcm_commands,s3_dtcm_responses,s3_dtcm_writes,s3_dtcm_reads,s3_dtcm_ram_writes,s3_dtcm_ram_reads,
      s3_dtcm_unknown_writes,s3_dtcm_unknown_reads,s3_dtcm_pending,s3_callee_seen);
    if(s3_dtcm_unknown_writes==0 && s3_dtcm_unknown_reads==0 && s3_dtcm_commands==s3_dtcm_responses &&
       s3_dtcm_pending==0 && s3_dtcm_writes==s3_dtcm_ram_writes && s3_dtcm_reads==s3_dtcm_ram_reads && s3_callee_seen==12'hfff)
      $display("S3_DTCM_UNKNOWN_AUDIT_PASS no_effective_unknown full_process generic_non_ppa=1");
  end
