// xu integer transaction API smoke. Synthetic pins; no SRAM or full SoC claim.
`timescale 1ns/1fs
module tb_xu_joint_numeric_smoke;
  reg [9:0] A=0;
  reg CEN=1,CLK=0;
  reg [15:0] D=0;
  reg [2:0] EMA=0;
  reg [1:0] EMAW=0;
  reg GWEN=1,RET1N=1;
  reg [15:0] WEN=16'hffff;
  wire [15:0] Q;
  xu_joint_micro_macro dut(A,CEN,CLK,D,EMA,EMAW,GWEN,Q,RET1N,WEN);
  integer mode=0,task_id=0,cycles=1403985,request_cycle=2394640;
  reg [31:0] source_addr=32'ha0000000,final_addr=32'ha00517fc;
  reg read_flag=1,valid_flag=1,ready_flag=1;
  integer writes=50688;
  initial begin
    if(!$value$plusargs("MODE=%d",mode)) mode=0;
    $xu_sram_joint_register("tb_xu_joint_numeric_smoke.dut",dut.A,dut.CEN,dut.CLK,dut.D,
      dut.EMA,dut.EMAW,dut.GWEN,dut.Q,dut.RET1N,dut.WEN);
    #1;
    if(mode==1) source_addr=32'hx0000000;
    $xu_sram_joint_begin_transaction(task_id,cycles,source_addr,read_flag,valid_flag,ready_flag);
    #1;CEN=0;GWEN=0;CLK=1;D=16'h1234;
    #1;CLK=0;dut.Q=16'habcd;
    #1;
    cycles=2394641;
    if(mode==2) task_id=1;
    if(mode==3) request_cycle=cycles;
    if(mode==4) writes=50687;
    $xu_sram_joint_end_transaction(task_id,cycles,request_cycle,final_addr,
      valid_flag,ready_flag,writes);
    #1;$display("XU_JOINT_NUMERIC_SMOKE_DONE mode=%0d",mode);$finish;
  end
endmodule
