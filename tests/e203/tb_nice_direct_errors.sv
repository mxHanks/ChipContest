`include "e203_defines.v"
// Direct-side failures are injected through the published interface. No force.
// These mock-side tests complement the real MAC wrapper fixture and SoC run.
module tb_nice_direct_errors;
  reg clk=0,rst_n=0;
  always #5 clk=~clk;
  reg req_valid=0,rsp_ready=0,cmd_ready=0,bus_valid=0,bus_err=0;
  reg [31:0] rs1=32'ha0020000,rs2=32'h43,inst=32'h4000707b,bus_data=0;
  reg capable=1,direct_valid=0,commit_ready=0,commit_err=0;
  reg [31:0] direct_status=32'hc3;
  reg [255:0] direct_payload=0;
  wire req_ready,rsp_valid,rsp_err,cmd_valid,cmd_read,bus_ready,claim,direct_ready,commit;
  wire [31:0] rsp_data,cmd_addr,cmd_data;
  wire [1:0] cmd_size;
  integer cases=0,commands=0,responses=0,commits=0;
  integer error_writes=0,resets=0;
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
    if(commit&&commit_ready&&!commit_err) commits=commits+1;
  end
  function automatic [31:0] word(input integer l); word=32'hf0000000+l;endfunction
  task automatic request(input [31:0] descriptor,input [31:0] address,input [31:0] instruction);
    begin
      @(negedge clk);rs1=address;rs2=descriptor;inst=instruction;req_valid=1;
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
      if(!reading&&cmd_data!==word((address-32'ha0020000)/4))$fatal(1,"snapshot data mismatch");
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
      repeat(21)begin @(negedge clk);if(!claim||!direct_ready||cmd_valid||rsp_valid)$fatal(1,"direct wait consumed poll budget as cycles");end
      direct_valid=1;@(posedge clk);#1;@(negedge clk);direct_valid=0;
    end
  endtask
  task automatic commit_bundle(input bit error);
    begin
      if(!commit||!claim)$fatal(1,"commit missing");
      for(integer l=0;l<8;l=l+1)if(dut.snapshot[l]!==word(l))$fatal(1,"commit before captured lane");
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
    end
  endtask
  initial begin
    for(integer l=0;l<8;l=l+1)direct_payload[32*l +: 32]=word(l);
    reset_now();
    request(32'h43,32'ha0020000,0);finish_case(1);
    request(32'h43,32'ha0020004,32'h4000707b);finish_case(2);
    request(32'h43,32'ha0040000,32'h4000707b);finish_case(3);
    request(3,32'ha0020000,32'h4000707b);finish_case(4);
    request(32'h23,32'ha0020000,32'h4000707b);reply(32'h100420c4,1,1,0);finish_case(5);
    request(32'h43,32'ha0020000,32'h4000707b);reply(32'h100420c4,1,32'h103,0);finish_case(6);
    request(32'h43,32'ha0020000,32'h4000707b);reply(32'h100420c4,1,32'hc2,0);finish_case(7);
    request(32'h43,32'ha0020000,32'h4000707b);reply(32'h100420c4,1,0,1);finish_case(8);
    request(32'h43,32'ha0020000,32'h4000707b);reply(32'h100420c4,1,32'hc3,0);bundle(32'h103);finish_case(6);
    request(32'h43,32'ha0020000,32'h4000707b);reply(32'h100420c4,1,32'hc3,0);bundle(32'hc2);finish_case(7);
    request(32'h43,32'ha0020000,32'h4000707b);reply(32'h100420c4,1,32'hc3,0);bundle(32'hc3);commit_bundle(1);finish_case(7);
    for(integer e=0;e<8;e=e+1)begin
      request(32'h23,32'ha0020000,32'h4000707b);reply(32'h100420c4,1,32'hc3,0);
      bundle(32'hc3);commit_bundle(0);
      for(integer l=0;l<=e;l=l+1)reply(32'ha0020000+4*l,0,0,l==e);
      finish_case(8);error_writes=error_writes+1;
    end
    request(32'h23,32'ha0020000,32'h4000707b);reply(32'h100420c4,1,32'hc3,0);bundle(32'hc3);
    reset_now(); // held commit / captured snapshot discarded by common reset.
    request(32'h23,32'ha0020000,32'h4000707b);reply(32'h100420c4,1,32'hc3,0);
    reset_now(); // waiting direct valid.
    request(32'h23,32'ha0020000,32'h4000707b);
    reset_now(); // held LSU command, before acceptance.
    $display("NICE_DIRECT_ERRORS_PASS cases=%0d bus_error_positions=9 direct_status_errors=2 commit_error=1 shared_error_lanes=%0d resets=%0d",cases,error_writes,resets);
    $finish;
  end
  initial begin #1000000;$fatal(1,"direct errors timeout");end
endmodule
