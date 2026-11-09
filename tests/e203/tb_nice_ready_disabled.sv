`include "e203_defines.v"
// Direct-side failures are injected through the published interface. No force.
// These mock-side tests complement the real MAC wrapper fixture and SoC run.
module tb_nice_ready_disabled;
  reg clk=0,rst_n=0;
  always #5 clk=~clk;
  reg req_valid=0,rsp_ready=0,cmd_ready=0,bus_valid=0,bus_err=0;
  reg [31:0] rs1=32'ha0020000,rs2=32'h43,inst=32'h4000707b,bus_data=0;
  reg capable=1,direct_valid=0,commit_ready=0,commit_err=0;
  reg [31:0] direct_status=32'h80000003;
  reg [255:0] direct_payload=0;
  wire req_ready,rsp_valid,rsp_err,cmd_valid,cmd_read,bus_ready,claim,direct_ready,commit;
  wire [31:0] rsp_data,cmd_addr,cmd_data;
  wire [1:0] cmd_size;
  integer cases=0,commands=0,responses=0,commits=0;
  integer error_writes=0,resets=0,status_abort_positions=0,success_counts=0;
  integer group_index=0,completed_groups=0,case_writes=0,case_commits=0;
  integer writes=0,cycle=0,last_commit_cycle=-99,claim_low_edges=0;
  reg [31:0] base_addr=32'ha0020000;
  integer first_group=0;
  reg streaming=0;
  xu_nice_drain8 #(.DIRECT_ENABLE(0)) dut(
    .nice_clk(clk),.nice_rst_n(rst_n),.nice_active(),.nice_mem_holdup(),
    .nice_req_valid(req_valid),.nice_req_ready(req_ready),.nice_req_inst(inst),
    .nice_req_rs1(rs1),.nice_req_rs2(rs2),.nice_rsp_valid(rsp_valid),.nice_rsp_ready(rsp_ready),
    .nice_rsp_rdat(rsp_data),.nice_rsp_err(rsp_err),
    .nice_icb_cmd_valid(cmd_valid),.nice_icb_cmd_ready(cmd_ready),
    .nice_icb_cmd_addr(cmd_addr),.nice_icb_cmd_read(cmd_read),
    .nice_icb_cmd_wdata(cmd_data),.nice_icb_cmd_size(cmd_size),
    .nice_icb_rsp_valid(bus_valid),.nice_icb_rsp_ready(bus_ready),
    .nice_icb_rsp_rdata(bus_data),.nice_icb_rsp_err(bus_err),
    .xu_direct_capable(capable),.xu_direct_claim(claim),.xu_direct_valid(direct_valid),
    .xu_direct_ready(direct_ready),.xu_direct_payload(direct_payload),.xu_direct_status(direct_status),
    .xu_direct_commit(commit),.xu_direct_commit_ready(commit_ready),.xu_direct_commit_err(commit_err));
  always @(posedge clk) if(rst_n) begin
    cycle=cycle+1;
    if(!claim) claim_low_edges=claim_low_edges+1;
    if(cmd_valid&&cmd_ready) begin
      commands=commands+1;
      if(!cmd_read) begin
        if(streaming && case_commits!=group_index+1)$fatal(1,"write before current group POP");
        writes=writes+1;case_writes=case_writes+1;
      end
    end
    if(bus_valid&&bus_ready) responses=responses+1;
    if(commit&&commit_ready&&!commit_err) begin
      commits=commits+1;case_commits=case_commits+1;
      if(streaming && completed_groups!=group_index)$fatal(1,"next POP before previous writes complete");
      if(streaming && group_index>0 && claim_low_edges==0)$fatal(1,"no claim-low edge between groups");
      last_commit_cycle=cycle;claim_low_edges=0;
    end
  end
  function automatic [31:0] word(input integer l); word=32'hf0000000+l;endfunction
  task automatic request(input [31:0] descriptor,input [31:0] address,input [31:0] instruction);
    begin
      @(negedge clk);rs1=address;rs2=descriptor;inst=instruction;req_valid=1;
      base_addr=address;first_group=descriptor[4:0];group_index=0;
      completed_groups=0;case_writes=0;case_commits=0;streaming=instruction==32'h4800707b;
      @(posedge clk);if(!req_ready)$fatal(1,"request not ready");
      @(negedge clk);req_valid=0;rs1=32'hdeadbeef;rs2=0;inst=0;
    end
  endtask
  task automatic reply(input [31:0] address,input bit reading,input [31:0] data,input bit err);
    reg [66:0] held;
    integer guard;
    begin
      guard=0;
      while(!cmd_valid) begin @(negedge clk);guard=guard+1;if(guard>100)$fatal(1,"command timeout");end
      if(cmd_addr!==address||cmd_read!==reading||cmd_size!==2)$fatal(1,"wrong direct command %h",cmd_addr);
      if(!reading&&cmd_data!==word((address-base_addr)/4))$fatal(1,"snapshot data mismatch");
      held={cmd_addr,cmd_read,cmd_data,cmd_size};
      repeat(13)begin @(negedge clk);if(!cmd_valid||{cmd_addr,cmd_read,cmd_data,cmd_size}!==held)$fatal(1,"command changed under stall");end
      cmd_ready=1;@(posedge clk);#1;@(negedge clk);cmd_ready=0;
      repeat(17)begin @(negedge clk);if(cmd_valid||rsp_valid)$fatal(1,"overlap or early completion");end
      bus_data=data;bus_err=err;bus_valid=1;
      @(posedge clk);if(!bus_ready)$fatal(1,"lost outstanding response");#1;
      @(negedge clk);bus_valid=0;bus_err=0;
    end
  endtask
  task automatic finish_case(input integer code);
    reg [32:0] held;
    integer guard;
    begin
      guard=0;
      while(!rsp_valid)begin @(negedge clk);guard=guard+1;if(guard>100)$fatal(1,"completion timeout");end
      if(rsp_data!==code||rsp_err!==(code!=0))$fatal(1,"wrong error code %0d want %0d",rsp_data,code);
      held={rsp_err,rsp_data};
      repeat(19)begin @(negedge clk);if(!rsp_valid||{rsp_err,rsp_data}!==held||cmd_valid||claim||commit)$fatal(1,"completion unstable/post-error side effect");end
      rsp_ready=1;@(posedge clk);#1;@(negedge clk);rsp_ready=0;cases=cases+1;
      if(commands!=responses)$fatal(1,"orphan bus command");
    end
  endtask
  task automatic bundle(input [31:0] status);
    begin
      if(!claim||!direct_ready||cmd_valid)$fatal(1,"direct request missing");
      direct_status=status;
      for(integer l=0;l<8;l=l+1)direct_payload[32*l +: 32]=word(group_index*8+l);
      repeat(21)begin @(negedge clk);if(!claim||!direct_ready||cmd_valid||rsp_valid)$fatal(1,"direct wait consumed poll budget as cycles");end
      direct_valid=1;@(posedge clk);#1;@(negedge clk);direct_valid=0;
    end
  endtask
  task automatic commit_bundle(input bit error);
    begin
      if(!commit||!claim)$fatal(1,"commit missing");
      for(integer l=0;l<8;l=l+1)if(dut.snapshot[l]!==word(group_index*8+l))$fatal(1,"commit before captured lane");
      repeat(23)begin @(negedge clk);if(!commit||!claim||cmd_valid||rsp_valid)$fatal(1,"commit withdrawn while stalled");end
      commit_ready=1;commit_err=error;
      @(posedge clk);#1;@(negedge clk);commit_ready=0;commit_err=0;
    end
  endtask
  task automatic reset_now;
    begin
      @(negedge clk);rst_n=0;req_valid=0;bus_valid=0;direct_valid=0;commit_ready=0;cmd_ready=0;
      repeat(3)@(negedge clk);
      if(cmd_valid||rsp_valid||claim||commit||direct_ready||!req_ready)$fatal(1,"reset did not clear ownership");
      rst_n=1;commands=0;responses=0;resets=resets+1;
      group_index=0;completed_groups=0;case_writes=0;case_commits=0;streaming=0;
    end
  endtask

  function automatic [31:0] status(input integer group);
    status=3+(group<<6);
  endfunction
  function automatic [31:0] desc(input integer group,input integer count,input integer budget);
    desc=(budget<<10)|((count-1)<<5)|group;
  endfunction
  task automatic current_poll;
    begin reply(32'h100420c4,1,status(first_group+group_index),0); end
  endtask
  task automatic current_bundle;
    begin bundle(status(first_group+group_index));commit_bundle(0);end
  endtask
  task automatic drain_group;
    begin
      current_poll();current_bundle();
      for(integer l=0;l<8;l=l+1)reply(base_addr+group_index*32+4*l,0,0,0);
      completed_groups=completed_groups+1;group_index=group_index+1;
    end
  endtask
  task automatic prefix(input integer groups);
    begin for(integer g=0;g<groups;g=g+1)drain_group();end
  endtask

  initial begin
    reset_now();
    request(desc(0,32,2),32'ha0020000,32'h4800707b);finish_case(1);
    if(commands||commits||writes)$fatal(1,"disabled stream emitted side effect");
    $display("NICE_READY8_DISABLED_PASS compile_time_enable=0 no_side_effect=1");
    $finish;
  end
  initial begin #100000;$fatal(1,"disabled timeout");end
endmodule
