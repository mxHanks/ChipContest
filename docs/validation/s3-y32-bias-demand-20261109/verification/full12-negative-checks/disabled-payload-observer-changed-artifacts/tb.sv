`timescale 1ns/1fs
`include "e203_defines.v"
module tb_accel_soc;
  reg clk = 0, lfclk = 0, rst_n = 0;
  initial begin : s3_measure_hf_clock
    realtime first_edge, period_ns;
    @(posedge clk); first_edge=$realtime;
    @(posedge clk); period_ns=$realtime-first_edge;
    if (period_ns<=0) $fatal(1,"S3 clock profile has a nonpositive period");
    $display("S3_CLOCK_PROFILE domain=hf requested_half_ns=3.333333333 measured_half_ns=%.9f period_ns=%.9f frequency_hz=%.9f precision_fs=1",
      period_ns/2.0,period_ns,1.0e9/period_ns);
  end
  initial begin : s3_measure_lf_clock
    realtime first_edge, period_ns;
    @(posedge lfclk); first_edge=$realtime;
    @(posedge lfclk); period_ns=$realtime-first_edge;
    if (period_ns<=0) $fatal(1,"S3 clock profile has a nonpositive period");
    $display("S3_CLOCK_PROFILE domain=lf requested_half_ns=15258.7890625 measured_half_ns=%.9f period_ns=%.9f frequency_hz=%.9f precision_fs=1",
      period_ns/2.0,period_ns,1.0e9/period_ns);
  end

  reg s3_startup_complete=0;
  realtime s3_startup_assert_ns;
  always #3.333333333 clk = ~clk;
  always #15258.7890625 lfclk = ~lfclk;
  wire cmd_valid, cmd_read, cmd_ready, rsp_ready;
  wire [31:0] cmd_addr, cmd_wdata;
  wire [3:0] cmd_wmask;
  reg rsp_valid = 0;
  reg [31:0] rsp_rdata = 0;
  reg [31:0] ram [0:131071]; // Development shared SRAM: exactly 512 KiB.
  reg [15:0] x [0:6335], w [0:16383];
  reg [39:0] bias [0:255];
  reg [47:0] golden [0:25343];
  reg [31:0] golden_y32 [0:25343], w_packed16 [0:8191];
  reg [7:0] program_bytes [0:65535];
  string testcase, vectors;
  integer tasks, layer = 0, completed = 0, writes = 0;
  integer cycles = 0, first_cycle = -1, last_cycle = 0;
  integer first_accept_cycle = -1, first_source_stall = 0;
  integer max_cycles, firmware_cycles = 0;
  integer outstanding = 0;
  reg final_write_pending = 0;
  integer dumpwave;
  integer output_y32 = 0, shared_w_packed16 = 0, output_words = 50688, nice_drain8 = 0, nice_read_pop = 0, nice_direct = 0;
  integer nice_stream=0, stream_group=0, stream_groups_written=0, stream_group_cycle=0;
  integer nice_ready=0, ready_wait_cycles=0, ready_edges=0, ready_group_wait=0;
  integer ready_budget=0, ready_row_responses=0, ready_row_response_cycle=-1;
  reg ready_row_pending=0;
  wire nice_prepop = nice_read_pop || nice_direct;
  localparam BASE = 32'ha0000000, YOFF = 32'h20000, HOST = 32'h7f000;

  // Backpressure exercises CPU/bus waits; responses remain stable until accepted.
  wire source_request = cmd_valid && cmd_read && cmd_addr>=BASE && cmd_addr<BASE+'h18800;
  wire initial_source_block = source_request && first_accept_cycle<0 &&
      (first_cycle<0 ? first_source_stall>0 : cycles-first_cycle<first_source_stall);
  assign cmd_ready = (!rsp_valid || rsp_ready) && (cycles % 7 != 0) && !initial_source_block;
  `define CPU dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top
  `define EXU `CPU.u_e203_cpu.u_e203_core.u_e203_exu
  `define ITCM `CPU.u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram
  `define ACCEL dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.u_accel_icb_slave
  `define NICE `CPU.u_e203_cpu.u_e203_nice_core
  `define OITF `EXU.u_e203_exu_oitf
  `define LONGWB `EXU.u_e203_exu_longpwbck
  `define NICE_FRONT `EXU.u_e203_exu_alu.u_e203_exu_nice
  `define LSU `CPU.u_e203_cpu.u_e203_core.u_e203_lsu.u_e203_lsu_ctrl


  // Public PACK32 passive physical-clear proof. No force, DUT assignment, or task-data preloading.
  integer s3_clear_ticks=0, s3_clear_first=-1, s3_clear_last_response=-1;
  integer s3_clear_writes=0, s3_clear_commands=0, s3_clear_responses=0;
  integer s3_clear_w_count=0, s3_clear_x_count=0, s3_clear_legacy_count=0;
  integer s3_clear_bias_count=0, s3_clear_disable_count=0, s3_clear_reads=0;
  integer s3_clear_w_addr_count=0, s3_clear_x_addr_count=0;
  integer s3_clear_legacy_addr_count=0, s3_clear_bias_addr_count=0;
  integer s3_clear_sram_commands=0, s3_clear_sram_done=0, s3_clear_sram_start=-1;
  integer s3_clear_proof_reads=0, s3_preflight_commands=0, s3_preflight_responses=0;
  integer s3_clear_w_packs=0, s3_clear_x_packs=0, s3_clear_stream_proofs=0;
  reg s3_clear_stream_verified=0;

  reg [16383:0] s3_physical_w_seen=0;
  reg [767:0] s3_physical_bias_seen=0;
  integer s3_physical_w_count=0, s3_physical_bias_count=0;
  task s3_check_physical_w;
    input integer bank, half;
    input [9:0] address;
    input [15:0] data;
    integer flat;
    begin
      if ((^{address,data})===1'bx || data!==0)
        $fatal(1,"S3_CLEAR_REJECT nonzero/unknown physical W write");
      flat=bank*2048+half*1024+address;
      if (s3_physical_w_seen[flat])
        $fatal(1,"S3_CLEAR_REJECT duplicate physical W write");
      if (`ACCEL.u_linear_compute_core.io_wLoadWen!==1'b1 ||
          `ACCEL.u_linear_compute_core.io_wLoadBank!==bank ||
          `ACCEL.u_linear_compute_core.io_wLoadAddr!==half*1024+address ||
          `ACCEL.u_linear_compute_core.io_wLoadData!==data)
        $fatal(1,"S3_CLEAR_REJECT physical W/core mismatch");
      s3_physical_w_seen[flat]=1;
      s3_physical_w_count=s3_physical_w_count+1;
    end
  endtask

  task s3_observe_physical_clear;
    integer p, row, column, bank, address, macros_this_edge;
    begin
      macros_this_edge=0;
      if ((^{`ACCEL.u_linear_compute_core.io_wLoadWen,
             `ACCEL.u_linear_compute_core.io_xLoadWen})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown actual core strobe");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.io_ren!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT compute memory read during clear");
      if (`ACCEL.u_linear_compute_core.io_wLoadWen) begin
        if (!s3_clear_pending || s3_clear_pending_read ||
            s3_clear_response_address!=12'h05c || s3_clear_w_count>=16384 ||
            s3_clear_w_count>=2*s3_clear_w_packs)
          $fatal(1,"S3_CLEAR_REJECT unexpected actual W write");
        p=s3_clear_w_count; row=p/256; column=p%256;
        bank=column%8; address=(column/8)*64+row;
        if (`ACCEL.u_linear_compute_core.io_wLoadBank!==bank ||
            `ACCEL.u_linear_compute_core.io_wLoadAddr!==address ||
            `ACCEL.u_linear_compute_core.io_wLoadData!==0 ||
            s3_clear_w_seen[bank*2048+address])
          $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate/misordered actual W write");
        s3_clear_w_seen[bank*2048+address]=1;
        s3_clear_bank_seen[bank]=1;
        s3_clear_w_count=s3_clear_w_count+1;
      end
      if (`ACCEL.u_linear_compute_core.io_xLoadWen) begin
        address=`ACCEL.u_linear_compute_core.io_xLoadAddr;
        if (!s3_clear_pending || s3_clear_pending_read ||
            s3_clear_response_address!=12'h068 || s3_clear_x_count>=64 ||
            s3_clear_x_count>=2*s3_clear_x_packs ||
            address!=s3_clear_x_count || s3_clear_x_seen[address] ||
            `ACCEL.u_linear_compute_core.io_xLoadData!==0)
          $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate/misordered actual X write");
        s3_clear_x_seen[address]=1;
        s3_clear_x_count=s3_clear_x_count+1;
      end
      if (`ACCEL.u_linear_compute_core.core.xBuffer.io_wen !==
          `ACCEL.u_linear_compute_core.io_xLoadWen ||
          (`ACCEL.u_linear_compute_core.core.xBuffer.io_wen &&
           (`ACCEL.u_linear_compute_core.core.xBuffer.io_waddr !==
            `ACCEL.u_linear_compute_core.io_xLoadAddr ||
            `ACCEL.u_linear_compute_core.core.xBuffer.io_wdata!==0)))
        $fatal(1,"S3_CLEAR_REJECT physical X/core mismatch");

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(0,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(0,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(1,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(1,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(2,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(2,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(3,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(3,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(4,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(4,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(5,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(5,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(6,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(6,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(7,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(7,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if (macros_this_edge != (`ACCEL.u_linear_compute_core.io_wLoadWen ? 1 : 0))
        $fatal(1,"S3_CLEAR_REJECT physical W strobe cardinality");

      if ((^{`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical bias control");
      if (`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_en) begin
        address=`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_addr;
        if (`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_wmode!==1'b1 || `ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_wdata!==0 ||
            s3_clear_sram_commands!=1 || s3_clear_sram_done!=0 ||
            address>=768 || address!=s3_physical_bias_count || s3_physical_bias_seen[address])
          $fatal(1,"S3_CLEAR_REJECT invalid physical bias clear write");
        s3_physical_bias_seen[address]=1;
        s3_physical_bias_count=s3_physical_bias_count+1;
      end

    end
  endtask

  task s3_require_physical_clear_coverage;
    integer a;
    begin
      s3_require_physical_clear_idle();
      if (s3_physical_w_count!=16384 || s3_physical_w_seen!=={16384{1'b1}} ||
          s3_clear_w_seen!=={16384{1'b1}} || s3_clear_x_seen!=={64{1'b1}} ||
          `ACCEL.w_cursor!==16384 || `ACCEL.x_cursor!==64)
        $fatal(1,"S3_CLEAR_REJECT incomplete physical W/X coverage");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=0 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=0 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=1 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=1 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=2 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=2 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=3 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=3 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=4 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=4 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=5 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=5 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=6 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=6 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=7 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=7 half=1");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_0!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=0");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_1!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=1");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_2!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=2");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_3!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=3");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_4!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=4");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_5!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=5");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_6!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=6");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_7!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=7");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_8!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=8");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_9!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=9");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_10!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=10");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_11!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=11");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_12!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=12");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_13!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=13");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_14!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=14");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_15!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=15");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_16!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=16");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_17!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=17");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_18!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=18");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_19!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=19");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_20!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=20");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_21!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=21");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_22!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=22");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_23!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=23");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_24!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=24");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_25!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=25");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_26!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=26");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_27!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=27");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_28!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=28");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_29!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=29");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_30!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=30");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_31!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=31");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_32!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=32");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_33!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=33");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_34!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=34");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_35!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=35");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_36!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=36");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_37!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=37");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_38!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=38");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_39!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=39");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_40!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=40");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_41!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=41");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_42!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=42");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_43!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=43");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_44!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=44");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_45!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=45");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_46!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=46");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_47!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=47");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_48!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=48");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_49!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=49");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_50!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=50");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_51!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=51");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_52!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=52");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_53!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=53");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_54!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=54");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_55!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=55");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_56!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=56");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_57!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=57");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_58!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=58");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_59!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=59");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_60!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=60");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_61!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=61");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_62!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=62");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_63!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=63");

      if (`ACCEL.bias_regs[0]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=0");

      if (`ACCEL.bias_regs[1]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=1");

      if (`ACCEL.bias_regs[2]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=2");

      if (`ACCEL.bias_regs[3]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=3");

      if (`ACCEL.bias_regs[4]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=4");

      if (`ACCEL.bias_regs[5]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=5");

      if (`ACCEL.bias_regs[6]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=6");

      if (`ACCEL.bias_regs[7]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=7");

      if (!s3_clear_is_sram || s3_physical_bias_count!=768 ||
          s3_physical_bias_seen!=={768{1'b1}} ||
          `ACCEL.u_linear_compute_core.biasCache.slotValid_0!==1'b0 ||
          `ACCEL.u_linear_compute_core.biasCache.slotValid_1!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT incomplete physical bias coverage");
      for (a=0;a<768;a=a+1)
        if (`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical bias poststate");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_0!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=0");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_1!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=1");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_2!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=2");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_3!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=3");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_4!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=4");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_5!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=5");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_6!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=6");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_7!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=7");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_0!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=0");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_1!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=1");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_2!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=2");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_3!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=3");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_4!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=4");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_5!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=5");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_6!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=6");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_7!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=7");

    end
  endtask
  task s3_require_physical_clear_idle;
    begin
      if (`ACCEL.u_linear_compute_core.core.xBuffer.io_wen!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X write still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias port still active at proof");

    end
  endtask

  reg [16383:0] s3_clear_w_seen=0;
  reg [63:0] s3_clear_x_seen=0;
  reg [7:0] s3_clear_bank_seen=0;
  reg [4:0] s3_clear_bias_seen [0:255];
  reg [4:0] s3_clear_legacy_seen [0:7];
  reg [5:0] s3_clear_read_seen=0;
  reg s3_clear_complete=0, s3_clear_pending=0, s3_clear_pending_read=0;
  reg [11:0] s3_clear_response_address=0;
  reg s3_clear_cap_seen=0, s3_clear_is_sram=0;
  reg s3_clear_verified=0, s3_clear_pending_proof=0, s3_clear_pending_preflight=0;
  reg s3_clear_held_response=0, s3_clear_held_error=0;
  reg [31:0] s3_clear_held_data=0;
  integer s3_clear_init;
  initial begin
    for (s3_clear_init=0;s3_clear_init<256;s3_clear_init=s3_clear_init+1)
      s3_clear_bias_seen[s3_clear_init]=0;
    for (s3_clear_init=0;s3_clear_init<8;s3_clear_init=s3_clear_init+1)
      s3_clear_legacy_seen[s3_clear_init]=0;
  end

  task s3_require_clear_coverage;
    integer expected_writes;
    begin
      expected_writes=s3_clear_is_sram ? 8252 : 9019;
      if (!s3_clear_cap_seen || s3_clear_read_seen!==6'h3f ||
          s3_clear_writes!=expected_writes || s3_clear_disable_count!=1 ||
          s3_clear_w_count!=16384 || s3_clear_x_count!=64 || s3_clear_legacy_count!=8 ||
          s3_clear_bank_seen!==8'hff || s3_clear_w_addr_count!=1 ||
          s3_clear_x_addr_count!=1 || s3_clear_w_packs!=8192 || s3_clear_x_packs!=32 || s3_clear_legacy_addr_count!=8 ||
          (s3_clear_is_sram && (s3_clear_sram_commands!=1 ||
            s3_clear_sram_done!=1 || s3_clear_bias_count!=0 || s3_clear_bias_addr_count!=0)) ||
          (!s3_clear_is_sram && (s3_clear_bias_count!=256 ||
            s3_clear_bias_addr_count!=256 || s3_clear_sram_commands!=0 || s3_clear_sram_done!=0)))
        $fatal(1,"S3_CLEAR_REJECT incomplete clear before first source request");
      s3_require_physical_clear_coverage();
    end
  endtask

  task s3_observe_task_clear;
    input first_source_request;
    input nice_idle;
    output payload_phase;
    integer a, read_index;
    reg [4:0] old_mask, new_mask;
    begin
      s3_clear_ticks=s3_clear_ticks+1;
      if (!s3_clear_complete) begin
        if (first_source_request!==1'b0 && first_source_request!==1'b1)
          $fatal(1,"S3_CLEAR_REJECT unknown source-request predicate");
        if (nice_idle!==1'b1)
          $fatal(1,"S3_CLEAR_REJECT NICE not idle before task request");
        if (`ACCEL.cache_enable!==1'b0 || `ACCEL.busy!==1'b0 ||
            `ACCEL.core_start!==1'b0 || `ACCEL.row_count!==0)
          $fatal(1,"S3_CLEAR_REJECT non-idle/enabled clear phase");

        // Check BEFORE consuming anything on this edge. A simultaneous pending
        // write or response is not proof of clear before the first request.
        if (first_source_request) begin
          if (s3_clear_pending || s3_clear_commands!=s3_clear_responses ||
              s3_preflight_commands!=s3_preflight_responses ||
              `ACCEL.rsp_valid!==1'b0 || `ACCEL.cmd_valid!==1'b0 ||
              `ACCEL.cache_pending!==1'b0 || `ACCEL.stream_pending!==1'b0 ||
              `ACCEL.cache_idle!==1'b1 || `ACCEL.w_load_wen!==1'b0 ||
              `ACCEL.x_load_wen!==1'b0 ||
              `ACCEL.u_linear_compute_core.io_wLoadWen!==1'b0 ||
              `ACCEL.u_linear_compute_core.io_xLoadWen!==1'b0)
            $fatal(1,"S3_CLEAR_REJECT undrained clear before first source request");
          s3_require_clear_coverage();
          if (!s3_clear_verified || s3_clear_proof_reads!=1 || s3_clear_reads!=8 ||
              s3_clear_stream_proofs!=1 || !s3_clear_stream_verified)
            $fatal(1,"S3_CLEAR_REJECT missing clear completion proof before first source request");
          s3_clear_complete=1;
          $display("S3_TASK_CLEAR_OBSERVED mode_sram=%0d writes=%0d reads=%0d w=16384 x=64 legacy_bias=8 bias_entries=%0d physical_w=%0d physical_x=%0d physical_bias=%0d w_packs=%0d x_packs=%0d sram_clear_commands=%0d sram_done=%0d commands=%0d responses=%0d clear_cycles=%0d response_end_cycle=%0d gap_to_source_request=%0d preflight_commands=%0d preflight_responses=%0d nice_idle=1 fifo_payload_physical_zero=UNPROVEN policy=REVIEW_PENDING clear_transport=public-pack32",
            s3_clear_is_sram,s3_clear_writes,s3_clear_reads,s3_clear_bias_count,
            s3_physical_w_count,s3_clear_x_count,s3_physical_bias_count,
            s3_clear_w_packs,s3_clear_x_packs,s3_clear_sram_commands,s3_clear_sram_done,s3_clear_commands,s3_clear_responses,
            s3_clear_last_response-s3_clear_first+1,s3_clear_last_response,
            s3_clear_ticks-s3_clear_last_response,s3_preflight_commands,s3_preflight_responses);
        end else begin
          s3_observe_physical_clear();
          if (`ACCEL.cmd_valid && s3_clear_first<0) s3_clear_first=s3_clear_ticks;
          if (s3_clear_held_response && (`ACCEL.rsp_valid!==1'b1 ||
              `ACCEL.rsp_err!==s3_clear_held_error || `ACCEL.rsp_rdata!==s3_clear_held_data))
            $fatal(1,"S3_CLEAR_REJECT unstable held MMIO response");
          s3_clear_held_response=`ACCEL.rsp_valid && !`ACCEL.rsp_ready;
          s3_clear_held_error=`ACCEL.rsp_err;
          s3_clear_held_data=`ACCEL.rsp_rdata;

          if (`ACCEL.cache_clear_done) begin
            if (!s3_clear_is_sram || s3_clear_sram_commands!=1 || s3_clear_sram_done ||
                s3_clear_ticks-s3_clear_sram_start<768 || s3_physical_bias_count!=768)
              $fatal(1,"S3_CLEAR_REJECT invalid or premature physical bias clear done");
            s3_clear_sram_done=s3_clear_sram_done+1;
          end
          // Retire old response before accepting a replacement command.
          if (`ACCEL.rsp_valid && `ACCEL.rsp_ready) begin
            if (!s3_clear_pending || `ACCEL.rsp_err!==1'b0)
              $fatal(1,"S3_CLEAR_REJECT orphan/error clear response");
            if (!s3_clear_pending_read && s3_clear_response_address==12'h05c &&
                (s3_clear_w_count!=2*s3_clear_w_packs ||
                 s3_physical_w_count!=s3_clear_w_count || `ACCEL.stream_pending!==1'b0 ||
                 `ACCEL.u_linear_compute_core.io_wLoadWen!==1'b0))
              $fatal(1,"S3_CLEAR_REJECT W packed response preceded both physical writes");
            if (!s3_clear_pending_read && s3_clear_response_address==12'h068 &&
                (s3_clear_x_count!=2*s3_clear_x_packs || `ACCEL.stream_pending!==1'b0 ||
                 `ACCEL.u_linear_compute_core.io_xLoadWen!==1'b0))
              $fatal(1,"S3_CLEAR_REJECT X packed response preceded both physical writes");
            if (s3_clear_pending_preflight) begin
              if (!s3_clear_pending_read || (^`ACCEL.rsp_rdata)===1'bx)
                $fatal(1,"S3_CLEAR_REJECT unknown/non-read ABI preflight response");
              s3_preflight_responses=s3_preflight_responses+1;
            end else if (s3_clear_pending_read) begin
              case (s3_clear_response_address)
                12'h000: if (`ACCEL.rsp_rdata!==32'hacce2030)
                  $fatal(1,"S3_CLEAR_REJECT bad ID response");
                12'h050: if (`ACCEL.rsp_rdata!==32'h58550003)
                  $fatal(1,"S3_CLEAR_REJECT bad legacy capability response");
                12'h00c: begin
                  if (`ACCEL.rsp_rdata!==0)
                    $fatal(1,"S3_CLEAR_REJECT non-fresh status response");
                  if (s3_clear_pending_proof) begin
                    s3_clear_verified=1; s3_clear_proof_reads=s3_clear_proof_reads+1;
                  end
                end
                12'h070: if (`ACCEL.rsp_rdata!==32'h58530003)
                  $fatal(1,"S3_CLEAR_REJECT bad stream capability response");
                12'h074: if (`ACCEL.rsp_rdata!==32'h58500003)
                  $fatal(1,"S3_CLEAR_REJECT bad packed capability response");
                12'h06c: begin
                  if (`ACCEL.rsp_rdata!==0)
                    $fatal(1,"S3_CLEAR_REJECT nonzero stream completion status");
                  s3_clear_stream_verified=1;
                end
                12'h0ec: begin
                  if (`ACCEL.rsp_rdata!==0 && `ACCEL.rsp_rdata!==32'h42530001)
                    $fatal(1,"S3_CLEAR_REJECT unsupported bias capability response");
                  s3_clear_cap_seen=1;
                  s3_clear_is_sram=`ACCEL.rsp_rdata===32'h42530001;
                end
                default: $fatal(1,"S3_CLEAR_REJECT untracked clear read response");
              endcase
            end else if (s3_clear_response_address==12'h0e8 && s3_clear_sram_done!=1)
              $fatal(1,"S3_CLEAR_REJECT bias response without physical clear done");
            s3_clear_pending=0;
            if (!s3_clear_pending_preflight) begin
              s3_clear_responses=s3_clear_responses+1;
              s3_clear_last_response=s3_clear_ticks;
            end
          end
          if (`ACCEL.cmd_valid && `ACCEL.cmd_ready) begin
            if (s3_clear_pending) $fatal(1,"S3_CLEAR_REJECT multiple clear commands in flight");
            s3_clear_pending=1; s3_clear_pending_read=`ACCEL.cmd_read;
            s3_clear_response_address=`ACCEL.cmd_addr[11:0];
            s3_clear_pending_proof=0; s3_clear_pending_preflight=s3_clear_verified;
            if (s3_clear_verified) begin
              if (!`ACCEL.cmd_read)
                $fatal(1,"S3_CLEAR_REJECT parameter write before first source request");
              case (`ACCEL.cmd_addr[11:0])
                12'h000,12'h00c,12'h050,12'h070,12'h074,12'h078,12'h0e0,12'h0e4: begin end
                default: $fatal(1,"S3_CLEAR_REJECT unexpected ABI preflight read");
              endcase
              s3_preflight_commands=s3_preflight_commands+1;
            end else if (`ACCEL.cmd_read) begin
              s3_clear_commands=s3_clear_commands+1;
              case (`ACCEL.cmd_addr[11:0])
                12'h000: read_index=0;
                12'h050: read_index=1;
                12'h00c: read_index=2;
                12'h0ec: read_index=3;
                12'h070: read_index=4;
                12'h074: read_index=5;
                12'h06c: begin
                  if (s3_clear_reads!=6 || s3_clear_stream_proofs!=0)
                    $fatal(1,"S3_CLEAR_REJECT invalid stream completion proof order");
                  s3_require_clear_coverage();
                  if (`ACCEL.stream_pending!==1'b0 || `ACCEL.cache_pending!==1'b0 ||
                      `ACCEL.u_linear_compute_core.io_wLoadWen!==1'b0 ||
                      `ACCEL.u_linear_compute_core.io_xLoadWen!==1'b0)
                    $fatal(1,"S3_CLEAR_REJECT undrained clear before stream proof");
                  s3_clear_stream_proofs=s3_clear_stream_proofs+1;
                  read_index=6;
                end
                default: $fatal(1,"S3_CLEAR_REJECT unexpected pretask MMIO read");
              endcase
              if (read_index==6) begin end
              else if (s3_clear_read_seen[read_index]) begin
                if (read_index!=2 || s3_clear_reads!=7 || !s3_clear_stream_verified)
                  $fatal(1,"S3_CLEAR_REJECT repeated ABI read");
                s3_require_clear_coverage();
                if (`ACCEL.cache_pending!==1'b0 || `ACCEL.stream_pending!==1'b0 ||
                    `ACCEL.cache_idle!==1'b1 || `ACCEL.w_load_wen!==1'b0 ||
                    `ACCEL.x_load_wen!==1'b0 ||
                    `ACCEL.u_linear_compute_core.io_wLoadWen!==1'b0 ||
                    `ACCEL.u_linear_compute_core.io_xLoadWen!==1'b0)
                  $fatal(1,"S3_CLEAR_REJECT undrained clear before completion proof");
                s3_clear_pending_proof=1;
              end else s3_clear_read_seen[read_index]=1;
              s3_clear_reads=s3_clear_reads+1;
            end else begin
              s3_clear_commands=s3_clear_commands+1;
              if (!s3_clear_cap_seen || s3_clear_read_seen!==6'h3f ||
                  `ACCEL.cmd_wmask!==4'hf || (^`ACCEL.cmd_wdata)===1'bx)
                $fatal(1,"S3_CLEAR_REJECT missing ABI or incomplete/unknown clear word");
              s3_clear_writes=s3_clear_writes+1;
              case (`ACCEL.cmd_addr[11:0])
                12'h040: begin
                  if (`ACCEL.cmd_wdata!==0 || s3_clear_disable_count!=0)
                    $fatal(1,"S3_CLEAR_REJECT cache disable");
                  s3_clear_disable_count=s3_clear_disable_count+1;
                end
                12'h054: begin
                  if (`ACCEL.cmd_wdata!==0 || s3_clear_w_addr_count!=0 || s3_clear_w_packs!=0)
                    $fatal(1,"S3_CLEAR_REJECT W cursor initialization");
                  s3_clear_w_addr_count=s3_clear_w_addr_count+1;
                end
                12'h060: begin
                  if (`ACCEL.cmd_wdata!==0 || s3_clear_x_addr_count!=0 || s3_clear_x_packs!=0)
                    $fatal(1,"S3_CLEAR_REJECT X cursor initialization");
                  s3_clear_x_addr_count=s3_clear_x_addr_count+1;
                end
                12'h05c: begin
                  if (`ACCEL.cmd_wdata!==0 || s3_clear_w_addr_count!=1 ||
                      `ACCEL.w_cursor!==2*s3_clear_w_packs || s3_clear_w_packs>=8192)
                    $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate W packed command");
                  s3_clear_w_packs=s3_clear_w_packs+1;
                end
                12'h068: begin
                  if (`ACCEL.cmd_wdata!==0 || s3_clear_x_addr_count!=1 ||
                      `ACCEL.x_cursor!==2*s3_clear_x_packs || s3_clear_x_packs>=32)
                    $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate X packed command");
                  s3_clear_x_packs=s3_clear_x_packs+1;
                end
                12'h028: begin
                  if (`ACCEL.cmd_wdata>7) $fatal(1,"S3_CLEAR_REJECT legacy bias address");
                  s3_clear_legacy_addr_count=s3_clear_legacy_addr_count+1;
                end
                12'h044: begin
                  if (s3_clear_is_sram || `ACCEL.cmd_wdata>255)
                    $fatal(1,"S3_CLEAR_REJECT register bias address");
                  s3_clear_bias_addr_count=s3_clear_bias_addr_count+1;
                end
                12'h0e8: begin
                  if (!s3_clear_is_sram || `ACCEL.cmd_wdata!==1 || s3_clear_sram_commands)
                    $fatal(1,"S3_CLEAR_REJECT SRAM bias clear command");
                  s3_clear_sram_commands=1; s3_clear_sram_start=s3_clear_ticks;
                end
                12'h048,12'h04c,12'h02c,12'h030: begin
                  if (`ACCEL.cmd_wdata!==0) $fatal(1,"S3_CLEAR_REJECT nonzero bias clear");
                  if (`ACCEL.cmd_addr[11:0]==12'h048 || `ACCEL.cmd_addr[11:0]==12'h04c) begin
                    if (s3_clear_is_sram || (^`ACCEL.cache_addr_reg)===1'bx)
                      $fatal(1,"S3_CLEAR_REJECT invalid register bias clear");
                    a=`ACCEL.cache_addr_reg; old_mask=s3_clear_bias_seen[a];
                  end else begin
                    if ((^`ACCEL.bias_index_reg)===1'bx)
                      $fatal(1,"S3_CLEAR_REJECT unknown legacy bias destination");
                    a=`ACCEL.bias_index_reg; old_mask=s3_clear_legacy_seen[a];
                  end
                  if (`ACCEL.cmd_addr[11:0]==12'h048 || `ACCEL.cmd_addr[11:0]==12'h02c) begin
                    if (old_mask[3:0]!=0) $fatal(1,"S3_CLEAR_REJECT duplicate bias low clear");
                    new_mask=old_mask|5'b01111;
                  end else begin
                    if (old_mask[4]) $fatal(1,"S3_CLEAR_REJECT duplicate bias high clear");
                    new_mask=old_mask|5'b10000;
                  end
                  if (`ACCEL.cmd_addr[11:0]==12'h048 || `ACCEL.cmd_addr[11:0]==12'h04c) begin
                    s3_clear_bias_seen[a]=new_mask;
                    if (new_mask==5'b11111) s3_clear_bias_count=s3_clear_bias_count+1;
                  end else begin
                    s3_clear_legacy_seen[a]=new_mask;
                    if (new_mask==5'b11111) s3_clear_legacy_count=s3_clear_legacy_count+1;
                  end
                end
                default: $fatal(1,"S3_CLEAR_REJECT unexpected pretask MMIO write");
              endcase
            end
          end
        end
      end
      payload_phase=s3_clear_complete;
    end
  endtask

  reg s3_payload_phase=0, s3_clear_armed=0;
  integer nice_requests=0, nice_responses=0, nice_retired=0;
  integer nice_request_cycle=0;
  integer nice_polls=0, nice_reads=0, nice_pops=0, nice_writes=0, nice_step=0;
  integer nice_direct_snapshots=0, nice_direct_pops=0;
  reg direct_bundle_hold=0;
  reg [287:0] direct_saved_bundle;
  integer nice_bundle_cycle=-1;
  integer nice_alias_responses=0, nice_group_writes=0, nice_final_y_response_cycle=-1;
  reg [7:0] nice_lane_responses=0;
  reg nice_pop_retired=0;
  reg nice_instruction=0, nice_pending=0, nice_endpoint=0, nice_endpoint_done=0;
  reg [31:0] nice_destination=0, nice_address=0, nice_data=0, nice_endpoint_data=0;
  reg nice_read=0;
  reg [4:0] nice_rd=0, nice_group=0;
  reg [`E203_ITAG_WIDTH-1:0] nice_tag=0;
  reg nice_cmd_hold=0, nice_completion_hold=0;
  reg [66:0] nice_saved_command;
  reg [32:0] nice_saved_completion;
  wire [66:0] nice_command_payload={`NICE.nice_icb_cmd_addr,`NICE.nice_icb_cmd_read,
      `NICE.nice_icb_cmd_wdata,`NICE.nice_icb_cmd_size};
  wire [32:0] nice_completion_payload={`NICE.nice_rsp_err,`NICE.nice_rsp_rdat};

  // Observe the real core, LSU and both real endpoints. No internal signal is
  // driven. Completion is tracked beyond final Y retirement, outside timing.
  task observe_nice_legacy;
    reg endpoint_command, endpoint_response;
    reg [31:0] endpoint_address, endpoint_data;
    reg endpoint_read, endpoint_error;
    integer lane;
    begin
      if (nice_cmd_hold && (!`NICE.nice_icb_cmd_valid || nice_command_payload!==nice_saved_command))
        $fatal(1,"NICE command changed under backpressure");
      if (nice_completion_hold && (!`NICE.nice_rsp_valid || nice_completion_payload!==nice_saved_completion))
        $fatal(1,"NICE completion changed under backpressure");
      nice_cmd_hold=`NICE.nice_icb_cmd_valid && !`NICE.nice_icb_cmd_ready;
      nice_completion_hold=`NICE.nice_rsp_valid && !`NICE.nice_rsp_ready;
      nice_saved_command=nice_command_payload; nice_saved_completion=nice_completion_payload;

      if (`NICE.nice_rsp_valid &&
          (!nice_instruction || nice_pending || nice_step!=(nice_prepop ? 17 : 18) ||
           nice_lane_responses!==8'hff || !nice_pop_retired || nice_group_writes!=8 ||
           nice_final_y_response_cycle<0 || cycles<=nice_final_y_response_cycle))
        $fatal(1,"NICE completion offered before final Y response retired");

      if (nice_instruction && `OITF.ret_ena && `OITF.ret_ptr===nice_tag &&
          !(`NICE.nice_rsp_valid && `NICE.nice_rsp_ready))
        $fatal(1,"NICE OITF entry retired before its completion");
      if (nice_instruction && cycles-nice_request_cycle>1024) begin
        $display("NICE_COMPLETION_BLOCKED valid=%b ready=%b code=%h active=%b mem_holdup=%b fifo_valid=%b fifo_tag=%0d oitf_empty=%b ret_ptr=%0d expected_tag=%0d ret_rdidx=%0d expected_rd=%0d wb_selected=%b step=%0d",
          `NICE.nice_rsp_valid,`NICE.nice_rsp_ready,`NICE.nice_rsp_rdat,
          `NICE.nice_active,`NICE.nice_mem_holdup,`NICE_FRONT.fifo_o_vld,`NICE_FRONT.nice_o_itag,
          `OITF.oitf_empty,`OITF.ret_ptr,nice_tag,`OITF.ret_rdidx,nice_rd,
          `LONGWB.wbck_sel_nice,nice_step);
        $fatal(1,"NICE exceeded bounded development interconnect/producer latency");
      end

      if (`NICE.nice_req_valid && `NICE.nice_req_ready) begin
        if (nice_instruction || nice_pending || nice_requests>=3168 ||
            `NICE.nice_req_inst[6:0]!==7'h7b || `NICE.nice_req_inst[14:12]!==7 ||
            `NICE.nice_req_inst[31:25]!==7'h20 || `NICE.nice_req_inst[11:7]==0 ||
            `NICE.nice_req_rs1!==BASE+YOFF+nice_requests*32 ||
            `NICE.nice_req_rs2[4:0]!==nice_requests%32 || `NICE.nice_req_rs2[31:5]==0 ||
            !`OITF.dis_ena || !`OITF.disp_i_rdwen ||
            `OITF.disp_i_rdidx!==`NICE.nice_req_inst[11:7])
          $fatal(1,"NICE instruction descriptor or OITF allocation mismatch index=%0d",nice_requests);
        nice_instruction=1; nice_step=0; nice_request_cycle=cycles; nice_destination=`NICE.nice_req_rs1;
        nice_lane_responses=0; nice_pop_retired=0; nice_group_writes=0;
        nice_final_y_response_cycle=-1;
        nice_group=`NICE.nice_req_rs2[4:0]; nice_rd=`NICE.nice_req_inst[11:7];
        nice_tag=`OITF.dis_ptr; nice_requests=nice_requests+1;
      end
      if (nice_direct) begin
        if (direct_bundle_hold && (!`NICE.xu_direct_valid ||
            {`NICE.xu_direct_status,`NICE.xu_direct_payload}!==direct_saved_bundle))
          $fatal(1,"direct bundle changed under backpressure");
        direct_bundle_hold=`NICE.xu_direct_valid && !`NICE.xu_direct_ready;
        direct_saved_bundle={`NICE.xu_direct_status,`NICE.xu_direct_payload};
        if (`NICE.xu_direct_valid && `NICE.xu_direct_ready) begin
          if (!nice_instruction || nice_step!=1 || nice_pending ||
              !`ACCEL.row_valid || !`ACCEL.row_active || `ACCEL.row_pop ||
              `ACCEL.row_group!==nice_group ||
              `NICE.xu_direct_payload!==`ACCEL.xu_direct_payload ||
              `NICE.xu_direct_status!==`ACCEL.xu_direct_status ||
              `NICE.xu_direct_status[10:6]!==nice_group ||
              `NICE.xu_direct_status[1:0]!==2'b11)
            $fatal(1,"direct bundle producer/consumer ownership mismatch");
          for (lane=0;lane<8;lane=lane+1)
            if (`NICE.xu_direct_payload[32*lane +: 32]!==golden_y32[(nice_requests-1)*8+lane])
              $fatal(1,"direct bundle value differs from golden lane=%0d",lane);
          nice_lane_responses=8'hff;
          nice_direct_snapshots=nice_direct_snapshots+1;
          nice_bundle_cycle=cycles;
          nice_step=9;
        end
        if (`NICE.xu_direct_commit && `NICE.xu_direct_commit_ready) begin
          if (!nice_instruction || nice_step!=9 || nice_pending ||
              nice_lane_responses!==8'hff || nice_pop_retired ||
              cycles<=nice_bundle_cycle || !`ACCEL.direct_row_pop ||
              `NICE.xu_direct_commit_err)
            $fatal(1,"direct POP before eight NICE registers captured");
          for (lane=0;lane<8;lane=lane+1)
            if (`NICE.u_drain8.snapshot[lane]!==golden_y32[(nice_requests-1)*8+lane])
              $fatal(1,"direct NICE snapshot changed before POP lane=%0d",lane);
          nice_pop_retired=1; nice_pops=nice_pops+1;
          nice_direct_pops=nice_direct_pops+1;
        end
      end
      if (`NICE.nice_icb_cmd_valid && `NICE.nice_icb_cmd_ready) begin
        if (!nice_instruction || nice_pending || `NICE.nice_icb_cmd_size!==2'b10 ||
            !`LSU.arbt_icb_cmd_valid || !`LSU.arbt_icb_cmd_ready ||
            `LSU.arbt_icb_cmd_addr!==`NICE.nice_icb_cmd_addr ||
            `LSU.arbt_icb_cmd_read!==`NICE.nice_icb_cmd_read)
          $fatal(1,"NICE command did not pass through real LSU");
        nice_address=`NICE.nice_icb_cmd_addr; nice_read=`NICE.nice_icb_cmd_read;
        nice_data=`NICE.nice_icb_cmd_wdata;
        if (nice_step==0) begin
          if (!nice_read || nice_address!==32'h100420c4) $fatal(1,"NICE status poll order");
        end else if (nice_step<=8) begin
          if (!nice_read || nice_address!==(nice_read_pop && nice_step==8 ?
              32'h100421a0 : 32'h10042180+4*(nice_step-1)))
            $fatal(1,"NICE lane snapshot order/profile mismatch");
          if (nice_read_pop && nice_step==8 &&
              (nice_lane_responses!==8'h7f || nice_group_writes!=0 || nice_pop_retired))
            $fatal(1,"NICE alias preceded seven lane responses or followed a Y write");
        end else if (!nice_prepop && nice_step==16) begin
          if (nice_read || nice_address!==32'h100420c8 || nice_data!==1 ||
              nice_lane_responses!==8'hff || nice_group_writes!=7 || nice_pop_retired)
            $fatal(1,"NICE legacy POP order");
        end else if (nice_step<=(nice_prepop ? 16 : 17)) begin
          lane=nice_prepop ? nice_step-9 : (nice_step==17 ? 7 : nice_step-9);
          if (nice_read || nice_address!==nice_destination+4*lane ||
              nice_lane_responses!==8'hff || nice_group_writes!=lane ||
              ((nice_prepop || lane==7) ? !nice_pop_retired : nice_pop_retired) ||
              nice_data!==golden_y32[(nice_requests-1)*8+lane]) $fatal(1,"NICE shared write order/value");
        end else $fatal(1,"NICE extra bus command after last write");
        nice_pending=1; nice_endpoint=0; nice_endpoint_done=0;
      end

      if (nice_pending) begin
        endpoint_command=0; endpoint_response=0; endpoint_address=0; endpoint_data=0;
        endpoint_read=0; endpoint_error=0;
        if (nice_address[31:12]==20'h10042) begin
          endpoint_command=`ACCEL.cmd_valid && `ACCEL.cmd_ready;
          endpoint_response=`ACCEL.rsp_valid && `ACCEL.rsp_ready;
          endpoint_address=`ACCEL.cmd_addr; endpoint_read=`ACCEL.cmd_read;
          endpoint_data=`ACCEL.cmd_wdata;
          if (endpoint_command && !endpoint_read && `ACCEL.cmd_wmask!==4'hf) $fatal(1,"NICE MMIO mask");
        end else begin
          endpoint_command=cmd_valid && cmd_ready;
          endpoint_response=rsp_valid && rsp_ready;
          endpoint_address=cmd_addr; endpoint_read=cmd_read; endpoint_data=cmd_wdata;
          if (endpoint_command && cmd_wmask!==4'hf) $fatal(1,"NICE RAM mask");
        end
        if (endpoint_command) begin
          if (nice_endpoint || endpoint_address!==nice_address || endpoint_read!==nice_read ||
              (!nice_read && endpoint_data!==nice_data)) $fatal(1,"NICE endpoint differs from source");
          nice_endpoint=1;
        end
        if (endpoint_response) begin
          if (!nice_endpoint || nice_endpoint_done) $fatal(1,"NICE orphan endpoint response");
          nice_endpoint_done=1;
          if (nice_address[31:12]==20'h10042) begin
            nice_endpoint_data=`ACCEL.rsp_rdata; endpoint_error=`ACCEL.rsp_err;
          end else nice_endpoint_data=rsp_rdata;
          if (endpoint_error) $fatal(1,"NICE endpoint error in successful task");
        end
      end
      if (`NICE.nice_icb_rsp_valid && `NICE.nice_icb_rsp_ready) begin
        if (!nice_pending || !nice_endpoint_done || `NICE.nice_icb_rsp_err ||
            (nice_read && `NICE.nice_icb_rsp_rdata!==nice_endpoint_data))
          $fatal(1,"NICE response differs from real endpoint");
        if (nice_step==0) begin
          nice_polls=nice_polls+1;
          if (`NICE.nice_icb_rsp_rdata[1]) begin
            if (!`NICE.nice_icb_rsp_rdata[0] || `NICE.nice_icb_rsp_rdata[10:6]!==nice_group)
              $fatal(1,"NICE polled FIFO head differs from expected group");
            nice_step=1;
          end
        end else begin
          if (nice_step<=8) begin
            nice_reads=nice_reads+1;
            nice_lane_responses[nice_step-1]=1;
            if (nice_read_pop && nice_step==8) begin
              nice_alias_responses=nice_alias_responses+1;
              nice_pops=nice_pops+1;
              nice_pop_retired=1;
            end
          end else if (!nice_prepop && nice_step==16) begin
            nice_pops=nice_pops+1;
            nice_pop_retired=1;
          end else begin
            nice_writes=nice_writes+1;
            nice_group_writes=nice_group_writes+1;
            if (nice_step==(nice_prepop ? 16 : 17)) nice_final_y_response_cycle=cycles;
          end
          nice_step=nice_step+1;
        end
        nice_pending=0;
      end
      if (`NICE.nice_rsp_valid && `NICE.nice_rsp_ready) begin
        if (!nice_instruction || nice_pending || nice_step!=(nice_prepop ? 17 : 18) || nice_completion_payload!==0 ||
            !`LONGWB.wbck_sel_nice || !`OITF.ret_ena || `OITF.ret_ptr!==nice_tag ||
            !`OITF.ret_rdwen || `OITF.ret_rdidx!==nice_rd ||
            !`LONGWB.longp_wbck_o_valid || !`LONGWB.longp_wbck_o_ready ||
            `LONGWB.longp_wbck_o_wdat!==0 || `LONGWB.longp_wbck_o_rdidx!==nice_rd)
          $fatal(1,"NICE completion/code/OITF/rd writeback mismatch index=%0d",nice_responses);
        nice_responses=nice_responses+1; nice_retired=nice_retired+1; nice_instruction=0;
      end
    end
  endtask

  task observe_nice_stream;
    reg endpoint_command, endpoint_response;
    reg [31:0] endpoint_address, endpoint_data;
    reg endpoint_read, endpoint_error;
    integer lane;
    begin
      if (nice_cmd_hold && (!`NICE.nice_icb_cmd_valid || nice_command_payload!==nice_saved_command))
        $fatal(1,"NICE command changed under backpressure");
      if (nice_completion_hold && (!`NICE.nice_rsp_valid || nice_completion_payload!==nice_saved_completion))
        $fatal(1,"NICE completion changed under backpressure");
      nice_cmd_hold=`NICE.nice_icb_cmd_valid && !`NICE.nice_icb_cmd_ready;
      nice_completion_hold=`NICE.nice_rsp_valid && !`NICE.nice_rsp_ready;
      nice_saved_command=nice_command_payload; nice_saved_completion=nice_completion_payload;

      if (`NICE.nice_rsp_valid &&
          (!nice_instruction || nice_pending || stream_group!=31 || nice_step!=(nice_prepop ? 17 : 18) ||
           nice_lane_responses!==8'hff || !nice_pop_retired || nice_group_writes!=8 ||
           nice_final_y_response_cycle<0 || cycles<=nice_final_y_response_cycle))
        $fatal(1,"NICE completion offered before final Y response retired");

      if (nice_instruction && `OITF.ret_ena && `OITF.ret_ptr===nice_tag &&
          !(`NICE.nice_rsp_valid && `NICE.nice_rsp_ready))
        $fatal(1,"NICE OITF entry retired before its completion");
      if (nice_instruction && (cycles-nice_request_cycle>32*1024 || cycles-stream_group_cycle>1024)) begin
        $display("NICE_COMPLETION_BLOCKED valid=%b ready=%b code=%h active=%b mem_holdup=%b fifo_valid=%b fifo_tag=%0d oitf_empty=%b ret_ptr=%0d expected_tag=%0d ret_rdidx=%0d expected_rd=%0d wb_selected=%b step=%0d",
          `NICE.nice_rsp_valid,`NICE.nice_rsp_ready,`NICE.nice_rsp_rdat,
          `NICE.nice_active,`NICE.nice_mem_holdup,`NICE_FRONT.fifo_o_vld,`NICE_FRONT.nice_o_itag,
          `OITF.oitf_empty,`OITF.ret_ptr,nice_tag,`OITF.ret_rdidx,nice_rd,
          `LONGWB.wbck_sel_nice,nice_step);
        $fatal(1,"NICE exceeded bounded development interconnect/producer latency");
      end

      if (`NICE.nice_req_valid && `NICE.nice_req_ready) begin
        if (nice_instruction || nice_pending || nice_requests>=99 ||
            `NICE.nice_req_inst[6:0]!==7'h7b || `NICE.nice_req_inst[14:12]!==7 ||
            `NICE.nice_req_inst[31:25]!==(nice_ready ? 7'h24 : 7'h23) || `NICE.nice_req_inst[11:7]==0 ||
            `NICE.nice_req_rs1!==BASE+YOFF+nice_requests*1024 ||
            `NICE.nice_req_rs2[4:0]!==0 || `NICE.nice_req_rs2[9:5]!==31 ||
            `NICE.nice_req_rs2[31:10]==0 ||
            !`OITF.dis_ena || !`OITF.disp_i_rdwen ||
            `OITF.disp_i_rdidx!==`NICE.nice_req_inst[11:7])
          $fatal(1,"NICE instruction descriptor or OITF allocation mismatch index=%0d",nice_requests);
        if (nice_ready && (ready_row_pending || ready_row_responses!=nice_requests+1 ||
            ready_row_response_cycle<0 || cycles<=ready_row_response_cycle))
          $fatal(1,"ready instruction preceded STARTROW response retirement pending=%0d rows=%0d requests=%0d response_cycle=%0d request_cycle=%0d",
            ready_row_pending,ready_row_responses,nice_requests,ready_row_response_cycle,cycles);
        ready_budget=`NICE.nice_req_rs2[31:10]; ready_group_wait=0;
        nice_instruction=1; nice_step=0; stream_group=0; stream_group_cycle=cycles; nice_request_cycle=cycles; nice_destination=`NICE.nice_req_rs1;
        nice_lane_responses=0; nice_pop_retired=0; nice_group_writes=0;
        nice_final_y_response_cycle=-1;
        nice_group=`NICE.nice_req_rs2[4:0]; nice_rd=`NICE.nice_req_inst[11:7];
        nice_tag=`OITF.dis_ptr; nice_requests=nice_requests+1;
      end
      if (nice_ready && `NICE.u_drain8.state==4'd9) begin
        // Observe real READY_WAIT edges independently of marker expectations.
        // Live metadata exists only with claim low and must equal ROW_STATUS.
        if (!nice_instruction || nice_step!=0 || nice_pending ||
            `NICE.xu_direct_claim || `NICE.xu_direct_ready || `NICE.xu_direct_commit ||
            `NICE.nice_icb_cmd_valid || !`NICE.xu_direct_capable ||
            `NICE.xu_direct_status!=={1'b1,1'b0,`ACCEL.row_retired,2'b0,`ACCEL.row_produced,
              5'b0,`ACCEL.row_group,`ACCEL.row_count,`ACCEL.row_running,
              (`ACCEL.row_produced==32),`ACCEL.row_valid,`ACCEL.row_active} ||
            `NICE.u_drain8.polls_left!==ready_budget-ready_group_wait)
          $fatal(1,"ready live-status ownership/metadata/budget mismatch");
        ready_wait_cycles=ready_wait_cycles+1; ready_group_wait=ready_group_wait+1;
        if (ready_group_wait>ready_budget) $fatal(1,"ready exceeded per-group edge budget");
        if (`NICE.xu_direct_status[1]) begin
          if (!`NICE.xu_direct_status[0] || `NICE.xu_direct_status[10:6]!==nice_group)
            $fatal(1,"ready live FIFO head differs from expected group");
          ready_edges=ready_edges+1; nice_step=1;
        end
      end
      if (nice_direct) begin
        if (direct_bundle_hold && (!`NICE.xu_direct_valid ||
            {`NICE.xu_direct_status,`NICE.xu_direct_payload}!==direct_saved_bundle))
          $fatal(1,"direct bundle changed under backpressure");
        direct_bundle_hold=`NICE.xu_direct_valid && !`NICE.xu_direct_ready;
        direct_saved_bundle={`NICE.xu_direct_status,`NICE.xu_direct_payload};
        if (`NICE.xu_direct_valid && `NICE.xu_direct_ready) begin
          if (!nice_instruction || nice_step!=1 || nice_pending ||
              !`ACCEL.row_valid || !`ACCEL.row_active || `ACCEL.row_pop ||
              `ACCEL.row_group!==nice_group ||
              `NICE.xu_direct_payload!==`ACCEL.xu_direct_payload ||
              `NICE.xu_direct_status!==`ACCEL.xu_direct_status ||
              `NICE.xu_direct_status[10:6]!==nice_group ||
              `NICE.xu_direct_status[1:0]!==2'b11)
            $fatal(1,"direct bundle producer/consumer ownership mismatch");
          for (lane=0;lane<8;lane=lane+1)
            if (`NICE.xu_direct_payload[32*lane +: 32]!==golden_y32[(nice_requests-1)*256+stream_group*8+lane])
              $fatal(1,"direct bundle value differs from golden lane=%0d",lane);
          nice_lane_responses=8'hff;
          nice_direct_snapshots=nice_direct_snapshots+1;
          nice_bundle_cycle=cycles;
          nice_step=9;
        end
        if (`NICE.xu_direct_commit && `NICE.xu_direct_commit_ready) begin
          if (!nice_instruction || nice_step!=9 || nice_pending ||
              nice_lane_responses!==8'hff || nice_pop_retired ||
              cycles<=nice_bundle_cycle || !`ACCEL.direct_row_pop ||
              `NICE.xu_direct_commit_err)
            $fatal(1,"direct POP before eight NICE registers captured");
          for (lane=0;lane<8;lane=lane+1)
            if (`NICE.u_drain8.snapshot[lane]!==golden_y32[(nice_requests-1)*256+stream_group*8+lane])
              $fatal(1,"direct NICE snapshot changed before POP lane=%0d",lane);
          nice_pop_retired=1; nice_pops=nice_pops+1;
          nice_direct_pops=nice_direct_pops+1;
        end
      end
      if (`NICE.nice_icb_cmd_valid && `NICE.nice_icb_cmd_ready) begin
        if (!nice_instruction || nice_pending || `NICE.nice_icb_cmd_size!==2'b10 ||
            !`LSU.arbt_icb_cmd_valid || !`LSU.arbt_icb_cmd_ready ||
            `LSU.arbt_icb_cmd_addr!==`NICE.nice_icb_cmd_addr ||
            `LSU.arbt_icb_cmd_read!==`NICE.nice_icb_cmd_read)
          $fatal(1,"NICE command did not pass through real LSU");
        nice_address=`NICE.nice_icb_cmd_addr; nice_read=`NICE.nice_icb_cmd_read;
        nice_data=`NICE.nice_icb_cmd_wdata;
        if (nice_ready && nice_read) $fatal(1,"ready instruction issued an LSU read");
        if (nice_step==0) begin
          if (!nice_read || nice_address!==32'h100420c4) $fatal(1,"NICE status poll order");
        end else if (nice_step<=8) begin
          if (!nice_read || nice_address!==(nice_read_pop && nice_step==8 ?
              32'h100421a0 : 32'h10042180+4*(nice_step-1)))
            $fatal(1,"NICE lane snapshot order/profile mismatch");
          if (nice_read_pop && nice_step==8 &&
              (nice_lane_responses!==8'h7f || nice_group_writes!=0 || nice_pop_retired))
            $fatal(1,"NICE alias preceded seven lane responses or followed a Y write");
        end else if (!nice_prepop && nice_step==16) begin
          if (nice_read || nice_address!==32'h100420c8 || nice_data!==1 ||
              nice_lane_responses!==8'hff || nice_group_writes!=7 || nice_pop_retired)
            $fatal(1,"NICE legacy POP order");
        end else if (nice_step<=(nice_prepop ? 16 : 17)) begin
          lane=nice_prepop ? nice_step-9 : (nice_step==17 ? 7 : nice_step-9);
          if (nice_read || nice_address!==nice_destination+4*lane ||
              nice_lane_responses!==8'hff || nice_group_writes!=lane ||
              ((nice_prepop || lane==7) ? !nice_pop_retired : nice_pop_retired) ||
              nice_data!==golden_y32[(nice_requests-1)*256+stream_group*8+lane]) $fatal(1,"NICE shared write order/value");
        end else $fatal(1,"NICE extra bus command after last write");
        nice_pending=1; nice_endpoint=0; nice_endpoint_done=0;
      end

      if (nice_pending) begin
        endpoint_command=0; endpoint_response=0; endpoint_address=0; endpoint_data=0;
        endpoint_read=0; endpoint_error=0;
        if (nice_address[31:12]==20'h10042) begin
          endpoint_command=`ACCEL.cmd_valid && `ACCEL.cmd_ready;
          endpoint_response=`ACCEL.rsp_valid && `ACCEL.rsp_ready;
          endpoint_address=`ACCEL.cmd_addr; endpoint_read=`ACCEL.cmd_read;
          endpoint_data=`ACCEL.cmd_wdata;
          if (endpoint_command && !endpoint_read && `ACCEL.cmd_wmask!==4'hf) $fatal(1,"NICE MMIO mask");
        end else begin
          endpoint_command=cmd_valid && cmd_ready;
          endpoint_response=rsp_valid && rsp_ready;
          endpoint_address=cmd_addr; endpoint_read=cmd_read; endpoint_data=cmd_wdata;
          if (endpoint_command && cmd_wmask!==4'hf) $fatal(1,"NICE RAM mask");
        end
        if (endpoint_command) begin
          if (nice_endpoint || endpoint_address!==nice_address || endpoint_read!==nice_read ||
              (!nice_read && endpoint_data!==nice_data)) $fatal(1,"NICE endpoint differs from source");
          nice_endpoint=1;
        end
        if (endpoint_response) begin
          if (!nice_endpoint || nice_endpoint_done) $fatal(1,"NICE orphan endpoint response");
          nice_endpoint_done=1;
          if (nice_address[31:12]==20'h10042) begin
            nice_endpoint_data=`ACCEL.rsp_rdata; endpoint_error=`ACCEL.rsp_err;
          end else nice_endpoint_data=rsp_rdata;
          if (endpoint_error) $fatal(1,"NICE endpoint error in successful task");
        end
      end
      if (`NICE.nice_icb_rsp_valid && `NICE.nice_icb_rsp_ready) begin
        if (!nice_pending || !nice_endpoint_done || `NICE.nice_icb_rsp_err ||
            (nice_read && `NICE.nice_icb_rsp_rdata!==nice_endpoint_data))
          $fatal(1,"NICE response differs from real endpoint");
        if (nice_step==0) begin
          nice_polls=nice_polls+1;
          if (`NICE.nice_icb_rsp_rdata[1]) begin
            if (!`NICE.nice_icb_rsp_rdata[0] || `NICE.nice_icb_rsp_rdata[10:6]!==nice_group)
              $fatal(1,"NICE polled FIFO head differs from expected group");
            nice_step=1;
          end
        end else begin
          if (nice_step<=8) begin
            nice_reads=nice_reads+1;
            nice_lane_responses[nice_step-1]=1;
            if (nice_read_pop && nice_step==8) begin
              nice_alias_responses=nice_alias_responses+1;
              nice_pops=nice_pops+1;
              nice_pop_retired=1;
            end
          end else if (!nice_prepop && nice_step==16) begin
            nice_pops=nice_pops+1;
            nice_pop_retired=1;
          end else begin
            nice_writes=nice_writes+1;
            nice_group_writes=nice_group_writes+1;
            if (nice_step==(nice_prepop ? 16 : 17)) nice_final_y_response_cycle=cycles;
          end
          nice_step=nice_step+1;
          if (nice_step==17) begin
            stream_groups_written=stream_groups_written+1;
            if (stream_group<31) begin
              stream_group=stream_group+1; nice_group=nice_group+1;
              nice_destination=nice_destination+32; stream_group_cycle=cycles;
              nice_step=0; ready_group_wait=0; nice_lane_responses=0; nice_pop_retired=0;
              nice_group_writes=0; nice_final_y_response_cycle=-1;
            end
          end
        end
        nice_pending=0;
      end
      if (`NICE.nice_rsp_valid && `NICE.nice_rsp_ready) begin
        if (!nice_instruction || nice_pending || stream_group!=31 || nice_step!=(nice_prepop ? 17 : 18) || nice_completion_payload!==0 ||
            !`LONGWB.wbck_sel_nice || !`OITF.ret_ena || `OITF.ret_ptr!==nice_tag ||
            !`OITF.ret_rdwen || `OITF.ret_rdidx!==nice_rd ||
            !`LONGWB.longp_wbck_o_valid || !`LONGWB.longp_wbck_o_ready ||
            `LONGWB.longp_wbck_o_wdat!==0 || `LONGWB.longp_wbck_o_rdidx!==nice_rd)
          $fatal(1,"NICE completion/code/OITF/rd writeback mismatch index=%0d",nice_responses);
        nice_responses=nice_responses+1; nice_retired=nice_retired+1; nice_instruction=0;
      end
    end
  endtask

  task observe_nice;
    begin
      if (nice_ready) begin
        // Response metadata retires before accepting a new endpoint command.
        if (ready_row_pending && `ACCEL.rsp_valid && `ACCEL.rsp_ready) begin
          if (`ACCEL.rsp_err) $fatal(1,"STARTROW failed before ready instruction");
          ready_row_pending=0; ready_row_responses=ready_row_responses+1;
          ready_row_response_cycle=cycles;
        end
        if (`ACCEL.cmd_valid && `ACCEL.cmd_ready) begin
          if (`ACCEL.cmd_read && `ACCEL.cmd_addr[11:0]==12'h0c4)
            $fatal(1,"ready profile issued a ROW_STATUS query");
          if (!`ACCEL.cmd_read && `ACCEL.cmd_addr[11:0]==12'h0c0 && `ACCEL.cmd_wdata[0]) begin
            if (ready_row_pending) $fatal(1,"overlapping STARTROW commands");
            ready_row_pending=1;
          end
        end
      end
      if (nice_stream) observe_nice_stream();
      else observe_nice_legacy();
    end
  endtask

  // Observation only: these counters never drive the SoC or its memory model.
  // A phase includes software and bus gaps between its first and last operation.
  // Load phases end when the final data-write response retires; writeback ends
  // at every group's final Y-write response. Accepted operations start a new
  // phase on that edge, while an ending response changes the following edge.
  localparam PERF_OTHER = 0, PERF_W = 1, PERF_X = 2, PERF_BIAS = 3,
             PERF_COMPUTE = 4, PERF_WRITEBACK = 5;
  integer perf_phase;
  reg perf_active, perf_mmio_end_phase, perf_shared_end_writeback;
  integer perf_cycles, perf_w_load, perf_x_load, perf_bias_load;
  integer perf_compute_wait, perf_writeback, perf_other;
  integer perf_busy, perf_mac_fire, perf_starts, perf_dones;
  integer perf_mmio_reads, perf_mmio_writes, perf_mmio_stall;
  integer perf_shared_reads, perf_shared_writes, perf_shared_stall;
  integer perf_auto_rows, perf_auto_pops, perf_auto_overlap, perf_auto_full;
  integer perf_result_legacy, perf_result_packed, perf_result_logical, perf_result_y32;
  reg [15:0] perf_result_seen, perf_result_pending_mask;
  reg perf_result_pending, perf_result_pending_packed, perf_result_pending_y32;
  reg perf_result_pending_alias;
  integer perf_read_pop_aliases, perf_explicit_pops;
  reg [31:0] perf_result_expected;
  // Packed-source coverage is independent of transaction totals: every source
  // address must return its original W pair, then both values must be uploaded.
  reg [8191:0] packed_w_source_seen;
  reg [16383:0] packed_w_upload_seen;
  integer packed_w_source_words, packed_w_uploaded_values, packed_w_source_index;
  reg packed_w_source_pending, packed_w_upload_pending, packed_w_upload_rsp_seen;
  integer packed_w_upload_index;
  reg [31:0] packed_w_upload_rsp_data;
  reg [31:0] packed_w_source_expected;

  task reset_performance;
    begin
      perf_phase=PERF_OTHER;
      perf_active=0; perf_mmio_end_phase=0; perf_shared_end_writeback=0;
      perf_cycles=0; perf_w_load=0; perf_x_load=0; perf_bias_load=0;
      perf_compute_wait=0; perf_writeback=0; perf_other=0;
      perf_busy=0; perf_mac_fire=0; perf_starts=0; perf_dones=0;
      perf_mmio_reads=0; perf_mmio_writes=0; perf_mmio_stall=0;
      perf_shared_reads=0; perf_shared_writes=0; perf_shared_stall=0;
      perf_auto_rows=0; perf_auto_pops=0; perf_auto_overlap=0; perf_auto_full=0;
      perf_result_legacy=0; perf_result_packed=0; perf_result_logical=0; perf_result_y32=0;
      perf_result_seen=0; perf_result_pending=0; perf_result_pending_mask=0;
      perf_result_pending_packed=0; perf_result_pending_y32=0; perf_result_expected=0;
      perf_result_pending_alias=0; perf_read_pop_aliases=0; perf_explicit_pops=0;
      packed_w_source_seen=0; packed_w_upload_seen=0;
      packed_w_source_words=0; packed_w_uploaded_values=0;
      packed_w_source_index=0; packed_w_source_pending=0; packed_w_source_expected=0;
      packed_w_upload_pending=0; packed_w_upload_index=0;
      packed_w_upload_rsp_seen=0; packed_w_upload_rsp_data=0;
      nice_requests=0; nice_responses=0; nice_retired=0; nice_polls=0;
      nice_reads=0; nice_pops=0; nice_writes=0; nice_step=0;
      nice_direct_snapshots=0; nice_direct_pops=0; direct_bundle_hold=0; nice_bundle_cycle=-1;
      nice_alias_responses=0; nice_group_writes=0; nice_final_y_response_cycle=-1;
      nice_lane_responses=0; nice_pop_retired=0;
      stream_group=0; stream_groups_written=0; stream_group_cycle=0;
      ready_wait_cycles=0; ready_edges=0; ready_group_wait=0; ready_budget=0;
      ready_row_responses=0; ready_row_response_cycle=-1; ready_row_pending=0;
      nice_instruction=0; nice_pending=0; nice_endpoint=0; nice_endpoint_done=0;
      nice_request_cycle=0;
      nice_cmd_hold=0; nice_completion_hold=0;
    end
  endtask

  // Observe each returned logical word independently of the firmware's schedule.
  // Paired-HI covers two HI16 words, never two signs or two FIFO heads at once.
  task observe_result_reads;
    integer lane, index;
    reg [15:0] mask;
    begin
      if (perf_result_pending) begin
        if (`ACCEL.rsp_valid!==1'b1 || `ACCEL.rsp_err!==1'b0 ||
            `ACCEL.rsp_rdata!==perf_result_expected)
          $fatal(1,"owned result response changed or differs from integer golden");
        if (`ACCEL.rsp_ready) begin
          // The alias retires its POP at this endpoint edge. NICE may receive
          // the returned lane7 on a later edge, so count ownership here using
          // this accepted endpoint response rather than NICE's response mask.
          perf_result_seen=perf_result_seen | perf_result_pending_mask;
          if (perf_result_pending_alias) begin
            if (!nice_read_pop || !`ACCEL.row_pop)
              $fatal(1,"alias response retired without its owned POP");
            perf_read_pop_aliases=perf_read_pop_aliases+1;
          end
          if (perf_result_pending_y32) begin
            perf_result_y32=perf_result_y32+1;
            perf_result_logical=perf_result_logical+1;
          end else if (perf_result_pending_packed) begin
            perf_result_packed=perf_result_packed+1;
            perf_result_logical=perf_result_logical+2;
          end else begin
            perf_result_legacy=perf_result_legacy+1;
            perf_result_logical=perf_result_logical+1;
          end
          perf_result_pending=0;
        end
      end
      if (output_y32 && `ACCEL.cmd_valid && `ACCEL.cmd_ready && !`ACCEL.cmd_read &&
          `ACCEL.cmd_addr[11:0]==12'h0c8 && `ACCEL.cmd_wdata[0]) begin
        if (perf_result_seen!==16'h00ff || perf_result_pending)
          $fatal(1,"Y32 POP accepted before all eight lane responses retired");
        if (nice_read_pop) $fatal(1,"read-pop profile issued explicit POP write");
        perf_explicit_pops=perf_explicit_pops+1;
      end
      if (nice_direct && `ACCEL.xu_direct_valid && `ACCEL.xu_direct_ready) begin
        if (!`ACCEL.row_valid || !`ACCEL.row_active || `ACCEL.row_pop ||
            perf_result_seen || perf_result_pending || perf_auto_rows<1 || perf_auto_rows>99)
          $fatal(1,"direct logical result snapshot ownership mismatch");
        for (lane=0;lane<8;lane=lane+1) begin
          index=(perf_auto_rows-1)*256+`ACCEL.row_group*8+lane;
          if (`ACCEL.xu_direct_payload[32*lane +: 32]!==golden_y32[index])
            $fatal(1,"direct endpoint payload differs from integer golden lane=%0d",lane);
        end
        perf_result_seen=16'h00ff;
        perf_result_y32=perf_result_y32+8;
        perf_result_logical=perf_result_logical+8;
      end
      if (`ACCEL.row_pop) begin
        if (nice_direct && !`ACCEL.direct_row_pop)
          $fatal(1,"direct profile retired an MMIO POP");
        if (perf_result_seen!==(output_y32 ? 16'h00ff : 16'hffff) || perf_result_pending)
          $fatal(1,"POP retired before all owned logical result words returned");
        perf_result_seen=0;
      end
      if (`ACCEL.row_active && `ACCEL.cmd_valid && `ACCEL.cmd_ready &&
          `ACCEL.cmd_read &&
          ((`ACCEL.cmd_addr[11:0]>=12'h100 && `ACCEL.cmd_addr[11:0]<=12'h13c) ||
           (`ACCEL.cmd_addr[11:0]>=12'h140 && `ACCEL.cmd_addr[11:0]<=12'h14c) ||
           (`ACCEL.cmd_addr[11:0]>=12'h180 && `ACCEL.cmd_addr[11:0]<=12'h19c) ||
           `ACCEL.cmd_addr[11:0]==12'h1a0)) begin
        if (`ACCEL.row_valid!==1'b1 || `ACCEL.row_pop!==1'b0 || perf_result_pending ||
            `ACCEL.cmd_addr[1:0]!=0 || (^`ACCEL.row_group)===1'bx ||
            perf_auto_rows<1 || perf_auto_rows>99)
          $fatal(1,"ambiguous or unaligned owned result read");
        perf_result_pending_alias=`ACCEL.cmd_addr[11:0]==12'h1a0;
        if (perf_result_pending_alias &&
            (!nice_read_pop || perf_result_seen!==16'h007f || perf_result_pending))
          $fatal(1,"read-pop alias requires seven retired ordinary lane responses");
        perf_result_pending_y32=`ACCEL.cmd_addr[11:0]>=12'h180;
        if (perf_result_pending_y32 != (output_y32!=0))
          $fatal(1,"owned result read used the wrong output profile");
        lane=`ACCEL.cmd_addr[5:3];
        perf_result_pending_packed=`ACCEL.cmd_addr[11:0]>=12'h140 &&
                                   `ACCEL.cmd_addr[11:0]<=12'h14c;
        if (perf_result_pending_y32) lane=perf_result_pending_alias ? 7 : `ACCEL.cmd_addr[4:2];
        if (perf_result_pending_packed) lane=2*`ACCEL.cmd_addr[3:2];
        index=(perf_auto_rows-1)*256+`ACCEL.row_group*8+lane;
        if (perf_result_pending_y32) begin
          mask=16'h0001 << lane;
          perf_result_expected=golden_y32[index];
        end else if (perf_result_pending_packed) begin
          mask=16'h000a << (2*lane);
          perf_result_expected={golden[index+1][47:32],golden[index][47:32]};
        end else begin
          mask=16'h0001 << `ACCEL.cmd_addr[5:2];
          perf_result_expected=`ACCEL.cmd_addr[2] ?
            {16'b0,golden[index][47:32]} : golden[index][31:0];
        end
        if ((perf_result_seen & mask)!=0)
          $fatal(1,"duplicate logical result word from owned FIFO head");
        perf_result_pending_mask=mask;
        perf_result_pending=1;
      end
    end
  endtask

  task observe_packed_weight_transport;
    integer index;
    begin
      if (shared_w_packed16) begin
        if (packed_w_source_pending) begin
          if (rsp_valid!==1'b1 || rsp_rdata!==packed_w_source_expected)
            $fatal(1,"packed W source response changed or differs from original values");
          if (rsp_ready) begin
            packed_w_source_seen[packed_w_source_index]=1;
            packed_w_source_words=packed_w_source_words+1;
            packed_w_source_pending=0;
          end
        end
        if (cmd_valid && cmd_ready && cmd_read &&
            cmd_addr>=BASE+'h08000 && cmd_addr<BASE+'h18000) begin
          if (cmd_addr>=BASE+'h10000 || cmd_addr[1:0]!=0 || packed_w_source_pending)
            $fatal(1,"invalid packed W source address %h",cmd_addr);
          index=(cmd_addr-BASE-'h08000)/4;
          if (index!=packed_w_source_words || packed_w_source_seen[index])
            $fatal(1,"duplicate or out-of-order packed W source word %0d",index);
          packed_w_source_index=index;
          packed_w_source_expected={w[2*index+1],w[2*index]};
          packed_w_source_pending=1;
        end
        if (packed_w_upload_pending) begin
          // W_PACK32 can take multiple cycles to update its two SRAM banks.
          // Once offered, the response must stay stable until retirement.
          if (packed_w_upload_rsp_seen &&
              (`ACCEL.rsp_valid!==1'b1 || `ACCEL.rsp_rdata!==packed_w_upload_rsp_data))
            $fatal(1,"packed W upload response changed under backpressure");
          if (`ACCEL.rsp_valid) begin
            if (`ACCEL.rsp_err!==1'b0)
              $fatal(1,"packed W upload returned an error");
            packed_w_upload_rsp_seen=1;
            packed_w_upload_rsp_data=`ACCEL.rsp_rdata;
          end
          if (`ACCEL.rsp_valid && `ACCEL.rsp_ready) begin
            packed_w_upload_seen[packed_w_upload_index]=1;
            packed_w_upload_seen[packed_w_upload_index+1]=1;
            packed_w_uploaded_values=packed_w_uploaded_values+2;
            packed_w_upload_pending=0;
          end
        end
        if (`ACCEL.cmd_valid && `ACCEL.cmd_ready && !`ACCEL.cmd_read) begin
          if (`ACCEL.cmd_addr[11:0]==12'h024 || `ACCEL.cmd_addr[11:0]==12'h058)
            $fatal(1,"packed W source must use W_PACK32 uploads");
          if (`ACCEL.cmd_addr[11:0]==12'h05c) begin
            index=`ACCEL.w_cursor;
            if (index<0 || index>=16383 || index%2 ||
                index!=packed_w_uploaded_values)
              $fatal(1,"invalid packed W upload cursor %0d",index);
            if (packed_w_upload_pending || !packed_w_source_seen[index/2] ||
                packed_w_upload_seen[index] || packed_w_upload_seen[index+1] ||
                `ACCEL.cmd_wdata!=={w[index+1],w[index]})
              $fatal(1,"packed W upload lacks the correct retired source pair %0d",index);
            packed_w_upload_index=index;
            packed_w_upload_pending=1;
            packed_w_upload_rsp_seen=0;
          end
        end
      end
    end
  endtask

  task observe_performance;
    integer phase_now, phase_next;
    reg shared_accept, shared_retire, mmio_accept, mmio_retire, start_accept;
    reg in_window, row_start_accept;
    begin
      shared_accept=cmd_valid && cmd_ready;
      shared_retire=rsp_valid && rsp_ready;
      mmio_accept=`ACCEL.cmd_valid && `ACCEL.cmd_ready;
      mmio_retire=`ACCEL.rsp_valid && `ACCEL.rsp_ready;
      start_accept=mmio_accept && !`ACCEL.cmd_read &&
                   `ACCEL.cmd_addr[11:0]==12'h008 &&
                   `ACCEL.cmd_wdata[0] && !`ACCEL.busy;
      row_start_accept=`ACCEL.row_start_accept;
      // Include the first source request and all waits before its acceptance.
      in_window=perf_active || (first_cycle<0 && source_request);
      if (dumpwave==2 && !perf_active && in_window) begin
        $dumpon;
        $display("ACTIVITY_BEGIN layer=%0d time=%0t",layer,$time);
      end
      if (in_window) begin
        perf_active=1;
        observe_result_reads();
        observe_packed_weight_transport();
        phase_now=perf_phase;
        phase_next=perf_phase;
        if ((mmio_retire && perf_mmio_end_phase) ||
            (shared_retire && perf_shared_end_writeback) ||
            (`ACCEL.core_done && (!`ACCEL.row_active || perf_phase==PERF_COMPUTE)))
          phase_next=PERF_OTHER;

        if (mmio_accept && !`ACCEL.cmd_read) begin
          case (`ACCEL.cmd_addr[11:0])
            12'h01c, 12'h020, 12'h024, 12'h054, 12'h058, 12'h05c: begin
              phase_now=PERF_W; phase_next=PERF_W;
            end
            12'h014, 12'h018, 12'h060, 12'h064, 12'h068: begin
              phase_now=PERF_X; phase_next=PERF_X;
            end
            12'h028, 12'h02c, 12'h030,
            12'h040, 12'h044, 12'h048, 12'h04c: begin
              phase_now=PERF_BIAS; phase_next=PERF_BIAS;
            end
            12'h034: begin
              phase_now=PERF_WRITEBACK; phase_next=PERF_WRITEBACK;
            end
            default: begin end
          endcase
        end
        // The read-only window has no RESULT_INDEX write to start writeback.
        if (mmio_accept && `ACCEL.cmd_read &&
            ((`ACCEL.cmd_addr[11:0]>=12'h080 && `ACCEL.cmd_addr[11:0]<=12'h0bc) ||
             (`ACCEL.cmd_addr[11:0]>=12'h100 && `ACCEL.cmd_addr[11:0]<=12'h14c) ||
             (`ACCEL.cmd_addr[11:0]>=12'h180 && `ACCEL.cmd_addr[11:0]<=12'h19c) ||
             `ACCEL.cmd_addr[11:0]==12'h1a0)) begin
          phase_now=PERF_WRITEBACK; phase_next=PERF_WRITEBACK;
        end
        // Direct claim starts actual result acquisition in this profile;
        // the producer spends eight cycles capturing lanes into its bundle.
        // Legacy profiles still start writeback only at their MMIO result read.
        if (nice_direct && `ACCEL.xu_direct_claim) begin
          phase_now=PERF_WRITEBACK; phase_next=PERF_WRITEBACK;
        end
        if (start_accept || row_start_accept) begin
          phase_now=PERF_COMPUTE; phase_next=PERF_COMPUTE;
        end
        if (mmio_accept && `ACCEL.cmd_read && `ACCEL.cmd_addr[11:0]==12'h0c4) begin
          phase_now=PERF_COMPUTE; phase_next=PERF_COMPUTE;
        end
        // Source reads can precede their matching MMIO load operation.
        if (cmd_valid && cmd_read && (shared_accept || first_cycle<0)) begin
          if (cmd_addr>=BASE+'h08000 && cmd_addr<BASE+'h18000) begin
            phase_now=PERF_W; phase_next=PERF_W;
          end else if (cmd_addr>=BASE && cmd_addr<BASE+'h06300) begin
            phase_now=PERF_X; phase_next=PERF_X;
          end else if (cmd_addr>=BASE+'h18000 && cmd_addr<BASE+'h18800) begin
            phase_now=PERF_BIAS; phase_next=PERF_BIAS;
          end
        end
        perf_phase=phase_next;
        perf_cycles=perf_cycles+1;
        case (phase_now)
          PERF_W: perf_w_load=perf_w_load+1;
          PERF_X: perf_x_load=perf_x_load+1;
          PERF_BIAS: perf_bias_load=perf_bias_load+1;
          PERF_COMPUTE: perf_compute_wait=perf_compute_wait+1;
          PERF_WRITEBACK: perf_writeback=perf_writeback+1;
          default: perf_other=perf_other+1;
        endcase
        if (`ACCEL.manual_busy || `ACCEL.row_running ||
            (`ACCEL.row_active && `ACCEL.compute_start)) perf_busy=perf_busy+1;
        if (row_start_accept) perf_auto_rows=perf_auto_rows+1;
        if (`ACCEL.row_pop) perf_auto_pops=perf_auto_pops+1;
        if (`ACCEL.row_running && phase_now==PERF_WRITEBACK)
          perf_auto_overlap=perf_auto_overlap+1;
        if (`ACCEL.row_active && `ACCEL.row_count==2 && !`ACCEL.row_running)
          perf_auto_full=perf_auto_full+1;
        // All eight PEs share this enable: one fire means eight signed16 MACs.
        if (`ACCEL.u_linear_compute_core.core.engine.peArray.io_enable)
          perf_mac_fire=perf_mac_fire+1;
        if (start_accept || (`ACCEL.row_active && `ACCEL.compute_start))
          perf_starts=perf_starts+1;
        if (`ACCEL.core_done) perf_dones=perf_dones+1;
        if (mmio_accept) begin
          if (`ACCEL.cmd_read) perf_mmio_reads=perf_mmio_reads+1;
          else perf_mmio_writes=perf_mmio_writes+1;
        end
        if (shared_accept) begin
          if (cmd_read) perf_shared_reads=perf_shared_reads+1;
          else perf_shared_writes=perf_shared_writes+1;
        end
        // A stall is a cycle with either blocked channel, counted once.
        if ((`ACCEL.cmd_valid && !`ACCEL.cmd_ready) ||
            (`ACCEL.rsp_valid && !`ACCEL.rsp_ready))
          perf_mmio_stall=perf_mmio_stall+1;
        if ((cmd_valid && !cmd_ready) || (rsp_valid && !rsp_ready))
          perf_shared_stall=perf_shared_stall+1;
        if (shared_retire && final_write_pending) begin
          perf_active=0;
          if (dumpwave==2) begin
            $display("ACTIVITY_END layer=%0d time=%0t",layer,$time);
            $dumpoff;
          end
        end
      end

      // Retiring metadata belongs to the old response even when the next
      // command is accepted on the same edge. Each endpoint has one slot.
      if (mmio_retire) perf_mmio_end_phase=0;
      if (mmio_accept)
        perf_mmio_end_phase=!`ACCEL.cmd_read &&
          ((`ACCEL.cmd_addr[11:0]==12'h024 &&
            `ACCEL.w_bank_reg==7 && `ACCEL.w_addr_reg==2047) ||
           (`ACCEL.cmd_addr[11:0]==12'h018 && `ACCEL.x_addr_reg==63) ||
           (`ACCEL.cmd_addr[11:0]==12'h058 && `ACCEL.w_cursor==16383) ||
           (`ACCEL.cmd_addr[11:0]==12'h064 && `ACCEL.x_cursor==63) ||
           (`ACCEL.cmd_addr[11:0]==12'h05c && `ACCEL.w_cursor==16382) ||
           (`ACCEL.cmd_addr[11:0]==12'h068 && `ACCEL.x_cursor==62) ||
           (`ACCEL.cmd_addr[11:0]==12'h030 && `ACCEL.bias_index_reg==7) ||
           (`ACCEL.cmd_addr[11:0]==12'h040 && `ACCEL.cmd_wdata[0]));
      if (shared_retire) perf_shared_end_writeback=0;
      if (shared_accept)
        perf_shared_end_writeback=!cmd_read && cmd_addr>=BASE+YOFF &&
          cmd_addr<BASE+YOFF+output_words*4 &&
          (output_y32 ? cmd_addr[4:0]==5'h1c : cmd_addr[5:0]==6'h3c);
    end
  endtask

  task report_performance;
    begin
      if (perf_cycles!=last_cycle-first_cycle+1 ||
          perf_w_load+perf_x_load+perf_bias_load+perf_compute_wait+
          perf_writeback+perf_other!=perf_cycles)
        $fatal(1,"performance interval or phase sum mismatch");
      if (first_accept_cycle<first_cycle || first_accept_cycle<0 ||
          first_accept_cycle-first_cycle<first_source_stall)
        $fatal(1,"first source request/wait is missing from the measured interval");
      $display("WINDOW_TASK layer=%0d first_request=%0d first_accept=%0d final_y_response=%0d first_request_wait=%0d",
        layer,first_cycle,first_accept_cycle,last_cycle,first_accept_cycle-first_cycle);
      if (output_y32 && perf_auto_rows==0)
        $fatal(1,"Y32 requires complete autonomous row and lane observations");
      if (perf_auto_rows!=0) begin
        if (nice_direct)
          $display("DIRECT_AUTO_DIAGNOSTIC rows=%0d pops=%0d active=%b retired=%0d produced=%0d count=%0d overlap=%0d full_wait=%0d bundles=%0d direct_pops=%0d logical=%0d",
            perf_auto_rows,perf_auto_pops,`ACCEL.row_active,`ACCEL.row_retired,
            `ACCEL.row_produced,`ACCEL.row_count,perf_auto_overlap,perf_auto_full,
            nice_direct_snapshots,nice_direct_pops,perf_result_logical);
        if (perf_auto_rows!=99 || perf_auto_pops!=3168 || `ACCEL.row_active ||
            `ACCEL.row_retired!=32 || `ACCEL.row_produced!=32 || `ACCEL.row_count!=0 ||
            perf_auto_overlap==0)
          $fatal(1,"autonomous row/POP retirement or overlap contract mismatch");
        $display("AUTO_TASK layer=%0d rows=%0d pops_retired=%0d compute_writeback_overlap=%0d fifo_full_wait=%0d",
          layer,perf_auto_rows,perf_auto_pops,perf_auto_overlap,perf_auto_full);
        if (perf_result_logical!=(output_y32 ? 25344 : 50688) ||
            perf_result_seen || perf_result_pending)
          $fatal(1,"incomplete logical FIFO results at final Y response retirement");
        if (output_y32) begin
          if (perf_result_y32!=25344 || perf_result_legacy || perf_result_packed)
            $fatal(1,"incomplete Y32 lane response retirement");
          $display("RESULT_TASK_Y32 layer=%0d words=%0d logical_results=%0d",
            layer,perf_result_y32,perf_result_logical);
        end else
          $display("RESULT_TASK layer=%0d legacy_words=%0d packed_words=%0d logical_words=%0d",
            layer,perf_result_legacy,perf_result_packed,perf_result_logical);
      end
      if (shared_w_packed16) begin
        if (packed_w_source_words!=8192 || packed_w_uploaded_values!=16384 ||
            packed_w_source_seen!=={8192{1'b1}} ||
            packed_w_upload_seen!=={16384{1'b1}} || packed_w_source_pending ||
            packed_w_upload_pending)
          $fatal(1,"incomplete packed W source or uploaded-value coverage");
        $display("W_PACKED16_TASK layer=%0d source_words=%0d uploaded_values=%0d",
          layer,packed_w_source_words,packed_w_uploaded_values);
      end
      if (nice_drain8) begin
        if (nice_requests!=(nice_stream ? 99 : 3168) || nice_responses!=(nice_stream ? 99 : 3168) ||
            nice_retired!=(nice_stream ? 99 : 3168) ||
            (nice_ready ? nice_polls!=0 : nice_polls<3168) || nice_reads!=(nice_direct ? 0 : 25344) || nice_pops!=3168 || nice_writes!=25344 ||
            nice_alias_responses!=(nice_read_pop ? 3168 : 0) || nice_group_writes!=8 ||
            nice_lane_responses!==8'hff || !nice_pop_retired || nice_final_y_response_cycle<0 ||
            nice_instruction || nice_pending || nice_cmd_hold || nice_completion_hold)
          $fatal(1,"NICE complete task instruction/payload retirement mismatch");
        $display("NICE_TASK layer=%0d requests=%0d responses=%0d oitf_retired=%0d status_polls=%0d result_reads=%0d pops_retired=%0d shared_writes=%0d",
          layer,nice_requests,nice_responses,nice_retired,nice_polls,nice_reads,nice_pops,nice_writes);
        if (nice_direct) begin
          if (nice_direct_snapshots!=3168 || nice_direct_pops!=3168 ||
              perf_read_pop_aliases || perf_explicit_pops)
            $fatal(1,"direct endpoint count/profile mismatch");
          $display("DIRECT_TASK layer=%0d snapshots=%0d lanes=%0d pops_retired=%0d result_mmio_reads=%0d",
            layer,nice_direct_snapshots,8*nice_direct_snapshots,nice_direct_pops,nice_reads);
          if (nice_stream) begin
            if (stream_groups_written!=3168 || stream_group!=31)
              $fatal(1,"stream group/final-response coverage mismatch");
            $display("STREAM_TASK layer=%0d requests=%0d groups=%0d snapshots=%0d pops_retired=%0d shared_writes=%0d final_response_before_completion=1",
              layer,nice_requests,stream_groups_written,nice_direct_snapshots,nice_direct_pops,nice_writes);
            if (nice_ready) begin
              if (ready_edges!=3168 || ready_wait_cycles<3168 || ready_wait_cycles>perf_cycles ||
                  ready_row_responses!=99 || ready_row_pending || nice_polls!=0)
                $fatal(1,"ready exact wait/row/zero-poll coverage mismatch");
              $display("READY_TASK layer=%0d requests=%0d groups=%0d ready_edges=%0d ready_wait_cycles=%0d status_polls=%0d snapshots=%0d pops_retired=%0d shared_writes=%0d final_response_before_completion=1",
                layer,nice_requests,stream_groups_written,ready_edges,ready_wait_cycles,nice_polls,
                nice_direct_snapshots,nice_direct_pops,nice_writes);
            end
          end
        end else if (nice_read_pop) begin
          if (perf_read_pop_aliases!=3168 || perf_explicit_pops!=0)
            $fatal(1,"read-pop alias endpoint retirement or explicit POP count mismatch");
          $display("READ_POP_TASK layer=%0d alias_reads=%0d explicit_pops=%0d",
            layer,perf_read_pop_aliases,perf_explicit_pops);
        end else if (perf_read_pop_aliases || perf_explicit_pops!=3168)
          $fatal(1,"legacy NICE endpoint POP profile mismatch");
      end
      $display("PERF_TASK layer=%0d cycles=%0d w_load=%0d x_load=%0d bias_load=%0d compute_wait=%0d writeback=%0d other=%0d busy=%0d mac_fire=%0d mmio_reads=%0d mmio_writes=%0d shared_reads=%0d shared_writes=%0d shared_stall=%0d mmio_stall=%0d starts=%0d dones=%0d",
        layer,perf_cycles,perf_w_load,perf_x_load,perf_bias_load,
        perf_compute_wait,perf_writeback,perf_other,perf_busy,perf_mac_fire,
        perf_mmio_reads,perf_mmio_writes,perf_shared_reads,perf_shared_writes,
        perf_shared_stall,perf_mmio_stall,perf_starts,perf_dones);
    end
  endtask

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

  task load_layer(input integer index);
    string directory;
    integer i;
    begin
      directory = $sformatf("%s/layer_%02d/", vectors, index);
      $readmemh({directory,"x.mem"}, x);
      $readmemh({directory,"w.mem"}, w);
      $readmemh({directory,"bias.mem"}, bias);
      $readmemh({directory,"y.mem"}, golden);
      if (output_y32) begin
        for (i=0; i<25344; i=i+1) golden_y32[i]=32'bx;
        $readmemh({directory,"y32.mem"}, golden_y32);
        for (i=0; i<25344; i=i+1)
          if ((^golden_y32[i])===1'bx) $fatal(1,"missing or unknown Y32 golden %0d",i);
      end
      if (shared_w_packed16) begin
        for (i=0; i<8192; i=i+1) w_packed16[i]=32'bx;
        $readmemh({directory,"w_packed16.mem"}, w_packed16);
      end
      for (i=0; i<6336; i=i+1) ram[i] = {16'b0,x[i]};
      if (shared_w_packed16) begin
        for (i=0; i<8192; i=i+1) begin
          if ((^w_packed16[i])===1'bx || w_packed16[i]!=={w[2*i+1],w[2*i]})
            $fatal(1,"packed W fixture differs from original pair %0d",i);
          ram['h8000/4+i] = w_packed16[i];
        end
      end else
        for (i=0; i<16384; i=i+1) ram['h8000/4+i] = {16'b0,w[i]};
      for (i=0; i<256; i=i+1) begin
        ram['h18000/4+2*i] = bias[i][31:0];
        ram['h18000/4+2*i+1] = {{24{bias[i][39]}},bias[i][39:32]};
      end
      // Poison output memory on every layer; no result survives as evidence.
      for (i=0; i<output_words; i=i+1) ram[YOFF/4+i] = 32'hdeadbeef;
      writes = 0; first_cycle = -1; first_accept_cycle = -1; final_write_pending = 0;
      reset_performance();
    end
  endtask

  initial begin : initialize
    integer i;
    if (!$value$plusargs("TESTCASE=%s",testcase) ||
        !$value$plusargs("VECTORS=%s",vectors) ||
        !$value$plusargs("TASKS=%d",tasks)) $fatal(1,"missing plusargs");
    if (tasks < 1 || tasks > 12) $fatal(1,"invalid task count");
    if (tasks!=1) $fatal(1,"S3 clear campaign requires fresh-reset TASKS=1");
    if (!$value$plusargs("OUTPUT_Y32=%d",output_y32)) output_y32=0;
    if (!$value$plusargs("SHARED_W_PACKED16=%d",shared_w_packed16)) shared_w_packed16=0;
    if (!$value$plusargs("NICE_DRAIN8=%d",nice_drain8)) nice_drain8=0;
    if (!$value$plusargs("NICE_READ_POP=%d",nice_read_pop)) nice_read_pop=0;
    if (!$value$plusargs("NICE_DIRECT=%d",nice_direct)) nice_direct=0;
    if (!$value$plusargs("NICE_STREAM=%d",nice_stream)) nice_stream=0;
    if (!$value$plusargs("NICE_READY=%d",nice_ready)) nice_ready=0;
    if ((output_y32!=0 && output_y32!=1) ||
        (shared_w_packed16!=0 && shared_w_packed16!=1) ||
        (nice_drain8!=0 && nice_drain8!=1) || (nice_drain8 && (!output_y32 || !shared_w_packed16)) ||
        (nice_read_pop!=0 && nice_read_pop!=1) || (nice_read_pop && !nice_drain8) ||
        (nice_direct!=0 && nice_direct!=1) || (nice_direct && (!nice_drain8 || nice_read_pop)) ||
        (nice_stream!=0 && nice_stream!=1) || (nice_stream && !nice_direct) ||
        (nice_ready!=0 && nice_ready!=1) || (nice_ready && !nice_stream))
      $fatal(1,"invalid output or shared W layout mode");
    output_words=output_y32 ? 25344 : 50688;
    if (!$value$plusargs("MAX_CYCLES=%d",max_cycles)) max_cycles=200000000;
    if (!$value$plusargs("FIRST_SOURCE_STALL=%d",first_source_stall)) first_source_stall=0;
    if (first_source_stall<0 || first_source_stall>1000) $fatal(1,"invalid first-source stall");
    for (i=0; i<65536; i=i+1) program_bytes[i]=0;
    $readmemh({testcase,".verilog"},program_bytes);
    for (i=0; i<8192; i=i+1)
      `ITCM.mem_r[i] = {program_bytes[8*i+7],program_bytes[8*i+6],
        program_bytes[8*i+5],program_bytes[8*i+4],program_bytes[8*i+3],
        program_bytes[8*i+2],program_bytes[8*i+1],program_bytes[8*i]};
    ram[HOST/4]=tasks;
    load_layer(0);
    if ($value$plusargs("DUMPWAVE=%d",dumpwave) && dumpwave) begin
      $dumpfile("tb_accel_soc.vcd");
      if (dumpwave==2) begin
        $dumpvars(0,`ACCEL);
        $dumpoff;
      end else $dumpvars(0,tb_accel_soc);
    end
    #120 rst_n=1;
    // Let synchronized CPU reset become high, before any transaction can begin.
    wait (`CPU.u_e203_cpu.rst_core===1'b1);
    @(negedge clk);
    if (source_request || `NICE.nice_req_valid || `ACCEL.cmd_valid || cmd_valid)
      $fatal(1,"S3 startup reset unsafe prewarm transaction");
    s3_startup_assert_ns=$realtime/1ns;
    $display("S3_STARTUP_PROFILE event=second_assert time_ns=%.6f cpu_reset_n=%b",
      s3_startup_assert_ns,`CPU.u_e203_cpu.rst_core);
    rst_n=0;
    #120ns;
    if (`CPU.u_e203_cpu.rst_core!==1'b0)
      $fatal(1,"S3 startup reset did not reach actual CPU reset");
    $display("S3_STARTUP_PROFILE event=second_release time_ns=%.6f held_ns=%.6f cpu_reset_n=%b",
      $realtime/1ns,$realtime/1ns-s3_startup_assert_ns,`CPU.u_e203_cpu.rst_core);
    s3_startup_complete=1;
    rst_n=1;
    $display("S3_STARTUP_PROFILE event=measurement_begin time_ns=%.6f external_reset_n=%b cycle=%0d",
      $realtime/1ns,rst_n,cycles);
  end

  always @(posedge clk) begin : memory_and_scoreboard
    integer offset, word_index;
    reg [63:0] expected;
    cycles <= s3_startup_complete ? cycles+1 : 0;
    if (cycles > max_cycles) $fatal(1,"SoC timeout layer=%0d writes=%0d",layer,writes);
    if (rst_n) begin
      // The chip-level reset releases before the peripheral clock/reset.
      // Arm on a real request, never on an idle/busy value becoming favorable.
      // A source request arriving first still arms and fails incomplete clear.
      if (!s3_clear_armed && ((`ACCEL.cmd_valid===1'b1) || source_request)) begin
        s3_clear_armed=1;
        if (`ACCEL.rst_n!==1'b1)
          $fatal(1,"S3 clear request before actual accelerator reset release");
        $display("S3_CLEAR_OBSERVER_ARM cycle=%0d actual_accel_reset_n=%b",cycles,`ACCEL.rst_n);
      end
      if (s3_clear_armed) s3_observe_task_clear(source_request,
        !`NICE.nice_active && !`NICE.nice_req_valid &&
        !`NICE.nice_icb_cmd_valid && !`NICE.nice_icb_rsp_valid &&
        !`NICE.nice_rsp_valid && !`NICE.nice_mem_holdup,
        s3_payload_phase);
      if (s3_payload_phase) begin
        if (1'b0 && nice_drain8) observe_nice();
        observe_performance();
      end
      if (first_cycle<0 && source_request) first_cycle=cycles;
      // A response must correspond to exactly one unretired shared-memory command.
      if (rsp_valid && outstanding != 1) $fatal(1,"orphan shared response");
      if (rsp_valid && rsp_ready) outstanding=outstanding-1;
      if (cmd_valid && cmd_ready) outstanding=outstanding+1;
      if (outstanding<0 || outstanding>1) $fatal(1,"shared outstanding count");
      if (rsp_valid && rsp_ready && final_write_pending) begin
        last_cycle=cycles;
        final_write_pending=0;
      end
      // Response retirement is independent of accepting the next command.
      if (rsp_valid && rsp_ready) rsp_valid <= 0;
      if (cmd_ready) begin
        rsp_valid <= cmd_valid;
        if (cmd_valid) begin
          if (cmd_addr < BASE || cmd_addr >= BASE+'h80000 || cmd_addr[1:0]!=0)
            $fatal(1,"invalid shared address %h",cmd_addr);
          offset=cmd_addr-BASE;
          word_index=offset/4;
          if (cmd_read) begin
            rsp_rdata <= ram[word_index];
            if (offset < 'h18800 && first_accept_cycle<0) begin
              if (first_cycle<0) $fatal(1,"source accepted before observed first request");
              first_accept_cycle=cycles;
            end
          end else begin
            if (cmd_wmask != 4'hf) $fatal(1,"partial shared write");
            if (offset>=YOFF && offset<YOFF+output_words*4) begin
              if (offset != YOFF+writes*4) $fatal(1,"write order %h index %0d",offset,writes);
              if (output_y32) expected={32'b0,golden_y32[writes]};
              else expected={{16{golden[writes/2][47]}},golden[writes/2]};
              if (cmd_wdata !== (output_y32 ? expected[31:0] :
                                (writes%2 ? expected[63:32] : expected[31:0])))
                $fatal(1,"result mismatch layer=%0d word=%0d got=%h expected=%h",
                  layer,writes,cmd_wdata,output_y32 ? expected[31:0] :
                  (writes%2 ? expected[63:32] : expected[31:0]));
              ram[word_index]=cmd_wdata;
              writes=writes+1;
              if (writes==output_words) final_write_pending=1;
            end else if (offset==HOST+8) firmware_cycles=cmd_wdata;
            else if (offset==HOST+4) begin
              if (cmd_wdata!=layer+1 || writes!=output_words || final_write_pending || first_cycle<0)
                $fatal(1,"premature or incorrect writeback ACK");
              $display("TASK_PASS layer=%0d outputs=25344 writes=%0d cycles=%0d firmware_cycles=%0d",
                layer,writes,last_cycle-first_cycle+1,firmware_cycles);
              report_performance();
              $fflush();
              completed=completed+1;
              layer=layer+1;
              if (layer<tasks) load_layer(layer);
            end else $fatal(1,"unexpected shared write %h",cmd_addr);
          end
        end
      end
      if (`EXU.u_e203_exu_commit.alu_cmt_i_valid && `EXU.u_e203_exu_commit.alu_cmt_i_ready &&
          `EXU.u_e203_exu_commit.alu_cmt_i_pc==32'h80000086) begin
        if (`EXU.u_e203_exu_regfile.rf_r[3]!=1 || completed!=tasks)
          $fatal(1,"firmware failure gp=%0d completed=%0d",`EXU.u_e203_exu_regfile.rf_r[3],completed);
        $display("SOC_PASS tasks=%0d outputs=%0d writes=%0d",completed,completed*25344,completed*output_words);
        $finish;
      end
    end
  end
  // Prewarm cannot execute clear or payload; all original monitors remain active.
  always @(posedge source_request or posedge `NICE.nice_req_valid or
           posedge `ACCEL.cmd_valid or posedge cmd_valid) begin
    if (!s3_startup_complete)
      $fatal(1,"S3 startup reset prewarm issued a transaction");
  end
  initial begin
    #10ms;
    if (!s3_startup_complete) $fatal(1,"S3 startup reset actual CPU release timeout");
  end
endmodule
