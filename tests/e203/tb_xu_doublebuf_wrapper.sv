`timescale 1ns/1ps
module tb_xu_doublebuf_wrapper;
  reg clk=0;
  always #5 clk=~clk;
  reg rst_n=0, cmd_valid=0, cmd_read=0, rsp_ready=0;
  reg [31:0] cmd_addr=0, cmd_wdata=0;
  reg [3:0] cmd_wmask=0;
  wire cmd_ready, rsp_valid, rsp_err;
  wire [31:0] rsp_rdata;
  accel_icb_slave dut(.*);
  integer starts=0, dones=0, accepts=0, retires=0, overlap=0, x_overlap=0, pops=0;
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
      total=bv(0,8*group_id+l);
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
    if (dut.compute_start) starts=starts+1;
    if (dut.core_done) dones=dones+1;
    if (dut.db_pop) pops=pops+1;
    if (dut.db_running && cmd_valid && cmd_ready && cmd_read &&
        cmd_addr[11:0]>='h200 && cmd_addr[11:0]<='h23c) overlap=overlap+1;
    if (dut.db_running && dut.u_linear_compute_core.io_dbXLoadWen) x_overlap=x_overlap+1;
    if (dut.db_count>2 || dut.db_outstanding>2 || dut.db_queued>2)
      $fatal(1,"double-buffer capacity exceeded");
    if (dut.u_linear_compute_core.io_dbXLoadWen &&
        !dut.db_bank_free[dut.u_linear_compute_core.io_dbXLoadBank])
      $fatal(1,"X write escaped descriptor ownership");
    if (dut.db_outstanding && (dut.u_linear_compute_core.io_wLoadWen ||
        dut.u_linear_compute_core.io_cacheWriteEnable))
      $fatal(1,"single W/bias array modified during row computation");
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
      saved_retired=pops;
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
        if(pops!=saved_retired) $fatal(1,"POP occurred before response retirement");
      end
      result=held;
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      if (!reading && offset=='hc8 && !error_expected && pops!=saved_retired+1)
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
        transfer(1,'hd4,0,0,0,0,status); polls=polls+1;
        if(polls>40) $fatal(1,"FIFO producer timeout");
      end
    end
  endtask

  task automatic load_x(input integer r);
    begin
      put('hd8,(r%2)<<8,15,0);
      for(k=0;k<64;k=k+2) put('hdc,{xv(r,k+1),xv(r,k)},15,0);
    end
  endtask

  task automatic collide_pop_and_read;
    integer saved;
    begin
      saved=pops;
      @(negedge clk); cmd_valid=1; cmd_read=0; cmd_addr=32'h100420e4;
      cmd_wdata=1; cmd_wmask=15; rsp_ready=0;
      @(posedge clk); #1;
      @(negedge clk); cmd_valid=0;
      repeat(160) begin
        @(posedge clk); #1;
        if(!rsp_valid || rsp_err || pops!=saved) $fatal(1,"blocked DB POP moved head");
      end
      @(negedge clk); cmd_valid=1; cmd_read=1; cmd_addr=32'h10042200; rsp_ready=1;
      @(posedge clk); #1;
      if(!rsp_valid || !rsp_err || pops!=saved+1) $fatal(1,"DB POP/read collision replayed head");
      @(negedge clk); cmd_valid=0; rsp_ready=0;
      repeat(3) begin
        @(posedge clk); #1;
        if(!rsp_valid || !rsp_err || pops!=saved+1) $fatal(1,"DB collision response changed");
      end
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
    end
  endtask

  initial begin
    repeat(4) @(negedge clk); rst_n=1;
    get('h050,32'h58550003,2); get('h070,32'h58530003,2);
    get('h074,32'h58500003,2); get('h078,32'h58410001,2); get('h07c,32'h58440001,2);
    put('hd0,1,15,1); // Full bias cache must be enabled.
    put('he0,0,15,1); put('he4,1,15,1);
    transfer(1,'h200,0,0,1,3,response);
    put('h054,0,15,0);
    for(s=0;s<16384;s=s+2)
      put('h05c,{wv((s%256)/8,(s+1)%8,s/256),wv((s%256)/8,s%8,s/256)},15,0);
    for(col=0;col<256;col=col+1) begin
      value=bv(0,col);
      put('h044,col,15,0); put('h048,value[31:0],15,0); put('h04c,{24'b0,value[39:32]},15,0);
    end
    put('h040,1,15,0);
    put('hd0,1,7,1); put('hd0,2,15,1); put('hd0,1,15,0);
    put('hd8,1,15,0); put('hdc,0,15,1); // Packed cursor must be even.
    put('hd8,65,15,1); put('hd8,128,15,1); put('hd8,512,15,1);
    load_x(0);
    put('he0,0,7,1); put('he0,2,15,1); put('he0,0,15,0);
    put('hd8,0,15,1); put('hdc,0,15,1); put('he0,0,15,1);
    load_x(1);
    transfer(0,'he0,257,15,0,240,response);
    if(dut.db_count!=2 || starts!=2 || dones!=2 || dut.db_running ||
        dut.db_outstanding!=2 || dut.db_queued!=2)
      $fatal(1,"two result slots did not backpressure queued rows");
    repeat(100) @(negedge clk);
    if(starts!=2) $fatal(1,"producer overwrote full result FIFO");
    put('hd0,0,15,1); put('he0,512,15,1); put('hc0,1,15,1); put('hc8,1,15,1);
    for(s='h010;s<='h030;s=s+4) put(s,0,15,1);
    for(s='h040;s<='h04c;s=s+4) put(s,0,15,1);
    for(s='h054;s<='h068;s=s+4) put(s,0,15,1);
    for(row=0;row<4;row=row+1) begin
      for(g=0;g<32;g=g+1) begin
        wait_valid();
        if(dut.db_tag!=row || dut.db_group!=g) $fatal(1,"row/group ordering changed");
        get('he8,(row<<8)|g,0);
        for(lane=0;lane<8;lane=lane+1) begin
          value=expected(row,g,lane); raw=value[47:0];
          get('h200+lane*8,raw[31:0],(g==0 && lane==0)?100:0);
          get('h204+lane*8,{16'b0,raw[47:32]},0);
        end
        put('he4,0,15,1); put('he4,1,7,1);
        if(g==31 && row<2) begin
          // X is already free although the previous row still owns its head.
          if(!dut.db_bank_free[row%2]) $fatal(1,"X bank was not freed after final compute");
          load_x(row+2);
          put('he0,((row+2)<<8)|(row%2),15,1); // two rows still outstanding
        end
        if(g==0) collide_pop_and_read();
        else transfer(0,'he4,1,15,0,(g%7==0)?170:0,response);
        if(g==31 && row<2) put('he0,((row+2)<<8)|(row%2),15,0);
      end
    end
    if(dut.db_outstanding || dut.db_queued || dut.db_count || dut.db_running ||
        dut.db_bank_free!=3 || pops!=128 || starts!=128 || dones!=128)
      $fatal(1,"rows, descriptors, results and bank ownership did not drain exactly");
    if(overlap==0 || x_overlap==0) $fatal(1,"missing actual X/load/compute/readback overlap");
    put('he4,1,15,1); transfer(1,'h200,0,0,1,2,response);
    put('hd0,0,15,0);
    // Old mode uses bank0, which still holds row2, and the unchanged single-group contract.
    put('h010,19,15,0); put('h008,1,15,0); repeat(80) @(negedge clk);
    for(lane=0;lane<8;lane=lane+1) begin
      value=expected(2,19,lane); raw=value[47:0];
      get('h080+lane*8,raw[31:0],0); get('h084+lane*8,{16'b0,raw[47:32]},0);
    end
    if(accepts!=retires) $fatal(1,"orphan/duplicate DB response");
    put('hd0,1,15,0); put('he0,0,15,0); repeat(160) @(negedge clk);
    if(dut.db_count!=2) $fatal(1,"reset-abort precondition");
    rst_n=0; repeat(4) @(negedge clk); rst_n=1;
    if(dut.db_mode || dut.db_outstanding || dut.db_queued || dut.db_count ||
        dut.db_running || dut.db_bank_free!=3 || dut.rsp_db_pop || dut.cache_enable)
      $fatal(1,"reset did not abort all DB ownership/response state");
    $display("XU_DOUBLEBUF_WRAPPER_PASS rows=4 groups=128 lanes=1024 compute_read_overlap=%0d x_compute_overlap=%0d launches=%0d dones=%0d accepted=%0d retired=%0d",
      overlap,x_overlap,starts,dones,accepts,retires);
    $finish;
  end
  initial begin #6000000; $fatal(1,"double-buffer wrapper timeout"); end
endmodule
