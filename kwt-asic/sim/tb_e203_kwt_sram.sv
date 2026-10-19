`timescale 1ns/1ps
`include "e203_defines.v"
// CPU executes every load/configuration/result store. Golden is a scoreboard
// only. Shared backdoor preloads and aborted epochs are excluded from the
// explicitly named development window, never reported as official performance.
module tb_e203_kwt_sram;
  reg clk=0,lfextclk=0,rst_n=0;
  always #3.333 clk=~clk;
  always #15258.789 lfextclk=~lfextclk;
  wire hfclk=clk;
  `define SHARED u_e203_soc_top.u_kwt_shared
  `define ACCEL u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.u_kwt_accel
  `define ITCM u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top.u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram
  `define EXU u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top.u_e203_cpu.u_e203_core.u_e203_exu
  reg [7:0] firmware_bytes[0:65535];
  reg [15:0] xv[0:6335],wv[0:16383];
  reg [39:0] bv[0:255];
  reg [47:0] golden[0:25343];
  string vectors,firmware,file_name;
  integer tasks=12,current_task=0,completed=0;
  integer cycle_count=0,external_cycles=0;
  integer task_start=-1,first_config=-1,first_x=-1,last_write_rsp=-1,ack_rsp=-1;
  integer output_words=0,outputs_written=0,write_responses=0,load_commits=0,ack_responses=0;
  integer development_window=0,soft_aborts=0,hard_resets=0,pending_response_reset=0;
  bit epoch_active=0,preflight_done=0,need_begin=0,need_next=0,final_pending=0;
  bit reset_requested=0,await_restart=0;
  bit sp=0,sp_output=0,sp_phase=0,sp_final=0,sp_track=0;
  reg [31:0] sp_data;
  bit ap=0,ap_abort=0,ap_ack=0,ap_track=0;

  task automatic prepare_task(input integer id);
    begin
      file_name=$sformatf("%s/layer_%02d/x.mem",vectors,id);$readmemh(file_name,xv);
      file_name=$sformatf("%s/layer_%02d/w.mem",vectors,id);$readmemh(file_name,wv);
      file_name=$sformatf("%s/layer_%02d/bias.mem",vectors,id);$readmemh(file_name,bv);
      file_name=$sformatf("%s/layer_%02d/y.mem",vectors,id);$readmemh(file_name,golden);
      for(integer i=0;i<3168;i=i+1) `SHARED.memory[i]={xv[2*i+1],xv[2*i]};
      for(integer i=0;i<8192;i=i+1) `SHARED.memory[4096+i]={wv[2*i+1],wv[2*i]};
      for(integer i=0;i<256;i=i+1) begin
        `SHARED.memory[12288+2*i]=bv[i][31:0];
        `SHARED.memory[12288+2*i+1]={24'b0,bv[i][39:32]};
      end
      // Poison is a scoreboard sentinel, not a substitute for task loading.
      for(integer i=0;i<50688;i=i+1) `SHARED.memory[16384+i]=32'hdeadbeef;
      `SHARED.memory[131009]=0;
      `SHARED.memory[131008]=1;
      current_task=id;output_words=0;outputs_written=0;write_responses=0;load_commits=0;ack_responses=0;
      first_config=-1;first_x=-1;last_write_rsp=-1;ack_rsp=-1;task_start=-1;
    end
  endtask

  // Observe the same rising edge at which each endpoint consumes its response.
  // Request metadata is retained until that response, rather than inspecting
  // the unrelated command address/data that happen to be on the bus later.
  always @(posedge `SHARED.clk) begin
    cycle_count=cycle_count+1;
    if(await_restart && rst_n && `ACCEL.rst_n===1'b1) begin
      await_restart=0;epoch_active=1;task_start=cycle_count;
      $display("INFO E203_SRAM_RESTART_RELEASE cycle=%0d",cycle_count);$fflush();
    end
    if(!rst_n) sp=0;
    else begin
      if(`SHARED.rsp_valid && `SHARED.rsp_ready) begin
        if(!sp || `SHARED.rsp_err) $fatal(1,"shared response without request or with error");
        if(sp_output && sp_track) begin
          write_responses=write_responses+1;last_write_rsp=cycle_count;
        end
        if(sp_phase) begin
          if(preflight_done || soft_aborts!=1 || sp_data!==32'h51)
            $fatal(1,"invalid CPU recovery preflight completion");
          preflight_done=1;need_begin=1;
          $display("INFO E203_SRAM_SOFT_ABORT_CONFIRMED cycle=%0d",cycle_count);$fflush();
        end
        if(sp_final) begin
          if(!sp_track || sp_data!==32'h100+current_task || output_words!=50688 ||
             outputs_written!=25344 || write_responses!=50688 || load_commits!=22976 ||
             ack_responses!=1 || !`ACCEL.software_done || `ACCEL.engine_busy ||
             task_start<0 || first_config<task_start || first_x<first_config ||
             last_write_rsp>=ack_rsp || ack_rsp>=cycle_count || hard_resets!=1)
            $fatal(1,"incomplete/early SoC task response task=%0d words=%0d responses=%0d loads=%0d ack=%0d",current_task,output_words,write_responses,load_commits,ack_responses);
          development_window=development_window+cycle_count-task_start+1;
          $display("PASS E203_SRAM_TASK task=%0d outputs=%0d load_commits=%0d start=%0d first_config=%0d first_x=%0d last_write_rsp=%0d ack_rsp=%0d end=%0d window_cycles=%0d core_cycles=%0d output_write_responses=%0d ack_responses=%0d",current_task,outputs_written,load_commits,task_start,first_config,first_x,last_write_rsp,ack_rsp,cycle_count,cycle_count-task_start+1,`ACCEL.engine_cycles,write_responses,ack_responses);$fflush();
          completed=completed+1;epoch_active=0;
          if(completed==tasks) final_pending=1;else need_next=1;
        end
        sp=0;
      end
      if(`SHARED.cmd_valid && `SHARED.cmd_ready) begin
        if(sp) $fatal(1,"multiple outstanding shared commands");
        sp=1;sp_data=`SHARED.cmd_wdata;sp_track=epoch_active;
        sp_output=!`SHARED.cmd_read && `SHARED.cmd_addr>=32'ha0010000 && `SHARED.cmd_addr<32'ha0041800;
        sp_phase=!`SHARED.cmd_read && `SHARED.cmd_addr==32'ha007ff08;
        sp_final=!`SHARED.cmd_read && `SHARED.cmd_addr==32'ha007ff00;
        if((sp_phase || sp_final) && `SHARED.cmd_wmask!==4'hf)
          $fatal(1,"mailbox must use an aligned full-word store");
        if(!`SHARED.cmd_read && `SHARED.cmd_addr==32'ha007ff04)
          $fatal(1,"firmware fail/trap code=%h PC=%h",`SHARED.cmd_wdata,`EXU.u_e203_exu_commit.alu_cmt_i_pc);
        if(epoch_active && `SHARED.cmd_read && `SHARED.cmd_addr==32'ha0000000 && first_x<0) first_x=cycle_count;
        if(sp_output && epoch_active) begin
          if(`SHARED.cmd_wmask!==4'hf || `SHARED.cmd_addr!==32'ha0010000+4*output_words || output_words>=50688)
            $fatal(1,"writeback order/mask task=%0d word=%0d",current_task,output_words);
          if(output_words%2==0) begin
            if(`SHARED.cmd_wdata!==golden[output_words/2][31:0])
              $fatal(1,"writeback LO mismatch task=%0d index=%0d got=%h expected=%h",current_task,output_words/2,`SHARED.cmd_wdata,golden[output_words/2][31:0]);
          end else begin
            if(`SHARED.cmd_wdata!=={16'b0,golden[output_words/2][47:32]})
              $fatal(1,"writeback HI mismatch task=%0d index=%0d",current_task,output_words/2);
            outputs_written=outputs_written+1;
          end
          output_words=output_words+1;
        end
      end
    end
    if(`ACCEL.rst_n!==1'b1) ap=0;
    else begin
      if(`ACCEL.icb_rsp_valid && `ACCEL.icb_rsp_ready) begin
        if(!ap || `ACCEL.icb_rsp_err) $fatal(1,"accelerator response without request or with error");
        if(ap_abort) soft_aborts=soft_aborts+1;
        if(ap_ack && ap_track) begin
          if(write_responses!=50688 || last_write_rsp>=cycle_count)
            $fatal(1,"ACK response before final output store response");
          ack_responses=ack_responses+1;ack_rsp=cycle_count;
        end
        ap=0;
      end
      if(epoch_active && `ACCEL.engine_load_valid && `ACCEL.engine_load_ready) load_commits=load_commits+1;
      if(`ACCEL.icb_cmd_valid && `ACCEL.icb_cmd_ready) begin
        if(ap) $fatal(1,"multiple outstanding accelerator commands");
        ap=1;ap_track=epoch_active;
        ap_abort=!`ACCEL.icb_cmd_read && `ACCEL.icb_cmd_addr==32'h10042008 && `ACCEL.icb_cmd_wdata==4;
        ap_ack=!`ACCEL.icb_cmd_read && `ACCEL.icb_cmd_addr==32'h10042008 && `ACCEL.icb_cmd_wdata==2;
        if(ap_abort && (preflight_done || !`ACCEL.engine_busy)) $fatal(1,"abort must interrupt busy CPU preflight");
        if(epoch_active && !`ACCEL.icb_cmd_read && first_config<0) first_config=cycle_count;
      end
    end
  end

  always @(negedge `SHARED.clk) begin
    if(need_begin) begin need_begin=0;prepare_task(0);epoch_active=1;task_start=cycle_count+1;end
    if(need_next) begin need_next=0;prepare_task(current_task+1);epoch_active=1;task_start=cycle_count+1;end
    // Interrupt a real delayed output write response. No force of internal
    // bus/CPU signals; use the platform's existing external reset input.
    if(epoch_active && !reset_requested && sp && sp_output && output_words>=8 &&
       `SHARED.pending && `SHARED.delay_count>0) begin
      if(!preflight_done) $fatal(1,"reset before preflight response");
      $display("INFO E203_SRAM_PENDING_RESET cycle=%0d discarded_output_words=%0d",cycle_count,output_words);$fflush();
      reset_requested=1;epoch_active=0;rst_n=0;
    end
    if(final_pending) begin
      if(soft_aborts!=1 || hard_resets!=1 || pending_response_reset!=1 || sp || ap)
        $fatal(1,"missing recovery or response still pending at suite completion");
      $display("PASS E203_SRAM_RECOVERY soft_aborts=%0d hard_resets=%0d pending_response_reset=%0d",soft_aborts,hard_resets,pending_response_reset);
      $display("PASS E203_SRAM_SUITE tasks=%0d outputs=%0d development_window_cycles=%0d platform=open_fork_development",completed,completed*25344,development_window);$fflush();
      $finish;
    end
  end

  // PMU restart traverses the low-frequency AON domain, so observe its actual
  // reset. The independent external clock watchdog also runs while hfclk stops.
  initial begin
    wait(reset_requested);
    wait(`ACCEL.rst_n===1'b0);
    // The HF clock can stop immediately on reset assertion. Clear only the
    // scoreboard's abandoned request tags without requiring another HF edge;
    // the actual design pending/rsp reset is checked independently below.
    sp=0;ap=0;
    repeat(64) @(posedge clk);
    @(negedge clk);
    if(`SHARED.pending!==0 || `SHARED.rsp_valid!==0 || `SHARED.memory[131010]!==32'h51)
      $fatal(1,"external reset did not clear transaction state or retain test phase");
    hard_resets=hard_resets+1;pending_response_reset=pending_response_reset+1;
    prepare_task(0);await_restart=1;rst_n=1;
  end
  always @(posedge clk) begin
    external_cycles=external_cycles+1;
    if(external_cycles>200000000) $fatal(1,"SoC watchdog task=%0d reset=%0d bus_cycle=%0d PC=%h",current_task,reset_requested,cycle_count,`EXU.u_e203_exu_commit.alu_cmt_i_pc);
  end
  initial begin
    if(!$value$plusargs("VECTORS=%s",vectors) || !$value$plusargs("FIRMWARE=%s",firmware)) $fatal(1,"missing firmware/vectors");
    if($value$plusargs("TASKS=%d",tasks)) begin end
    if(tasks<1 || tasks>12) $fatal(1,"tasks out of range");
    $readmemh(firmware,firmware_bytes);
    for(integer i=0;i<8192;i=i+1)
      `ITCM.mem_r[i]={firmware_bytes[8*i+7],firmware_bytes[8*i+6],firmware_bytes[8*i+5],firmware_bytes[8*i+4],firmware_bytes[8*i+3],firmware_bytes[8*i+2],firmware_bytes[8*i+1],firmware_bytes[8*i]};
    `SHARED.memory[131010]=0;
    prepare_task(0);
    #120 rst_n=1;
  end
  wire jtag_TDI = 1'b0;
  wire jtag_TDO;
  wire jtag_TCK = 1'b0;
  wire jtag_TMS = 1'b0;
  wire jtag_TRST = 1'b0;

  wire jtag_DRV_TDO = 1'b0;


e203_soc_top u_e203_soc_top(
   
   .hfextclk(hfclk),
   .hfxoscen(),

   .lfextclk(lfextclk),
   .lfxoscen(),

   .io_pads_jtag_TCK_i_ival (jtag_TCK),
   .io_pads_jtag_TMS_i_ival (jtag_TMS),
   .io_pads_jtag_TDI_i_ival (jtag_TDI),
   .io_pads_jtag_TDO_o_oval (jtag_TDO),
   .io_pads_jtag_TDO_o_oe (),

   .io_pads_gpioA_i_ival(32'b0),
   .io_pads_gpioA_o_oval(),
   .io_pads_gpioA_o_oe  (),

   .io_pads_gpioB_i_ival(32'b0),
   .io_pads_gpioB_o_oval(),
   .io_pads_gpioB_o_oe  (),

   .io_pads_qspi0_sck_o_oval (),
   .io_pads_qspi0_cs_0_o_oval(),
   .io_pads_qspi0_dq_0_i_ival(1'b1),
   .io_pads_qspi0_dq_0_o_oval(),
   .io_pads_qspi0_dq_0_o_oe  (),
   .io_pads_qspi0_dq_1_i_ival(1'b1),
   .io_pads_qspi0_dq_1_o_oval(),
   .io_pads_qspi0_dq_1_o_oe  (),
   .io_pads_qspi0_dq_2_i_ival(1'b1),
   .io_pads_qspi0_dq_2_o_oval(),
   .io_pads_qspi0_dq_2_o_oe  (),
   .io_pads_qspi0_dq_3_i_ival(1'b1),
   .io_pads_qspi0_dq_3_o_oval(),
   .io_pads_qspi0_dq_3_o_oe  (),

   .io_pads_aon_erst_n_i_ival (rst_n),//This is the real reset, active low
   .io_pads_aon_pmu_dwakeup_n_i_ival (1'b1),

   .io_pads_aon_pmu_vddpaden_o_oval (),
    .io_pads_aon_pmu_padrst_o_oval    (),

    .io_pads_bootrom_n_i_ival       (1'b0),// In Simulation we boot from ROM
    .io_pads_dbgmode0_n_i_ival       (1'b1),
    .io_pads_dbgmode1_n_i_ival       (1'b1),
    .io_pads_dbgmode2_n_i_ival       (1'b1) 
);



endmodule
