`timescale 1ns/1ps

// Local diagnostic only.  This testbench exercises the native 32-bit
// e203_soc_top external-memory pins with a single outstanding response.
// It does not preload a task, expose a public ingress, or claim official
// workload/score acceptance.
module tb_e203_soc32_functional;
  reg hfclk = 1'b0;
  reg lfclk = 1'b0;
  reg rst_n = 1'b0;
  always #3.333333 hfclk = ~hfclk;
  always #15258.789 lfclk = ~lfclk;

  wire ext_cmd_valid;
  reg  ext_cmd_ready = 1'b0;
  wire [31:0] ext_cmd_addr;
  wire ext_cmd_read;
  wire [31:0] ext_cmd_wdata;
  wire [3:0] ext_cmd_wmask;
  reg ext_rsp_valid = 1'b0;
  wire ext_rsp_ready;
  reg ext_rsp_err = 1'b0;
  reg [31:0] ext_rsp_rdata = 32'b0;
  wire shared_mem_clk, shared_mem_rst_n;

  reg [31:0] mem [0:524287];
  reg [7:0] program_bytes [0:65535];
  integer command_count = 0;
  integer read_count = 0;
  integer write_count = 0;
  integer i;
  wire cmd_fire = ext_cmd_valid && ext_cmd_ready;
  wire rsp_fire = ext_rsp_valid && ext_rsp_ready;
  wire [18:0] mem_index = ext_cmd_addr[20:2];

  // The external endpoint accepts one request and returns one ordered
  // response.  Writes still retire through the same response channel.
  always @(posedge shared_mem_clk or negedge shared_mem_rst_n) begin
    if (!shared_mem_rst_n) begin
      ext_cmd_ready <= 1'b0;
      ext_rsp_valid <= 1'b0;
      ext_rsp_err <= 1'b0;
      ext_rsp_rdata <= 32'b0;
    end else begin
      ext_cmd_ready <= !ext_rsp_valid || ext_rsp_ready;
      if (rsp_fire)
        ext_rsp_valid <= 1'b0;
      if (cmd_fire) begin
        command_count <= command_count + 1;
        if (ext_cmd_read) begin
          read_count <= read_count + 1;
          ext_rsp_rdata <= mem[mem_index];
        end else begin
          write_count <= write_count + 1;
          for (i = 0; i < 4; i = i + 1)
            if (ext_cmd_wmask[i])
              mem[mem_index][8*i +: 8] <= ext_cmd_wdata[8*i +: 8];
          ext_rsp_rdata <= 32'b0;
        end
        ext_rsp_err <= 1'b0;
        ext_rsp_valid <= 1'b1;
      end
    end
  end

  e203_soc_top #(.EXTERNAL_SYSMEM(1)) dut (
    .ext_sysmem_cmd_valid(ext_cmd_valid), .ext_sysmem_cmd_ready(ext_cmd_ready),
    .ext_sysmem_cmd_addr(ext_cmd_addr), .ext_sysmem_cmd_read(ext_cmd_read),
    .ext_sysmem_cmd_wdata(ext_cmd_wdata), .ext_sysmem_cmd_wmask(ext_cmd_wmask),
    .ext_sysmem_rsp_valid(ext_rsp_valid), .ext_sysmem_rsp_ready(ext_rsp_ready),
    .ext_sysmem_rsp_err(ext_rsp_err), .ext_sysmem_rsp_rdata(ext_rsp_rdata),
    .shared_mem_clk(shared_mem_clk), .shared_mem_rst_n(shared_mem_rst_n),
    .hfextclk(hfclk), .lfextclk(lfclk),
    .io_pads_jtag_TCK_i_ival(1'b0), .io_pads_jtag_TMS_i_ival(1'b0),
    .io_pads_jtag_TDI_i_ival(1'b0),
    .io_pads_gpioA_i_ival(32'b0), .io_pads_gpioB_i_ival(32'b0),
    .io_pads_qspi0_dq_0_i_ival(1'b0), .io_pads_qspi0_dq_1_i_ival(1'b0),
    .io_pads_qspi0_dq_2_i_ival(1'b0), .io_pads_qspi0_dq_3_i_ival(1'b0),
    .io_pads_aon_erst_n_i_ival(rst_n),
    .io_pads_dbgmode0_n_i_ival(1'b1), .io_pads_dbgmode1_n_i_ival(1'b1),
    .io_pads_dbgmode2_n_i_ival(1'b1), .io_pads_bootrom_n_i_ival(1'b0),
    .io_pads_aon_pmu_dwakeup_n_i_ival(1'b1)
  );

  always @(posedge shared_mem_clk) begin
    if (cmd_fire && command_count < 8)
      $display("SOC32_CMD n=%0d read=%0d addr=%h wdata=%h wmask=%h", command_count,
               ext_cmd_read, ext_cmd_addr, ext_cmd_wdata, ext_cmd_wmask);
  end

  initial begin
    integer p;
    for (i = 0; i < 524288; i = i + 1)
      mem[i] = 32'b0;
    for (p = 0; p < 65536; p = p + 1)
      program_bytes[p] = 8'b0;
    $readmemh("docs/validation/xu-b41-handoff-20261112/reports/s3-y32-portable-software-design-20261110/hardware64-r1/b41-strict-input-r1/firmware/dma_day_soc.verilog", program_bytes);
    for (p = 0; p < 8192; p = p + 1)
      dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top.u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram.mem_r[p] =
        {program_bytes[8*p+7], program_bytes[8*p+6], program_bytes[8*p+5], program_bytes[8*p+4],
         program_bytes[8*p+3], program_bytes[8*p+2], program_bytes[8*p+1], program_bytes[8*p]};
    // One local diagnostic task descriptor.  The firmware observes these
    // through the same 32-bit external-memory path as the DMA.
    mem[(32'h7f000 >> 2)] = 32'd1; // tasks
    mem[(32'h7f00c >> 2)] = 32'd1; // rows
    mem[(32'h7f010 >> 2)] = 32'd0; // warmup
    mem[(32'h7f018 >> 2)] = 32'd1; // call token
    #120;
    rst_n = 1'b1;
    wait (dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top.u_e203_cpu.rst_core === 1'b1);
    @(negedge hfclk);
    rst_n = 1'b0;
    #120;
    rst_n = 1'b1;
    #2000000;
    $display("LOCAL_32BIT_SOC_DEBUG shared_rst=%b cpu_rst=%b ext_valid=%b ext_ready=%b pc=%h", shared_mem_rst_n,
             dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top.u_e203_cpu.rst_core,
             ext_cmd_valid, ext_cmd_ready,
             dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top.u_e203_cpu.u_e203_core.cmt_dpc);
    if (^ext_cmd_wdata === 1'bx || ^ext_cmd_wmask === 1'bx)
      $fatal(1, "32-bit external write pins became unknown");
    if (command_count == 0)
      $display("LOCAL_32BIT_SOC_RESET_GATE_BLOCKED commands=0 shared_rst=%b", shared_mem_rst_n);
    else
      $display("LOCAL_32BIT_SOC_TRANSPORT_PASS commands=%0d reads=%0d writes=%0d", command_count, read_count, write_count);
    $finish;
  end
endmodule
