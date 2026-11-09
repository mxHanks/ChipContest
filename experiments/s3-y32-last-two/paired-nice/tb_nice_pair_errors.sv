`include "e203_defines.v"
// Isolated public-interface fixture: payload models the frozen eight-lane
// producer; real-MAC composition is a separate test. No force or hierarchy writes.
module tb_nice_pair_errors #(parameter PAIR_EN=1);
  reg clk=0,rst_n=0; always #5 clk=~clk;
  reg req_valid=0,rsp_ready=0,cmd_ready=0,bus_valid=0,bus_err=0;
  reg [31:0] rs1=0,rs2=0,inst=0;
  reg capable=1, pair_cap=1,live_cap=1,direct_valid=0,commit_ready=0,commit_err=0;
  reg [31:0] direct_status=32'hc0000001;
  reg [255:0] direct_payload=0;
  wire req_ready,rsp_valid,rsp_err,cmd_valid,cmd_read,bus_ready,claim,direct_ready,commit;
  wire [31:0] rsp_data,cmd_addr,cmd_data;wire [1:0] cmd_size;
  integer cases=0,writes=0,responses=0,pops=0,snaps=0,cycles=0;
  integer group_index=0,row_index=0,first_group=0,count=0,has_second=0;
  integer case_writes=0,case_responses=0,case_pops=0,case_snaps=0;
  integer error_positions=0,row_errors=0,resets=0;reg [31:0] base=0;
  xu_nice_drain8 #(.DIRECT_ENABLE(1),.PAIR_ENABLE(PAIR_EN)) dut(
    .nice_clk(clk),.nice_rst_n(rst_n),.nice_active(),.nice_mem_holdup(),
    .nice_req_valid(req_valid),.nice_req_ready(req_ready),.nice_req_inst(inst),
    .nice_req_rs1(rs1),.nice_req_rs2(rs2),.nice_rsp_valid(rsp_valid),.nice_rsp_ready(rsp_ready),
    .nice_rsp_rdat(rsp_data),.nice_rsp_err(rsp_err),.nice_icb_cmd_valid(cmd_valid),
    .nice_icb_cmd_ready(cmd_ready),.nice_icb_cmd_addr(cmd_addr),.nice_icb_cmd_read(cmd_read),
    .nice_icb_cmd_wdata(cmd_data),.nice_icb_cmd_size(cmd_size),.nice_icb_rsp_valid(bus_valid),
    .nice_icb_rsp_ready(bus_ready),.nice_icb_rsp_rdata(32'd0),.nice_icb_rsp_err(bus_err),
    .xu_direct_capable(capable),.xu_direct_claim(claim),.xu_direct_valid(direct_valid),
    .xu_direct_ready(direct_ready),.xu_direct_payload(direct_payload),.xu_direct_status(direct_status),
    .xu_direct_commit(commit),.xu_direct_commit_ready(commit_ready),.xu_direct_commit_err(commit_err));
  always @(posedge clk)if(rst_n)begin
    cycles=cycles+1;
    if(cmd_valid&&cmd_ready)begin
      if(cmd_read||cmd_size!=2)$fatal(1,"pair emitted non-word write");
      if(case_pops!=case_snaps||case_pops==0)$fatal(1,"write before snapshot/POP");
      writes=writes+1;case_writes=case_writes+1;
    end
    if(bus_valid&&bus_ready)begin responses=responses+1;case_responses=case_responses+1;end
    if(direct_valid&&direct_ready)begin
      if(commit)$fatal(1,"same-edge snapshot/POP");
      snaps=snaps+1;case_snaps=case_snaps+1;
    end
    if(commit&&commit_ready&&!commit_err)begin
      if(case_snaps!=case_pops+1)$fatal(1,"POP without unique snapshot");
      pops=pops+1;case_pops=case_pops+1;
    end
  end
  function automatic [31:0] descriptor(input integer g,input integer n,input bit second,input integer budget);
    descriptor=(budget<<11)|(second<<10)|((n-1)<<5)|g;
  endfunction
  function automatic [31:0] status(input integer g,input integer r,input bit valid_head);
    status=(live_cap?32'h80000000:0)|(pair_cap?32'h40000000:0)|(r<<11)|(g<<6)|(valid_head?3:1);
  endfunction
  function automatic [31:0] word(input integer g,input integer r,input integer l);
    word=32'h90000000+g*256+r*64+l;
  endfunction
  task automatic request(input [31:0] address,input [31:0] desc,input [31:0] insn);
    begin
      @(negedge clk);base=address;rs1=address;rs2=desc;inst=insn;req_valid=1;
      first_group=desc[4:0];count=desc[9:5]+1;has_second=desc[10];group_index=0;row_index=0;
      case_writes=0;case_responses=0;case_pops=0;case_snaps=0;
      direct_status=status(first_group,0,0);
      @(posedge clk);if(!req_ready)$fatal(1,"request not accepted");
      @(negedge clk);req_valid=0;rs1=32'hdeadbeef;rs2=0;inst=0;
    end
  endtask
  task automatic finish(input integer code);
    reg [32:0] held;integer guard;
    begin
      guard=0;while(!rsp_valid)begin @(negedge clk);guard=guard+1;if(guard>50)$fatal(1,"no completion");end
      if(rsp_err!==(code!=0)||rsp_data!==code)$fatal(1,"completion %0d expected %0d",rsp_data,code);
      held={rsp_err,rsp_data};
      repeat(11)begin @(negedge clk);if(!rsp_valid||{rsp_err,rsp_data}!==held||claim||commit||cmd_valid||bus_ready)$fatal(1,"unstable completion or side effect");end
      rsp_ready=1;@(posedge clk);#1;@(negedge clk);rsp_ready=0;cases=cases+1;
      if(case_writes!=case_responses)$fatal(1,"unretired bus command");
    end
  endtask
  task automatic ready_head;
    integer guard;
    begin
      direct_status=status(first_group+group_index,row_index,0);
      if(dut.state!==9||claim||cmd_valid||commit)$fatal(1,"not waiting for head");
      @(negedge clk);direct_status=status(first_group+group_index,row_index,1);
      guard=0;while(!claim)begin @(negedge clk);guard=guard+1;if(guard>20)$fatal(1,"head not claimed");end
      if(!direct_ready||dut.state!==7)$fatal(1,"claim without capture ready");
    end
  endtask
  task automatic snapshot_and_pop(input bit bad_commit);
    integer g;
    begin
      g=first_group+group_index;
      for(integer l=0;l<8;l=l+1)direct_payload[32*l+:32]=word(g,row_index,l);
      repeat(2)begin @(negedge clk);if(!claim||!direct_ready||commit||cmd_valid)$fatal(1,"capture wait unstable");end
      direct_valid=1;@(posedge clk);#1;@(negedge clk);direct_valid=0;direct_payload=0;
      if(!commit)$fatal(1,"commit not offered next edge");
      for(integer l=0;l<8;l=l+1)if(dut.snapshot[l]!==word(g,row_index,l))$fatal(1,"snapshot lane mismatch");
      repeat(3)begin @(negedge clk);if(!claim||!commit||cmd_valid||rsp_valid)$fatal(1,"commit unstable");end
      commit_ready=1;commit_err=bad_commit;@(posedge clk);#1;@(negedge clk);commit_ready=0;commit_err=0;
    end
  endtask
  task automatic reply_write(input integer l,input bit error);
    reg [66:0] held;integer guard;
    begin
      guard=0;while(!cmd_valid)begin @(negedge clk);guard=guard+1;if(guard>20)$fatal(1,"no write");end
      if(claim||commit||cmd_addr!==base+group_index*32+row_index*1024+l*4||cmd_data!==word(first_group+group_index,row_index,l))
        $fatal(1,"write addr/data/ownership mismatch g=%0d row=%0d lane=%0d addr=%h",group_index,row_index,l,cmd_addr);
      held={cmd_addr,cmd_read,cmd_data,cmd_size};
      repeat(1+(l%3))begin @(negedge clk);if(!cmd_valid||{cmd_addr,cmd_read,cmd_data,cmd_size}!==held)$fatal(1,"command changed under stall");end
      cmd_ready=1;@(posedge clk);#1;@(negedge clk);cmd_ready=0;
      repeat(2+(l%2))begin @(negedge clk);if(cmd_valid||rsp_valid||claim||commit)$fatal(1,"next command/completion before write response");end
      bus_valid=1;bus_err=error;@(posedge clk);if(!bus_ready)$fatal(1,"lost write response");#1;
      @(negedge clk);bus_valid=0;bus_err=0;
    end
  endtask
  task automatic bundle;
    begin ready_head();snapshot_and_pop(0);for(integer l=0;l<8;l=l+1)reply_write(l,0);end
  endtask
  task automatic advance;
    begin
      if(has_second&&!row_index)row_index=1;
      else begin row_index=0;group_index=group_index+1;end
    end
  endtask
  task automatic prefix(input integer bundles);
    begin for(integer b=0;b<bundles;b=b+1)begin bundle();advance();end end
  endtask
  task automatic reset_now;
    begin
      @(negedge clk);rst_n=0;req_valid=0;direct_valid=0;commit_ready=0;cmd_ready=0;bus_valid=0;bus_err=0;rsp_ready=0;
      repeat(3)@(negedge clk);
      if(cmd_valid||rsp_valid||claim||commit||direct_ready||!req_ready)$fatal(1,"reset retained ownership");
      rst_n=1;capable=1;pair_cap=1;live_cap=1;direct_status=32'hc0000001;resets=resets+1;
    end
  endtask
  integer n,s,e,b,l,r,phase;
  initial begin
    reset_now();
    if(!PAIR_EN)begin
      request(32'ha0020000,descriptor(0,32,1,50),32'h4a00707b);finish(1);
      if(case_writes||case_pops)$fatal(1,"disabled pair side effect");
      $display("NICE_PAIR_DISABLED_PASS no_side_effect=1");$finish;
    end
    request(32'ha0020000,descriptor(0,32,1,50),32'h4a00607b);finish(1);
    // The pair producer rejects old opcodes before any partial row0 effects.
    request(32'ha0020000,descriptor(0,32,1,50),32'h4000707b);finish(1);
    request(32'ha0020000,descriptor(0,32,1,50),32'h4600707b);finish(1);
    request(32'ha0020000,descriptor(0,32,1,50),32'h4800707b);finish(1);
    pair_cap=0;request(32'ha0020000,descriptor(0,32,1,50),32'h4a00707b);finish(1);pair_cap=1;
    live_cap=0;request(32'ha0020000,descriptor(0,32,1,50),32'h4a00707b);finish(1);live_cap=1;
    capable=0;request(32'ha0020000,descriptor(0,32,1,50),32'h4a00707b);finish(1);capable=1;
    request(32'ha0020004,descriptor(0,32,1,50),32'h4a00707b);finish(2);
    request(32'ha001ffe0,descriptor(0,32,1,50),32'h4a00707b);finish(3);
    request(32'ha0038c00,descriptor(0,32,0,50),32'h4a00707b);finish(3);
    request(32'ha00203e0,descriptor(31,2,1,50),32'h4a00707b);finish(9);
    request(32'ha0020020,descriptor(0,1,1,50),32'h4a00707b);finish(9);
    request(32'ha0038800,descriptor(0,32,1,50),32'h4a00707b);finish(9);
    request(32'ha0020000,descriptor(0,1,0,0),32'h4a00707b);finish(4);
    request(32'ha0020000,descriptor(0,1,0,1),32'h4a00707b);finish(5);
    // Every legal group count, both tail modes, including row97/98 boundary.
    for(s=0;s<2;s=s+1)for(n=1;n<=32;n=n+1)begin
      request((s?32'ha0038400:32'ha0038800)+(32-n)*32,descriptor(32-n,n,s,50),32'h4a00707b);
      prefix(n*(s+1));finish(0);
      if(case_writes!=n*(s+1)*8||case_pops!=n*(s+1))$fatal(1,"success/tail count");
    end
    // Inject each of512 possible post-POP shared-write errors independently.
    for(e=0;e<512;e=e+1)begin
      request(32'ha0020000,descriptor(0,32,1,50),32'h4a00707b);prefix(e/8);
      ready_head();snapshot_and_pop(0);
      for(l=0;l<=e%8;l=l+1)reply_write(l,l==e%8);
      finish(8);if(case_writes!=e+1||case_pops!=e/8+1)$fatal(1,"error leaked next transfer");
      error_positions=error_positions+1;
    end
    // A wrong row tag is rejected before snapshot/POP and again after capture.
    for(r=0;r<2;r=r+1)begin
      request(32'ha0020000,descriptor(0,2,1,50),32'h4a00707b);prefix(r);
      direct_status=status(0,1-r,1);finish(10);row_errors=row_errors+1;
      request(32'ha0020000,descriptor(0,2,1,50),32'h4a00707b);prefix(r);ready_head();
      direct_status=status(0,1-r,1);direct_valid=1;@(posedge clk);#1;@(negedge clk);direct_valid=0;
      finish(10);row_errors=row_errors+1;
      request(32'ha0020000,descriptor(0,2,1,50),32'h4a00707b);prefix(r);ready_head();snapshot_and_pop(1);finish(7);
      request(32'ha0020000,descriptor(0,2,1,50),32'h4a00707b);prefix(r);ready_head();
      direct_status=status(0,r,1)&32'hbfffffff;direct_valid=1;@(posedge clk);#1;@(negedge clk);direct_valid=0;
      finish(1);
      request(32'ha0020000,descriptor(0,2,1,50),32'h4a00707b);prefix(r);
      direct_status=status(0,r,0)&32'hbfffffff;finish(1);
    end
    // Reset every state owning a pair transfer, in either row. After reset a
    // new descriptor must succeed, with no stale completion, POP or write.
    for(r=0;r<2;r=r+1)for(phase=0;phase<6;phase=phase+1)begin
      request(32'ha0020000,descriptor(0,1,1,50),32'h4a00707b);prefix(r);
      if(phase>0)ready_head();
      if(phase>1)begin
        for(l=0;l<8;l=l+1)direct_payload[32*l+:32]=word(0,r,l);
        direct_valid=1;@(posedge clk);#1;@(negedge clk);direct_valid=0;
      end
      if(phase>2)begin commit_ready=1;@(posedge clk);#1;@(negedge clk);commit_ready=0;end
      if(phase>3)begin cmd_ready=1;@(posedge clk);#1;@(negedge clk);cmd_ready=0;end
      if(phase>4)begin bus_valid=1;bus_err=1;@(posedge clk);#1;@(negedge clk);bus_valid=0;bus_err=0;end
      reset_now();request(32'ha0038800,descriptor(0,1,0,50),32'h4a00707b);prefix(1);finish(0);
    end
    $display("NICE_PAIR_PASS cases=%0d counts=64 write_error_positions=%0d row_tag_errors=%0d resets=%0d snapshots=%0d pops=%0d writes=%0d responses=%0d",cases,error_positions,row_errors,resets,snaps,pops,writes,responses);
    $finish;
  end
  initial begin #200000000;$fatal(1,"global timeout");end
endmodule
