// Generated from original TB SHA256 b80fa66842a4d7bed21b264ac30e0e561bc5b53ad3f0b71ed2337dfa1ddc76d2
`timescale 1ns/1fs
`include "e203_defines.v"
module tb_xu_soc_ppa;
  reg clk = 0, lfclk = 0, rst_n = 0;
  integer xu_half_index=0, xu_reset_edges=0, xu_static_checks=0;
  real xu_target_ns;
  `define XU_HCLK dut.u_soc.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_hclkgen
  always @(posedge clk) begin
    if (!rst_n) xu_reset_edges=xu_reset_edges+1;
    else begin
      if ({`XU_HCLK.test_mode,`XU_HCLK.pllbypass,`XU_HCLK.plloutdivby1,
           `XU_HCLK.plloutdiv,`XU_HCLK.pll_RESET,`XU_HCLK.pll_ASLEEP,
           `XU_HCLK.pll_OD,`XU_HCLK.pll_M,`XU_HCLK.pll_N} !==
          {1'b0,1'b1,1'b1,6'b0,1'b0,1'b0,2'd2,8'd50,5'd2})
        $fatal(1,"nominal150 clock controls departed from static reset bypass/divby1 mode");
      xu_static_checks=xu_static_checks+1;
    end
  end

  initial forever begin
    xu_half_index=xu_half_index+1;
    xu_target_ns=xu_half_index*(10.0/3.0);
    #(xu_target_ns-$realtime);
    clk=~clk;
  end
  integer xu_lf_half_index=0, xu_lf_static_checks=0;
  real xu_lf_target_ns, xu_lf_phase_error_fs;
  initial forever begin
    xu_lf_half_index=xu_lf_half_index+1;
    xu_lf_target_ns=xu_lf_half_index*15258.7890625;
    #(xu_lf_target_ns-$realtime);
    xu_lf_phase_error_fs=($realtime-xu_lf_target_ns)*1000000.0;
    if (xu_lf_phase_error_fs>1.01 || xu_lf_phase_error_fs< -1.01)
      $fatal(1,"nominal32768 LF absolute phase drift exceeded 1fs");
    xu_lf_static_checks=xu_lf_static_checks+1;
    lfclk=~lfclk;
  end
  wire cmd_valid, cmd_read, cmd_ready, rsp_ready;
  wire [31:0] cmd_addr, cmd_wdata;
  wire [3:0] cmd_wmask;
  wire rsp_valid;
  wire [31:0] rsp_rdata;
  wire rsp_err;
  reg [31:0] ram [0:131071]; // Development shared SRAM: exactly 512 KiB.
  reg [15:0] x [0:6335], w [0:16383];
  reg [39:0] bias [0:255];
  reg [47:0] golden [0:25343];
  reg [7:0] program_bytes [0:65535];
  reg [63:0] xu_program_words [0:8191];
  string testcase, vectors;
  integer tasks, layer = 0, completed = 0, writes = 0;
  integer cycles = 0, first_cycle = -1, last_cycle = 0;
  integer max_cycles, firmware_cycles = 0;
  integer outstanding = 0;
  reg final_write_pending = 0;
  integer dumpwave;
  localparam BASE = 32'ha0000000, YOFF = 32'h20000, HOST = 32'h7f000;

  // Backpressure exercises CPU/bus waits; responses remain stable until accepted.
  assign cmd_ready=dut.ext_sysmem_cmd_ready;
  assign cmd_valid=dut.ext_sysmem_cmd_valid;
  assign cmd_read=dut.ext_sysmem_cmd_read;
  assign cmd_addr=dut.ext_sysmem_cmd_addr;
  assign cmd_wdata=dut.ext_sysmem_cmd_wdata;
  assign cmd_wmask=dut.ext_sysmem_cmd_wmask;
  assign rsp_ready=dut.ext_sysmem_rsp_ready;
  assign rsp_valid=dut.ext_sysmem_rsp_valid;
  assign rsp_rdata=dut.ext_sysmem_rsp_rdata;
  assign rsp_err=dut.ext_sysmem_rsp_err;
  `define CPU dut.u_soc.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top
  `define EXU `CPU.u_e203_cpu.u_e203_core.u_e203_exu
  `define ITCM `CPU.u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram
  `define ACCEL dut.u_soc.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.u_accel_icb_slave

  // xu passive S2c observer. Reads actual core inputs at their sampling edge.
  integer xu_global_task, xu_saif_started=0, xu_saif_stopped=0;
  integer xu_w_count=0, xu_x_count=0, xu_bias_count=0, xu_rows=0;
  integer xu_starts=0, xu_dones=0, xu_pops=0, xu_w_pairs=0, xu_x_pairs=0;
  integer xu_clear_w_commits=0, xu_clear_x_commits=0, xu_clear_bias_commits=0;
  reg [16383:0] xu_clear_w_committed=0, xu_w_seen=0;
  reg [63:0] xu_clear_x_committed=0, xu_x_seen=0;
  reg [4:0] xu_bias_seen [0:255];
  reg [4:0] xu_clear_bias_committed [0:255];
  reg [15:0] xu_result_words=0;
  integer xu_reset_checked=0;
  integer xu_w_cursor_setups=0, xu_x_cursor_setups=0, xu_cache_mode_writes=0;
  reg xu_result_response_pending=0;
  reg [31:0] xu_result_response_word=0;

  task xu_observe_candidate;
    integer a, logical_index, lane, bit_index, b;
    reg [4:0] old_mask, new_mask;
    reg w_commit, x_commit, bias_commit;
    begin
      w_commit=`ACCEL.u_linear_compute_core.io_wLoadWen;
      x_commit=`ACCEL.u_linear_compute_core.io_xLoadWen;
      bias_commit=`ACCEL.u_linear_compute_core.io_cacheWriteEnable;
      if ((^{w_commit,x_commit,bias_commit,`ACCEL.row_active,`ACCEL.row_count,
              `ACCEL.row_running,`ACCEL.row_produced,`ACCEL.row_retired})===1'bx)
        $fatal(1,"XU_CANDIDATE_REJECT unknown commit/FIFO ownership state");
      if (!xu_reset_checked) begin
        if ({`ACCEL.row_active,`ACCEL.row_running,`ACCEL.row_count,
             `ACCEL.row_produced,`ACCEL.row_retired,
             `ACCEL.u_linear_compute_core.head,`ACCEL.u_linear_compute_core.tail}!==0)
          $fatal(1,"XU_CANDIDATE_REJECT FIFO logical ownership was not reset");
        xu_reset_checked=1;
      end
      if (`ACCEL.row_count>2 || `ACCEL.row_produced<`ACCEL.row_retired ||
          `ACCEL.row_produced-`ACCEL.row_retired!=`ACCEL.row_count)
        $fatal(1,"XU_CANDIDATE_REJECT FIFO conservation");
      if ((`ACCEL.row_active || `ACCEL.row_start) && (w_commit || x_commit || bias_commit))
        $fatal(1,"XU_CANDIDATE_REJECT operand commit while row owns storage");
      if (xu_result_response_pending) begin
        if (!`ACCEL.rsp_valid || `ACCEL.rsp_rdata!==xu_result_response_word)
          $fatal(1,"XU_CANDIDATE_REJECT result response absent/changed before retirement");
        if (`ACCEL.rsp_ready) xu_result_response_pending=0;
      end
      if (`ACCEL.rsp_valid && `ACCEL.rsp_err)
        $fatal(1,"XU_CANDIDATE_REJECT accelerator error response");
      if (w_commit) begin
        if ((^{`ACCEL.u_linear_compute_core.io_wLoadBank,
               `ACCEL.u_linear_compute_core.io_wLoadAddr,
               `ACCEL.u_linear_compute_core.io_wLoadData})===1'bx)
          $fatal(1,"XU_CANDIDATE_REJECT unknown W commit");
        a=`ACCEL.u_linear_compute_core.io_wLoadBank*2048+
          `ACCEL.u_linear_compute_core.io_wLoadAddr;
        logical_index=(`ACCEL.u_linear_compute_core.io_wLoadAddr%64)*256+
          (`ACCEL.u_linear_compute_core.io_wLoadAddr/64)*8+
          `ACCEL.u_linear_compute_core.io_wLoadBank;
        if (!xu_saif_started) begin
          if (xu_clear_w_committed[a] || `ACCEL.u_linear_compute_core.io_wLoadData!==16'b0)
            $fatal(1,"XU_CANDIDATE_REJECT duplicate/nonzero actual W clear commit");
          xu_clear_w_committed[a]=1; xu_clear_w_commits=xu_clear_w_commits+1;
        end else begin
          if (xu_saif_stopped || xu_w_seen[a] ||
              `ACCEL.u_linear_compute_core.io_wLoadData!==w[logical_index])
            $fatal(1,"XU_CANDIDATE_REJECT outside/duplicate/fixture-mismatched actual W commit");
          if (!`ACCEL.stream_pending || !`ACCEL.stream_is_w || !`ACCEL.stream_pair ||
              `ACCEL.stream_cursor!==2*(xu_w_count/2) ||
              `ACCEL.stream_second!==(xu_w_count%2!=0))
            $fatal(1,"XU_CANDIDATE_REJECT W PACK32 first/second commit order");
          xu_w_seen[a]=1; xu_w_count=xu_w_count+1;
        end
      end
      if (x_commit) begin
        if ((^{`ACCEL.u_linear_compute_core.io_xLoadAddr,
               `ACCEL.u_linear_compute_core.io_xLoadData})===1'bx)
          $fatal(1,"XU_CANDIDATE_REJECT unknown X commit");
        a=`ACCEL.u_linear_compute_core.io_xLoadAddr;
        if (!xu_saif_started) begin
          if (xu_clear_x_committed[a] || `ACCEL.u_linear_compute_core.io_xLoadData!==16'b0)
            $fatal(1,"XU_CANDIDATE_REJECT duplicate/nonzero actual X clear commit");
          xu_clear_x_committed[a]=1; xu_clear_x_commits=xu_clear_x_commits+1;
        end else begin
          if (xu_saif_stopped || xu_rows>=99 || xu_x_seen[a] ||
              `ACCEL.u_linear_compute_core.io_xLoadData!==x[xu_rows*64+a])
            $fatal(1,"XU_CANDIDATE_REJECT outside/duplicate/fixture-mismatched actual X commit");
          if (!`ACCEL.stream_pending || `ACCEL.stream_is_w || !`ACCEL.stream_pair ||
              `ACCEL.stream_cursor!==2*((xu_x_count%64)/2) ||
              `ACCEL.stream_second!==(xu_x_count%2!=0))
            $fatal(1,"XU_CANDIDATE_REJECT X PACK32 first/second commit order");
          xu_x_seen[a]=1; xu_x_count=xu_x_count+1;
        end
      end
      if (bias_commit) begin
        a=`ACCEL.u_linear_compute_core.io_cacheWriteAddr;
        if ((^{a,`ACCEL.u_linear_compute_core.io_cacheWriteData,
               `ACCEL.u_linear_compute_core.io_cacheWriteMask})===1'bx || `ACCEL.cache_enable)
          $fatal(1,"XU_CANDIDATE_REJECT unknown/enabled-cache bias commit");
        old_mask=xu_saif_started ? xu_bias_seen[a] : xu_clear_bias_committed[a];
        new_mask=`ACCEL.u_linear_compute_core.io_cacheWriteMask;
        if (new_mask!==5'b01111 && new_mask!==5'b10000)
          $fatal(1,"XU_CANDIDATE_REJECT incomplete bias commit mask");
        if ((new_mask & old_mask)!=0 || xu_saif_stopped)
          $fatal(1,"XU_CANDIDATE_REJECT duplicate/outside bias commit");
        for (b=0;b<5;b=b+1) if (new_mask[b] &&
            `ACCEL.u_linear_compute_core.io_cacheWriteData[8*b+:8] !==
            (xu_saif_started ? bias[a][8*b+:8] : 8'b0))
          $fatal(1,"XU_CANDIDATE_REJECT incorrect actual bias byte");
        if (xu_saif_started) xu_bias_seen[a]=old_mask|new_mask;
        else xu_clear_bias_committed[a]=old_mask|new_mask;
        if ((old_mask|new_mask)==31) begin
          if (xu_saif_started) xu_bias_count=xu_bias_count+1;
          else xu_clear_bias_commits=xu_clear_bias_commits+1;
        end
      end
      if (`ACCEL.cmd_valid && `ACCEL.cmd_ready && !`ACCEL.cmd_read && xu_saif_started) begin
        if (xu_saif_stopped) $fatal(1,"XU_CANDIDATE_REJECT task write after final Y retirement");
        case (`ACCEL.cmd_addr[11:0])
          12'h054: begin
            if (`ACCEL.cmd_wmask!==15 || `ACCEL.cmd_wdata!==0 || xu_w_count!=0 || xu_w_cursor_setups!=0)
              $fatal(1,"XU_CANDIDATE_REJECT W cursor setup");
            xu_w_cursor_setups=xu_w_cursor_setups+1;
          end
          12'h060: begin
            if (`ACCEL.cmd_wmask!==15 || `ACCEL.cmd_wdata!==0 || xu_x_count!=xu_rows*64 ||
                xu_x_cursor_setups!=xu_rows || xu_rows>=99)
              $fatal(1,"XU_CANDIDATE_REJECT X cursor setup");
            xu_x_cursor_setups=xu_x_cursor_setups+1;
          end
          12'h040: begin
            if (`ACCEL.cmd_wmask!==15 || xu_w_count!=16384 || xu_cache_mode_writes>=2 ||
                `ACCEL.cmd_wdata!==xu_cache_mode_writes ||
                xu_bias_count!=(xu_cache_mode_writes==0 ? 0 : 256))
              $fatal(1,"XU_CANDIDATE_REJECT cache mode setup order/count");
            xu_cache_mode_writes=xu_cache_mode_writes+1;
          end
          12'h05c: begin
            if (`ACCEL.cmd_wmask!==15) $fatal(1,"XU_CANDIDATE_REJECT W PACK32 mask");
            xu_w_pairs=xu_w_pairs+1;
          end
          12'h068: begin
            if (`ACCEL.cmd_wmask!==15) $fatal(1,"XU_CANDIDATE_REJECT X PACK32 mask");
            xu_x_pairs=xu_x_pairs+1;
          end
          12'h044,12'h048,12'h04c,12'h0c0,12'h0c8: begin end
          default: $fatal(1,"XU_CANDIDATE_REJECT unexpected payload MMIO write");
        endcase
      end
      if (`ACCEL.row_start_accept) begin
        if (!xu_saif_started || xu_saif_stopped || xu_rows>=99 ||
            xu_w_count!=16384 || xu_bias_count!=256 || xu_x_seen!==64'hffffffffffffffff ||
            `ACCEL.cache_enable!==1 || `ACCEL.stream_pending ||
            `ACCEL.u_linear_compute_core.io_wLoadWen || `ACCEL.u_linear_compute_core.io_xLoadWen ||
            `ACCEL.row_active || `ACCEL.row_count!=0 || xu_pops!=xu_rows*32 ||
            xu_starts!=xu_rows*32 || xu_dones!=xu_rows*32 || xu_result_words!=0)
          $fatal(1,"XU_CANDIDATE_REJECT STARTROW before fresh complete/drained operands/FIFO");
        xu_rows=xu_rows+1; xu_x_seen=0;
      end
      if (`ACCEL.row_active && `ACCEL.compute_start) begin
        if (!xu_saif_started || xu_saif_stopped ||
            `ACCEL.u_linear_compute_core.core.io_group!==xu_starts%32)
          $fatal(1,"XU_CANDIDATE_REJECT autonomous group start order/window");
        xu_starts=xu_starts+1;
      end
      if (`ACCEL.core_done) begin
        if (!xu_saif_started || xu_saif_stopped || xu_dones>=xu_starts)
          $fatal(1,"XU_CANDIDATE_REJECT unexpected done");
        xu_dones=xu_dones+1;
      end
      if (`ACCEL.cmd_valid && `ACCEL.cmd_ready && `ACCEL.cmd_read &&
          `ACCEL.cmd_addr[11:0]>=12'h100 && `ACCEL.cmd_addr[11:0]<=12'h13c) begin
        lane=`ACCEL.cmd_addr[5:3]; bit_index=`ACCEL.cmd_addr[5:2];
        if (!xu_saif_started || xu_saif_stopped || !`ACCEL.row_valid ||
            `ACCEL.row_group!==xu_pops%32 || xu_result_words[bit_index] ||
            `ACCEL.row_result[lane]!==golden[(xu_rows-1)*256+(xu_pops%32)*8+lane])
          $fatal(1,"XU_CANDIDATE_REJECT incomplete/duplicate/incorrect owned FIFO result");
        if (xu_result_response_pending)
          $fatal(1,"XU_CANDIDATE_REJECT result response overlap without retirement");
        xu_result_response_pending=1;
        xu_result_response_word=bit_index%2 ? {16'b0,`ACCEL.row_result[lane][47:32]} :
                                                           `ACCEL.row_result[lane][31:0];
        xu_result_words[bit_index]=1;
      end
      if (`ACCEL.row_pop) begin
        if (!xu_saif_started || xu_saif_stopped || !`ACCEL.row_active ||
            !`ACCEL.row_valid || `ACCEL.row_group!==xu_pops%32 ||
            xu_result_words!==16'hffff || xu_pops>=xu_rows*32)
          $fatal(1,"XU_CANDIDATE_REJECT POP before all owned words read / wrong group");
        xu_pops=xu_pops+1; xu_result_words=0;
      end
    end
  endtask

  // xu passive clear observer: no force, no DUT assignment, no task payload.
  integer xu_clear_writes=0, xu_clear_w_count=0, xu_clear_bias_count=0;
  integer xu_clear_legacy_count=0, xu_clear_x_count=0, xu_clear_disable_count=0;
  reg [16383:0] xu_clear_w_seen=0;
  reg [63:0] xu_clear_x_seen=0;
  reg [4:0] xu_clear_bias_seen [0:255];
  reg [4:0] xu_clear_legacy_seen [0:7];
  reg xu_clear_complete=0;
  integer xu_clear_init;
  initial begin
    for (xu_clear_init=0;xu_clear_init<256;xu_clear_init=xu_clear_init+1)
      xu_clear_bias_seen[xu_clear_init]=0;
    for (xu_clear_init=0;xu_clear_init<8;xu_clear_init=xu_clear_init+1)
      xu_clear_legacy_seen[xu_clear_init]=0;
  end

  task xu_observe_task_clear;
    input source_request;
    output payload_phase;
    integer a;
    reg [4:0] old_mask, new_mask;
    begin
      if (!xu_clear_complete) begin
        if (`ACCEL.cache_enable!==1'b0 || `ACCEL.busy!==1'b0 ||
            `ACCEL.core_start!==1'b0)
          $fatal(1,"XU_CLEAR_REJECT non-idle/enabled clear phase");
        if (source_request) begin
          if (xu_clear_writes!=33697 || xu_clear_disable_count!=1 ||
              xu_clear_w_count!=16384 || xu_clear_bias_count!=256 ||
              xu_clear_legacy_count!=8 || xu_clear_x_count!=64)
            $fatal(1,"XU_CLEAR_REJECT incomplete clear before first source request");
          // W/X stores are committed one clock after MMIO acceptance.
          if (`ACCEL.w_load_wen!==1'b0 || `ACCEL.x_load_wen!==1'b0 || `ACCEL.stream_pending!==1'b0 || `ACCEL.rsp_valid!==1'b0)
            $fatal(1,"XU_CLEAR_REJECT undrained W/X clear strobe");
          if (xu_clear_w_commits!=16384 || xu_clear_x_commits!=64 ||
              xu_clear_bias_commits!=256 || xu_clear_w_committed!=={16384{1'b1}} ||
              xu_clear_x_committed!==64'hffffffffffffffff || !xu_reset_checked ||
              `ACCEL.row_active || `ACCEL.row_running || `ACCEL.row_count!=0 ||
              `ACCEL.row_produced!=0 || `ACCEL.row_retired!=0 ||
              `ACCEL.u_linear_compute_core.head!==0 || `ACCEL.u_linear_compute_core.tail!==0 ||
              `ACCEL.stream_error || `ACCEL.w_cursor!=0 || `ACCEL.x_cursor!=0)
            $fatal(1,"XU_CLEAR_REJECT incomplete actual zero commits or nonempty FIFO/stream ownership");
          for (a=0;a<8;a=a+1) if (`ACCEL.bias_regs[a]!==40'b0)
            $fatal(1,"XU_CLEAR_REJECT actual legacy bias did not clear");
          xu_clear_complete=1;
          $display("XU_TASK_CLEAR_OBSERVED writes=33697 w=16384 bias=256 legacy_bias=8 x=64 drained=1 cache_enable=0 idle=1 source_request=1 task_setup_writes=0 actual_commits=1 fifo_reset_empty=1");
        end else if (`ACCEL.cmd_valid && `ACCEL.cmd_ready) begin
          if (`ACCEL.cmd_read) begin
            if (`ACCEL.cmd_addr[11:0]!=12'h000 &&
                `ACCEL.cmd_addr[11:0]!=12'h00c &&
                `ACCEL.cmd_addr[11:0]!=12'h050 && `ACCEL.cmd_addr[11:0]!=12'h070 &&
                `ACCEL.cmd_addr[11:0]!=12'h074 && `ACCEL.cmd_addr[11:0]!=12'h078)
              $fatal(1,"XU_CLEAR_REJECT unexpected pretask MMIO read");
          end else begin
            if (xu_clear_writes==33697)
              $fatal(1,"XU_CLEAR_REJECT candidate setup/data write before first source request");
            if (`ACCEL.cmd_wmask!==4'hf ||
                (^`ACCEL.cmd_wdata)===1'bx)
              $fatal(1,"XU_CLEAR_REJECT incomplete/unknown clear word");
            xu_clear_writes=xu_clear_writes+1;
            case (`ACCEL.cmd_addr[11:0])
              12'h040: begin
                if (`ACCEL.cmd_wdata!==32'b0 || xu_clear_disable_count!=0)
                  $fatal(1,"XU_CLEAR_REJECT cache disable");
                xu_clear_disable_count=xu_clear_disable_count+1;
              end
              12'h01c: if (`ACCEL.cmd_wdata>7)
                $fatal(1,"XU_CLEAR_REJECT W bank");
              12'h020: if (`ACCEL.cmd_wdata>2047)
                $fatal(1,"XU_CLEAR_REJECT W address");
              12'h044: if (`ACCEL.cmd_wdata>255)
                $fatal(1,"XU_CLEAR_REJECT bias address");
              12'h028: if (`ACCEL.cmd_wdata>7)
                $fatal(1,"XU_CLEAR_REJECT legacy bias address");
              12'h014: if (`ACCEL.cmd_wdata>63)
                $fatal(1,"XU_CLEAR_REJECT X address");
              12'h024: begin
                if ((^{`ACCEL.w_bank_reg,`ACCEL.w_addr_reg})===1'bx)
                  $fatal(1,"XU_CLEAR_REJECT unknown W destination");
                a=`ACCEL.w_bank_reg*2048+`ACCEL.w_addr_reg;
                if (`ACCEL.cmd_wdata!==32'b0 || xu_clear_w_seen[a])
                  $fatal(1,"XU_CLEAR_REJECT nonzero/duplicate W clear");
                xu_clear_w_seen[a]=1;
                xu_clear_w_count=xu_clear_w_count+1;
              end
              12'h018: begin
                if ((^`ACCEL.x_addr_reg)===1'bx)
                  $fatal(1,"XU_CLEAR_REJECT unknown X destination");
                a=`ACCEL.x_addr_reg;
                if (`ACCEL.cmd_wdata!==32'b0 || xu_clear_x_seen[a])
                  $fatal(1,"XU_CLEAR_REJECT nonzero/duplicate X clear");
                xu_clear_x_seen[a]=1;
                xu_clear_x_count=xu_clear_x_count+1;
              end
              12'h048,12'h04c,12'h02c,12'h030: begin
                if (`ACCEL.cmd_wdata!==32'b0)
                  $fatal(1,"XU_CLEAR_REJECT nonzero bias clear");
                if (`ACCEL.cmd_addr[11:0]==12'h048 ||
                    `ACCEL.cmd_addr[11:0]==12'h04c) begin
                  if ((^`ACCEL.cache_addr_reg)===1'bx)
                    $fatal(1,"XU_CLEAR_REJECT unknown bias destination");
                  a=`ACCEL.cache_addr_reg;
                  old_mask=xu_clear_bias_seen[a];
                end else begin
                  if ((^`ACCEL.bias_index_reg)===1'bx)
                    $fatal(1,"XU_CLEAR_REJECT unknown legacy bias destination");
                  a=`ACCEL.bias_index_reg;
                  old_mask=xu_clear_legacy_seen[a];
                end
                if (`ACCEL.cmd_addr[11:0]==12'h048 ||
                    `ACCEL.cmd_addr[11:0]==12'h02c) begin
                  if (old_mask[3:0]!=0)
                    $fatal(1,"XU_CLEAR_REJECT duplicate bias low clear");
                  new_mask=old_mask|5'b01111;
                end else begin
                  if (old_mask[4])
                    $fatal(1,"XU_CLEAR_REJECT duplicate bias high clear");
                  new_mask=old_mask|5'b10000;
                end
                if (`ACCEL.cmd_addr[11:0]==12'h048 ||
                    `ACCEL.cmd_addr[11:0]==12'h04c) begin
                  xu_clear_bias_seen[a]=new_mask;
                  if (new_mask==5'b11111) xu_clear_bias_count=xu_clear_bias_count+1;
                end else begin
                  xu_clear_legacy_seen[a]=new_mask;
                  if (new_mask==5'b11111) xu_clear_legacy_count=xu_clear_legacy_count+1;
                end
              end
              default: $fatal(1,"XU_CLEAR_REJECT unexpected pretask MMIO write");
            endcase
          end
        end
      end
      payload_phase=xu_clear_complete;
    end
  endtask

  reg xu_payload_phase=0;
  integer xu_request_cycle=-1, xu_accept_cycle=-1, xu_initial_wait=0;
  integer xu_formal_cycles=0, xu_clear_first_cycle=-1, xu_clear_last_cycle=-1;
  reg [31:0] xu_request_addr;

  task xu_observe_clear_window;
    reg source_request, source_accept, clear_write;
    begin
      source_request=cmd_valid && cmd_read && cmd_addr>=BASE && cmd_addr<BASE+'h18800;
      source_accept=source_request && cmd_ready;
      clear_write=!xu_clear_complete && xu_clear_writes<33697 &&
                  `ACCEL.cmd_valid && `ACCEL.cmd_ready && !`ACCEL.cmd_read;
      if (clear_write) begin
        if (xu_clear_first_cycle<0) begin
          xu_clear_first_cycle=cycles;
          $display("XU_TASK_CLEAR_BEGIN task=%0d cycle=%0d tick=%0.0f",xu_global_task,cycles,$realtime*1000000.0);
        end
        xu_clear_last_cycle=cycles;
      end
      xu_observe_candidate();
      // Once per post-reset edge, before any payload observation or SAIF start.
      xu_observe_task_clear(source_request,xu_payload_phase);
      if (clear_write && xu_clear_writes==33697)
        $display("XU_TASK_CLEAR_LAST_WRITE task=%0d cycle=%0d tick=%0.0f writes=33697",xu_global_task,cycles,$realtime*1000000.0);
      if (source_request && xu_request_cycle<0) begin
        if (!xu_clear_complete || xu_saif_started || xu_saif_stopped ||
            xu_w_count!=0 || xu_bias_count!=0 || xu_x_count!=0 || xu_starts!=0)
          $fatal(1,"clear recipe did not begin from verified empty payload state");
        xu_request_cycle=cycles;
        xu_request_addr=cmd_addr;
        xu_saif_started=1;
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
        $toggle_start();
`endif
        $display("XU_SOURCE_REQUEST task=%0d cycle=%0d tick=%0.0f",xu_global_task,cycles,$realtime*1000000.0);
        $display("XU_ACTIVITY_BEGIN task=%0d tick=%0.0f",xu_global_task,$realtime*1000000.0);
        $display("XU_CACHE_INITIAL task=%0d fresh_process=1 cache_enable=0 busy=0 prior_uploads=0 prior_starts=0",xu_global_task);
      end
      if (xu_request_cycle>=0 && xu_accept_cycle<0) begin
        if (!source_request || cmd_addr!==xu_request_addr)
          $fatal(1,"first source request changed before acceptance");
        if (source_accept) begin
          xu_accept_cycle=cycles;
          if (xu_initial_wait!=xu_accept_cycle-xu_request_cycle)
            $fatal(1,"initial source wait count differs");
          $display("XU_SOURCE_ACCEPT task=%0d cycle=%0d tick=%0.0f",xu_global_task,cycles,$realtime*1000000.0);
        end else xu_initial_wait=xu_initial_wait+1;
      end
      if (xu_saif_started && !xu_saif_stopped) xu_formal_cycles=xu_formal_cycles+1;
    end
  endtask

  // Observation only: these counters never drive the SoC or its memory model.
  // A phase includes software and bus gaps between its first and last operation.
  // Load phases end when the final data-write response retires; writeback ends
  // at every group's final Y-write response. Accepted operations start a new
  // phase on that edge, while an ending response changes the following edge.
  localparam PERF_OTHER = 0, PERF_W = 1, PERF_X = 2, PERF_BIAS = 3,
             PERF_COMPUTE = 4, PERF_WRITEBACK = 5;
  integer perf_phase;
  reg perf_active, perf_mmio_end_phase, perf_shared_end_writeback;
  integer perf_cycles, perf_w_load, perf_x_load, perf_bias_load;
  integer perf_compute_wait, perf_writeback, perf_other;
  integer perf_busy, perf_mac_fire, perf_starts, perf_dones;
  integer perf_mmio_reads, perf_mmio_writes, perf_mmio_stall;
  integer perf_shared_reads, perf_shared_writes, perf_shared_stall;
  integer perf_auto_rows, perf_auto_pops, perf_auto_overlap, perf_auto_full;

  task reset_performance;
    begin
      perf_phase=PERF_OTHER;
      perf_active=0; perf_mmio_end_phase=0; perf_shared_end_writeback=0;
      perf_cycles=0; perf_w_load=0; perf_x_load=0; perf_bias_load=0;
      perf_compute_wait=0; perf_writeback=0; perf_other=0;
      perf_busy=0; perf_mac_fire=0; perf_starts=0; perf_dones=0;
      perf_mmio_reads=0; perf_mmio_writes=0; perf_mmio_stall=0;
      perf_shared_reads=0; perf_shared_writes=0; perf_shared_stall=0;
      perf_auto_rows=0; perf_auto_pops=0; perf_auto_overlap=0; perf_auto_full=0;
    end
  endtask

  task observe_performance;
    integer phase_now, phase_next;
    reg shared_accept, shared_retire, mmio_accept, mmio_retire, start_accept;
    reg in_window, row_start_accept;
    begin
      shared_accept=cmd_valid && cmd_ready;
      shared_retire=rsp_valid && rsp_ready;
      mmio_accept=`ACCEL.cmd_valid && `ACCEL.cmd_ready;
      mmio_retire=`ACCEL.rsp_valid && `ACCEL.rsp_ready;
      start_accept=mmio_accept && !`ACCEL.cmd_read &&
                   `ACCEL.cmd_addr[11:0]==12'h008 &&
                   `ACCEL.cmd_wdata[0] && !`ACCEL.busy;
      row_start_accept=`ACCEL.row_start_accept;
      xu_observe_clear_window();
      // Match the existing inclusive first-input/final-Y-response interval.
      in_window=perf_active || (first_cycle<0 && shared_accept && cmd_read &&
                               cmd_addr>=BASE && cmd_addr<BASE+'h18800);
      if (dumpwave==2 && !perf_active && in_window) begin
        $dumpon;
        $display("ACTIVITY_BEGIN layer=%0d time=%0t",layer,$time);
      end
      if (in_window) begin
        if (!perf_active) begin
          $display("PPA_WINDOW_BEGIN layer=%0d cycle=%0d time_ns=%0.12f tick_fs=%0.0f",layer,cycles,$realtime,$realtime*1000000.0);

        end
        perf_active=1;
        phase_now=perf_phase;
        phase_next=perf_phase;
        if ((mmio_retire && perf_mmio_end_phase) ||
            (shared_retire && perf_shared_end_writeback) ||
            (`ACCEL.core_done && (!`ACCEL.row_active || perf_phase==PERF_COMPUTE)))
          phase_next=PERF_OTHER;

        if (mmio_accept && !`ACCEL.cmd_read) begin
          case (`ACCEL.cmd_addr[11:0])
            12'h01c, 12'h020, 12'h024, 12'h054, 12'h058, 12'h05c: begin
              phase_now=PERF_W; phase_next=PERF_W;
            end
            12'h014, 12'h018, 12'h060, 12'h064, 12'h068: begin
              phase_now=PERF_X; phase_next=PERF_X;
            end
            12'h028, 12'h02c, 12'h030,
            12'h040, 12'h044, 12'h048, 12'h04c: begin
              phase_now=PERF_BIAS; phase_next=PERF_BIAS;
            end
            12'h034: begin
              phase_now=PERF_WRITEBACK; phase_next=PERF_WRITEBACK;
            end
            default: begin end
          endcase
        end
        // The read-only window has no RESULT_INDEX write to start writeback.
        if (mmio_accept && `ACCEL.cmd_read &&
            ((`ACCEL.cmd_addr[11:0]>=12'h080 && `ACCEL.cmd_addr[11:0]<=12'h0bc) ||
             (`ACCEL.cmd_addr[11:0]>=12'h100 && `ACCEL.cmd_addr[11:0]<=12'h13c))) begin
          phase_now=PERF_WRITEBACK; phase_next=PERF_WRITEBACK;
        end
        if (start_accept || row_start_accept) begin
          phase_now=PERF_COMPUTE; phase_next=PERF_COMPUTE;
        end
        if (mmio_accept && `ACCEL.cmd_read && `ACCEL.cmd_addr[11:0]==12'h0c4) begin
          phase_now=PERF_COMPUTE; phase_next=PERF_COMPUTE;
        end
        // Source reads can precede their matching MMIO load operation.
        if (shared_accept && cmd_read) begin
          if (cmd_addr>=BASE+'h08000 && cmd_addr<BASE+'h18000) begin
            phase_now=PERF_W; phase_next=PERF_W;
          end else if (cmd_addr>=BASE && cmd_addr<BASE+'h06300) begin
            phase_now=PERF_X; phase_next=PERF_X;
          end else if (cmd_addr>=BASE+'h18000 && cmd_addr<BASE+'h18800) begin
            phase_now=PERF_BIAS; phase_next=PERF_BIAS;
          end
        end
        perf_phase=phase_next;
        perf_cycles=perf_cycles+1;
        case (phase_now)
          PERF_W: perf_w_load=perf_w_load+1;
          PERF_X: perf_x_load=perf_x_load+1;
          PERF_BIAS: perf_bias_load=perf_bias_load+1;
          PERF_COMPUTE: perf_compute_wait=perf_compute_wait+1;
          PERF_WRITEBACK: perf_writeback=perf_writeback+1;
          default: perf_other=perf_other+1;
        endcase
        if (`ACCEL.manual_busy || `ACCEL.row_running ||
            (`ACCEL.row_active && `ACCEL.compute_start)) perf_busy=perf_busy+1;
        if (row_start_accept) perf_auto_rows=perf_auto_rows+1;
        if (`ACCEL.row_pop) perf_auto_pops=perf_auto_pops+1;
        if (`ACCEL.row_running && phase_now==PERF_WRITEBACK)
          perf_auto_overlap=perf_auto_overlap+1;
        if (`ACCEL.row_active && `ACCEL.row_count==2 && !`ACCEL.row_running)
          perf_auto_full=perf_auto_full+1;
        // All eight PEs share this enable: one fire means eight signed16 MACs.
        if (`ACCEL.u_linear_compute_core.core.engine.peArray.io_enable)
          perf_mac_fire=perf_mac_fire+1;
        if (start_accept || (`ACCEL.row_active && `ACCEL.compute_start))
          perf_starts=perf_starts+1;
        if (`ACCEL.core_done) perf_dones=perf_dones+1;
        if (mmio_accept) begin
          if (`ACCEL.cmd_read) perf_mmio_reads=perf_mmio_reads+1;
          else perf_mmio_writes=perf_mmio_writes+1;
        end
        if (shared_accept) begin
          if (cmd_read) perf_shared_reads=perf_shared_reads+1;
          else perf_shared_writes=perf_shared_writes+1;
        end
        // A stall is a cycle with either blocked channel, counted once.
        if ((`ACCEL.cmd_valid && !`ACCEL.cmd_ready) ||
            (`ACCEL.rsp_valid && !`ACCEL.rsp_ready))
          perf_mmio_stall=perf_mmio_stall+1;
        if ((cmd_valid && !cmd_ready) || (rsp_valid && !rsp_ready))
          perf_shared_stall=perf_shared_stall+1;
        if (shared_retire && final_write_pending) begin
          $display("PPA_WINDOW_END layer=%0d cycle=%0d time_ns=%0.12f tick_fs=%0.0f",layer,cycles,$realtime,$realtime*1000000.0);
          if (xu_request_cycle<0 || xu_accept_cycle<xu_request_cycle ||
              xu_formal_cycles!=cycles-xu_request_cycle+1 ||
              xu_formal_cycles!=perf_cycles+xu_initial_wait ||
              xu_w_count!=16384 || xu_bias_count!=256 || xu_x_count!=6336 ||
              xu_rows!=99 || xu_starts!=3168 || xu_dones!=3168 || xu_pops!=3168 ||
              xu_w_pairs!=8192 || xu_x_pairs!=3168 || xu_result_words!=0 ||
              xu_w_cursor_setups!=1 || xu_x_cursor_setups!=99 || xu_cache_mode_writes!=2 ||
              xu_result_response_pending ||
              `ACCEL.row_active || `ACCEL.row_running || `ACCEL.row_count!=0 ||
              `ACCEL.row_produced!=32 || `ACCEL.row_retired!=32 || `ACCEL.stream_pending ||
              !xu_saif_started || xu_saif_stopped)
            $fatal(1,"XU_CANDIDATE_REJECT incomplete actual task coverage/window/FIFO drain");
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
          $toggle_stop();
`endif
          xu_saif_stopped=1;
          $display("XU_ACTIVITY_END task=%0d tick=%0.0f",xu_global_task,$realtime*1000000.0);
          $display("XU_TASK_WINDOW task=%0d request_cycle=%0d accept_cycle=%0d end_cycle=%0d initial_wait_cycles=%0d legacy_inclusive_cycles=%0d formal_inclusive_cycles=%0d formal_elapsed_cycles=%0d",xu_global_task,xu_request_cycle,xu_accept_cycle,cycles,xu_initial_wait,perf_cycles,xu_formal_cycles,xu_formal_cycles-1);
          $display("XU_CANDIDATE_UPLOAD_PASS task=%0d w_commits=16384 bias=256 x_commits=6336 rows=99 starts=3168 dones=3168 pops_retired=3168 w_pack32=8192 x_pack32=3168 fifo_empty=1 checked_data=1",xu_global_task);
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
          $toggle_report("task.saif",1.0e-15,"tb_xu_soc_ppa.dut");
`endif
          perf_active=0;
          if (dumpwave==2) begin
            $display("ACTIVITY_END layer=%0d time=%0t",layer,$time);
            $dumpoff;
          end
        end
      end

      // Retiring metadata belongs to the old response even when the next
      // command is accepted on the same edge. Each endpoint has one slot.
      if (mmio_retire) perf_mmio_end_phase=0;
      if (mmio_accept)
        perf_mmio_end_phase=!`ACCEL.cmd_read &&
          ((`ACCEL.cmd_addr[11:0]==12'h024 &&
            `ACCEL.w_bank_reg==7 && `ACCEL.w_addr_reg==2047) ||
           (`ACCEL.cmd_addr[11:0]==12'h018 && `ACCEL.x_addr_reg==63) ||
           (`ACCEL.cmd_addr[11:0]==12'h058 && `ACCEL.w_cursor==16383) ||
           (`ACCEL.cmd_addr[11:0]==12'h064 && `ACCEL.x_cursor==63) ||
           (`ACCEL.cmd_addr[11:0]==12'h05c && `ACCEL.w_cursor==16382) ||
           (`ACCEL.cmd_addr[11:0]==12'h068 && `ACCEL.x_cursor==62) ||
           (`ACCEL.cmd_addr[11:0]==12'h030 && `ACCEL.bias_index_reg==7) ||
           (`ACCEL.cmd_addr[11:0]==12'h040 && `ACCEL.cmd_wdata[0]));
      if (shared_retire) perf_shared_end_writeback=0;
      if (shared_accept)
        perf_shared_end_writeback=!cmd_read && cmd_addr>=BASE+YOFF &&
          cmd_addr<BASE+YOFF+50688*4 && cmd_addr[5:0]==6'h3c;
    end
  endtask

  task report_performance;
    begin
      if (perf_cycles!=last_cycle-first_cycle+1 ||
          perf_w_load+perf_x_load+perf_bias_load+perf_compute_wait+
          perf_writeback+perf_other!=perf_cycles)
        $fatal(1,"performance interval or phase sum mismatch");
      if (perf_auto_rows!=0) begin
        if (perf_auto_rows!=99 || perf_auto_pops!=3168 || `ACCEL.row_active ||
            `ACCEL.row_retired!=32 || `ACCEL.row_produced!=32 || `ACCEL.row_count!=0 ||
            perf_auto_overlap==0)
          $fatal(1,"autonomous row/POP retirement or overlap contract mismatch");
        $display("AUTO_TASK layer=%0d rows=%0d pops_retired=%0d compute_writeback_overlap=%0d fifo_full_wait=%0d",
          layer,perf_auto_rows,perf_auto_pops,perf_auto_overlap,perf_auto_full);
      end
      $display("PERF_TASK layer=%0d cycles=%0d w_load=%0d x_load=%0d bias_load=%0d compute_wait=%0d writeback=%0d other=%0d busy=%0d mac_fire=%0d mmio_reads=%0d mmio_writes=%0d shared_reads=%0d shared_writes=%0d shared_stall=%0d mmio_stall=%0d starts=%0d dones=%0d",
        layer,perf_cycles,perf_w_load,perf_x_load,perf_bias_load,
        perf_compute_wait,perf_writeback,perf_other,perf_busy,perf_mac_fire,
        perf_mmio_reads,perf_mmio_writes,perf_shared_reads,perf_shared_writes,
        perf_shared_stall,perf_mmio_stall,perf_starts,perf_dones);
    end
  endtask

  xu_soc_ppa_top dut (
    .hfextclk(clk), .lfextclk(lfclk), .io_pads_aon_erst_n_i_ival(rst_n),
    .io_pads_jtag_TCK_i_ival(1'b0), .io_pads_jtag_TMS_i_ival(1'b0),
    .io_pads_jtag_TDI_i_ival(1'b0), .io_pads_gpioA_i_ival(32'b0),
    .io_pads_gpioB_i_ival(32'b0), .io_pads_qspi0_dq_0_i_ival(1'b0),
    .io_pads_qspi0_dq_1_i_ival(1'b0), .io_pads_qspi0_dq_2_i_ival(1'b0),
    .io_pads_qspi0_dq_3_i_ival(1'b0), .io_pads_bootrom_n_i_ival(1'b0),
    .io_pads_dbgmode0_n_i_ival(1'b1), .io_pads_dbgmode1_n_i_ival(1'b1),
    .io_pads_dbgmode2_n_i_ival(1'b1), .io_pads_aon_pmu_dwakeup_n_i_ival(1'b1),
    .hfxoscen(), .lfxoscen(), .io_pads_jtag_TDO_o_oval(), .io_pads_jtag_TDO_o_oe(),
    .io_pads_gpioA_o_oval(), .io_pads_gpioA_o_oe(), .io_pads_gpioB_o_oval(), .io_pads_gpioB_o_oe(),
    .io_pads_qspi0_sck_o_oval(), .io_pads_qspi0_cs_0_o_oval(),
    .io_pads_qspi0_dq_0_o_oval(), .io_pads_qspi0_dq_0_o_oe(),
    .io_pads_qspi0_dq_1_o_oval(), .io_pads_qspi0_dq_1_o_oe(),
    .io_pads_qspi0_dq_2_o_oval(), .io_pads_qspi0_dq_2_o_oe(),
    .io_pads_qspi0_dq_3_o_oval(), .io_pads_qspi0_dq_3_o_oe(),
    .io_pads_aon_pmu_padrst_o_oval(), .io_pads_aon_pmu_vddpaden_o_oval()
  );

// Non-synthesizable preload: no force, no changes to live bus timing.
function automatic [63:0] xu_pack_vendor_row;
  input [15:0] a0,a1,a2,a3;
  integer b;
  begin
    for (b=0;b<16;b=b+1)
      xu_pack_vendor_row[4*b +: 4]={a3[b],a2[b],a1[b],a0[b]};
  end
endfunction
task xu_preload_itcm;
  integer row;
  begin
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[0].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[0+4*row+0][0 +: 16],xu_program_words[0+4*row+1][0 +: 16],xu_program_words[0+4*row+2][0 +: 16],xu_program_words[0+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[0].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[0+4*row+0][16 +: 16],xu_program_words[0+4*row+1][16 +: 16],xu_program_words[0+4*row+2][16 +: 16],xu_program_words[0+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[0].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[0+4*row+0][32 +: 16],xu_program_words[0+4*row+1][32 +: 16],xu_program_words[0+4*row+2][32 +: 16],xu_program_words[0+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[0].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[0+4*row+0][48 +: 16],xu_program_words[0+4*row+1][48 +: 16],xu_program_words[0+4*row+2][48 +: 16],xu_program_words[0+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[1].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[1024+4*row+0][0 +: 16],xu_program_words[1024+4*row+1][0 +: 16],xu_program_words[1024+4*row+2][0 +: 16],xu_program_words[1024+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[1].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[1024+4*row+0][16 +: 16],xu_program_words[1024+4*row+1][16 +: 16],xu_program_words[1024+4*row+2][16 +: 16],xu_program_words[1024+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[1].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[1024+4*row+0][32 +: 16],xu_program_words[1024+4*row+1][32 +: 16],xu_program_words[1024+4*row+2][32 +: 16],xu_program_words[1024+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[1].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[1024+4*row+0][48 +: 16],xu_program_words[1024+4*row+1][48 +: 16],xu_program_words[1024+4*row+2][48 +: 16],xu_program_words[1024+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[2].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[2048+4*row+0][0 +: 16],xu_program_words[2048+4*row+1][0 +: 16],xu_program_words[2048+4*row+2][0 +: 16],xu_program_words[2048+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[2].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[2048+4*row+0][16 +: 16],xu_program_words[2048+4*row+1][16 +: 16],xu_program_words[2048+4*row+2][16 +: 16],xu_program_words[2048+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[2].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[2048+4*row+0][32 +: 16],xu_program_words[2048+4*row+1][32 +: 16],xu_program_words[2048+4*row+2][32 +: 16],xu_program_words[2048+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[2].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[2048+4*row+0][48 +: 16],xu_program_words[2048+4*row+1][48 +: 16],xu_program_words[2048+4*row+2][48 +: 16],xu_program_words[2048+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[3].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[3072+4*row+0][0 +: 16],xu_program_words[3072+4*row+1][0 +: 16],xu_program_words[3072+4*row+2][0 +: 16],xu_program_words[3072+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[3].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[3072+4*row+0][16 +: 16],xu_program_words[3072+4*row+1][16 +: 16],xu_program_words[3072+4*row+2][16 +: 16],xu_program_words[3072+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[3].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[3072+4*row+0][32 +: 16],xu_program_words[3072+4*row+1][32 +: 16],xu_program_words[3072+4*row+2][32 +: 16],xu_program_words[3072+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[3].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[3072+4*row+0][48 +: 16],xu_program_words[3072+4*row+1][48 +: 16],xu_program_words[3072+4*row+2][48 +: 16],xu_program_words[3072+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[4].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[4096+4*row+0][0 +: 16],xu_program_words[4096+4*row+1][0 +: 16],xu_program_words[4096+4*row+2][0 +: 16],xu_program_words[4096+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[4].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[4096+4*row+0][16 +: 16],xu_program_words[4096+4*row+1][16 +: 16],xu_program_words[4096+4*row+2][16 +: 16],xu_program_words[4096+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[4].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[4096+4*row+0][32 +: 16],xu_program_words[4096+4*row+1][32 +: 16],xu_program_words[4096+4*row+2][32 +: 16],xu_program_words[4096+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[4].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[4096+4*row+0][48 +: 16],xu_program_words[4096+4*row+1][48 +: 16],xu_program_words[4096+4*row+2][48 +: 16],xu_program_words[4096+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[5].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[5120+4*row+0][0 +: 16],xu_program_words[5120+4*row+1][0 +: 16],xu_program_words[5120+4*row+2][0 +: 16],xu_program_words[5120+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[5].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[5120+4*row+0][16 +: 16],xu_program_words[5120+4*row+1][16 +: 16],xu_program_words[5120+4*row+2][16 +: 16],xu_program_words[5120+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[5].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[5120+4*row+0][32 +: 16],xu_program_words[5120+4*row+1][32 +: 16],xu_program_words[5120+4*row+2][32 +: 16],xu_program_words[5120+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[5].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[5120+4*row+0][48 +: 16],xu_program_words[5120+4*row+1][48 +: 16],xu_program_words[5120+4*row+2][48 +: 16],xu_program_words[5120+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[6].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[6144+4*row+0][0 +: 16],xu_program_words[6144+4*row+1][0 +: 16],xu_program_words[6144+4*row+2][0 +: 16],xu_program_words[6144+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[6].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[6144+4*row+0][16 +: 16],xu_program_words[6144+4*row+1][16 +: 16],xu_program_words[6144+4*row+2][16 +: 16],xu_program_words[6144+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[6].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[6144+4*row+0][32 +: 16],xu_program_words[6144+4*row+1][32 +: 16],xu_program_words[6144+4*row+2][32 +: 16],xu_program_words[6144+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[6].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[6144+4*row+0][48 +: 16],xu_program_words[6144+4*row+1][48 +: 16],xu_program_words[6144+4*row+2][48 +: 16],xu_program_words[6144+4*row+3][48 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[7].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[7168+4*row+0][0 +: 16],xu_program_words[7168+4*row+1][0 +: 16],xu_program_words[7168+4*row+2][0 +: 16],xu_program_words[7168+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[7].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[7168+4*row+0][16 +: 16],xu_program_words[7168+4*row+1][16 +: 16],xu_program_words[7168+4*row+2][16 +: 16],xu_program_words[7168+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[7].width_lane[2].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[7168+4*row+0][32 +: 16],xu_program_words[7168+4*row+1][32 +: 16],xu_program_words[7168+4*row+2][32 +: 16],xu_program_words[7168+4*row+3][32 +: 16]);
    for (row=0;row<256;row=row+1)
      `ITCM.macro_storage.depth_bank[7].width_lane[3].macro.mem[row]=
        xu_pack_vendor_row(xu_program_words[7168+4*row+0][48 +: 16],xu_program_words[7168+4*row+1][48 +: 16],xu_program_words[7168+4*row+2][48 +: 16],xu_program_words[7168+4*row+3][48 +: 16]);
  end
endtask
task xu_preload_shared;
  integer row;
  begin
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[0].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[0+4*row+0][0 +: 16],ram[0+4*row+1][0 +: 16],ram[0+4*row+2][0 +: 16],ram[0+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[0].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[0+4*row+0][16 +: 16],ram[0+4*row+1][16 +: 16],ram[0+4*row+2][16 +: 16],ram[0+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[1].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[1024+4*row+0][0 +: 16],ram[1024+4*row+1][0 +: 16],ram[1024+4*row+2][0 +: 16],ram[1024+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[1].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[1024+4*row+0][16 +: 16],ram[1024+4*row+1][16 +: 16],ram[1024+4*row+2][16 +: 16],ram[1024+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[2].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[2048+4*row+0][0 +: 16],ram[2048+4*row+1][0 +: 16],ram[2048+4*row+2][0 +: 16],ram[2048+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[2].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[2048+4*row+0][16 +: 16],ram[2048+4*row+1][16 +: 16],ram[2048+4*row+2][16 +: 16],ram[2048+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[3].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[3072+4*row+0][0 +: 16],ram[3072+4*row+1][0 +: 16],ram[3072+4*row+2][0 +: 16],ram[3072+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[3].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[3072+4*row+0][16 +: 16],ram[3072+4*row+1][16 +: 16],ram[3072+4*row+2][16 +: 16],ram[3072+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[4].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[4096+4*row+0][0 +: 16],ram[4096+4*row+1][0 +: 16],ram[4096+4*row+2][0 +: 16],ram[4096+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[4].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[4096+4*row+0][16 +: 16],ram[4096+4*row+1][16 +: 16],ram[4096+4*row+2][16 +: 16],ram[4096+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[5].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[5120+4*row+0][0 +: 16],ram[5120+4*row+1][0 +: 16],ram[5120+4*row+2][0 +: 16],ram[5120+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[5].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[5120+4*row+0][16 +: 16],ram[5120+4*row+1][16 +: 16],ram[5120+4*row+2][16 +: 16],ram[5120+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[6].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[6144+4*row+0][0 +: 16],ram[6144+4*row+1][0 +: 16],ram[6144+4*row+2][0 +: 16],ram[6144+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[6].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[6144+4*row+0][16 +: 16],ram[6144+4*row+1][16 +: 16],ram[6144+4*row+2][16 +: 16],ram[6144+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[7].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[7168+4*row+0][0 +: 16],ram[7168+4*row+1][0 +: 16],ram[7168+4*row+2][0 +: 16],ram[7168+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[7].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[7168+4*row+0][16 +: 16],ram[7168+4*row+1][16 +: 16],ram[7168+4*row+2][16 +: 16],ram[7168+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[8].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[8192+4*row+0][0 +: 16],ram[8192+4*row+1][0 +: 16],ram[8192+4*row+2][0 +: 16],ram[8192+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[8].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[8192+4*row+0][16 +: 16],ram[8192+4*row+1][16 +: 16],ram[8192+4*row+2][16 +: 16],ram[8192+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[9].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[9216+4*row+0][0 +: 16],ram[9216+4*row+1][0 +: 16],ram[9216+4*row+2][0 +: 16],ram[9216+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[9].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[9216+4*row+0][16 +: 16],ram[9216+4*row+1][16 +: 16],ram[9216+4*row+2][16 +: 16],ram[9216+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[10].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[10240+4*row+0][0 +: 16],ram[10240+4*row+1][0 +: 16],ram[10240+4*row+2][0 +: 16],ram[10240+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[10].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[10240+4*row+0][16 +: 16],ram[10240+4*row+1][16 +: 16],ram[10240+4*row+2][16 +: 16],ram[10240+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[11].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[11264+4*row+0][0 +: 16],ram[11264+4*row+1][0 +: 16],ram[11264+4*row+2][0 +: 16],ram[11264+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[11].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[11264+4*row+0][16 +: 16],ram[11264+4*row+1][16 +: 16],ram[11264+4*row+2][16 +: 16],ram[11264+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[12].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[12288+4*row+0][0 +: 16],ram[12288+4*row+1][0 +: 16],ram[12288+4*row+2][0 +: 16],ram[12288+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[12].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[12288+4*row+0][16 +: 16],ram[12288+4*row+1][16 +: 16],ram[12288+4*row+2][16 +: 16],ram[12288+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[13].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[13312+4*row+0][0 +: 16],ram[13312+4*row+1][0 +: 16],ram[13312+4*row+2][0 +: 16],ram[13312+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[13].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[13312+4*row+0][16 +: 16],ram[13312+4*row+1][16 +: 16],ram[13312+4*row+2][16 +: 16],ram[13312+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[14].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[14336+4*row+0][0 +: 16],ram[14336+4*row+1][0 +: 16],ram[14336+4*row+2][0 +: 16],ram[14336+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[14].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[14336+4*row+0][16 +: 16],ram[14336+4*row+1][16 +: 16],ram[14336+4*row+2][16 +: 16],ram[14336+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[15].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[15360+4*row+0][0 +: 16],ram[15360+4*row+1][0 +: 16],ram[15360+4*row+2][0 +: 16],ram[15360+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[15].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[15360+4*row+0][16 +: 16],ram[15360+4*row+1][16 +: 16],ram[15360+4*row+2][16 +: 16],ram[15360+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[16].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[16384+4*row+0][0 +: 16],ram[16384+4*row+1][0 +: 16],ram[16384+4*row+2][0 +: 16],ram[16384+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[16].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[16384+4*row+0][16 +: 16],ram[16384+4*row+1][16 +: 16],ram[16384+4*row+2][16 +: 16],ram[16384+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[17].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[17408+4*row+0][0 +: 16],ram[17408+4*row+1][0 +: 16],ram[17408+4*row+2][0 +: 16],ram[17408+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[17].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[17408+4*row+0][16 +: 16],ram[17408+4*row+1][16 +: 16],ram[17408+4*row+2][16 +: 16],ram[17408+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[18].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[18432+4*row+0][0 +: 16],ram[18432+4*row+1][0 +: 16],ram[18432+4*row+2][0 +: 16],ram[18432+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[18].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[18432+4*row+0][16 +: 16],ram[18432+4*row+1][16 +: 16],ram[18432+4*row+2][16 +: 16],ram[18432+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[19].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[19456+4*row+0][0 +: 16],ram[19456+4*row+1][0 +: 16],ram[19456+4*row+2][0 +: 16],ram[19456+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[19].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[19456+4*row+0][16 +: 16],ram[19456+4*row+1][16 +: 16],ram[19456+4*row+2][16 +: 16],ram[19456+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[20].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[20480+4*row+0][0 +: 16],ram[20480+4*row+1][0 +: 16],ram[20480+4*row+2][0 +: 16],ram[20480+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[20].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[20480+4*row+0][16 +: 16],ram[20480+4*row+1][16 +: 16],ram[20480+4*row+2][16 +: 16],ram[20480+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[21].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[21504+4*row+0][0 +: 16],ram[21504+4*row+1][0 +: 16],ram[21504+4*row+2][0 +: 16],ram[21504+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[21].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[21504+4*row+0][16 +: 16],ram[21504+4*row+1][16 +: 16],ram[21504+4*row+2][16 +: 16],ram[21504+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[22].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[22528+4*row+0][0 +: 16],ram[22528+4*row+1][0 +: 16],ram[22528+4*row+2][0 +: 16],ram[22528+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[22].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[22528+4*row+0][16 +: 16],ram[22528+4*row+1][16 +: 16],ram[22528+4*row+2][16 +: 16],ram[22528+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[23].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[23552+4*row+0][0 +: 16],ram[23552+4*row+1][0 +: 16],ram[23552+4*row+2][0 +: 16],ram[23552+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[23].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[23552+4*row+0][16 +: 16],ram[23552+4*row+1][16 +: 16],ram[23552+4*row+2][16 +: 16],ram[23552+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[24].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[24576+4*row+0][0 +: 16],ram[24576+4*row+1][0 +: 16],ram[24576+4*row+2][0 +: 16],ram[24576+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[24].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[24576+4*row+0][16 +: 16],ram[24576+4*row+1][16 +: 16],ram[24576+4*row+2][16 +: 16],ram[24576+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[25].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[25600+4*row+0][0 +: 16],ram[25600+4*row+1][0 +: 16],ram[25600+4*row+2][0 +: 16],ram[25600+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[25].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[25600+4*row+0][16 +: 16],ram[25600+4*row+1][16 +: 16],ram[25600+4*row+2][16 +: 16],ram[25600+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[26].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[26624+4*row+0][0 +: 16],ram[26624+4*row+1][0 +: 16],ram[26624+4*row+2][0 +: 16],ram[26624+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[26].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[26624+4*row+0][16 +: 16],ram[26624+4*row+1][16 +: 16],ram[26624+4*row+2][16 +: 16],ram[26624+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[27].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[27648+4*row+0][0 +: 16],ram[27648+4*row+1][0 +: 16],ram[27648+4*row+2][0 +: 16],ram[27648+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[27].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[27648+4*row+0][16 +: 16],ram[27648+4*row+1][16 +: 16],ram[27648+4*row+2][16 +: 16],ram[27648+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[28].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[28672+4*row+0][0 +: 16],ram[28672+4*row+1][0 +: 16],ram[28672+4*row+2][0 +: 16],ram[28672+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[28].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[28672+4*row+0][16 +: 16],ram[28672+4*row+1][16 +: 16],ram[28672+4*row+2][16 +: 16],ram[28672+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[29].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[29696+4*row+0][0 +: 16],ram[29696+4*row+1][0 +: 16],ram[29696+4*row+2][0 +: 16],ram[29696+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[29].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[29696+4*row+0][16 +: 16],ram[29696+4*row+1][16 +: 16],ram[29696+4*row+2][16 +: 16],ram[29696+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[30].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[30720+4*row+0][0 +: 16],ram[30720+4*row+1][0 +: 16],ram[30720+4*row+2][0 +: 16],ram[30720+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[30].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[30720+4*row+0][16 +: 16],ram[30720+4*row+1][16 +: 16],ram[30720+4*row+2][16 +: 16],ram[30720+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[31].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[31744+4*row+0][0 +: 16],ram[31744+4*row+1][0 +: 16],ram[31744+4*row+2][0 +: 16],ram[31744+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[31].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[31744+4*row+0][16 +: 16],ram[31744+4*row+1][16 +: 16],ram[31744+4*row+2][16 +: 16],ram[31744+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[32].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[32768+4*row+0][0 +: 16],ram[32768+4*row+1][0 +: 16],ram[32768+4*row+2][0 +: 16],ram[32768+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[32].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[32768+4*row+0][16 +: 16],ram[32768+4*row+1][16 +: 16],ram[32768+4*row+2][16 +: 16],ram[32768+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[33].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[33792+4*row+0][0 +: 16],ram[33792+4*row+1][0 +: 16],ram[33792+4*row+2][0 +: 16],ram[33792+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[33].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[33792+4*row+0][16 +: 16],ram[33792+4*row+1][16 +: 16],ram[33792+4*row+2][16 +: 16],ram[33792+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[34].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[34816+4*row+0][0 +: 16],ram[34816+4*row+1][0 +: 16],ram[34816+4*row+2][0 +: 16],ram[34816+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[34].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[34816+4*row+0][16 +: 16],ram[34816+4*row+1][16 +: 16],ram[34816+4*row+2][16 +: 16],ram[34816+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[35].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[35840+4*row+0][0 +: 16],ram[35840+4*row+1][0 +: 16],ram[35840+4*row+2][0 +: 16],ram[35840+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[35].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[35840+4*row+0][16 +: 16],ram[35840+4*row+1][16 +: 16],ram[35840+4*row+2][16 +: 16],ram[35840+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[36].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[36864+4*row+0][0 +: 16],ram[36864+4*row+1][0 +: 16],ram[36864+4*row+2][0 +: 16],ram[36864+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[36].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[36864+4*row+0][16 +: 16],ram[36864+4*row+1][16 +: 16],ram[36864+4*row+2][16 +: 16],ram[36864+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[37].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[37888+4*row+0][0 +: 16],ram[37888+4*row+1][0 +: 16],ram[37888+4*row+2][0 +: 16],ram[37888+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[37].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[37888+4*row+0][16 +: 16],ram[37888+4*row+1][16 +: 16],ram[37888+4*row+2][16 +: 16],ram[37888+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[38].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[38912+4*row+0][0 +: 16],ram[38912+4*row+1][0 +: 16],ram[38912+4*row+2][0 +: 16],ram[38912+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[38].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[38912+4*row+0][16 +: 16],ram[38912+4*row+1][16 +: 16],ram[38912+4*row+2][16 +: 16],ram[38912+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[39].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[39936+4*row+0][0 +: 16],ram[39936+4*row+1][0 +: 16],ram[39936+4*row+2][0 +: 16],ram[39936+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[39].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[39936+4*row+0][16 +: 16],ram[39936+4*row+1][16 +: 16],ram[39936+4*row+2][16 +: 16],ram[39936+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[40].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[40960+4*row+0][0 +: 16],ram[40960+4*row+1][0 +: 16],ram[40960+4*row+2][0 +: 16],ram[40960+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[40].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[40960+4*row+0][16 +: 16],ram[40960+4*row+1][16 +: 16],ram[40960+4*row+2][16 +: 16],ram[40960+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[41].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[41984+4*row+0][0 +: 16],ram[41984+4*row+1][0 +: 16],ram[41984+4*row+2][0 +: 16],ram[41984+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[41].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[41984+4*row+0][16 +: 16],ram[41984+4*row+1][16 +: 16],ram[41984+4*row+2][16 +: 16],ram[41984+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[42].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[43008+4*row+0][0 +: 16],ram[43008+4*row+1][0 +: 16],ram[43008+4*row+2][0 +: 16],ram[43008+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[42].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[43008+4*row+0][16 +: 16],ram[43008+4*row+1][16 +: 16],ram[43008+4*row+2][16 +: 16],ram[43008+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[43].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[44032+4*row+0][0 +: 16],ram[44032+4*row+1][0 +: 16],ram[44032+4*row+2][0 +: 16],ram[44032+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[43].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[44032+4*row+0][16 +: 16],ram[44032+4*row+1][16 +: 16],ram[44032+4*row+2][16 +: 16],ram[44032+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[44].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[45056+4*row+0][0 +: 16],ram[45056+4*row+1][0 +: 16],ram[45056+4*row+2][0 +: 16],ram[45056+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[44].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[45056+4*row+0][16 +: 16],ram[45056+4*row+1][16 +: 16],ram[45056+4*row+2][16 +: 16],ram[45056+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[45].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[46080+4*row+0][0 +: 16],ram[46080+4*row+1][0 +: 16],ram[46080+4*row+2][0 +: 16],ram[46080+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[45].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[46080+4*row+0][16 +: 16],ram[46080+4*row+1][16 +: 16],ram[46080+4*row+2][16 +: 16],ram[46080+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[46].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[47104+4*row+0][0 +: 16],ram[47104+4*row+1][0 +: 16],ram[47104+4*row+2][0 +: 16],ram[47104+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[46].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[47104+4*row+0][16 +: 16],ram[47104+4*row+1][16 +: 16],ram[47104+4*row+2][16 +: 16],ram[47104+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[47].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[48128+4*row+0][0 +: 16],ram[48128+4*row+1][0 +: 16],ram[48128+4*row+2][0 +: 16],ram[48128+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[47].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[48128+4*row+0][16 +: 16],ram[48128+4*row+1][16 +: 16],ram[48128+4*row+2][16 +: 16],ram[48128+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[48].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[49152+4*row+0][0 +: 16],ram[49152+4*row+1][0 +: 16],ram[49152+4*row+2][0 +: 16],ram[49152+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[48].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[49152+4*row+0][16 +: 16],ram[49152+4*row+1][16 +: 16],ram[49152+4*row+2][16 +: 16],ram[49152+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[49].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[50176+4*row+0][0 +: 16],ram[50176+4*row+1][0 +: 16],ram[50176+4*row+2][0 +: 16],ram[50176+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[49].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[50176+4*row+0][16 +: 16],ram[50176+4*row+1][16 +: 16],ram[50176+4*row+2][16 +: 16],ram[50176+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[50].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[51200+4*row+0][0 +: 16],ram[51200+4*row+1][0 +: 16],ram[51200+4*row+2][0 +: 16],ram[51200+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[50].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[51200+4*row+0][16 +: 16],ram[51200+4*row+1][16 +: 16],ram[51200+4*row+2][16 +: 16],ram[51200+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[51].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[52224+4*row+0][0 +: 16],ram[52224+4*row+1][0 +: 16],ram[52224+4*row+2][0 +: 16],ram[52224+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[51].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[52224+4*row+0][16 +: 16],ram[52224+4*row+1][16 +: 16],ram[52224+4*row+2][16 +: 16],ram[52224+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[52].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[53248+4*row+0][0 +: 16],ram[53248+4*row+1][0 +: 16],ram[53248+4*row+2][0 +: 16],ram[53248+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[52].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[53248+4*row+0][16 +: 16],ram[53248+4*row+1][16 +: 16],ram[53248+4*row+2][16 +: 16],ram[53248+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[53].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[54272+4*row+0][0 +: 16],ram[54272+4*row+1][0 +: 16],ram[54272+4*row+2][0 +: 16],ram[54272+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[53].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[54272+4*row+0][16 +: 16],ram[54272+4*row+1][16 +: 16],ram[54272+4*row+2][16 +: 16],ram[54272+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[54].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[55296+4*row+0][0 +: 16],ram[55296+4*row+1][0 +: 16],ram[55296+4*row+2][0 +: 16],ram[55296+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[54].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[55296+4*row+0][16 +: 16],ram[55296+4*row+1][16 +: 16],ram[55296+4*row+2][16 +: 16],ram[55296+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[55].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[56320+4*row+0][0 +: 16],ram[56320+4*row+1][0 +: 16],ram[56320+4*row+2][0 +: 16],ram[56320+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[55].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[56320+4*row+0][16 +: 16],ram[56320+4*row+1][16 +: 16],ram[56320+4*row+2][16 +: 16],ram[56320+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[56].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[57344+4*row+0][0 +: 16],ram[57344+4*row+1][0 +: 16],ram[57344+4*row+2][0 +: 16],ram[57344+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[56].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[57344+4*row+0][16 +: 16],ram[57344+4*row+1][16 +: 16],ram[57344+4*row+2][16 +: 16],ram[57344+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[57].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[58368+4*row+0][0 +: 16],ram[58368+4*row+1][0 +: 16],ram[58368+4*row+2][0 +: 16],ram[58368+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[57].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[58368+4*row+0][16 +: 16],ram[58368+4*row+1][16 +: 16],ram[58368+4*row+2][16 +: 16],ram[58368+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[58].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[59392+4*row+0][0 +: 16],ram[59392+4*row+1][0 +: 16],ram[59392+4*row+2][0 +: 16],ram[59392+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[58].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[59392+4*row+0][16 +: 16],ram[59392+4*row+1][16 +: 16],ram[59392+4*row+2][16 +: 16],ram[59392+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[59].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[60416+4*row+0][0 +: 16],ram[60416+4*row+1][0 +: 16],ram[60416+4*row+2][0 +: 16],ram[60416+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[59].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[60416+4*row+0][16 +: 16],ram[60416+4*row+1][16 +: 16],ram[60416+4*row+2][16 +: 16],ram[60416+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[60].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[61440+4*row+0][0 +: 16],ram[61440+4*row+1][0 +: 16],ram[61440+4*row+2][0 +: 16],ram[61440+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[60].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[61440+4*row+0][16 +: 16],ram[61440+4*row+1][16 +: 16],ram[61440+4*row+2][16 +: 16],ram[61440+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[61].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[62464+4*row+0][0 +: 16],ram[62464+4*row+1][0 +: 16],ram[62464+4*row+2][0 +: 16],ram[62464+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[61].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[62464+4*row+0][16 +: 16],ram[62464+4*row+1][16 +: 16],ram[62464+4*row+2][16 +: 16],ram[62464+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[62].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[63488+4*row+0][0 +: 16],ram[63488+4*row+1][0 +: 16],ram[63488+4*row+2][0 +: 16],ram[63488+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[62].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[63488+4*row+0][16 +: 16],ram[63488+4*row+1][16 +: 16],ram[63488+4*row+2][16 +: 16],ram[63488+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[63].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[64512+4*row+0][0 +: 16],ram[64512+4*row+1][0 +: 16],ram[64512+4*row+2][0 +: 16],ram[64512+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[63].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[64512+4*row+0][16 +: 16],ram[64512+4*row+1][16 +: 16],ram[64512+4*row+2][16 +: 16],ram[64512+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[64].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[65536+4*row+0][0 +: 16],ram[65536+4*row+1][0 +: 16],ram[65536+4*row+2][0 +: 16],ram[65536+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[64].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[65536+4*row+0][16 +: 16],ram[65536+4*row+1][16 +: 16],ram[65536+4*row+2][16 +: 16],ram[65536+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[65].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[66560+4*row+0][0 +: 16],ram[66560+4*row+1][0 +: 16],ram[66560+4*row+2][0 +: 16],ram[66560+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[65].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[66560+4*row+0][16 +: 16],ram[66560+4*row+1][16 +: 16],ram[66560+4*row+2][16 +: 16],ram[66560+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[66].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[67584+4*row+0][0 +: 16],ram[67584+4*row+1][0 +: 16],ram[67584+4*row+2][0 +: 16],ram[67584+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[66].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[67584+4*row+0][16 +: 16],ram[67584+4*row+1][16 +: 16],ram[67584+4*row+2][16 +: 16],ram[67584+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[67].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[68608+4*row+0][0 +: 16],ram[68608+4*row+1][0 +: 16],ram[68608+4*row+2][0 +: 16],ram[68608+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[67].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[68608+4*row+0][16 +: 16],ram[68608+4*row+1][16 +: 16],ram[68608+4*row+2][16 +: 16],ram[68608+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[68].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[69632+4*row+0][0 +: 16],ram[69632+4*row+1][0 +: 16],ram[69632+4*row+2][0 +: 16],ram[69632+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[68].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[69632+4*row+0][16 +: 16],ram[69632+4*row+1][16 +: 16],ram[69632+4*row+2][16 +: 16],ram[69632+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[69].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[70656+4*row+0][0 +: 16],ram[70656+4*row+1][0 +: 16],ram[70656+4*row+2][0 +: 16],ram[70656+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[69].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[70656+4*row+0][16 +: 16],ram[70656+4*row+1][16 +: 16],ram[70656+4*row+2][16 +: 16],ram[70656+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[70].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[71680+4*row+0][0 +: 16],ram[71680+4*row+1][0 +: 16],ram[71680+4*row+2][0 +: 16],ram[71680+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[70].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[71680+4*row+0][16 +: 16],ram[71680+4*row+1][16 +: 16],ram[71680+4*row+2][16 +: 16],ram[71680+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[71].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[72704+4*row+0][0 +: 16],ram[72704+4*row+1][0 +: 16],ram[72704+4*row+2][0 +: 16],ram[72704+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[71].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[72704+4*row+0][16 +: 16],ram[72704+4*row+1][16 +: 16],ram[72704+4*row+2][16 +: 16],ram[72704+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[72].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[73728+4*row+0][0 +: 16],ram[73728+4*row+1][0 +: 16],ram[73728+4*row+2][0 +: 16],ram[73728+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[72].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[73728+4*row+0][16 +: 16],ram[73728+4*row+1][16 +: 16],ram[73728+4*row+2][16 +: 16],ram[73728+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[73].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[74752+4*row+0][0 +: 16],ram[74752+4*row+1][0 +: 16],ram[74752+4*row+2][0 +: 16],ram[74752+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[73].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[74752+4*row+0][16 +: 16],ram[74752+4*row+1][16 +: 16],ram[74752+4*row+2][16 +: 16],ram[74752+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[74].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[75776+4*row+0][0 +: 16],ram[75776+4*row+1][0 +: 16],ram[75776+4*row+2][0 +: 16],ram[75776+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[74].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[75776+4*row+0][16 +: 16],ram[75776+4*row+1][16 +: 16],ram[75776+4*row+2][16 +: 16],ram[75776+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[75].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[76800+4*row+0][0 +: 16],ram[76800+4*row+1][0 +: 16],ram[76800+4*row+2][0 +: 16],ram[76800+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[75].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[76800+4*row+0][16 +: 16],ram[76800+4*row+1][16 +: 16],ram[76800+4*row+2][16 +: 16],ram[76800+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[76].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[77824+4*row+0][0 +: 16],ram[77824+4*row+1][0 +: 16],ram[77824+4*row+2][0 +: 16],ram[77824+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[76].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[77824+4*row+0][16 +: 16],ram[77824+4*row+1][16 +: 16],ram[77824+4*row+2][16 +: 16],ram[77824+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[77].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[78848+4*row+0][0 +: 16],ram[78848+4*row+1][0 +: 16],ram[78848+4*row+2][0 +: 16],ram[78848+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[77].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[78848+4*row+0][16 +: 16],ram[78848+4*row+1][16 +: 16],ram[78848+4*row+2][16 +: 16],ram[78848+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[78].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[79872+4*row+0][0 +: 16],ram[79872+4*row+1][0 +: 16],ram[79872+4*row+2][0 +: 16],ram[79872+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[78].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[79872+4*row+0][16 +: 16],ram[79872+4*row+1][16 +: 16],ram[79872+4*row+2][16 +: 16],ram[79872+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[79].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[80896+4*row+0][0 +: 16],ram[80896+4*row+1][0 +: 16],ram[80896+4*row+2][0 +: 16],ram[80896+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[79].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[80896+4*row+0][16 +: 16],ram[80896+4*row+1][16 +: 16],ram[80896+4*row+2][16 +: 16],ram[80896+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[80].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[81920+4*row+0][0 +: 16],ram[81920+4*row+1][0 +: 16],ram[81920+4*row+2][0 +: 16],ram[81920+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[80].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[81920+4*row+0][16 +: 16],ram[81920+4*row+1][16 +: 16],ram[81920+4*row+2][16 +: 16],ram[81920+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[81].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[82944+4*row+0][0 +: 16],ram[82944+4*row+1][0 +: 16],ram[82944+4*row+2][0 +: 16],ram[82944+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[81].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[82944+4*row+0][16 +: 16],ram[82944+4*row+1][16 +: 16],ram[82944+4*row+2][16 +: 16],ram[82944+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[82].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[83968+4*row+0][0 +: 16],ram[83968+4*row+1][0 +: 16],ram[83968+4*row+2][0 +: 16],ram[83968+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[82].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[83968+4*row+0][16 +: 16],ram[83968+4*row+1][16 +: 16],ram[83968+4*row+2][16 +: 16],ram[83968+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[83].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[84992+4*row+0][0 +: 16],ram[84992+4*row+1][0 +: 16],ram[84992+4*row+2][0 +: 16],ram[84992+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[83].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[84992+4*row+0][16 +: 16],ram[84992+4*row+1][16 +: 16],ram[84992+4*row+2][16 +: 16],ram[84992+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[84].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[86016+4*row+0][0 +: 16],ram[86016+4*row+1][0 +: 16],ram[86016+4*row+2][0 +: 16],ram[86016+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[84].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[86016+4*row+0][16 +: 16],ram[86016+4*row+1][16 +: 16],ram[86016+4*row+2][16 +: 16],ram[86016+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[85].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[87040+4*row+0][0 +: 16],ram[87040+4*row+1][0 +: 16],ram[87040+4*row+2][0 +: 16],ram[87040+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[85].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[87040+4*row+0][16 +: 16],ram[87040+4*row+1][16 +: 16],ram[87040+4*row+2][16 +: 16],ram[87040+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[86].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[88064+4*row+0][0 +: 16],ram[88064+4*row+1][0 +: 16],ram[88064+4*row+2][0 +: 16],ram[88064+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[86].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[88064+4*row+0][16 +: 16],ram[88064+4*row+1][16 +: 16],ram[88064+4*row+2][16 +: 16],ram[88064+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[87].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[89088+4*row+0][0 +: 16],ram[89088+4*row+1][0 +: 16],ram[89088+4*row+2][0 +: 16],ram[89088+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[87].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[89088+4*row+0][16 +: 16],ram[89088+4*row+1][16 +: 16],ram[89088+4*row+2][16 +: 16],ram[89088+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[88].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[90112+4*row+0][0 +: 16],ram[90112+4*row+1][0 +: 16],ram[90112+4*row+2][0 +: 16],ram[90112+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[88].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[90112+4*row+0][16 +: 16],ram[90112+4*row+1][16 +: 16],ram[90112+4*row+2][16 +: 16],ram[90112+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[89].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[91136+4*row+0][0 +: 16],ram[91136+4*row+1][0 +: 16],ram[91136+4*row+2][0 +: 16],ram[91136+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[89].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[91136+4*row+0][16 +: 16],ram[91136+4*row+1][16 +: 16],ram[91136+4*row+2][16 +: 16],ram[91136+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[90].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[92160+4*row+0][0 +: 16],ram[92160+4*row+1][0 +: 16],ram[92160+4*row+2][0 +: 16],ram[92160+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[90].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[92160+4*row+0][16 +: 16],ram[92160+4*row+1][16 +: 16],ram[92160+4*row+2][16 +: 16],ram[92160+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[91].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[93184+4*row+0][0 +: 16],ram[93184+4*row+1][0 +: 16],ram[93184+4*row+2][0 +: 16],ram[93184+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[91].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[93184+4*row+0][16 +: 16],ram[93184+4*row+1][16 +: 16],ram[93184+4*row+2][16 +: 16],ram[93184+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[92].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[94208+4*row+0][0 +: 16],ram[94208+4*row+1][0 +: 16],ram[94208+4*row+2][0 +: 16],ram[94208+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[92].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[94208+4*row+0][16 +: 16],ram[94208+4*row+1][16 +: 16],ram[94208+4*row+2][16 +: 16],ram[94208+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[93].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[95232+4*row+0][0 +: 16],ram[95232+4*row+1][0 +: 16],ram[95232+4*row+2][0 +: 16],ram[95232+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[93].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[95232+4*row+0][16 +: 16],ram[95232+4*row+1][16 +: 16],ram[95232+4*row+2][16 +: 16],ram[95232+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[94].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[96256+4*row+0][0 +: 16],ram[96256+4*row+1][0 +: 16],ram[96256+4*row+2][0 +: 16],ram[96256+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[94].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[96256+4*row+0][16 +: 16],ram[96256+4*row+1][16 +: 16],ram[96256+4*row+2][16 +: 16],ram[96256+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[95].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[97280+4*row+0][0 +: 16],ram[97280+4*row+1][0 +: 16],ram[97280+4*row+2][0 +: 16],ram[97280+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[95].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[97280+4*row+0][16 +: 16],ram[97280+4*row+1][16 +: 16],ram[97280+4*row+2][16 +: 16],ram[97280+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[96].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[98304+4*row+0][0 +: 16],ram[98304+4*row+1][0 +: 16],ram[98304+4*row+2][0 +: 16],ram[98304+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[96].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[98304+4*row+0][16 +: 16],ram[98304+4*row+1][16 +: 16],ram[98304+4*row+2][16 +: 16],ram[98304+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[97].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[99328+4*row+0][0 +: 16],ram[99328+4*row+1][0 +: 16],ram[99328+4*row+2][0 +: 16],ram[99328+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[97].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[99328+4*row+0][16 +: 16],ram[99328+4*row+1][16 +: 16],ram[99328+4*row+2][16 +: 16],ram[99328+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[98].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[100352+4*row+0][0 +: 16],ram[100352+4*row+1][0 +: 16],ram[100352+4*row+2][0 +: 16],ram[100352+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[98].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[100352+4*row+0][16 +: 16],ram[100352+4*row+1][16 +: 16],ram[100352+4*row+2][16 +: 16],ram[100352+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[99].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[101376+4*row+0][0 +: 16],ram[101376+4*row+1][0 +: 16],ram[101376+4*row+2][0 +: 16],ram[101376+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[99].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[101376+4*row+0][16 +: 16],ram[101376+4*row+1][16 +: 16],ram[101376+4*row+2][16 +: 16],ram[101376+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[100].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[102400+4*row+0][0 +: 16],ram[102400+4*row+1][0 +: 16],ram[102400+4*row+2][0 +: 16],ram[102400+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[100].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[102400+4*row+0][16 +: 16],ram[102400+4*row+1][16 +: 16],ram[102400+4*row+2][16 +: 16],ram[102400+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[101].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[103424+4*row+0][0 +: 16],ram[103424+4*row+1][0 +: 16],ram[103424+4*row+2][0 +: 16],ram[103424+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[101].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[103424+4*row+0][16 +: 16],ram[103424+4*row+1][16 +: 16],ram[103424+4*row+2][16 +: 16],ram[103424+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[102].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[104448+4*row+0][0 +: 16],ram[104448+4*row+1][0 +: 16],ram[104448+4*row+2][0 +: 16],ram[104448+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[102].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[104448+4*row+0][16 +: 16],ram[104448+4*row+1][16 +: 16],ram[104448+4*row+2][16 +: 16],ram[104448+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[103].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[105472+4*row+0][0 +: 16],ram[105472+4*row+1][0 +: 16],ram[105472+4*row+2][0 +: 16],ram[105472+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[103].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[105472+4*row+0][16 +: 16],ram[105472+4*row+1][16 +: 16],ram[105472+4*row+2][16 +: 16],ram[105472+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[104].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[106496+4*row+0][0 +: 16],ram[106496+4*row+1][0 +: 16],ram[106496+4*row+2][0 +: 16],ram[106496+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[104].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[106496+4*row+0][16 +: 16],ram[106496+4*row+1][16 +: 16],ram[106496+4*row+2][16 +: 16],ram[106496+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[105].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[107520+4*row+0][0 +: 16],ram[107520+4*row+1][0 +: 16],ram[107520+4*row+2][0 +: 16],ram[107520+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[105].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[107520+4*row+0][16 +: 16],ram[107520+4*row+1][16 +: 16],ram[107520+4*row+2][16 +: 16],ram[107520+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[106].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[108544+4*row+0][0 +: 16],ram[108544+4*row+1][0 +: 16],ram[108544+4*row+2][0 +: 16],ram[108544+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[106].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[108544+4*row+0][16 +: 16],ram[108544+4*row+1][16 +: 16],ram[108544+4*row+2][16 +: 16],ram[108544+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[107].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[109568+4*row+0][0 +: 16],ram[109568+4*row+1][0 +: 16],ram[109568+4*row+2][0 +: 16],ram[109568+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[107].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[109568+4*row+0][16 +: 16],ram[109568+4*row+1][16 +: 16],ram[109568+4*row+2][16 +: 16],ram[109568+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[108].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[110592+4*row+0][0 +: 16],ram[110592+4*row+1][0 +: 16],ram[110592+4*row+2][0 +: 16],ram[110592+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[108].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[110592+4*row+0][16 +: 16],ram[110592+4*row+1][16 +: 16],ram[110592+4*row+2][16 +: 16],ram[110592+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[109].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[111616+4*row+0][0 +: 16],ram[111616+4*row+1][0 +: 16],ram[111616+4*row+2][0 +: 16],ram[111616+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[109].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[111616+4*row+0][16 +: 16],ram[111616+4*row+1][16 +: 16],ram[111616+4*row+2][16 +: 16],ram[111616+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[110].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[112640+4*row+0][0 +: 16],ram[112640+4*row+1][0 +: 16],ram[112640+4*row+2][0 +: 16],ram[112640+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[110].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[112640+4*row+0][16 +: 16],ram[112640+4*row+1][16 +: 16],ram[112640+4*row+2][16 +: 16],ram[112640+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[111].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[113664+4*row+0][0 +: 16],ram[113664+4*row+1][0 +: 16],ram[113664+4*row+2][0 +: 16],ram[113664+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[111].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[113664+4*row+0][16 +: 16],ram[113664+4*row+1][16 +: 16],ram[113664+4*row+2][16 +: 16],ram[113664+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[112].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[114688+4*row+0][0 +: 16],ram[114688+4*row+1][0 +: 16],ram[114688+4*row+2][0 +: 16],ram[114688+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[112].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[114688+4*row+0][16 +: 16],ram[114688+4*row+1][16 +: 16],ram[114688+4*row+2][16 +: 16],ram[114688+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[113].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[115712+4*row+0][0 +: 16],ram[115712+4*row+1][0 +: 16],ram[115712+4*row+2][0 +: 16],ram[115712+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[113].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[115712+4*row+0][16 +: 16],ram[115712+4*row+1][16 +: 16],ram[115712+4*row+2][16 +: 16],ram[115712+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[114].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[116736+4*row+0][0 +: 16],ram[116736+4*row+1][0 +: 16],ram[116736+4*row+2][0 +: 16],ram[116736+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[114].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[116736+4*row+0][16 +: 16],ram[116736+4*row+1][16 +: 16],ram[116736+4*row+2][16 +: 16],ram[116736+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[115].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[117760+4*row+0][0 +: 16],ram[117760+4*row+1][0 +: 16],ram[117760+4*row+2][0 +: 16],ram[117760+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[115].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[117760+4*row+0][16 +: 16],ram[117760+4*row+1][16 +: 16],ram[117760+4*row+2][16 +: 16],ram[117760+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[116].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[118784+4*row+0][0 +: 16],ram[118784+4*row+1][0 +: 16],ram[118784+4*row+2][0 +: 16],ram[118784+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[116].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[118784+4*row+0][16 +: 16],ram[118784+4*row+1][16 +: 16],ram[118784+4*row+2][16 +: 16],ram[118784+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[117].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[119808+4*row+0][0 +: 16],ram[119808+4*row+1][0 +: 16],ram[119808+4*row+2][0 +: 16],ram[119808+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[117].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[119808+4*row+0][16 +: 16],ram[119808+4*row+1][16 +: 16],ram[119808+4*row+2][16 +: 16],ram[119808+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[118].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[120832+4*row+0][0 +: 16],ram[120832+4*row+1][0 +: 16],ram[120832+4*row+2][0 +: 16],ram[120832+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[118].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[120832+4*row+0][16 +: 16],ram[120832+4*row+1][16 +: 16],ram[120832+4*row+2][16 +: 16],ram[120832+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[119].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[121856+4*row+0][0 +: 16],ram[121856+4*row+1][0 +: 16],ram[121856+4*row+2][0 +: 16],ram[121856+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[119].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[121856+4*row+0][16 +: 16],ram[121856+4*row+1][16 +: 16],ram[121856+4*row+2][16 +: 16],ram[121856+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[120].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[122880+4*row+0][0 +: 16],ram[122880+4*row+1][0 +: 16],ram[122880+4*row+2][0 +: 16],ram[122880+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[120].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[122880+4*row+0][16 +: 16],ram[122880+4*row+1][16 +: 16],ram[122880+4*row+2][16 +: 16],ram[122880+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[121].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[123904+4*row+0][0 +: 16],ram[123904+4*row+1][0 +: 16],ram[123904+4*row+2][0 +: 16],ram[123904+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[121].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[123904+4*row+0][16 +: 16],ram[123904+4*row+1][16 +: 16],ram[123904+4*row+2][16 +: 16],ram[123904+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[122].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[124928+4*row+0][0 +: 16],ram[124928+4*row+1][0 +: 16],ram[124928+4*row+2][0 +: 16],ram[124928+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[122].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[124928+4*row+0][16 +: 16],ram[124928+4*row+1][16 +: 16],ram[124928+4*row+2][16 +: 16],ram[124928+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[123].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[125952+4*row+0][0 +: 16],ram[125952+4*row+1][0 +: 16],ram[125952+4*row+2][0 +: 16],ram[125952+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[123].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[125952+4*row+0][16 +: 16],ram[125952+4*row+1][16 +: 16],ram[125952+4*row+2][16 +: 16],ram[125952+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[124].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[126976+4*row+0][0 +: 16],ram[126976+4*row+1][0 +: 16],ram[126976+4*row+2][0 +: 16],ram[126976+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[124].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[126976+4*row+0][16 +: 16],ram[126976+4*row+1][16 +: 16],ram[126976+4*row+2][16 +: 16],ram[126976+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[125].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[128000+4*row+0][0 +: 16],ram[128000+4*row+1][0 +: 16],ram[128000+4*row+2][0 +: 16],ram[128000+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[125].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[128000+4*row+0][16 +: 16],ram[128000+4*row+1][16 +: 16],ram[128000+4*row+2][16 +: 16],ram[128000+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[126].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[129024+4*row+0][0 +: 16],ram[129024+4*row+1][0 +: 16],ram[129024+4*row+2][0 +: 16],ram[129024+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[126].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[129024+4*row+0][16 +: 16],ram[129024+4*row+1][16 +: 16],ram[129024+4*row+2][16 +: 16],ram[129024+4*row+3][16 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[127].width_lane[0].macro.mem[row]=
        xu_pack_vendor_row(ram[130048+4*row+0][0 +: 16],ram[130048+4*row+1][0 +: 16],ram[130048+4*row+2][0 +: 16],ram[130048+4*row+3][0 +: 16]);
    for (row=0;row<256;row=row+1)
      dut.u_shared.storage.macro_storage.depth_bank[127].width_lane[1].macro.mem[row]=
        xu_pack_vendor_row(ram[130048+4*row+0][16 +: 16],ram[130048+4*row+1][16 +: 16],ram[130048+4*row+2][16 +: 16],ram[130048+4*row+3][16 +: 16]);
  end
endtask

  task load_layer(input integer index);
    string directory;
    integer i;
    begin
      directory = $sformatf("%s/layer_%02d/", vectors, index);
      $readmemh({directory,"x.mem"}, x);
      $readmemh({directory,"w.mem"}, w);
      $readmemh({directory,"bias.mem"}, bias);
      $readmemh({directory,"y.mem"}, golden);
      for (i=0; i<6336; i=i+1) ram[i] = {16'b0,x[i]};
      for (i=0; i<16384; i=i+1) ram['h8000/4+i] = {16'b0,w[i]};
      for (i=0; i<256; i=i+1) begin
        ram['h18000/4+2*i] = bias[i][31:0];
        ram['h18000/4+2*i+1] = {{24{bias[i][39]}},bias[i][39:32]};
      end
      // Poison output memory on every layer; no result survives as evidence.
      for (i=0; i<50688; i=i+1) ram[YOFF/4+i] = 32'hdeadbeef;
      xu_preload_shared();
      $display("XU_CACHE_RELOAD task=%0d done_before_begin=1 scope=shared_fixture tick=%0.0f",xu_global_task,$realtime*1000000.0);
      writes = 0; first_cycle = -1; final_write_pending = 0;
      reset_performance();
    end
  endtask

  initial begin : initialize
    integer i;
    if (!$value$plusargs("TESTCASE=%s",testcase) ||
        !$value$plusargs("VECTORS=%s",vectors) ||
        !$value$plusargs("TASKS=%d",tasks)) $fatal(1,"missing plusargs");
    if (tasks < 1 || tasks > 12) $fatal(1,"invalid task count");
    if (!$value$plusargs("MAX_CYCLES=%d",max_cycles)) max_cycles=200000000;
    if (!$value$plusargs("XU_GLOBAL_TASK=%d",xu_global_task) ||
        xu_global_task<0 || xu_global_task>11 || tasks!=1)
      $fatal(1,"candidate requires valid global task and TASKS=1 fresh process");
    for (i=0;i<256;i=i+1) begin xu_bias_seen[i]=0; xu_clear_bias_committed[i]=0; end
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
    $set_gate_level_monitoring("rtl_on");
    $set_toggle_region(tb_xu_soc_ppa.dut);
`endif
    #1; // Finish vendor initialization before the first HF edge.
    for (i=0; i<65536; i=i+1) program_bytes[i]=0;
    $readmemh({testcase,".verilog"},program_bytes);
    for (i=0; i<8192; i=i+1)
      xu_program_words[i] = {program_bytes[8*i+7],program_bytes[8*i+6],
        program_bytes[8*i+5],program_bytes[8*i+4],program_bytes[8*i+3],
        program_bytes[8*i+2],program_bytes[8*i+1],program_bytes[8*i]};
    xu_preload_itcm();
    ram[HOST/4]=tasks;
    load_layer(0);
    if ($value$plusargs("DUMPWAVE=%d",dumpwave) && dumpwave) begin
      $dumpfile("tb_accel_soc.vcd");
      if (dumpwave==2) begin
        $dumpvars(0,dut);
        $dumpoff;
      end else $dumpvars(0,tb_xu_soc_ppa);
    end
    #(200-$realtime);
    if (xu_reset_edges!=30) $fatal(1,"nominal150 reset HF edge count=%0d",xu_reset_edges);
    rst_n=1;
    $display("PPA_CLOCK mode=nominal150 hf_nominal_period_ns=6.666666666666667 precision_fs=1 reset_hf_edges=%0d",xu_reset_edges);
  end

  always @(posedge clk) begin : memory_and_scoreboard
    integer offset, word_index;
    reg [63:0] expected;
    cycles <= cycles+1;
    if (cycles>0 && cycles%1000000==0) begin
      $display("PPA_PROGRESS cycles=%0d layer=%0d writes=%0d completed=%0d",cycles,layer,writes,completed);
      $fflush();
    end
    if (cycles > max_cycles) $fatal(1,"SoC timeout layer=%0d writes=%0d",layer,writes);
    if (rst_n) begin
      observe_performance();
      // A response must correspond to exactly one unretired shared-memory command.
      if (rsp_valid && outstanding != 1) $fatal(1,"orphan shared response");
      if (rsp_valid && rsp_ready) outstanding=outstanding-1;
      if (cmd_valid && cmd_ready) outstanding=outstanding+1;
      if (outstanding<0 || outstanding>1) $fatal(1,"shared outstanding count");
      if (rsp_valid && rsp_ready && final_write_pending) begin
        last_cycle=cycles;
        final_write_pending=0;
      end
      if (rsp_valid && rsp_err) $fatal(1,"shared endpoint error");
      if (cmd_ready !== ((!rsp_valid || rsp_ready) && (cycles % 7 != 0)))
        $fatal(1,"shared endpoint backpressure phase differs cycle=%0d",cycles);
      if (cmd_ready) begin
        if (cmd_valid) begin
          if (cmd_addr < BASE || cmd_addr >= BASE+'h80000 || cmd_addr[1:0]!=0)
            $fatal(1,"invalid shared address %h",cmd_addr);
          offset=cmd_addr-BASE;
          word_index=offset/4;
          if (cmd_read) begin
            if (offset < 'h18800 && first_cycle<0) first_cycle=cycles;
          end else begin
            if (cmd_wmask != 4'hf) $fatal(1,"partial shared write");
            if (offset>=YOFF && offset<YOFF+50688*4) begin
              if (offset != YOFF+writes*4) $fatal(1,"write order %h index %0d",offset,writes);
              expected={{16{golden[writes/2][47]}},golden[writes/2]};
              if (cmd_wdata !== (writes%2 ? expected[63:32] : expected[31:0]))
                $fatal(1,"result mismatch layer=%0d word=%0d got=%h expected=%h",
                  layer,writes,cmd_wdata,writes%2 ? expected[63:32] : expected[31:0]);
              ram[word_index]=cmd_wdata;
              writes=writes+1;
              if (writes==50688) final_write_pending=1;
            end else if (offset==HOST+8) firmware_cycles=cmd_wdata;
            else if (offset==HOST+4) begin
              if (cmd_wdata!=layer+1 || writes!=50688 || final_write_pending || first_cycle<0)
                $fatal(1,"premature or incorrect writeback ACK");
              $display("TASK_PASS layer=%0d outputs=25344 writes=50688 cycles=%0d firmware_cycles=%0d",
                layer,last_cycle-first_cycle+1,firmware_cycles);
              report_performance();
              $fflush();
              completed=completed+1;
              layer=layer+1;
              if (layer<tasks) load_layer(layer);
            end else $fatal(1,"unexpected shared write %h",cmd_addr);
          end
        end
      end
      if (`EXU.u_e203_exu_commit.alu_cmt_i_valid && `EXU.u_e203_exu_commit.alu_cmt_i_pc==32'h80000086) begin
        if (`EXU.u_e203_exu_regfile.rf_r[3]!=1 || completed!=tasks)
          $fatal(1,"firmware failure gp=%0d completed=%0d",`EXU.u_e203_exu_regfile.rf_r[3],completed);
        if (!xu_saif_stopped || xu_lf_static_checks<=0) $fatal(1,"missing candidate SAIF end/LF checks");
        $display("XU_LF_CLOCK_STATIC_PASS nominal_hz=32768 checked_edges=%0d max_phase_error_fs=1",xu_lf_static_checks);
        $display("XU_CLOCK_STATIC_PASS checked_hf_edges=%0d",xu_static_checks);
        $display("SOC_PASS tasks=%0d outputs=%0d writes=%0d",completed,completed*25344,completed*50688);
        $finish;
      end
    end
  end
endmodule
