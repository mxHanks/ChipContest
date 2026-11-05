`timescale 1ns/1ps
// Compare actual platform geometries against the unchanged Nuclei model.
module xu_geometry_case #(
  parameter DW=32, DP=131072, MW=(DW+7)/8, AW=$clog2(DP), FZ=0
)(output reg done=0);
  reg clk=0;
  always #5 clk=~clk;
  reg cs=0,we=0;
  reg [AW-1:0] addr=0;
  reg [DW-1:0] din=0;
  reg [MW-1:0] wem=0;
  wire [DW-1:0] got,want;
  sirv_sim_ram #(.DW(DW),.DP(DP),.MW(MW),.AW(AW),.FORCE_X2ZERO(FZ)) dut
    (.clk(clk),.din(din),.addr(addr),.cs(cs),.we(we),.wem(wem),.dout(got));
  xu_reference_sirv_sim_ram #(.DW(DW),.DP(DP),.MW(MW),.AW(AW),.FORCE_X2ZERO(FZ)) reference
    (.clk(clk),.din(din),.addr(addr),.cs(cs),.we(we),.wem(wem),.dout(want));
  integer cycles=0,bank,edge_index,a,j,i;
  integer seed=32'h78563412;
  task step(input en,input wr,input [AW-1:0] address,input [DW-1:0] data,input [MW-1:0] mask);
    begin
      @(negedge clk);cs=en;we=wr;addr=address;din=data;wem=mask;
      @(posedge clk);#1;cycles=cycles+1;
      if(got!==want) $fatal(1,"geometry mismatch DW=%0d DP=%0d FZ=%0d cycle=%0d got=%h want=%h",DW,DP,FZ,cycles,got,want);
    end
  endtask
  task exercise(input integer address);
    begin
      // Unwritten read, all-zero write mask, same-address forwarding,
      // disabled writes and a different-bank write while retaining the read.
      step(1,0,address,0,0);
      step(1,1,address,{$random(seed),$random(seed)},0);
      step(1,1,address,{$random(seed),$random(seed)},{MW{1'b1}});
      for(j=0;j<MW;j=j+1)
        step(1,1,address,{$random(seed),$random(seed)},1<<j);
      step(0,1,address,0,{MW{1'b1}});
      step(1,1,(address+1024)%DP,{$random(seed),$random(seed)},{MW{1'b1}});
      step(0,0,(address+1024)%DP,0,0);
      step(1,0,(address+1024)%DP,0,0);
      step(1,0,address,0,0);
    end
  endtask
  initial begin
    // Every bank boundary and all byte lanes; avoid initializing 512KiB
    // merely to read a few words. Unknown bits must match in four-state sim.
    for(bank=0;bank<(DP+1023)/1024;bank=bank+1)
      for(edge_index=0;edge_index<4;edge_index=edge_index+1) begin
        case(edge_index)
          0:a=bank*1024;
          1:a=bank*1024+1;
          2:a=bank*1024+1022;
          3:a=bank*1024+1023;
        endcase
        if(a<DP) exercise(a);
      end
    for(i=0;i<128;i=i+1) begin
      a=($random(seed)&32'h7fffffff)%DP;
      exercise(a);
    end
    $display("XU_SRAM_GEOMETRY_PASS DW=%0d DP=%0d FZ=%0d cycles=%0d",DW,DP,FZ,cycles);
    done=1;
  end
endmodule
module tb_xu_sram_geometry;
  wire a,b,c,d,e,f;
  xu_geometry_case #(.DW(64),.DP(8192)) itcm(a);
  xu_geometry_case #(.DW(32),.DP(16384)) dtcm(b);
  xu_geometry_case #(.DW(32),.DP(131072)) shared(c);
  xu_geometry_case #(.DW(32),.DP(7)) debug_ram(d);
  xu_geometry_case #(.DW(32),.DP(1024),.FZ(1)) force_zero(e);
  xu_geometry_case #(.DW(13),.DP(7),.FZ(1)) partial_byte(f);
  initial begin wait(a&&b&&c&&d&&e&&f);$display("XU_SRAM_ALL_GEOMETRIES_PASS");$finish;end
  initial begin #1000000;$fatal(1,"geometry timeout");end
endmodule
