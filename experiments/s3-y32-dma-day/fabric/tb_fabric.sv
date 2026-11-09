`timescale 1ns/1ps
module tb_fabric;
  reg clk=0; always #3.333 clk=~clk;
  reg rst_n=0;
  reg cpu_cmd_valid=0,cpu_cmd_read=1,cpu_rsp_ready=1;
  reg [31:0] cpu_cmd_addr=0,cpu_cmd_wdata=0;
  reg [3:0] cpu_cmd_wmask=4'hf;
  wire cpu_cmd_ready,cpu_rsp_valid,cpu_rsp_err;
  wire [31:0] cpu_rsp_rdata;
  reg dma_cmd_valid=0,dma_cmd_read=1,dma_rsp_ready=1;
  reg [31:0] dma_cmd_addr=0,dma_cmd_wdata=0;
  reg [3:0] dma_cmd_wmask=4'hf;
  wire dma_cmd_ready,dma_rsp_valid,dma_rsp_err;
  wire [31:0] dma_rsp_rdata;
  wire mem_cmd_valid,mem_cmd_ready,mem_cmd_read,mem_rsp_valid,mem_rsp_ready,mem_rsp_err;
  wire [31:0] mem_cmd_addr,mem_cmd_wdata,mem_rsp_rdata;
  wire [3:0] mem_cmd_wmask;
  xu_dma_shared_arb arb (.*);
  xu_shared_icb_sram #(.THROTTLE_RESET_PHASE(2)) shared (
    .clk(clk),.rst_n(rst_n),.cmd_valid(mem_cmd_valid),.cmd_ready(mem_cmd_ready),
    .cmd_addr(mem_cmd_addr),.cmd_read(mem_cmd_read),.cmd_wdata(mem_cmd_wdata),.cmd_wmask(mem_cmd_wmask),
    .rsp_valid(mem_rsp_valid),.rsp_ready(mem_rsp_ready),.rsp_err(mem_rsp_err),.rsp_rdata(mem_rsp_rdata));

  integer cycles=0;
  integer all_accept=0,all_retire=0,actual_outstanding=0,max_outstanding=0;
  integer start_cycle, finish_cycle, dma_count, dma_responses, cpu_count, cpu_responses;
  integer req_stalls, arbitration_stalls, response_stalls, downstream_stalls;
  integer accepted_cycle, last_dma_accept, min_interval,max_interval, interval_sum;
  integer latency_sum, max_latency;
  reg pending_owner,pending_read,pending_error;
  reg [31:0] pending_addr,pending_expected;
  reg cmd_held=0,rsp_held=0;
  reg [68:0] held_cmd;
  reg [32:0] held_rsp;
  reg measure=0;
  reg phase_stream=0, cpu_contention=0, random_backpressure=0;
  integer phase_kind=0,target_count=0;
  integer n,i;

  function [31:0] pattern(input [31:0] addr);
    pattern=(addr^32'hc15672d9)+(addr<<5);
  endfunction
  function [31:0] stream_addr(input integer kind,input integer idx);
    if (kind==0) stream_addr=idx<8192?32'ha0008000+idx*4:32'ha0018000+(idx-8192)*4;
    else stream_addr=(idx%5)==0?32'ha0000000+(idx/5)*4:32'ha0020000+(idx-idx/5-1)*4;
  endfunction
  function stream_read(input integer kind,input integer idx);
    stream_read=kind==0 || idx%5==0;
  endfunction
  function [31:0] stream_data(input integer idx);
    stream_data=32'hd4000000 ^ idx;
  endfunction
  function [31:0] expected_write(input integer output_idx);
    expected_write=stream_data((output_idx/4)*5+(output_idx%4)+1);
  endfunction

  // The monitor observes only accepted public-interface requests/responses.
  // It never reads or writes storage hierarchically.
  always @(posedge clk) begin
    cycles=cycles+1;
    if (!rst_n) begin
      actual_outstanding=0;cmd_held=0;rsp_held=0;
    end else begin
      if (cmd_held && (!mem_cmd_valid || {mem_cmd_read,mem_cmd_addr,mem_cmd_wdata,mem_cmd_wmask}!==held_cmd))
        $fatal(1,"command changed under backpressure");
      cmd_held=mem_cmd_valid && !mem_cmd_ready;
      held_cmd={mem_cmd_read,mem_cmd_addr,mem_cmd_wdata,mem_cmd_wmask};
      if (rsp_held && (!mem_rsp_valid || {mem_rsp_err,mem_rsp_rdata}!==held_rsp))
        $fatal(1,"response changed under backpressure");
      rsp_held=mem_rsp_valid && !mem_rsp_ready;
      held_rsp={mem_rsp_err,mem_rsp_rdata};
      if ((cpu_rsp_valid && dma_rsp_valid) || (cpu_cmd_valid &&cpu_cmd_ready && dma_cmd_valid &&dma_cmd_ready))
        $fatal(1,"dual routing");
      if (mem_rsp_valid && mem_rsp_ready) begin
        if (actual_outstanding!=1) $fatal(1,"unowned response");
        if (cpu_rsp_valid!==!pending_owner || dma_rsp_valid!==pending_owner) $fatal(1,"wrong response owner");
        if (mem_rsp_err!==pending_error) $fatal(1,"wrong error response");
        if (pending_read && !pending_error && mem_rsp_rdata!==pending_expected)
          $fatal(1,"read mismatch addr=%h expected=%h got=%h",pending_addr,pending_expected,mem_rsp_rdata);
        actual_outstanding=actual_outstanding-1;all_retire=all_retire+1;
        if (measure && pending_owner) begin
          dma_responses=dma_responses+1;
          latency_sum=latency_sum+cycles-accepted_cycle;
          if(cycles-accepted_cycle>max_latency)max_latency=cycles-accepted_cycle;
          finish_cycle=cycles;
        end
        if (measure && !pending_owner) cpu_responses=cpu_responses+1;
      end
      if (mem_cmd_valid && mem_cmd_ready) begin
        if (actual_outstanding!=0) $fatal(1,"more than one inflight");
        actual_outstanding=actual_outstanding+1;all_accept=all_accept+1;
        if(actual_outstanding>max_outstanding)max_outstanding=actual_outstanding;
        pending_owner=dma_cmd_valid && dma_cmd_ready;
        pending_read=mem_cmd_read;pending_addr=mem_cmd_addr;
        pending_error=mem_cmd_addr<32'ha0000000 || mem_cmd_addr>=32'ha0080000 || mem_cmd_addr[1:0]!=0;
        if(mem_cmd_addr>=32'ha0020000 &&mem_cmd_addr<32'ha0020000+25344*4)
          pending_expected=expected_write((mem_cmd_addr-32'ha0020000)/4);
        else pending_expected=pattern(mem_cmd_addr);
        if(measure &&pending_owner)begin
          if(dma_count==0) start_cycle=cycles;
          else begin
            if(cycles-last_dma_accept<min_interval)min_interval=cycles-last_dma_accept;
            if(cycles-last_dma_accept>max_interval)max_interval=cycles-last_dma_accept;
            interval_sum=interval_sum+cycles-last_dma_accept;
          end
          last_dma_accept=cycles; accepted_cycle=cycles; dma_count=dma_count+1;
        end
        if(measure &&!pending_owner)cpu_count=cpu_count+1;
      end
      if(measure)begin
        if(dma_cmd_valid &&!dma_cmd_ready)req_stalls=req_stalls+1;
        if(dma_cmd_valid &&cpu_cmd_valid &&mem_cmd_valid &&!arb.select_dma)arbitration_stalls=arbitration_stalls+1;
        if(mem_rsp_valid &&!mem_rsp_ready)response_stalls=response_stalls+1;
        if(mem_cmd_valid &&!mem_cmd_ready)downstream_stalls=downstream_stalls+1;
      end
    end
  end

  task cpu_xfer(input bit rd,input [31:0] addr,input [31:0] data,input [3:0] mask);
    begin
      @(negedge clk);cpu_cmd_valid=1;cpu_cmd_read=rd;cpu_cmd_addr=addr;cpu_cmd_wdata=data;cpu_cmd_wmask=mask;
      do @(posedge clk); while(!cpu_cmd_ready);
      @(negedge clk);cpu_cmd_valid=0;
      do @(posedge clk); while(!cpu_rsp_valid);
      @(negedge clk);
    end
  endtask
  task dma_xfer(input bit rd,input [31:0] addr,input [31:0] data);
    begin
      @(negedge clk);dma_cmd_valid=1;dma_cmd_read=rd;dma_cmd_addr=addr;dma_cmd_wdata=data;
      do @(posedge clk); while(!dma_cmd_ready);
      @(negedge clk);dma_cmd_valid=0;
      do @(posedge clk); while(!dma_rsp_valid);
      @(negedge clk);
    end
  endtask
  task run_stream(input integer kind,input integer words,input bit contention,input bit stalls);
    begin
      measure=0;
      dma_count=0;dma_responses=0;cpu_count=0;cpu_responses=0;
      req_stalls=0;arbitration_stalls=0;response_stalls=0;downstream_stalls=0;
      interval_sum=0;latency_sum=0;max_latency=0;min_interval=1000000;max_interval=0;
      @(negedge clk); measure=1; phase_stream=1; phase_kind=kind; target_count=words;
      cpu_contention=contention;random_backpressure=stalls;
      dma_cmd_valid=1;dma_cmd_addr=stream_addr(kind,0);dma_cmd_read=stream_read(kind,0);dma_cmd_wdata=stream_data(0);
      while(dma_responses<words)begin
        @(negedge clk);
        dma_cmd_valid=dma_count<words;
        dma_cmd_addr=stream_addr(kind,dma_count);dma_cmd_read=stream_read(kind,dma_count);dma_cmd_wdata=stream_data(dma_count);
        cpu_cmd_valid=contention &&dma_count<words;
        cpu_cmd_addr=32'ha0070000+((cpu_count%128)*4);cpu_cmd_read=0;cpu_cmd_wdata=32'hcc000000+cpu_count;cpu_cmd_wmask=4'hf;
        dma_rsp_ready=!stalls ||cycles%13<8;
        cpu_rsp_ready=!stalls ||cycles%11<7;
      end
      dma_cmd_valid=0;cpu_cmd_valid=0;dma_rsp_ready=1;cpu_rsp_ready=1;
      while(actual_outstanding!=0)@(negedge clk);
      measure=0;phase_stream=0;
      $display("METRIC kind=%0d words=%0d contention=%0d backpressure=%0d cycles=%0d accepted=%0d retired=%0d cpu_accepted=%0d cpu_retired=%0d req_stalls=%0d arbitration_stalls=%0d endpoint_stalls=%0d response_stalls=%0d interval_min=%0d interval_max=%0d interval_sum=%0d latency_sum=%0d latency_max=%0d max_outstanding=%0d",kind,words,contention,stalls,finish_cycle-start_cycle+1,dma_count,dma_responses,cpu_count,cpu_responses,req_stalls,arbitration_stalls,downstream_stalls,response_stalls,min_interval,max_interval,interval_sum,latency_sum,max_latency,max_outstanding);
      @(negedge clk);
    end
  endtask

  initial begin
    repeat(5)@(negedge clk);rst_n=1;
    // Public CPU requests establish known nonzero backing SRAM contents.
    for(i=0;i<8192;i=i+1)cpu_xfer(0,32'ha0008000+i*4,pattern(32'ha0008000+i*4),4'hf);
    for(i=0;i<512;i=i+1)cpu_xfer(0,32'ha0018000+i*4,pattern(32'ha0018000+i*4),4'hf);
    for(i=0;i<6336;i=i+1)cpu_xfer(0,32'ha0000000+i*4,pattern(32'ha0000000+i*4),4'hf);
    run_stream(0,8704,0,0);
    run_stream(1,31680,0,0);
    // Confirm all Y storage values through the tested public memory interface.
    for(i=0;i<25344;i=i+1)cpu_xfer(1,32'ha0020000+i*4,0,4'hf);
    run_stream(0,8704,1,0);
    run_stream(1,31680,1,1);
    for(i=0;i<25344;i=i+1)cpu_xfer(1,32'ha0020000+i*4,0,4'hf);
    cpu_xfer(1,32'ha0080000,0,4'hf);dma_xfer(1,32'ha0000001,0);
    cpu_xfer(0,32'h90000000,0,4'hf);dma_xfer(0,32'ha0080000,0);
    // Reset with accepted response held, then ensure no response survives reset.
    @(negedge clk);dma_rsp_ready=0;dma_cmd_valid=1;dma_cmd_read=1;dma_cmd_addr=32'ha0000000;
    do @(posedge clk);while(!dma_cmd_ready);
    @(negedge clk);dma_cmd_valid=0;
    repeat(3)@(negedge clk);rst_n=0;
    repeat(3)@(negedge clk);
    if(cpu_rsp_valid||dma_rsp_valid)$fatal(1,"response visible during reset");
    rst_n=1;dma_rsp_ready=1;
    repeat(3)@(negedge clk);
    if(cpu_rsp_valid||dma_rsp_valid||actual_outstanding)$fatal(1,"stale response after reset");
    dma_xfer(1,32'ha0000000,0);cpu_xfer(1,32'ha0018000,0,4'hf);
    $display("FABRIC_PASS all_accept=%0d all_retire=%0d reset_cancelled=1 errors=4 physical_y_readbacks=50688",all_accept,all_retire);
    $finish;
  end
  initial begin #100000000; $fatal(1,"watchdog");end
endmodule
