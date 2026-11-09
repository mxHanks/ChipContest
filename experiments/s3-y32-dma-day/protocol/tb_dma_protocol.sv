`timescale 1ns/1ps
module tb_dma_protocol;
  reg clk=0;always #3.333 clk=~clk;
  reg rst_n=0;
  reg cfg_cmd_valid=0,cfg_cmd_read=0,cfg_rsp_ready=1;
  reg [31:0] cfg_cmd_addr=0,cfg_cmd_wdata=0;
  reg [3:0] cfg_cmd_wmask=4'hf;
  wire cfg_cmd_ready,cfg_rsp_valid,cfg_rsp_err;
  wire [31:0] cfg_rsp_rdata;
  wire dma_cmd_valid,dma_cmd_ready,dma_cmd_read,dma_rsp_valid,dma_rsp_ready,dma_rsp_err;
  wire [31:0] dma_cmd_addr,dma_cmd_wdata,dma_rsp_rdata;
  wire [3:0] dma_cmd_wmask;
  reg cpu_cmd_valid=0,cpu_cmd_read=0,cpu_rsp_ready=1;
  reg [31:0] cpu_cmd_addr=0,cpu_cmd_wdata=0;
  reg [3:0] cpu_cmd_wmask=4'hf;
  wire cpu_cmd_ready,cpu_rsp_valid,cpu_rsp_err;
  wire [31:0] cpu_rsp_rdata;
  wire mem_cmd_valid,mem_cmd_ready,mem_cmd_read,mem_rsp_valid,mem_rsp_ready,mem_rsp_err;
  wire [31:0] mem_cmd_addr,mem_cmd_wdata,mem_rsp_rdata;
  wire [3:0] mem_cmd_wmask;
  wire endpoint_cmd_ready,endpoint_rsp_valid,endpoint_rsp_ready,endpoint_rsp_err;
  wire [31:0] endpoint_rsp_rdata;
  integer cycles=0;
  reg throttle_stress=0,hold_response=0,force_command_hold=0;
  wire command_gate=!force_command_hold&&(!throttle_stress ||cycles%17<12);
  wire response_gate=!hold_response &&(!throttle_stress ||cycles%19<12);
  assign mem_cmd_ready=endpoint_cmd_ready&&command_gate;
  assign mem_rsp_valid=endpoint_rsp_valid&&response_gate;
  assign endpoint_rsp_ready=mem_rsp_ready&&response_gate;
  reg injected_error=0;
  assign mem_rsp_err=endpoint_rsp_err||injected_error;
  assign mem_rsp_rdata=endpoint_rsp_rdata;
  xu_matrix_dma dut (
    .clk(clk),.rst_n(rst_n),
    .cfg_cmd_valid(cfg_cmd_valid),.cfg_cmd_ready(cfg_cmd_ready),.cfg_cmd_addr(cfg_cmd_addr),
    .cfg_cmd_read(cfg_cmd_read),.cfg_cmd_wdata(cfg_cmd_wdata),.cfg_cmd_wmask(cfg_cmd_wmask),
    .cfg_rsp_valid(cfg_rsp_valid),.cfg_rsp_ready(cfg_rsp_ready),.cfg_rsp_err(cfg_rsp_err),.cfg_rsp_rdata(cfg_rsp_rdata),
    .mem_cmd_valid(dma_cmd_valid),.mem_cmd_ready(dma_cmd_ready),.mem_cmd_addr(dma_cmd_addr),
    .mem_cmd_read(dma_cmd_read),.mem_cmd_wdata(dma_cmd_wdata),.mem_cmd_wmask(dma_cmd_wmask),
    .mem_rsp_valid(dma_rsp_valid),.mem_rsp_ready(dma_rsp_ready),.mem_rsp_err(dma_rsp_err),.mem_rsp_rdata(dma_rsp_rdata));
  xu_dma_shared_arb arb (.*);
  xu_shared_icb_sram #(.THROTTLE_RESET_PHASE(2)) shared (
    .clk(clk),.rst_n(rst_n),.cmd_valid(mem_cmd_valid&&command_gate),.cmd_ready(endpoint_cmd_ready),
    .cmd_addr(mem_cmd_addr),.cmd_read(mem_cmd_read),.cmd_wdata(mem_cmd_wdata),.cmd_wmask(mem_cmd_wmask),
    .rsp_valid(endpoint_rsp_valid),.rsp_ready(endpoint_rsp_ready),.rsp_err(endpoint_rsp_err),.rsp_rdata(endpoint_rsp_rdata));

  reg [15:0] x[0:6335],w[0:16383];
  reg [39:0] bias[0:255];
  reg [31:0] golden[0:25343],packed_w[0:8191];
  reg [25343:0] seen_y;
  reg [15039:0] seen_source;
  string vectors,case_name;
  integer i, j, mode=2, timeout, run_number=0,checked=0;
  integer accepted=0,retired=0,outstanding=0,max_outstanding=0;
  integer dma_reads=0,dma_writes=0,dma_returns=0,pops=0,macs=0;
  integer source_first /* verilator public_flat_rw */ =-1;
  integer y_last /* verilator public_flat_rw */ =-1;
  integer done_at /* verilator public_flat_rw */ =-1;
  integer clear_at /* verilator public_flat_rw */ =-1;
  integer clear_start=-1;
  integer cpu_count=0,cfg_errors=0,faults=0;
  integer inject_kind=0,inject_index=0,inject_count=0;
  integer read_serial=0,write_serial=0;
  integer held_write_cycles=0,held_write_error_responses=0;
  reg current_offer_held=0,accepted_offer_held=0;
  reg run_monitor=0,contention=0;
  reg pending_dma=0,pending_y=0;
  reg [31:0] pending_addr;
  reg dma_hold=0,mem_hold=0,rsp_hold=0,cfg_hold=0;
  reg [68:0] dma_saved,mem_saved,cfg_saved;
  reg [32:0] rsp_saved;
  integer index;
  reg previous_done=0,previous_clear=0;
  reg [31:0] got;

  always @(posedge clk) begin
    cycles=cycles+1;
    if(!rst_n)begin
      outstanding=0;dma_hold=0;mem_hold=0;rsp_hold=0;cfg_hold=0;
      previous_done=0;previous_clear=0;injected_error<=0;
    end else begin
      if(dut.locked&&dut.pending)$fatal(1,"one-inflight invariant: locked cannot own previous request");
      if(dma_cmd_valid&&!dma_cmd_ready)begin
        current_offer_held=1;
        if(!dma_cmd_read)held_write_cycles=held_write_cycles+1;
      end
      if(dma_rsp_valid&&dma_rsp_ready&&dma_rsp_err&&dma_cmd_valid)
        $fatal(1,"new command offered while first error retires");
      if(dma_hold&&(!dma_cmd_valid||dma_saved!=={dma_cmd_read,dma_cmd_addr,dma_cmd_wdata,dma_cmd_wmask}))
        $fatal(1,"DMA command unstable under backpressure");
      dma_hold=dma_cmd_valid&&!dma_cmd_ready;dma_saved={dma_cmd_read,dma_cmd_addr,dma_cmd_wdata,dma_cmd_wmask};
      if(mem_hold&&(!mem_cmd_valid||mem_saved!=={mem_cmd_read,mem_cmd_addr,mem_cmd_wdata,mem_cmd_wmask}))
        $fatal(1,"arbiter command unstable under backpressure");
      mem_hold=mem_cmd_valid&&!mem_cmd_ready;mem_saved={mem_cmd_read,mem_cmd_addr,mem_cmd_wdata,mem_cmd_wmask};
      if(rsp_hold&&(!mem_rsp_valid||rsp_saved!=={mem_rsp_err,mem_rsp_rdata}))
        $fatal(1,"shared response unstable under backpressure");
      rsp_hold=mem_rsp_valid&&!mem_rsp_ready;rsp_saved={mem_rsp_err,mem_rsp_rdata};
      if(cfg_hold&&(!cfg_rsp_valid||cfg_saved!=={36'b0,cfg_rsp_err,cfg_rsp_rdata}))
        $fatal(1,"cfg response unstable under backpressure");
      cfg_hold=cfg_rsp_valid&&!cfg_rsp_ready;cfg_saved={36'b0,cfg_rsp_err,cfg_rsp_rdata};
      if(mem_rsp_valid&&mem_rsp_ready)begin
        if(outstanding!=1)$fatal(1,"unowned endpoint response");
        if(pending_dma)begin
          dma_returns=dma_returns+1;
          if(run_monitor&&pending_y)y_last=cycles;
          if(injected_error)begin faults=faults+1;if(pending_y&&accepted_offer_held)held_write_error_responses=held_write_error_responses+1;end
        end
        outstanding=outstanding-1;retired=retired+1;
      end
      if(mem_cmd_valid&&mem_cmd_ready)begin
        if(outstanding!=0)$fatal(1,"more than one endpoint request");
        outstanding=outstanding+1;accepted=accepted+1;if(outstanding>max_outstanding)max_outstanding=outstanding;
        pending_dma=dma_cmd_valid&&dma_cmd_ready;
        pending_y=pending_dma&&!mem_cmd_read;pending_addr=mem_cmd_addr;
        injected_error<=0;
        if(pending_dma)begin
          accepted_offer_held=current_offer_held;current_offer_held=0;
          if(mem_cmd_read)begin
            if(inject_kind==1&&read_serial==inject_index)begin injected_error<=1;inject_count=inject_count+1;end
            read_serial=read_serial+1;
          end else begin
            if(inject_kind==2&&write_serial==inject_index)begin injected_error<=1;inject_count=inject_count+1;end
            write_serial=write_serial+1;
          end
        end
      end
      if(cpu_cmd_valid&&cpu_cmd_ready)cpu_count=cpu_count+1;
      if(run_monitor)begin
        if(dut.core_pop)pops=pops+1;
        if(dut.core_mac_step)macs=macs+1;
        if(dma_cmd_valid&&dma_cmd_ready)begin
          if(dma_cmd_wmask!==4'hf)$fatal(1,"DMA mask");
          if(dma_cmd_read)begin
            if(source_first<0)source_first=cycles;
            if(dma_cmd_addr>=32'ha0008000&&dma_cmd_addr<32'ha0010000)index=(dma_cmd_addr-32'ha0008000)/4;
            else if(dma_cmd_addr>=32'ha0018000&&dma_cmd_addr<32'ha0018800)index=8192+(dma_cmd_addr-32'ha0018000)/4;
            else if(dma_cmd_addr>=32'ha0000000&&dma_cmd_addr<32'ha0006300)index=8704+(dma_cmd_addr-32'ha0000000)/4;
            else $fatal(1,"DMA source out of descriptor %h",dma_cmd_addr);
            if(seen_source[index])$fatal(1,"duplicate source %h",dma_cmd_addr);
            seen_source[index]=1;dma_reads=dma_reads+1;
          end else begin
            if(dma_cmd_addr<32'ha0020000||dma_cmd_addr>=32'ha0038c00||dma_cmd_addr[1:0]!=0)$fatal(1,"Y range %h",dma_cmd_addr);
            index=(dma_cmd_addr-32'ha0020000)/4;
            if(index>=25344||seen_y[index])$fatal(1,"duplicate or bad Y %0d",index);
            if(dma_cmd_wdata!==golden[index])$fatal(1,"Y mismatch index=%0d row=%0d col=%0d expected=%h got=%h cycle=%0d",index,index/256,index%256,golden[index],dma_cmd_wdata,cycles);
            seen_y[index]=1;dma_writes=dma_writes+1;
          end
        end
        if(dut.done&&!previous_done)begin
          if((outstanding!=0&&pending_dma)||dut.pending||dut.locked||dut.core_out_valid||dut.core_active||dma_cmd_valid)
            $fatal(1,"early completion or stale ownership");
          done_at=cycles;
        end
      end
      if(dut.clear_done&&!previous_clear)clear_at=cycles;
      previous_done=dut.done;previous_clear=dut.clear_done;
    end
  end

  // Saturated CPU public-master writes contend with the actual DMA arbiter.
  // This driver never addresses input, output, or accelerator internal storage.
  always @(negedge clk)if(contention)begin
    cpu_cmd_valid=1;cpu_cmd_addr=32'ha0070000+(cpu_count%128)*4;
    cpu_cmd_read=0;cpu_cmd_wdata=32'hcc000000+cpu_count;cpu_cmd_wmask=4'hf;
  end
  task cpu_xfer(input bit rd,input [31:0] addr,input [31:0] data,input [31:0] expected);
    begin
      @(negedge clk);cpu_cmd_valid=1;cpu_cmd_addr=addr;cpu_cmd_read=rd;cpu_cmd_wdata=data;
      do @(posedge clk);while(!cpu_cmd_ready);
      @(negedge clk);cpu_cmd_valid=0;
      do @(posedge clk);while(!cpu_rsp_valid);
      if(cpu_rsp_err)$fatal(1,"CPU storage error %h",addr);
      if(rd&&cpu_rsp_rdata!==expected)$fatal(1,"public storage readback %h expected=%h got=%h",addr,expected,cpu_rsp_rdata);
      @(negedge clk);
    end
  endtask
  task cfg(input bit rd,input [31:0] off,input [31:0] data,input bit err);
    begin
      @(negedge clk);cfg_cmd_valid=1;cfg_cmd_addr=32'h10042300+off;cfg_cmd_read=rd;cfg_cmd_wdata=data;
      do @(posedge clk);while(!cfg_cmd_ready);
      @(negedge clk);cfg_cmd_valid=0;
      do @(posedge clk);while(!cfg_rsp_valid);
      if(cfg_rsp_err!==err)$fatal(1,"cfg error off=%h rd=%0d expected=%0d got=%0d",off,rd,err,cfg_rsp_err);
      got=cfg_rsp_rdata;if(err)cfg_errors=cfg_errors+1;
      @(negedge clk);
    end
  endtask
  task physical_clear;
    begin
      clear_start=cycles;clear_at=-1;cfg(0,4,1,0);
      timeout=0;
      while(!dut.clear_done)begin @(negedge clk);timeout=timeout+1;if(timeout>4000)$fatal(1,"clear timeout");end
      if(dut.clear_write_count!=16640)$fatal(1,"W+X clear counter expected16640 got%0d",dut.clear_write_count);
      if(physical_w!=16384||physical_b!=768||physical_x!=256)$fatal(1,"physical clear pin counts W=%0d B=%0d X=%0d",physical_w,physical_b,physical_x);
      $display("DMA_CLEAR_PASS W=%0d BIAS=%0d X=%0d total=17408 elapsed=%0d counter_wx=%0d",physical_w,physical_b,physical_x,dut.clear_cycles,dut.clear_write_count);
      cfg(1,8,0,0);if(got!==8)$fatal(1,"clear status %h",got);
    end
  endtask
  task begin_run(input bit dual_mode);
    begin
      seen_y=0;seen_source=0;dma_reads=0;dma_writes=0;dma_returns=0;pops=0;macs=0;
      source_first=-1;y_last=-1;done_at=-1;read_serial=0;write_serial=0;run_monitor=1;run_number=run_number+1;
      cfg(0,4,dual_mode?32'h102:2,0);
    end
  endtask
  task await_idle(input bit expected_error);
    begin
      timeout=0;
      while(dut.busy)begin @(negedge clk);timeout=timeout+1;if(timeout>1000000)$fatal(1,"task timeout state=%0d reads=%0d writes=%0d",dut.state,dma_reads,dma_writes);end
      repeat(4)@(negedge clk);
      cfg(1,8,0,0);
      if(expected_error)begin
        if(got!==4||dut.done||outstanding!=0||dma_cmd_valid||dut.pending||dut.locked)$fatal(1,"abort drain/status %h",got);
        if(inject_count!=1)$fatal(1,"error injection not observed once");
        $display("DMA_ABORT_PASS kind=%0d at=%0d reads=%0d writes=%0d returns=%0d faults=%0d",inject_kind,inject_index,dma_reads,dma_writes,dma_returns,faults);
      end else begin
        if(got!==2||!dut.done||dma_reads!=15040||dma_writes!=25344||dma_returns!=40384||pops!=3168||macs!=(mode==2?102400:202752)||!(&seen_y)||!(&seen_source)||done_at<=y_last)
          $fatal(1,"success coverage status=%h reads=%0d writes=%0d returns=%0d pops=%0d macs=%0d done=%0d lastY=%0d",got,dma_reads,dma_writes,dma_returns,pops,macs,done_at,y_last);
        checked=checked+25344;
        $display("DMA_NUMERIC_PASS run=%0d mode=%0d outputs=25344 payload=%0d clear=%0d sum=%0d wb=%0d compute=%0d reads=%0d writes=%0d pops=%0d macs=%0d first_source_to_lastY=%0d",run_number,mode,dut.cycle_count,dut.clear_cycles,dut.cycle_count+dut.clear_cycles,dut.wb_cycles,dut.run_cycles,dma_reads,dma_writes,pops,macs,y_last-source_first+1);
      end
      run_monitor=0;
    end
  endtask

  `include "dma_physical_connections.svh"
  initial begin
    if(!$value$plusargs("vectors=%s",vectors))$fatal(1,"vectors required");
    if(!$value$plusargs("case=%s",case_name))case_name="numeric";
    if(!$value$plusargs("mode=%d",mode))mode=2;
    $readmemh({vectors,"/x.mem"},x);$readmemh({vectors,"/w.mem"},w);
    $readmemh({vectors,"/w_packed16.mem"},packed_w);$readmemh({vectors,"/bias.mem"},bias);$readmemh({vectors,"/y32.mem"},golden);
    repeat(5)@(negedge clk);rst_n=1;
    // Source and poison output memory are established only by public requests.
    for(i=0;i<6336;i=i+1)cpu_xfer(0,32'ha0000000+i*4,{16'b0,x[i]},0);
    for(i=0;i<8192;i=i+1)begin
      if(packed_w[i]!=={w[i*2+1],w[i*2]})$fatal(1,"packed weight identity");
      cpu_xfer(0,32'ha0008000+i*4,packed_w[i],0);
    end
    for(i=0;i<256;i=i+1)begin
      cpu_xfer(0,32'ha0018000+i*8,bias[i][31:0],0);
      cpu_xfer(0,32'ha0018004+i*8,{{24{bias[i][39]}},bias[i][39:32]},0);
    end
    for(i=0;i<25344;i=i+1)cpu_xfer(0,32'ha0020000+i*4,32'hdeadbeef,0);
    cfg_rsp_ready=0;cfg(1,0,0,0);if(got!==32'h444d4131)$fatal(1,"DMA id");
    repeat(8)@(negedge clk);cfg_rsp_ready=1;repeat(2)@(negedge clk);
    cfg(0,4,mode==2?32'h102:2,1); // start before physical clear
    cfg(1,1,0,1);cfg(1,32'h7c,0,1);cfg(0,0,0,1);
    cfg_cmd_wmask=1;cfg(0,32'h10,32'ha0000000,1);cfg_cmd_wmask=4'hf;
    physical_clear();
    if(case_name=="reset_clear")begin
      cfg(0,4,1,0);repeat(100)@(negedge clk);
      if(dut.clear_done||!dut.busy||!dut.core_clearing)$fatal(1,"clear interruption stage");
      rst_n=0;repeat(4)@(negedge clk);rst_n=1;repeat(5)@(negedge clk);
      cfg(1,8,0,0);if(got!==0)$fatal(1,"interrupted clear reported done");
      $display("DMA_RESET_PASS stage=clear clear_done=0");physical_clear();
    end
    if(case_name=="descriptor")begin
      cfg(0,32'h10,32'ha0000001,0);cfg(0,4,32'h102,1);
      cfg(0,32'h10,32'ha0000000,0);cfg(0,32'h1c,32'ha0000000,0);cfg(0,4,32'h102,1);
      cfg(0,32'h1c,32'ha0070000,0);cfg(0,4,32'h102,1);
      cfg(0,32'h1c,32'ha0020000,0);
    end
    if(case_name=="stress")begin throttle_stress=1;contention=1;end
    if(case_name=="readerror")begin inject_kind=1;inject_index=0;end
    if(case_name=="writeerror0")begin inject_kind=2;inject_index=0;end
    if(case_name=="writeerror_mid")begin inject_kind=2;inject_index=12672;end
    if(case_name=="writeerror_last")begin inject_kind=2;inject_index=25343;end
    if($value$plusargs("inject_index=%d",inject_index))begin end
    hold_response=1;begin_run(mode==2);
    cfg(0,32'h10,32'ha0040000,1);cfg(0,4,1,1);cfg(0,4,mode==2?32'h102:2,1);
    cfg(1,32'h10,0,0);if(got!==32'ha0000000)$fatal(1,"busy descriptor mutated");
    if(case_name=="reset"||case_name=="reset_bias"||case_name=="reset_x"||case_name=="reset_y0"||case_name=="reset_y_mid")begin
      if(case_name=="reset_bias")begin
        hold_response=0;while(dut.state!=8)@(negedge clk);
      end else if(case_name=="reset_x")begin
        hold_response=0;while(read_serial<8705)@(negedge clk);hold_response=1;
        if(!dut.pending||dut.pending_kind!=3)$fatal(1,"X reset requires live prefetch");
      end else if(case_name=="reset_y0"||case_name=="reset_y_mid")begin
        hold_response=0;
        while(write_serial<(case_name=="reset_y0"?1:12673))@(negedge clk);
        hold_response=1;if(!dut.pending||dut.pending_kind!=4)$fatal(1,"Y reset requires live write response");
      end else begin
        hold_response=1;while(!endpoint_rsp_valid)@(negedge clk);repeat(5)@(negedge clk);
        if(!dut.pending||outstanding!=1)$fatal(1,"W reset requires live request");
      end
      run_monitor=0;rst_n=0;repeat(4)@(negedge clk);hold_response=0;rst_n=1;
      repeat(5)@(negedge clk);
      if(dma_rsp_valid||dut.done||outstanding!=0||dma_cmd_valid)$fatal(1,"stale reset response");
      cfg(1,8,0,0);if(got!==0)$fatal(1,"reset status %h",got);
      $display("DMA_RESET_PASS stage=%s stale_responses=0",case_name);
      physical_clear();begin_run(mode==2);await_idle(0);
    end else if(inject_kind!=0)begin
      hold_response=0;
      if(inject_kind==2)fork
        begin
          wait(dma_cmd_valid&&!dma_cmd_read&&write_serial==inject_index);
          force_command_hold=1;repeat(5)@(negedge clk);force_command_hold=0;
        end
      join_none
      await_idle(1);
      if(inject_kind==2&&held_write_error_responses!=1)$fatal(1,"write fault did not drain a previously held command");
      cfg(1,32'h0c,0,0);if(got!==1)$fatal(1,"first error code");
      inject_kind=0;inject_count=0;physical_clear();begin_run(mode==2);await_idle(0);
    end else begin hold_response=0;await_idle(0);end
    @(negedge clk);contention=0;cpu_cmd_valid=0;throttle_stress=0;
    while(outstanding!=0)@(negedge clk);
    for(i=0;i<25344;i=i+1)cpu_xfer(1,32'ha0020000+i*4,0,golden[i]);
    $display("DMA_PROTOCOL_PASS case=%s mode=%0d exact_outputs=%0d physical_y_readback=25344 cfg_rejections=%0d faults=%0d max_outstanding=%0d held_write_cycles=%0d held_write_error_responses=%0d",case_name,mode,checked,cfg_errors,faults,max_outstanding,held_write_cycles,held_write_error_responses);
    $finish;
  end
  initial begin #200000000; $fatal(1,"watchdog");end
endmodule
