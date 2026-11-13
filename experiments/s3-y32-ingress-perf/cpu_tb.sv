`timescale 1ns/1fs
`include "e203_defines.v"
`ifndef C32_THROTTLE
`define C32_THROTTLE 7
`endif
module tb_sysbus32_soc;
  `define MAIN dut.u_e203_subsys_top.u_e203_subsys_main
  `define CPU `MAIN.u_e203_cpu_top
  `define EXU `CPU.u_e203_cpu.u_e203_core.u_e203_exu
  `define ITCM `CPU.u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram
  `define DMA `MAIN.u_e203_subsys_perips.u_xu_matrix_dma
  `define CORE `DMA.u_core
  `define NICE `CPU.u_e203_cpu.u_e203_nice_core

  reg clk=0,lfclk=0,rst_n=0,startup_complete=0;
  always #3.333333333 clk=~clk;
  always #15258.7890625 lfclk=~lfclk;
  wire shared_mem_clk,shared_mem_rst_n;
  wire cmd_valid,cmd_ready,cmd_read,rsp_valid,rsp_ready,rsp_err;
  wire [31:0] cmd_addr; wire [31:0] cmd_wdata,rsp_rdata;wire[3:0]cmd_wmask;
  reg host_valid=0,host_read=0;reg[31:0]host_addr=0,host_wdata=0;
  wire host_ready,host_rsp_valid,host_rsp_err;wire[31:0]host_rdata;
  wire endpoint_ready;
  localparam BASE=32'ha0000000,YOFF=32'h20000,HOST=32'h7f000;
  reg[15:0]x[0:6335],w[0:16383];reg[39:0]bias[0:255];
  reg[31:0]golden[0:25343],packed_w[0:8191];reg[7:0]program_bytes[0:65535];
  reg y_seen[0:25343],x_seen[0:6335],w_seen[0:8191],b_seen[0:511];
  string testcase,vectors;integer tasks,rows,warmup=1,warmup_active=0;
  integer layer=0,completed=0,call_index=0,host_ack=0,clear_ack=0,firmware_pass=0;
  integer cycles=0,max_cycles=20000000,first_source_stall=0,first_load_stall=0,load_pipeline=1;
  integer first_request=-1,first_accept=-1,last_y_response=-1,first_offer=-1,first_endpoint_source_accept=-1;
  integer clear_request=-1,clear_finish=-1,start_request=-1,done_cycle=-1;
  integer reads=0,wreads=0,breads=0,xreads=0,writes=0,yresponses=0;
  integer dma_requests=0,dma_responses=0,dma_stalls=0,source_stall=0,write_stall=0;
  integer mmio_reads=0,mmio_writes=0,pops=0,macs=0,firmware_cycles=0;
  integer fixture_source_writes=0,fixture_poison_writes=0,fixture_readbacks=0;
  integer fixture_x_writes=0,fixture_w_writes=0,fixture_b_writes=0;
  integer load_begin=-1,load_finish=-1,load_retired=0,load_endpoint_offer=-1,load_endpoint_accept=-1;
  integer host_kind[0:3],host_address[0:3];
  integer host_head=0,host_tail=0,host_outstanding=0,host_max_outstanding=0;
  integer source_requests=0,source_responses=0,host_source_stalls=0;
  reg host_hold=0;reg[64:0]host_saved;
  integer endpoint_requests=0,endpoint_responses=0;
  integer endpoint_source_reads=0,endpoint_source_writes=0,endpoint_y_writes=0,endpoint_y_responses=0,endpoint_pending=0,endpoint_y_pending=0;
  integer cpu_pending_kind=0;reg[31:0]cpu_pending_data=0;
  reg endpoint_hold=0;reg[68:0]endpoint_saved;
  reg[2:0] dma_kind[0:3];reg[13:0]dma_index[0:3];
  integer dma_head=0,dma_tail=0,outstanding=0,max_outstanding=0,last_wb_response=-1,first_xy=-1;
  reg clear_seen=0,start_seen=0,done_seen=0,previous_done=0,previous_clear_done=0;
  reg[3:0]descriptor_writes=0;reg dma_hold=0,cfg_hold=0;
  reg[68:0]dma_saved;reg[68:0]cfg_saved;
  longint unsigned hf_prev=0,lf_prev=0,hf_period=0,lf_period=0;
  integer hf_edges=0,lf_edges=0;
  always @(posedge clk)begin
    if(hf_edges>0)hf_period=longint'($realtime/1fs)-hf_prev;
    hf_prev=longint'($realtime/1fs);hf_edges=hf_edges+1;
    cycles<=startup_complete?cycles+1:0;
    if(startup_complete&&cycles>max_cycles)$fatal(1,"SoC timeout layer=%0d state=%0d reads=%0d writes=%0d",layer,`DMA.state,reads,writes);
  end
  always @(posedge lfclk)begin
    if(lf_edges>0)lf_period=longint'($realtime/1fs)-lf_prev;
    lf_prev=longint'($realtime/1fs);lf_edges=lf_edges+1;
  end
  // Only test stimulus is inserted before the original mem_fab, never at SRAM.
  wire source_addr=cmd_addr>=BASE && cmd_addr<BASE+32'h18800;
  wire dma_initial_block=cmd_valid&&cmd_read&&source_addr&&start_seen&&first_endpoint_source_accept<0&&
       (first_offer<0?first_source_stall>0:cycles-first_offer<first_source_stall);
  wire load_initial_block=cmd_valid&&!cmd_read&&source_addr&&load_endpoint_accept<0&&
       (load_endpoint_offer<0?first_load_stall>0:cycles-load_endpoint_offer<first_load_stall);
  wire initial_block=dma_initial_block||load_initial_block;
  assign cmd_ready=endpoint_ready&&!initial_block;
  xu_shared_icb_sram endpoint(
    .clk(shared_mem_clk),.rst_n(shared_mem_rst_n),.cmd_valid(cmd_valid&&!initial_block),.cmd_ready(endpoint_ready),
    .cmd_addr(cmd_addr),.cmd_read(cmd_read),.cmd_wdata(cmd_wdata),.cmd_wmask(cmd_wmask),
    .rsp_valid(rsp_valid),.rsp_ready(rsp_ready),.rsp_err(rsp_err),.rsp_rdata(rsp_rdata));
  e203_soc_top #(.EXTERNAL_SYSMEM(1)) dut(
    .shared_mem_clk(shared_mem_clk),.shared_mem_rst_n(shared_mem_rst_n),
    .hfextclk(clk),.lfextclk(lfclk),.io_pads_aon_erst_n_i_ival(rst_n),
    .io_pads_jtag_TCK_i_ival(1'b0),.io_pads_jtag_TMS_i_ival(1'b0),.io_pads_jtag_TDI_i_ival(1'b0),
    .io_pads_gpioA_i_ival(32'b0),.io_pads_gpioB_i_ival(32'b0),
    .io_pads_qspi0_dq_0_i_ival(1'b0),.io_pads_qspi0_dq_1_i_ival(1'b0),
    .io_pads_qspi0_dq_2_i_ival(1'b0),.io_pads_qspi0_dq_3_i_ival(1'b0),
    .io_pads_bootrom_n_i_ival(1'b0),.io_pads_dbgmode0_n_i_ival(1'b1),.io_pads_dbgmode1_n_i_ival(1'b1),
    .io_pads_dbgmode2_n_i_ival(1'b1),.io_pads_aon_pmu_dwakeup_n_i_ival(1'b1),
    .sysbus_load_cmd_valid(host_valid),.sysbus_load_cmd_ready(host_ready),
    .sysbus_load_cmd_addr(host_addr),.sysbus_load_cmd_read(host_read),
    .sysbus_load_cmd_wdata(host_wdata),.sysbus_load_cmd_wmask(4'hf),
    .sysbus_load_rsp_valid(host_rsp_valid),.sysbus_load_rsp_ready(1'b1),
    .sysbus_load_rsp_err(host_rsp_err),.sysbus_load_rsp_rdata(host_rdata),
    .ext_sysmem_cmd_valid(cmd_valid),.ext_sysmem_cmd_ready(cmd_ready),.ext_sysmem_cmd_addr(cmd_addr),
    .ext_sysmem_cmd_read(cmd_read),.ext_sysmem_cmd_wdata(cmd_wdata),.ext_sysmem_cmd_wmask(cmd_wmask),
    .ext_sysmem_rsp_valid(rsp_valid),.ext_sysmem_rsp_ready(rsp_ready),.ext_sysmem_rsp_err(rsp_err),.ext_sysmem_rsp_rdata(rsp_rdata));
  task automatic host_access(input bit rd,input[31:0]addr,input[31:0]data,output[31:0]value);
    begin
      @(negedge shared_mem_clk);host_valid=1;host_read=rd;host_addr=addr;host_wdata=data;
      do @(posedge shared_mem_clk);while(!host_ready);
      @(negedge shared_mem_clk);host_valid=0;
      do @(posedge shared_mem_clk);while(!host_rsp_valid);
      if(host_rsp_err)$fatal(1,"SystemBus loader error %h",addr);
      value=host_rdata;
      @(negedge shared_mem_clk);
    end
  endtask
  task automatic put(input[31:0]addr,input[31:0]data);
    reg[31:0]unused;begin host_access(0,addr,data,unused);end
  endtask
  task automatic prepare_layer(input integer index);
    string directory;integer i;
    begin
      fixture_source_writes=0;fixture_poison_writes=0;fixture_readbacks=0;
      fixture_x_writes=0;fixture_w_writes=0;fixture_b_writes=0;
      directory=$sformatf("%s/layer_%02d/",vectors,index);
      $readmemh({directory,"x.mem"},x);$readmemh({directory,"w.mem"},w);
      $readmemh({directory,"bias.mem"},bias);
      for(i=0;i<8192;i++)packed_w[i]={w[2*i+1],w[2*i]};
      $readmemh({directory,"y32.mem"},golden);
      first_request=-1;first_accept=-1;last_y_response=-1;first_offer=-1;first_endpoint_source_accept=-1;
      clear_request=-1;clear_finish=-1;start_request=-1;done_cycle=-1;
      reads=0;wreads=0;breads=0;xreads=0;writes=0;yresponses=0;dma_requests=0;dma_responses=0;
      dma_stalls=0;source_stall=0;write_stall=0;mmio_reads=0;mmio_writes=0;pops=0;macs=0;
      dma_head=0;dma_tail=0;outstanding=0;max_outstanding=0;last_wb_response=-1;first_xy=-1;
      for(i=0;i<4;i++)begin dma_kind[i]=0;dma_index[i]=0;end
      clear_seen=0;start_seen=0;done_seen=0;descriptor_writes=0;
      load_begin=-1;load_finish=-1;load_retired=0;load_endpoint_offer=-1;load_endpoint_accept=-1;
      if(host_outstanding!=0)$fatal(1,"loader carried owner into next task");
      host_max_outstanding=0;source_requests=0;source_responses=0;host_source_stalls=0;
      // Global endpoint owners survive task-local counter rollover: CPU may
      // legally have a mailbox poll in flight between tasks.
      endpoint_source_reads=0;endpoint_source_writes=0;endpoint_y_writes=0;endpoint_y_responses=0;
      for(i=0;i<25344;i++)begin put(BASE+YOFF+4*i,32'hdeadbeef);y_seen[i]=0;end
      for(i=0;i<6336;i++)x_seen[i]=0;
      for(i=0;i<8192;i++)w_seen[i]=0;
      for(i=0;i<512;i++)b_seen[i]=0;
    end
  endtask
  // Source sequence is exactly the original 6,336 X + 8,192 W + 512 BIAS
  // writes. Pipeline mode changes only submission spacing at the same ingress.
  task automatic source_word(input integer word_index,output reg[31:0]addr,output reg[31:0]data);
    integer i;
    begin
      if(word_index<6336)begin addr=BASE+4*word_index;data={16'b0,x[word_index]};end
      else if(word_index<14528)begin
        i=word_index-6336;addr=BASE+'h8000+4*i;data=packed_w[i];
        if(data!=={w[2*i+1],w[2*i]})$fatal(1,"packed W identity");
      end else begin
        i=(word_index-14528)/2;addr=BASE+'h18000+4*(word_index-14528);
        data=word_index[0]?{{24{bias[i][39]}},bias[i][39:32]}:bias[i][31:0];
      end
    end
  endtask
  task automatic load_layer;
    integer i,sent;reg[31:0]addr,data;
    begin
      if(load_pipeline==0)begin
        // Differential reference preserves every host_access scheduling wait.
        for(i=0;i<15040;i++)begin source_word(i,addr,data);put(addr,data);end
      end else begin
        sent=0;
        @(negedge shared_mem_clk);
        source_word(sent,addr,data);host_valid=1;host_read=0;host_addr=addr;host_wdata=data;
        while(sent<15040)begin
          @(posedge shared_mem_clk);
          if(host_valid&&host_ready)sent=sent+1;
          @(negedge shared_mem_clk);
          // Keep a stalled request unchanged; advance only after acceptance.
          // Responses retire independently in the monitor below.
          if(sent<15040)begin
            if(host_outstanding<4)begin
              source_word(sent,addr,data);host_valid=1;host_addr=addr;host_wdata=data;
            end else host_valid=0;
          end else host_valid=0;
        end
        wait(source_responses==15040);
        @(negedge shared_mem_clk);
      end
      if(source_requests!=15040||source_responses!=15040||host_outstanding!=0)
        $fatal(1,"source owner not fully retired req=%0d rsp=%0d pending=%0d",source_requests,source_responses,host_outstanding);
    end
  endtask
  task automatic report_layer;
    integer i;string p;
    begin
      p=warmup_active?"C32_WARMUP":"C32";
      if(!clear_seen||!start_seen||!done_seen||outstanding!=0||dma_requests!=dma_responses||
        reads!=15040||wreads!=8192||breads!=512||xreads!=6336||writes!=25344||yresponses!=25344||pops!=3168||
        macs!=((99+rows-1)/rows)*32*64)$fatal(1,"task incomplete rd=%0d wr=%0d rsp=%0d pop=%0d mac=%0d",reads,writes,yresponses,pops,macs);
      for(i=0;i<25344;i++)if(!y_seen[i])$fatal(1,"Y coverage %0d",i);
      for(i=0;i<6336;i++)if(!x_seen[i])$fatal(1,"X coverage %0d",i);
      for(i=0;i<8192;i++)if(!w_seen[i])$fatal(1,"W coverage %0d",i);
      for(i=0;i<512;i++)if(!b_seen[i])$fatal(1,"BIAS coverage %0d",i);
      if(`DMA.read_count!==15040||`DMA.write_count!==25344||`DMA.pop_count!==3168||`DMA.mac_count!==macs)
        $fatal(1,"independent counters disagree");
      if(load_begin<0||load_finish<load_begin||load_retired!=15040||clear_finish>=load_begin)
        $fatal(1,"source load not fully counted/retired");
      $display("%s_TASK_PASS layer=%0d rows=%0d outputs=25344 total=%0d load_to_y=%0d loading=%0d clear=%0d dma_payload=%0d firmware_cycles=%0d start_to_done=%0d",p,layer,rows,last_y_response-clear_request+1,last_y_response-load_begin+1,load_finish-load_begin+1,clear_finish-clear_request+1,last_y_response-first_request+1,firmware_cycles,done_cycle-start_request+1);
      $display("%s_WINDOW layer=%0d load_begin=%0d load_finish=%0d first_request=%0d first_accept=%0d last_y_response=%0d clear_request=%0d clear_done=%0d start=%0d done=%0d",p,layer,load_begin,load_finish,first_request,first_accept,last_y_response,clear_request,clear_finish,start_request,done_cycle);
      $display("%s_COUNTS layer=%0d reads=%0d w_reads=%0d bias_reads=%0d x_reads=%0d writes=%0d write_responses=%0d requests=%0d responses=%0d pops=%0d macs=%0d mmio_reads=%0d mmio_writes=%0d",p,layer,reads,wreads,breads,xreads,writes,yresponses,dma_requests,dma_responses,pops,macs,mmio_reads,mmio_writes);
      if(first_endpoint_source_accept-first_offer<first_source_stall)$fatal(1,"forced source stall omitted");
      if(load_endpoint_accept-load_endpoint_offer<first_load_stall)$fatal(1,"forced load stall omitted");
      $display("%s_CHANNEL layer=%0d wb_cycles=%0d xy_window=%0d dma_stall=%0d source_stall=%0d write_stall=%0d max_outstanding=%0d endpoint_first_offer=%0d endpoint_first_accept=%0d forced_wait=%0d load_endpoint_offer=%0d load_endpoint_accept=%0d forced_load_wait=%0d",p,layer,last_wb_response-first_request+1,last_y_response-first_xy+1,dma_stalls,source_stall,write_stall,max_outstanding,first_offer,first_endpoint_source_accept,first_source_stall,load_endpoint_offer,load_endpoint_accept,first_load_stall);
      if(endpoint_source_reads!=15040||endpoint_source_writes!=15040||endpoint_y_writes!=50688||endpoint_y_responses!=50688)
        $fatal(1,"endpoint transaction retirement/coverage req=%0d rsp=%0d src=%0d yw=%0d yr=%0d",endpoint_requests,endpoint_responses,endpoint_source_writes,endpoint_y_writes,endpoint_y_responses);
      $display("%s_ENDPOINT layer=%0d requests=%0d responses=%0d outstanding=%0d source_reads=%0d source_writes=%0d y_writes=%0d y_write_responses=%0d",p,layer,endpoint_requests,endpoint_responses,endpoint_pending,endpoint_source_reads,endpoint_source_writes,endpoint_y_writes,endpoint_y_responses);
      $display("%s_LOADER_PIPELINE layer=%0d mode=%0d requests=%0d responses=%0d outstanding=%0d max_outstanding=%0d source_stall=%0d",p,layer,load_pipeline,source_requests,source_responses,host_outstanding,host_max_outstanding,host_source_stalls);
      $fflush();
    end
  endtask
  initial begin : stimulus
    integer i,callno;reg[31:0]value;
    if(!$value$plusargs("TESTCASE=%s",testcase)||!$value$plusargs("VECTORS=%s",vectors)||!$value$plusargs("TASKS=%d",tasks)||!$value$plusargs("ROWS=%d",rows))$fatal(1,"missing plusargs");
    if(!$value$plusargs("WARMUP=%d",warmup))warmup=1;
    if(!$value$plusargs("MAX_CYCLES=%d",max_cycles))max_cycles=20000000;
    if(!$value$plusargs("FIRST_SOURCE_STALL=%d",first_source_stall))first_source_stall=0;
    if(!$value$plusargs("FIRST_LOAD_STALL=%d",first_load_stall))first_load_stall=0;
    if(!$value$plusargs("LOAD_PIPELINE=%d",load_pipeline))load_pipeline=1;
    if(load_pipeline<0||load_pipeline>1)$fatal(1,"invalid loader mode");
    for(i=0;i<4;i++)begin host_kind[i]=0;host_address[i]=0;dma_kind[i]=0;dma_index[i]=0;end
    if(tasks<1||tasks>12||(rows!=1&&rows!=8)||warmup<0||warmup>1)$fatal(1,"invalid test scope");
    for(i=0;i<65536;i++)program_bytes[i]=0;
    $readmemh({testcase,".verilog"},program_bytes);
    for(i=0;i<8192;i++)`ITCM.mem_r[i]={program_bytes[8*i+7],program_bytes[8*i+6],program_bytes[8*i+5],program_bytes[8*i+4],program_bytes[8*i+3],program_bytes[8*i+2],program_bytes[8*i+1],program_bytes[8*i]};
    #120 rst_n=1;
    wait(`CPU.u_e203_cpu.rst_core===1'b1);@(negedge clk);rst_n=0;#120ns;
    if(`CPU.u_e203_cpu.rst_core!==1'b0)$fatal(1,"external reset did not reach CPU");
    startup_complete=1;rst_n=1;
    wait(shared_mem_rst_n===1'b1);
    $display("C32_CLOCK measured_hf_period_fs=%0d measured_lf_period_fs=%0d hf_edges=%0d lf_edges=%0d",hf_period,lf_period,hf_edges,lf_edges);$fflush();
    put(BASE+HOST,tasks);put(BASE+HOST+4,0);put(BASE+HOST+12,rows);put(BASE+HOST+16,warmup);put(BASE+HOST+20,0);put(BASE+HOST+24,0);put(BASE+HOST+28,0);put(BASE+HOST+32,0);
    for(callno=1;callno<=tasks+warmup;callno++)begin
      call_index=callno;warmup_active=(warmup&&callno==1);layer=callno-1-warmup;if(layer<0)layer=0;
      prepare_layer(layer);put(BASE+HOST+32,callno);
      wait(clear_ack==callno);
      load_layer();put(BASE+HOST+24,callno);
      wait(host_ack==callno);
      @(negedge shared_mem_clk);
      for(i=0;i<25344;i++)begin host_access(1,BASE+YOFF+4*i,0,value);if(value!==golden[i])$fatal(1,"public readback mismatch layer=%0d word=%0d got=%h expected=%h",layer,i,value,golden[i]);end
      if(fixture_source_writes!=15040||fixture_poison_writes!=25344||fixture_readbacks!=25344||fixture_x_writes!=6336||fixture_w_writes!=8192||fixture_b_writes!=512)$fatal(1,"public fixture transfer counts");
      report_layer();
      $display("C32_SYSTEMBUS_LOAD_PASS call=%0d layer=%0d source_writes=%0d poison_writes=%0d readbacks=%0d ready_sequence=%0d",callno,layer,fixture_source_writes,fixture_poison_writes,fixture_readbacks,callno);$fflush();
      if(warmup_active)$display("C32_WARMUP_DONE tasks=1 outputs=25344 excluded_principal=1");else completed=completed+1;
    end
    wait(firmware_pass);$display("C32_SOC_PASS tasks=%0d rows=%0d outputs=%0d writes=%0d",completed,rows,completed*25344,completed*25344);$finish;
  end
  always @(posedge shared_mem_clk)begin : observe
    integer offset,index,new_kind,new_index;reg[8:0]cfg_offset;
    if(startup_complete&&shared_mem_rst_n)begin
      if(host_hold&&(!host_valid||{host_addr,host_read,host_wdata}!==host_saved))
        $fatal(1,"SystemBus loader changed while stalled");
      host_hold=host_valid&&!host_ready;host_saved={host_addr,host_read,host_wdata};
      if(host_valid&&!host_ready&&!host_read&&host_addr>=BASE&&host_addr<BASE+32'h18800)
        host_source_stalls=host_source_stalls+1;
      if(host_rsp_valid)begin
        if(host_outstanding<1||host_rsp_err)$fatal(1,"orphan/error loader response");
        if(host_kind[host_head]==1)begin
          load_retired=load_retired+1;source_responses=source_responses+1;load_finish=cycles;
        end
        host_kind[host_head]=0;host_address[host_head]=0;
        host_head=(host_head+1)%4;host_outstanding=host_outstanding-1;
      end
      if(host_valid&&!host_read&&host_addr>=BASE&&host_addr<BASE+32'h18800&&load_begin<0)
        load_begin=cycles;
      if(host_valid&&host_ready)begin
        offset=host_addr-BASE;
        if(host_outstanding>=4)$fatal(1,"loader owner FIFO overflow");
        host_kind[host_tail]=(!host_read&&offset<32'h18800)?1:2;
        host_address[host_tail]=host_addr;
        if(host_kind[host_tail]==1)begin
          source_requests=source_requests+1;
          if(source_requests-source_responses>host_max_outstanding)
            host_max_outstanding=source_requests-source_responses;
        end
        host_tail=(host_tail+1)%4;host_outstanding=host_outstanding+1;
        if(host_read)begin
          if(offset<YOFF||offset>=YOFF+25344*4)$fatal(1,"unexpected public fixture read");
          fixture_readbacks=fixture_readbacks+1;
        end else if(offset<6336*4)begin
          if(host_wdata!=={16'b0,x[offset/4]})$fatal(1,"public X identity");
          fixture_x_writes=fixture_x_writes+1;fixture_source_writes=fixture_source_writes+1;
        end else if(offset>='h8000&&offset<'h10000)begin
          if(host_wdata!==packed_w[(offset-'h8000)/4])$fatal(1,"public W identity");
          fixture_w_writes=fixture_w_writes+1;fixture_source_writes=fixture_source_writes+1;
        end else if(offset>='h18000&&offset<'h18800)begin
          index=(offset-'h18000)/8;
          if(offset[2])begin if(host_wdata!=={{24{bias[index][39]}},bias[index][39:32]})$fatal(1,"public high BIAS identity");end
          else if(host_wdata!==bias[index][31:0])$fatal(1,"public low BIAS identity");
          fixture_b_writes=fixture_b_writes+1;fixture_source_writes=fixture_source_writes+1;
        end else if(offset>=YOFF&&offset<YOFF+25344*4)begin
          if(host_wdata!==32'hdeadbeef)$fatal(1,"public poison identity");
          fixture_poison_writes=fixture_poison_writes+1;
        end else if(offset<HOST||offset>HOST+32)$fatal(1,"unexpected public fixture write");
      end
      if(`DMA.pending_count!==3'(outstanding)||`DMA.pending!==(outstanding!=0))
        $fatal(1,"DMA owner count differs rtl=%0d independent=%0d",`DMA.pending_count,outstanding);
      if(outstanding>0&&(`DMA.pending_kind!==dma_kind[dma_head]||`DMA.pending_index!==dma_index[dma_head]))
        $fatal(1,"DMA owner head differs kind=%0d/%0d index=%0d/%0d",`DMA.pending_kind,dma_kind[dma_head],`DMA.pending_index,dma_index[dma_head]);
      if(source_requests-source_responses<0||source_requests-source_responses>4||host_outstanding<0||host_outstanding>4)
        $fatal(1,"loader request/response accounting");
      if(`NICE.nice_req_valid)$fatal(1,"unexpected NICE traffic");
      if(host_valid&&start_seen&&last_y_response<0)$fatal(1,"loader overlaps DMA task");
      if(dma_hold&&(!`DMA.mem_cmd_valid||{`DMA.mem_cmd_addr,`DMA.mem_cmd_read,`DMA.mem_cmd_wdata,`DMA.mem_cmd_wmask}!==dma_saved))$fatal(1,"DMA changed while stalled");
      dma_hold=`DMA.mem_cmd_valid&&!`DMA.mem_cmd_ready;dma_saved={`DMA.mem_cmd_addr,`DMA.mem_cmd_read,`DMA.mem_cmd_wdata,`DMA.mem_cmd_wmask};
      if(cfg_hold&&(!`DMA.cfg_cmd_valid||{`DMA.cfg_cmd_addr,`DMA.cfg_cmd_read,`DMA.cfg_cmd_wdata,`DMA.cfg_cmd_wmask}!==cfg_saved))$fatal(1,"MMIO changed while stalled");
      cfg_hold=`DMA.cfg_cmd_valid&&!`DMA.cfg_cmd_ready;cfg_saved={`DMA.cfg_cmd_addr,`DMA.cfg_cmd_read,`DMA.cfg_cmd_wdata,`DMA.cfg_cmd_wmask};
      if(`DMA.cfg_cmd_valid&&`DMA.cfg_cmd_ready)begin
        cfg_offset=`DMA.cfg_cmd_addr[8:0];
        if(`DMA.cfg_cmd_read)mmio_reads=mmio_reads+1;
        else begin
          mmio_writes=mmio_writes+1;
          if(`DMA.cfg_cmd_wmask!==4'hf)$fatal(1,"partial MMIO");
          case(cfg_offset)
            9'h104:if(`DMA.cfg_cmd_wdata===1)begin
              if(clear_seen||start_seen||outstanding!=0)$fatal(1,"unsafe clear");clear_seen=1;clear_request=cycles;
            end else if(`DMA.cfg_cmd_wdata===(rows==8?32'h802:32'h2))begin
              if(!clear_seen||clear_finish<0||start_seen||descriptor_writes!==4'hf)$fatal(1,"unsafe start");start_seen=1;start_request=cycles;
            end else $fatal(1,"unexpected CTRL %h",`DMA.cfg_cmd_wdata);
            9'h110:begin if(`DMA.cfg_cmd_wdata!==BASE)$fatal(1,"X identity");descriptor_writes[0]=1;end
            9'h114:begin if(`DMA.cfg_cmd_wdata!==BASE+'h8000)$fatal(1,"W identity");descriptor_writes[1]=1;end
            9'h118:begin if(`DMA.cfg_cmd_wdata!==BASE+'h18000)$fatal(1,"BIAS identity");descriptor_writes[2]=1;end
            9'h11c:begin if(`DMA.cfg_cmd_wdata!==BASE+YOFF)$fatal(1,"Y identity");descriptor_writes[3]=1;end
            default:$fatal(1,"unexpected MMIO offset %h",cfg_offset);
          endcase
        end
      end
      if(`DMA.clear_done&&!previous_clear_done)begin if(!clear_seen||start_seen)$fatal(1,"orphan clear_done");clear_finish=cycles;end
      previous_clear_done=`DMA.clear_done;
      if(`DMA.done&&!previous_done)begin
        if(!start_seen||outstanding||writes!=25344||yresponses!=25344||`DMA.mem_cmd_valid||dma_requests!=dma_responses)$fatal(1,"premature completion");done_seen=1;done_cycle=cycles;
      end
      previous_done=`DMA.done;
      if(`DMA.error)$fatal(1,"hardware error %h",`DMA.error_code);
      if(`CORE.io_outValid&&`CORE.io_outPop)pops=pops+1;
      if(`CORE.io_macStep)macs=macs+1;
      if(`DMA.mem_cmd_valid&&`DMA.mem_cmd_read&&first_request<0)first_request=cycles;
      if(cmd_valid&&!cmd_read&&source_addr&&load_endpoint_offer<0)load_endpoint_offer=cycles;
      if(cmd_valid&&cmd_read&&source_addr&&start_seen&&first_offer<0)first_offer=cycles;
      if(`DMA.mem_cmd_valid&&!`DMA.mem_cmd_ready)begin dma_stalls=dma_stalls+1;if(`DMA.mem_cmd_read)source_stall=source_stall+1;else write_stall=write_stall+1;end
      if(`DMA.mem_rsp_valid&&`DMA.mem_rsp_ready)begin
        if(outstanding<1||outstanding>4||`DMA.mem_rsp_err)$fatal(1,"orphan/error DMA response");
        dma_responses=dma_responses+1;outstanding=outstanding-1;
        if(dma_kind[dma_head]==0||dma_kind[dma_head]==1)last_wb_response=cycles;
        if(dma_kind[dma_head]==4)begin yresponses=yresponses+1;if(yresponses==25344)last_y_response=cycles;end
        dma_kind[dma_head]=0;dma_index[dma_head]=0;dma_head=(dma_head+1)%4;
      end
      if(`DMA.mem_cmd_valid&&`DMA.mem_cmd_ready)begin
        // DMA acceptance is upstream of the original fabric queues; it need
        // not coincide with the endpoint acceptance cycle.
        if(`DMA.mem_cmd_addr[1:0]!=0||`DMA.mem_cmd_wmask!==4'hf)$fatal(1,"DMA width/alignment");
        outstanding=outstanding+1;if(outstanding>4)$fatal(1,"DMA occupancy");if(outstanding>max_outstanding)max_outstanding=outstanding;dma_requests=dma_requests+1;
        offset=`DMA.mem_cmd_addr-BASE;
        if(`DMA.mem_cmd_read)begin
          if(!start_seen||clear_finish<0)$fatal(1,"source before start");if(first_accept<0)first_accept=cycles;
          reads=reads+1;
          if(offset<6336*4)begin index=offset/4;if(x_seen[index])$fatal(1,"duplicate X");x_seen[index]=1;xreads=xreads+1;new_kind=3;new_index=index%(rows*64);if(first_xy<0)first_xy=cycles;end
          else if(offset>='h8000&&offset<'h10000)begin index=(offset-'h8000)/4;if(w_seen[index])$fatal(1,"duplicate W");w_seen[index]=1;wreads=wreads+1;new_kind=0;new_index=index;end
          else if(offset>='h18000&&offset<'h18800)begin index=(offset-'h18000)/4;if(b_seen[index])$fatal(1,"duplicate BIAS");b_seen[index]=1;breads=breads+1;new_kind=1;new_index=index;end
          else $fatal(1,"invalid source address %h",`DMA.mem_cmd_addr);
        end else begin
          if(offset<YOFF||offset>=YOFF+25344*4)$fatal(1,"invalid Y address");index=(offset-YOFF)/4;
          if(y_seen[index]||`DMA.mem_cmd_wdata!==golden[index])$fatal(1,"Y mismatch layer=%0d index=%0d got=%h exp=%h",layer,index,`DMA.mem_cmd_wdata,golden[index]);
          y_seen[index]=1;writes=writes+1;new_kind=4;new_index=index%8;
        end
        dma_kind[dma_tail]=3'(new_kind);dma_index[dma_tail]=14'(new_index);dma_tail=(dma_tail+1)%4;
      end
      if(dma_requests-dma_responses!=outstanding||outstanding<0||outstanding>4)
        $fatal(1,"DMA request/response conservation");
      // Endpoint checks independently show all traffic used the original
      // SystemBus output. CPU mailbox and loader accesses share this port.
      if(endpoint_hold&&(!cmd_valid||{cmd_addr,cmd_read,cmd_wdata,cmd_wmask}!==endpoint_saved))$fatal(1,"SystemBus endpoint changed while stalled");
      endpoint_hold=cmd_valid&&!cmd_ready;endpoint_saved={cmd_addr,cmd_read,cmd_wdata,cmd_wmask};
      if(rsp_valid&&rsp_ready)begin
        if(endpoint_pending!=1)$fatal(1,"orphan endpoint response");
        endpoint_responses=endpoint_responses+1;endpoint_pending=0;
        if(endpoint_y_pending)endpoint_y_responses=endpoint_y_responses+1;
        endpoint_y_pending=0;if(rsp_err)$fatal(1,"endpoint error");
      end
      if(cmd_valid&&cmd_ready)begin
        if(!cmd_read&&source_addr&&load_endpoint_accept<0)load_endpoint_accept=cycles;
        if(cmd_read&&source_addr&&start_seen&&first_endpoint_source_accept<0)first_endpoint_source_accept=cycles;
        endpoint_requests=endpoint_requests+1;endpoint_pending=endpoint_pending+1;
        if(endpoint_pending!=1)$fatal(1,"endpoint more than one in flight");
        if(cmd_read&&cmd_addr>=BASE&&cmd_addr<BASE+'h18800)endpoint_source_reads=endpoint_source_reads+1;
        if(!cmd_read&&cmd_addr>=BASE&&cmd_addr<BASE+'h18800)endpoint_source_writes=endpoint_source_writes+1;
        if(!cmd_read&&cmd_addr>=BASE+YOFF&&cmd_addr<BASE+YOFF+25344*4)begin endpoint_y_writes=endpoint_y_writes+1;endpoint_y_pending=1;end
        if(cmd_addr[1:0]||cmd_wmask!==4'hf)$fatal(1,"endpoint width/alignment");
      end
      // CPU mailbox events become visible only after the original bus
      // response retires; accepting an upstream request is not completion.
      if(`MAIN.mem_icb_rsp_valid&&`MAIN.mem_icb_rsp_ready)begin
        if(cpu_pending_kind==0||`MAIN.mem_icb_rsp_err)$fatal(1,"orphan/error CPU SystemBus response");
        case(cpu_pending_kind)
          1:firmware_cycles=cpu_pending_data;
          2:host_ack=cpu_pending_data;
          3:begin if(clear_finish<0||start_seen)$fatal(1,"clear ACK before physical clear");clear_ack=cpu_pending_data;end
          default:begin end
        endcase
        cpu_pending_kind=0;
      end
      if(`MAIN.mem_icb_cmd_valid&&`MAIN.mem_icb_cmd_ready)begin
        if(cpu_pending_kind!=0)$fatal(1,"CPU more than one owner");
        cpu_pending_kind=4;cpu_pending_data=`MAIN.mem_icb_cmd_wdata;
        if(!`MAIN.mem_icb_cmd_read)begin
          offset=`MAIN.mem_icb_cmd_addr-BASE;
          if(offset==HOST+8)cpu_pending_kind=1;
          else if(offset==HOST+4)cpu_pending_kind=2;
          else if(offset==HOST+28)cpu_pending_kind=3;
          else if(offset==HOST+20)$fatal(1,"firmware error code %h",`MAIN.mem_icb_cmd_wdata);
          else $fatal(1,"unexpected CPU shared write %h",`MAIN.mem_icb_cmd_addr);
        end
      end
      if(endpoint_requests-endpoint_responses!=endpoint_pending||endpoint_pending<0||endpoint_pending>1)$fatal(1,"global endpoint accounting");
      if(`EXU.u_e203_exu_commit.alu_cmt_i_valid&&`EXU.u_e203_exu_commit.alu_cmt_i_ready&&`EXU.u_e203_exu_commit.alu_cmt_i_pc==32'h80000086)begin
        if(`EXU.u_e203_exu_regfile.rf_r[3]!=1)$fatal(1,"firmware return %0d",`EXU.u_e203_exu_regfile.rf_r[3]);firmware_pass=1;
      end
    end
  end
  `include "sysbus32_physical_observer.svh"
  initial begin #10ms;if(!startup_complete)$fatal(1,"CPU startup timeout");end
endmodule
