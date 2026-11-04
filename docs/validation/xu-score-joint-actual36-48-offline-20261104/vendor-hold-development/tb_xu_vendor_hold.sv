// xu frozen vendor hold-case check. No force, hierarchical drive or memory init.
`timescale 1ns/1ps
module tb_xu_vendor_hold;
reg clk=0,ret=1,gwen=1;reg [2:0] cen=3'b111;reg [9:0] addr=0;
reg [15:0] wen=16'hffff,d1=0,d2=16'hffff;reg [2:0] ema=2;reg [1:0] emaw=0;
wire [15:0] q0,q1,q2;integer i,mode=0;reg live=0;integer transitions=0;
RAMSP1024X16 untouched(q0,clk,cen[0],wen,addr,d1,ema,emaw,gwen,ret);
RAMSP1024X16 seeded_zero(q1,clk,cen[1],wen,addr,d1,ema,emaw,gwen,ret);
RAMSP1024X16 seeded_one(q2,clk,cen[2],wen,addr,d2,ema,emaw,gwen,ret);
always @(q0 or q1 or q2) if(live) transitions=transitions+1;
task cycle;
begin #5;clk=1;#5;clk=0;#1;end
endtask
task check_held;
begin
 if(q0!==16'hxxxx || q1!==16'h0000 || q2!==16'hffff || transitions!=0)
  $fatal(1,"XU_VENDOR_HOLD_REJECT mode=%0d i=%0d q0=%h q1=%h q2=%h transitions=%0d",mode,i,q0,q1,q2,transitions);
end
endtask
initial begin
 if(!$value$plusargs("MODE=%d",mode)) mode=0;
 #2;cycle();cen=3'b001;gwen=0;wen=0;cycle(); // ordinary writes seed two different arbitrary initial output classes
 gwen=1;wen=16'hffff;cycle(); // ordinary read obtains 0 / ffff; untouched stays X
 cen=3'b111;#2;
 check_held();live=1;
 for(i=0;i<256;i=i+1) begin
  addr=(i*37)&1023;d1=(i*953)^16'h5ac3;d2=~d1;wen=(i*79)^16'ha5c3;
  gwen=i[0];ema=2+(i%6);emaw=i[1:0];
  if(mode==1 && i==17) begin cen[1]=0;addr=10'd999;gwen=1;end
  if(mode==2 && i==17) ret=1'bx;
  cycle();check_held();
 end
 live=0;$display("XU_VENDOR_HOLD_PASS mode=%0d cycles=256 untouched_x=1 seeded0=1 seeded1=1 q_events=0",mode);$finish;
end
endmodule
