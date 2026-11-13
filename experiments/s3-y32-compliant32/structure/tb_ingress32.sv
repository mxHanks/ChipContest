`timescale 1ns/1ps
module tb_ingress32;
  parameter HAS_LOAD=1;
  reg clk=0,rst_n=0;always #5 clk=~clk;
  reg [2:0] valid=0,read=3'b101,rready=3'b111;
  wire [2:0] ready,rvalid,rerr;
  wire [31:0] rdata[0:2];
  reg [31:0] addr[0:2],data[0:2];reg [3:0] mask[0:2];
  wire bv,br;reg bready=0;wire [31:0] ba,bd;wire [3:0] bm;
  reg rv=0,re=0;reg [31:0] rd=0;wire rr;
  integer accepts=0,responses=0,outstanding=0,max_outstanding=0,last_owner=-1;
  integer accepted[0:2],retired[0:2];reg [2:0] drop=0;
  reg stalled=0;reg[68:0] saved;integer i;
  xu_systembus_ingress32 #(.TEST_LOADER(HAS_LOAD)) dut(
    .clk(clk),.rst_n(rst_n),
    .cpu_cmd_valid(valid[0]),.cpu_cmd_ready(ready[0]),.cpu_cmd_addr(addr[0]),.cpu_cmd_read(read[0]),.cpu_cmd_wdata(data[0]),.cpu_cmd_wmask(mask[0]),
    .cpu_rsp_valid(rvalid[0]),.cpu_rsp_ready(rready[0]),.cpu_rsp_err(rerr[0]),.cpu_rsp_rdata(rdata[0]),
    .dma_cmd_valid(valid[1]),.dma_cmd_ready(ready[1]),.dma_cmd_addr(addr[1]),.dma_cmd_read(read[1]),.dma_cmd_wdata(data[1]),.dma_cmd_wmask(mask[1]),
    .dma_rsp_valid(rvalid[1]),.dma_rsp_ready(rready[1]),.dma_rsp_err(rerr[1]),.dma_rsp_rdata(rdata[1]),
    .load_cmd_valid(valid[2]),.load_cmd_ready(ready[2]),.load_cmd_addr(addr[2]),.load_cmd_read(read[2]),.load_cmd_wdata(data[2]),.load_cmd_wmask(mask[2]),
    .load_rsp_valid(rvalid[2]),.load_rsp_ready(rready[2]),.load_rsp_err(rerr[2]),.load_rsp_rdata(rdata[2]),
    .bus_cmd_valid(bv),.bus_cmd_ready(bready),.bus_cmd_addr(ba),.bus_cmd_read(br),.bus_cmd_wdata(bd),.bus_cmd_wmask(bm),
    .bus_rsp_valid(rv),.bus_rsp_ready(rr),.bus_rsp_err(re),.bus_rsp_rdata(rd));
  always @(posedge clk)begin
    if(!rst_n)begin outstanding=0;stalled=0;end
    else begin
      if(stalled && (!bv || {ba,br,bd,bm}!==saved))$fatal(1,"downstream payload changed under stall");
      stalled=bv&&!bready;saved={ba,br,bd,bm};
      for(integer k=0;k<3;k=k+1)begin
        if(valid[k]&&ready[k])begin accepted[k]=accepted[k]+1;drop[k]=1;end
        if(rvalid[k]&&rready[k])begin
          if(k!=last_owner || rdata[k]!==rd || rerr[k]!==re)$fatal(1,"response wrong owner/payload/error");
          retired[k]=retired[k]+1;responses=responses+1;
        end
      end
      if(rv&&rr)outstanding=outstanding-1;
      if(bv&&bready)begin
        last_owner=ba[9:8];accepts=accepts+1;outstanding=outstanding+1;
        if(last_owner>2 || ba!==addr[last_owner] || bd!==data[last_owner] || bm!==mask[last_owner] || br!==read[last_owner])$fatal(1,"command fields corrupted");
      end
      if(outstanding<0||outstanding>1)$fatal(1,"outstanding limit changed");
      if(outstanding>max_outstanding)max_outstanding=outstanding;
    end
  end
  always @(negedge clk)begin
    for(integer k=0;k<3;k=k+1)if(drop[k])begin valid[k]=0;drop[k]=0;end
  end
  task tick;begin @(posedge clk);#2;end endtask
  task respond(input integer owner,input bit err);
    integer target;
    begin
      target=responses+1;
      @(negedge clk);#1;rv=1;rd=32'ha5500000+owner;re=err;
      while(responses<target)tick();
      @(negedge clk);#1;rv=0;re=0;
    end
  endtask
  initial begin
    for(i=0;i<3;i=i+1)begin addr[i]=32'ha0000000+(i<<8);data[i]=32'h52340000+i;mask[i]=4'hf-i;accepted[i]=0;retired[i]=0;end
    repeat(3)tick();@(negedge clk);#1;rst_n=1;valid[1]=1;
    repeat(2)tick();if(!bv||ba!==addr[1])$fatal(1,"DMA initial offer missing");
    @(negedge clk);#1;valid[0]=1;valid[2]=1;
    repeat(3)begin tick();if(!bv||ba!==addr[1])$fatal(1,"new requester stole stalled DMA grant");end
    @(negedge clk);#1;bready=1;
    while(accepts<1)tick();if(last_owner!=1)$fatal(1,"first owner not DMA");
    @(negedge clk);#1;rv=1;rd=32'hdecaf123;re=1;rready[1]=0;
    repeat(4)begin tick();if(rvalid!==3'b010||!rerr[1]||rdata[1]!==32'hdecaf123||accepts!=1)$fatal(1,"blocked error response not held for DMA");end
    @(negedge clk);#1;rready[1]=1;tick();@(negedge clk);#1;rv=0;re=0;
    while(accepts<2)tick();respond(last_owner,0);
    if(HAS_LOAD)begin while(accepts<3)tick();respond(last_owner,0);end
    repeat(2)tick();if(!HAS_LOAD && (ready[2]||rvalid[2]||accepted[2]))$fatal(1,"production loader activated");
    if(accepted[0]!=1||accepted[1]!=1||(HAS_LOAD&&accepted[2]!=1))$fatal(1,"CPU/DMA/loader arbitration missing");
    // Joint SystemBus reset discards the pending owner with the endpoint.
    @(negedge clk);#1;valid=3'b001;
    while(accepted[0]<2)tick();
    @(negedge clk);#1;rst_n=0;rv=0;valid=0;repeat(2)tick();
    @(negedge clk);#1;rst_n=1;rv=1;rd=32'hbad00000;re=1;
    repeat(2)begin tick();if(rvalid||rr)$fatal(1,"old response leaked without an owned request after reset");end
    @(negedge clk);#1;rv=0;re=0;valid[1]=1;
    while(accepted[1]<2)tick();respond(1,0);repeat(2)tick();
    if(outstanding||retired[1]!=2||retired[0]!=1)$fatal(1,"reset recovery/drain mismatch");
    $display("INGRESS32_PASS loader=%0d accepted=%0d responses=%0d max_outstanding=%0d stable_stall=1 error_route=1 reset_recovery=1",HAS_LOAD,accepts,responses,max_outstanding);$finish;
  end
  initial begin #10000;$fatal(1,"ingress timeout");end
endmodule
