`include "e203_defines.v"
module tb_accel_soc;
  reg clk = 0, lfclk = 0, rst_n = 0;
  always #2 clk = ~clk;
  always #33 lfclk = ~lfclk;
  wire cmd_valid, cmd_read, cmd_ready, rsp_ready;
  wire [31:0] cmd_addr, cmd_wdata;
  wire [3:0] cmd_wmask;
  reg rsp_valid = 0;
  reg [31:0] rsp_rdata = 0;
  reg [31:0] ram [0:131071]; // Development shared SRAM: exactly 512 KiB.
  reg [15:0] x [0:6335], w [0:16383];
  reg [39:0] bias [0:255];
  reg [47:0] golden [0:25343];
  reg [7:0] program_bytes [0:65535];
  string testcase, vectors;
  integer tasks, layer = 0, completed = 0, writes = 0;
  integer cycles = 0, first_cycle = -1, last_cycle = 0;
  integer max_cycles, firmware_cycles = 0;
  integer outstanding = 0;
  reg final_write_pending = 0;
  integer dumpwave;
  localparam BASE = 32'ha0000000, YOFF = 32'h20000, HOST = 32'h7f000;

  // Backpressure exercises CPU/bus waits; responses remain stable until accepted.
  assign cmd_ready = (!rsp_valid || rsp_ready) && (cycles % 7 != 0);
  `define CPU dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top
  `define EXU `CPU.u_e203_cpu.u_e203_core.u_e203_exu
  `define ITCM `CPU.u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram
  `define ACCEL dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.u_accel_icb_slave

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
  integer perf_result_legacy, perf_result_packed, perf_result_logical;
  reg [15:0] perf_result_seen, perf_result_pending_mask;
  reg perf_result_pending, perf_result_pending_packed;
  reg [31:0] perf_result_expected;

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
      perf_result_legacy=0; perf_result_packed=0; perf_result_logical=0;
      perf_result_seen=0; perf_result_pending=0; perf_result_pending_mask=0;
      perf_result_pending_packed=0; perf_result_expected=0;
    end
  endtask

  // Observe each returned logical word independently of the firmware's schedule.
  // Paired-HI covers two HI16 words, never two signs or two FIFO heads at once.
  task observe_result_reads;
    integer lane, index;
    reg [15:0] mask;
    begin
      if (perf_result_pending) begin
        if (!`ACCEL.rsp_valid || `ACCEL.rsp_err ||
            `ACCEL.rsp_rdata!==perf_result_expected)
          $fatal(1,"owned result response changed or differs from integer golden");
        if (`ACCEL.rsp_ready) begin
          perf_result_seen=perf_result_seen | perf_result_pending_mask;
          if (perf_result_pending_packed) begin
            perf_result_packed=perf_result_packed+1;
            perf_result_logical=perf_result_logical+2;
          end else begin
            perf_result_legacy=perf_result_legacy+1;
            perf_result_logical=perf_result_logical+1;
          end
          perf_result_pending=0;
        end
      end
      if (`ACCEL.row_pop) begin
        if (perf_result_seen!==16'hffff || perf_result_pending)
          $fatal(1,"POP retired before all owned logical result words returned");
        perf_result_seen=0;
      end
      if (`ACCEL.row_active && `ACCEL.cmd_valid && `ACCEL.cmd_ready &&
          `ACCEL.cmd_read &&
          ((`ACCEL.cmd_addr[11:0]>=12'h100 && `ACCEL.cmd_addr[11:0]<=12'h13c) ||
           (`ACCEL.cmd_addr[11:0]>=12'h140 && `ACCEL.cmd_addr[11:0]<=12'h14c))) begin
        if (!`ACCEL.row_valid || `ACCEL.row_pop || perf_result_pending ||
            `ACCEL.cmd_addr[1:0]!=0)
          $fatal(1,"ambiguous or unaligned owned result read");
        lane=`ACCEL.cmd_addr[5:3];
        perf_result_pending_packed=`ACCEL.cmd_addr[11:0]>=12'h140;
        if (perf_result_pending_packed) lane=2*`ACCEL.cmd_addr[3:2];
        index=(perf_auto_rows-1)*256+`ACCEL.row_group*8+lane;
        if (perf_result_pending_packed) begin
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
      // Match the existing inclusive first-input/final-Y-response interval.
      in_window=perf_active || (first_cycle<0 && shared_accept && cmd_read &&
                               cmd_addr>=BASE && cmd_addr<BASE+'h18800);
      if (dumpwave==2 && !perf_active && in_window) begin
        $dumpon;
        $display("ACTIVITY_BEGIN layer=%0d time=%0t",layer,$time);
      end
      if (in_window) begin
        perf_active=1;
        observe_result_reads();
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
             (`ACCEL.cmd_addr[11:0]>=12'h100 && `ACCEL.cmd_addr[11:0]<=12'h14c))) begin
          phase_now=PERF_WRITEBACK; phase_next=PERF_WRITEBACK;
        end
        if (start_accept || row_start_accept) begin
          phase_now=PERF_COMPUTE; phase_next=PERF_COMPUTE;
        end
        if (mmio_accept && `ACCEL.cmd_read && `ACCEL.cmd_addr[11:0]==12'h0c4) begin
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
          cmd_addr<BASE+YOFF+50688*4 && cmd_addr[5:0]==6'h3c;
    end
  endtask

  task report_performance;
    begin
      if (perf_cycles!=last_cycle-first_cycle+1 ||
          perf_w_load+perf_x_load+perf_bias_load+perf_compute_wait+
          perf_writeback+perf_other!=perf_cycles)
        $fatal(1,"performance interval or phase sum mismatch");
      if (perf_auto_rows!=0) begin
        if (perf_auto_rows!=99 || perf_auto_pops!=3168 || `ACCEL.row_active ||
            `ACCEL.row_retired!=32 || `ACCEL.row_produced!=32 || `ACCEL.row_count!=0 ||
            perf_auto_overlap==0)
          $fatal(1,"autonomous row/POP retirement or overlap contract mismatch");
        $display("AUTO_TASK layer=%0d rows=%0d pops_retired=%0d compute_writeback_overlap=%0d fifo_full_wait=%0d",
          layer,perf_auto_rows,perf_auto_pops,perf_auto_overlap,perf_auto_full);
        if (perf_result_logical!=50688 || perf_result_seen || perf_result_pending)
          $fatal(1,"incomplete logical FIFO results at final Y response retirement");
        $display("RESULT_TASK layer=%0d legacy_words=%0d packed_words=%0d logical_words=%0d",
          layer,perf_result_legacy,perf_result_packed,perf_result_logical);
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
      for (i=0; i<6336; i=i+1) ram[i] = {16'b0,x[i]};
      for (i=0; i<16384; i=i+1) ram['h8000/4+i] = {16'b0,w[i]};
      for (i=0; i<256; i=i+1) begin
        ram['h18000/4+2*i] = bias[i][31:0];
        ram['h18000/4+2*i+1] = {{24{bias[i][39]}},bias[i][39:32]};
      end
      // Poison output memory on every layer; no result survives as evidence.
      for (i=0; i<50688; i=i+1) ram[YOFF/4+i] = 32'hdeadbeef;
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
  end

  always @(posedge clk) begin : memory_and_scoreboard
    integer offset, word_index;
    reg [63:0] expected;
    cycles <= cycles+1;
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
