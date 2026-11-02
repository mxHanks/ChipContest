// Generated from original TB SHA256 bba0248513ca2dfe67be907306417bf6eb2c34d45603a7c55a33b5a062d2fc44
`include "e203_defines.v"
module tb_xu_soc_ppa;
  reg clk = 0, lfclk = 0, rst_n = 0;
  always #2 clk = ~clk;
  always #33 lfclk = ~lfclk;
  wire cmd_valid, cmd_read, cmd_ready, rsp_ready;
  wire [31:0] cmd_addr, cmd_wdata;
  wire [3:0] cmd_wmask;
  wire rsp_valid;
  wire [31:0] rsp_rdata;
  wire rsp_err;
  reg [31:0] ram [0:131071]; // Development shared SRAM: exactly 512 KiB.
  reg [15:0] x [0:6335], w [0:16383];
  reg [39:0] bias [0:255];
  reg [47:0] golden [0:25343];
  reg [7:0] program_bytes [0:65535];
  reg [63:0] xu_program_words [0:8191];
  string testcase, vectors;
  integer tasks, layer = 0, completed = 0, writes = 0;
  integer cycles = 0, first_cycle = -1, last_cycle = 0;
  integer max_cycles, firmware_cycles = 0;
  integer outstanding = 0;
  reg final_write_pending = 0;
  integer dumpwave;
  localparam BASE = 32'ha0000000, YOFF = 32'h20000, HOST = 32'h7f000;

  // Backpressure exercises CPU/bus waits; responses remain stable until accepted.
  assign cmd_ready=dut.ext_sysmem_cmd_ready;
  assign cmd_valid=dut.ext_sysmem_cmd_valid;
  assign cmd_read=dut.ext_sysmem_cmd_read;
  assign cmd_addr=dut.ext_sysmem_cmd_addr;
  assign cmd_wdata=dut.ext_sysmem_cmd_wdata;
  assign cmd_wmask=dut.ext_sysmem_cmd_wmask;
  assign rsp_ready=dut.ext_sysmem_rsp_ready;
  assign rsp_valid=dut.ext_sysmem_rsp_valid;
  assign rsp_rdata=dut.ext_sysmem_rsp_rdata;
  assign rsp_err=dut.ext_sysmem_rsp_err;
  `define CPU dut.u_soc.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top
  `define EXU `CPU.u_e203_cpu.u_e203_core.u_e203_exu
  `define ITCM `CPU.u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram
  `define ACCEL dut.u_soc.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.u_accel_icb_slave

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

  task reset_performance;
    begin
      perf_phase=PERF_OTHER;
      perf_active=0; perf_mmio_end_phase=0; perf_shared_end_writeback=0;
      perf_cycles=0; perf_w_load=0; perf_x_load=0; perf_bias_load=0;
      perf_compute_wait=0; perf_writeback=0; perf_other=0;
      perf_busy=0; perf_mac_fire=0; perf_starts=0; perf_dones=0;
      perf_mmio_reads=0; perf_mmio_writes=0; perf_mmio_stall=0;
      perf_shared_reads=0; perf_shared_writes=0; perf_shared_stall=0;
    end
  endtask

  task observe_performance;
    integer phase_now, phase_next;
    reg shared_accept, shared_retire, mmio_accept, mmio_retire, start_accept;
    reg in_window;
    begin
      shared_accept=cmd_valid && cmd_ready;
      shared_retire=rsp_valid && rsp_ready;
      mmio_accept=`ACCEL.cmd_valid && `ACCEL.cmd_ready;
      mmio_retire=`ACCEL.rsp_valid && `ACCEL.rsp_ready;
      start_accept=mmio_accept && !`ACCEL.cmd_read &&
                   `ACCEL.cmd_addr[11:0]==12'h008 &&
                   `ACCEL.cmd_wdata[0] && !`ACCEL.busy;
      // Match the existing inclusive first-input/final-Y-response interval.
      in_window=perf_active || (first_cycle<0 && shared_accept && cmd_read &&
                               cmd_addr>=BASE && cmd_addr<BASE+'h18800);
      if (dumpwave==2 && !perf_active && in_window) begin
        $dumpon;
        $display("ACTIVITY_BEGIN layer=%0d time=%0t",layer,$time);
      end
      if (in_window) begin
        perf_active=1;
        phase_now=perf_phase;
        phase_next=perf_phase;
        if ((mmio_retire && perf_mmio_end_phase) ||
            (shared_retire && perf_shared_end_writeback) || `ACCEL.core_done)
          phase_next=PERF_OTHER;

        if (mmio_accept && !`ACCEL.cmd_read) begin
          case (`ACCEL.cmd_addr[11:0])
            12'h01c, 12'h020, 12'h024: begin
              phase_now=PERF_W; phase_next=PERF_W;
            end
            12'h014, 12'h018: begin
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
            `ACCEL.cmd_addr[11:0]>=12'h080 && `ACCEL.cmd_addr[11:0]<=12'h0bc) begin
          phase_now=PERF_WRITEBACK; phase_next=PERF_WRITEBACK;
        end
        if (start_accept) begin
          phase_now=PERF_COMPUTE; phase_next=PERF_COMPUTE;
        end
        // Source reads can precede their matching MMIO load operation.
        if (shared_accept && cmd_read) begin
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
        if (`ACCEL.busy) perf_busy=perf_busy+1;
        // All eight PEs share this enable: one fire means eight signed16 MACs.
        if (`ACCEL.u_linear_compute_core.core.engine.peArray.io_enable)
          perf_mac_fire=perf_mac_fire+1;
        if (start_accept) perf_starts=perf_starts+1;
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
           (`ACCEL.cmd_addr[11:0]==12'h030 && `ACCEL.bias_index_reg==7) ||
           (`ACCEL.cmd_addr[11:0]==12'h040 && `ACCEL.cmd_wdata[0]));
      if (shared_retire) perf_shared_end_writeback=0;
      if (shared_accept)
        perf_shared_end_writeback=!cmd_read && cmd_addr>=BASE+YOFF &&
          cmd_addr<BASE+YOFF+50688*4 && cmd_addr[5:0]==6'h3c;
    end
  endtask

  task report_performance;
    begin
      if (perf_cycles!=last_cycle-first_cycle+1 ||
          perf_w_load+perf_x_load+perf_bias_load+perf_compute_wait+
          perf_writeback+perf_other!=perf_cycles)
        $fatal(1,"performance interval or phase sum mismatch");
      $display("PERF_TASK layer=%0d cycles=%0d w_load=%0d x_load=%0d bias_load=%0d compute_wait=%0d writeback=%0d other=%0d busy=%0d mac_fire=%0d mmio_reads=%0d mmio_writes=%0d shared_reads=%0d shared_writes=%0d shared_stall=%0d mmio_stall=%0d starts=%0d dones=%0d",
        layer,perf_cycles,perf_w_load,perf_x_load,perf_bias_load,
        perf_compute_wait,perf_writeback,perf_other,perf_busy,perf_mac_fire,
        perf_mmio_reads,perf_mmio_writes,perf_shared_reads,perf_shared_writes,
        perf_shared_stall,perf_mmio_stall,perf_starts,perf_dones);
    end
  endtask

  xu_soc_ppa_top dut (
    .hfextclk(clk), .lfextclk(lfclk), .io_pads_aon_erst_n_i_ival(rst_n),
    .io_pads_jtag_TCK_i_ival(1'b0), .io_pads_jtag_TMS_i_ival(1'b0),
    .io_pads_jtag_TDI_i_ival(1'b0), .io_pads_gpioA_i_ival(32'b0),
    .io_pads_gpioB_i_ival(32'b0), .io_pads_qspi0_dq_0_i_ival(1'b0),
    .io_pads_qspi0_dq_1_i_ival(1'b0), .io_pads_qspi0_dq_2_i_ival(1'b0),
    .io_pads_qspi0_dq_3_i_ival(1'b0), .io_pads_bootrom_n_i_ival(1'b0),
    .io_pads_dbgmode0_n_i_ival(1'b1), .io_pads_dbgmode1_n_i_ival(1'b1),
    .io_pads_dbgmode2_n_i_ival(1'b1), .io_pads_aon_pmu_dwakeup_n_i_ival(1'b1),
    .hfxoscen(), .lfxoscen(), .io_pads_jtag_TDO_o_oval(), .io_pads_jtag_TDO_o_oe(),
    .io_pads_gpioA_o_oval(), .io_pads_gpioA_o_oe(), .io_pads_gpioB_o_oval(), .io_pads_gpioB_o_oe(),
    .io_pads_qspi0_sck_o_oval(), .io_pads_qspi0_cs_0_o_oval(),
    .io_pads_qspi0_dq_0_o_oval(), .io_pads_qspi0_dq_0_o_oe(),
    .io_pads_qspi0_dq_1_o_oval(), .io_pads_qspi0_dq_1_o_oe(),
    .io_pads_qspi0_dq_2_o_oval(), .io_pads_qspi0_dq_2_o_oe(),
    .io_pads_qspi0_dq_3_o_oval(), .io_pads_qspi0_dq_3_o_oe(),
    .io_pads_aon_pmu_padrst_o_oval(), .io_pads_aon_pmu_vddpaden_o_oval()
  );

// Non-synthesizable preload: no force, no changes to live bus timing.
function automatic [63:0] xu_pack_vendor_row;
  input [15:0] a0,a1,a2,a3;
  integer b;
  begin
    for (b=0;b<16;b=b+1)
      xu_pack_vendor_row[4*b +: 4]={a3[b],a2[b],a1[b],a0[b]};
  end
endfunction
task xu_preload_itcm;
  integer row;
  begin
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[0].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[0+4*row+0][0 +: 16],xu_program_words[0+4*row+1][0 +: 16],xu_program_words[0+4*row+2][0 +: 16],xu_program_words[0+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[0].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[0+4*row+0][16 +: 16],xu_program_words[0+4*row+1][16 +: 16],xu_program_words[0+4*row+2][16 +: 16],xu_program_words[0+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[0].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[0+4*row+0][32 +: 16],xu_program_words[0+4*row+1][32 +: 16],xu_program_words[0+4*row+2][32 +: 16],xu_program_words[0+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[0].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[0+4*row+0][48 +: 16],xu_program_words[0+4*row+1][48 +: 16],xu_program_words[0+4*row+2][48 +: 16],xu_program_words[0+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[1].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[1024+4*row+0][0 +: 16],xu_program_words[1024+4*row+1][0 +: 16],xu_program_words[1024+4*row+2][0 +: 16],xu_program_words[1024+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[1].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[1024+4*row+0][16 +: 16],xu_program_words[1024+4*row+1][16 +: 16],xu_program_words[1024+4*row+2][16 +: 16],xu_program_words[1024+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[1].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[1024+4*row+0][32 +: 16],xu_program_words[1024+4*row+1][32 +: 16],xu_program_words[1024+4*row+2][32 +: 16],xu_program_words[1024+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[1].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[1024+4*row+0][48 +: 16],xu_program_words[1024+4*row+1][48 +: 16],xu_program_words[1024+4*row+2][48 +: 16],xu_program_words[1024+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[2].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[2048+4*row+0][0 +: 16],xu_program_words[2048+4*row+1][0 +: 16],xu_program_words[2048+4*row+2][0 +: 16],xu_program_words[2048+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[2].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[2048+4*row+0][16 +: 16],xu_program_words[2048+4*row+1][16 +: 16],xu_program_words[2048+4*row+2][16 +: 16],xu_program_words[2048+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[2].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[2048+4*row+0][32 +: 16],xu_program_words[2048+4*row+1][32 +: 16],xu_program_words[2048+4*row+2][32 +: 16],xu_program_words[2048+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[2].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[2048+4*row+0][48 +: 16],xu_program_words[2048+4*row+1][48 +: 16],xu_program_words[2048+4*row+2][48 +: 16],xu_program_words[2048+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[3].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[3072+4*row+0][0 +: 16],xu_program_words[3072+4*row+1][0 +: 16],xu_program_words[3072+4*row+2][0 +: 16],xu_program_words[3072+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[3].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[3072+4*row+0][16 +: 16],xu_program_words[3072+4*row+1][16 +: 16],xu_program_words[3072+4*row+2][16 +: 16],xu_program_words[3072+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[3].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[3072+4*row+0][32 +: 16],xu_program_words[3072+4*row+1][32 +: 16],xu_program_words[3072+4*row+2][32 +: 16],xu_program_words[3072+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[3].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[3072+4*row+0][48 +: 16],xu_program_words[3072+4*row+1][48 +: 16],xu_program_words[3072+4*row+2][48 +: 16],xu_program_words[3072+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[4].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[4096+4*row+0][0 +: 16],xu_program_words[4096+4*row+1][0 +: 16],xu_program_words[4096+4*row+2][0 +: 16],xu_program_words[4096+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[4].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[4096+4*row+0][16 +: 16],xu_program_words[4096+4*row+1][16 +: 16],xu_program_words[4096+4*row+2][16 +: 16],xu_program_words[4096+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[4].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[4096+4*row+0][32 +: 16],xu_program_words[4096+4*row+1][32 +: 16],xu_program_words[4096+4*row+2][32 +: 16],xu_program_words[4096+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[4].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[4096+4*row+0][48 +: 16],xu_program_words[4096+4*row+1][48 +: 16],xu_program_words[4096+4*row+2][48 +: 16],xu_program_words[4096+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[5].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[5120+4*row+0][0 +: 16],xu_program_words[5120+4*row+1][0 +: 16],xu_program_words[5120+4*row+2][0 +: 16],xu_program_words[5120+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[5].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[5120+4*row+0][16 +: 16],xu_program_words[5120+4*row+1][16 +: 16],xu_program_words[5120+4*row+2][16 +: 16],xu_program_words[5120+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[5].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[5120+4*row+0][32 +: 16],xu_program_words[5120+4*row+1][32 +: 16],xu_program_words[5120+4*row+2][32 +: 16],xu_program_words[5120+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[5].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[5120+4*row+0][48 +: 16],xu_program_words[5120+4*row+1][48 +: 16],xu_program_words[5120+4*row+2][48 +: 16],xu_program_words[5120+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[6].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[6144+4*row+0][0 +: 16],xu_program_words[6144+4*row+1][0 +: 16],xu_program_words[6144+4*row+2][0 +: 16],xu_program_words[6144+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[6].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[6144+4*row+0][16 +: 16],xu_program_words[6144+4*row+1][16 +: 16],xu_program_words[6144+4*row+2][16 +: 16],xu_program_words[6144+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[6].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[6144+4*row+0][32 +: 16],xu_program_words[6144+4*row+1][32 +: 16],xu_program_words[6144+4*row+2][32 +: 16],xu_program_words[6144+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[6].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[6144+4*row+0][48 +: 16],xu_program_words[6144+4*row+1][48 +: 16],xu_program_words[6144+4*row+2][48 +: 16],xu_program_words[6144+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[7].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[7168+4*row+0][0 +: 16],xu_program_words[7168+4*row+1][0 +: 16],xu_program_words[7168+4*row+2][0 +: 16],xu_program_words[7168+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[7].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[7168+4*row+0][16 +: 16],xu_program_words[7168+4*row+1][16 +: 16],xu_program_words[7168+4*row+2][16 +: 16],xu_program_words[7168+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[7].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[7168+4*row+0][32 +: 16],xu_program_words[7168+4*row+1][32 +: 16],xu_program_words[7168+4*row+2][32 +: 16],xu_program_words[7168+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[7].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[7168+4*row+0][48 +: 16],xu_program_words[7168+4*row+1][48 +: 16],xu_program_words[7168+4*row+2][48 +: 16],xu_program_words[7168+4*row+3][48 +: 16]);
  end
endtask
task xu_preload_shared;
  integer row;
  begin
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[0].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[0+4*row+0][0 +: 16],ram[0+4*row+1][0 +: 16],ram[0+4*row+2][0 +: 16],ram[0+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[0].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[0+4*row+0][16 +: 16],ram[0+4*row+1][16 +: 16],ram[0+4*row+2][16 +: 16],ram[0+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[1].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[1024+4*row+0][0 +: 16],ram[1024+4*row+1][0 +: 16],ram[1024+4*row+2][0 +: 16],ram[1024+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[1].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[1024+4*row+0][16 +: 16],ram[1024+4*row+1][16 +: 16],ram[1024+4*row+2][16 +: 16],ram[1024+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[2].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[2048+4*row+0][0 +: 16],ram[2048+4*row+1][0 +: 16],ram[2048+4*row+2][0 +: 16],ram[2048+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[2].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[2048+4*row+0][16 +: 16],ram[2048+4*row+1][16 +: 16],ram[2048+4*row+2][16 +: 16],ram[2048+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[3].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[3072+4*row+0][0 +: 16],ram[3072+4*row+1][0 +: 16],ram[3072+4*row+2][0 +: 16],ram[3072+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[3].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[3072+4*row+0][16 +: 16],ram[3072+4*row+1][16 +: 16],ram[3072+4*row+2][16 +: 16],ram[3072+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[4].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[4096+4*row+0][0 +: 16],ram[4096+4*row+1][0 +: 16],ram[4096+4*row+2][0 +: 16],ram[4096+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[4].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[4096+4*row+0][16 +: 16],ram[4096+4*row+1][16 +: 16],ram[4096+4*row+2][16 +: 16],ram[4096+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[5].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[5120+4*row+0][0 +: 16],ram[5120+4*row+1][0 +: 16],ram[5120+4*row+2][0 +: 16],ram[5120+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[5].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[5120+4*row+0][16 +: 16],ram[5120+4*row+1][16 +: 16],ram[5120+4*row+2][16 +: 16],ram[5120+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[6].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[6144+4*row+0][0 +: 16],ram[6144+4*row+1][0 +: 16],ram[6144+4*row+2][0 +: 16],ram[6144+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[6].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[6144+4*row+0][16 +: 16],ram[6144+4*row+1][16 +: 16],ram[6144+4*row+2][16 +: 16],ram[6144+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[7].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[7168+4*row+0][0 +: 16],ram[7168+4*row+1][0 +: 16],ram[7168+4*row+2][0 +: 16],ram[7168+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[7].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[7168+4*row+0][16 +: 16],ram[7168+4*row+1][16 +: 16],ram[7168+4*row+2][16 +: 16],ram[7168+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[8].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[8192+4*row+0][0 +: 16],ram[8192+4*row+1][0 +: 16],ram[8192+4*row+2][0 +: 16],ram[8192+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[8].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[8192+4*row+0][16 +: 16],ram[8192+4*row+1][16 +: 16],ram[8192+4*row+2][16 +: 16],ram[8192+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[9].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[9216+4*row+0][0 +: 16],ram[9216+4*row+1][0 +: 16],ram[9216+4*row+2][0 +: 16],ram[9216+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[9].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[9216+4*row+0][16 +: 16],ram[9216+4*row+1][16 +: 16],ram[9216+4*row+2][16 +: 16],ram[9216+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[10].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[10240+4*row+0][0 +: 16],ram[10240+4*row+1][0 +: 16],ram[10240+4*row+2][0 +: 16],ram[10240+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[10].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[10240+4*row+0][16 +: 16],ram[10240+4*row+1][16 +: 16],ram[10240+4*row+2][16 +: 16],ram[10240+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[11].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[11264+4*row+0][0 +: 16],ram[11264+4*row+1][0 +: 16],ram[11264+4*row+2][0 +: 16],ram[11264+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[11].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[11264+4*row+0][16 +: 16],ram[11264+4*row+1][16 +: 16],ram[11264+4*row+2][16 +: 16],ram[11264+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[12].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[12288+4*row+0][0 +: 16],ram[12288+4*row+1][0 +: 16],ram[12288+4*row+2][0 +: 16],ram[12288+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[12].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[12288+4*row+0][16 +: 16],ram[12288+4*row+1][16 +: 16],ram[12288+4*row+2][16 +: 16],ram[12288+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[13].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[13312+4*row+0][0 +: 16],ram[13312+4*row+1][0 +: 16],ram[13312+4*row+2][0 +: 16],ram[13312+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[13].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[13312+4*row+0][16 +: 16],ram[13312+4*row+1][16 +: 16],ram[13312+4*row+2][16 +: 16],ram[13312+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[14].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[14336+4*row+0][0 +: 16],ram[14336+4*row+1][0 +: 16],ram[14336+4*row+2][0 +: 16],ram[14336+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[14].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[14336+4*row+0][16 +: 16],ram[14336+4*row+1][16 +: 16],ram[14336+4*row+2][16 +: 16],ram[14336+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[15].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[15360+4*row+0][0 +: 16],ram[15360+4*row+1][0 +: 16],ram[15360+4*row+2][0 +: 16],ram[15360+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[15].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[15360+4*row+0][16 +: 16],ram[15360+4*row+1][16 +: 16],ram[15360+4*row+2][16 +: 16],ram[15360+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[16].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[16384+4*row+0][0 +: 16],ram[16384+4*row+1][0 +: 16],ram[16384+4*row+2][0 +: 16],ram[16384+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[16].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[16384+4*row+0][16 +: 16],ram[16384+4*row+1][16 +: 16],ram[16384+4*row+2][16 +: 16],ram[16384+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[17].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[17408+4*row+0][0 +: 16],ram[17408+4*row+1][0 +: 16],ram[17408+4*row+2][0 +: 16],ram[17408+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[17].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[17408+4*row+0][16 +: 16],ram[17408+4*row+1][16 +: 16],ram[17408+4*row+2][16 +: 16],ram[17408+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[18].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[18432+4*row+0][0 +: 16],ram[18432+4*row+1][0 +: 16],ram[18432+4*row+2][0 +: 16],ram[18432+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[18].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[18432+4*row+0][16 +: 16],ram[18432+4*row+1][16 +: 16],ram[18432+4*row+2][16 +: 16],ram[18432+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[19].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[19456+4*row+0][0 +: 16],ram[19456+4*row+1][0 +: 16],ram[19456+4*row+2][0 +: 16],ram[19456+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[19].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[19456+4*row+0][16 +: 16],ram[19456+4*row+1][16 +: 16],ram[19456+4*row+2][16 +: 16],ram[19456+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[20].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[20480+4*row+0][0 +: 16],ram[20480+4*row+1][0 +: 16],ram[20480+4*row+2][0 +: 16],ram[20480+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[20].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[20480+4*row+0][16 +: 16],ram[20480+4*row+1][16 +: 16],ram[20480+4*row+2][16 +: 16],ram[20480+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[21].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[21504+4*row+0][0 +: 16],ram[21504+4*row+1][0 +: 16],ram[21504+4*row+2][0 +: 16],ram[21504+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[21].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[21504+4*row+0][16 +: 16],ram[21504+4*row+1][16 +: 16],ram[21504+4*row+2][16 +: 16],ram[21504+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[22].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[22528+4*row+0][0 +: 16],ram[22528+4*row+1][0 +: 16],ram[22528+4*row+2][0 +: 16],ram[22528+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[22].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[22528+4*row+0][16 +: 16],ram[22528+4*row+1][16 +: 16],ram[22528+4*row+2][16 +: 16],ram[22528+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[23].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[23552+4*row+0][0 +: 16],ram[23552+4*row+1][0 +: 16],ram[23552+4*row+2][0 +: 16],ram[23552+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[23].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[23552+4*row+0][16 +: 16],ram[23552+4*row+1][16 +: 16],ram[23552+4*row+2][16 +: 16],ram[23552+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[24].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[24576+4*row+0][0 +: 16],ram[24576+4*row+1][0 +: 16],ram[24576+4*row+2][0 +: 16],ram[24576+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[24].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[24576+4*row+0][16 +: 16],ram[24576+4*row+1][16 +: 16],ram[24576+4*row+2][16 +: 16],ram[24576+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[25].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[25600+4*row+0][0 +: 16],ram[25600+4*row+1][0 +: 16],ram[25600+4*row+2][0 +: 16],ram[25600+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[25].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[25600+4*row+0][16 +: 16],ram[25600+4*row+1][16 +: 16],ram[25600+4*row+2][16 +: 16],ram[25600+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[26].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[26624+4*row+0][0 +: 16],ram[26624+4*row+1][0 +: 16],ram[26624+4*row+2][0 +: 16],ram[26624+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[26].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[26624+4*row+0][16 +: 16],ram[26624+4*row+1][16 +: 16],ram[26624+4*row+2][16 +: 16],ram[26624+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[27].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[27648+4*row+0][0 +: 16],ram[27648+4*row+1][0 +: 16],ram[27648+4*row+2][0 +: 16],ram[27648+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[27].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[27648+4*row+0][16 +: 16],ram[27648+4*row+1][16 +: 16],ram[27648+4*row+2][16 +: 16],ram[27648+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[28].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[28672+4*row+0][0 +: 16],ram[28672+4*row+1][0 +: 16],ram[28672+4*row+2][0 +: 16],ram[28672+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[28].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[28672+4*row+0][16 +: 16],ram[28672+4*row+1][16 +: 16],ram[28672+4*row+2][16 +: 16],ram[28672+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[29].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[29696+4*row+0][0 +: 16],ram[29696+4*row+1][0 +: 16],ram[29696+4*row+2][0 +: 16],ram[29696+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[29].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[29696+4*row+0][16 +: 16],ram[29696+4*row+1][16 +: 16],ram[29696+4*row+2][16 +: 16],ram[29696+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[30].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[30720+4*row+0][0 +: 16],ram[30720+4*row+1][0 +: 16],ram[30720+4*row+2][0 +: 16],ram[30720+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[30].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[30720+4*row+0][16 +: 16],ram[30720+4*row+1][16 +: 16],ram[30720+4*row+2][16 +: 16],ram[30720+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[31].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[31744+4*row+0][0 +: 16],ram[31744+4*row+1][0 +: 16],ram[31744+4*row+2][0 +: 16],ram[31744+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[31].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[31744+4*row+0][16 +: 16],ram[31744+4*row+1][16 +: 16],ram[31744+4*row+2][16 +: 16],ram[31744+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[32].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[32768+4*row+0][0 +: 16],ram[32768+4*row+1][0 +: 16],ram[32768+4*row+2][0 +: 16],ram[32768+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[32].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[32768+4*row+0][16 +: 16],ram[32768+4*row+1][16 +: 16],ram[32768+4*row+2][16 +: 16],ram[32768+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[33].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[33792+4*row+0][0 +: 16],ram[33792+4*row+1][0 +: 16],ram[33792+4*row+2][0 +: 16],ram[33792+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[33].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[33792+4*row+0][16 +: 16],ram[33792+4*row+1][16 +: 16],ram[33792+4*row+2][16 +: 16],ram[33792+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[34].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[34816+4*row+0][0 +: 16],ram[34816+4*row+1][0 +: 16],ram[34816+4*row+2][0 +: 16],ram[34816+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[34].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[34816+4*row+0][16 +: 16],ram[34816+4*row+1][16 +: 16],ram[34816+4*row+2][16 +: 16],ram[34816+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[35].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[35840+4*row+0][0 +: 16],ram[35840+4*row+1][0 +: 16],ram[35840+4*row+2][0 +: 16],ram[35840+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[35].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[35840+4*row+0][16 +: 16],ram[35840+4*row+1][16 +: 16],ram[35840+4*row+2][16 +: 16],ram[35840+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[36].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[36864+4*row+0][0 +: 16],ram[36864+4*row+1][0 +: 16],ram[36864+4*row+2][0 +: 16],ram[36864+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[36].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[36864+4*row+0][16 +: 16],ram[36864+4*row+1][16 +: 16],ram[36864+4*row+2][16 +: 16],ram[36864+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[37].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[37888+4*row+0][0 +: 16],ram[37888+4*row+1][0 +: 16],ram[37888+4*row+2][0 +: 16],ram[37888+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[37].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[37888+4*row+0][16 +: 16],ram[37888+4*row+1][16 +: 16],ram[37888+4*row+2][16 +: 16],ram[37888+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[38].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[38912+4*row+0][0 +: 16],ram[38912+4*row+1][0 +: 16],ram[38912+4*row+2][0 +: 16],ram[38912+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[38].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[38912+4*row+0][16 +: 16],ram[38912+4*row+1][16 +: 16],ram[38912+4*row+2][16 +: 16],ram[38912+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[39].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[39936+4*row+0][0 +: 16],ram[39936+4*row+1][0 +: 16],ram[39936+4*row+2][0 +: 16],ram[39936+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[39].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[39936+4*row+0][16 +: 16],ram[39936+4*row+1][16 +: 16],ram[39936+4*row+2][16 +: 16],ram[39936+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[40].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[40960+4*row+0][0 +: 16],ram[40960+4*row+1][0 +: 16],ram[40960+4*row+2][0 +: 16],ram[40960+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[40].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[40960+4*row+0][16 +: 16],ram[40960+4*row+1][16 +: 16],ram[40960+4*row+2][16 +: 16],ram[40960+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[41].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[41984+4*row+0][0 +: 16],ram[41984+4*row+1][0 +: 16],ram[41984+4*row+2][0 +: 16],ram[41984+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[41].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[41984+4*row+0][16 +: 16],ram[41984+4*row+1][16 +: 16],ram[41984+4*row+2][16 +: 16],ram[41984+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[42].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[43008+4*row+0][0 +: 16],ram[43008+4*row+1][0 +: 16],ram[43008+4*row+2][0 +: 16],ram[43008+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[42].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[43008+4*row+0][16 +: 16],ram[43008+4*row+1][16 +: 16],ram[43008+4*row+2][16 +: 16],ram[43008+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[43].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[44032+4*row+0][0 +: 16],ram[44032+4*row+1][0 +: 16],ram[44032+4*row+2][0 +: 16],ram[44032+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[43].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[44032+4*row+0][16 +: 16],ram[44032+4*row+1][16 +: 16],ram[44032+4*row+2][16 +: 16],ram[44032+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[44].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[45056+4*row+0][0 +: 16],ram[45056+4*row+1][0 +: 16],ram[45056+4*row+2][0 +: 16],ram[45056+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[44].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[45056+4*row+0][16 +: 16],ram[45056+4*row+1][16 +: 16],ram[45056+4*row+2][16 +: 16],ram[45056+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[45].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[46080+4*row+0][0 +: 16],ram[46080+4*row+1][0 +: 16],ram[46080+4*row+2][0 +: 16],ram[46080+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[45].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[46080+4*row+0][16 +: 16],ram[46080+4*row+1][16 +: 16],ram[46080+4*row+2][16 +: 16],ram[46080+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[46].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[47104+4*row+0][0 +: 16],ram[47104+4*row+1][0 +: 16],ram[47104+4*row+2][0 +: 16],ram[47104+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[46].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[47104+4*row+0][16 +: 16],ram[47104+4*row+1][16 +: 16],ram[47104+4*row+2][16 +: 16],ram[47104+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[47].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[48128+4*row+0][0 +: 16],ram[48128+4*row+1][0 +: 16],ram[48128+4*row+2][0 +: 16],ram[48128+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[47].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[48128+4*row+0][16 +: 16],ram[48128+4*row+1][16 +: 16],ram[48128+4*row+2][16 +: 16],ram[48128+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[48].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[49152+4*row+0][0 +: 16],ram[49152+4*row+1][0 +: 16],ram[49152+4*row+2][0 +: 16],ram[49152+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[48].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[49152+4*row+0][16 +: 16],ram[49152+4*row+1][16 +: 16],ram[49152+4*row+2][16 +: 16],ram[49152+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[49].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[50176+4*row+0][0 +: 16],ram[50176+4*row+1][0 +: 16],ram[50176+4*row+2][0 +: 16],ram[50176+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[49].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[50176+4*row+0][16 +: 16],ram[50176+4*row+1][16 +: 16],ram[50176+4*row+2][16 +: 16],ram[50176+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[50].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[51200+4*row+0][0 +: 16],ram[51200+4*row+1][0 +: 16],ram[51200+4*row+2][0 +: 16],ram[51200+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[50].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[51200+4*row+0][16 +: 16],ram[51200+4*row+1][16 +: 16],ram[51200+4*row+2][16 +: 16],ram[51200+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[51].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[52224+4*row+0][0 +: 16],ram[52224+4*row+1][0 +: 16],ram[52224+4*row+2][0 +: 16],ram[52224+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[51].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[52224+4*row+0][16 +: 16],ram[52224+4*row+1][16 +: 16],ram[52224+4*row+2][16 +: 16],ram[52224+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[52].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[53248+4*row+0][0 +: 16],ram[53248+4*row+1][0 +: 16],ram[53248+4*row+2][0 +: 16],ram[53248+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[52].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[53248+4*row+0][16 +: 16],ram[53248+4*row+1][16 +: 16],ram[53248+4*row+2][16 +: 16],ram[53248+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[53].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[54272+4*row+0][0 +: 16],ram[54272+4*row+1][0 +: 16],ram[54272+4*row+2][0 +: 16],ram[54272+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[53].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[54272+4*row+0][16 +: 16],ram[54272+4*row+1][16 +: 16],ram[54272+4*row+2][16 +: 16],ram[54272+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[54].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[55296+4*row+0][0 +: 16],ram[55296+4*row+1][0 +: 16],ram[55296+4*row+2][0 +: 16],ram[55296+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[54].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[55296+4*row+0][16 +: 16],ram[55296+4*row+1][16 +: 16],ram[55296+4*row+2][16 +: 16],ram[55296+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[55].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[56320+4*row+0][0 +: 16],ram[56320+4*row+1][0 +: 16],ram[56320+4*row+2][0 +: 16],ram[56320+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[55].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[56320+4*row+0][16 +: 16],ram[56320+4*row+1][16 +: 16],ram[56320+4*row+2][16 +: 16],ram[56320+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[56].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[57344+4*row+0][0 +: 16],ram[57344+4*row+1][0 +: 16],ram[57344+4*row+2][0 +: 16],ram[57344+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[56].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[57344+4*row+0][16 +: 16],ram[57344+4*row+1][16 +: 16],ram[57344+4*row+2][16 +: 16],ram[57344+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[57].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[58368+4*row+0][0 +: 16],ram[58368+4*row+1][0 +: 16],ram[58368+4*row+2][0 +: 16],ram[58368+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[57].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[58368+4*row+0][16 +: 16],ram[58368+4*row+1][16 +: 16],ram[58368+4*row+2][16 +: 16],ram[58368+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[58].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[59392+4*row+0][0 +: 16],ram[59392+4*row+1][0 +: 16],ram[59392+4*row+2][0 +: 16],ram[59392+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[58].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[59392+4*row+0][16 +: 16],ram[59392+4*row+1][16 +: 16],ram[59392+4*row+2][16 +: 16],ram[59392+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[59].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[60416+4*row+0][0 +: 16],ram[60416+4*row+1][0 +: 16],ram[60416+4*row+2][0 +: 16],ram[60416+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[59].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[60416+4*row+0][16 +: 16],ram[60416+4*row+1][16 +: 16],ram[60416+4*row+2][16 +: 16],ram[60416+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[60].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[61440+4*row+0][0 +: 16],ram[61440+4*row+1][0 +: 16],ram[61440+4*row+2][0 +: 16],ram[61440+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[60].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[61440+4*row+0][16 +: 16],ram[61440+4*row+1][16 +: 16],ram[61440+4*row+2][16 +: 16],ram[61440+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[61].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[62464+4*row+0][0 +: 16],ram[62464+4*row+1][0 +: 16],ram[62464+4*row+2][0 +: 16],ram[62464+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[61].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[62464+4*row+0][16 +: 16],ram[62464+4*row+1][16 +: 16],ram[62464+4*row+2][16 +: 16],ram[62464+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[62].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[63488+4*row+0][0 +: 16],ram[63488+4*row+1][0 +: 16],ram[63488+4*row+2][0 +: 16],ram[63488+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[62].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[63488+4*row+0][16 +: 16],ram[63488+4*row+1][16 +: 16],ram[63488+4*row+2][16 +: 16],ram[63488+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[63].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[64512+4*row+0][0 +: 16],ram[64512+4*row+1][0 +: 16],ram[64512+4*row+2][0 +: 16],ram[64512+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[63].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[64512+4*row+0][16 +: 16],ram[64512+4*row+1][16 +: 16],ram[64512+4*row+2][16 +: 16],ram[64512+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[64].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[65536+4*row+0][0 +: 16],ram[65536+4*row+1][0 +: 16],ram[65536+4*row+2][0 +: 16],ram[65536+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[64].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[65536+4*row+0][16 +: 16],ram[65536+4*row+1][16 +: 16],ram[65536+4*row+2][16 +: 16],ram[65536+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[65].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[66560+4*row+0][0 +: 16],ram[66560+4*row+1][0 +: 16],ram[66560+4*row+2][0 +: 16],ram[66560+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[65].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[66560+4*row+0][16 +: 16],ram[66560+4*row+1][16 +: 16],ram[66560+4*row+2][16 +: 16],ram[66560+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[66].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[67584+4*row+0][0 +: 16],ram[67584+4*row+1][0 +: 16],ram[67584+4*row+2][0 +: 16],ram[67584+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[66].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[67584+4*row+0][16 +: 16],ram[67584+4*row+1][16 +: 16],ram[67584+4*row+2][16 +: 16],ram[67584+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[67].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[68608+4*row+0][0 +: 16],ram[68608+4*row+1][0 +: 16],ram[68608+4*row+2][0 +: 16],ram[68608+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[67].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[68608+4*row+0][16 +: 16],ram[68608+4*row+1][16 +: 16],ram[68608+4*row+2][16 +: 16],ram[68608+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[68].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[69632+4*row+0][0 +: 16],ram[69632+4*row+1][0 +: 16],ram[69632+4*row+2][0 +: 16],ram[69632+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[68].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[69632+4*row+0][16 +: 16],ram[69632+4*row+1][16 +: 16],ram[69632+4*row+2][16 +: 16],ram[69632+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[69].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[70656+4*row+0][0 +: 16],ram[70656+4*row+1][0 +: 16],ram[70656+4*row+2][0 +: 16],ram[70656+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[69].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[70656+4*row+0][16 +: 16],ram[70656+4*row+1][16 +: 16],ram[70656+4*row+2][16 +: 16],ram[70656+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[70].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[71680+4*row+0][0 +: 16],ram[71680+4*row+1][0 +: 16],ram[71680+4*row+2][0 +: 16],ram[71680+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[70].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[71680+4*row+0][16 +: 16],ram[71680+4*row+1][16 +: 16],ram[71680+4*row+2][16 +: 16],ram[71680+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[71].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[72704+4*row+0][0 +: 16],ram[72704+4*row+1][0 +: 16],ram[72704+4*row+2][0 +: 16],ram[72704+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[71].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[72704+4*row+0][16 +: 16],ram[72704+4*row+1][16 +: 16],ram[72704+4*row+2][16 +: 16],ram[72704+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[72].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[73728+4*row+0][0 +: 16],ram[73728+4*row+1][0 +: 16],ram[73728+4*row+2][0 +: 16],ram[73728+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[72].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[73728+4*row+0][16 +: 16],ram[73728+4*row+1][16 +: 16],ram[73728+4*row+2][16 +: 16],ram[73728+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[73].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[74752+4*row+0][0 +: 16],ram[74752+4*row+1][0 +: 16],ram[74752+4*row+2][0 +: 16],ram[74752+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[73].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[74752+4*row+0][16 +: 16],ram[74752+4*row+1][16 +: 16],ram[74752+4*row+2][16 +: 16],ram[74752+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[74].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[75776+4*row+0][0 +: 16],ram[75776+4*row+1][0 +: 16],ram[75776+4*row+2][0 +: 16],ram[75776+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[74].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[75776+4*row+0][16 +: 16],ram[75776+4*row+1][16 +: 16],ram[75776+4*row+2][16 +: 16],ram[75776+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[75].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[76800+4*row+0][0 +: 16],ram[76800+4*row+1][0 +: 16],ram[76800+4*row+2][0 +: 16],ram[76800+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[75].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[76800+4*row+0][16 +: 16],ram[76800+4*row+1][16 +: 16],ram[76800+4*row+2][16 +: 16],ram[76800+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[76].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[77824+4*row+0][0 +: 16],ram[77824+4*row+1][0 +: 16],ram[77824+4*row+2][0 +: 16],ram[77824+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[76].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[77824+4*row+0][16 +: 16],ram[77824+4*row+1][16 +: 16],ram[77824+4*row+2][16 +: 16],ram[77824+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[77].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[78848+4*row+0][0 +: 16],ram[78848+4*row+1][0 +: 16],ram[78848+4*row+2][0 +: 16],ram[78848+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[77].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[78848+4*row+0][16 +: 16],ram[78848+4*row+1][16 +: 16],ram[78848+4*row+2][16 +: 16],ram[78848+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[78].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[79872+4*row+0][0 +: 16],ram[79872+4*row+1][0 +: 16],ram[79872+4*row+2][0 +: 16],ram[79872+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[78].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[79872+4*row+0][16 +: 16],ram[79872+4*row+1][16 +: 16],ram[79872+4*row+2][16 +: 16],ram[79872+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[79].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[80896+4*row+0][0 +: 16],ram[80896+4*row+1][0 +: 16],ram[80896+4*row+2][0 +: 16],ram[80896+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[79].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[80896+4*row+0][16 +: 16],ram[80896+4*row+1][16 +: 16],ram[80896+4*row+2][16 +: 16],ram[80896+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[80].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[81920+4*row+0][0 +: 16],ram[81920+4*row+1][0 +: 16],ram[81920+4*row+2][0 +: 16],ram[81920+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[80].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[81920+4*row+0][16 +: 16],ram[81920+4*row+1][16 +: 16],ram[81920+4*row+2][16 +: 16],ram[81920+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[81].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[82944+4*row+0][0 +: 16],ram[82944+4*row+1][0 +: 16],ram[82944+4*row+2][0 +: 16],ram[82944+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[81].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[82944+4*row+0][16 +: 16],ram[82944+4*row+1][16 +: 16],ram[82944+4*row+2][16 +: 16],ram[82944+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[82].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[83968+4*row+0][0 +: 16],ram[83968+4*row+1][0 +: 16],ram[83968+4*row+2][0 +: 16],ram[83968+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[82].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[83968+4*row+0][16 +: 16],ram[83968+4*row+1][16 +: 16],ram[83968+4*row+2][16 +: 16],ram[83968+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[83].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[84992+4*row+0][0 +: 16],ram[84992+4*row+1][0 +: 16],ram[84992+4*row+2][0 +: 16],ram[84992+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[83].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[84992+4*row+0][16 +: 16],ram[84992+4*row+1][16 +: 16],ram[84992+4*row+2][16 +: 16],ram[84992+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[84].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[86016+4*row+0][0 +: 16],ram[86016+4*row+1][0 +: 16],ram[86016+4*row+2][0 +: 16],ram[86016+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[84].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[86016+4*row+0][16 +: 16],ram[86016+4*row+1][16 +: 16],ram[86016+4*row+2][16 +: 16],ram[86016+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[85].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[87040+4*row+0][0 +: 16],ram[87040+4*row+1][0 +: 16],ram[87040+4*row+2][0 +: 16],ram[87040+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[85].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[87040+4*row+0][16 +: 16],ram[87040+4*row+1][16 +: 16],ram[87040+4*row+2][16 +: 16],ram[87040+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[86].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[88064+4*row+0][0 +: 16],ram[88064+4*row+1][0 +: 16],ram[88064+4*row+2][0 +: 16],ram[88064+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[86].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[88064+4*row+0][16 +: 16],ram[88064+4*row+1][16 +: 16],ram[88064+4*row+2][16 +: 16],ram[88064+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[87].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[89088+4*row+0][0 +: 16],ram[89088+4*row+1][0 +: 16],ram[89088+4*row+2][0 +: 16],ram[89088+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[87].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[89088+4*row+0][16 +: 16],ram[89088+4*row+1][16 +: 16],ram[89088+4*row+2][16 +: 16],ram[89088+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[88].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[90112+4*row+0][0 +: 16],ram[90112+4*row+1][0 +: 16],ram[90112+4*row+2][0 +: 16],ram[90112+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[88].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[90112+4*row+0][16 +: 16],ram[90112+4*row+1][16 +: 16],ram[90112+4*row+2][16 +: 16],ram[90112+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[89].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[91136+4*row+0][0 +: 16],ram[91136+4*row+1][0 +: 16],ram[91136+4*row+2][0 +: 16],ram[91136+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[89].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[91136+4*row+0][16 +: 16],ram[91136+4*row+1][16 +: 16],ram[91136+4*row+2][16 +: 16],ram[91136+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[90].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[92160+4*row+0][0 +: 16],ram[92160+4*row+1][0 +: 16],ram[92160+4*row+2][0 +: 16],ram[92160+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[90].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[92160+4*row+0][16 +: 16],ram[92160+4*row+1][16 +: 16],ram[92160+4*row+2][16 +: 16],ram[92160+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[91].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[93184+4*row+0][0 +: 16],ram[93184+4*row+1][0 +: 16],ram[93184+4*row+2][0 +: 16],ram[93184+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[91].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[93184+4*row+0][16 +: 16],ram[93184+4*row+1][16 +: 16],ram[93184+4*row+2][16 +: 16],ram[93184+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[92].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[94208+4*row+0][0 +: 16],ram[94208+4*row+1][0 +: 16],ram[94208+4*row+2][0 +: 16],ram[94208+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[92].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[94208+4*row+0][16 +: 16],ram[94208+4*row+1][16 +: 16],ram[94208+4*row+2][16 +: 16],ram[94208+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[93].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[95232+4*row+0][0 +: 16],ram[95232+4*row+1][0 +: 16],ram[95232+4*row+2][0 +: 16],ram[95232+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[93].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[95232+4*row+0][16 +: 16],ram[95232+4*row+1][16 +: 16],ram[95232+4*row+2][16 +: 16],ram[95232+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[94].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[96256+4*row+0][0 +: 16],ram[96256+4*row+1][0 +: 16],ram[96256+4*row+2][0 +: 16],ram[96256+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[94].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[96256+4*row+0][16 +: 16],ram[96256+4*row+1][16 +: 16],ram[96256+4*row+2][16 +: 16],ram[96256+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[95].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[97280+4*row+0][0 +: 16],ram[97280+4*row+1][0 +: 16],ram[97280+4*row+2][0 +: 16],ram[97280+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[95].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[97280+4*row+0][16 +: 16],ram[97280+4*row+1][16 +: 16],ram[97280+4*row+2][16 +: 16],ram[97280+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[96].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[98304+4*row+0][0 +: 16],ram[98304+4*row+1][0 +: 16],ram[98304+4*row+2][0 +: 16],ram[98304+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[96].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[98304+4*row+0][16 +: 16],ram[98304+4*row+1][16 +: 16],ram[98304+4*row+2][16 +: 16],ram[98304+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[97].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[99328+4*row+0][0 +: 16],ram[99328+4*row+1][0 +: 16],ram[99328+4*row+2][0 +: 16],ram[99328+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[97].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[99328+4*row+0][16 +: 16],ram[99328+4*row+1][16 +: 16],ram[99328+4*row+2][16 +: 16],ram[99328+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[98].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[100352+4*row+0][0 +: 16],ram[100352+4*row+1][0 +: 16],ram[100352+4*row+2][0 +: 16],ram[100352+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[98].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[100352+4*row+0][16 +: 16],ram[100352+4*row+1][16 +: 16],ram[100352+4*row+2][16 +: 16],ram[100352+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[99].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[101376+4*row+0][0 +: 16],ram[101376+4*row+1][0 +: 16],ram[101376+4*row+2][0 +: 16],ram[101376+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[99].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[101376+4*row+0][16 +: 16],ram[101376+4*row+1][16 +: 16],ram[101376+4*row+2][16 +: 16],ram[101376+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[100].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[102400+4*row+0][0 +: 16],ram[102400+4*row+1][0 +: 16],ram[102400+4*row+2][0 +: 16],ram[102400+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[100].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[102400+4*row+0][16 +: 16],ram[102400+4*row+1][16 +: 16],ram[102400+4*row+2][16 +: 16],ram[102400+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[101].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[103424+4*row+0][0 +: 16],ram[103424+4*row+1][0 +: 16],ram[103424+4*row+2][0 +: 16],ram[103424+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[101].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[103424+4*row+0][16 +: 16],ram[103424+4*row+1][16 +: 16],ram[103424+4*row+2][16 +: 16],ram[103424+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[102].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[104448+4*row+0][0 +: 16],ram[104448+4*row+1][0 +: 16],ram[104448+4*row+2][0 +: 16],ram[104448+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[102].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[104448+4*row+0][16 +: 16],ram[104448+4*row+1][16 +: 16],ram[104448+4*row+2][16 +: 16],ram[104448+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[103].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[105472+4*row+0][0 +: 16],ram[105472+4*row+1][0 +: 16],ram[105472+4*row+2][0 +: 16],ram[105472+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[103].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[105472+4*row+0][16 +: 16],ram[105472+4*row+1][16 +: 16],ram[105472+4*row+2][16 +: 16],ram[105472+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[104].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[106496+4*row+0][0 +: 16],ram[106496+4*row+1][0 +: 16],ram[106496+4*row+2][0 +: 16],ram[106496+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[104].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[106496+4*row+0][16 +: 16],ram[106496+4*row+1][16 +: 16],ram[106496+4*row+2][16 +: 16],ram[106496+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[105].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[107520+4*row+0][0 +: 16],ram[107520+4*row+1][0 +: 16],ram[107520+4*row+2][0 +: 16],ram[107520+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[105].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[107520+4*row+0][16 +: 16],ram[107520+4*row+1][16 +: 16],ram[107520+4*row+2][16 +: 16],ram[107520+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[106].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[108544+4*row+0][0 +: 16],ram[108544+4*row+1][0 +: 16],ram[108544+4*row+2][0 +: 16],ram[108544+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[106].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[108544+4*row+0][16 +: 16],ram[108544+4*row+1][16 +: 16],ram[108544+4*row+2][16 +: 16],ram[108544+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[107].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[109568+4*row+0][0 +: 16],ram[109568+4*row+1][0 +: 16],ram[109568+4*row+2][0 +: 16],ram[109568+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[107].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[109568+4*row+0][16 +: 16],ram[109568+4*row+1][16 +: 16],ram[109568+4*row+2][16 +: 16],ram[109568+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[108].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[110592+4*row+0][0 +: 16],ram[110592+4*row+1][0 +: 16],ram[110592+4*row+2][0 +: 16],ram[110592+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[108].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[110592+4*row+0][16 +: 16],ram[110592+4*row+1][16 +: 16],ram[110592+4*row+2][16 +: 16],ram[110592+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[109].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[111616+4*row+0][0 +: 16],ram[111616+4*row+1][0 +: 16],ram[111616+4*row+2][0 +: 16],ram[111616+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[109].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[111616+4*row+0][16 +: 16],ram[111616+4*row+1][16 +: 16],ram[111616+4*row+2][16 +: 16],ram[111616+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[110].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[112640+4*row+0][0 +: 16],ram[112640+4*row+1][0 +: 16],ram[112640+4*row+2][0 +: 16],ram[112640+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[110].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[112640+4*row+0][16 +: 16],ram[112640+4*row+1][16 +: 16],ram[112640+4*row+2][16 +: 16],ram[112640+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[111].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[113664+4*row+0][0 +: 16],ram[113664+4*row+1][0 +: 16],ram[113664+4*row+2][0 +: 16],ram[113664+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[111].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[113664+4*row+0][16 +: 16],ram[113664+4*row+1][16 +: 16],ram[113664+4*row+2][16 +: 16],ram[113664+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[112].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[114688+4*row+0][0 +: 16],ram[114688+4*row+1][0 +: 16],ram[114688+4*row+2][0 +: 16],ram[114688+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[112].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[114688+4*row+0][16 +: 16],ram[114688+4*row+1][16 +: 16],ram[114688+4*row+2][16 +: 16],ram[114688+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[113].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[115712+4*row+0][0 +: 16],ram[115712+4*row+1][0 +: 16],ram[115712+4*row+2][0 +: 16],ram[115712+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[113].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[115712+4*row+0][16 +: 16],ram[115712+4*row+1][16 +: 16],ram[115712+4*row+2][16 +: 16],ram[115712+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[114].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[116736+4*row+0][0 +: 16],ram[116736+4*row+1][0 +: 16],ram[116736+4*row+2][0 +: 16],ram[116736+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[114].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[116736+4*row+0][16 +: 16],ram[116736+4*row+1][16 +: 16],ram[116736+4*row+2][16 +: 16],ram[116736+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[115].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[117760+4*row+0][0 +: 16],ram[117760+4*row+1][0 +: 16],ram[117760+4*row+2][0 +: 16],ram[117760+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[115].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[117760+4*row+0][16 +: 16],ram[117760+4*row+1][16 +: 16],ram[117760+4*row+2][16 +: 16],ram[117760+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[116].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[118784+4*row+0][0 +: 16],ram[118784+4*row+1][0 +: 16],ram[118784+4*row+2][0 +: 16],ram[118784+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[116].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[118784+4*row+0][16 +: 16],ram[118784+4*row+1][16 +: 16],ram[118784+4*row+2][16 +: 16],ram[118784+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[117].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[119808+4*row+0][0 +: 16],ram[119808+4*row+1][0 +: 16],ram[119808+4*row+2][0 +: 16],ram[119808+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[117].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[119808+4*row+0][16 +: 16],ram[119808+4*row+1][16 +: 16],ram[119808+4*row+2][16 +: 16],ram[119808+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[118].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[120832+4*row+0][0 +: 16],ram[120832+4*row+1][0 +: 16],ram[120832+4*row+2][0 +: 16],ram[120832+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[118].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[120832+4*row+0][16 +: 16],ram[120832+4*row+1][16 +: 16],ram[120832+4*row+2][16 +: 16],ram[120832+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[119].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[121856+4*row+0][0 +: 16],ram[121856+4*row+1][0 +: 16],ram[121856+4*row+2][0 +: 16],ram[121856+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[119].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[121856+4*row+0][16 +: 16],ram[121856+4*row+1][16 +: 16],ram[121856+4*row+2][16 +: 16],ram[121856+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[120].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[122880+4*row+0][0 +: 16],ram[122880+4*row+1][0 +: 16],ram[122880+4*row+2][0 +: 16],ram[122880+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[120].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[122880+4*row+0][16 +: 16],ram[122880+4*row+1][16 +: 16],ram[122880+4*row+2][16 +: 16],ram[122880+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[121].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[123904+4*row+0][0 +: 16],ram[123904+4*row+1][0 +: 16],ram[123904+4*row+2][0 +: 16],ram[123904+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[121].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[123904+4*row+0][16 +: 16],ram[123904+4*row+1][16 +: 16],ram[123904+4*row+2][16 +: 16],ram[123904+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[122].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[124928+4*row+0][0 +: 16],ram[124928+4*row+1][0 +: 16],ram[124928+4*row+2][0 +: 16],ram[124928+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[122].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[124928+4*row+0][16 +: 16],ram[124928+4*row+1][16 +: 16],ram[124928+4*row+2][16 +: 16],ram[124928+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[123].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[125952+4*row+0][0 +: 16],ram[125952+4*row+1][0 +: 16],ram[125952+4*row+2][0 +: 16],ram[125952+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[123].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[125952+4*row+0][16 +: 16],ram[125952+4*row+1][16 +: 16],ram[125952+4*row+2][16 +: 16],ram[125952+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[124].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[126976+4*row+0][0 +: 16],ram[126976+4*row+1][0 +: 16],ram[126976+4*row+2][0 +: 16],ram[126976+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[124].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[126976+4*row+0][16 +: 16],ram[126976+4*row+1][16 +: 16],ram[126976+4*row+2][16 +: 16],ram[126976+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[125].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[128000+4*row+0][0 +: 16],ram[128000+4*row+1][0 +: 16],ram[128000+4*row+2][0 +: 16],ram[128000+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[125].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[128000+4*row+0][16 +: 16],ram[128000+4*row+1][16 +: 16],ram[128000+4*row+2][16 +: 16],ram[128000+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[126].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[129024+4*row+0][0 +: 16],ram[129024+4*row+1][0 +: 16],ram[129024+4*row+2][0 +: 16],ram[129024+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[126].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[129024+4*row+0][16 +: 16],ram[129024+4*row+1][16 +: 16],ram[129024+4*row+2][16 +: 16],ram[129024+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[127].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[130048+4*row+0][0 +: 16],ram[130048+4*row+1][0 +: 16],ram[130048+4*row+2][0 +: 16],ram[130048+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[127].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[130048+4*row+0][16 +: 16],ram[130048+4*row+1][16 +: 16],ram[130048+4*row+2][16 +: 16],ram[130048+4*row+3][16 +: 16]);
  end
endtask

  task load_layer(input integer index);
    string directory;
    integer i;
    begin
      directory = $sformatf("%s/layer_%02d/", vectors, index);
      $readmemh({directory,"x.mem"}, x);
      $readmemh({directory,"w.mem"}, w);
      $readmemh({directory,"bias.mem"}, bias);
      $readmemh({directory,"y.mem"}, golden);
      for (i=0; i<6336; i=i+1) ram[i] = {16'b0,x[i]};
      for (i=0; i<16384; i=i+1) ram['h8000/4+i] = {16'b0,w[i]};
      for (i=0; i<256; i=i+1) begin
        ram['h18000/4+2*i] = bias[i][31:0];
        ram['h18000/4+2*i+1] = {{24{bias[i][39]}},bias[i][39:32]};
      end
      // Poison output memory on every layer; no result survives as evidence.
      for (i=0; i<50688; i=i+1) ram[YOFF/4+i] = 32'hdeadbeef;
      xu_preload_shared();
      writes = 0; first_cycle = -1; final_write_pending = 0;
      reset_performance();
    end
  endtask

  initial begin : initialize
    integer i;
    if (!$value$plusargs("TESTCASE=%s",testcase) ||
        !$value$plusargs("VECTORS=%s",vectors) ||
        !$value$plusargs("TASKS=%d",tasks)) $fatal(1,"missing plusargs");
    if (tasks < 1 || tasks > 12) $fatal(1,"invalid task count");
    if (!$value$plusargs("MAX_CYCLES=%d",max_cycles)) max_cycles=200000000;
    #1; // Finish vendor initialization before the first HF edge.
    for (i=0; i<65536; i=i+1) program_bytes[i]=0;
    $readmemh({testcase,".verilog"},program_bytes);
    for (i=0; i<8192; i=i+1)
      xu_program_words[i] = {program_bytes[8*i+7],program_bytes[8*i+6],
        program_bytes[8*i+5],program_bytes[8*i+4],program_bytes[8*i+3],
        program_bytes[8*i+2],program_bytes[8*i+1],program_bytes[8*i]};
    xu_preload_itcm();
    ram[HOST/4]=tasks;
    load_layer(0);
    if ($value$plusargs("DUMPWAVE=%d",dumpwave) && dumpwave) begin
      $dumpfile("tb_accel_soc.vcd");
      if (dumpwave==2) begin
        $dumpvars(0,dut);
        $dumpoff;
      end else $dumpvars(0,tb_xu_soc_ppa);
    end
    #(120-$realtime) rst_n=1;
  end

  always @(posedge clk) begin : memory_and_scoreboard
    integer offset, word_index;
    reg [63:0] expected;
    cycles <= cycles+1;
    if (cycles>0 && cycles%1000000==0) begin
      $display("PPA_PROGRESS cycles=%0d layer=%0d writes=%0d completed=%0d",cycles,layer,writes,completed);
      $fflush();
    end
    if (cycles > max_cycles) $fatal(1,"SoC timeout layer=%0d writes=%0d",layer,writes);
    if (rst_n) begin
      observe_performance();
      // A response must correspond to exactly one unretired shared-memory command.
      if (rsp_valid && outstanding != 1) $fatal(1,"orphan shared response");
      if (rsp_valid && rsp_ready) outstanding=outstanding-1;
      if (cmd_valid && cmd_ready) outstanding=outstanding+1;
      if (outstanding<0 || outstanding>1) $fatal(1,"shared outstanding count");
      if (rsp_valid && rsp_ready && final_write_pending) begin
        last_cycle=cycles;
        final_write_pending=0;
      end
      if (rsp_valid && rsp_err) $fatal(1,"shared endpoint error");
      if (cmd_ready !== ((!rsp_valid || rsp_ready) && (cycles % 7 != 0)))
        $fatal(1,"shared endpoint backpressure phase differs cycle=%0d",cycles);
      if (cmd_ready) begin
        if (cmd_valid) begin
          if (cmd_addr < BASE || cmd_addr >= BASE+'h80000 || cmd_addr[1:0]!=0)
            $fatal(1,"invalid shared address %h",cmd_addr);
          offset=cmd_addr-BASE;
          word_index=offset/4;
          if (cmd_read) begin
            if (offset < 'h18800 && first_cycle<0) first_cycle=cycles;
          end else begin
            if (cmd_wmask != 4'hf) $fatal(1,"partial shared write");
            if (offset>=YOFF && offset<YOFF+50688*4) begin
              if (offset != YOFF+writes*4) $fatal(1,"write order %h index %0d",offset,writes);
              expected={{16{golden[writes/2][47]}},golden[writes/2]};
              if (cmd_wdata !== (writes%2 ? expected[63:32] : expected[31:0]))
                $fatal(1,"result mismatch layer=%0d word=%0d got=%h expected=%h",
                  layer,writes,cmd_wdata,writes%2 ? expected[63:32] : expected[31:0]);
              ram[word_index]=cmd_wdata;
              writes=writes+1;
              if (writes==50688) final_write_pending=1;
            end else if (offset==HOST+8) firmware_cycles=cmd_wdata;
            else if (offset==HOST+4) begin
              if (cmd_wdata!=layer+1 || writes!=50688 || final_write_pending || first_cycle<0)
                $fatal(1,"premature or incorrect writeback ACK");
              $display("TASK_PASS layer=%0d outputs=25344 writes=50688 cycles=%0d firmware_cycles=%0d",
                layer,last_cycle-first_cycle+1,firmware_cycles);
              report_performance();
              $fflush();
              completed=completed+1;
              layer=layer+1;
              if (layer<tasks) load_layer(layer);
            end else $fatal(1,"unexpected shared write %h",cmd_addr);
          end
        end
      end
      if (`EXU.u_e203_exu_commit.alu_cmt_i_valid && `EXU.u_e203_exu_commit.alu_cmt_i_pc==32'h80000086) begin
        if (`EXU.u_e203_exu_regfile.rf_r[3]!=1 || completed!=tasks)
          $fatal(1,"firmware failure gp=%0d completed=%0d",`EXU.u_e203_exu_regfile.rf_r[3],completed);
        $display("SOC_PASS tasks=%0d outputs=%0d writes=%0d",completed,completed*25344,completed*50688);
        $finish;
      end
    end
  end
endmodule
