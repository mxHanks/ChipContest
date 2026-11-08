`include "e203_defines.v"
// Direct-side failures are injected through the published interface. No force.
// These mock-side tests complement the real MAC wrapper fixture and SoC run.
module tb_nice_batch16_errors;
  reg clk=0,rst_n=0;
  always #5 clk=~clk;
  reg req_valid=0,rsp_ready=0,cmd_ready=0,bus_valid=0,bus_err=0;
  reg [31:0] rs1=32'ha0020000,rs2=32'h40,inst=32'h4400707b,bus_data=0;
  reg capable=1,direct_valid=0,commit_ready=0,commit_err=0;
  reg [31:0] direct_status=32'hc3;
  reg [255:0] direct_payload=0;
  wire req_ready,rsp_valid,rsp_err,cmd_valid,cmd_read,bus_ready,claim,direct_ready,commit;
  wire [31:0] rsp_data,cmd_addr,cmd_data;
  wire [1:0] cmd_size;
  integer cases=0,commands=0,responses=0,commits=0;
  integer error_writes=0,resets=0,second_failures=0,successes=0;
  integer case_start_writes=0,writes=0,commit_count=0,cycle=0,last_commit_cycle=-99;
  reg was_claim=0;
  integer claim_gaps=0;
  reg [31:0] base_addr=32'ha0020000;
  reg [31:0] current_group=0;
  xu_nice_drain8 #(.DIRECT_ENABLE(1)) dut(
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
    if(cmd_valid&&cmd_ready) commands=commands+1;
    if(bus_valid&&bus_ready) responses=responses+1;
    cycle=cycle+1;
    if(cmd_valid&&cmd_ready&&!cmd_read) begin
      if(dut.wide_mode && commit_count!=2)$fatal(1,"Y write before both bundle commits");
      writes=writes+1;
    end
    if(commit&&commit_ready&&!commit_err) begin
      commits=commits+1;commit_count=commit_count+1;
      last_commit_cycle=cycle;
    end
    if(was_claim&&!claim) claim_gaps=claim_gaps+1;
    was_claim=claim;
  end
  function automatic [31:0] word(input integer l); word=32'hf0000000+l;endfunction
  task automatic request(input [31:0] descriptor,input [31:0] address,input [31:0] instruction);
    begin
      @(negedge clk);rs1=address;rs2=descriptor;inst=instruction;req_valid=1;
      base_addr=address;current_group=descriptor[4:0];
      case_start_writes=writes;commit_count=0;
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
      for(integer l=0;l<8;l=l+1)direct_payload[32*l +: 32]=word(l+8*commit_count);
      repeat(21)begin @(negedge clk);if(!claim||!direct_ready||cmd_valid||rsp_valid)$fatal(1,"direct wait consumed poll budget as cycles");end
      direct_valid=1;@(posedge clk);#1;@(negedge clk);direct_valid=0;
    end
  endtask
  task automatic commit_bundle(input bit error);
    begin
      if(!commit||!claim)$fatal(1,"commit missing");
      for(integer l=0;l<8;l=l+1)if(dut.snapshot[l+8*commit_count]!==word(l+8*commit_count))$fatal(1,"commit before captured lane");
      repeat(23)begin @(negedge clk);if(!commit||!claim||cmd_valid||rsp_valid)$fatal(1,"commit withdrawn while stalled");end
      commit_ready=1;commit_err=error;
      @(posedge clk);#1;@(negedge clk);commit_ready=0;commit_err=0;
      if(dut.wide_mode && commit_count==1 && !error) begin
        if(claim || direct_ready || commit || cmd_valid || rsp_valid)$fatal(1,"claim gap not isolated");
        @(posedge clk);#1;
        if(claim || direct_ready || commit)$fatal(1,"claim gap absent for full edge");
        @(negedge clk);
      end
    end
  endtask
  task automatic reset_now;
    begin
      @(negedge clk);rst_n=0;req_valid=0;bus_valid=0;direct_valid=0;commit_ready=0;cmd_ready=0;
      repeat(3)@(negedge clk);
      if(cmd_valid||rsp_valid||claim||commit||direct_ready||!req_ready)$fatal(1,"reset did not clear ownership");
      rst_n=1;commands=0;responses=0;commit_count=0;was_claim=0;resets=resets+1;
    end
  endtask

  function automatic [31:0] status(input integer group);
    status=3+(group<<6);
  endfunction
  task automatic first_bundle;
    begin
      reply(32'h100420c4,1,status(current_group),0);
      bundle(status(current_group));commit_bundle(0);
    end
  endtask
  task automatic second_bundle;
    begin
      reply(32'h100420c4,1,status(current_group+1),0);
      bundle(status(current_group+1));commit_bundle(0);
    end
  endtask
  task automatic zero_writes;
    begin
      if(writes!=case_start_writes)$fatal(1,"failed pair leaked Y writes");
      second_failures=second_failures+1;
    end
  endtask
  task automatic all_writes;
    begin
      for(integer l=0;l<16;l=l+1)reply(base_addr+4*l,0,0,0);
      finish_case(0);successes=successes+1;
    end
  endtask
  initial begin
    reset_now();
    request(32'h40,32'ha0020000,0);finish_case(1);
    capable=0;request(32'h40,32'ha0020000,32'h4400707b);finish_case(1);capable=1;
    request(32'h40,32'ha0020004,32'h4400707b);finish_case(2);
    request(32'h40,32'ha0020020,32'h4400707b);finish_case(2);
    request(32'h40,32'ha001ffc0,32'h4400707b);finish_case(3);
    request(32'h40,32'ha0038c00,32'h4400707b);finish_case(3);
    request(32'h41,32'ha0020000,32'h4400707b);finish_case(6);
    request(0,32'ha0020000,32'h4400707b);finish_case(4);
    request(32'h20,32'ha0020000,32'h4400707b);reply(32'h100420c4,1,1,0);finish_case(5);
    request(32'h40,32'ha0020000,32'h4400707b);reply(32'h100420c4,1,status(1),0);finish_case(6);
    request(32'h40,32'ha0020000,32'h4400707b);reply(32'h100420c4,1,2,0);finish_case(7);
    request(32'h40,32'ha0020000,32'h4400707b);reply(32'h100420c4,1,0,1);finish_case(8);
    request(32'h40,32'ha0020000,32'h4400707b);reply(32'h100420c4,1,status(0),0);bundle(status(1));finish_case(6);
    request(32'h40,32'ha0020000,32'h4400707b);reply(32'h100420c4,1,status(0),0);bundle(2);finish_case(7);
    request(32'h40,32'ha0020000,32'h4400707b);reply(32'h100420c4,1,status(0),0);bundle(status(0));commit_bundle(1);finish_case(7);
    // Every second-group failure must leave all sixteen destination words untouched.
    request(32'h40,32'ha0020000,32'h4400707b);first_bundle();reply(32'h100420c4,1,0,1);finish_case(8);zero_writes();
    request(32'h20,32'ha0020000,32'h4400707b);first_bundle();reply(32'h100420c4,1,1,0);finish_case(5);zero_writes();
    request(32'h40,32'ha0020000,32'h4400707b);first_bundle();reply(32'h100420c4,1,status(2),0);finish_case(6);zero_writes();
    request(32'h40,32'ha0020000,32'h4400707b);first_bundle();reply(32'h100420c4,1,2,0);finish_case(7);zero_writes();
    request(32'h40,32'ha0020000,32'h4400707b);first_bundle();reply(32'h100420c4,1,status(1),0);bundle(status(2));finish_case(6);zero_writes();
    request(32'h40,32'ha0020000,32'h4400707b);first_bundle();reply(32'h100420c4,1,status(1),0);bundle(2);finish_case(7);zero_writes();
    request(32'h40,32'ha0020000,32'h4400707b);first_bundle();reply(32'h100420c4,1,status(1),0);bundle(status(1));commit_bundle(1);finish_case(7);zero_writes();
    for(integer e=0;e<16;e=e+1)begin
      request(32'h40,32'ha0020000,32'h4400707b);first_bundle();second_bundle();
      for(integer l=0;l<=e;l=l+1)reply(base_addr+4*l,0,0,l==e);
      finish_case(8);error_writes=error_writes+1;
    end
    // Both groups may consume their full per-group poll budget independently.
    request(32'h40,32'ha0020000,32'h4400707b);
    reply(32'h100420c4,1,1,0);first_bundle();
    reply(32'h100420c4,1,1,0);second_bundle();all_writes();
    // Last valid aligned span and highest even group.
    request(32'h5e,32'ha0038bc0,32'h4400707b);first_bundle();second_bundle();all_writes();
    // Legacy drain8 retains its original odd group and 32-byte alignment ABI.
    request(32'h43,32'ha0020020,32'h4000707b);
    reply(32'h100420c4,1,status(3),0);bundle(status(3));commit_bundle(0);
    for(integer l=0;l<8;l=l+1)reply(base_addr+4*l,0,0,0);
    finish_case(0);
    // Reset at every new instruction state, with no stale completion or command.
    request(32'h40,32'ha0020000,32'h4400707b);reset_now(); // SEND_POLL
    request(32'h40,32'ha0020000,32'h4400707b);
    while(!cmd_valid)@(negedge clk);cmd_ready=1;@(posedge clk);#1;@(negedge clk);cmd_ready=0;reset_now(); // WAIT_POLL
    request(32'h40,32'ha0020000,32'h4400707b);reply(32'h100420c4,1,status(0),0);reset_now(); // first DIRECT_WAIT
    request(32'h40,32'ha0020000,32'h4400707b);reply(32'h100420c4,1,status(0),0);bundle(status(0));reset_now(); // first COMMIT
    request(32'h40,32'ha0020000,32'h4400707b);reply(32'h100420c4,1,status(0),0);bundle(status(0));
    commit_ready=1;@(posedge clk);#1;if(dut.state!=9)$fatal(1,"gap state missing");reset_now(); // GAP
    request(32'h40,32'ha0020000,32'h4400707b);first_bundle();reply(32'h100420c4,1,status(1),0);reset_now(); // second WAIT
    request(32'h40,32'ha0020000,32'h4400707b);first_bundle();reply(32'h100420c4,1,status(1),0);bundle(status(1));reset_now(); // second COMMIT
    request(32'h40,32'ha0020000,32'h4400707b);first_bundle();second_bundle();reset_now(); // SEND_WRITE
    request(32'h40,32'ha0020000,32'h4400707b);first_bundle();second_bundle();
    while(!cmd_valid)@(negedge clk);cmd_ready=1;@(posedge clk);#1;@(negedge clk);cmd_ready=0;reset_now(); // WAIT_WRITE
    request(32'h40,32'ha0020004,32'h4400707b);reset_now(); // RESP
    $display("NICE_BATCH16_PASS cases=%0d success16=%0d write_error_lanes=%0d second_group_failures_no_write=%0d resets=%0d claim_gaps=%0d",cases,successes,error_writes,second_failures,resets,claim_gaps);
    $finish;
  end
  initial begin #3000000;$fatal(1,"batch16 errors timeout state=%0d",dut.state);end
endmodule
