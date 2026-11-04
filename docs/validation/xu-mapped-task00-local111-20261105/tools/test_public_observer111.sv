// xu host-only protocol contract fixture. No SoC/model/functionality claim.
`timescale 1ns/1fs
module tb_xu_soc_ppa;
 reg a_cmd_valid=0,a_cmd_ready=1,a_cmd_read=0,a_rsp_valid=0,a_rsp_ready=1,a_rsp_err=0,a_rst_n=1;
 reg[31:0]a_cmd_addr=0,a_cmd_wdata=0,a_rsp_rdata=0;reg[3:0]a_cmd_wmask=15;
 integer a_reset_seen=1,a_reset_ready=1,a_reset_edges=4594,cycles=1403985;
 reg[15:0]w[0:16383],x[0:6335];reg[39:0]bias[0:255];reg[47:0]golden[0:25343];
 reg[31:0]cmd_addr=32'ha0008000;
`include "xu_public_observer111.svh"
 task issue_write(input[11:0]address,input[31:0]data);
  begin a_cmd_addr=32'h10042000+address;a_cmd_wdata=data;a_cmd_read=0;a_cmd_valid=1;a_rsp_valid=0;observe_mmio();a_cmd_valid=0;a_rsp_valid=1;a_rsp_rdata=0;observe_mmio();a_rsp_valid=0;end
 endtask
 task issue_read(input[11:0]address,input[31:0]data);
  begin a_cmd_addr=32'h10042000+address;a_cmd_read=1;a_cmd_valid=1;a_rsp_valid=0;observe_mmio();a_cmd_valid=0;a_rsp_valid=1;a_rsp_rdata=data;observe_mmio();a_rsp_valid=0;end
 endtask
 integer b,j,row,group,lane,index,mode=0;reg[31:0]data;
 initial begin
  if(!$value$plusargs("MODE=%d",mode))mode=0;
  for(j=0;j<256;j=j+1)begin clear_bias_seen[j]=0;payload_bias_seen[j]=0;bias[j]=40'h8000000000+j*17;end
  for(j=0;j<8;j=j+1)clear_legacy_seen[j]=0;
  for(j=0;j<16384;j=j+1)w[j]=(j*31)^16'h852a;
  for(j=0;j<6336;j=j+1)x[j]=(j*17)^16'h3a55;
  for(j=0;j<25344;j=j+1)golden[j]=48'h800000000000+j*937;
  issue_write(12'h040,0);
  for(b=0;b<8;b=b+1)begin issue_write(12'h01c,b);for(j=0;j<2048;j=j+1)begin issue_write(12'h020,j);if(!(mode==1&&b==7&&j==2047))issue_write(12'h024,0);end end
  if(mode==2)begin issue_write(12'h020,2047);issue_write(12'h024,0);end
  for(j=0;j<256;j=j+1)begin issue_write(12'h044,j);issue_write(12'h048,0);issue_write(12'h04c,0);end
  for(j=0;j<8;j=j+1)begin issue_write(12'h028,j);issue_write(12'h02c,0);issue_write(12'h030,0);end
  for(j=0;j<64;j=j+1)begin issue_write(12'h014,j);issue_write(12'h018,0);end
  start_window();
  issue_write(12'h054,0);
  for(j=0;j<8192;j=j+1)begin data={w[2*j+1],w[2*j]};if(mode==3&&j==8191)data=data^1;issue_write(12'h05c,data);end
  issue_write(12'h040,0);
  for(j=0;j<256;j=j+1)begin issue_write(12'h044,j);issue_write(12'h048,bias[j][31:0]);issue_write(12'h04c,{24'b0,bias[j][39:32]});end
  issue_write(12'h040,1);
  for(row=0;row<99;row=row+1)begin
   issue_write(12'h060,0);
   for(j=0;j<32;j=j+1)issue_write(12'h068,{x[row*64+2*j+1],x[row*64+2*j]});
   issue_write(12'h0c0,1);
   for(group=0;group<32;group=group+1)begin
    for(lane=0;lane<16;lane=lane+1)begin index=row*256+group*8+lane/2;data=lane%2?{16'b0,golden[index][47:32]}:golden[index][31:0];if(mode==4&&row==98&&group==31&&lane==15)data=data^1;issue_read(12'h100+lane*4,data);end
    issue_write(12'h0c8,1);
   end
  end
  if(payload_w_pairs!=8192||payload_x_pairs!=3168||payload_bias!=256||payload_rows!=99||payload_pops!=3168||result_reads!=50688||clear_writes!=33697)$fatal(1,"XU_MAPPED111_HOST_CONTRACT_REJECT totals");
  source_reads=23232;
  if(mode==5)end_window(); // Real cycle/tick gate must reject invented phase.
  $display("XU_MAPPED111_HOST_PUBLIC_CONTRACT_PASS ONLY_GENERATED_BUS_FIXTURE_NOT_SOC_OR_ACTIVITY_OR_ENERGY_PROOF");$finish;
 end
endmodule
