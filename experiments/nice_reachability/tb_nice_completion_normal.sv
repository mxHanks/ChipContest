`include "e203_defines.v"
module tb_nice_completion_normal;
  reg clk=0, lfclk=0, rst_n=0;
  always #2 clk=~clk;
  always #33 lfclk=~lfclk;
  wire cmd_valid, cmd_read, cmd_ready, rsp_ready;
  wire [31:0] cmd_addr, cmd_wdata;
  wire [3:0] cmd_wmask;
  reg rsp_valid=0, rsp_err=0;
  reg [31:0] rsp_rdata=0;
  reg [31:0] ram[0:7];
  reg [7:0] program_bytes[0:65535];
  string testcase;
  integer cycles=0, request_cycle=0, requests=0, responses=0;
  integer polls=0, lanes=0, pops=0, writes=0, checked=0, pending=0;
  reg [7:0] seen_writes=0, seen_checks=0;
  integer error_write=-1, committed=0, failed_responses=0;
  integer source_pending_kind=0, retired_pops=0;
  reg [4:0] rd;
  reg [`E203_ITAG_WIDTH-1:0] tag;
  assign cmd_ready=(!rsp_valid || rsp_ready) && cycles%7!=0;
  `define CPU dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top
  `define EXU `CPU.u_e203_cpu.u_e203_core.u_e203_exu
  `define NICE `CPU.u_e203_cpu.u_e203_nice_core
  `define FRONT `EXU.u_e203_exu_alu.u_e203_exu_nice
  `define OITF `EXU.u_e203_exu_oitf
  `define WB `EXU.u_e203_exu_longpwbck
  `define ITCM `CPU.u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram
  function automatic [31:0] golden(input integer lane);
    case(lane)
      0,2: golden=0;
      1,6: golden=2;
      3,7: golden=-2;
      4: golden=1;
      5: golden=-1;
      default: golden=32'bx;
    endcase
  endfunction
  e203_soc_top #(.EXTERNAL_SYSMEM(1)) dut (
    .hfextclk(clk), .lfextclk(lfclk), .io_pads_aon_erst_n_i_ival(rst_n),
    .io_pads_jtag_TCK_i_ival(1'b0), .io_pads_jtag_TMS_i_ival(1'b0),
    .io_pads_jtag_TDI_i_ival(1'b0), .io_pads_gpioA_i_ival(32'b0),
    .io_pads_gpioB_i_ival(32'b0), .io_pads_qspi0_dq_0_i_ival(1'b0),
    .io_pads_qspi0_dq_1_i_ival(1'b0), .io_pads_qspi0_dq_2_i_ival(1'b0),
    .io_pads_qspi0_dq_3_i_ival(1'b0), .io_pads_bootrom_n_i_ival(1'b0),
    .io_pads_dbgmode0_n_i_ival(1'b1), .io_pads_dbgmode1_n_i_ival(1'b1),
    .io_pads_dbgmode2_n_i_ival(1'b1), .io_pads_aon_pmu_dwakeup_n_i_ival(1'b1),
    .ext_sysmem_cmd_valid(cmd_valid), .ext_sysmem_cmd_ready(cmd_ready),
    .ext_sysmem_cmd_addr(cmd_addr), .ext_sysmem_cmd_read(cmd_read),
    .ext_sysmem_cmd_wdata(cmd_wdata), .ext_sysmem_cmd_wmask(cmd_wmask),
    .ext_sysmem_rsp_valid(rsp_valid), .ext_sysmem_rsp_ready(rsp_ready),
    .ext_sysmem_rsp_err(rsp_err), .ext_sysmem_rsp_rdata(rsp_rdata),
    .hfxoscen(), .lfxoscen(), .io_pads_jtag_TDO_o_oval(), .io_pads_jtag_TDO_o_oe(),
    .io_pads_gpioA_o_oval(), .io_pads_gpioA_o_oe(), .io_pads_gpioB_o_oval(), .io_pads_gpioB_o_oe(),
    .io_pads_qspi0_sck_o_oval(), .io_pads_qspi0_cs_0_o_oval(),
    .io_pads_qspi0_dq_0_o_oval(), .io_pads_qspi0_dq_0_o_oe(),
    .io_pads_qspi0_dq_1_o_oval(), .io_pads_qspi0_dq_1_o_oe(),
    .io_pads_qspi0_dq_2_o_oval(), .io_pads_qspi0_dq_2_o_oe(),
    .io_pads_qspi0_dq_3_o_oval(), .io_pads_qspi0_dq_3_o_oe(),
    .io_pads_aon_pmu_padrst_o_oval(), .io_pads_aon_pmu_vddpaden_o_oval()
  );
  initial begin : initialize
    integer i;
    if(!$value$plusargs("TESTCASE=%s",testcase)) $fatal(1,"missing TESTCASE");
    if(!$value$plusargs("ERROR_WRITE=%d",error_write)) error_write=-1;
    if(error_write < -1 || error_write > 7) $fatal(1,"invalid error-write lane");
    for(i=0;i<65536;i=i+1) program_bytes[i]=0;
    $readmemh({testcase,".verilog"},program_bytes);
    for(i=0;i<8192;i=i+1)
      `ITCM.mem_r[i]={program_bytes[8*i+7],program_bytes[8*i+6],program_bytes[8*i+5],
        program_bytes[8*i+4],program_bytes[8*i+3],program_bytes[8*i+2],program_bytes[8*i+1],program_bytes[8*i]};
    for(i=0;i<8;i=i+1) ram[i]=32'hdeadbeef;
    #120 rst_n=1;
  end
  always @(posedge clk) begin : observe
    integer lane;
    cycles=cycles+1;
    if(cycles>100000) $fatal(1,"small real CPU drain watchdog");
    if(rst_n) begin
      if(rsp_valid && rsp_ready) begin
        pending=pending-1; rsp_valid<=0;
        if(rsp_err) failed_responses=failed_responses+1;
      end
      if(cmd_valid && cmd_ready) begin
        if(cmd_addr<32'ha0020000 || cmd_addr>32'ha002001c || cmd_addr[1:0]!=0)
          $fatal(1,"unexpected small-probe shared address %h",cmd_addr);
        lane=(cmd_addr-32'ha0020000)/4;
        pending=pending+1; rsp_valid<=1; rsp_err<=0;
        if(!cmd_read) begin
          if(responses || requests!=1 || seen_writes[lane] || cmd_wmask!==15 ||
              lane!=writes || cmd_wdata!==golden(lane)) $fatal(1,"bad real NICE output/owner/order");
          if(lane==7 && retired_pops!=1) $fatal(1,"last write preceded successful POP response");
          if(lane==error_write) rsp_err<=1;
          else begin ram[lane]=cmd_wdata; committed=committed+1; end
          seen_writes[lane]=1; writes=writes+1; rsp_rdata<=0;
        end else begin
          if(error_write>=0 || responses!=1 || seen_checks[lane] || ram[lane]!==golden(lane))
            $fatal(1,"CPU readback preceded real NICE completion");
          seen_checks[lane]=1; checked=checked+1; rsp_rdata<=ram[lane];
        end
      end else if(cmd_ready && !rsp_valid) rsp_valid<=0;
      if(pending<0 || pending>1) $fatal(1,"shared response conservation");
      if(`NICE.nice_req_valid && `NICE.nice_req_ready) begin
        if(requests || `NICE.nice_req_rs1!==32'ha0020000 || `NICE.nice_req_rs2!==3200 ||
            `NICE.nice_req_inst[31:25]!==7'h20 || `NICE.nice_req_inst[14:12]!==7 ||
            `NICE.nice_req_inst[11:7]==0 || !`OITF.dis_ena || !`OITF.disp_i_rdwen)
          $fatal(1,"bad small real NICE instruction allocation");
        requests=1; request_cycle=cycles; tag=`OITF.dis_ptr; rd=`NICE.nice_req_inst[11:7];
        $display("NICE_NORMAL_REQUEST rd=%0d tag=%0d cycle=%0d",rd,tag,cycles);
      end
      if(`NICE.nice_icb_rsp_valid && `NICE.nice_icb_rsp_ready) begin
        if(!source_pending_kind) $fatal(1,"unowned NICE response");
        if(source_pending_kind==2) begin
          if(`NICE.nice_icb_rsp_err) $fatal(1,"POP unexpectedly failed");
          retired_pops=retired_pops+1;
        end
        source_pending_kind=0;
      end
      if(`NICE.nice_icb_cmd_valid && `NICE.nice_icb_cmd_ready) begin
        if(source_pending_kind) $fatal(1,"multiple NICE bus commands outstanding");
        source_pending_kind=(!`NICE.nice_icb_cmd_read && `NICE.nice_icb_cmd_addr==32'h100420c8) ? 2 : 1;
        if(!requests || responses) $fatal(1,"NICE command outside owned instruction");
        if(`NICE.nice_icb_cmd_read && `NICE.nice_icb_cmd_addr==32'h100420c4) polls=polls+1;
        else if(`NICE.nice_icb_cmd_read && `NICE.nice_icb_cmd_addr>=32'h10042180 &&
            `NICE.nice_icb_cmd_addr<=32'h1004219c) lanes=lanes+1;
        else if(!`NICE.nice_icb_cmd_read && `NICE.nice_icb_cmd_addr==32'h100420c8) pops=pops+1;
        else if(`NICE.nice_icb_cmd_read || `NICE.nice_icb_cmd_addr<32'ha0020000 ||
            `NICE.nice_icb_cmd_addr>32'ha002001c) $fatal(1,"unexpected NICE source command");
      end
      if(`NICE.nice_rsp_valid && `NICE.nice_rsp_ready) begin
        if(responses || writes!=(error_write>=0 ? error_write+1 : 8) || polls<1 || lanes!=8 ||
            pops!=(error_write>=0 && error_write<7 ? 0 : 1) || retired_pops!=pops || pending ||
            source_pending_kind || committed!=(error_write>=0 ? error_write : 8) ||
            failed_responses!=(error_write>=0 ? 1 : 0) ||
            `NICE.nice_rsp_err!==(error_write>=0) || `NICE.nice_rsp_rdat!==(error_write>=0 ? 32'd8 : 32'd0) ||
            !`OITF.ret_ena || `OITF.ret_ptr!==tag || !`OITF.ret_rdwen || `OITF.ret_rdidx!==rd ||
            !`WB.wbck_sel_nice || !`WB.longp_wbck_o_valid || !`WB.longp_wbck_o_ready ||
            `WB.longp_wbck_o_wdat!==(error_write>=0 ? 32'd8 : 32'd0) || `WB.longp_wbck_o_rdidx!==rd)
          $fatal(1,"small drain completion did not retire through actual OITF/rd");
        responses=1;
        $display("NICE_NORMAL_RETIRED code=%0d error_write=%0d cycle=%0d",error_write>=0 ? 8 : 0,error_write,cycles);
      end
      if(requests && !responses && cycles-request_cycle>1024) begin
        $display("NICE_COMPLETION_BLOCKED valid=%b ready=%b code=%h state=%0d owner=%b fifo_valid=%b fifo_tag=%0d oitf_empty=%b ret_ptr=%0d ret_rdwen=%b ret_rdidx=%0d wb_selected=%b wb_ready=%b writes=%0d polls=%0d lanes=%0d pops=%0d",
          `NICE.nice_rsp_valid,`NICE.nice_rsp_ready,`NICE.nice_rsp_rdat,
          `NICE.u_drain8.state,`NICE.owner_valid,`FRONT.fifo_o_vld,`FRONT.nice_o_itag,
          `OITF.oitf_empty,`OITF.ret_ptr,`OITF.ret_rdwen,`OITF.ret_rdidx,
          `WB.wbck_sel_nice,`WB.nice_longp_wbck_i_ready,writes,polls,lanes,pops);
        $fatal(1,"real CPU normal completion exceeded bounded small-fixture latency");
      end
      if(`EXU.u_e203_exu_commit.alu_cmt_i_valid && `EXU.u_e203_exu_commit.alu_cmt_i_ready &&
          `EXU.u_e203_exu_commit.alu_cmt_i_pc==32'h80000086) begin
        if(`EXU.u_e203_exu_regfile.rf_r[3]!==1 || requests!=1 || responses!=1 ||
            writes!=(error_write>=0 ? error_write+1 : 8) || checked!=(error_write>=0 ? 0 : 8) ||
            seen_writes!==((9'b1<<writes)-1) || seen_checks!==(error_write>=0 ? 8'h00 : 8'hff) || pending)
          $fatal(1,"CPU did not validate actual drain outputs/error");
        for(lane=0;lane<8;lane=lane+1)
          if(ram[lane]!==(lane<committed ? golden(lane) : 32'hdeadbeef))
          $fatal(1,"CPU did not validate actual drain outputs");
        $display("NICE_NORMAL_CPU_PASS requests=1 responses=1 code=%0d error_write=%0d writes=%0d committed=%0d checked=%0d pops=%0d cycles=%0d",
          error_write>=0 ? 8 : 0,error_write,writes,committed,checked,retired_pops,cycles);
        $finish;
      end
    end
  end
endmodule
