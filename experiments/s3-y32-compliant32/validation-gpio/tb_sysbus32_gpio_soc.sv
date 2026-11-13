`timescale 1ns/1fs
`include "e203_defines.v"
`include "gpio_profile.svh"
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
  reg[31:0] gpioA_input=0,gpioB_input=0;
  wire[31:0]gpioA_output,gpioA_oe,gpioB_output,gpioB_oe;
  reg gpio_req=0; integer gpio_words=0,gpio_acks=0,gpio_first_data=-1;
  longint unsigned gpio_first_data_fs=0;
  integer cpu_pending_index=0,clear_ack_retired_cycle=-1;
  wire endpoint_ready;
  localparam BASE=32'ha0000000,YOFF=32'h20000,HOST=32'h7f000;
  reg[15:0]x[0:6335],w[0:16383];reg[39:0]bias[0:255];
  reg[31:0]golden[0:25343],packed_w[0:8191];reg[7:0]program_bytes[0:65535];
  reg y_seen[0:25343],x_seen[0:6335],w_seen[0:8191],b_seen[0:511];
  string testcase,vectors;integer tasks,rows,warmup=1,warmup_active=0;
  integer layer=0,completed=0,call_index=0,host_ack=0,clear_ack=0,firmware_pass=0;
  integer cycles=0,max_cycles=20000000,first_source_stall=0,first_load_stall=0;
  integer first_request=-1,first_accept=-1,last_y_response=-1,first_offer=-1,first_endpoint_source_accept=-1;
  integer clear_request=-1,clear_finish=-1,start_request=-1,done_cycle=-1;
  integer reads=0,wreads=0,breads=0,xreads=0,writes=0,yresponses=0;
  integer dma_requests=0,dma_responses=0,dma_stalls=0,source_stall=0,write_stall=0;
  integer mmio_reads=0,mmio_writes=0,pops=0,macs=0,firmware_cycles=0;
  integer fixture_source_writes=0,fixture_poison_writes=0,fixture_readbacks=0;
  integer fixture_x_writes=0,fixture_w_writes=0,fixture_b_writes=0;
  integer load_begin=-1,load_finish=-1,load_retired=0,load_endpoint_offer=-1,load_endpoint_accept=-1;
  integer host_pending_kind=0,endpoint_requests=0,endpoint_responses=0;
  integer endpoint_source_reads=0,endpoint_source_writes=0,endpoint_y_writes=0,endpoint_y_responses=0,endpoint_pending=0,endpoint_y_pending=0;
  integer cpu_pending_kind=0;reg[31:0]cpu_pending_data=0;
  reg endpoint_hold=0;reg[68:0]endpoint_saved;
  integer pending_kind=0,outstanding=0,max_outstanding=0,last_wb_response=-1,first_xy=-1;
  reg clear_seen=0,start_seen=0,done_seen=0,previous_done=0,previous_clear_done=0;
  reg[3:0]descriptor_writes=0;reg dma_hold=0,cfg_hold=0;
  reg[68:0]dma_saved;reg[68:0]cfg_saved;
  longint unsigned hf_prev=0,lf_prev=0,hf_period=0,lf_period=0;
  integer hf_edges=0,lf_edges=0;
  integer last_public_progress_cycle=0;
  reg[31:0] previous_gpio_output=0;
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
  // Production N2 SystemBus. Endpoint backpressure is a test condition; all
  // input/parameter data enter existing GPIO pads and are stored by the CPU.
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
    .io_pads_gpioA_i_ival(gpioA_input),.io_pads_gpioB_i_ival(gpioB_input),
    .io_pads_gpioA_o_oval(gpioA_output),.io_pads_gpioA_o_oe(gpioA_oe),
    .io_pads_gpioB_o_oval(gpioB_output),.io_pads_gpioB_o_oe(gpioB_oe),
    .io_pads_qspi0_dq_0_i_ival(1'b0),.io_pads_qspi0_dq_1_i_ival(1'b0),
    .io_pads_qspi0_dq_2_i_ival(1'b0),.io_pads_qspi0_dq_3_i_ival(1'b0),
    .io_pads_bootrom_n_i_ival(1'b0),.io_pads_dbgmode0_n_i_ival(1'b1),.io_pads_dbgmode1_n_i_ival(1'b1),
    .io_pads_dbgmode2_n_i_ival(1'b1),.io_pads_aon_pmu_dwakeup_n_i_ival(1'b1),
    .ext_sysmem_cmd_valid(cmd_valid),.ext_sysmem_cmd_ready(cmd_ready),.ext_sysmem_cmd_addr(cmd_addr),
    .ext_sysmem_cmd_read(cmd_read),.ext_sysmem_cmd_wdata(cmd_wdata),.ext_sysmem_cmd_wmask(cmd_wmask),
    .ext_sysmem_rsp_valid(rsp_valid),.ext_sysmem_rsp_ready(rsp_ready),.ext_sysmem_rsp_err(rsp_err),.ext_sysmem_rsp_rdata(rsp_rdata));
  task automatic gpio_send(input[31:0]data,input bit source_word);
    integer previous_retired;
    begin
      wait(gpioA_output[22] && gpioA_oe[22]);
      if(gpioA_output[23])$fatal(1,"GPIO firmware error");
      @(negedge clk);gpioB_input=data;
      if(source_word)begin
        if(clear_ack_retired_cycle<0||clear_ack_retired_cycle<=clear_finish)$fatal(1,"GPIO data before clear ACK retirement");
        if(load_begin<0)begin load_begin=cycles;gpio_first_data=cycles;gpio_first_data_fs=longint'($realtime/1fs);end
        gpio_words=gpio_words+1;
      end
      previous_retired=load_retired;
      repeat(3)@(posedge clk);
      @(negedge clk);gpio_req=~gpio_req;gpioA_input[20]=gpio_req;
      wait(gpioA_output[21]===gpio_req && gpioA_oe[21]);
      if(source_word)begin
        if(load_retired!=previous_retired+1)$fatal(1,"GPIO ACK before exact shared write response retirement");
        gpio_acks=gpio_acks+1;
      end
      @(negedge clk);
    end
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
      pending_kind=0;outstanding=0;max_outstanding=0;last_wb_response=-1;first_xy=-1;
      clear_seen=0;start_seen=0;done_seen=0;descriptor_writes=0;
      load_begin=-1;load_finish=-1;load_retired=0;load_endpoint_offer=-1;load_endpoint_accept=-1;host_pending_kind=0;
      // Global endpoint owners survive task-local counter rollover: CPU may
      // legally have a mailbox poll in flight between tasks.
      endpoint_source_reads=0;endpoint_source_writes=0;endpoint_y_writes=0;endpoint_y_responses=0;
      for(i=0;i<25344;i++)y_seen[i]=0;
      gpio_words=0;gpio_acks=0;gpio_first_data=-1;gpio_first_data_fs=0;clear_ack_retired_cycle=-1;
      for(i=0;i<6336;i++)x_seen[i]=0;
      for(i=0;i<8192;i++)w_seen[i]=0;
      for(i=0;i<512;i++)b_seen[i]=0;
    end
  endtask
  task automatic load_layer;
    integer i;
    begin
      for(i=0;i<6336;i++)gpio_send({16'b0,x[i]},1);
      for(i=0;i<8192;i++)begin
        if(packed_w[i]!=={w[2*i+1],w[2*i]})$fatal(1,"packed W identity");
        gpio_send(packed_w[i],1);
      end
      for(i=0;i<256;i++)begin
        gpio_send(bias[i][31:0],1);
        gpio_send({{24{bias[i][39]}},bias[i][39:32]},1);
      end
    end
  endtask
  task automatic report_layer;
    integer i;string p;
    begin
      p=warmup_active?"C32_WARMUP":"C32";
      if(!clear_seen||!start_seen||!done_seen||outstanding!=0||pending_kind!=0||dma_requests!=dma_responses||
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
      $fflush();
    end
  endtask
  initial begin : stimulus
    integer i,callno;reg[31:0]value;
    if(!$value$plusargs("TESTCASE=%s",testcase)||!$value$plusargs("VECTORS=%s",vectors)||!$value$plusargs("TASKS=%d",tasks)||!$value$plusargs("ROWS=%d",rows))$fatal(1,"missing plusargs");
    if(!$value$plusargs("WARMUP=%d",warmup))warmup=1;
    if(!$value$plusargs("MAX_CYCLES=%d",max_cycles))max_cycles=100000000;
    if(!$value$plusargs("FIRST_SOURCE_STALL=%d",first_source_stall))first_source_stall=0;
    if(!$value$plusargs("FIRST_LOAD_STALL=%d",first_load_stall))first_load_stall=0;
    if(tasks<1||tasks>12||(rows!=1&&rows!=8)||warmup<0||warmup>1)$fatal(1,"invalid test scope");
    for(i=0;i<65536;i++)program_bytes[i]=0;
    $readmemh({testcase,".verilog"},program_bytes);
    activity_firmware_loaded=1;wait(&activity_boot_macro_done);
    #120 rst_n=1;
    wait(`CPU.u_e203_cpu.rst_core===1'b1);@(negedge clk);rst_n=0;#120ns;
    if(`CPU.u_e203_cpu.rst_core!==1'b0)$fatal(1,"external reset did not reach CPU");
    startup_complete=1;rst_n=1;
    wait(shared_mem_rst_n===1'b1);
    $display("C32_CLOCK measured_hf_period_fs=%0d measured_lf_period_fs=%0d hf_edges=%0d lf_edges=%0d",hf_period,lf_period,hf_edges,lf_edges);$fflush();
    if(`MAIN.u_xu_systembus_ingress.N!=2||`MAIN.u_xu_systembus_ingress.PW!=1)$fatal(1,"production ingress is not N2/PW1");
    $display("G32_PRODUCTION_TOPOLOGY ingress_sources=2 pointer_bits=1 cpu_macros=64 shared_macros=256 internal_macros=%0d total_macros=%0d",`G32_INTERNAL_MACROS,`G32_TOTAL_MACROS);
    gpio_send(tasks,0);gpio_send(rows,0);gpio_send(warmup,0);
    for(callno=1;callno<=tasks+warmup;callno++)begin
      call_index=callno;warmup_active=(warmup&&callno==1);layer=callno-1-warmup;if(layer<0)layer=0;
      prepare_layer(layer);gpio_send(callno,0);
      wait(clear_ack==callno);
      load_layer();
      wait(host_ack==callno);
      @(negedge shared_mem_clk);
      if(fixture_source_writes!=15040||fixture_poison_writes!=25344||fixture_readbacks!=25344||fixture_x_writes!=6336||fixture_w_writes!=8192||fixture_b_writes!=512)$fatal(1,"public fixture transfer counts");
      report_layer();
      if(gpio_words!=15040||gpio_acks!=15040||gpio_first_data!=load_begin)$fatal(1,"GPIO input/ACK count");
      $display("G32_GPIO_LOAD_PASS call=%0d layer=%0d words=%0d acks=%0d first_data=%0d first_data_fs=%0d clear_ack_retired=%0d setup_hf_edges=3",callno,layer,gpio_words,gpio_acks,gpio_first_data,gpio_first_data_fs,clear_ack_retired_cycle);
      $display("C32_SYSTEMBUS_LOAD_PASS call=%0d layer=%0d source_writes=%0d poison_writes=%0d readbacks=%0d ready_sequence=%0d",callno,layer,fixture_source_writes,fixture_poison_writes,fixture_readbacks,callno);$fflush();
      if(warmup_active)$display("C32_WARMUP_DONE tasks=1 outputs=25344 excluded_principal=1");else completed=completed+1;
    end
    wait(firmware_pass);$display("C32_SOC_PASS tasks=%0d rows=%0d outputs=%0d writes=%0d",completed,rows,completed*25344,completed*25344);$finish;
  end
  always @(posedge shared_mem_clk)begin : observe
    integer offset,index;reg[8:0]cfg_offset;
    if(startup_complete&&shared_mem_rst_n)begin
      if(gpioA_oe[23]&&gpioA_output[23])$fatal(1,"GPIO firmware ERROR output");
      if(gpioA_output!==previous_gpio_output||(cmd_valid&&cmd_ready)||(rsp_valid&&rsp_ready)||
         (`DMA.cfg_cmd_valid&&`DMA.cfg_cmd_ready)||(`DMA.mem_rsp_valid&&`DMA.mem_rsp_ready))
        last_public_progress_cycle=cycles;
      previous_gpio_output=gpioA_output;
      if(cycles%250000==0)begin
        $display("G32_PROGRESS cycle=%0d call=%0d gpio_words=%0d gpio_acks=%0d gpio_out=%h pc=%h clear=%0d start=%0d dma_reads=%0d dma_writes=%0d cpu_load_rsp=%0d cpu_y_reads=%0d",cycles,call_index,gpio_words,gpio_acks,gpioA_output,`EXU.u_e203_exu_commit.alu_cmt_i_pc,clear_seen,start_seen,reads,writes,load_retired,fixture_readbacks);
        $fflush();
      end
      if(cycles-last_public_progress_cycle>2000000)$fatal(1,"GPIO/CPU/SystemBus made no public protocol progress for 2000000 cycles");
`ifdef XU_MATRIX_STORAGE_SRAM
      if(`CORE.io_clearDone)begin
        if(`CORE.biasLow!==0||`CORE.hostData!==0||`CORE.hostAddr!==0||`CORE.hostState!==0||
           `DMA.w_low!==0||`DMA.bias_low!==0||`DMA.bias_data!==0||`DMA.bias_addr!==0||`DMA.lock_data!==0)
          $fatal(1,"storage transaction/operand assembly not physically zero after clear");
        if(`CORE.state!==0||`CORE.active!==0||`CORE.runSet!==0||`CORE.validRows!==0||
           `CORE.produced!==0||`CORE.k!==0||`CORE.storeIndex!==0||`CORE.biasLane!==0||
           `CORE.head!==0||`CORE.tail!==0||`CORE.count!==0||`CORE.tag0!==0||`CORE.tag1!==0||
           `CORE.outRow!==0||`CORE.outColumn!==0||`CORE.readHeld!==0||
           `DMA.lock_addr!==0||`DMA.lock_kind!==0||`DMA.lock_index!==0||`DMA.lock_read!==0||
           `DMA.pending_kind!==0||`DMA.pending_index!==0||`DMA.run_row!==0||`DMA.run_set!==0||
           `DMA.x_row!==0||`DMA.x_set!==0||`DMA.x_issue!==0||`DMA.x_limit!==0||`DMA.issued_rows!==0||
           `DMA.w_issue!==0||`DMA.w_complete!==0||`DMA.b_issue!==0||`DMA.b_complete!==0)
          $fatal(1,"storage queue/transaction ownership metadata not zero after clear");
        if(`DMA.run_x!==0||`DMA.run_w!==0||`DMA.run_b!==0||`DMA.run_y!==0)
          $fatal(1,"task descriptor snapshot survived physical clear");
        if(`DMA.pending||`DMA.locked||`DMA.core_active||`DMA.core_out_valid||
           `DMA.bias_busy||`DMA.bias_valid||`DMA.bias_wait||`DMA.x_filling||`DMA.x_ready||
           `DMA.tile_running||`DMA.y_active||`DMA.clear_write_count!=32768+1024*`G32_RESULT_MACROS)
          $fatal(1,"storage clear owners/count not drained");
        $display("G32_STORAGE_STATE_CLEAR_PASS call=%0d warmup=%0d result_macros=%0d ACC=64 ASSEMBLY=1 METADATA=1 DESCRIPTORS=1 OWNERS=1",call_index,warmup_active,`G32_RESULT_MACROS);
      end
`endif
      if(`NICE.nice_req_valid)$fatal(1,"unexpected NICE traffic");

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
`ifdef XU_MATRIX_STORAGE_SRAM
      if(`CORE.io_outValid&&`CORE.io_outPop&&`CORE.io_outColumn==7)pops=pops+1;
`else
      if(`CORE.io_outValid&&`CORE.io_outPop)pops=pops+1;
`endif
      if(`CORE.io_macStep)macs=macs+1;
      if(`DMA.mem_cmd_valid&&`DMA.mem_cmd_read&&first_request<0)first_request=cycles;
      if(cmd_valid&&!cmd_read&&source_addr&&load_endpoint_offer<0)load_endpoint_offer=cycles;
      if(cmd_valid&&cmd_read&&source_addr&&start_seen&&first_offer<0)first_offer=cycles;
      if(`DMA.mem_cmd_valid&&!`DMA.mem_cmd_ready)begin dma_stalls=dma_stalls+1;if(`DMA.mem_cmd_read)source_stall=source_stall+1;else write_stall=write_stall+1;end
      if(`DMA.mem_rsp_valid&&`DMA.mem_rsp_ready)begin
        if(outstanding!=1||pending_kind==0||`DMA.mem_rsp_err)$fatal(1,"orphan/error DMA response");
        dma_responses=dma_responses+1;outstanding=outstanding-1;
        if(pending_kind==1||pending_kind==2)last_wb_response=cycles;
        if(pending_kind==4)begin yresponses=yresponses+1;if(yresponses==25344)last_y_response=cycles;end
        pending_kind=0;
      end
      if(`DMA.mem_cmd_valid&&`DMA.mem_cmd_ready)begin
        // DMA acceptance is upstream of the original fabric queues; it need
        // not coincide with the endpoint acceptance cycle.
        if(`DMA.mem_cmd_addr[1:0]!=0||`DMA.mem_cmd_wmask!==4'hf)$fatal(1,"DMA width/alignment");
        outstanding=outstanding+1;if(outstanding!=1)$fatal(1,"DMA occupancy");max_outstanding=1;dma_requests=dma_requests+1;
        offset=`DMA.mem_cmd_addr-BASE;
        if(`DMA.mem_cmd_read)begin
          if(!start_seen||clear_finish<0)$fatal(1,"source before start");if(first_accept<0)first_accept=cycles;
          reads=reads+1;
          if(offset<6336*4)begin index=offset/4;if(x_seen[index])$fatal(1,"duplicate X");x_seen[index]=1;xreads=xreads+1;pending_kind=3;if(first_xy<0)first_xy=cycles;end
          else if(offset>='h8000&&offset<'h10000)begin index=(offset-'h8000)/4;if(w_seen[index])$fatal(1,"duplicate W");w_seen[index]=1;wreads=wreads+1;pending_kind=1;end
          else if(offset>='h18000&&offset<'h18800)begin index=(offset-'h18000)/4;if(b_seen[index])$fatal(1,"duplicate BIAS");b_seen[index]=1;breads=breads+1;pending_kind=2;end
          else $fatal(1,"invalid source address %h",`DMA.mem_cmd_addr);
        end else begin
          if(offset<YOFF||offset>=YOFF+25344*4)$fatal(1,"invalid Y address");index=(offset-YOFF)/4;
          if(y_seen[index]||`DMA.mem_cmd_wdata!==golden[index])$fatal(1,"Y mismatch layer=%0d index=%0d got=%h exp=%h",layer,index,`DMA.mem_cmd_wdata,golden[index]);
          y_seen[index]=1;writes=writes+1;pending_kind=4;
        end
      end
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
        if(`MAIN.mem_icb_rsp_err)$fatal(1,"CPU SystemBus error");
        case(cpu_pending_kind)
          1:firmware_cycles=cpu_pending_data;
          2:host_ack=cpu_pending_data;
          3:begin if(clear_finish<0||start_seen)$fatal(1,"clear ACK before physical clear");clear_ack=cpu_pending_data;clear_ack_retired_cycle=cycles;end
          5:begin load_retired=load_retired+1;load_finish=cycles;end
          6:begin
            if(`MAIN.mem_icb_rsp_rdata!==golden[cpu_pending_index])$fatal(1,"CPU public readback mismatch index=%0d got=%h expected=%h",cpu_pending_index,`MAIN.mem_icb_rsp_rdata,golden[cpu_pending_index]);
            fixture_readbacks=fixture_readbacks+1;
          end
          default:begin end
        endcase
        cpu_pending_kind=0;
      end
      if(`MAIN.mem_icb_cmd_valid&&`MAIN.mem_icb_cmd_ready)begin
        cpu_pending_kind=4;cpu_pending_data=`MAIN.mem_icb_cmd_wdata;
        if(!`MAIN.mem_icb_cmd_read)begin
          offset=`MAIN.mem_icb_cmd_addr-BASE;
          if(offset==HOST+8)cpu_pending_kind=1;
          else if(offset==HOST+4)cpu_pending_kind=2;
          else if(offset==HOST+28)cpu_pending_kind=3;
          else if(offset==HOST+20)$fatal(1,"firmware error code %h",`MAIN.mem_icb_cmd_wdata);
          else if(offset>=YOFF&&offset<YOFF+25344*4)begin
            if(clear_seen||start_seen||cpu_pending_data!==32'hdeadbeef||offset!=YOFF+4*fixture_poison_writes)$fatal(1,"CPU poison outside preparation/order");
            fixture_poison_writes=fixture_poison_writes+1;
          end else if(offset<6336*4)begin
            if(clear_ack_retired_cycle<0||start_seen||offset!=4*fixture_x_writes||fixture_w_writes!=0||fixture_b_writes!=0||cpu_pending_data!=={16'b0,x[offset/4]})$fatal(1,"CPU X identity/order");
            fixture_x_writes=fixture_x_writes+1;fixture_source_writes=fixture_source_writes+1;cpu_pending_kind=5;
          end else if(offset>='h8000&&offset<'h10000)begin
            if(clear_ack_retired_cycle<0||start_seen||offset!='h8000+4*fixture_w_writes||fixture_x_writes!=6336||fixture_b_writes!=0||cpu_pending_data!==packed_w[(offset-'h8000)/4])$fatal(1,"CPU W identity/order");
            fixture_w_writes=fixture_w_writes+1;fixture_source_writes=fixture_source_writes+1;cpu_pending_kind=5;
          end else if(offset>='h18000&&offset<'h18800)begin
            index=(offset-'h18000)/8;
            if(clear_ack_retired_cycle<0||start_seen||offset!='h18000+4*fixture_b_writes||fixture_x_writes!=6336||fixture_w_writes!=8192)$fatal(1,"CPU bias load before clear ACK/order");
            if(offset[2])begin if(cpu_pending_data!=={{24{bias[index][39]}},bias[index][39:32]})$fatal(1,"CPU high bias identity");end
            else if(cpu_pending_data!==bias[index][31:0])$fatal(1,"CPU low bias identity");
            fixture_b_writes=fixture_b_writes+1;fixture_source_writes=fixture_source_writes+1;cpu_pending_kind=5;
          end else if(offset==HOST+36)begin end
          else $fatal(1,"unexpected CPU shared write %h",`MAIN.mem_icb_cmd_addr);
        end else begin
          offset=`MAIN.mem_icb_cmd_addr-BASE;
          if(offset>=YOFF&&offset<YOFF+25344*4)begin
            if(!done_seen||last_y_response<0||fixture_readbacks!=(offset-YOFF)/4)$fatal(1,"CPU readback before DONE/fence or wrong order");
            cpu_pending_kind=6;cpu_pending_index=(offset-YOFF)/4;
          end else if(`MAIN.mem_icb_cmd_addr>=32'h00001000&&`MAIN.mem_icb_cmd_addr<32'h00002000)begin
            // The unchanged CPU fetches its reset trampoline from the original
            // boot ROM through mem_icb before entering ITCM. It is not a Y read.
          end else $fatal(1,"unexpected CPU shared read %h",`MAIN.mem_icb_cmd_addr);
        end
      end
      if(endpoint_requests-endpoint_responses!=endpoint_pending||endpoint_pending<0||endpoint_pending>1)$fatal(1,"global endpoint accounting");
      if(`EXU.u_e203_exu_commit.alu_cmt_i_valid&&`EXU.u_e203_exu_commit.alu_cmt_i_ready&&`EXU.u_e203_exu_commit.alu_cmt_i_pc==32'h80000086)begin
        if(`EXU.u_e203_exu_regfile.rf_r[3]!=1)$fatal(1,"firmware return %0d",`EXU.u_e203_exu_regfile.rf_r[3]);firmware_pass=1;
      end
    end
  end
  `include "sysbus32_physical_observer.svh"
  `include "boot_cpu_macros.svh"
  initial begin #10ms;if(!startup_complete)$fatal(1,"CPU startup timeout");end
endmodule
