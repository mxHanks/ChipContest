`timescale 1ns/1ps
module tb_ingress32_pipeline;
  parameter HAS_LOAD=1;
  reg clk=0,rst_n=0; always #5 clk=~clk;
  reg [2:0] valid=0,read=3'b101,rready=3'b111;
  wire [2:0] ready,rvalid,rerr;
  wire [31:0] rdata[0:2];
  reg [31:0] addr[0:2],data[0:2];
  reg [3:0] mask[0:2];
  wire bv,br; reg bready=0;
  wire [31:0] ba,bd; wire [3:0] bm;
  reg response_enable=0,fake_response=0,stop_commands=0;
  wire rv,rr,re; wire [31:0] rd;
  reg [1:0] owners[0:255];
  reg [31:0] payloads[0:255]; reg errors[0:255];
  integer head=0,tail=0,count=0,accepts=0,responses=0,dropped=0;
  integer max_outstanding=0,simultaneous=0,error_count=0,stalls=0;
  integer accepted[0:2],retired[0:2],sequence_no[0:2];
  reg [2:0] advance=0;
  reg stalled=0; reg [68:0] saved;
  reg [2:0] expected_rsp;
  integer source_count,owner,cycle=0,i;
  wire push=bv&&bready,pop=rv&&rr;
  assign rv=fake_response || (response_enable && count!=0);
  assign rd=count!=0 ? payloads[head] : 32'hbad0bad0;
  assign re=count!=0 ? errors[head] : 1'b1;

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

  // The endpoint deliberately accepts ordered commands independently of their
  // responses. Its scoreboard checks owner order at every response, including
  // concurrent enqueue/dequeue and wraparound of the ingress's four entries.
  always @(posedge clk) begin
    cycle=cycle+1;
    advance=0;
    if(!rst_n) begin
      dropped=dropped+count;head=0;tail=0;count=0;stalled=0;
      if(ready || rvalid || rr || bv)$fatal(1,"reset handshake leaked");
    end else begin
      if(stalled && (!bv || {ba,br,bd,bm}!==saved))$fatal(1,"payload changed under command stall");
      stalled=bv&&!bready;saved={ba,br,bd,bm};
      if(stalled)stalls=stalls+1;
      if(!HAS_LOAD && (ready[2] || rvalid[2]))$fatal(1,"production loader became active");
      source_count=0;
      for(integer k=0;k<3;k=k+1)begin
        if(valid[k]&&ready[k])begin
          accepted[k]=accepted[k]+1;advance[k]=1;source_count=source_count+1;
        end
      end
      if(source_count!=(push?1:0))$fatal(1,"source/fabric command handshake mismatch");
      expected_rsp=0;
      if(rv && count!=0)expected_rsp[owners[head]]=1;
      if(rvalid!==expected_rsp)$fatal(1,"response owner/order mismatch got=%b expected=%b",rvalid,expected_rsp);
      if(count==0 && rr)$fatal(1,"unowned response accepted");
      if(count!=0 && rv && rr!==rready[owners[head]])$fatal(1,"response backpressure routed to wrong source");
      for(integer k=0;k<3;k=k+1)if(rvalid[k])begin
        if(rdata[k]!==rd || rerr[k]!==re)$fatal(1,"response payload/error corrupted");
        if(rready[k])begin retired[k]=retired[k]+1;responses=responses+1;if(re)error_count=error_count+1;end
      end
      if(push && pop)simultaneous=simultaneous+1;
      if(push)begin
        owner=ba[9:8];
        if(owner>2 || (!HAS_LOAD&&owner==2) || !advance[owner])$fatal(1,"unknown source");
        if(ba!==addr[owner] || bd!==data[owner] || bm!==mask[owner] || br!==read[owner])$fatal(1,"command payload corrupted");
        owners[tail]=owner;payloads[tail]=ba^bd^32'hcafe9000;errors[tail]=bd[0];
        tail=(tail+1)%256;accepts=accepts+1;
      end
      if(pop)head=(head+1)%256;
      case({push,pop})
        2'b10:count=count+1;
        2'b01:count=count-1;
      endcase
      if(count<0 || count>4)$fatal(1,"owner FIFO capacity violated: %0d",count);
      if(count>max_outstanding)max_outstanding=count;
    end
  end
  always @(negedge clk)begin
    for(integer k=0;k<3;k=k+1)if(advance[k])begin
      if(stop_commands)valid[k]=0;
      sequence_no[k]=sequence_no[k]+1;
      addr[k]=32'ha0000000+(sequence_no[k]<<12)+(k<<8);
      data[k]=32'h52340000+(sequence_no[k]<<2)+k;
      mask[k]=4'hf-(sequence_no[k]%7);
      read[k]=sequence_no[k][0];
    end
  end
  task tick;begin @(posedge clk);#2;end endtask
  task drive;begin @(negedge clk);#1;end endtask
  initial begin
    for(i=0;i<3;i=i+1)begin addr[i]=32'ha0000000+(i<<8);data[i]=32'h52340000+i;mask[i]=4'hf-i;accepted[i]=0;retired[i]=0;sequence_no[i]=0;end
    repeat(3)tick();drive();rst_n=1;valid=3'b010;
    repeat(2)tick();if(!bv||ba[9:8]!=1)$fatal(1,"initial DMA offer missing");
    drive();valid=3'b111;
    repeat(3)begin tick();if(!bv||ba[9:8]!=1)$fatal(1,"new requester stole stalled DMA grant");end
    drive();bready=1;
    while(accepts<4)tick();
    repeat(3)begin tick();if(accepts!=4||bv||ready)$fatal(1,"owner FIFO did not stop at four");end
    drive();response_enable=1;rready[1]=0;
    repeat(4)begin tick();if(rvalid!==3'b010 || !rerr[1] || rr || accepts!=4)$fatal(1,"blocked DMA error response changed or owner full ignored");end
    drive();rready=3'b111;
    for(i=0;i<300;i=i+1)begin
      drive();bready=(i%9!=2 && i%9!=3);rready[0]=(i%7!=0);rready[1]=(i%5!=0);rready[2]=(i%11!=0);
    end
    drive();stop_commands=1;if(!HAS_LOAD)valid[2]=0;bready=1;rready=3'b111;
    while(valid || count)tick();
    if(accepted[0]<20||accepted[1]<20||(HAS_LOAD&&accepted[2]<20))$fatal(1,"round-robin fairness lost");
    if(max_outstanding!=4||simultaneous<20||error_count<10||stalls<10)$fatal(1,"pipeline coverage incomplete");
    // A joint reset drops all four endpoint commands and their owner IDs.
    drive();stop_commands=0;response_enable=0;valid=3'b111;
    while(count<4)tick();
    drive();rst_n=0;valid=0;repeat(2)tick();
    drive();rst_n=1;fake_response=1;
    repeat(3)begin tick();if(rvalid||rr)$fatal(1,"old response leaked after reset");end
    drive();fake_response=0;valid=3'b010;
    tick();drive();valid=0;response_enable=1;
    while(count)tick();repeat(2)tick();
    if(accepts!=responses+dropped||dropped!=4)$fatal(1,"drain/reset accounting mismatch");
    $display("INGRESS_PIPELINE_PASS loader=%0d accepted=%0d responses=%0d reset_dropped=%0d max_outstanding=%0d simultaneous=%0d errors=%0d stalls=%0d",HAS_LOAD,accepts,responses,dropped,max_outstanding,simultaneous,error_count,stalls);$finish;
  end
  initial begin #50000;$fatal(1,"ingress pipeline timeout");end
endmodule
