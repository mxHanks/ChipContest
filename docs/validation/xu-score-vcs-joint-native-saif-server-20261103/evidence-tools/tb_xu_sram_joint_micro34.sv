// xu independent variant: owner/actual pin callbacks + native SAIF, no event equivalence assumed.
// xu real continuous pin event microbenchmark, not a vendor SRAM model.
`timescale 1ns/1fs
module xu_joint_micro_macro(input [9:0] A,input CEN,CLK,input [15:0] D,
  input [2:0] EMA,input [1:0] EMAW,input GWEN,output reg [15:0] Q,
  input RET1N,input [15:0] WEN);
  initial Q=16'hxxxx;
endmodule
module tb_xu_sram_joint_micro;
  reg [9:0] A=0;
  reg CEN=1,CLK=0;
  reg [15:0] D=0;
  reg [2:0] EMA=0;
  reg [1:0] EMAW=0;
  reg GWEN=1,RET1N=1;
  reg [15:0] WEN=16'hffff;
  wire [15:0] Q;
  xu_joint_micro_macro dut(A,CEN,CLK,D,EMA,EMAW,GWEN,Q,RET1N,WEN);
  integer mode=0,i;
  string out;
  reg xu_probe_live=0;
  task xu_micro_begin(input string identity);
    begin
`ifndef XU_JOINT_HOST_NO_SAIF
      $toggle_start();
`endif
      xu_probe_live=1;
      $xu_probe_begin();
      $xu_sram_joint_begin(0,out,identity);
    end
  endtask
  task xu_micro_end(input string identity);
    begin
      $xu_sram_joint_end(0,identity);
      $xu_probe_end();
      xu_probe_live=0;
`ifndef XU_JOINT_HOST_NO_SAIF
      $toggle_stop();
      $toggle_report("native.saif",1.0e-15,"tb_xu_sram_joint_micro");
`endif
    end
  endtask
  always @(CLK) if(xu_probe_live) $display("XU_SV_EVENT role=owner_CLK tick=%0.0f value=%b",$realtime*1000000.0,CLK);
  always @(dut.CLK) if(xu_probe_live) $display("XU_SV_EVENT role=actual_CLK tick=%0.0f value=%b",$realtime*1000000.0,dut.CLK);
  always @(D) if(xu_probe_live) $display("XU_SV_EVENT role=owner_D tick=%0.0f value=%b",$realtime*1000000.0,D);
  always @(dut.D) if(xu_probe_live) $display("XU_SV_EVENT role=actual_D tick=%0.0f value=%b",$realtime*1000000.0,dut.D);
  always @(dut.Q) if(xu_probe_live) $display("XU_SV_EVENT role=owner_Q tick=%0.0f value=%b",$realtime*1000000.0,dut.Q);
  always @(Q) if(xu_probe_live) $display("XU_SV_EVENT role=connected_Q tick=%0.0f value=%b",$realtime*1000000.0,Q);
  initial begin
`ifndef XU_JOINT_HOST_NO_SAIF
    $set_gate_level_monitoring("rtl_on");
    $set_toggle_region(tb_xu_sram_joint_micro);
`endif
    $xu_probe_register("owner_CLK",CLK);
    $xu_probe_register("actual_CLK",dut.CLK);
    $xu_probe_register("owner_D",D);
    $xu_probe_register("actual_D",dut.D);
    $xu_probe_register("owner_Q",dut.Q);
    $xu_probe_register("connected_Q",Q);
    $xu_probe_register("owner_CEN",CEN);
    $xu_probe_register("actual_CEN",dut.CEN);
    if(!$value$plusargs("MODE=%d",mode)) mode=0;
    if(!$value$plusargs("OUT=%s",out)) $fatal(1,"OUT required");
    $xu_sram_joint_register("tb_xu_sram_joint_micro.dut",dut.A,dut.CEN,dut.CLK,dut.D,
      dut.EMA,dut.EMAW,dut.GWEN,dut.Q,dut.RET1N,dut.WEN);
    #1;
    if(mode==1 || mode==2) begin
      CEN=0;GWEN=(mode==1)?0:1;
      #1;xu_micro_begin("micro_correlation_begin");
      #2;CEN=1;GWEN=(mode==1)?1:0;
      #2;xu_micro_end("micro_correlation_end");
    end else if(mode==3) begin
      #1;xu_micro_begin("unfinished_begin");
      #2;
    end else begin
      #1;xu_micro_begin("micro_request");
      // Q stays X in standby but its actual Liberty condition is still true.
      #3;
      // All 256 known control tuples, without assuming independence.
      for(i=0;i<256;i=i+1) begin
        RET1N=i[7];CEN=i[6];GWEN=i[5];EMA=i[4:2];EMAW=i[1:0];
        #1;CLK=1;
        #1;CLK=0;
      end
      // Mixed WEN/GWEN states have neither of the two D conditions true.
      WEN=0;GWEN=0;D=16'hffff;#1;
      WEN=16'hffff;GWEN=1;D=0;#1;
      WEN=0;GWEN=1;D=16'h5555;#1;
      WEN=16'hffff;GWEN=0;D=16'haaaa;#1;
      RET1N=0;CEN=1'bx;EMA=3'bxxx;EMAW=2'bzz;GWEN=1'bx;
      #1;CLK=1'bx;#1;CLK=1'bz;#1;CLK=0;
      // Same timestamp active, #0/inactive and NBA changes remain events.
      RET1N=1;CEN=1;GWEN=1;EMA=0;EMAW=0;
      #1;CLK=1;CLK=0;CLK=1;D=16'h1234;
      dut.Q<=16'h1111;CEN<=0;
      #0;D=16'h5678;dut.Q<=16'h2222;
      #1;
      // Boundary changes are intentionally retained as uncertain-order data.
      CLK=0;CEN=1;
      xu_micro_end("micro_final_y_retire");
    end
    #1;$display("XU_JOINT_MICRO_DONE mode=%0d",mode);$finish;
  end
endmodule
