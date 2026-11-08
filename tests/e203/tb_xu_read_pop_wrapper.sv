`timescale 1ns/1ps
module tb_xu_read_pop_wrapper;
  reg clk=0;
  always #5 clk=~clk;
  reg rst_n=0, cmd_valid=0, cmd_read=0, rsp_ready=0;
  reg [31:0] cmd_addr=0, cmd_wdata=0;
  reg [3:0] cmd_wmask=0;
  wire cmd_ready, rsp_valid, rsp_err;
  wire [31:0] rsp_rdata;
  accel_icb_slave dut(.*);
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
      if(dut.row_active) next_group=next_group+1;
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
      @(negedge clk); cmd_valid=1; cmd_read=reading; cmd_addr={20'h10042,offset};
      cmd_wdata=data; cmd_wmask=mask; rsp_ready=0;
      @(posedge clk);
      while (!cmd_ready) @(posedge clk);
      #1;
      saved_retired=dut.row_retired;
      saved_valid=dut.row_valid;
      saved_head=dut.u_linear_compute_core.head;
      saved_group=dut.row_group;
      for(head_lane=0;head_lane<8;head_lane=head_lane+1)
        held_head[head_lane]=dut.row_result[head_lane];
      @(negedge clk); cmd_valid=0; cmd_addr=32'hdeadbeef; cmd_wdata=32'hbad0cafe;
      cmd_wmask=0; cmd_read=1;
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
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      if (((!reading && offset=='hc8) || (reading && offset=='h1a0)) && !error_expected) begin
        if(dut.row_retired!=saved_retired+1) $fatal(1,"POP response did not retire exactly once");
        if(reading) alias_pops=alias_pops+1; else explicit_pops=explicit_pops+1;
      end else if(dut.row_retired!=saved_retired &&
                  !(offset=='hc0 && !reading && !error_expected))
        $fatal(1,"ordinary/failed access changed retired count offset=%h saved=%0d current=%0d",
          offset,saved_retired,dut.row_retired);
      @(negedge clk); rsp_ready=0;
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

  // This is an isolated wrapper/core fixture, not CPU/LSU reachability or a
  // performance result. Forced cases below only diagnose interface guards and
  // numeric assertions; all normal row values are produced by the real MACs.
  task automatic alias_rejections;
    integer byte_offset;
    reg [31:0] ignored;
    begin
      for(byte_offset='h1a0;byte_offset<='h1a3;byte_offset=byte_offset+1) begin
        transfer(0,byte_offset,32'hdeadbeef,15,1,5,ignored);
        if(byte_offset!='h1a0) transfer(1,byte_offset,0,0,1,3,ignored);
      end
    end
  endtask

  initial begin
    repeat(4) @(negedge clk); rst_n=1;
    get('he4,32'h59330001,2);
    transfer(1,'h1a0,0,0,1,7,response); // Naturally inactive and empty.
    alias_rejections();
    put('h054,0,15,0);
    for(s=0;s<16384;s=s+2)
      put('h05c,{wv((s%256)/8,(s+1)%8,s/256),wv((s%256)/8,s%8,s/256)},15,0);
    row=0;
    put('h060,0,15,0);
    for(k=0;k<64;k=k+2) put('h068,{xv(row,k+1),xv(row,k)},15,0);
    put('h040,0,15,0);
    for(col=0;col<256;col=col+1) begin
      value=bv(row,col);
      put('h044,col,15,0); put('h048,value[31:0],15,0); put('h04c,{24'b0,value[39:32]},15,0);
    end
    put('h040,1,15,0);
    put('hc0,1,15,0);
    if(!dut.row_active || dut.row_valid) $fatal(1,"active/empty alias guard precondition");
    transfer(1,'h1a0,0,0,1,5,response); // Active but not yet a valid head.
    wait_valid();
    repeat(200) @(negedge clk);
    if(!dut.row_active || dut.row_count!=2 || dut.row_running ||
       dut.u_linear_compute_core.head!==1'b0) $fatal(1,"full FIFO fixture precondition");
    alias_rejections();

    // Isolated invalid-state/illegal-input diagnostics, explicitly separated
    // from the arithmetic checks. These mutate no production core source.
    force dut.row_active=1'b0;
    if(!dut.row_valid) $fatal(1,"inactive/valid guard diagnostic precondition");
    transfer(1,'h1a0,0,0,1,5,response);
    release dut.row_active;
    if($test$plusargs("ALIAS_BAD_HIGH")) begin
      force dut.u_linear_compute_core.results_0_7=48'sd618475290624;
      get('h1a0,0,0); $fatal(1,"missing alias high range assertion");
    end
    if($test$plusargs("ALIAS_BAD_LOW")) begin
      force dut.u_linear_compute_core.results_0_7=-48'sd618473193473;
      get('h1a0,0,0); $fatal(1,"missing alias low range assertion");
    end
    if($test$plusargs("ALIAS_BAD_UNKNOWN")) begin
      force dut.u_linear_compute_core.results_0_7=48'hxxxxxxxxxxxx;
      get('h1a0,0,0); $fatal(1,"missing alias unknown assertion");
    end
    if($test$plusargs("ALIAS_LEGAL_EXTREMES")) begin
      force dut.u_linear_compute_core.results_0_7=-48'sd618473193472;
      get('h1a0,-32'sd1207955456,5);
      release dut.u_linear_compute_core.results_0_7;
      force dut.u_linear_compute_core.results_1_7=48'sd618475290623;
      get('h1a0,32'sd1207959552,7);
      release dut.u_linear_compute_core.results_1_7;
      if(alias_pops!=2 || pop_events!=2) $fatal(1,"alias legal extremes POP mismatch");
      $display("READ_POP_ALIAS_INTERFACE_DIAGNOSTIC_PASS forced_legal_extremes_not_mac_results=2");
      $finish;
    end

    for(g=0;g<32;g=g+1) begin
      wait_valid();
      if(dut.row_group!=g || dut.row_retired!=g) $fatal(1,"next FIFO head metadata wrong");
      for(lane=0;lane<7;lane=lane+1) begin
        value=expected(0,g,lane);
        get('h180+4*lane,rne_reference(value),lane==0 ? 3 : 0);
        numeric_y32_reads=numeric_y32_reads+1;
      end
      // The old lane7 remains repeatable and side-effect free.
      value=expected(0,g,7);
      get('h19c,rne_reference(value),11);
      get('h19c,rne_reference(value),4);
      if(dut.row_retired!=g) $fatal(1,"ordinary lane7 read unexpectedly popped");
      // Read the same eighth value through the alias. The transfer helper
      // verifies response/head stability throughout stall and exactly one POP
      // at retirement. Vary head/tail so both backing slots are exercised.
      get('h1a0,rne_reference(value),g%2==0 ? 180 : 7);
      if(dut.row_retired!=g+1 || (g!=31 && dut.row_group!=(g+1)%32))
        $fatal(1,"alias did not advance to the correct next head");
      repeat(3) @(negedge clk);
      if(dut.row_retired!=g+1 || dut.rsp_row_pop) $fatal(1,"alias replayed a retired POP");
    end
    if(dut.row_active || dut.row_valid || dut.row_count || dut.row_retired!=32 ||
       starts!=32 || dones!=32 || alias_pops!=32 || explicit_pops!=0 || pop_events!=32)
      $fatal(1,"alias row conservation mismatch");
    transfer(1,'h1a0,0,0,1,4,response);
    transfer(1,'h19c,0,0,1,4,response);
    put('hc8,1,15,1);

    // Confirm the public explicit POP still works on a naturally produced row.
    put('hc0,1,15,0); wait_valid();
    get('h19c,rne_reference(expected(0,0,7)),5);
    transfer(0,'hc8,1,15,0,17,response);
    if(dut.row_retired!=1 || dut.row_group!=1 || explicit_pops!=1 || pop_events!=33)
      $fatal(1,"legacy POP compatibility failed");
    if(accepts!=retires) $fatal(1,"orphan or duplicated response");
    $display("READ_POP_WRAPPER_PASS alias_pops=%0d legacy_pops=%0d pop_events=%0d real_groups=32 normal_lane7_reads=64 rejected_writes_and_unaligned=1 active_empty_guard=1 inactive_valid_diagnostic=1 stable_stalled_head=1",alias_pops,explicit_pops,pop_events);
    $finish;
  end
  initial begin
    #20000000; $fatal(1,"read-pop wrapper timed out");
  end
endmodule
