`timescale 1ns/1fs
module xu_probe_dut(input wire clk);
 reg q=0;reg[3:0]count=0;
 always @(posedge clk)begin q<=~q;count<=count+1;end
 wire[15:0]Q;wire[9:0]A=10'd0;wire[15:0]D=16'h55aa;
 wire CEN=0,GWEN=(count>1);wire[15:0]WEN=16'b0;
 RAMSP1024X16 macro(.Q(Q),.CLK(clk),.CEN(CEN),.WEN(WEN),.A(A),.D(D),.EMA(3'b010),.EMAW(2'b00),.GWEN(GWEN),.RET1N(1'b1));
endmodule
module tb_xu_cell;
 reg clk=0;always #5 clk=~clk;xu_probe_dut dut(.clk(clk));string policy;
 initial begin
  if(!$value$plusargs("POLICY=%s",policy))$fatal(1,"missingpolicy");
  $dumpfile("ports.vcd");$dumpvars(0,tb_xu_cell.dut.macro.CLK,tb_xu_cell.dut.macro.CEN,tb_xu_cell.dut.macro.WEN,tb_xu_cell.dut.macro.A,tb_xu_cell.dut.macro.D,tb_xu_cell.dut.macro.EMA,tb_xu_cell.dut.macro.EMAW,tb_xu_cell.dut.macro.GWEN,tb_xu_cell.dut.macro.RET1N,tb_xu_cell.dut.macro.Q);
  case(policy)
   "default":begin end
   "on":$set_gate_level_monitoring("on");
   "rtl_on":$set_gate_level_monitoring("rtl_on");
   "rtl_then_on":begin $set_gate_level_monitoring("rtl_on");$set_gate_level_monitoring("on");end
   "on_then_rtl":begin $set_gate_level_monitoring("on");$set_gate_level_monitoring("rtl_on");end
   default:$fatal(1,"policy");
  endcase
  $set_toggle_region(tb_xu_cell.dut);#22;$toggle_start();#40;$toggle_stop();
  $toggle_report("task.saif",1.0e-15,"tb_xu_cell.dut");
  if(dut.Q!==16'h55aa)$fatal(1,"macrofunction");
  $display("XU_CELL_PROBE_PASS policy=%s Q=%h",policy,dut.Q);$finish;
 end
endmodule
