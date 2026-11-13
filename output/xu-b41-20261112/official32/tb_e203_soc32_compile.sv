`timescale 1ns/1ps
module tb_e203_soc32_compile;
  e203_soc_top #(.EXTERNAL_SYSMEM(1)) dut();
  initial begin
    #2;
    $display("OFFICIAL32_SOC_ELAB_PASS");
    $finish;
  end
endmodule
