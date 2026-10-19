`timescale 1ns/1ps
`include "e203_defines.v"
module tb_e203_kwt;
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
  integer tasks=12,current_task=0,outputs_written=0,output_words=0;
  integer completed=0,load_commits=0,icb_responses=0,shared_transactions=0;
  integer cycle_count=0,task_start=-1,task_end=-1,full_window=0;
  integer task_phase=0;
  bit need_next=0,final_pending=0;
  always @(posedge `SHARED.clk) begin
    cycle_count=cycle_count+1;
    if(rst_n) begin
      if(`ACCEL.icb_rsp_valid && `ACCEL.icb_rsp_ready) begin
        if(`ACCEL.icb_rsp_err) $fatal(1,"CPU accelerator ICB error task=%0d addr=%h",current_task,`ACCEL.icb_cmd_addr);
        icb_responses=icb_responses+1;
      end
      if(`ACCEL.engine_load_valid && `ACCEL.engine_load_ready) load_commits=load_commits+1;
      if(`SHARED.cmd_valid && `SHARED.cmd_ready) begin
        shared_transactions=shared_transactions+1;
        if(`SHARED.cmd_addr==32'ha0000000 && `SHARED.cmd_read && task_start<0) task_start=cycle_count;
        if(!`SHARED.cmd_read) begin
          if(`SHARED.cmd_addr==32'ha007ff04) $fatal(1,"firmware fail/trap code=%h PC=%h",`SHARED.cmd_wdata,`EXU.u_e203_exu_commit.alu_cmt_i_pc);
          if(`SHARED.cmd_addr>=32'ha0010000 && `SHARED.cmd_addr<32'ha0041800) begin
            if(`SHARED.cmd_wmask!==4'hf || `SHARED.cmd_addr!==32'ha0010000+4*output_words)
              $fatal(1,"writeback order/mask mismatch task=%0d word=%0d addr=%h",current_task,output_words,`SHARED.cmd_addr);
            if(output_words%2==0) begin
              if(`SHARED.cmd_wdata!==golden[output_words/2][31:0]) begin
                $display("DEBUG_MISMATCH task=%0d index=%0d got=%h exp=%h engine=%h",current_task,output_words/2,`SHARED.cmd_wdata,golden[output_words/2][31:0],`ACCEL.engine_y_data);
                $fatal(1,"writeback LO mismatch task=%0d index=%0d",current_task,output_words/2);
              end
            end else begin
              if(`SHARED.cmd_wdata!=={16'b0,golden[output_words/2][47:32]}) $fatal(1,"writeback HI mismatch task=%0d index=%0d",current_task,output_words/2);
              outputs_written=outputs_written+1;
            end
            output_words=output_words+1;
          end
          if(`SHARED.cmd_addr==32'ha007ff00) begin
            if(`SHARED.cmd_wdata!==32'h100+current_task || output_words!=50688 || outputs_written!=25344 || load_commits!=22976 || !`ACCEL.software_done || `ACCEL.engine_busy)
              $fatal(1,"premature/incomplete software task completion task=%0d words=%0d loads=%0d",current_task,output_words,load_commits);
            // All stores have completed in this single-outstanding bus before
            // the completion flag is issued. Include WRITEBACK_ACK response.
            task_end=cycle_count;
            full_window=full_window+task_end-task_start+1;
            $display("PASS E203_KWT_TASK task=%0d outputs=%0d load_commits=%0d cycles=%0d core_cycles=%0d icb_responses=%0d shared_transactions=%0d",current_task,outputs_written,load_commits,task_end-task_start+1,`ACCEL.engine_cycles,icb_responses,shared_transactions);
            completed=completed+1;
            if(completed==tasks) final_pending=1;
            else need_next=1;
          end
        end
      end
    end
    if(cycle_count>200000000) $fatal(1,"SoC watchdog PC=%h",`EXU.u_e203_exu_commit.alu_cmt_i_pc);
  end
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
      for(integer i=0;i<50688;i=i+1) `SHARED.memory[16384+i]=32'hdeadbeef;
      `SHARED.memory[131009]=0;
      `SHARED.memory[131008]=1;
      current_task=id;outputs_written=0;output_words=0;load_commits=0;icb_responses=0;shared_transactions=0;task_start=-1;
    end
  endtask
  always @(negedge `SHARED.clk) begin
    if(need_next) begin need_next=0;prepare_task(current_task+1);end
    if(final_pending && `SHARED.rsp_valid && `SHARED.rsp_ready) begin
      $display("PASS E203_KWT_SUITE tasks=%0d outputs=%0d full_window_cycles=%0d frequency_mhz=150 platform=open_fork_development",completed,completed*25344,full_window);
      $finish;
    end
  end
  initial begin
    if(!$value$plusargs("VECTORS=%s",vectors) || !$value$plusargs("FIRMWARE=%s",firmware)) $fatal(1,"missing firmware/vectors");
    if($value$plusargs("TASKS=%d",tasks)) begin end
    if(tasks<1 || tasks>12) $fatal(1,"tasks out of range");
    $readmemh(firmware,firmware_bytes);
    for(integer i=0;i<8192;i=i+1) begin
      `ITCM.mem_r[i]={firmware_bytes[8*i+7],firmware_bytes[8*i+6],firmware_bytes[8*i+5],firmware_bytes[8*i+4],firmware_bytes[8*i+3],firmware_bytes[8*i+2],firmware_bytes[8*i+1],firmware_bytes[8*i]};
    end
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
