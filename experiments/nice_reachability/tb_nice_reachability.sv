`include "e203_defines.v"
module tb_nice_reachability;
  reg clk = 0, lfclk = 0, rst_n = 0;
  always #2 clk = ~clk;
  always #33 lfclk = ~lfclk;
  wire cmd_valid, cmd_ready, cmd_read, rsp_ready;
  wire [31:0] cmd_addr, cmd_wdata;
  wire [3:0] cmd_wmask;
  reg rsp_valid = 0;
  reg [31:0] rsp_rdata = 0;
  reg [31:0] ram [0:131071];
  reg [7:0] program_bytes [0:65535];
  string testcase;
  integer backpressure = 1, max_cycles = 100000, dumpwave = 0;
  integer cycles = 0, ram_cmd_wait = 0, ram_rsp_wait = 0, ram_serial = 0;
  reg ram_pending = 0;
  reg [31:0] ram_pending_data = 0;
  reg ram_pending_nice = 0;
  integer ram_commands = 0, ram_responses = 0;
  integer nice_requests = 0, nice_responses = 0;
  integer nice_commands = 0, nice_bus_responses = 0;
  integer nice_endpoint_commands = 0, nice_endpoint_responses = 0;
  integer nice_ram_reads = 0, nice_ram_writes = 0;
  integer nice_mmio_reads = 0, nice_mmio_writes = 0;
  integer nice_ram_cmd_stall = 0, nice_ram_rsp_delay = 0;
  integer nice_cmd_stall = 0, nice_rsp_hold_cycles = 0;
  integer ram_rsp_hold_cycles = 0, mmio_rsp_hold_cycles = 0;
  integer instruction_commands = 0, instruction_responses = 0, instruction_cycle = 0;
  integer pending_sequence = 0;
  reg instruction_active = 0, nice_bus_pending = 0;
  reg nice_endpoint_seen = 0, nice_endpoint_done = 0;
  reg [31:0] pending_addr = 0, pending_data = 0;
  reg pending_read = 0;
  reg mmio_pending = 0, mmio_pending_nice = 0, mmio_pending_read = 0;
  reg [31:0] mmio_pending_addr = 0;
  reg ram_endpoint_pending = 0, ram_endpoint_nice = 0, ram_endpoint_read = 0;
  reg [31:0] ram_endpoint_addr = 0;
  reg [2:0] src_initialized = 0, dst0_poisoned = 0, dst1_poisoned = 0;
  reg [2:0] dst0_written = 0, dst1_written = 0;
  reg [2:0] dst0_cpu_checked = 0, dst1_cpu_checked = 0, mmio_cpu_checked = 0;
  localparam [31:0] BASE = 32'ha0000000, SRC = 32'ha0040000;
  localparam [31:0] DST0 = 32'ha0040040, DST1 = 32'ha0040080;
  localparam [31:0] MMIO = 32'h10042014, POISON = 32'hdeadbeef;

  `define CPU dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top
  `define CORE `CPU.u_e203_cpu.u_e203_core
  `define EXU `CORE.u_e203_exu
  `define NICE `CPU.u_e203_cpu.u_e203_nice_core
  `define LSU `CORE.u_e203_lsu.u_e203_lsu_ctrl
  `define ACCEL dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.u_accel_icb_slave
  `define ITCM `CPU.u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram

  // Every external command waits two cycles in the reproducible pressure run.
  // Responses are registered and delayed, never returned in the command cycle.
  assign cmd_ready = !ram_pending && !rsp_valid &&
                     (!backpressure || ram_cmd_wait >= 2);

  wire nice_cmd_accept = `NICE.nice_icb_cmd_valid && `NICE.nice_icb_cmd_ready;
  wire nice_rsp_accept = `NICE.nice_icb_rsp_valid && `NICE.nice_icb_rsp_ready;
  wire mmio_cmd_accept = `ACCEL.cmd_valid && `ACCEL.cmd_ready;
  wire mmio_rsp_accept = `ACCEL.rsp_valid && `ACCEL.rsp_ready;
  wire [66:0] nice_cmd_payload = {`NICE.nice_icb_cmd_addr, `NICE.nice_icb_cmd_read,
                                 `NICE.nice_icb_cmd_wdata, `NICE.nice_icb_cmd_size};
  wire [32:0] nice_rsp_payload = {`NICE.nice_icb_rsp_err, `NICE.nice_icb_rsp_rdata};
  wire [95:0] request_payload = {`NICE.nice_req_inst, `NICE.nice_req_rs1, `NICE.nice_req_rs2};
  wire [32:0] completion_payload = {`NICE.nice_rsp_err, `NICE.nice_rsp_rdat};
  wire [68:0] ram_cmd_payload = {cmd_addr, cmd_read, cmd_wdata, cmd_wmask};
  wire [68:0] mmio_cmd_payload = {`ACCEL.cmd_addr, `ACCEL.cmd_read,
                                 `ACCEL.cmd_wdata, `ACCEL.cmd_wmask};
  wire [32:0] mmio_rsp_payload = {`ACCEL.rsp_err, `ACCEL.rsp_rdata};
  reg hold_nice_cmd = 0, hold_nice_rsp = 0, hold_request = 0, hold_completion = 0;
  reg hold_ram_cmd = 0, hold_ram_rsp = 0, hold_mmio_cmd = 0, hold_mmio_rsp = 0;
  reg [66:0] saved_nice_cmd;
  reg [32:0] saved_nice_rsp, saved_completion, saved_mmio_rsp;
  reg [95:0] saved_request;
  reg [68:0] saved_ram_cmd, saved_mmio_cmd;
  reg [31:0] saved_ram_rsp;

  function automatic [31:0] pattern(input integer lane);
    case (lane)
      0: pattern = 32'd3;
      1: pattern = 32'h0000a55a;
      2: pattern = 32'd5;
      default: pattern = 32'hxxxxxxxx;
    endcase
  endfunction

  function automatic [31:0] instruction_base(input integer index);
    case (index)
      0: instruction_base = SRC;
      1: instruction_base = DST0;
      2, 3: instruction_base = MMIO;
      4: instruction_base = DST1;
      default: instruction_base = 32'hxxxxxxxx;
    endcase
  endfunction

  function automatic instruction_read(input integer index);
    instruction_read = index == 0 || index == 3;
  endfunction

  task check_holds;
    begin
      if (hold_request && (`NICE.nice_req_valid !== 1'b1 || request_payload !== saved_request))
        $fatal(1,"NICE instruction request changed under backpressure");
      if (hold_completion && (`NICE.nice_rsp_valid !== 1'b1 || completion_payload !== saved_completion))
        $fatal(1,"NICE instruction completion was lost or changed under backpressure");
      if (hold_nice_cmd && (`NICE.nice_icb_cmd_valid !== 1'b1 || nice_cmd_payload !== saved_nice_cmd)) begin
        $display("[DEBUG-NICE] event=hold_previous cycle=%0d valid=1 ready=0 addr=%h read=%b data=%h size=%b",
                 cycles-1,saved_nice_cmd[66:35],saved_nice_cmd[34],
                 saved_nice_cmd[33:2],saved_nice_cmd[1:0]);
        $display("[DEBUG-NICE] event=hold_current cycle=%0d valid=%b ready=%b addr=%h read=%b data=%h size=%b commands=%0d responses=%0d inst_commands=%0d inst_responses=%0d bus_rsp_valid=%b bus_rsp_ready=%b bus_rsp_data=%h bus_rsp_err=%b",
                 cycles,`NICE.nice_icb_cmd_valid,`NICE.nice_icb_cmd_ready,
                 `NICE.nice_icb_cmd_addr,`NICE.nice_icb_cmd_read,`NICE.nice_icb_cmd_wdata,
                 `NICE.nice_icb_cmd_size,
                 nice_commands,nice_bus_responses,instruction_commands,instruction_responses,
                 `NICE.nice_icb_rsp_valid,`NICE.nice_icb_rsp_ready,
                 `NICE.nice_icb_rsp_rdata,`NICE.nice_icb_rsp_err);
        $fatal(1,"NICE memory command changed under backpressure");
      end
      if (hold_nice_rsp && (`NICE.nice_icb_rsp_valid !== 1'b1 || nice_rsp_payload !== saved_nice_rsp))
        $fatal(1,"NICE memory response changed under backpressure");
      if (hold_ram_cmd && (cmd_valid !== 1'b1 || ram_cmd_payload !== saved_ram_cmd))
        $fatal(1,"external RAM command changed under backpressure");
      if (hold_ram_rsp && (rsp_valid !== 1'b1 || rsp_rdata !== saved_ram_rsp))
        $fatal(1,"external RAM response changed under backpressure");
      if (hold_mmio_cmd && (`ACCEL.cmd_valid !== 1'b1 || mmio_cmd_payload !== saved_mmio_cmd))
        $fatal(1,"real accelerator command changed under backpressure");
      if (hold_mmio_rsp && (`ACCEL.rsp_valid !== 1'b1 || mmio_rsp_payload !== saved_mmio_rsp))
        $fatal(1,"real accelerator response changed under backpressure");
      hold_request = `NICE.nice_req_valid && !`NICE.nice_req_ready;
      hold_completion = `NICE.nice_rsp_valid && !`NICE.nice_rsp_ready;
      hold_nice_cmd = `NICE.nice_icb_cmd_valid && !`NICE.nice_icb_cmd_ready;
      hold_nice_rsp = `NICE.nice_icb_rsp_valid && !`NICE.nice_icb_rsp_ready;
      hold_ram_cmd = cmd_valid && !cmd_ready;
      hold_ram_rsp = rsp_valid && !rsp_ready;
      hold_mmio_cmd = `ACCEL.cmd_valid && !`ACCEL.cmd_ready;
      hold_mmio_rsp = `ACCEL.rsp_valid && !`ACCEL.rsp_ready;
      saved_request = request_payload;
      saved_completion = completion_payload;
      saved_nice_cmd = nice_cmd_payload;
      saved_nice_rsp = nice_rsp_payload;
      saved_ram_cmd = ram_cmd_payload;
      saved_ram_rsp = rsp_rdata;
      saved_mmio_cmd = mmio_cmd_payload;
      saved_mmio_rsp = mmio_rsp_payload;
      if (hold_nice_cmd) nice_cmd_stall = nice_cmd_stall + 1;
      if (hold_completion) nice_rsp_hold_cycles = nice_rsp_hold_cycles + 1;
      if (hold_ram_rsp) ram_rsp_hold_cycles = ram_rsp_hold_cycles + 1;
      if (hold_mmio_rsp) mmio_rsp_hold_cycles = mmio_rsp_hold_cycles + 1;
      if (hold_ram_cmd && nice_bus_pending && !nice_endpoint_seen)
        nice_ram_cmd_stall = nice_ram_cmd_stall + 1;
    end
  endtask

  // All endpoint observations are passive: the NICE/LSU/core signals are never driven.
  task accept_nice_endpoint(input [31:0] addr, input read_op,
                            input [31:0] data, input [3:0] mask);
    begin
      if (nice_endpoint_seen || addr !== pending_addr || read_op !== pending_read ||
          (!read_op && (data !== pending_data || mask !== 4'hf)))
        $fatal(1,"NICE command differs at real endpoint seq=%0d addr=%h",pending_sequence,addr);
      nice_endpoint_seen = 1;
      nice_endpoint_commands = nice_endpoint_commands + 1;
      $display("NICE_ENDPOINT_CMD seq=%0d addr=%h read=%0d data=%h mask=%h",
               pending_sequence,addr,read_op,data,mask);
    end
  endtask

  task retire_nice_endpoint(input read_op, input [31:0] data, input err);
    begin
      if (!nice_bus_pending || !nice_endpoint_seen || nice_endpoint_done || err !== 1'b0 ||
          (read_op && data !== pending_data))
        $fatal(1,"NICE real endpoint response mismatch seq=%0d",pending_sequence);
      nice_endpoint_done = 1;
      nice_endpoint_responses = nice_endpoint_responses + 1;
      $display("NICE_ENDPOINT_RSP seq=%0d data=%h err=%0d",pending_sequence,data,err);
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

  initial begin : initialize
    integer i;
    if (!$value$plusargs("TESTCASE=%s",testcase)) $fatal(1,"missing TESTCASE");
    if (!$value$plusargs("BACKPRESSURE=%d",backpressure)) backpressure=1;
    if (!$value$plusargs("MAX_CYCLES=%d",max_cycles)) max_cycles=100000;
    if ((backpressure!=0 && backpressure!=1) || max_cycles<1) $fatal(1,"invalid probe mode");
    for (i=0; i<131072; i=i+1) ram[i]=POISON;
    for (i=0; i<65536; i=i+1) program_bytes[i]=0;
    $readmemh({testcase,".verilog"},program_bytes);
    for (i=0; i<8192; i=i+1)
      `ITCM.mem_r[i]={program_bytes[8*i+7],program_bytes[8*i+6],
        program_bytes[8*i+5],program_bytes[8*i+4],program_bytes[8*i+3],
        program_bytes[8*i+2],program_bytes[8*i+1],program_bytes[8*i]};
    if ($value$plusargs("DUMPWAVE=%d",dumpwave) && dumpwave) begin
      $dumpfile("nice_reachability.vcd");
      $dumpvars(0,tb_nice_reachability);
    end
    #120 rst_n=1;
  end

  always @(posedge clk) begin : scoreboard
    integer lane, offset, i;
    reg from_nice;
    cycles = cycles + 1;
    if (cycles > max_cycles)
      $fatal(1,"NICE probe timeout req=%0d rsp=%0d cmd=%0d bus_rsp=%0d",
             nice_requests,nice_responses,nice_commands,nice_bus_responses);
    if (rst_n) begin
      check_holds();
      if (`EXU.u_e203_exu_commit.commit_trap)
        $fatal(1,"unexpected CPU trap during normal NICE probe");
      if (`NICE.nice_mem_holdup &&
          (`LSU.agu_icb_cmd_valid_pos !== 1'b0 || `LSU.agu_icb_cmd_ready !== 1'b0))
        $fatal(1,"ordinary CPU AGU escaped NICE LSU hold");
      if (instruction_active && cycles>instruction_cycle && `NICE.nice_mem_holdup !== 1'b1)
        $fatal(1,"NICE released LSU before instruction completion");

      // The first memory command can handshake with the instruction request.
      if (`NICE.nice_req_valid && `NICE.nice_req_ready) begin
        if (instruction_active || nice_requests>=5 || nice_requests!=nice_responses ||
            src_initialized!==3'b111 || dst0_poisoned!==3'b111 || dst1_poisoned!==3'b111)
          $fatal(1,"unexpected NICE request or incomplete CPU initialization");
        if (`NICE.nice_req_inst[6:0]!==7'h7b || `NICE.nice_req_inst[14:12]!==3'd2 ||
            `NICE.nice_req_inst[11:7]!==5'd0 || `NICE.nice_req_inst[24:20]!==5'd0 ||
            `NICE.nice_req_inst[31:25] !== (instruction_read(nice_requests) ? 7'd1 : 7'd2) ||
            `NICE.nice_req_rs1 !== instruction_base(nice_requests))
          $fatal(1,"wrong actual demo instruction/operand index=%0d inst=%h rs1=%h",
                 nice_requests,`NICE.nice_req_inst,`NICE.nice_req_rs1);
        $display("NICE_REQUEST index=%0d inst=%h rs1=%h",nice_requests,
                 `NICE.nice_req_inst,`NICE.nice_req_rs1);
        instruction_active=1;
        instruction_cycle=cycles;
        instruction_commands=0;
        instruction_responses=0;
        nice_requests=nice_requests+1;
      end

      // Real endpoint responses retire before matching upstream NICE responses.
      if (rsp_valid && !ram_endpoint_pending) $fatal(1,"orphan external RAM response");
      if (rsp_valid && rsp_ready) begin
        if (ram_endpoint_nice) retire_nice_endpoint(ram_endpoint_read,rsp_rdata,1'b0);
        ram_endpoint_pending=0;
        ram_responses=ram_responses+1;
        rsp_valid<=0;
      end
      if (`ACCEL.rsp_valid && !mmio_pending) $fatal(1,"orphan real MMIO response");
      if (mmio_rsp_accept) begin
        if (`ACCEL.rsp_err !== 1'b0) $fatal(1,"real MMIO error addr=%h",mmio_pending_addr);
        if (mmio_pending_nice)
          retire_nice_endpoint(mmio_pending_read,`ACCEL.rsp_rdata,`ACCEL.rsp_err);
        else if (mmio_pending_read && mmio_pending_addr>=MMIO && mmio_pending_addr<=MMIO+8) begin
          lane=(mmio_pending_addr-MMIO)/4;
          if (`ACCEL.rsp_rdata !== pattern(lane)) $fatal(1,"CPU MMIO readback mismatch");
          mmio_cpu_checked[lane]=1;
        end
        mmio_pending=0;
      end

      // One outstanding: process the old response before accepting a new command.
      if (nice_rsp_accept) begin
        $display("[DEBUG-NICE] event=bus_response cycle=%0d seq=%0d cmd_valid=%b cmd_ready=%b cmd_addr=%h cmd_read=%b cmd_data=%h cmd_size=%b commands=%0d responses_before=%0d inst_commands=%0d inst_responses_before=%0d rsp_data=%h rsp_err=%b",
                 cycles,pending_sequence,
                 `NICE.nice_icb_cmd_valid,`NICE.nice_icb_cmd_ready,`NICE.nice_icb_cmd_addr,
                 `NICE.nice_icb_cmd_read,`NICE.nice_icb_cmd_wdata,`NICE.nice_icb_cmd_size,
                 nice_commands,nice_bus_responses,instruction_commands,instruction_responses,
                 `NICE.nice_icb_rsp_rdata,`NICE.nice_icb_rsp_err);
        if (!nice_bus_pending || !nice_endpoint_seen || !nice_endpoint_done ||
            `NICE.nice_icb_rsp_err !== 1'b0 ||
            (pending_read && `NICE.nice_icb_rsp_rdata !== pending_data))
          $fatal(1,"NICE LSU response mismatch seq=%0d",pending_sequence);
        $display("NICE_BUS_RSP seq=%0d data=%h err=%0d",pending_sequence,
                 `NICE.nice_icb_rsp_rdata,`NICE.nice_icb_rsp_err);
        nice_bus_pending=0;
        nice_bus_responses=nice_bus_responses+1;
        instruction_responses=instruction_responses+1;
      end
      if (nice_cmd_accept) begin
        if (!instruction_active || nice_bus_pending || instruction_commands>=3)
          $fatal(1,"NICE command without owner or more than one outstanding");
        pending_addr=instruction_base(nice_requests-1)+4*instruction_commands;
        pending_read=instruction_read(nice_requests-1);
        pending_data=pattern(instruction_commands);
        pending_sequence=nice_commands;
        if (`NICE.nice_icb_cmd_addr !== pending_addr ||
            `NICE.nice_icb_cmd_read !== pending_read || `NICE.nice_icb_cmd_size !== 2'b10 ||
            (!pending_read && `NICE.nice_icb_cmd_wdata !== pending_data))
          $fatal(1,"NICE memory command mismatch seq=%0d",pending_sequence);
        if (!(`LSU.arbt_icb_cmd_valid && `LSU.arbt_icb_cmd_ready) ||
            `LSU.arbt_icb_cmd_addr !== pending_addr || `LSU.arbt_icb_cmd_read !== pending_read ||
            `LSU.arbt_icb_cmd_size !== 2'b10 || `LSU.arbt_icb_cmd_wmask !== 4'hf ||
            (!pending_read && `LSU.arbt_icb_cmd_wdata !== pending_data))
          $fatal(1,"NICE request did not traverse the real LSU arbiter");
        nice_bus_pending=1;
        nice_endpoint_seen=0;
        nice_endpoint_done=0;
        nice_commands=nice_commands+1;
        instruction_commands=instruction_commands+1;
        $display("NICE_BUS_CMD seq=%0d addr=%h read=%0d data=%h",
                 pending_sequence,pending_addr,pending_read,`NICE.nice_icb_cmd_wdata);
      end

      if (mmio_cmd_accept) begin
        if (mmio_pending) $fatal(1,"multiple real MMIO requests outstanding");
        from_nice=nice_bus_pending && !nice_endpoint_seen;
        if (from_nice) begin
          accept_nice_endpoint(`ACCEL.cmd_addr,`ACCEL.cmd_read,`ACCEL.cmd_wdata,`ACCEL.cmd_wmask);
          if (`ACCEL.cmd_read) nice_mmio_reads=nice_mmio_reads+1;
          else nice_mmio_writes=nice_mmio_writes+1;
        end else if (!`ACCEL.cmd_read)
          $fatal(1,"CPU/stray MMIO write cannot stand in for NICE");
        mmio_pending=1;
        mmio_pending_nice=from_nice;
        mmio_pending_read=`ACCEL.cmd_read;
        mmio_pending_addr=`ACCEL.cmd_addr;
      end

      // The only active memory model is the SoC's external system-memory port.
      if (!ram_pending && !rsp_valid) begin
        if (cmd_valid && !cmd_ready) ram_cmd_wait<=ram_cmd_wait+1;
        else if (!cmd_valid) ram_cmd_wait<=0;
      end
      if (ram_pending) begin
        if (ram_rsp_wait==0) begin
          rsp_valid<=1;
          rsp_rdata<=ram_pending_data;
          ram_pending<=0;
        end else begin
          ram_rsp_wait<=ram_rsp_wait-1;
          if (ram_pending_nice) nice_ram_rsp_delay=nice_ram_rsp_delay+1;
        end
      end
      if (cmd_valid && cmd_ready) begin
        if (ram_endpoint_pending || ram_pending || rsp_valid || cmd_addr[1:0]!==2'b00 ||
            cmd_addr<BASE || cmd_addr>=BASE+32'h80000)
          $fatal(1,"invalid or multiple external RAM request addr=%h",cmd_addr);
        from_nice=nice_bus_pending && !nice_endpoint_seen;
        if (from_nice) begin
          accept_nice_endpoint(cmd_addr,cmd_read,cmd_wdata,cmd_wmask);
          if (cmd_read) nice_ram_reads=nice_ram_reads+1;
          else nice_ram_writes=nice_ram_writes+1;
        end
        offset=(cmd_addr-BASE)/4;
        if (cmd_addr>=SRC && cmd_addr<=SRC+8) begin
          lane=(cmd_addr-SRC)/4;
          if (!cmd_read) begin
            if (from_nice || nice_requests!=0 || src_initialized[lane] ||
                cmd_wdata!==pattern(lane) || cmd_wmask!==4'hf)
              $fatal(1,"unexpected source initialization");
            src_initialized[lane]=1;
          end else if (!from_nice) $fatal(1,"CPU source read cannot replace NICE load");
        end else if ((cmd_addr>=DST0 && cmd_addr<=DST0+8) ||
                     (cmd_addr>=DST1 && cmd_addr<=DST1+8)) begin
          lane=(cmd_addr>=DST1 ? cmd_addr-DST1 : cmd_addr-DST0)/4;
          if (!cmd_read) begin
            if (cmd_wmask!==4'hf) $fatal(1,"partial output/poison write");
            if (from_nice) begin
              if (cmd_wdata!==pattern(lane)) $fatal(1,"NICE shared output mismatch");
              if (cmd_addr>=DST1) begin
                if (dst1_written[lane]) $fatal(1,"duplicate NICE dst1 write");
                dst1_written[lane]=1;
              end else begin
                if (dst0_written[lane]) $fatal(1,"duplicate NICE dst0 write");
                dst0_written[lane]=1;
              end
            end else begin
              if (nice_requests!=0 || cmd_wdata!==POISON) $fatal(1,"CPU forged output write");
              if (cmd_addr>=DST1) begin
                if (dst1_poisoned[lane]) $fatal(1,"duplicate dst1 poison");
                dst1_poisoned[lane]=1;
              end else begin
                if (dst0_poisoned[lane]) $fatal(1,"duplicate dst0 poison");
                dst0_poisoned[lane]=1;
              end
            end
          end else begin
            if (from_nice || ram[offset]!==pattern(lane)) $fatal(1,"CPU checked unwritten output");
            if (cmd_addr>=DST1) dst1_cpu_checked[lane]=1;
            else dst0_cpu_checked[lane]=1;
          end
        end else $fatal(1,"unexpected shared probe address %h",cmd_addr);
        ram_endpoint_pending=1;
        ram_endpoint_nice=from_nice;
        ram_endpoint_read=cmd_read;
        ram_endpoint_addr=cmd_addr;
        ram_pending<=1;
        ram_pending_nice=from_nice;
        ram_pending_data=cmd_read ? ram[offset] : 32'b0;
        if (!cmd_read) ram[offset]=cmd_wdata;
        ram_rsp_wait<=backpressure ? 1+(ram_serial%7) : 0;
        ram_serial=ram_serial+1;
        ram_commands=ram_commands+1;
        ram_cmd_wait<=0;
      end

      // The final bus response and instruction completion may occur together.
      if (`NICE.nice_rsp_valid && `NICE.nice_rsp_ready) begin
        if (!instruction_active || instruction_commands!=3 || instruction_responses!=3 ||
            nice_bus_pending || `NICE.nice_rsp_err!==1'b0 || `NICE.nice_rsp_rdat!==32'b0)
          $fatal(1,"NICE completion preceded complete real memory work");
        $display("NICE_COMPLETE index=%0d commands=%0d responses=%0d",
                 nice_responses,instruction_commands,instruction_responses);
        instruction_active=0;
        nice_responses=nice_responses+1;
      end
      if (nice_commands-nice_bus_responses<0 || nice_commands-nice_bus_responses>1 ||
          ram_commands-ram_responses<0 || ram_commands-ram_responses>1)
        $fatal(1,"accepted/retired request conservation failed");

      if (`EXU.u_e203_exu_commit.alu_cmt_i_valid &&
          `EXU.u_e203_exu_commit.alu_cmt_i_ready &&
          `EXU.u_e203_exu_commit.alu_cmt_i_pc==32'h80000086) begin
        if (`EXU.u_e203_exu_regfile.rf_r[3]!==32'd1 || nice_requests!=5 || nice_responses!=5 ||
            nice_commands!=15 || nice_bus_responses!=15 ||
            nice_endpoint_commands!=15 || nice_endpoint_responses!=15 ||
            nice_ram_reads!=3 || nice_ram_writes!=6 || nice_mmio_reads!=3 || nice_mmio_writes!=3 ||
            instruction_active || nice_bus_pending || mmio_pending || ram_endpoint_pending ||
            ram_pending || rsp_valid || ram_commands!=ram_responses ||
            dst0_written!==3'b111 || dst1_written!==3'b111 ||
            dst0_cpu_checked!==3'b111 || dst1_cpu_checked!==3'b111 || mmio_cpu_checked!==3'b111)
          $fatal(1,"incomplete real NICE probe gp=%0d req=%0d rsp=%0d cmd=%0d bus_rsp=%0d",
                 `EXU.u_e203_exu_regfile.rf_r[3],nice_requests,nice_responses,nice_commands,nice_bus_responses);
        for (i=0; i<3; i=i+1)
          if (ram[(DST0-BASE)/4+i]!==pattern(i) || ram[(DST1-BASE)/4+i]!==pattern(i))
            $fatal(1,"final output image differs lane=%0d",i);
        if (backpressure && (nice_ram_cmd_stall==0 || nice_ram_rsp_delay==0 || nice_cmd_stall==0))
          $fatal(1,"requested backpressure did not exercise actual NICE traffic");
        $display("NICE_REACHABILITY_PASS requests=5 responses=5 commands=15 bus_responses=15 ram_reads=3 ram_writes=6 mmio_reads=3 mmio_writes=3 backpressure=%0d nice_cmd_stall=%0d ram_cmd_stall=%0d ram_rsp_delay=%0d nice_rsp_hold=%0d ram_rsp_hold=%0d mmio_rsp_hold=%0d cycles=%0d",
                 backpressure,nice_cmd_stall,nice_ram_cmd_stall,nice_ram_rsp_delay,
                 nice_rsp_hold_cycles,ram_rsp_hold_cycles,mmio_rsp_hold_cycles,cycles);
        $finish;
      end
    end
  end
endmodule
