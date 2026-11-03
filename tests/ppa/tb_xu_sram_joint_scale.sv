// xu 352-instance registration/continuous-event scale check, open geometry only.
// This is neither a SRAM model nor a whole SoC/vendor/power simulation.
`timescale 1ns/1fs
module tb_xu_sram_joint_scale;
  reg clk=0;
  always #0.5 clk=~clk;
  string out;
  genvar index;
  for(index=0;index<352;index=index+1) begin: macro_instances
    wire [15:0] q;
    xu_joint_micro_macro dut(.A(10'b0),.CEN(1'b1),.CLK(clk),.D(16'b0),
      .EMA(3'b0),.EMAW(2'b0),.GWEN(1'b1),.Q(q),.RET1N(1'b1),.WEN(16'hffff));
    initial $xu_sram_joint_register($sformatf("tb_xu_sram_joint_scale.macro_instances[%0d].dut",index),
      dut.A,dut.CEN,dut.CLK,dut.D,dut.EMA,dut.EMAW,dut.GWEN,dut.Q,dut.RET1N,dut.WEN);
  end
  initial begin
    if(!$value$plusargs("OUT=%s",out)) $fatal(1,"OUT required");
    #1.25;$xu_sram_joint_begin(0,out,"scale352_begin");
    #100;$xu_sram_joint_end(0,"scale352_end");
    #1;$finish;
  end
endmodule
