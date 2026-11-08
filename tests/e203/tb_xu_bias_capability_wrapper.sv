`timescale 1ns/1ps
// Compile this same public-port test with each real generated storage variant.
// There is no force, replacement core, or direct memory write.
`ifndef XU_EXPECT_BIAS_SRAM
`define XU_EXPECT_BIAS_SRAM 1
`endif
module tb_xu_bias_capability_wrapper;
  localparam EXPECT_SRAM = `XU_EXPECT_BIAS_SRAM;
  localparam [31:0] EXPECT_CAP = EXPECT_SRAM ? 32'h42530001 : 32'b0;
  reg clk=0;
  always #5 clk=~clk;
  reg rst_n=0, cmd_valid=0, cmd_read=0, rsp_ready=0;
  reg [31:0] cmd_addr=0, cmd_wdata=0;
  reg [3:0] cmd_wmask=0;
  wire cmd_ready, rsp_valid, rsp_err;
  wire [31:0] rsp_rdata;
  accel_icb_slave dut(.*);
  integer accepted=0, retired=0, clear_commands=0;
  integer elapsed, clear_wait;
  reg [31:0] value;
  reg held=0, held_error=0;
  reg [31:0] held_data=0;

  always @(posedge clk) begin
    if (!rst_n) held=0;
    else begin
      if (held && (!rsp_valid || rsp_rdata!==held_data || rsp_err!==held_error))
        $fatal(1,"Capability/clear response changed before retirement");
      held=rsp_valid && !rsp_ready;
      held_data=rsp_rdata; held_error=rsp_err;
      if (cmd_valid && cmd_ready) accepted=accepted+1;
      if (rsp_valid && rsp_ready) retired=retired+1;
      if (dut.clear_command) clear_commands=clear_commands+1;
      if (!EXPECT_SRAM && dut.clear_command)
        $fatal(1,"Unsupported clear reached the register-cache core");
    end
  end

  task automatic transfer(input bit reading, input [11:0] offset,
                          input [31:0] data, input [3:0] mask,
                          input bit expected_error, output [31:0] result,
                          output integer response_wait);
    integer command_wait;
    reg [31:0] snapshot;
    begin
      @(negedge clk); cmd_valid=1; cmd_read=reading;
      cmd_addr={20'h10042,offset}; cmd_wdata=data; cmd_wmask=mask; rsp_ready=0;
      command_wait=0;
      @(posedge clk);
      while (cmd_ready!==1'b1) begin
        command_wait=command_wait+1;
        if (command_wait>16) $fatal(1,"Capability/clear command hung offset=%h",offset);
        @(posedge clk);
      end
      #1;
      @(negedge clk); cmd_valid=0; cmd_read=!reading;
      cmd_addr=32'hdeadbeef; cmd_wdata=~data; cmd_wmask=~mask;
      response_wait=0;
      while (rsp_valid!==1'b1) begin
        @(posedge clk); #1; response_wait=response_wait+1;
        if (response_wait>1000) $fatal(1,"Capability/clear response hung offset=%h",offset);
      end
      if (rsp_err!==expected_error)
        $fatal(1,"Unexpected response error offset=%h got=%b expected=%b",offset,rsp_err,expected_error);
      snapshot=rsp_rdata;
      repeat(4) begin
        @(posedge clk); #1;
        if (!rsp_valid || rsp_err!==expected_error || rsp_rdata!==snapshot || cmd_ready)
          $fatal(1,"Blocked capability/clear response unstable offset=%h",offset);
      end
      result=snapshot;
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
    end
  endtask

  task automatic read_word(input [11:0] offset,input [31:0] expected);
    begin
      transfer(1,offset,0,0,0,value,elapsed);
      if (value!==expected)
        $fatal(1,"Capability/data mismatch offset=%h got=%h expected=%h",offset,value,expected);
    end
  endtask
  task automatic write_word(input [11:0] offset,input [31:0] data,
                            input [3:0] mask,input bit expected_error);
    begin transfer(0,offset,data,mask,expected_error,value,elapsed); end
  endtask

  initial begin
    repeat(3) @(negedge clk); rst_n=1;
    read_word('h000,32'hacce2030);
    read_word('h0ec,EXPECT_CAP);
    write_word('h044,255,1,0);
    write_word('h048,32'h12345678,15,0);
    write_word('h04c,32'h000000ab,1,0);
    read_word('h048,32'h12345678);
    read_word('h04c,32'h000000ab);
    // Invalid requests must complete as errors on both implementations.
    write_word('h0e8,0,15,1);
    write_word('h0e8,1,7,1);
    if (clear_commands!=0) $fatal(1,"Malformed clear reached the core");
    read_word('h048,32'h12345678);
    read_word('h04c,32'h000000ab);

    transfer(0,'h0e8,1,15,!EXPECT_SRAM,value,clear_wait);
    if (value!==0) $fatal(1,"Clear response payload is not deterministic zero");
    if (EXPECT_SRAM && clear_wait<768)
      $fatal(1,"SRAM clear completed before 768 physical writes cycles=%0d",clear_wait);
    if (!EXPECT_SRAM && clear_wait>1)
      $fatal(1,"Unsupported clear did not promptly return its error");
    if (clear_commands!=EXPECT_SRAM)
      $fatal(1,"Clear dispatch count mismatch got=%0d expected=%0d",clear_commands,EXPECT_SRAM);
    read_word('h048,EXPECT_SRAM ? 32'b0 : 32'h12345678);
    read_word('h04c,EXPECT_SRAM ? 32'b0 : 32'h000000ab);
    read_word('h000,32'hacce2030); // channel remains live after the held response
    @(negedge clk); rst_n=0;
    repeat(2) @(negedge clk); rst_n=1;
    read_word('h0ec,EXPECT_CAP);
    if (accepted!=retired) $fatal(1,"Incomplete ICB retirement");
    $display("XU_BIAS_CAPABILITY_WRAPPER_PASS sram=%0d capability=%h clear_commands=%0d clear_wait=%0d accepted=%0d retired=%0d",
      EXPECT_SRAM,EXPECT_CAP,clear_commands,clear_wait,accepted,retired);
    $finish;
  end
  initial begin #100000; $fatal(1,"Capability wrapper global timeout"); end
endmodule
