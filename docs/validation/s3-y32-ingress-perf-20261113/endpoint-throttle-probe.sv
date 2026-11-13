`timescale 1ns/1ps
module tb_ingress32_fabric;
 parameter EXPECT_FAST=1;
 reg clk=0,rst_n=0;always #5 clk=~clk;
 wire dr,dv,de;wire [31:0] dd;wire bv,br,bread,rv,rr,re;wire[31:0]ba,bd,rd;wire[3:0]bm;
 wire ev,er;wire[31:0]ea;reg erv=0;wire errdy;
 integer cyc=0,n=0,r=0,first=-1,last=-1,prev=-1,min_gap=99999,max_gap=0;
 xu_systembus_ingress32 #(.TEST_LOADER(0)) ingress(
  .clk(clk),.rst_n(rst_n),.cpu_cmd_valid(1'b0),.cpu_cmd_ready(),.cpu_cmd_addr(32'b0),.cpu_cmd_read(1'b0),.cpu_cmd_wdata(32'b0),.cpu_cmd_wmask(4'b0),.cpu_rsp_valid(),.cpu_rsp_ready(1'b1),.cpu_rsp_err(),.cpu_rsp_rdata(),
  .dma_cmd_valid(rst_n && n<1000),.dma_cmd_ready(dr),.dma_cmd_addr(32'ha0000000),.dma_cmd_read(1'b0),.dma_cmd_wdata(32'h12345678),.dma_cmd_wmask(4'hf),.dma_rsp_valid(dv),.dma_rsp_ready(1'b1),.dma_rsp_err(de),.dma_rsp_rdata(dd),
  .load_cmd_valid(1'b0),.load_cmd_ready(),.load_cmd_addr(32'b0),.load_cmd_read(1'b0),.load_cmd_wdata(32'b0),.load_cmd_wmask(4'b0),.load_rsp_valid(),.load_rsp_ready(1'b1),.load_rsp_err(),.load_rsp_rdata(),
  .bus_cmd_valid(bv),.bus_cmd_ready(br),.bus_cmd_addr(ba),.bus_cmd_read(bread),.bus_cmd_wdata(bd),.bus_cmd_wmask(bm),.bus_rsp_valid(rv),.bus_rsp_ready(rr),.bus_rsp_err(re),.bus_rsp_rdata(rd));
 sirv_icb1to8_bus #(.ICB_FIFO_DP(2),.ICB_FIFO_CUT_READY(1),.SPLT_FIFO_OUTS_NUM(1),.SPLT_FIFO_CUT_READY(1),.O4_BASE_ADDR(32'h80000000),.O4_BASE_REGION_LSB(31)) fabric(
  .clk(clk),.rst_n(rst_n),.o0_icb_enable(1'b0),.o1_icb_enable(1'b0),.o2_icb_enable(1'b0),.o3_icb_enable(1'b0),.o4_icb_enable(1'b1),.o5_icb_enable(1'b0),.o6_icb_enable(1'b0),.o7_icb_enable(1'b0),
  .i_icb_cmd_valid(bv),.i_icb_cmd_ready(br),.i_icb_cmd_addr(ba),.i_icb_cmd_read(bread),.i_icb_cmd_wdata(bd),.i_icb_cmd_wmask(bm),.i_icb_cmd_burst(2'b0),.i_icb_cmd_beat(2'b0),.i_icb_cmd_lock(1'b0),.i_icb_cmd_excl(1'b0),.i_icb_cmd_size(2'b10),
  .i_icb_rsp_valid(rv),.i_icb_rsp_ready(rr),.i_icb_rsp_err(re),.i_icb_rsp_rdata(rd),
  .o4_icb_cmd_valid(ev),.o4_icb_cmd_ready(er),.o4_icb_cmd_addr(ea),.o4_icb_rsp_valid(erv),.o4_icb_rsp_ready(errdy),.o4_icb_rsp_err(1'b0),.o4_icb_rsp_excl_ok(1'b0),.o4_icb_rsp_rdata(32'b0));
 reg[2:0]phase=2;
 always @(posedge clk)if(!rst_n)phase<=2;else phase<=phase==6?0:phase+1'b1;
 assign er=(!erv || errdy) && phase!=0;
 always @(posedge clk)begin
  cyc<=cyc+1;
  if(!rst_n)erv<=0;
  else begin
   if(erv&&errdy)erv<=0;
   if(ev&&er)erv<=1;
   if(n<1000&&dr)begin n<=n+1;if(first<0)first=cyc;last=cyc;if(prev>=0)begin if(cyc-prev<min_gap)min_gap=cyc-prev;if(cyc-prev>max_gap)max_gap=cyc-prev;end prev=cyc;end
   if(dv)begin if(de)$fatal(1,"bus error");r<=r+1;if(r==999)begin
    if(EXPECT_FAST && last-first+1>2100)$fatal(1,"owner bottleneck: 1000 commands took %0d cycles, expected <=2100",last-first+1);
    $display("INGRESS_FABRIC_PASS requests=%0d responses=%0d first=%0d last=%0d acceptance_span=%0d min_gap=%0d max_gap=%0d retire_span=%0d",n,r+1,first,last,last-first+1,min_gap,max_gap,cyc-first+1);$finish;end end
   if(cyc>20000)$fatal(1,"timeout");
  end
 end
 initial begin repeat(4)@(negedge clk);rst_n=1;end
endmodule
