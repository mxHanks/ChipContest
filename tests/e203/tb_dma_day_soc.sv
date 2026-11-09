`timescale 1ns/1fs
`include "e203_defines.v"
// Real CPU + peripheral master + real subsystem arbitration + the tested shared
// ICB SRAM endpoint. Arrays below are endpoint storage and public input vectors;
// the only hierarchical write is the established ITCM program-load contract.
module tb_dma_day_soc;
  reg clk=0, lfclk=0, rst_n=0, startup_complete=0;
  always #3.333333333 clk=~clk;
  always #15258.7890625 lfclk=~lfclk;
  wire cmd_valid,cmd_ready,cmd_read,rsp_ready;
  wire [31:0] cmd_addr,cmd_wdata;
  wire [3:0] cmd_wmask;
  reg rsp_valid=0;
  reg [31:0] rsp_rdata=0;
  reg [31:0] ram[0:131071];
  reg [15:0] x[0:6335],w[0:16383];
  reg [39:0] bias[0:255];
  reg [31:0] golden[0:25343],packed_w[0:8191];
  reg [7:0] program_bytes[0:65535];
  reg y_seen[0:25343],x_seen[0:6335],w_seen[0:8191],b_seen[0:511];
  localparam BASE=32'ha0000000,YOFF=32'h20000,HOST=32'h7f000;
  string testcase,vectors;
  integer tasks,dual,layer=0,completed=0,cycles=0,max_cycles;
  integer warmup=0,warmup_active=0,warmup_completed=0;
  integer throttle=7,first_source_stall=0;
  integer first_request=-1,first_endpoint_request=-1,first_accept=-1,last_y_response=-1;
  integer clear_request=-1,clear_finish=-1,start_request=-1,done_cycle=-1;
  integer reads=0,wreads=0,breads=0,xreads=0,writes=0,yresponses=0;
  integer dma_requests=0,dma_responses=0,dma_stalls=0,endpoint_stalls=0;
  integer source_stall=0,write_stall=0,mmio_reads=0,mmio_writes=0,pops=0,macs=0;
  integer outstanding=0,max_outstanding=0,firmware_cycles=0;
  integer last_accept=-1,accept_interval_sum=0,accept_intervals=0,max_accept_interval=0;
  integer accepted_cycle=-1,latency_sum=0,max_latency=0;
  integer last_wb_response=-1,first_xy_request=-1;
  integer pending_kind=0,pending_index=-1;
  reg endpoint_hold=0,dma_hold=0,cfg_hold=0;
  reg [68:0] endpoint_saved,dma_saved,cfg_saved;
  reg previous_done=0,previous_clear_done=0;
  reg clear_seen=0,start_seen=0,done_seen=0;
  reg [3:0] descriptor_writes=0;
  integer dumpwave=0;
  realtime startup_assert_ns;
  longint unsigned hf_previous_fs=0,lf_previous_fs=0,hf_period_fs=0,lf_period_fs=0;
  integer hf_edges=0,lf_edges=0;
  always @(posedge clk) begin
    if(hf_edges>0) hf_period_fs=longint'($realtime/1fs)-hf_previous_fs;
    hf_previous_fs=longint'($realtime/1fs);hf_edges=hf_edges+1;
  end
  always @(posedge lfclk) begin
    if(lf_edges>0) lf_period_fs=longint'($realtime/1fs)-lf_previous_fs;
    lf_previous_fs=longint'($realtime/1fs);lf_edges=lf_edges+1;
  end

  `define MAIN dut.u_e203_subsys_top.u_e203_subsys_main
  `define CPU `MAIN.u_e203_cpu_top
  `define EXU `CPU.u_e203_cpu.u_e203_core.u_e203_exu
  `define ITCM `CPU.u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram
  `define DMA `MAIN.u_e203_subsys_perips.u_xu_matrix_dma
  `define CORE `DMA.u_core
  `define NICE `CPU.u_e203_cpu.u_e203_nice_core
  wire source_request=cmd_valid && cmd_read && cmd_addr>=BASE && cmd_addr<BASE+'h18800;
  wire dma_source_request=`DMA.mem_cmd_valid && `DMA.mem_cmd_read;
  wire initial_block=source_request && first_accept<0 &&
      (first_endpoint_request<0 ? first_source_stall>0 : cycles-first_endpoint_request<first_source_stall);
  assign cmd_ready=(!rsp_valid || rsp_ready) && (throttle==0 || cycles%throttle!=0) && !initial_block;

  e203_soc_top #(.EXTERNAL_SYSMEM(1)) dut (
    .hfextclk(clk),.lfextclk(lfclk),.io_pads_aon_erst_n_i_ival(rst_n),
    .io_pads_jtag_TCK_i_ival(1'b0),.io_pads_jtag_TMS_i_ival(1'b0),
    .io_pads_jtag_TDI_i_ival(1'b0),.io_pads_gpioA_i_ival(32'b0),
    .io_pads_gpioB_i_ival(32'b0),.io_pads_qspi0_dq_0_i_ival(1'b0),
    .io_pads_qspi0_dq_1_i_ival(1'b0),.io_pads_qspi0_dq_2_i_ival(1'b0),
    .io_pads_qspi0_dq_3_i_ival(1'b0),.io_pads_bootrom_n_i_ival(1'b0),
    .io_pads_dbgmode0_n_i_ival(1'b1),.io_pads_dbgmode1_n_i_ival(1'b1),
    .io_pads_dbgmode2_n_i_ival(1'b1),.io_pads_aon_pmu_dwakeup_n_i_ival(1'b1),
    .ext_sysmem_cmd_valid(cmd_valid),.ext_sysmem_cmd_ready(cmd_ready),
    .ext_sysmem_cmd_addr(cmd_addr),.ext_sysmem_cmd_read(cmd_read),
    .ext_sysmem_cmd_wdata(cmd_wdata),.ext_sysmem_cmd_wmask(cmd_wmask),
    .ext_sysmem_rsp_valid(rsp_valid),.ext_sysmem_rsp_ready(rsp_ready),
    .ext_sysmem_rsp_err(1'b0),.ext_sysmem_rsp_rdata(rsp_rdata),
    .hfxoscen(),.lfxoscen(),.io_pads_jtag_TDO_o_oval(),.io_pads_jtag_TDO_o_oe(),
    .io_pads_gpioA_o_oval(),.io_pads_gpioA_o_oe(),.io_pads_gpioB_o_oval(),.io_pads_gpioB_o_oe(),
    .io_pads_qspi0_sck_o_oval(),.io_pads_qspi0_cs_0_o_oval(),
    .io_pads_qspi0_dq_0_o_oval(),.io_pads_qspi0_dq_0_o_oe(),
    .io_pads_qspi0_dq_1_o_oval(),.io_pads_qspi0_dq_1_o_oe(),
    .io_pads_qspi0_dq_2_o_oval(),.io_pads_qspi0_dq_2_o_oe(),
    .io_pads_qspi0_dq_3_o_oval(),.io_pads_qspi0_dq_3_o_oe(),
    .io_pads_aon_pmu_padrst_o_oval(),.io_pads_aon_pmu_vddpaden_o_oval()
  );

  task load_layer(input integer index);
    string directory;
    integer i;
    begin
      directory=$sformatf("%s/layer_%02d/",vectors,index);
      $readmemh({directory,"x.mem"},x);
      $readmemh({directory,"w.mem"},w);
      $readmemh({directory,"bias.mem"},bias);
      $readmemh({directory,"w_packed16.mem"},packed_w);
      $readmemh({directory,"y32.mem"},golden);
      for(i=0;i<6336;i=i+1) begin ram[i]={16'b0,x[i]};x_seen[i]=0;end
      for(i=0;i<8192;i=i+1) begin
        if(packed_w[i]!=={w[2*i+1],w[2*i]}) $fatal(1,"packed W source mismatch %0d",i);
        ram['h8000/4+i]=packed_w[i];w_seen[i]=0;
      end
      for(i=0;i<256;i=i+1) begin
        ram['h18000/4+2*i]=bias[i][31:0];
        ram['h18000/4+2*i+1]={{24{bias[i][39]}},bias[i][39:32]};
        b_seen[2*i]=0;b_seen[2*i+1]=0;
      end
      for(i=0;i<25344;i=i+1) begin ram[YOFF/4+i]=32'hdeadbeef;y_seen[i]=0;end
      first_request=-1;first_endpoint_request=-1;first_accept=-1;last_y_response=-1;
      clear_request=-1;clear_finish=-1;start_request=-1;done_cycle=-1;
      reads=0;wreads=0;breads=0;xreads=0;writes=0;yresponses=0;
      dma_requests=0;dma_responses=0;dma_stalls=0;endpoint_stalls=0;
      source_stall=0;write_stall=0;mmio_reads=0;mmio_writes=0;pops=0;macs=0;
      last_accept=-1;accept_interval_sum=0;accept_intervals=0;max_accept_interval=0;
      latency_sum=0;max_latency=0;last_wb_response=-1;first_xy_request=-1;
      clear_seen=0;start_seen=0;done_seen=0;descriptor_writes=0;
    end
  endtask

  task report_layer;
    integer i;
    string record_prefix;
    begin
      record_prefix=warmup_active ? "DMA_WARMUP" : "DMA";
      if(!clear_seen || !start_seen || !done_seen || clear_finish<clear_request ||
          first_request<start_request || last_y_response<first_request || done_cycle<=last_y_response ||
          outstanding!=1 || pending_kind!=0 || dma_requests!=dma_responses ||
          reads!=15040 || wreads!=8192 || breads!=512 || xreads!=6336 ||
          writes!=25344 || yresponses!=25344 || pops!=3168 ||
          macs!=(dual?102400:202752))
        $fatal(1,"incomplete task layer=%0d rd=%0d wr=%0d yrsp=%0d pop=%0d mac=%0d dma=%0d/%0d done=%0d last=%0d clear=%0d/%0d",
          layer,reads,writes,yresponses,pops,macs,dma_requests,dma_responses,done_cycle,last_y_response,clear_request,clear_finish);
      if(first_accept-first_request<first_source_stall)
        $fatal(1,"first source VALID boundary omitted forced waiting");
      for(i=0;i<25344;i=i+1)
        if(!y_seen[i] || ram[YOFF/4+i]!==golden[i]) $fatal(1,"final Y coverage/value %0d",i);
      for(i=0;i<6336;i=i+1) if(!x_seen[i]) $fatal(1,"missing X source %0d",i);
      for(i=0;i<8192;i=i+1) if(!w_seen[i]) $fatal(1,"missing W source %0d",i);
      for(i=0;i<512;i=i+1) if(!b_seen[i]) $fatal(1,"missing bias source %0d",i);
      if(`DMA.read_count!==15040 || `DMA.write_count!==25344 || `DMA.pop_count!==3168 ||
          `DMA.mac_count!==(dual?102400:202752)) $fatal(1,"DMA counters differ from independent observers");
      $display("%s_TASK_PASS layer=%0d dual=%0d outputs=25344 payload=%0d clear=%0d principal=%0d gap=%0d including_gap=%0d firmware_cycles=%0d start_to_done=%0d",
        record_prefix,layer,dual,last_y_response-first_request+1,clear_finish-clear_request+1,
        last_y_response-first_request+1+clear_finish-clear_request+1,
        first_request-clear_finish-1,last_y_response-clear_request+1,firmware_cycles,done_cycle-start_request+1);
      $display("%s_WINDOW layer=%0d first_request=%0d endpoint_request=%0d first_accept=%0d last_y_response=%0d clear_request=%0d clear_done=%0d start=%0d done=%0d",
        record_prefix,layer,first_request,first_endpoint_request,first_accept,last_y_response,clear_request,clear_finish,start_request,done_cycle);
      $display("%s_COUNTS layer=%0d reads=%0d w_reads=%0d bias_reads=%0d x_reads=%0d writes=%0d write_responses=%0d requests=%0d responses=%0d pops=%0d macs=%0d mmio_reads=%0d mmio_writes=%0d",
        record_prefix,layer,reads,wreads,breads,xreads,writes,yresponses,dma_requests,dma_responses,pops,macs,mmio_reads,mmio_writes);
      $display("%s_CHANNEL layer=%0d wb_cycles=%0d xy_window=%0d endpoint_stall=%0d dma_stall=%0d source_stall=%0d write_stall=%0d accept_interval_sum=%0d accept_intervals=%0d max_accept_interval=%0d response_latency_sum=%0d max_response_latency=%0d max_outstanding=%0d",
        record_prefix,layer,last_wb_response-first_request+1,last_y_response-first_xy_request+1,endpoint_stalls,dma_stalls,source_stall,write_stall,
        accept_interval_sum,accept_intervals,max_accept_interval,latency_sum,max_latency,max_outstanding);
      $fflush();
    end
  endtask

  initial begin : initialize
    integer i;
    if(!$value$plusargs("TESTCASE=%s",testcase) || !$value$plusargs("VECTORS=%s",vectors) ||
       !$value$plusargs("TASKS=%d",tasks) || !$value$plusargs("DUAL=%d",dual)) $fatal(1,"missing plusargs");
    if(!$value$plusargs("WARMUP=%d",warmup)) warmup=0;
    warmup_active=warmup;
    if(tasks<1 || tasks>12 || dual<0 || dual>1 || warmup<0 || warmup>1) $fatal(1,"invalid task/dual mode");
    if(!$value$plusargs("MAX_CYCLES=%d",max_cycles)) max_cycles=20000000;
    if(!$value$plusargs("THROTTLE=%d",throttle)) throttle=7;
    if(!$value$plusargs("FIRST_SOURCE_STALL=%d",first_source_stall)) first_source_stall=0;
    if(throttle<0 || throttle==1 || first_source_stall<0 || first_source_stall>1000) $fatal(1,"invalid channel settings");
    for(i=0;i<65536;i=i+1) program_bytes[i]=0;
    $readmemh({testcase,".verilog"},program_bytes);
    for(i=0;i<8192;i=i+1)
      `ITCM.mem_r[i]={program_bytes[8*i+7],program_bytes[8*i+6],program_bytes[8*i+5],program_bytes[8*i+4],
        program_bytes[8*i+3],program_bytes[8*i+2],program_bytes[8*i+1],program_bytes[8*i]};
    ram[HOST/4]=tasks;ram[HOST/4+3]=dual;ram[HOST/4+4]=warmup;ram[HOST/4+5]=0;
    load_layer(0);
    if($value$plusargs("DUMPWAVE=%d",dumpwave) && dumpwave) begin
      $dumpfile("tb_dma_day_soc.vcd");$dumpvars(0,`DMA);
    end
    #120 rst_n=1;
    wait(`CPU.u_e203_cpu.rst_core===1'b1);
    @(negedge clk);
    if(cmd_valid || `DMA.cfg_cmd_valid || `DMA.mem_cmd_valid || `NICE.nice_req_valid)
      $fatal(1,"unsafe reset prewarm transaction");
    startup_assert_ns=$realtime/1ns;
    rst_n=0;
    #120ns;
    if(`CPU.u_e203_cpu.rst_core!==1'b0) $fatal(1,"external reset did not reach real CPU");
    if(hf_period_fs!=6666666 || lf_period_fs!=30517578126 || hf_edges<2 || lf_edges<2)
      $fatal(1,"measured clock period differs from declared 150MHz development stimulus");
    startup_complete=1;rst_n=1;
    $display("DMA_CLOCK measured_hf_period_fs=%0d measured_lf_period_fs=%0d hf_edges=%0d lf_edges=%0d",
      hf_period_fs,lf_period_fs,hf_edges,lf_edges);
    $display("DMA_STARTUP external_double_reset=1 held_ns=%.6f clock_period_fs=6666666",
      $realtime/1ns-startup_assert_ns);
  end

  always @(posedge clk) begin : monitor_and_memory
    integer offset,index,interval,latency;
    reg [8:0] cfg_offset;
    cycles<=startup_complete ? cycles+1 : 0;
    if(startup_complete && cycles>max_cycles) $fatal(1,"SoC timeout layer=%0d writes=%0d state=%0d",layer,writes,`DMA.state);
    if(startup_complete && rst_n) begin
      if(`NICE.nice_req_valid) $fatal(1,"independent DMA candidate unexpectedly used NICE");
      if(endpoint_hold && (!cmd_valid || {cmd_addr,cmd_read,cmd_wdata,cmd_wmask}!==endpoint_saved))
        $fatal(1,"shared command changed under backpressure");
      endpoint_hold=cmd_valid && !cmd_ready;endpoint_saved={cmd_addr,cmd_read,cmd_wdata,cmd_wmask};
      if(dma_hold && (!`DMA.mem_cmd_valid || {`DMA.mem_cmd_addr,`DMA.mem_cmd_read,`DMA.mem_cmd_wdata,`DMA.mem_cmd_wmask}!==dma_saved))
        $fatal(1,"DMA command changed under backpressure");
      dma_hold=`DMA.mem_cmd_valid && !`DMA.mem_cmd_ready;
      dma_saved={`DMA.mem_cmd_addr,`DMA.mem_cmd_read,`DMA.mem_cmd_wdata,`DMA.mem_cmd_wmask};
      if(cfg_hold && (!`DMA.cfg_cmd_valid || {`DMA.cfg_cmd_addr,`DMA.cfg_cmd_read,`DMA.cfg_cmd_wdata,`DMA.cfg_cmd_wmask}!==cfg_saved))
        $fatal(1,"CPU DMA MMIO command changed under backpressure");
      cfg_hold=`DMA.cfg_cmd_valid && !`DMA.cfg_cmd_ready;
      cfg_saved={`DMA.cfg_cmd_addr,`DMA.cfg_cmd_read,`DMA.cfg_cmd_wdata,`DMA.cfg_cmd_wmask};
      if(`DMA.cfg_cmd_valid && `DMA.cfg_cmd_ready) begin
        cfg_offset=`DMA.cfg_cmd_addr[8:0];
        if(`DMA.cfg_cmd_read) mmio_reads=mmio_reads+1;
        else begin
          mmio_writes=mmio_writes+1;
          if(`DMA.cfg_cmd_wmask!==4'hf) $fatal(1,"partial DMA MMIO write");
          case(cfg_offset)
            9'h104: begin // full peripheral offset 0x304, low9 =0x104
              if(`DMA.cfg_cmd_wdata===1) begin
                if(clear_seen || start_seen || outstanding!=0) $fatal(1,"duplicate/unsafe clear");
                clear_seen=1;clear_request=cycles;
              end else if(`DMA.cfg_cmd_wdata===(2|(dual<<8))) begin
                if(!clear_seen || clear_finish<0 || start_seen || descriptor_writes!==4'hf)
                  $fatal(1,"start before physical clear/descriptor completion");
                start_seen=1;start_request=cycles;
              end else $fatal(1,"unexpected DMA CTRL write %h",`DMA.cfg_cmd_wdata);
            end
            9'h110: begin if(`DMA.cfg_cmd_wdata!==BASE) $fatal(1,"X descriptor identity");descriptor_writes[0]=1;end
            9'h114: begin if(`DMA.cfg_cmd_wdata!==BASE+'h8000) $fatal(1,"W descriptor identity");descriptor_writes[1]=1;end
            9'h118: begin if(`DMA.cfg_cmd_wdata!==BASE+'h18000) $fatal(1,"bias descriptor identity");descriptor_writes[2]=1;end
            9'h11c: begin if(`DMA.cfg_cmd_wdata!==BASE+YOFF) $fatal(1,"Y descriptor identity");descriptor_writes[3]=1;end
            default:$fatal(1,"unexpected DMA MMIO write offset=%h",cfg_offset);
          endcase
        end
      end
      if(`DMA.clear_done && !previous_clear_done) begin
        if(!clear_seen || start_seen) $fatal(1,"clear_done without current clear request");
        clear_finish=cycles;
      end
      previous_clear_done=`DMA.clear_done;
      if(`DMA.done && !previous_done) begin
        if(!start_seen || outstanding!=0 || writes!=25344 || yresponses!=25344 ||
            `DMA.mem_cmd_valid || dma_requests!=dma_responses) $fatal(1,"premature DMA completion");
        done_seen=1;done_cycle=cycles;
      end
      previous_done=`DMA.done;
      if(`DMA.error) $fatal(1,"DMA reported hardware error");
      if(`CORE.io_outValid && `CORE.io_outPop) pops=pops+1;
      if(`CORE.io_macStep) macs=macs+1;
      if(dma_source_request && first_request<0) first_request=cycles;
      if(source_request && first_endpoint_request<0) first_endpoint_request=cycles;
      if(`DMA.mem_cmd_valid && !`DMA.mem_cmd_ready) dma_stalls=dma_stalls+1;
      // End-to-end identity across the actual peripheral arbiter: an accepted
      // master command is precisely the accepted external shared-SRAM command.
      if(`DMA.mem_cmd_valid && `DMA.mem_cmd_ready) begin
        if(!(cmd_valid && cmd_ready) ||
            {cmd_addr,cmd_read,cmd_wdata,cmd_wmask}!==
            {`DMA.mem_cmd_addr,`DMA.mem_cmd_read,`DMA.mem_cmd_wdata,`DMA.mem_cmd_wmask} ||
            cmd_addr<BASE || cmd_addr>=BASE+'h40000)
          $fatal(1,"DMA command did not traverse real shared fabric/arbiter unchanged");
        dma_requests=dma_requests+1;
      end
      if(cmd_valid && cmd_ready && cmd_addr>=BASE && cmd_addr<BASE+'h40000 &&
          !(`DMA.mem_cmd_valid && `DMA.mem_cmd_ready))
        $fatal(1,"tensor endpoint command has no accepted independent DMA owner");
      if(`DMA.mem_rsp_valid && `DMA.mem_rsp_ready) begin
        if(!(rsp_valid && rsp_ready) || pending_kind==0 || `DMA.mem_rsp_err ||
            `DMA.mem_rsp_rdata!==rsp_rdata)
          $fatal(1,"DMA response differs from real shared endpoint owner/data");
        dma_responses=dma_responses+1;
      end
      if(rsp_valid && rsp_ready && pending_kind!=0 &&
          !(`DMA.mem_rsp_valid && `DMA.mem_rsp_ready))
        $fatal(1,"tensor endpoint response retired without DMA owner");
      if(cmd_valid && !cmd_ready && cmd_addr<BASE+'h40000) begin
        endpoint_stalls=endpoint_stalls+1;
        if(cmd_read) source_stall=source_stall+1;else write_stall=write_stall+1;
      end
      if(rsp_valid && outstanding!=1) $fatal(1,"orphan shared response");
      if(rsp_valid && rsp_ready) begin
        outstanding=outstanding-1;
        if(pending_kind!=0) begin
          latency=cycles-accepted_cycle;latency_sum=latency_sum+latency;
          if(latency>max_latency) max_latency=latency;
        end
        if(pending_kind==1 || pending_kind==2) last_wb_response=cycles;
        if(pending_kind==4) begin
          yresponses=yresponses+1;
          if(yresponses==25344) last_y_response=cycles;
        end
        pending_kind=0;pending_index=-1;
        rsp_valid<=0;
      end
      if(cmd_ready) begin
        rsp_valid<=cmd_valid;
        if(cmd_valid) begin
          if(cmd_addr<BASE || cmd_addr>=BASE+'h80000 || cmd_addr[1:0]!=0) $fatal(1,"shared address %h",cmd_addr);
          outstanding=outstanding+1;if(outstanding>max_outstanding) max_outstanding=outstanding;
          if(outstanding!=1) $fatal(1,"shared occupancy exceeds endpoint configuration");
          offset=cmd_addr-BASE;index=offset/4;accepted_cycle=cycles;
          if(cmd_read) begin
            rsp_rdata<=ram[index];
            if(offset<'h18800) begin
              if(!start_seen || clear_finish<0) $fatal(1,"source before start/clear");
              if(first_accept<0) first_accept=cycles;
              if(last_accept>=0) begin
                interval=cycles-last_accept;accept_interval_sum=accept_interval_sum+interval;
                accept_intervals=accept_intervals+1;if(interval>max_accept_interval) max_accept_interval=interval;
              end
              last_accept=cycles;reads=reads+1;
              if(offset<6336*4) begin
                if(x_seen[index]) $fatal(1,"duplicate X read %0d",index);
                x_seen[index]=1;xreads=xreads+1;pending_kind=3;
                if(first_xy_request<0) first_xy_request=cycles;
              end else if(offset>='h8000 && offset<'h10000) begin
                index=(offset-'h8000)/4;if(w_seen[index]) $fatal(1,"duplicate W read");
                w_seen[index]=1;wreads=wreads+1;pending_kind=1;
              end else if(offset>='h18000 && offset<'h18800) begin
                index=(offset-'h18000)/4;if(b_seen[index]) $fatal(1,"duplicate bias read");
                b_seen[index]=1;breads=breads+1;pending_kind=2;
              end else $fatal(1,"invalid source gap read %h",cmd_addr);
            end else if(offset<HOST || offset>=HOST+24) $fatal(1,"unexpected CPU shared read %h",cmd_addr);
          end else begin
            if(cmd_wmask!==4'hf) $fatal(1,"partial shared write");
            if(offset>=YOFF && offset<YOFF+25344*4) begin
              index=(offset-YOFF)/4;
              if(y_seen[index] || cmd_wdata!==golden[index])
                $fatal(1,"Y mismatch/duplicate layer=%0d word=%0d got=%h expected=%h",layer,index,cmd_wdata,golden[index]);
              y_seen[index]=1;ram[offset/4]=cmd_wdata;writes=writes+1;pending_kind=4;
              if(last_accept>=0) begin
                interval=cycles-last_accept;accept_interval_sum=accept_interval_sum+interval;
                accept_intervals=accept_intervals+1;if(interval>max_accept_interval) max_accept_interval=interval;
              end
              last_accept=cycles;
            end else if(offset==HOST+8) firmware_cycles=cmd_wdata;
            else if(offset==HOST+20) $fatal(1,"firmware first error code=%h",cmd_wdata);
            else if(offset==HOST+4) begin
              if(cmd_wdata!=completed+warmup_completed+1) $fatal(1,"incorrect host ACK");
              report_layer();
              if(warmup_active) begin
                warmup_active=0;warmup_completed=1;
                $display("DMA_WARMUP_DONE tasks=1 outputs=25344 excluded_principal=1");
                load_layer(0);
              end else begin
                completed=completed+1;layer=layer+1;
                if(layer<tasks) load_layer(layer);
              end
            end else $fatal(1,"unexpected shared write %h",cmd_addr);
          end
        end
      end
      if(`EXU.u_e203_exu_commit.alu_cmt_i_valid && `EXU.u_e203_exu_commit.alu_cmt_i_ready &&
          `EXU.u_e203_exu_commit.alu_cmt_i_pc==32'h80000086) begin
        if(`EXU.u_e203_exu_regfile.rf_r[3]!=1 || completed!=tasks || warmup_completed!=warmup)
          $fatal(1,"firmware failure gp=%0d completed=%0d",`EXU.u_e203_exu_regfile.rf_r[3],completed);
        $display("DMA_SOC_PASS tasks=%0d dual=%0d outputs=%0d writes=%0d",completed,dual,completed*25344,completed*25344);
        $finish;
      end
    end
  end

  initial begin #10ms;if(!startup_complete) $fatal(1,"CPU reset-release timeout");end
endmodule
