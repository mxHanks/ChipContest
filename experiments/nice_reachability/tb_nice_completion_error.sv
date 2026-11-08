`include "e203_defines.v"
module tb_nice_completion_error;
  reg clk=0, lfclk=0, rst_n=0;
  always #2 clk=~clk;
  always #33 lfclk=~lfclk;
  wire cmd_valid, cmd_ready=1, cmd_read, rsp_ready;
  wire [31:0] cmd_addr, cmd_wdata;
  wire [3:0] cmd_wmask;
  wire rsp_valid=0;
  wire [31:0] rsp_rdata=0;
  reg [7:0] program_bytes[0:65535];
  string testcase;
  integer cycles=0, request_cycle=0, requests=0, responses=0;
  integer expected_code=2, bus_commands=0, bus_responses=0;
  reg [4:0] rd;
  reg [`E203_ITAG_WIDTH-1:0] tag;
  `define CPU dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top
  `define EXU `CPU.u_e203_cpu.u_e203_core.u_e203_exu
  `define NICE `CPU.u_e203_cpu.u_e203_nice_core
  `define FRONT `EXU.u_e203_exu_alu.u_e203_exu_nice
  `define OITF `EXU.u_e203_exu_oitf
  `define WB `EXU.u_e203_exu_longpwbck
  `define ITCM `CPU.u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram
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
    .ext_sysmem_rsp_err(1'b0), .ext_sysmem_rsp_rdata(rsp_rdata),
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
    if(!$value$plusargs("EXPECT_CODE=%d",expected_code)) expected_code=2;
    if(expected_code!=1 && expected_code!=2 && expected_code!=5) $fatal(1,"unknown probe mode");
    for(i=0;i<65536;i=i+1) program_bytes[i]=0;
    $readmemh({testcase,".verilog"},program_bytes);
    for(i=0;i<8192;i=i+1)
      `ITCM.mem_r[i]={program_bytes[8*i+7],program_bytes[8*i+6],program_bytes[8*i+5],
        program_bytes[8*i+4],program_bytes[8*i+3],program_bytes[8*i+2],program_bytes[8*i+1],program_bytes[8*i]};
    #120 rst_n=1;
  end
  always @(posedge clk) begin
    cycles=cycles+1;
    if(cycles>20000) $fatal(1,"single-instruction CPU watchdog");
    if(rst_n) begin
      if(cmd_valid || (expected_code!=5 && `NICE.nice_icb_cmd_valid))
        $fatal(1,"invalid descriptor caused forbidden memory traffic");
      if(`NICE.nice_icb_cmd_valid && `NICE.nice_icb_cmd_ready) begin
        if(expected_code!=5 || bus_commands || `NICE.nice_icb_cmd_addr!==32'h100420c4 ||
            !`NICE.nice_icb_cmd_read || `NICE.nice_icb_cmd_size!==2)
          $fatal(1,"unexpected real MMIO timeout probe command");
        bus_commands=bus_commands+1;
        $display("NICE_ERROR_BUS_COMMAND cycle=%0d",cycles);
      end
      if(`NICE.nice_icb_rsp_valid && `NICE.nice_icb_rsp_ready) begin
        if(bus_responses || bus_commands!=1 || `NICE.nice_icb_rsp_err ||
            `NICE.nice_icb_rsp_rdata!==0) $fatal(1,"bad real ROW_STATUS response");
        bus_responses=bus_responses+1;
        $display("NICE_ERROR_BUS_RESPONSE cycle=%0d oitf_ret=%b",cycles,`OITF.ret_ena);
      end
      if(`NICE.nice_req_valid && `NICE.nice_req_ready) begin
        if(requests || `NICE.nice_req_rs1!==(expected_code==2 ? 32'ha0020004 : 32'ha0020000) || `NICE.nice_req_rs2!==32'h20 ||
            `NICE.nice_req_inst[31:25]!==(expected_code==1 ? 7'h00 : 7'h20) || `NICE.nice_req_inst[14:12]!==7 ||
            `NICE.nice_req_inst[11:7]==0 || !`OITF.dis_ena || !`OITF.disp_i_rdwen)
          $fatal(1,"bad real NICE instruction allocation");
        requests=requests+1; request_cycle=cycles;
        tag=`OITF.dis_ptr; rd=`NICE.nice_req_inst[11:7];
        $display("NICE_ERROR_REQUEST rd=%0d tag=%0d cycle=%0d",rd,tag,cycles);
      end
      if(`NICE.nice_rsp_valid) begin
        if(`NICE.nice_rsp_err!==1 || `NICE.nice_rsp_rdat!==expected_code)
          $fatal(1,"expected stable error code");
        if(`NICE.nice_rsp_ready) begin
          if(responses || !`OITF.ret_ena || `OITF.ret_ptr!==tag ||
              !`OITF.ret_rdwen || `OITF.ret_rdidx!==rd || !`WB.wbck_sel_nice ||
              !`WB.longp_wbck_o_valid || !`WB.longp_wbck_o_ready ||
              `WB.longp_wbck_o_wdat!==expected_code || `WB.longp_wbck_o_rdidx!==rd)
            $fatal(1,"error code did not retire through real OITF/rd");
          responses=responses+1;
          $display("NICE_ERROR_RETIRED code=%0d rd=%0d cycle=%0d",expected_code,rd,cycles);
        end
      end
      if(requests && !responses && cycles-request_cycle>64) begin
        $display("NICE_COMPLETION_BLOCKED valid=%b ready=%b code=%h state=%0d owner=%b fifo_valid=%b fifo_tag=%0d oitf_empty=%b ret_ptr=%0d ret_rdwen=%b ret_rdidx=%0d wb_selected=%b wb_ready=%b",
          `NICE.nice_rsp_valid,`NICE.nice_rsp_ready,`NICE.nice_rsp_rdat,
          `NICE.u_drain8.state,`NICE.owner_valid,`FRONT.fifo_o_vld,`FRONT.nice_o_itag,
          `OITF.oitf_empty,`OITF.ret_ptr,`OITF.ret_rdwen,`OITF.ret_rdidx,
          `WB.wbck_sel_nice,`WB.nice_longp_wbck_i_ready);
        $fatal(1,"real CPU NICE completion exceeded 64-cycle bound with no memory work");
      end
      if(`EXU.u_e203_exu_commit.alu_cmt_i_valid && `EXU.u_e203_exu_commit.alu_cmt_i_ready &&
          `EXU.u_e203_exu_commit.alu_cmt_i_pc==32'h80000086) begin
        if(`EXU.u_e203_exu_regfile.rf_r[3]!==1 || requests!=1 || responses!=1 ||
            bus_commands!=(expected_code==5 ? 1 : 0) || bus_responses!=bus_commands)
          $fatal(1,"CPU did not check actual NICE error code");
        $display("NICE_ERROR_CPU_PASS requests=1 responses=1 code=%0d gp=1 commands=%0d cycles=%0d",expected_code,bus_commands,cycles);
        $finish;
      end
    end
  end
endmodule
