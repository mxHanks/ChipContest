// xu four-state observer probe. Supply a model; no vendor model is redistributed.
`timescale 1ns/1ps
module xu_sram_alias_probe_design(
  input source_clk, gate, cs, we,
  input [3:0] wem,
  input [9:0] addr,
  input [31:0] din,
  output [31:0] dout
);
  wire gated_clk = source_clk & gate;
  sirv_sim_ram #(.DP(1024),.AW(10),.DW(32),.MW(4),.FORCE_X2ZERO(0)) live
    (.clk(gated_clk),.cs(cs),.we(we),.wem(wem),.addr(addr),.din(din),.dout(dout));
  wire [15:0] idle_data;
  // Like an untouched, clock-gated DTCM: data/address are unknown; controls are known.
  sirv_sim_ram #(.DP(1024),.AW(10),.DW(16),.MW(2),.FORCE_X2ZERO(1)) idle
    (.clk(1'b0),.cs(1'b0),.we(1'b0),.wem(2'bxx),.addr(10'bx),.din(16'bx),.dout(idle_data));
endmodule

module tb_xu_sram_activity_alias;
  reg source_clk=0, gate=1, cs=0, we=0;
  reg [3:0] wem=0;
  reg [9:0] addr=0;
  reg [31:0] din=0;
  wire [31:0] dout;
  always #5 source_clk=~source_clk;
  xu_sram_alias_probe_design dut(source_clk,gate,cs,we,wem,addr,din,dout);
  `include "xu_sram_activity_alias.svh"
  initial begin
    $dumpfile("xu_sram_alias_probe.vcd");
    $dumpvars(1,tb_xu_sram_activity_alias);
    $dumpvars(0,tb_xu_sram_activity_alias.xu_sram_activity_alias);
    // Select actual ports explicitly. Vendor model private realtime objects
    // are outside this digital pin-equality experiment.
    `include "xu_sram_activity_alias_dump.svh"
    #12;cs=1;we=1;addr=3;din=32'h11223344;wem=4'b1111;
    #10;we=0;
    #5;if(dout!==32'h11223344) $fatal(1,"initial fullword read differs");
    #5;we=1;din=32'haabbccdd;wem=4'b0101;
    #10;we=0;
    #5;if(dout!==32'h11bb33dd) $fatal(1,"byte write read differs");
    #5;gate=0;cs=0;din=32'hzzxx0f0f;
    #20;gate=1;cs=1;addr=4;din=32'h12345678;
    #10;gate=0;cs=0;
    #18;
    if(dut.live.macro_storage.depth_bank[0].width_lane[0].macro.Q!==16'hxxxx ||
       dut.idle.macro_storage.depth_bank[0].width_lane[0].macro.Q!==16'hxxxx)
      $fatal(1,"unwritten physical macro Q was sanitized");
    $display("XU_SRAM_ACTIVITY_ALIAS_PROBE_PASS gated_clock=1 idle=1 byte_writes=1 unknown_Q=1");
    $finish;
  end
endmodule
