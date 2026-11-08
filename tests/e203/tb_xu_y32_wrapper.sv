`timescale 1ns/1ps
module tb_xu_y32_wrapper;
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
  wire xu_direct_claim=0, xu_direct_ready=0, xu_direct_commit=0;
  accel_icb_slave dut(.*);
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
      if (!reading && offset=='hc8 && !error_expected && dut.row_retired!=saved_retired+1)
        $fatal(1,"POP response did not retire exactly once");
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

  task automatic collide_pop_retirement(input integer next_command);
    integer saved;
    begin
      saved=dut.row_retired;
      @(negedge clk); cmd_valid=1; cmd_read=0; cmd_addr=32'h100420c8;
      cmd_wdata=1; cmd_wmask=15; rsp_ready=0;
      @(posedge clk); #1;
      @(negedge clk); cmd_valid=0;
      repeat(170) begin
        @(posedge clk); #1;
        if(!rsp_valid || rsp_err || dut.row_retired!=saved)
          $fatal(1,"blocked POP lost its owned head");
      end
      // New commands see pre-retirement state. Reject an ambiguous head
      // read/second POP, or a new STARTROW on the final POP retirement edge.
      @(negedge clk); cmd_valid=1; cmd_read=next_command==1 || next_command==3 || next_command==4 || next_command>=5;
      cmd_addr=next_command>=5 ? 32'h10042180+4*(next_command-5) :
               (next_command==1 ? 32'h10042100 :
               (next_command==3 ? 32'h10042140 :
               (next_command==4 ? 32'h1004214c :
               (next_command==2 ? 32'h100420c0 : 32'h100420c8))));
      rsp_ready=1;
      @(posedge clk); #1;
      if(dut.row_retired!=saved+1 || !rsp_valid || !rsp_err)
        $fatal(1,"simultaneous POP retirement and head command was ambiguous");
      @(negedge clk); cmd_valid=0; rsp_ready=0;
      repeat(3) begin
        @(posedge clk); #1;
        if(!rsp_valid || !rsp_err || dut.row_retired!=saved+1)
          $fatal(1,"collision error response replayed a POP");
      end
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
    end
  endtask

  task automatic reject_start_at_legacy_commit;
    begin
      put('h014,0,15,0);
      @(negedge clk); cmd_valid=1; cmd_read=0; cmd_addr=32'h10042018;
      cmd_wdata={16'b0,xv(row,0)}; cmd_wmask=15; rsp_ready=0;
      @(posedge clk); #1;
      @(negedge clk); cmd_addr=32'h100420c0; cmd_wdata=1; rsp_ready=1;
      @(posedge clk); #1;
      if(!rsp_valid || !rsp_err || dut.row_active || dut.row_start)
        $fatal(1,"STARTROW accepted with an old load strobe in flight");
      @(negedge clk); cmd_valid=0;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
    end
  endtask

  task automatic final_pop_immediate_restart;
    integer selected_group;
    begin
      put('hc0,1,15,0);
      // Drain this row quickly to isolate the final response-slot boundary.
      for(selected_group=0;selected_group<31;selected_group=selected_group+1) begin
        wait_valid(); put('hc8,1,15,0);
      end
      wait_valid();
      @(negedge clk); cmd_valid=1; cmd_read=0; cmd_addr=32'h100420c8;
      cmd_wdata=1; cmd_wmask=15; rsp_ready=0;
      @(posedge clk); #1;
      if(!rsp_valid || rsp_err || dut.row_retired!=31) $fatal(1,"final POP precondition");
      @(negedge clk); cmd_addr=32'h100420c0; rsp_ready=1;
      @(posedge clk); #1;
      if(!rsp_valid || !rsp_err || dut.row_active || dut.row_start || dut.row_retired!=32)
        $fatal(1,"STARTROW was not rejected on the final POP retirement edge");
      // The very next edge retires that error response and accepts STARTROW.
      // Its old response metadata must not clear/pop the new row afterward.
      @(posedge clk); #1;
      if(!rsp_valid || rsp_err || !dut.row_start || dut.row_active || dut.rsp_row_pop)
        $fatal(1,"STARTROW did not succeed one edge after final POP retirement");
      @(negedge clk); cmd_valid=0; rsp_ready=0;
      repeat(200) begin
        @(posedge clk); #1;
        if(!rsp_valid || rsp_err || dut.rsp_row_pop || dut.row_retired!=0)
          $fatal(1,"previous error response corrupted new row metadata");
      end
      if(!dut.row_active || dut.row_count!=2 || dut.row_produced!=2 || dut.row_running)
        $fatal(1,"restarted row did not retain both produced slots");
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      if(dut.row_retired!=0 || dut.row_count!=2 || !dut.row_active)
        $fatal(1,"new STARTROW response retirement incorrectly popped its FIFO");
      @(negedge clk); rsp_ready=0;
    end
  endtask

  task automatic reject_paired_window;
    integer offset;
    reg [31:0] ignored;
    begin
      for(offset='h140;offset<='h14f;offset=offset+1)
        transfer(1,offset,0,0,1,offset=='h140 ? 4 : 0,ignored);
    end
  endtask

  task automatic reject_paired_mutations;
    integer offset;
    reg [31:0] ignored;
    begin
      // Every byte address is read-only. Unaligned reads inside the complete
      // new aperture must fail rather than alias an adjacent lane pair.
      for(offset='h140;offset<='h14f;offset=offset+1) begin
        put(offset,32'hdeadbeef,15,1);
        if(offset%4!=0) transfer(1,offset,0,0,1,2,ignored);
      end
    end
  endtask

  task automatic reject_y32_window;
    integer offset;
    reg [31:0] ignored;
    begin
      for(offset='h180;offset<='h19f;offset=offset+1)
        transfer(1,offset,0,0,1,offset=='h180 ? 4 : 0,ignored);
    end
  endtask

  task automatic reject_y32_mutations;
    integer offset;
    reg [31:0] ignored;
    begin
      for(offset='h180;offset<='h19f;offset=offset+1) begin
        put(offset,32'hdeadbeef,15,1);
        if(offset%4!=0) transfer(1,offset,0,0,1,2,ignored);
      end
    end
  endtask

  task automatic diagnostic_y32_snapshot;
    integer saved;
    reg [31:0] held;
    begin
      if(!dut.row_active || dut.row_count!=2 || dut.row_running ||
         dut.u_linear_compute_core.head!==1'b0)
        $fatal(1,"Y32 snapshot diagnostic requires quiescent full FIFO head zero");
      $display("XU_Y32_INTERFACE_DIAGNOSTIC_BEGIN legal_forced_fifo_patterns_not_mac_results");
      // Bad-input runs deliberately fail in the production wrapper assertion.
      if($test$plusargs("Y32_BAD_HIGH")) begin
        force dut.u_linear_compute_core.results_0_0=48'sd618475290624;
        get('h180,0,0);
        $fatal(1,"missing high range assertion");
      end
      if($test$plusargs("Y32_BAD_LOW")) begin
        force dut.u_linear_compute_core.results_0_0=-48'sd618473193473;
        get('h180,0,0);
        $fatal(1,"missing low range assertion");
      end
      if($test$plusargs("Y32_BAD_UNKNOWN")) begin
        force dut.u_linear_compute_core.results_0_0=48'hxxxxxxxxxxxx;
        get('h180,0,0);
        $fatal(1,"missing unknown input assertion");
      end
      force dut.u_linear_compute_core.results_0_0=-48'sd256;
      force dut.u_linear_compute_core.results_0_1=-48'sd768;
      force dut.u_linear_compute_core.results_0_2=48'sd256;
      force dut.u_linear_compute_core.results_0_3=48'sd768;
      force dut.u_linear_compute_core.results_0_4=-48'sd618473193472;
      force dut.u_linear_compute_core.results_0_5=48'sd618475290623;
      force dut.u_linear_compute_core.results_0_6=-48'sd257;
      force dut.u_linear_compute_core.results_0_7=48'sd257;
      get('h180,32'd0,7); get('h184,-32'sd2,4);
      get('h188,32'd0,3); get('h18c,32'd2,9);
      get('h190,-32'sd1207955456,1); get('h194,32'd1207959552,1);
      get('h198,-32'sd1,1); get('h19c,32'd1,1);
      saved=dut.row_retired;
      @(negedge clk); cmd_valid=1; cmd_read=1; cmd_addr=32'h10042180;
      cmd_wdata=0; cmd_wmask=0; rsp_ready=0;
      @(posedge clk); #1;
      if(!rsp_valid || rsp_err || rsp_rdata!==32'b0)
        $fatal(1,"Y32 snapshot acceptance failed");
      held=rsp_rdata;
      @(negedge clk); cmd_valid=0;
      force dut.u_linear_compute_core.results_0_0=48'sd618475290623;
      repeat(7) begin
        @(posedge clk); #1;
        if(!rsp_valid || rsp_err || rsp_rdata!==held || cmd_ready || dut.row_retired!=saved)
          $fatal(1,"Y32 response followed live FIFO instead of held snapshot");
      end
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
      get('h180,32'd1207959552,1);
      release dut.u_linear_compute_core.results_0_0;
      release dut.u_linear_compute_core.results_0_1;
      release dut.u_linear_compute_core.results_0_2;
      release dut.u_linear_compute_core.results_0_3;
      release dut.u_linear_compute_core.results_0_4;
      release dut.u_linear_compute_core.results_0_5;
      release dut.u_linear_compute_core.results_0_6;
      release dut.u_linear_compute_core.results_0_7;
      force dut.row_active=1'b0;
      if(!dut.row_valid) $fatal(1,"Y32 inactive/valid diagnostic precondition");
      reject_y32_window();
      release dut.row_active;
      $display("XU_Y32_INTERFACE_DIAGNOSTIC_PASS signed_ties_legal_extremes_snapshot_inactive_guard");
    end
  endtask

  task automatic diagnostic_extreme_interface;
    integer saved;
    reg [31:0] held;
    begin
      // This isolated stage injects interface patterns into the *existing*
      // Chisel FIFO slots after all real MAC checks. A signed-48 minimum is
      // outside the range of 64 int16 products plus int40 bias, so these
      // values are not claimed as arithmetic results.
      if(!dut.row_active || dut.row_count!=2 || dut.row_running ||
         dut.u_linear_compute_core.head!==1'b0)
        $fatal(1,"extreme interface diagnostic requires quiescent full FIFO head zero");
      $display("XU_PAIRED_HI_INTERFACE_DIAGNOSTIC_BEGIN forced_fifo_patterns_not_mac_results");
      force dut.u_linear_compute_core.results_0_0=48'h800000000000;
      force dut.u_linear_compute_core.results_0_1=48'h7fffffffffff;
      force dut.u_linear_compute_core.results_0_2=48'hffffffffffff;
      force dut.u_linear_compute_core.results_0_3=48'h000000000000;
      force dut.u_linear_compute_core.results_0_4=48'h123456789abc;
      force dut.u_linear_compute_core.results_0_5=48'hfedcba987654;
      force dut.u_linear_compute_core.results_0_6=48'h7fff76543210;
      force dut.u_linear_compute_core.results_0_7=48'h800089abcdef;
      get('h140,32'h7fff8000,7);
      get('h144,32'h0000ffff,4);
      get('h148,32'hfedc1234,3);
      get('h14c,32'h80007fff,9);
      // The old high-half window must remain zero extended for signed values.
      get('h104,32'h00008000,2); get('h10c,32'h00007fff,0);
      get('h114,32'h0000ffff,0); get('h11c,32'h00000000,0);
      get('h124,32'h00001234,0); get('h12c,32'h0000fedc,0);
      get('h134,32'h00007fff,0); get('h13c,32'h00008000,2);
      get('h100,32'h00000000,0); get('h108,32'hffffffff,0);
      get('h130,32'h76543210,0); get('h138,32'h89abcdef,0);
      saved=dut.row_retired;
      @(negedge clk); cmd_valid=1; cmd_read=1; cmd_addr=32'h10042140;
      cmd_wdata=0; cmd_wmask=0; rsp_ready=0;
      @(posedge clk); #1;
      if(!rsp_valid || rsp_err || rsp_rdata!==32'h7fff8000)
        $fatal(1,"diagnostic paired snapshot acceptance failed");
      held=rsp_rdata;
      @(negedge clk); cmd_valid=0;
      // Change the real backing slots only after the response captured them.
      force dut.u_linear_compute_core.results_0_0=48'h000012345678;
      force dut.u_linear_compute_core.results_0_1=48'hffff87654321;
      repeat(7) begin
        @(posedge clk); #1;
        if(!rsp_valid || rsp_err || rsp_rdata!==held || cmd_ready || dut.row_retired!=saved)
          $fatal(1,"paired response followed live FIFO instead of held snapshot");
      end
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
      get('h140,32'hffff0000,1);
      release dut.u_linear_compute_core.results_0_0;
      release dut.u_linear_compute_core.results_0_1;
      release dut.u_linear_compute_core.results_0_2;
      release dut.u_linear_compute_core.results_0_3;
      release dut.u_linear_compute_core.results_0_4;
      release dut.u_linear_compute_core.results_0_5;
      release dut.u_linear_compute_core.results_0_6;
      release dut.u_linear_compute_core.results_0_7;
      // Prove the explicit rowActive guard even with an invalid but isolated
      // forced state (valid FIFO while inactive); manual mode below is natural.
      force dut.u_linear_compute_core.active=1'b0;
      if(!dut.row_valid) $fatal(1,"inactive/valid diagnostic precondition");
      reject_paired_window();
      release dut.u_linear_compute_core.active;
      $display("XU_PAIRED_HI_INTERFACE_DIAGNOSTIC_PASS signed48_extremes_snapshot_inactive_guard");
    end
  endtask

  initial begin
    repeat(4) @(negedge clk); rst_n=1;
    get('h050,32'h58550003,2); get('h070,32'h58530003,2);
    get('h074,32'h58500003,2); get('h078,32'h58410001,2);
    get('he0,32'h58480001,4); get('he4,32'h59330001,4);
    // Capability writes follow the historical ignored-write convention.
    put('he0,32'hffffffff,15,0); get('he0,32'h58480001,0);
    put('he4,32'hffffffff,15,0); get('he4,32'h59330001,0);
    reject_paired_window(); reject_paired_mutations();
    reject_y32_window(); reject_y32_mutations();
    put('hc0,1,15,1); // Cache must be enabled.
    put('hc8,1,15,1);
    transfer(1,'h100,0,0,1,4,response); // Empty reads are errors, no side effect.
    put('h054,0,15,0);
    for(s=0;s<16384;s=s+2)
      put('h05c,{wv((s%256)/8,(s+1)%8,s/256),wv((s%256)/8,s%8,s/256)},15,0);
    for(row=0;row<2;row=row+1) begin
      put('h060,0,15,0);
      for(k=0;k<64;k=k+2) put('h068,{xv(row,k+1),xv(row,k)},15,0);
      put('h040,0,15,0);
      for(col=0;col<256;col=col+1) begin
        value=bv(row,col);
        put('h044,col,15,0); put('h048,value[31:0],15,0); put('h04c,{24'b0,value[39:32]},15,0);
      end
      put('h040,1,15,0);
      put('hc0,1,7,1); put('hc0,0,15,1); put('hc0,3,15,1);
      reject_start_at_legacy_commit();
      before_starts=starts; before_dones=dones;
      // Start-response backpressure does not stop the producer. Exactly two
      // groups complete, then full FIFO stops all further core launches.
      transfer(0,'hc0,1,15,0,240,response);
      if(dut.row_count!=2 || starts!=before_starts+2 || dones!=before_dones+2 || dut.row_running)
        $fatal(1,"two-slot full backpressure failed");
      repeat(90) @(negedge clk);
      if(starts!=before_starts+2) $fatal(1,"producer overwrote full FIFO");
      // Every legacy operand/config write and stream write is excluded.
      for(s='h010;s<='h030;s=s+4) put(s,32'hdeadbeef,15,1);
      for(s='h040;s<='h04c;s=s+4) put(s,32'hdeadbeef,15,1);
      for(s='h054;s<='h068;s=s+4) put(s,0,15,1);
      put('hc0,1,15,1); // STARTROW while active has no effect.
      put('h008,1,15,0); // Historical manual START while busy is ignored.
      reject_paired_mutations(); reject_y32_mutations();
      for(g=0;g<32;g=g+1) begin
        wait_valid();
        if(dut.row_group!=g || dut.row_retired!=g) $fatal(1,"head metadata changed early");
        for(pair_id=0;pair_id<4;pair_id=pair_id+1) begin
          value=expected(row,g,2*pair_id); paired_even=value[47:0];
          value=expected(row,g,2*pair_id+1); paired_odd=value[47:0];
          get('h140+4*pair_id,{paired_odd[47:32],paired_even[47:32]},
              (g==0 && pair_id==0)?100:((g==31 && pair_id==3)?7:0));
          numeric_paired_reads=numeric_paired_reads+1;
        end
        for(lane=0;lane<8;lane=lane+1) begin
          value=expected(row,g,lane); raw=value[47:0];
          get('h180+lane*4,rne_reference(value),(g==0 && lane==0)?100:((g==31 && lane==7)?7:0));
          numeric_y32_reads=numeric_y32_reads+1;
          if(value==-64'sd618473193472) legal_min_seen=legal_min_seen+1;
          if(value==64'sd618475290623) legal_max_seen=legal_max_seen+1;
          magnitude=value<0 ? -value : value;
          trunc_quotient=magnitude/512;
          if(magnitude%512==256) begin
            if(value<0) negative_ties=negative_ties+1;
            else positive_ties=positive_ties+1;
            if(trunc_quotient[0]) odd_ties=odd_ties+1;
            else even_ties=even_ties+1;
          end
          get('h100+lane*8,raw[31:0],(g==0 && lane==0)?100:0);
          get('h104+lane*8,{16'b0,raw[47:32]},0);
          numeric_lanes=numeric_lanes+1;
          if(value<0) numeric_negative=numeric_negative+1;
          else numeric_nonnegative=numeric_nonnegative+1;
        end
        put('hc8,0,15,1); put('hc8,1,1,1);
        if(g<8) collide_pop_retirement(5+g);
        else if(g==8) collide_pop_retirement(row==0 ? 3 : 0);
        else if(g==9) collide_pop_retirement(row==0 ? 1 : 4);
        else if(g==31) collide_pop_retirement(2);
        else transfer(0,'hc8,1,15,0,(g%7==0)?170:0,response);
      end
      if(dut.row_active || dut.row_count!=0 || dut.row_retired!=32 || dut.row_produced!=32 ||
          starts!=before_starts+32 || dones!=before_dones+32)
        $fatal(1,"row did not retire exactly 32 groups");
      put('hc8,1,15,1); transfer(1,'h100,0,0,1,2,response);
      reject_paired_window(); reject_y32_window();
    end
    if(numeric_paired_reads!=256 || numeric_lanes!=512 || numeric_negative!=256 || numeric_nonnegative!=256)
      $fatal(1,"real MAC coverage count mismatch");
    if(numeric_y32_reads!=512 || positive_ties==0 || negative_ties==0 ||
        even_ties==0 || odd_ties==0 || legal_min_seen==0 || legal_max_seen==0)
      $fatal(1,"real Y32 numeric coverage count mismatch");
    if(y32_overlap==0) $fatal(1,"no real compute/Y32 overlap observed");
    if(overlap==0 || paired_overlap==0) $fatal(1,"no real compute/readback overlap observed");
    // Manual one-group meaning, read windows and cache selections remain valid.
    put('h010,19,15,0); put('h00c,2,15,0); put('h008,1,15,0);
    reject_paired_window(); reject_y32_window(); // Natural manual mode cannot expose row data.
    repeat(80) @(negedge clk);
    for(lane=0;lane<8;lane=lane+1) begin
      value=expected(1,19,lane); raw=value[47:0];
      get('h080+lane*8,raw[31:0],0); get('h084+lane*8,{16'b0,raw[47:32]},0);
    end
    get('h00c,2,0); reject_paired_window(); reject_y32_window();
    if(accepts!=retires) $fatal(1,"orphan/duplicate response");
    // Reset is the only abort: pending results disappear and cache selection
    // resets. Storage data is deliberately not claimed to have been cleared.
    final_pop_immediate_restart();
    if(accepts!=retires) $fatal(1,"restart sequence lost a response");
    if(starts!=99 || dones!=99) $fatal(1,"unexpected complete/aborted-row work count");
    if(dut.row_count!=2) $fatal(1,"reset-abort precondition");
    diagnostic_y32_snapshot();
    diagnostic_extreme_interface();
    if(accepts!=retires) $fatal(1,"diagnostic left an orphan response");
    rst_n=0;
    repeat(4) @(negedge clk);
    rst_n=1;
    if(dut.row_active || dut.row_valid || dut.row_count || dut.row_retired ||
        dut.row_produced || dut.cache_enable || dut.rsp_row_pop)
      $fatal(1,"reset did not abort autonomous state");
    $display("XU_Y32_WRAPPER_PASS real_y32_reads=%0d positive_ties=%0d negative_ties=%0d even_ties=%0d odd_ties=%0d legal_min_seen=%0d legal_max_seen=%0d y32_overlap=%0d",
      numeric_y32_reads,positive_ties,negative_ties,even_ties,odd_ties,legal_min_seen,legal_max_seen,y32_overlap);
    $display("XU_Y32_LEGACY_WRAPPER_PASS real_rows=2 real_groups=64 real_lanes=%0d real_paired_reads=%0d negative=%0d nonnegative=%0d overlap=%0d paired_overlap=%0d launches=%0d dones=%0d accepted=%0d retired=%0d",
      numeric_lanes,numeric_paired_reads,numeric_negative,numeric_nonnegative,overlap,paired_overlap,starts,dones,accepts,retires);
    $finish;
  end
  initial begin #5000000; $fatal(1,"wrapper timeout"); end
endmodule
