`timescale 1ns/1ps
// xu: unaligned and exclusive-upper-bound reads keep the historical unknown
// register response (zero/no error) and cannot alias any owned result lane.
module tb_xu_pe64_boundaries;
  reg clk=0, rst_n=0;
  always #2 clk=~clk;
  reg cmd_valid=0, cmd_read=0, rsp_ready=0;
  reg [31:0] cmd_addr=0, cmd_wdata=0;
  reg [3:0] cmd_wmask=0;
  wire cmd_ready, rsp_valid, rsp_err;
  wire [31:0] rsp_rdata;
  xu_pe64_icb_slave dut(.*);
  integer mode, base, ctrl, pop, n, polls;
  reg [31:0] word;
  reg [5:0] saved_retired, saved_produced;
  reg [4:0] saved_group;
  reg [1:0] saved_count;

  task automatic access(input bit read_op, input [11:0] offset,
                        input [31:0] value, input bit expected_error,
                        output [31:0] result);
    reg [31:0] held;
    begin
      @(negedge clk);
      cmd_valid=1; cmd_read=read_op; cmd_addr={20'h10042,offset};
      cmd_wdata=value; cmd_wmask=15; rsp_ready=0;
      @(posedge clk);
      while(!cmd_ready) @(posedge clk);
      #1;
      @(negedge clk); cmd_valid=0; cmd_addr=32'hffffffff;
      if(!rsp_valid || rsp_err!==expected_error) $fatal(1,"boundary response offset=%h",offset);
      held=rsp_rdata;
      repeat(7) begin
        @(posedge clk); #1;
        if(!rsp_valid || rsp_rdata!==held || rsp_err!==expected_error || cmd_ready)
          $fatal(1,"boundary response changed under stall");
      end
      result=held;
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
    end
  endtask

  task automatic check_unknown(input [11:0] address);
    begin
      saved_retired=dut.row_retired; saved_produced=dut.row_produced;
      saved_group=dut.row_group; saved_count=dut.row_count;
      access(1,address,0,0,word);
      if(word!==0 || dut.row_retired!==saved_retired || dut.row_produced!==saved_produced ||
         dut.row_group!==saved_group || dut.row_count!==saved_count || !dut.row_active)
        $fatal(1,"unknown/unaligned read aliased an owned result address=%h",address);
    end
  endtask

  initial begin
    for(mode=0;mode<3;mode=mode+1) begin
      rst_n=0; repeat(4) @(negedge clk); rst_n=1;
      ctrl=mode==0?'hc0:(mode==1?'hd0:'he0);
      pop=ctrl+8;
      base=mode==0?'h100:(mode==1?'h200:'h400);
      access(0,'h040,1,0,word);
      access(0,ctrl,1,0,word);
      polls=0;
      while(dut.row_count!=2 && polls<200) begin @(negedge clk); polls=polls+1; end
      if(dut.row_count!=2 || dut.row_running || dut.row_group!=0 || dut.row_retired!=0)
        $fatal(1,"boundary owned-FIFO precondition");
      // Includes all three byte misalignments at low/high halves of first,
      // middle and last lanes. Full FIFO keeps the producer stable throughout.
      for(n=1;n<4;n=n+1) begin
        check_unknown(base+n);
        check_unknown(base+4+n);
        check_unknown(base+(mode==0?4:(mode==1?16:32))*8+n);
        check_unknown(base+(mode==0?8:(mode==1?32:64))*8-4+n);
      end
      check_unknown('h300); check_unknown('h600);
      // An aligned window belonging to another mode must reject explicitly.
      access(1,mode==0?'h200:'h100,0,1,word);
      if(dut.row_retired!=0 || dut.row_count!=2 || dut.row_group!=0)
        $fatal(1,"wrong-mode read moved FIFO head");
      access(0,pop,1,0,word);
      if(dut.row_retired!=1 || dut.row_group!=1)
        $fatal(1,"valid POP did not retire owned head exactly once");
      $display("XU_PE64_BOUNDARY_PASS mode=%0d unknown_reads=14 mode_error=1 pop_retired=1",mode);
    end
    $display("XU_PE64_BOUNDARIES_PASS modes=3");
    $finish;
  end
  initial begin #100000; $fatal(1,"boundary watchdog"); end
endmodule
