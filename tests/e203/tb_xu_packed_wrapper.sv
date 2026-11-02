`timescale 1ns/1ps
module tb_xu_packed_wrapper;
  reg clk=0;
  always #5 clk=~clk;
  reg rst_n=0, cmd_valid=0, cmd_read=0, rsp_ready=0;
  reg [31:0] cmd_addr=0, cmd_wdata=0;
  reg [3:0] cmd_wmask=0;
  wire cmd_ready, rsp_valid, rsp_err;
  wire [31:0] rsp_rdata;
  accel_icb_slave dut(.*);

  // Check the pins sampled by the real Chisel core, rather than the wrapper's
  // cursor/capture registers. Every downstream write must consume one entry.
  integer expected_kind [0:17023];
  integer expected_bank [0:17023];
  integer expected_addr [0:17023];
  reg [15:0] expected_data [0:17023];
  reg signed [15:0] model_w [0:16383];
  reg signed [15:0] model_x [0:63];
  integer queued=0, committed=0, w_committed=0, x_committed=0;
  integer accepted=0, retired=0, starts=0;
  integer index, mask, trial, group_id, lane, k, saved_commits;
  reg [31:0] response;
  reg [15:0] datum;

  task automatic check_write(input integer kind, input integer bank,
                             input integer address, input [15:0] data);
    begin
      if (committed>=queued)
        $fatal(1,"unexpected downstream write kind=%0d bank=%0d addr=%0d",kind,bank,address);
      if (kind!=expected_kind[committed] || bank!=expected_bank[committed] ||
          address!=expected_addr[committed] || data!==expected_data[committed])
        $fatal(1,"downstream write %0d got kind/bank/addr/data=%0d/%0d/%0d/%h expected=%0d/%0d/%0d/%h",
          committed,kind,bank,address,data,expected_kind[committed],
          expected_bank[committed],expected_addr[committed],expected_data[committed]);
      committed=committed+1;
      if (kind==1) w_committed=w_committed+1;
      else x_committed=x_committed+1;
    end
  endtask

  always @(posedge clk) if (rst_n) begin
    if (cmd_valid && cmd_ready) accepted=accepted+1;
    if (rsp_valid && rsp_ready) retired=retired+1;
    if (dut.u_linear_compute_core.io_wLoadWen)
      check_write(1,dut.u_linear_compute_core.io_wLoadBank,
                  dut.u_linear_compute_core.io_wLoadAddr,dut.u_linear_compute_core.io_wLoadData);
    if (dut.u_linear_compute_core.io_xLoadWen)
      check_write(0,0,dut.u_linear_compute_core.io_xLoadAddr,
                  dut.u_linear_compute_core.io_xLoadData);
    if (dut.u_linear_compute_core.io_start) begin
      if (committed!=queued) $fatal(1,"START reached the core before the final write committed");
      starts=starts+1;
    end
  end

  task automatic queue_w(input integer bank,input integer address,input [15:0] data);
    begin
      expected_kind[queued]=1; expected_bank[queued]=bank;
      expected_addr[queued]=address; expected_data[queued]=data; queued=queued+1;
      model_w[bank*2048+address]=data;
    end
  endtask

  task automatic queue_stream_w(input integer position,input [15:0] data);
    integer row, column;
    begin
      // Independent row-major model: 64 rows, 256 output columns, 8 banks.
      row=position/256; column=position%256;
      queue_w(column%8,(column/8)*64+row,data);
    end
  endtask

  task automatic queue_x(input integer address,input [15:0] data);
    begin
      expected_kind[queued]=0; expected_bank[queued]=0;
      expected_addr[queued]=address; expected_data[queued]=data; queued=queued+1;
      model_x[address]=data;
    end
  endtask

  function automatic [15:0] pattern(input integer position);
    begin
      case (position%16)
        0: pattern=16'h8000;
        1: pattern=16'h7fff;
        2: pattern=16'hffff;
        3: pattern=16'h0000;
        4: pattern=16'h0001;
        5: pattern=16'h8001;
        6: pattern=16'h5555;
        7: pattern=16'haaaa;
        default: pattern=(position*73)^(position/8);
      endcase
    end
  endfunction

  // Poison the live command immediately after acceptance. A stream write must
  // use its accepted address/data, commit on the next edge, then respond once.
  task automatic transfer(input bit read_access,input [11:0] offset,
                          input [31:0] data,input [3:0] byte_mask,
                          input bit error_expected,input integer stream_commit,
                          input integer hold_cycles,output [31:0] result);
    integer timeout, before_commits;
    reg [31:0] held_data;
    reg held_error;
    begin
      @(negedge clk);
      cmd_valid=1; cmd_read=read_access; cmd_addr={20'h10042,offset};
      cmd_wdata=data; cmd_wmask=byte_mask; rsp_ready=0;
      timeout=0; before_commits=committed;
      @(posedge clk);
      while (!cmd_ready) begin
        timeout=timeout+1;
        if (timeout>32) $fatal(1,"command acceptance timed out offset=%h",offset);
        @(posedge clk);
      end
      #1;
      if (stream_commit && (rsp_valid || committed!=before_commits || cmd_ready))
        $fatal(1,"stream command responded/committed before its commit edge offset=%h",offset);
      @(negedge clk);
      cmd_valid=0; cmd_addr=32'hdeadbeef; cmd_wdata=32'hbad0cafe;
      cmd_wmask=0; cmd_read=1;
      timeout=0;
      if (stream_commit==2) begin
        @(posedge clk); #1;
        if (rsp_valid || cmd_ready || committed!=before_commits+1)
          $fatal(1,"packed low beat responded early or did not commit once offset=%h",offset);
      end
      while (!rsp_valid) begin
        @(posedge clk); #1; timeout=timeout+1;
        if (timeout>32) $fatal(1,"response timed out offset=%h",offset);
      end
      if (rsp_err!==error_expected)
        $fatal(1,"response error offset=%h got=%b expected=%b",offset,rsp_err,error_expected);
      if (stream_commit && committed!=before_commits+stream_commit)
        $fatal(1,"stream response preceded/exceeded the required actual writes offset=%h",offset);
      held_data=rsp_rdata; held_error=rsp_err;
      repeat (hold_cycles) begin
        @(posedge clk); #1;
        if (!rsp_valid || cmd_ready || rsp_rdata!==held_data || rsp_err!==held_error)
          $fatal(1,"blocked response changed offset=%h",offset);
        if (stream_commit && committed!=before_commits+stream_commit)
          $fatal(1,"stalled stream response replayed a write");
      end
      result=held_data;
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
    end
  endtask

  task automatic put(input [11:0] offset,input [31:0] data,input [3:0] byte_mask,
                     input bit error_expected);
    reg [31:0] ignored;
    begin transfer(0,offset,data,byte_mask,error_expected,0,1,ignored); end
  endtask

  task automatic stream_put(input [11:0] offset,input [15:0] data,input integer stall);
    reg [31:0] ignored;
    begin transfer(0,offset,{16'hcafe,data},15,0,1,stall,ignored); end
  endtask

  task automatic packed_put(input [11:0] offset,input [31:0] data,input integer stall);
    reg [31:0] ignored;
    begin transfer(0,offset,data,15,0,2,stall,ignored); end
  endtask

  // Hold the original valid/data through both commits and a blocked response.
  // A command is accepted exactly once until its first response can retire.
  task automatic held_packed;
    integer before_commits, before_accepts;
    begin
      put('h054,254,15,0);
      queue_stream_w(254,16'h8001); queue_stream_w(255,16'h7fff);
      before_commits=committed; before_accepts=accepted;
      @(negedge clk); cmd_valid=1; cmd_read=0; cmd_addr=32'h1004205c;
      cmd_wdata=32'h7fff8001; cmd_wmask=15; rsp_ready=0;
      @(posedge clk); #1;
      if (rsp_valid || cmd_ready) $fatal(1,"held packed did not capture");
      @(posedge clk); #1;
      if (rsp_valid || committed!=before_commits+1 || dut.w_cursor!=254)
        $fatal(1,"held packed low beat or cursor failure");
      @(posedge clk); #1;
      if (!rsp_valid || rsp_err || committed!=before_commits+2 || dut.w_cursor!=256)
        $fatal(1,"held packed high beat or cursor failure");
      repeat(5) begin
        @(posedge clk); #1;
        if (!rsp_valid || rsp_err || cmd_ready || accepted!=before_accepts+1 ||
            committed!=before_commits+2 || dut.w_cursor!=256)
          $fatal(1,"held valid repeated packed acceptance/commit");
      end
      @(negedge clk); cmd_valid=0; rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
      expect_read('h054,256);
    end
  endtask

  task automatic expect_read(input [11:0] offset,input [31:0] expected_word);
    reg [31:0] actual;
    begin
      transfer(1,offset,0,0,0,0,1,actual);
      if (actual!==expected_word)
        $fatal(1,"read offset=%h got=%h expected=%h",offset,actual,expected_word);
    end
  endtask

  task automatic wait_done;
    reg [31:0] status;
    integer polls;
    begin
      status=0; polls=0;
      while (!status[1]) begin
        transfer(1,'h00c,0,0,0,0,0,status); polls=polls+1;
        if (polls>64) $fatal(1,"compute completion timed out");
      end
      if (status[0]) $fatal(1,"completion left busy asserted");
    end
  endtask

  task automatic check_results(input integer selected_group);
    integer selected_lane, selected_k;
    reg signed [63:0] total;
    reg signed [31:0] product;
    reg [47:0] raw;
    begin
      for (selected_lane=0;selected_lane<8;selected_lane=selected_lane+1) begin
        total=0;
        for (selected_k=0;selected_k<64;selected_k=selected_k+1) begin
          product=model_x[selected_k]*model_w[selected_lane*2048+selected_group*64+selected_k];
          total=total+product;
        end
        raw=total[47:0];
        expect_read('h080+selected_lane*8,raw[31:0]);
        expect_read('h084+selected_lane*8,{16'b0,raw[47:32]});
      end
    end
  endtask

  // Keep START asserted while the final data command is pending and its
  // response is blocked. START can only be accepted when that response retires.
  task automatic final_write_then_start;
    integer before_commits, before_accepts, before_starts;
    reg [31:0] held_data;
    begin
      put('h010,31,15,0); put('h054,16382,15,0);
      queue_stream_w(16382,16'h7fff); queue_stream_w(16383,16'h8000);
      before_commits=committed; before_accepts=accepted; before_starts=starts;
      @(negedge clk);
      cmd_valid=1; cmd_read=0; cmd_addr=32'h1004205c;
      cmd_wdata=32'h80007fff; cmd_wmask=15; rsp_ready=0;
      @(posedge clk); #1;
      if (rsp_valid || cmd_ready || committed!=before_commits)
        $fatal(1,"final stream write did not enter a pending interval");
      @(negedge clk); cmd_addr=32'h10042008; cmd_wdata=1;
      @(posedge clk); #1;
      if (rsp_valid || cmd_ready || committed!=before_commits+1 || dut.w_cursor!=16382)
        $fatal(1,"packed low beat responded/advanced cursor or missed its commit");
      @(posedge clk); #1;
      if (!rsp_valid || rsp_err || committed!=before_commits+2 || dut.w_cursor!=16384)
        $fatal(1,"packed final commit/response missing");
      held_data=rsp_rdata;
      repeat(4) begin
        @(posedge clk); #1;
        if (!rsp_valid || cmd_ready || rsp_err || rsp_rdata!==held_data ||
            committed!=before_commits+2 || accepted!=before_accepts+1 || starts!=before_starts)
          $fatal(1,"held START changed state before the final write response retired");
      end
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      if (!rsp_valid || rsp_err || accepted!=before_accepts+2)
        $fatal(1,"START was not accepted exactly on prior response retirement");
      @(negedge clk); cmd_valid=0; rsp_ready=0;
      @(posedge clk); #1;
      if (starts!=before_starts+1 || committed!=before_commits+2 || !rsp_valid)
        $fatal(1,"START ordering or stalled response replay failure");
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
      wait_done(); check_results(31);
      expect_read('h054,16384);
    end
  endtask

  initial begin
    repeat(3) @(negedge clk); rst_n=1;
    expect_read('h000,32'hacce2030);
    expect_read('h050,32'h58550003); expect_read('h070,32'h58530003);
    expect_read('h054,0); expect_read('h060,0); expect_read('h06c,0);
    expect_read('h058,0); expect_read('h064,0);
    expect_read('h05c,0); expect_read('h068,0); expect_read('h074,32'h58500003);
    put('h074,0,15,0); expect_read('h074,32'h58500003);
    put('h050,0,15,0); put('h070,0,15,0);
    expect_read('h050,32'h58550003); expect_read('h070,32'h58530003);

    // Separate legacy pointers and data registers survive new-port activity.
    put('h01c,6,15,0); put('h020,1701,15,0); put('h014,43,15,0);
    put('h054,1025,15,0); put('h060,62,15,0);
    queue_stream_w(1025,16'h7fff); stream_put('h058,16'h7fff,3);
    queue_x(62,16'h8000); stream_put('h064,16'h8000,2);
    queue_x(63,16'hffff); stream_put('h064,16'hffff,3);
    expect_read('h01c,6); expect_read('h020,1701); expect_read('h014,43);
    expect_read('h024,0); expect_read('h018,0);
    // Legacy mask semantics and legacy pointer behavior are deliberately kept.
    queue_w(6,1701,16'haaaa); put('h024,32'h9876aaaa,0,0);
    queue_x(43,16'h5555); put('h018,32'h12345555,0,0);
    expect_read('h054,1026); expect_read('h060,64);
    expect_read('h01c,6); expect_read('h020,1701); expect_read('h014,43);
    expect_read('h024,32'haaaa); expect_read('h018,32'h5555);

    // Every illegal mask on every new cursor/data port must be atomic.
    put('h054,7,15,0); put('h060,9,15,0); saved_commits=committed;
    for (mask=0;mask<15;mask=mask+1) begin
      put('h054,100,mask,1); put('h058,32'h8000,mask,1);
      put('h060,20,mask,1); put('h064,32'h7fff,mask,1);
      put('h05c,32'h7fff8000,mask,1); put('h068,32'h80007fff,mask,1);
      expect_read('h054,7); expect_read('h060,9); expect_read('h06c,2);
    end
    put('h05c,32'h7fff8000,15,1); put('h068,32'h80007fff,15,1);
    put('h054,16385,15,1); put('h054,65536,15,1); put('h054,32'hffffffff,15,1);
    put('h060,65,15,1); put('h060,128,15,1); put('h060,32'hffffffff,15,1);
    expect_read('h054,7); expect_read('h060,9);
    if (committed!=saved_commits) $fatal(1,"invalid stream command wrote the core");
    put('h06c,2,0,0); expect_read('h06c,2);
    put('h06c,2,2,0); expect_read('h06c,2);
    put('h06c,1,1,0); expect_read('h06c,2);
    put('h06c,2,1,0); expect_read('h06c,0);

    held_packed();

    // Exhaust all 16,384 sequence positions, including every bank, K, group,
    // and transition across 8, 256, 8192, and the final non-wrapping sentinel.
    put('h054,0,15,0);
    for (index=0;index<16384;index=index+2) begin
      queue_stream_w(index,pattern(index)); queue_stream_w(index+1,pattern(index+1));
      packed_put('h05c,{pattern(index+1),pattern(index)},(index/2)%4);
      if (index==6 || index==254 || index==8190 || index==16382)
        expect_read('h054,index+2);
    end
    put('h060,0,15,0);
    for (index=0;index<64;index=index+2) begin
      queue_x(index,pattern(index+16)); queue_x(index+1,pattern(index+17));
      packed_put('h068,{pattern(index+17),pattern(index+16)},(index/2)%4);
      if (index==62) expect_read('h060,index+2);
    end
    expect_read('h01c,6); expect_read('h020,1701); expect_read('h014,43);
    expect_read('h024,32'haaaa); expect_read('h018,32'h5555);
    saved_commits=committed;
    put('h058,32'h1234,15,1); put('h064,32'h5678,15,1);
    put('h05c,32'h12345678,15,1); put('h068,32'h56781234,15,1);
    expect_read('h054,16384); expect_read('h060,64); expect_read('h06c,2);
    // Cursor sentinels are legal to write, but may never wrap on data writes.
    put('h054,16384,15,0); put('h060,64,15,0);
    put('h058,32'h8000,15,1); put('h064,32'h8000,15,1);
    put('h05c,32'h80008000,15,1); put('h068,32'h80008000,15,1);
    put('h054,16383,15,0); put('h060,63,15,0);
    put('h05c,32'h80008000,15,1); put('h068,32'h80008000,15,1);
    expect_read('h054,16383); expect_read('h060,63);
    if (committed!=saved_commits) $fatal(1,"exhausted cursor wrapped or wrote");
    put('h06c,2,1,0);

    // Valid-looking full-word writes also fail atomically while computing.
    put('h054,40,15,0); put('h060,16,15,0);
    put('h010,0,15,0); put('h008,1,15,0); saved_commits=committed;
    put('h054,0,15,1); put('h058,32'h7fff,15,1);
    put('h060,0,15,1); put('h064,32'h8000,15,1);
    put('h05c,32'h7fff8000,15,1); put('h068,32'h80007fff,15,1);
    expect_read('h054,40); expect_read('h060,16); expect_read('h06c,2);
    if (committed!=saved_commits) $fatal(1,"busy stream command wrote the core");
    wait_done(); check_results(0); put('h06c,2,1,0);

    // Arithmetic checks exercise the actual SRAM mapping and signed samples,
    // beyond the full physical-write scoreboard above.
    for (group_id=1;group_id<32;group_id=group_id+1) begin
      put('h010,group_id,15,0); put('h008,1,15,0);
      wait_done(); check_results(group_id);
    end
    final_write_then_start();
    expect_read('h06c,0);
    if (committed!=queued || accepted!=retired || w_committed!=16390 || x_committed!=67)
      $fatal(1,"count mismatch writes=%0d/%0d W=%0d X=%0d requests=%0d/%0d",
        committed,queued,w_committed,x_committed,accepted,retired);
    @(negedge clk); rst_n=0;
    repeat(2) @(negedge clk); rst_n=1;
    expect_read('h054,0); expect_read('h060,0); expect_read('h06c,0);
    expect_read('h050,32'h58550003); expect_read('h070,32'h58530003);
    if (accepted!=retired) $fatal(1,"request/response imbalance after reset");
    $display("XU_PACKED_WRAPPER_PASS accepted=%0d retired=%0d writes=%0d W=%0d X=%0d starts=%0d",
      accepted,retired,committed,w_committed,x_committed,starts);
    $finish;
  end
  initial begin #3000000; $fatal(1,"test timed out"); end
endmodule
