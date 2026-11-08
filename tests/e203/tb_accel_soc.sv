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
  integer output_y32 = 0, shared_w_packed16 = 0, output_words = 50688, nice_drain8 = 0, nice_read_pop = 0;
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

  integer nice_requests=0, nice_responses=0, nice_retired=0;
  integer nice_request_cycle=0;
  integer nice_polls=0, nice_reads=0, nice_pops=0, nice_writes=0, nice_step=0;
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
  task observe_nice;
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
          (!nice_instruction || nice_pending || nice_step!=(nice_read_pop ? 17 : 18) ||
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
        end else if (!nice_read_pop && nice_step==16) begin
          if (nice_read || nice_address!==32'h100420c8 || nice_data!==1 ||
              nice_lane_responses!==8'hff || nice_group_writes!=7 || nice_pop_retired)
            $fatal(1,"NICE legacy POP order");
        end else if (nice_step<=(nice_read_pop ? 16 : 17)) begin
          lane=nice_read_pop ? nice_step-9 : (nice_step==17 ? 7 : nice_step-9);
          if (nice_read || nice_address!==nice_destination+4*lane ||
              nice_lane_responses!==8'hff || nice_group_writes!=lane ||
              ((nice_read_pop || lane==7) ? !nice_pop_retired : nice_pop_retired) ||
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
          end else if (!nice_read_pop && nice_step==16) begin
            nice_pops=nice_pops+1;
            nice_pop_retired=1;
          end else begin
            nice_writes=nice_writes+1;
            nice_group_writes=nice_group_writes+1;
            if (nice_step==(nice_read_pop ? 16 : 17)) nice_final_y_response_cycle=cycles;
          end
          nice_step=nice_step+1;
        end
        nice_pending=0;
      end
      if (`NICE.nice_rsp_valid && `NICE.nice_rsp_ready) begin
        if (!nice_instruction || nice_pending || nice_step!=(nice_read_pop ? 17 : 18) || nice_completion_payload!==0 ||
            !`LONGWB.wbck_sel_nice || !`OITF.ret_ena || `OITF.ret_ptr!==nice_tag ||
            !`OITF.ret_rdwen || `OITF.ret_rdidx!==nice_rd ||
            !`LONGWB.longp_wbck_o_valid || !`LONGWB.longp_wbck_o_ready ||
            `LONGWB.longp_wbck_o_wdat!==0 || `LONGWB.longp_wbck_o_rdidx!==nice_rd)
          $fatal(1,"NICE completion/code/OITF/rd writeback mismatch index=%0d",nice_responses);
        nice_responses=nice_responses+1; nice_retired=nice_retired+1; nice_instruction=0;
      end
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
      nice_alias_responses=0; nice_group_writes=0; nice_final_y_response_cycle=-1;
      nice_lane_responses=0; nice_pop_retired=0;
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
      if (`ACCEL.row_pop) begin
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
        if (nice_requests!=3168 || nice_responses!=3168 || nice_retired!=3168 ||
            nice_polls<3168 || nice_reads!=25344 || nice_pops!=3168 || nice_writes!=25344 ||
            nice_alias_responses!=(nice_read_pop ? 3168 : 0) || nice_group_writes!=8 ||
            nice_lane_responses!==8'hff || !nice_pop_retired || nice_final_y_response_cycle<0 ||
            nice_instruction || nice_pending || nice_cmd_hold || nice_completion_hold)
          $fatal(1,"NICE complete task instruction/payload retirement mismatch");
        $display("NICE_TASK layer=%0d requests=%0d responses=%0d oitf_retired=%0d status_polls=%0d result_reads=%0d pops_retired=%0d shared_writes=%0d",
          layer,nice_requests,nice_responses,nice_retired,nice_polls,nice_reads,nice_pops,nice_writes);
        if (nice_read_pop) begin
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
    if (!$value$plusargs("OUTPUT_Y32=%d",output_y32)) output_y32=0;
    if (!$value$plusargs("SHARED_W_PACKED16=%d",shared_w_packed16)) shared_w_packed16=0;
    if (!$value$plusargs("NICE_DRAIN8=%d",nice_drain8)) nice_drain8=0;
    if (!$value$plusargs("NICE_READ_POP=%d",nice_read_pop)) nice_read_pop=0;
    if ((output_y32!=0 && output_y32!=1) ||
        (shared_w_packed16!=0 && shared_w_packed16!=1) ||
        (nice_drain8!=0 && nice_drain8!=1) || (nice_drain8 && (!output_y32 || !shared_w_packed16)) ||
        (nice_read_pop!=0 && nice_read_pop!=1) || (nice_read_pop && !nice_drain8))
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
  end

  always @(posedge clk) begin : memory_and_scoreboard
    integer offset, word_index;
    reg [63:0] expected;
    cycles <= cycles+1;
    if (cycles > max_cycles) $fatal(1,"SoC timeout layer=%0d writes=%0d",layer,writes);
    if (rst_n) begin
      if (nice_drain8) observe_nice();
      observe_performance();
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
endmodule
