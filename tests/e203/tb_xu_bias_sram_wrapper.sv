`timescale 1ns/1ps
// Real wrapper + generated Chisel core. No forced data, shadow DUT RAM, or mock.
module tb_xu_bias_sram_wrapper;
  reg clk=0;
  always #5 clk=~clk;
  reg rst_n=0, cmd_valid=0, cmd_read=0, rsp_ready=0;
  reg [31:0] cmd_addr=0, cmd_wdata=0;
  reg [3:0] cmd_wmask=0;
  wire cmd_ready, rsp_valid, rsp_err;
  wire [31:0] rsp_rdata;
  accel_icb_slave dut(.*);
  reg [39:0] expected [0:255];
  reg [31:0] seed=32'hb1a53203;
  integer accepted=0, retired=0, overlaps=0, core_commands=0, clear_commands=0;
  integer masks_checked=0, read_words=0, forbidden_checked=0, clear_cycles=0;
  integer index, mask_id, byte_id, k, group_id, lane, timeout;
  reg reject_scope=0, held_response=0;
  reg [31:0] held_data=0;
  reg held_error=0;
  reg [31:0] response, low_data, high_data;
  reg [39:0] data40;
  reg [47:0] signed_bias;

  function automatic [31:0] random_next(input [31:0] previous);
    random_next=previous*32'd1664525+32'd1013904223;
  endfunction

  always @(posedge clk) begin
    if (!rst_n) held_response=0;
    else begin
      if (held_response && (!rsp_valid || rsp_rdata!==held_data || rsp_err!==held_error))
        $fatal(1,"ICB response changed before retirement");
      held_response=rsp_valid && !rsp_ready;
      held_data=rsp_rdata; held_error=rsp_err;
      if (cmd_valid && cmd_ready) accepted=accepted+1;
      if (rsp_valid && rsp_ready) retired=retired+1;
      if (cmd_valid && cmd_ready && rsp_valid && rsp_ready) overlaps=overlaps+1;
      if (dut.cache_command) core_commands=core_commands+1;
      if (dut.clear_command) clear_commands=clear_commands+1;
      if (reject_scope && cmd_valid && cmd_ready && !cmd_read) begin
        if (dut.cache_command || dut.clear_command)
          $fatal(1,"Rejected runtime operation escaped to the SRAM core");
        forbidden_checked=forbidden_checked+1;
      end
    end
  end

  task automatic transfer(input bit reading,input [11:0] offset,input [31:0] data,
                          input [3:0] mask,input bit error_expected,input integer stall,
                          output [31:0] result);
    integer wait_cycles;
    reg [31:0] snapshot;
    begin
      @(negedge clk); cmd_valid=1; cmd_read=reading;
      cmd_addr={20'h10042,offset}; cmd_wdata=data; cmd_wmask=mask; rsp_ready=0;
      wait_cycles=0;
      @(posedge clk);
      while (cmd_ready!==1'b1) begin
        wait_cycles=wait_cycles+1;
        if (wait_cycles>1000) $fatal(1,"Command timeout offset=%h",offset);
        @(posedge clk);
      end
      #1;
      // An asynchronous read/write must use the accepted descriptor, including
      // the original LO/HI selection. Change every live command input now.
      @(negedge clk); cmd_valid=0; cmd_read=!reading;
      cmd_addr=32'hdeadbeef; cmd_wdata=~data; cmd_wmask=~mask;
      wait_cycles=0;
      while (rsp_valid!==1'b1) begin
        @(posedge clk); #1; wait_cycles=wait_cycles+1;
        if (wait_cycles>1000) $fatal(1,"Response timeout offset=%h",offset);
      end
      if (rsp_err!==error_expected)
        $fatal(1,"Response error mismatch offset=%h got=%b expected=%b",offset,rsp_err,error_expected);
      snapshot=rsp_rdata;
      repeat(stall) begin
        @(posedge clk); #1;
        if (!rsp_valid || rsp_rdata!==snapshot || rsp_err!==error_expected || cmd_ready)
          $fatal(1,"Blocked response changed offset=%h",offset);
      end
      result=snapshot;
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
    end
  endtask
  task automatic put(input [11:0] offset,input [31:0] data,input [3:0] mask,input bit error_expected);
    reg [31:0] ignored;
    begin transfer(0,offset,data,mask,error_expected,1,ignored); end
  endtask
  task automatic get(input [11:0] offset,input [31:0] expected_word,input integer stall);
    reg [31:0] actual;
    begin
      transfer(1,offset,0,0,0,stall,actual);
      if (actual!==expected_word)
        $fatal(1,"Read mismatch offset=%h got=%h expected=%h",offset,actual,expected_word);
      read_words=read_words+1;
    end
  endtask
  task automatic check_bias(input integer selected);
    begin
      put('h044,selected,1,0);
      get('h048,expected[selected][31:0],selected%4);
      get('h04c,{24'b0,expected[selected][39:32]},(selected+1)%4);
    end
  endtask
  task automatic load_bias(input integer selected,input [39:0] value);
    begin
      put('h044,selected,1,0);
      put('h048,value[31:0],15,0);
      // Irrelevant HI data/mask bits must not alter the 40-bit representation.
      put('h04c,{24'hca55ee,value[39:32]},15,0);
      expected[selected]=value;
    end
  endtask

  task automatic read_retire_new_read;
    integer elapsed, before_core;
    begin
      put('h044,73,1,0);
      @(negedge clk); cmd_valid=1; cmd_read=1; cmd_addr=32'h10042048;
      cmd_wdata=0; cmd_wmask=0; rsp_ready=0;
      @(posedge clk);
      while (cmd_ready!==1'b1) @(posedge clk);
      #1;
      @(negedge clk); cmd_valid=0;
      elapsed=0;
      while (!rsp_valid) begin
        @(posedge clk); #1; elapsed=elapsed+1;
        if(elapsed>1000) $fatal(1,"First overlap read timed out");
      end
      if(rsp_err || rsp_rdata!==expected[73][31:0]) $fatal(1,"First overlap read wrong");
      before_core=core_commands;
      @(negedge clk); cmd_valid=1; cmd_read=1; cmd_addr=32'h1004204c;
      repeat(3) begin
        @(posedge clk); #1;
        if(cmd_ready || !rsp_valid || rsp_err || rsp_rdata!==expected[73][31:0] ||
           core_commands!=before_core) $fatal(1,"Blocked second read accepted early");
      end
      @(negedge clk); rsp_ready=1;
      @(posedge clk);
      if(!cmd_ready || !rsp_valid) $fatal(1,"Read retirement/new command did not overlap");
      #1;
      @(negedge clk); cmd_valid=0; rsp_ready=0; cmd_addr=32'h10042048;
      elapsed=0;
      while(!rsp_valid) begin
        @(posedge clk); #1; elapsed=elapsed+1;
        if(elapsed>1000) $fatal(1,"Second overlap read timed out");
      end
      if(rsp_err || rsp_rdata!=={24'b0,expected[73][39:32]})
        $fatal(1,"New read inherited retired LO descriptor");
      repeat(3) @(posedge clk);
      @(negedge clk); rsp_ready=1; @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
      $display("XU_BIAS_READ_OVERLAP_PASS");
    end
  endtask

  task automatic id_retire_new_write;
    integer elapsed, before_core;
    begin
      put('h044,42,1,0);
      @(negedge clk); cmd_valid=1; cmd_read=1; cmd_addr=32'h10042000;
      cmd_wdata=0; cmd_wmask=0; rsp_ready=0;
      @(posedge clk); #1;
      if(!rsp_valid || rsp_err || rsp_rdata!==32'hacce2030) $fatal(1,"ID setup failed");
      before_core=core_commands;
      @(negedge clk); cmd_read=0; cmd_addr=32'h10042048;
      cmd_wdata=32'h13579bdf; cmd_wmask=15;
      repeat(3) begin
        @(posedge clk); #1;
        if(cmd_ready || !rsp_valid || rsp_rdata!==32'hacce2030 ||
           core_commands!=before_core) $fatal(1,"Blocked write escaped acceptance");
      end
      @(negedge clk); rsp_ready=1;
      @(posedge clk);
      if(!cmd_ready || !rsp_valid) $fatal(1,"ID retirement/write acceptance did not overlap");
      #1;
      @(negedge clk); cmd_valid=0; rsp_ready=0; cmd_addr=32'h1004204c;
      cmd_wdata=32'hfedcba98; cmd_wmask=1;
      elapsed=0;
      while(!rsp_valid) begin
        @(posedge clk); #1; elapsed=elapsed+1;
        if(elapsed>1000) $fatal(1,"Overlapped write timed out");
      end
      if(rsp_err) $fatal(1,"Overlapped write failed");
      repeat(3) @(posedge clk);
      @(negedge clk); rsp_ready=1; @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
      expected[42][31:0]=32'h13579bdf;
      check_bias(42);
      $display("XU_BIAS_WRITE_OVERLAP_PASS");
    end
  endtask

  task automatic clear_and_block;
    integer elapsed, before_accept;
    begin
      @(negedge clk); cmd_valid=1; cmd_read=0; cmd_addr=32'h100420e8;
      cmd_wdata=1; cmd_wmask=15; rsp_ready=0;
      @(posedge clk);
      while(cmd_ready!==1'b1) @(posedge clk);
      #1; before_accept=accepted;
      @(negedge clk); cmd_valid=1; cmd_read=1; cmd_addr=32'h10042000;
      cmd_wdata=0; cmd_wmask=0;
      elapsed=0;
      while(!rsp_valid) begin
        @(posedge clk); #1; elapsed=elapsed+1;
        if(cmd_ready || accepted!=before_accept)
          $fatal(1,"Command accepted while physical clear was in flight");
        if(elapsed>1000) $fatal(1,"768-word clear timed out");
      end
      clear_cycles=elapsed;
      if(elapsed<768 || rsp_err || rsp_rdata!==0)
        $fatal(1,"Clear response arrived before physical commits cycles=%0d",elapsed);
      repeat(3) begin
        @(posedge clk); #1;
        if(cmd_ready || !rsp_valid || rsp_err || rsp_rdata!==0 || accepted!=before_accept)
          $fatal(1,"Blocked clear response lost ownership");
      end
      @(negedge clk); rsp_ready=1;
      @(posedge clk);
      if(!cmd_ready || !rsp_valid) $fatal(1,"Clear retirement/new ID acceptance did not overlap");
      #1;
      if(!rsp_valid || rsp_err || rsp_rdata!==32'hacce2030) $fatal(1,"ID after clear wrong");
      @(negedge clk); cmd_valid=0; rsp_ready=0;
      repeat(2) @(posedge clk);
      @(negedge clk); rsp_ready=1; @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
      $display("XU_BIAS_CLEAR_PASS cycles=%0d",clear_cycles);
    end
  endtask

  initial begin
    repeat(3) @(negedge clk); rst_n=1;
    get('h000,32'hacce2030,2); get('h0ec,32'h42530001,3);
    get('h040,0,1); get('h044,0,1);
    put('h0e8,0,15,1); put('h0e8,1,7,1);
    for(index=0;index<256;index=index+1) begin
      data40=(index[0]?40'h8000000000:40'h7fffffffff)^index;
      load_bias(index,data40); check_bias(index);
    end
    for(index=0;index<256;index=index+1) begin
      put('h044,index,1,0);
      for(mask_id=0;mask_id<32;mask_id=mask_id+1) begin
        seed=random_next(seed); low_data=seed;
        seed=random_next(seed); high_data=seed;
        put('h048,low_data,mask_id[3:0],0);
        put('h04c,high_data,{3'b111,mask_id[4]},0);
        data40={high_data[7:0],low_data};
        for(byte_id=0;byte_id<5;byte_id=byte_id+1)
          if(mask_id[byte_id]) expected[index][byte_id*8+:8]=data40[byte_id*8+:8];
        get('h048,expected[index][31:0],mask_id%4);
        get('h04c,{24'b0,expected[index][39:32]},(mask_id+1)%4);
        masks_checked=masks_checked+1;
      end
    end
    read_retire_new_read(); id_retire_new_write();
    clear_and_block();
    for(index=0;index<256;index=index+1) begin expected[index]=0; check_bias(index); end
    // Refill before reset; reset must drop ownership, not silently erase payload.
    for(index=0;index<256;index=index+1)
      load_bias(index,(index[0]?40'h8000000000:40'h7fffffffff)^index);
    @(negedge clk); rst_n=0;
    repeat(2) @(negedge clk); rst_n=1;
    get('h040,0,1); get('h044,0,1);
    for(index=0;index<256;index=index+1) check_bias(index);
    $display("XU_BIAS_RESET_RETAINS_PASS items=256");

    // Real X=0/W=1 MACs make FIFO heads equal the complete signed40 bias.
    // Only groups 0 and 1 can launch before both FIFO slots are filled.
    for(k=0;k<64;k=k+1) begin put('h014,k,15,0); put('h018,0,15,0); end
    for(group_id=0;group_id<2;group_id=group_id+1)
      for(lane=0;lane<8;lane=lane+1) begin
        put('h01c,lane,15,0);
        for(k=0;k<64;k=k+1) begin
          put('h020,group_id*64+k,15,0); put('h024,1,15,0);
        end
      end
    put('h044,42,1,0); put('h040,1,1,0); put('h0c0,1,15,0);
    timeout=0;
    while(dut.row_count!==2 || dut.row_running) begin
      @(posedge clk); #1; timeout=timeout+1;
      if(timeout>1000) $fatal(1,"Real producer did not fill its two FIFO slots");
    end
    for(lane=0;lane<8;lane=lane+1) begin
      signed_bias={{8{expected[lane][39]}},expected[lane]};
      get('h100+lane*8,signed_bias[31:0],2);
      get('h104+lane*8,{16'b0,signed_bias[47:32]},2);
    end
    reject_scope=1;
    put('h040,0,1,1); put('h044,73,1,1);
    put('h048,32'hdeadbeef,15,1); put('h04c,32'h55,15,1);
    put('h0e8,1,15,1);
    reject_scope=0;
    get('h040,1,2); get('h044,42,2);
    get('h048,expected[42][31:0],2); get('h04c,{24'b0,expected[42][39:32]},2);
    if(!dut.row_active || dut.row_count!==2 || forbidden_checked!=5)
      $fatal(1,"Runtime rejection changed row ownership");
    $display("XU_BIAS_RUNTIME_REJECT_PASS operations=%0d",forbidden_checked);
    @(negedge clk); rst_n=0;
    repeat(2) @(negedge clk); rst_n=1;
    get('h00c,0,2);
    for(index=0;index<256;index=index+1) check_bias(index);
    if(accepted!=retired || clear_commands!=1 || overlaps<3 || masks_checked!=8192)
      $fatal(1,"Final accounting wrong accepted=%0d retired=%0d clear=%0d overlap=%0d masks=%0d",
        accepted,retired,clear_commands,overlaps,masks_checked);
    $display("XU_BIAS_SRAM_WRAPPER_PASS masks=%0d items=256 read_words=%0d accepted=%0d retired=%0d core_commands=%0d overlaps=%0d clear_cycles=%0d",
      masks_checked,read_words,accepted,retired,core_commands,overlaps,clear_cycles);
    $finish;
  end
  initial begin #50000000; $fatal(1,"Bias wrapper global timeout"); end
endmodule
