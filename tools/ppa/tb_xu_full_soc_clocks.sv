`timescale 1ns/1ps
// Tests the actual fixed-platform divider/gate/mux/PLL and register reset RTL.
// No FPGA_SOURCE: otherwise the platform intentionally bypasses clock gates.
module tb_xu_full_soc_clocks;
  reg clk=0;
  always #5 clk=~clk;
  reg rst_n=0, divby1=1;
  reg [5:0] div=0;
  wire divided;
  e203_subsys_pllclkdiv u_div(
    .rst_n(rst_n),.test_mode(1'b0),.divby1(divby1),.div(div),
    .clk(clk),.clkout(divided));
  reg hfreset=1, bypass=1, hby1=1;
  reg [5:0] hdiv=0;
  wire hfclk,inspect_ref,inspect_pll;
  e203_subsys_hclkgen u_hclk(
    .test_mode(1'b0),.hfclkrst(hfreset),.hfextclk(clk),
    .pllbypass(bypass),.pll_RESET(1'b0),.pll_ASLEEP(1'b0),
    .pll_OD(2'b10),.pll_M(8'd32),.pll_N(5'd2),
    .plloutdivby1(hby1),.plloutdiv(hdiv),
    .inspect_16m_clk(inspect_ref),.inspect_pll_clk(inspect_pll),.hfclk(hfclk));
  wire rbypass,rby1;
  wire [5:0] rdiv;
  wire ready,rsp_valid;
  wire [31:0] rdata;
  sirv_hclkgen_regs u_regs(
    .clk(clk),.rst_n(rst_n),.pllbypass(rbypass),.plloutdivby1(rby1),.plloutdiv(rdiv),
    .pll_RESET(),.pll_ASLEEP(),.pll_OD(),.pll_M(),.pll_N(),.hfxoscen(),
    .i_icb_cmd_valid(1'b0),.i_icb_cmd_ready(ready),.i_icb_cmd_addr(12'b0),
    .i_icb_cmd_read(1'b1),.i_icb_cmd_wdata(32'b0),
    .i_icb_rsp_valid(rsp_valid),.i_icb_rsp_ready(1'b1),.i_icb_rsp_rdata(rdata));
  task check_divider(input integer divisor);
    realtime rising;
    begin
      rst_n=0; divby1=(divisor<0); div=(divisor<0)?0:divisor;
      repeat(3) @(negedge clk);
      #1;
      if(rbypass!==1 || rby1!==1 || rdiv!==0) $fatal(1,"register reset mode differs");
      rst_n=1;
      repeat(4) begin
        @(posedge divided); rising=$realtime;
        @(negedge divided);
        if($realtime-rising!=5.0) $fatal(1,"divider high width div=%0d",divisor);
        @(posedge divided);
        if($realtime-rising!=((divisor<0)?10.0:20.0*(divisor+1)))
          $fatal(1,"divider period div=%0d observed=%0f",divisor,$realtime-rising);
      end
    end
  endtask
  task check_hclk(input integer bypass_mode,input integer divisor);
    realtime rising;
    begin
      hfreset=1; bypass=bypass_mode; hby1=(divisor<0); hdiv=(divisor<0)?0:divisor;
      repeat(4) @(negedge clk);
      #1 hfreset=0;
      // Ignore reset/mux acquisition, then inspect steady-state pulse shape.
      repeat(8) @(posedge hfclk);
      repeat(4) begin
        @(posedge hfclk); rising=$realtime;
        @(negedge hfclk);
        if($realtime-rising!=5.0) $fatal(1,"HCLKGEN high width");
        @(posedge hfclk);
        if($realtime-rising!=((bypass_mode || divisor<0)?10.0:20.0*(divisor+1)))
          $fatal(1,"HCLKGEN period");
      end
    end
  endtask
  integer d;
  initial begin
    #1; rst_n=1; #1 rst_n=0;
    check_divider(-1);
    for(d=0;d<64;d=d+1) check_divider(d);
    check_hclk(1,-1); check_hclk(0,-1); check_hclk(0,0); check_hclk(0,1); check_hclk(0,63);
    $display("XU_CLOCK_RTL_PASS divider_by1+all64_divisors; reset_registers; PLL_assignthrough+GFCM_steady_modes");
    $finish;
  end
  initial begin #1000000; $fatal(1,"clock regression timeout"); end
endmodule
