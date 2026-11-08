`timescale 1ns/1ps
`include "e203_defines.v"
module tb_xu_direct_wrapper;
  reg clk=0;
  always #5 clk=~clk;
  reg rst_n=0, cmd_valid=0, cmd_read=0, rsp_ready=0;
  reg [31:0] cmd_addr=0, cmd_wdata=0;
  reg [3:0] cmd_wmask=0;
  wire cmd_ready, rsp_valid, rsp_err;
  wire [31:0] rsp_rdata;
  wire xu_direct_capable, xu_direct_valid, xu_direct_commit_ready, xu_direct_commit_err;
  wire [255:0] xu_direct_payload;
  wire [31:0] xu_direct_status;
  wire xu_direct_claim, xu_direct_ready, xu_direct_commit;
  wire nice_direct_ready, nice_direct_commit;
  wire nice_req_ready, nice_rsp_valid, nice_rsp_err, nice_cmd_valid, nice_cmd_read, nice_bus_ready;
  wire [31:0] nice_rsp_data, nice_cmd_addr, nice_cmd_data;
  wire [1:0] nice_cmd_size;
  reg nice_req_valid=0, nice_rsp_ready=0, allow_bundle=0, allow_commit=0;
  reg [31:0] nice_req_rs1=32'ha0020000, nice_req_rs2=0;
  reg manual=1;
  reg [31:0] mmio_addr=0, mmio_data=0;
  reg mmio_valid=0, mmio_read=0, mmio_rsp_ready=0;
  reg [3:0] mmio_mask=0;
  wire nice_status=nice_cmd_addr==32'h100420c4 && nice_cmd_read;
  integer ticks=0, writes=0, write_responses=0, snapshots=0, direct_pops=0, completions=0;
  integer fail_lane=-1, response_delay=0;
  integer reset_phase=0;
  reg write_pending=0, write_error=0;
  wire shared_ready=(ticks%5==0 || ticks%5==2) && !write_pending;
  wire shared_rsp=write_pending && response_delay==0;
  wire nice_cmd_ready=nice_status ? cmd_ready && !manual : shared_ready;
  wire nice_bus_valid=shared_rsp || (!manual && rsp_valid);
  wire [31:0] nice_bus_data=shared_rsp ? 0 : rsp_rdata;
  wire nice_bus_error=shared_rsp ? write_error : rsp_err;
  assign xu_direct_ready=nice_direct_ready && allow_bundle;
  assign xu_direct_commit=nice_direct_commit && allow_commit;
  always @* begin
    cmd_valid=manual ? mmio_valid : nice_cmd_valid && nice_status;
    cmd_read=manual ? mmio_read : nice_cmd_read;
    cmd_addr=manual ? mmio_addr : nice_cmd_addr;
    cmd_wdata=manual ? mmio_data : nice_cmd_data;
    cmd_wmask=manual ? mmio_mask : 4'hf;
    rsp_ready=manual ? mmio_rsp_ready : nice_bus_ready && !write_pending;
  end
  accel_icb_slave #(.DIRECT_ENABLE(1)) dut(.*);
  xu_nice_drain8 #(.DIRECT_ENABLE(1)) nice(
    .nice_clk(clk),.nice_rst_n(rst_n),.nice_active(),.nice_mem_holdup(),
    .nice_req_valid(nice_req_valid),.nice_req_ready(nice_req_ready),
    .nice_req_inst(32'h4000707b),.nice_req_rs1(nice_req_rs1),.nice_req_rs2(nice_req_rs2),
    .nice_rsp_valid(nice_rsp_valid),.nice_rsp_ready(nice_rsp_ready),
    .nice_rsp_rdat(nice_rsp_data),.nice_rsp_err(nice_rsp_err),
    .nice_icb_cmd_valid(nice_cmd_valid),.nice_icb_cmd_ready(nice_cmd_ready),
    .nice_icb_cmd_addr(nice_cmd_addr),.nice_icb_cmd_read(nice_cmd_read),
    .nice_icb_cmd_wdata(nice_cmd_data),.nice_icb_cmd_size(nice_cmd_size),
    .nice_icb_rsp_valid(nice_bus_valid),.nice_icb_rsp_ready(nice_bus_ready),
    .nice_icb_rsp_rdata(nice_bus_data),.nice_icb_rsp_err(nice_bus_error),
    .xu_direct_capable(xu_direct_capable),.xu_direct_claim(xu_direct_claim),
    .xu_direct_valid(xu_direct_valid && allow_bundle),.xu_direct_ready(nice_direct_ready),
    .xu_direct_payload(xu_direct_payload),.xu_direct_status(xu_direct_status),
    .xu_direct_commit(nice_direct_commit),
    .xu_direct_commit_ready(xu_direct_commit_ready && allow_commit),
    .xu_direct_commit_err(xu_direct_commit_err));

  integer alias_pops=0, explicit_pops=0, pop_events=0;
  integer starts=0, dones=0, accepts=0, retires=0, overlap=0, paired_overlap=0, next_group=0;
  integer row, g, lane, pair_id, k, col, s, before_starts, before_dones;
  integer numeric_paired_reads=0, numeric_lanes=0, numeric_negative=0, numeric_nonnegative=0;
  integer numeric_y32_reads=0, y32_overlap=0, positive_ties=0, negative_ties=0;
  integer even_ties=0, odd_ties=0, legal_min_seen=0, legal_max_seen=0;
  reg signed [63:0] magnitude, trunc_quotient;
  reg [31:0] response;
  reg signed [63:0] value;
  reg [47:0] raw, paired_even, paired_odd;

  // Real MAC fixtures reach both full-domain bounds. The other six lanes
  // have zero W and exercise signed ties and either side of the half step.
  function automatic signed [15:0] xv(input integer r,input integer i);
    xv=r==0 ? -16'sd32768 : 16'sd32767;
  endfunction
  function automatic signed [15:0] wv(input integer group_id,input integer l,input integer i);
    if(l==0) wv=-16'sd32768;
    else if(l==1) wv=16'sd32767;
    else wv=0;
  endfunction
  function automatic signed [39:0] bv(input integer r,input integer c);
    integer group_id;
    begin
      group_id=c/8;
      case(c%8)
        0: bv=r==0 ? 40'sh7fffffffff : -40'sh8000000000;
        1: bv=r==0 ? -40'sh8000000000 : 40'sh7fffffffff;
        2: bv=-256-1024*group_id-512*r;
        3: bv=-768-1024*group_id+512*r;
        4: bv=256+1024*group_id+512*r;
        5: bv=768+1024*group_id-512*r;
        6: bv=-257-1024*group_id+group_id%3;
        7: bv=255+1024*group_id+group_id%3;
      endcase
    end
  endfunction
  // Independent sign/magnitude oracle, rather than the RTL floor/remainder
  // formulation: round |value| with integer division, then restore its sign.
  function automatic [31:0] rne_reference(input signed [63:0] operand);
    reg signed [63:0] absolute_value, quotient, remainder;
    begin
      absolute_value=operand<0 ? -operand : operand;
      quotient=absolute_value/512;
      remainder=absolute_value%512;
      if(remainder>256 || (remainder==256 && quotient[0])) quotient=quotient+1;
      rne_reference=operand<0 ? -quotient : quotient;
    end
  endfunction
  function automatic signed [63:0] expected(input integer r,input integer group_id,input integer l);
    integer i;
    reg signed [31:0] product;
    reg signed [63:0] total;
    begin
      total=bv(r,8*group_id+l);
      for(i=0;i<64;i=i+1) begin
        product=xv(r,i)*wv(group_id,l,i);
        total=total+product;
      end
      expected=total;
    end
  endfunction

  always @(posedge clk) if (rst_n) begin
    if (cmd_valid && cmd_ready) accepts=accepts+1;
    if (dut.row_pop) pop_events=pop_events+1;
    if (rsp_valid && rsp_ready) retires=retires+1;
    if (dut.row_start) next_group=0;
    if (dut.compute_start) begin
      if (dut.row_active && dut.u_linear_compute_core.core.io_group!==next_group)
        $fatal(1,"duplicate/missing/out-of-order autonomous group start");
      starts=starts+1;
      if(dut.row_active) next_group=next_group+2;
    end
    if (dut.core_done) dones=dones+1;
    if (dut.row_running && cmd_valid && cmd_ready && cmd_read &&
        cmd_addr[11:0]>='h100 && cmd_addr[11:0]<='h13c) overlap=overlap+1;
    if (dut.row_running && cmd_valid && cmd_ready && cmd_read &&
        cmd_addr[11:0]>='h140 && cmd_addr[11:0]<='h14f) paired_overlap=paired_overlap+1;
    if (dut.row_running && cmd_valid && cmd_ready && cmd_read &&
        cmd_addr[11:0]>='h180 && cmd_addr[11:0]<='h19f) y32_overlap=y32_overlap+1;
    if (dut.row_active && (dut.u_linear_compute_core.io_wLoadWen ||
        dut.u_linear_compute_core.io_xLoadWen || dut.u_linear_compute_core.io_cacheWriteEnable))
      $fatal(1,"operand write escaped row ownership");
    if (dut.row_count>2 || dut.row_produced-dut.row_retired!=dut.row_count)
      $fatal(1,"FIFO conservation failed");
  end

  task automatic transfer(input bit reading,input [11:0] offset,input [31:0] data,
                          input [3:0] mask,input bit error_expected,input integer stall,
                          output [31:0] result);
    integer timeout, saved_retired, saved_group, head_lane;
    reg saved_valid, saved_head;
    reg [31:0] held;
    reg [47:0] held_head [0:7];
    begin
      @(negedge clk); mmio_valid=1; mmio_read=reading; mmio_addr={20'h10042,offset};
      mmio_data=data; mmio_mask=mask; mmio_rsp_ready=0;
      @(posedge clk);
      while (!cmd_ready) @(posedge clk);
      #1;
      saved_retired=dut.row_retired;
      saved_valid=dut.row_valid;
      saved_head=dut.u_linear_compute_core.head;
      saved_group=dut.row_group;
      for(head_lane=0;head_lane<8;head_lane=head_lane+1)
        held_head[head_lane]=dut.row_result[head_lane];
      @(negedge clk); mmio_valid=0; mmio_addr=32'hdeadbeef; mmio_data=32'hbad0cafe;
      mmio_mask=0; mmio_read=1;
      timeout=0;
      while (!rsp_valid) begin
        @(posedge clk); #1; timeout=timeout+1;
        if (timeout>8) $fatal(1,"response timeout offset=%h",offset);
      end
      if (rsp_err!==error_expected) $fatal(1,"error mismatch offset=%h",offset);
      held=rsp_rdata;
      repeat(stall) begin
        @(posedge clk); #1;
        if (!rsp_valid || rsp_err!==error_expected || rsp_rdata!==held || cmd_ready)
          $fatal(1,"response changed under backpressure offset=%h",offset);
        if(saved_valid && dut.row_active) begin
          if(dut.u_linear_compute_core.head!==saved_head || dut.row_group!==saved_group)
            $fatal(1,"FIFO head moved before response retirement offset=%h",offset);
          for(head_lane=0;head_lane<8;head_lane=head_lane+1)
            if(dut.row_result[head_lane]!==held_head[head_lane])
              $fatal(1,"FIFO owned result changed before retirement lane=%0d",head_lane);
        end
        if(dut.row_retired!=saved_retired && !(offset=='hc0 && !reading && !error_expected)) $fatal(1,"POP occurred before response retirement");
      end
      result=held;
      @(negedge clk); mmio_rsp_ready=1;
      @(posedge clk); #1;
      if (((!reading && offset=='hc8) || (reading && offset=='h1a0)) && !error_expected) begin
        if(dut.row_retired!=saved_retired+1) $fatal(1,"POP response did not retire exactly once");
        if(reading) alias_pops=alias_pops+1; else explicit_pops=explicit_pops+1;
      end else if(dut.row_retired!=saved_retired &&
                  !(offset=='hc0 && !reading && !error_expected))
        $fatal(1,"ordinary/failed access changed retired count offset=%h saved=%0d current=%0d",
          offset,saved_retired,dut.row_retired);
      @(negedge clk); mmio_rsp_ready=0;
    end
  endtask
  task automatic put(input [11:0] offset,input [31:0] data,input [3:0] mask,input bit err);
    reg [31:0] ignored;
    begin transfer(0,offset,data,mask,err,0,ignored); end
  endtask
  task automatic get(input [11:0] offset,input [31:0] word,input integer stall);
    reg [31:0] actual;
    begin
      transfer(1,offset,0,0,0,stall,actual);
      if(actual!==word) $fatal(1,"read mismatch offset=%h got=%h expected=%h",offset,actual,word);
    end
  endtask
  task automatic wait_valid;
    integer polls;
    reg [31:0] status;
    begin
      polls=0; status=0;
      while(!status[1]) begin
        transfer(1,'hc4,0,0,0,0,status); polls=polls+1;
        if(polls>40) $fatal(1,"FIFO producer timeout");
      end
    end
  endtask


  reg previous_valid=0;
  reg [287:0] held_bundle;
  integer previous_group=0;
  always @(posedge clk) if(rst_n) begin
    ticks=ticks+1;
    if(previous_valid && {xu_direct_status,xu_direct_payload}!==held_bundle)
      $fatal(1,"direct valid bundle changed under backpressure");
    previous_valid=xu_direct_valid && !xu_direct_ready;
    held_bundle={xu_direct_status,xu_direct_payload};
    if(xu_direct_valid && xu_direct_ready) begin
      if(dut.row_retired!==xu_direct_status[10:6] || direct_pops!=snapshots)
        $fatal(1,"bundle ownership/order mismatch");
      for(integer l=0;l<8;l=l+1) begin
        if(xu_direct_payload[32*l +: 32]!==rne_reference(expected(0,snapshots,l)))
          $fatal(1,"direct payload differs from real MAC oracle group=%0d lane=%0d",snapshots,l);
        // Reach real domain endpoints and both signs/parities of RNE ties.
        // This uses actual uploaded W/X/bias and MAC output, without force.
        if(expected(0,snapshots,l)==-64'sd618473193472) legal_min_seen=legal_min_seen+1;
        if(expected(0,snapshots,l)==64'sd618475290623) legal_max_seen=legal_max_seen+1;
        if((expected(0,snapshots,l)&64'sd511)==64'sd256) begin
          if(expected(0,snapshots,l)<0) negative_ties=negative_ties+1;
          else positive_ties=positive_ties+1;
          if((expected(0,snapshots,l)>>>9)&1) odd_ties=odd_ties+1;
          else even_ties=even_ties+1;
        end
      end
      snapshots=snapshots+1;
    end
    if(dut.direct_row_pop) begin
      if(snapshots!=direct_pops+1 || nice.state!==8)
        $fatal(1,"POP before all NICE snapshot registers captured");
      for(integer l=0;l<8;l=l+1)
        if(nice.snapshot[l]!==rne_reference(expected(0,direct_pops,l)))
          $fatal(1,"POP before NICE lane %0d captured",l);
      direct_pops=direct_pops+1;
    end
    if(nice_cmd_valid && nice_cmd_ready && !nice_cmd_read) begin
      if(direct_pops!=snapshots || nice_cmd_addr!==32'ha0020000+4*writes ||
         nice_cmd_data!==rne_reference(expected(0,writes/8,writes%8)) || nice_cmd_size!==2)
        $fatal(1,"Y write before POP or wrong frozen snapshot index=%0d",writes);
      write_pending=1;
      response_delay=2+(ticks%7);
      write_error=(writes%8==fail_lane);
      writes=writes+1;
    end else if(write_pending) begin
      if(response_delay>0) response_delay=response_delay-1;
      else if(nice_bus_ready) begin
        write_pending=0;
        write_responses=write_responses+1;
      end
    end
    if(nice_rsp_valid && nice_rsp_ready) completions=completions+1;
  end

  task automatic run_drain(input integer group_id,input integer error_lane);
    integer guard,before_writes,expected_writes;
    reg [32:0] held_completion;
    begin
      manual=0;fail_lane=error_lane;
      before_writes=writes;
      expected_writes=error_lane<0 ? 8 : error_lane+1;
      @(negedge clk);nice_req_valid=1;nice_req_rs1=32'ha0020000+32*group_id;
      nice_req_rs2=(128<<5)|group_id;
      @(posedge clk);if(!nice_req_ready) $fatal(1,"direct NICE instruction rejected");
      @(negedge clk);nice_req_valid=0;
      guard=0;
      while(!xu_direct_valid) begin
        @(negedge clk);guard=guard+1;
        if(guard>1000) $fatal(1,"direct bundle timeout");
      end
      if(group_id==0) begin
        // Claim rejects MMIO aliases and explicit POP; held bundle cannot move.
        manual=1;
        transfer(1,'h1a0,0,0,1,9,response);
        transfer(1,'h180,0,0,1,9,response);
        transfer(0,'hc8,1,15,1,9,response);
        manual=0;
      end
      repeat(11) @(negedge clk);
      if(dut.row_retired!=group_id || direct_pops!=group_id)
        $fatal(1,"bundle stall POPped FIFO");
      allow_bundle=1;
      @(posedge clk);#1;
      @(negedge clk);allow_bundle=0;
      repeat(13) @(negedge clk);
      if(dut.row_retired!=group_id || nice.state!==8 || nice_cmd_valid)
        $fatal(1,"commit stall failed to own complete snapshot");
      allow_commit=1;
      @(posedge clk);#1;
      @(negedge clk);allow_commit=0;
      guard=0;
      while(!nice_rsp_valid) begin
        @(negedge clk);guard=guard+1;
        if(guard>1000) $fatal(1,"NICE Y write/completion timeout");
      end
      if(writes-before_writes!=expected_writes || writes!=write_responses ||
          nice_rsp_data!==(error_lane<0 ? 0 : 8) || nice_rsp_err!==(error_lane>=0))
        $fatal(1,"direct completion or first-error stop mismatch");
      held_completion={nice_rsp_err,nice_rsp_data};
      repeat(17) begin
        @(negedge clk);
        if(!nice_rsp_valid || {nice_rsp_err,nice_rsp_data}!==held_completion || nice_cmd_valid)
          $fatal(1,"completion changed under CPU backpressure or issued post-error command");
      end
      nice_rsp_ready=1;
      @(posedge clk);#1;
      @(negedge clk);nice_rsp_ready=0;
    end
  endtask

  initial begin
    repeat(4) @(negedge clk);rst_n=1;
    get('hf0,32'h59440001,2);
    put('hf4,1,15,0);
    if(!xu_direct_capable) $fatal(1,"direct mode not enabled");
    put('h054,0,15,0);
    for(s=0;s<16384;s=s+2)
      put('h05c,{wv((s%256)/8,(s+1)%8,s/256),wv((s%256)/8,s%8,s/256)},15,0);
    row=0;
    put('h060,0,15,0);
    for(k=0;k<64;k=k+2) put('h068,{xv(row,k+1),xv(row,k)},15,0);
    put('h040,0,15,0);
    for(col=0;col<256;col=col+1) begin
      value=bv(row,col);
      put('h044,col,15,0);put('h048,value[31:0],15,0);put('h04c,{24'b0,value[39:32]},15,0);
    end
    put('h040,1,15,0);put('hc0,1,15,0);wait_valid();
    if ($value$plusargs("RESET_PHASE=%d",reset_phase)) begin
      manual=0;
      @(negedge clk);nice_req_valid=1;nice_req_rs1=32'ha0020000;nice_req_rs2=(128<<5);
      @(posedge clk);if(!nice_req_ready)$fatal(1,"reset fixture request not accepted");
      @(negedge clk);nice_req_valid=0;
      if(reset_phase==1) wait(dut.direct_state==1);
      else if(reset_phase==2) wait(dut.direct_state==2);
      else begin
        allow_bundle=1;
        wait(dut.direct_state==3);
      end
      @(negedge clk);rst_n=0;allow_bundle=0;
      repeat(4)@(negedge clk);
      if(xu_direct_capable || xu_direct_valid || xu_direct_commit_ready || dut.row_pop ||
          xu_direct_claim || nice_direct_commit || nice_cmd_valid || nice_rsp_valid || !nice_req_ready)
        $fatal(1,"common reset retained stale direct ownership phase=%0d",reset_phase);
      rst_n=1;manual=1;
      get('hf4,0,3);get('he4,32'h59330001,2);
      if(dut.direct_state!=0 || xu_direct_valid || xu_direct_capable)
        $fatal(1,"direct mode not reset-disabled");
      $display("DIRECT_RESET_PASS phase=%0d mode_disabled=1 stale_bundle=0 stale_pop=0",reset_phase);
      $finish;
    end
    for(g=0;g<32;g=g+1) run_drain(g,-1);
    if(starts!=16 || dones!=16) $fatal(1,"PE16 physical pair count wrong");
    if(snapshots!=32 || direct_pops!=32 || writes!=256 || completions!=32 || dut.row_active)
      $fatal(1,"incomplete real row direct coverage");
    if(legal_min_seen!=32 || legal_max_seen!=32 || positive_ties!=75 || negative_ties!=75 ||
        even_ties!=75 || odd_ties!=75)
      $fatal(1,"direct real RNE domain/tie coverage missing");
    $display("DIRECT_REAL_NUMERIC_PASS legal_min=%0d legal_max=%0d positive_ties=%0d negative_ties=%0d even_ties=%0d odd_ties=%0d force_used=0",
      legal_min_seen,legal_max_seen,positive_ties,negative_ties,even_ties,odd_ties);
    // A second real row injects a shared-write error after POP. No retries:
    // task aborts at the first error and issues no further shared Y writes.
    manual=1;put('hc0,1,15,0);wait_valid();
    // Reset counters only for row-indexed assertions and destination checks.
    snapshots=0;direct_pops=0;writes=0;write_responses=0;
    run_drain(0,3);
    if(writes!=4 || direct_pops!=1 || snapshots!=1 || completions!=33)
      $fatal(1,"write-error coverage missing");
    $display("DIRECT_WRAPPER_PASS real_groups=32 real_y32_lanes=256 mmio_conflicts=3 bundle_stall=11 commit_stall=13 shared_write_error_lane=3 completion_stall=17");
    $finish;
  end
  initial begin #30000000;$fatal(1,"direct fixture timeout");end
endmodule
