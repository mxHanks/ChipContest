`ifdef XU_VENDOR_SRAM_MODEL
  `define XU_MODEL_NAME "vendor-functional"
`else
  `define XU_MODEL_NAME "open-contract-stand-in"
`endif
module xu_adapter_case #(parameter DW=32, MW=DW/8, DP=2048, AW=$clog2(DP)) (output reg done=0);
  reg clk=0;
  always #5 clk=~clk;
  reg cs=0,we=0;
  reg [AW-1:0] addr=0;
  reg [DW-1:0] din=0;
  reg [MW-1:0] wem=0;
  wire [DW-1:0] got,want;
  sirv_sim_ram #(.DW(DW),.MW(MW),.DP(DP),.AW(AW),.FORCE_X2ZERO(0)) dut
    (.clk(clk),.din(din),.addr(addr),.cs(cs),.we(we),.wem(wem),.dout(got));
  xu_reference_sirv_sim_ram #(.DW(DW),.MW(MW),.DP(DP),.AW(AW),.FORCE_X2ZERO(0)) reference
    (.clk(clk),.din(din),.addr(addr),.cs(cs),.we(we),.wem(wem),.dout(want));
  integer cycle=0,i,j;
  task step(input en,input wr,input [AW-1:0] a,input [DW-1:0] d,input [MW-1:0] mask);
    begin
      @(negedge clk);cs=en;we=wr;addr=a;din=d;wem=mask;
      @(posedge clk);#1;cycle=cycle+1;
      if (got!==want) $fatal(1,"SRAM mismatch DW=%0d cycle=%0d a=%0d got=%h want=%h",DW,cycle,a,got,want);
    end
  endtask
  initial begin
    // Initialize written cells before comparing reads. Initial X is preserved.
    for(i=0;i<DP;i=i+1) step(1,1,i,64'h1020304050607080^i,{MW{1'b1}});
    for(i=0;i<DP;i=i+1) begin
      step(1,0,i,0,0);
      step(0,0,DP-1-i,0,0); // address noise must not change held read
      for(j=0;j<MW;j=j+1) step(1,1,i,64'hffeeddccbbaa9988 ^ (i+j),1<<j);
      step(0,1,i,0,{MW{1'b1}}); // disabled write
      step(1,1,(i+1024)%DP,64'h0102030405060708,{MW{1'b1}});
      step(1,0,(i+1024)%DP,0,0); // read delayed bank selection boundary
    end
    for(i=0;i<1000;i=i+1) step($random,$random,$urandom%DP,{$random,$random},$random);
    $display("XU_SRAM_ADAPTER_CONTRACT_PASS DW=%0d DP=%0d cycles=%0d model=%s",DW,DP,cycle,`XU_MODEL_NAME);
    done=1;
  end
endmodule
module tb_xu_sram_adapter;
  wire a,b;
  xu_adapter_case #(.DW(32)) a32(a);
  xu_adapter_case #(.DW(64)) b64(b);
  initial begin wait(a&&b);$display("XU_SRAM_ADAPTER_ALL_CONTRACT_PASS model=%s",`XU_MODEL_NAME);$finish;end
  initial begin #1000000;$fatal(1,"timeout");end
endmodule
