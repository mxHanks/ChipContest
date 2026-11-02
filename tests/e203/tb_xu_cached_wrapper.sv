`timescale 1ns/1ps
module tb_xu_cached_wrapper;
  reg clk=0;
  always #5 clk=~clk;
  reg rst_n=0, cmd_valid=0, cmd_read=0, rsp_ready=0;
  reg [31:0] cmd_addr=0, cmd_wdata=0;
  reg [3:0] cmd_wmask=0;
  wire cmd_ready, rsp_valid, rsp_err;
  wire [31:0] rsp_rdata;
  accel_icb_slave dut(.*);
  reg [39:0] expected [0:255];
  reg [39:0] legacy [0:7];
  reg [31:0] seed=32'h2032026;
  integer accepted=0, retired=0;
  integer addr, lane, group_id, k, trial;
  reg [31:0] value, low_word, high_word;
  reg [39:0] data40;
  reg has_bias_cache;

  always @(posedge clk) if (rst_n) begin
    if (cmd_valid && cmd_ready) accepted=accepted+1;
    if (rsp_valid && rsp_ready) retired=retired+1;
  end

  function automatic [31:0] random_next(input [31:0] previous);
    random_next=previous*32'd1664525+32'd1013904223;
  endfunction

  // Every transfer holds the response for a deterministic random interval.
  // Neither data nor rsp_valid may change while the consumer is blocked.
  task automatic transfer(input bit read_access, input [11:0] offset,
                          input [31:0] data, input [3:0] mask,
                          output [31:0] response);
    integer wait_cycles, timeout;
    reg [31:0] captured;
    begin
      seed=random_next(seed);
      repeat (seed[1:0]) @(negedge clk);
      @(negedge clk);
      cmd_valid=1; cmd_read=read_access; cmd_addr={20'h10042,offset};
      cmd_wdata=data; cmd_wmask=mask; rsp_ready=0;
      timeout=0;
      @(posedge clk);
      while (!cmd_ready) begin
        timeout=timeout+1;
        if (timeout>16) $fatal(1,"command acceptance timed out");
        @(posedge clk);
      end
      #1;
      if (!rsp_valid || rsp_err) $fatal(1,"missing/error response");
      captured=rsp_rdata;
      @(negedge clk); cmd_valid=0;
      seed=random_next(seed); wait_cycles=1+seed[1:0];
      repeat (wait_cycles) begin
        @(posedge clk); #1;
        if (!rsp_valid || cmd_ready || rsp_rdata!==captured)
          $fatal(1,"blocked response changed offset=%h",offset);
      end
      response=captured;
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
    end
  endtask

  task automatic put(input [11:0] offset,input [31:0] data,input [3:0] mask);
    reg [31:0] ignored;
    begin transfer(0,offset,data,mask,ignored); end
  endtask

  task automatic expect_read(input [11:0] offset,input [31:0] expected_word);
    reg [31:0] actual;
    begin
      transfer(1,offset,0,0,actual);
      if (actual!==expected_word)
        $fatal(1,"read offset=%h got=%h expected=%h",offset,actual,expected_word);
    end
  endtask

  task automatic load_cache(input integer index,input [39:0] raw);
    begin
      put('h044,index,15); put('h048,raw[31:0],15);
      // Upper HI bits must be discarded.
      put('h04c,{24'habcdef,raw[39:32]},15);
      expected[index]=raw;
    end
  endtask

  task automatic check_group(input integer selected_group,input bit cached);
    integer poll_count, selected_lane;
    reg [39:0] selected_bias;
    reg [47:0] expected_result;
    reg [31:0] status;
    begin
      put('h040,cached,1); put('h010,selected_group,15);
      put('h00c,2,15); put('h008,1,15);
      poll_count=0; status=0;
      while (!status[1]) begin
        transfer(1,'h00c,0,0,status); poll_count=poll_count+1;
        if (poll_count>32) $fatal(1,"compute timeout");
      end
      if (status[0]) $fatal(1,"busy remains asserted after completion");
      put('h034,3,15);
      for (selected_lane=7;selected_lane>=0;selected_lane=selected_lane-1) begin
        selected_bias=(cached && has_bias_cache)?expected[selected_group*8+selected_lane]:legacy[selected_lane];
        expected_result={{8{selected_bias[39]}},selected_bias};
        expect_read('h080+selected_lane*8,expected_result[31:0]);
        expect_read('h084+selected_lane*8,{16'b0,expected_result[47:32]});
      end
      expect_read('h034,3); // Window reads have no index side effects.
      for (selected_lane=0;selected_lane<8;selected_lane=selected_lane+1) begin
        selected_bias=(cached && has_bias_cache)?expected[selected_group*8+selected_lane]:legacy[selected_lane];
        expected_result={{8{selected_bias[39]}},selected_bias};
        put('h034,selected_lane,15);
        expect_read('h038,expected_result[31:0]);
        expect_read('h03c,{16'b0,expected_result[47:32]});
      end
      // Completion remains sticky, including after the final result read.
      expect_read('h00c,2); put('h00c,2,15); expect_read('h00c,0);
    end
  endtask

  // Accept one command while retiring a prior stalled response. Cache bytes
  // must not update before cmd_ready; both responses must retire exactly once.
  task automatic blocked_write;
    reg [39:0] original;
    begin
      put('h044,42,15); original=expected[42];
      @(negedge clk);
      cmd_valid=1; cmd_read=1; cmd_addr=32'h10042000; rsp_ready=0;
      @(posedge clk); #1;
      @(negedge clk);
      cmd_read=0; cmd_addr=has_bias_cache?32'h10042048:32'h10042004;
      cmd_wdata=32'hcafef00d; cmd_wmask=15;
      repeat(4) begin
        @(posedge clk); #1;
        if (cmd_ready || (has_bias_cache && dut.cache_read_data!==original) || rsp_rdata!==32'hacce2030)
          $fatal(1,"blocked command had a side effect");
      end
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      if (has_bias_cache && dut.cache_read_data!=={original[39:32],32'hcafef00d})
        $fatal(1,"accepted pipelined cache write missing");
      expected[42]={original[39:32],32'hcafef00d};
      @(negedge clk); cmd_valid=0;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
      if (!has_bias_cache) expect_read('h004,32'hcafef00d);
    end
  endtask

  initial begin
    repeat(3) @(negedge clk); rst_n=1;
    expect_read('h000,32'hacce2030);
    transfer(1,'h050,0,0,value);
    if (value!==32'h58550003 && value!==32'h58550002)
      $fatal(1,"unsupported capability=%h",value);
    has_bias_cache=value[0];
    expect_read('h040,0); expect_read('h044,0);
    put('h040,1,2); expect_read('h040,0);
    put('h044,255,2); expect_read('h044,0);
    put('h004,32'h12345678,15); expect_read('h004,32'h12345678);
    if (has_bias_cache) begin
    for (addr=0;addr<256;addr=addr+1) begin
      data40=(addr[0]?40'h8000000000:40'h7fffffffff)^addr;
      load_cache(addr,data40);
      expect_read('h048,expected[addr][31:0]);
      expect_read('h04c,{24'b0,expected[addr][39:32]});
    end
    // All byte lanes, zero mask, irrelevant high mask, and address truncation.
    for (trial=0;trial<24;trial=trial+1) begin
      seed=random_next(seed); addr=seed[7:0];
      put('h044,32'hffff0000|addr,1); expect_read('h044,addr);
      put('h048,32'ha1b2c3d4,5);
      expected[addr]=(expected[addr]&40'hffff00ff00)|40'h00b200d4;
      put('h048,0,0); put('h04c,0,2);
      expect_read('h048,expected[addr][31:0]);
      expect_read('h04c,{24'b0,expected[addr][39:32]});
      put('h04c,32'hffffff89,1); expected[addr][39:32]=8'h89;
      expect_read('h04c,32'h89);
    end
    end else begin
      // Reserved cache offsets acknowledge writes but expose no storage or mode.
      put('h040,1,15); expect_read('h040,0);
      for (addr=0;addr<256;addr=addr+1) begin
        load_cache(addr,40'h7fffffffff^addr);
        expect_read('h044,0); expect_read('h048,0); expect_read('h04c,0);
      end
      $display("XU_BIAS_CACHE_UNSUPPORTED capability=58550002 cache_checks=not_run");
    end
    blocked_write();
    // X=0 ensures full signed40 bias is observed without arithmetic ambiguity.
    for(k=0;k<64;k=k+1) begin put('h014,k,15); put('h018,0,15); end
    for(group_id=0;group_id<=31;group_id=group_id+31)
      for(lane=0;lane<8;lane=lane+1) begin
        put('h01c,lane,15);
        for(k=0;k<64;k=k+1) begin
          put('h020,group_id*64+k,15); put('h024,1,15);
        end
      end
    for(lane=0;lane<8;lane=lane+1) begin
      legacy[lane]=(lane[0]?40'h8000000000:40'h7fffffffff)^lane;
      put('h028,lane,15); put('h02c,legacy[lane][31:0],15);
      put('h030,{24'b0,legacy[lane][39:32]},1);
    end
    check_group(0,0); check_group(31,0); check_group(0,1); check_group(31,1);
    if (has_bias_cache) begin
      for(addr=0;addr<256;addr=addr+1) load_cache(addr,-40'd1-addr);
      check_group(0,1); check_group(31,1); check_group(0,0);
    end
    @(negedge clk); rst_n=0;
    repeat(2) @(negedge clk); rst_n=1;
    expect_read('h040,0); expect_read('h044,0); expect_read('h00c,0);
    if(accepted!=retired) $fatal(1,"request/response count mismatch %0d/%0d",accepted,retired);
    if (has_bias_cache)
      $display("XU_CACHED_WRAPPER_PASS accepted=%0d retired=%0d",accepted,retired);
    else
      $display("XU_H2_ONLY_WRAPPER_PASS accepted=%0d retired=%0d",accepted,retired);
    $finish;
  end
  initial begin #2000000; $fatal(1,"test timed out"); end
endmodule
