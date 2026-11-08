`timescale 1ns/1ps
module tb_xu_autogroup_wrapper;
  reg clk=0;
  always #5 clk=~clk;
  reg rst_n=0, cmd_valid=0, cmd_read=0, rsp_ready=0;
  reg [31:0] cmd_addr=0, cmd_wdata=0;
  reg [3:0] cmd_wmask=0;
  wire cmd_ready, rsp_valid, rsp_err;
  wire [31:0] rsp_rdata;
  accel_icb_slave dut(.*);
  integer starts=0, dones=0, accepts=0, retires=0, overlap=0, next_group=0;
  integer row, g, lane, k, col, s, before_starts, before_dones;
  reg [31:0] response;
  reg signed [63:0] value;
  reg [47:0] raw;

  function automatic signed [15:0] xv(input integer r,input integer i);
    if (i==0) xv=-32768;
    else if (i==63) xv=32767;
    else xv=r*11+i-32;
  endfunction
  function automatic signed [15:0] wv(input integer group_id,input integer l,input integer i);
    if (i==l) wv=-32768;
    else if (i==63-l) wv=32767;
    else wv=group_id*97-l*5-i;
  endfunction
  function automatic signed [39:0] bv(input integer r,input integer c);
    if (c%2==0) bv=-40'sh8000000000+r+c;
    else bv=40'sh7fffffffff-r-c;
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
    if (dut.row_active && (dut.u_linear_compute_core.io_wLoadWen ||
        dut.u_linear_compute_core.io_xLoadWen || dut.u_linear_compute_core.io_cacheWriteEnable))
      $fatal(1,"operand write escaped row ownership");
    if (dut.row_count>2 || dut.row_produced-dut.row_retired!=dut.row_count)
      $fatal(1,"FIFO conservation failed");
  end

  task automatic transfer(input bit reading,input [11:0] offset,input [31:0] data,
                          input [3:0] mask,input bit error_expected,input integer stall,
                          output [31:0] result);
    integer timeout, saved_retired;
    reg [31:0] held;
    begin
      @(negedge clk); cmd_valid=1; cmd_read=reading; cmd_addr={20'h10042,offset};
      cmd_wdata=data; cmd_wmask=mask; rsp_ready=0;
      @(posedge clk);
      while (!cmd_ready) @(posedge clk);
      #1;
      saved_retired=dut.row_retired;
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
  // A cold synchronous bias group can extend manual START. Wait for the
  // original STATUS contract; keep all value, FIFO and response assertions.
  task automatic wait_manual_done;
    time begun;
    reg [31:0] status;
    begin
      begun=$time; status=0;
      while(status!==32'd2) begin
        transfer(1,'h00c,0,0,0,0,status);
        if($time-begun>1500) $fatal(1,"manual SRAM-backed computation exceeded 150 cycles");
      end
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
      @(negedge clk); cmd_valid=1; cmd_read=next_command==1;
      cmd_addr=next_command==1 ? 32'h10042100 :
               (next_command==2 ? 32'h100420c0 : 32'h100420c8);
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

  initial begin
    repeat(4) @(negedge clk); rst_n=1;
    get('h050,32'h58550003,2); get('h070,32'h58530003,2);
    get('h074,32'h58500003,2); get('h078,32'h58410001,2);
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
      for(g=0;g<32;g=g+1) begin
        wait_valid();
        if(dut.row_group!=g || dut.row_retired!=g) $fatal(1,"head metadata changed early");
        for(lane=0;lane<8;lane=lane+1) begin
          value=expected(row,g,lane); raw=value[47:0];
          get('h100+lane*8,raw[31:0],(g==0 && lane==0)?100:0);
          get('h104+lane*8,{16'b0,raw[47:32]},0);
        end
        put('hc8,0,15,1); put('hc8,1,1,1);
        if(g==0) collide_pop_retirement(row==0 ? 1 : 0);
        else if(g==31) collide_pop_retirement(2);
        else transfer(0,'hc8,1,15,0,(g%7==0)?170:0,response);
      end
      if(dut.row_active || dut.row_count!=0 || dut.row_retired!=32 || dut.row_produced!=32 ||
          starts!=before_starts+32 || dones!=before_dones+32)
        $fatal(1,"row did not retire exactly 32 groups");
      put('hc8,1,15,1); transfer(1,'h100,0,0,1,2,response);
    end
    if(overlap==0) $fatal(1,"no real compute/readback overlap observed");
    // Manual one-group meaning, read windows and cache selections remain valid.
    put('h010,19,15,0); put('h00c,2,15,0); put('h008,1,15,0);
    wait_manual_done();
    for(lane=0;lane<8;lane=lane+1) begin
      value=expected(1,19,lane); raw=value[47:0];
      get('h080+lane*8,raw[31:0],0); get('h084+lane*8,{16'b0,raw[47:32]},0);
    end
    get('h00c,2,0);
    if(accepts!=retires) $fatal(1,"orphan/duplicate response");
    // Reset is the only abort: pending results disappear and cache selection
    // resets. Storage data is deliberately not claimed to have been cleared.
    final_pop_immediate_restart();
    if(accepts!=retires) $fatal(1,"restart sequence lost a response");
    if(starts!=99 || dones!=99) $fatal(1,"unexpected complete/aborted-row work count");
    if(dut.row_count!=2) $fatal(1,"reset-abort precondition");
    rst_n=0;
    repeat(4) @(negedge clk);
    rst_n=1;
    if(dut.row_active || dut.row_valid || dut.row_count || dut.row_retired ||
        dut.row_produced || dut.cache_enable || dut.rsp_row_pop)
      $fatal(1,"reset did not abort autonomous state");
    $display("XU_AUTOGROUP_WRAPPER_PASS rows=2 groups=64 lanes=512 overlap=%0d launches=%0d dones=%0d accepted=%0d retired=%0d",
      overlap,starts,dones,accepts,retires);
    $finish;
  end
  initial begin #5000000; $fatal(1,"wrapper timeout"); end
endmodule
