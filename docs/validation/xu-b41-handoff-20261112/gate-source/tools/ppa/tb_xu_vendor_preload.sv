`timescale 1ns/10ps
// Four-state check of the exact vendor physical-row preload used by the SoC TB.
// Compile with -DARM_UD_MODEL and the external vendor file; no copied model.
module tb_xu_vendor_preload;
  reg clk=0;
  always #2 clk=~clk;
  reg cen=1;
  reg [9:0] addr=0;
  wire [15:0] q;
  RAMSP1024X16 macro (.Q(q),.CLK(clk),.CEN(cen),.WEN(16'hffff),
    .GWEN(1'b1),.A(addr),.D(16'b0),.EMA(3'b010),.EMAW(2'b00),.RET1N(1'b1));

  function automatic [15:0] pattern(input integer a);
    pattern=(a*16'h35ad)^16'hc071;
  endfunction

  function automatic [63:0] pack_row;
    input [15:0] a0,a1,a2,a3;
    integer b;
    begin
      for (b=0;b<16;b=b+1) pack_row[4*b +: 4]={a3[b],a2[b],a1[b],a0[b]};
    end
  endfunction

  task check_word(input integer a,input [15:0] expected);
    begin
      @(negedge clk); addr=a; cen=0;
      @(posedge clk); #0.2;
      if (q !== expected) $fatal(1,"preload word=%0d got=%h expected=%h",a,q,expected);
    end
  endtask

  integer row,a;
  initial begin
    #1;
    for (row=0;row<256;row=row+1)
      macro.mem[row]=pack_row(pattern(4*row),pattern(4*row+1),pattern(4*row+2),pattern(4*row+3));
    for (a=0;a<1024;a=a+1) check_word(a,pattern(a));
    @(negedge clk); cen=1;
    macro.mem[0]=pack_row(16'hx55a,16'h6x5a,16'h65xa,16'h65ax);
    check_word(0,16'hx55a);
    check_word(1,16'h6x5a);
    check_word(2,16'h65xa);
    check_word(3,16'h65ax);
    $display("XU_VENDOR_PRELOAD_PASS words=1024 four_state_x_words=4");
    $finish;
  end
endmodule
