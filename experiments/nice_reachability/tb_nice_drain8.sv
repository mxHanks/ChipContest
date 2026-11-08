`include "e203_defines.v"
// Isolated transport/FSM tests only. This does NOT prove real LSU reachability.
module tb_nice_drain8;
  reg clk=0, rst_n=0;
  always #5 clk=~clk;
  reg req_valid=0, rsp_ready=0, cmd_ready=0, bus_rsp_valid=0, bus_rsp_err=0;
  reg [31:0] req_inst=32'h4000707b, req_rs1=0, req_rs2=0, bus_rsp_data=0;
  wire req_ready, rsp_valid, rsp_err, cmd_valid, cmd_read, bus_rsp_ready, active, hold;
  wire [31:0] rsp_data, cmd_addr, cmd_data;
  wire [1:0] cmd_size;
  integer cases=0, total_commands=0, total_responses=0;
  integer case_commands=0, case_responses=0;
  integer clock_count=0;
  reg [7:0] lane_responses=0, write_responses=0;
  reg alias_retired=0;
  integer alias_errors=0, post_pop_write_errors=0;
  wire [66:0] payload={cmd_addr,cmd_read,cmd_data,cmd_size};

  xu_nice_drain8 dut (
    .nice_clk(clk), .nice_rst_n(rst_n), .nice_active(active), .nice_mem_holdup(hold),
    .nice_req_valid(req_valid), .nice_req_ready(req_ready), .nice_req_inst(req_inst),
    .nice_req_rs1(req_rs1), .nice_req_rs2(req_rs2),
    .nice_rsp_valid(rsp_valid), .nice_rsp_ready(rsp_ready),
    .nice_rsp_rdat(rsp_data), .nice_rsp_err(rsp_err),
    .nice_icb_cmd_valid(cmd_valid), .nice_icb_cmd_ready(cmd_ready),
    .nice_icb_cmd_addr(cmd_addr), .nice_icb_cmd_read(cmd_read),
    .nice_icb_cmd_wdata(cmd_data), .nice_icb_cmd_size(cmd_size),
    .nice_icb_rsp_valid(bus_rsp_valid), .nice_icb_rsp_ready(bus_rsp_ready),
    .nice_icb_rsp_rdata(bus_rsp_data), .nice_icb_rsp_err(bus_rsp_err)
  );

  function automatic [31:0] lane_data(input integer lane);
    case (lane)
      0: lane_data=32'h00000000;
      1: lane_data=32'h00000001;
      2: lane_data=32'hffffffff;
      3: lane_data=32'h01234567;
      4: lane_data=32'hfedcba98;
      5: lane_data=32'h40000000;
      6: lane_data=32'hc0000000;
      7: lane_data=32'hbbbbbbbb;
      default: lane_data=32'hxxxxxxxx;
    endcase
  endfunction

  // Every accepted command receives exactly one delayed response. Every SEND
  // boundary is stalled independently; no timer may cancel the held command.
  task service_command(input [31:0] destination, input integer group_id,
      input integer empty_polls, input integer bad_head, input integer error_index,
      input integer stall_seed);
    integer index, lane, command_delay, response_delay, j;
    reg [31:0] expected_addr, expected_data, reply;
    reg expected_read, reply_error;
    reg [66:0] saved;
    begin
      index=case_commands;
      expected_addr=0; expected_data=0; expected_read=1; reply=0;
      if (index<=empty_polls) begin
        expected_addr=32'h100420c4;
        reply=(group_id<<6)|32'h1;
        if (index==empty_polls) reply=reply|32'h2;
        if (bad_head==1) reply=(((group_id+1)%32)<<6)|32'h3;
        if (bad_head==2) reply=(group_id<<6)|32'h2;
      end else if (index<=empty_polls+8) begin
        lane=index-empty_polls-1;
        expected_addr=lane==7 ? 32'h100421a0 : 32'h10042180+4*lane;
        reply=lane_data(lane);
      end else if (index<=empty_polls+16) begin
        lane=index-empty_polls-9;
        expected_addr=destination+4*lane;
        expected_data=lane_data(lane);
        expected_read=0;
      end else $fatal(1,"unexpected extra command index=%0d",index);
      if (cmd_addr!==expected_addr || cmd_read!==expected_read || cmd_size!==2'b10 ||
          (!expected_read && cmd_data!==expected_data))
        $fatal(1,"wrong drain command index=%0d addr=%h read=%b data=%h",index,cmd_addr,cmd_read,cmd_data);
      saved=payload;
      command_delay=(stall_seed+index)%5;
      if (stall_seed==31) command_delay=17;
      for (j=0; j<command_delay; j=j+1) begin
        @(negedge clk);
        if (cmd_valid!==1'b1 || payload!==saved || rsp_valid || req_ready)
          $fatal(1,"command withdrawn/changed before ready index=%0d",index);
      end
      cmd_ready=1;
      @(posedge clk);
      if (!(cmd_valid && cmd_ready) || case_commands!=case_responses)
        $fatal(1,"command handshake or single outstanding failed");
      if(expected_addr==32'h100421a0 &&
         (lane_responses!==8'h7f || write_responses!==0 || alias_retired))
        $fatal(1,"alias issued before all seven ordinary lane responses retired");
      if(!expected_read && (lane_responses!==8'hff || !alias_retired))
        $fatal(1,"Y write before complete snapshot and read-POP response retirement");
      case_commands=case_commands+1;
      total_commands=total_commands+1;
      @(negedge clk);
      cmd_ready=0;
      response_delay=1+(stall_seed+3*index)%7;
      if (stall_seed==31) response_delay=19;
      for (j=0; j<response_delay; j=j+1) begin
        if (cmd_valid || rsp_valid || !hold || req_ready || case_commands-case_responses!=1)
          $fatal(1,"in-flight request canceled or overlapped index=%0d",index);
        @(negedge clk);
      end
      reply_error=(index==error_index);
      bus_rsp_data=reply;
      bus_rsp_err=reply_error;
      bus_rsp_valid=1;
      @(posedge clk);
      if (!bus_rsp_ready) $fatal(1,"DUT did not consume outstanding response");
      if(!reply_error) begin
        if(index>empty_polls && index<=empty_polls+8) lane_responses[lane]=1;
        if(expected_addr==32'h100421a0) alias_retired=1;
        if(!expected_read) write_responses[lane]=1;
      end else if(expected_addr==32'h100421a0) alias_errors=alias_errors+1;
      else if(!expected_read) begin
        if(!alias_retired) $fatal(1,"post-POP write error coverage missed ownership release");
        post_pop_write_errors=post_pop_write_errors+1;
      end
      case_responses=case_responses+1;
      total_responses=total_responses+1;
      @(negedge clk);
      bus_rsp_valid=0;
      bus_rsp_err=0;
      bus_rsp_data=0;
    end
  endtask

  task run_case(input [31:0] destination, input integer poll_limit,
      input integer group_id, input integer expected_code, input integer expected_commands,
      input integer error_index, input integer empty_polls, input integer bad_head,
      input integer stall_seed, input [31:0] instruction);
    integer guard, j;
    reg [32:0] saved_completion;
    begin
      @(negedge clk);
      if (!req_ready || cmd_valid || rsp_valid) $fatal(1,"case did not start idle");
      case_commands=0; case_responses=0; lane_responses=0; write_responses=0; alias_retired=0;
      req_inst=instruction; req_rs1=destination; req_rs2=(poll_limit<<5)|group_id;
      req_valid=1;
      @(posedge clk);
      if (!req_ready) $fatal(1,"instruction request not accepted");
      @(negedge clk);
      req_valid=0;
      // A request is captured once: subsequent changing operands must not alter it.
      req_inst=0; req_rs1=32'hffffffff; req_rs2=0;
      guard=0;
      while (!rsp_valid) begin
        if (cmd_valid) begin
          if (case_commands>=expected_commands) $fatal(1,"command after error/timeout/invalid descriptor");
          service_command(destination,group_id,empty_polls,bad_head,error_index,stall_seed);
        end else @(negedge clk);
        guard=guard+1;
        if (guard>100) $fatal(1,"case made no progress");
      end
      if (rsp_data!==expected_code || rsp_err!==(expected_code!=0) ||
          case_commands!=expected_commands || case_responses!=case_commands)
        $fatal(1,"wrong completion code=%0d expected=%0d commands=%0d expected_commands=%0d",
               rsp_data,expected_code,case_commands,expected_commands);
      if(expected_code==0 && (lane_responses!==8'hff || write_responses!==8'hff || !alias_retired))
        $fatal(1,"completion before eighth Y response retired");
      saved_completion={rsp_err,rsp_data};
      // Completion backpressure must retain the response, with no new command
      // or new instruction acceptance, including all eight post-POP write errors.
      req_valid=1;
      for (j=0; j<9; j=j+1) begin
        @(negedge clk);
        if (!rsp_valid || {rsp_err,rsp_data}!==saved_completion || cmd_valid ||
            req_ready || !hold || bus_rsp_ready)
          $fatal(1,"completion changed or error emitted later work");
      end
      req_valid=0;
      rsp_ready=1;
      @(posedge clk);
      if (!rsp_valid) $fatal(1,"completion disappeared at retirement");
      @(negedge clk);
      rsp_ready=0;
      if (!req_ready || rsp_valid || cmd_valid || hold) $fatal(1,"DUT failed to return idle");
      cases=cases+1;
    end
  endtask

  initial begin : tests
    integer group_id, error_index;
    #22 rst_n=1;
    // All 32 group tags, all lanes and delayed head availability.
    for (group_id=0; group_id<32; group_id=group_id+1)
      run_case(32'ha0020000+32*group_id,3,group_id,0,19,-1,2,0,group_id,32'h4000707b);
    // Both range endpoints; poll_limit=1 is NOT a bus-cycle timeout.
    run_case(32'ha0020000,1,0,0,17,-1,0,0,31,32'h4000707b);
    run_case(32'ha0038be0,1,31,0,17,-1,0,0,31,32'h4000707b);
    // Same legal aligned destination is allowed with any matching head tag.
    run_case(32'ha0020000,1,31,0,17,-1,0,0,2,32'h4000707b);
    // An error on every individual transaction forbids all later commands.
    for (error_index=0; error_index<17; error_index=error_index+1)
      run_case(32'ha0020000,1,0,8,error_index+1,error_index,0,0,error_index,32'h4000707b);
    run_case(32'ha0020000,3,0,5,3,-1,3,0,3,32'h4000707b);
    run_case(32'ha0020000,1,31,6,1,-1,0,1,4,32'h4000707b);
    run_case(32'ha0020000,1,0,7,1,-1,0,2,4,32'h4000707b);
    // Invalid descriptors must issue zero bus commands.
    run_case(32'ha0020000,1,0,1,0,-1,0,0,0,32'h00000000);
    run_case(32'ha0020004,1,0,2,0,-1,0,0,0,32'h4000707b);
    run_case(32'ha001ffe0,1,0,3,0,-1,0,0,0,32'h4000707b);
    run_case(32'ha0038c00,1,0,3,0,-1,0,0,0,32'h4000707b);
    run_case(32'hffffffe0,1,0,3,0,-1,0,0,0,32'h4000707b);
    run_case(32'ha0020000,0,0,4,0,-1,0,0,0,32'h4000707b);
    if (total_commands!=total_responses) $fatal(1,"final request conservation failed");
    if(alias_errors!=1 || post_pop_write_errors!=8) $fatal(1,"read-pop error coverage incomplete");
    $display("NICE_DRAIN8_UNIT_PASS cases=%0d commands=%0d responses=%0d all_error_transactions=17 groups=32 alias_errors=%0d post_pop_write_errors=%0d",
             cases,total_commands,total_responses,alias_errors,post_pop_write_errors);
    $finish;
  end

  always @(posedge clk) begin
    clock_count=clock_count+1;
    if (clock_count>100000) $fatal(1,"drain8 unit timeout");
  end
endmodule
