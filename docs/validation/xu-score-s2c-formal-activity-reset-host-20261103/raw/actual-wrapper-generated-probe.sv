// xu actual S2c wrapper protocol/arithmetic probe; no SoC, vendor SAIF or PPA claim.
`timescale 1ns/1fs
module tb_xu_s2c_task_observer;
  reg clk=0, rst_n=0;
  always #5 clk=~clk;
  reg bus_valid=0,bus_read=0,bus_rsp_ready=0;
  reg [31:0] bus_addr=0,bus_data=0;
  reg [3:0] bus_mask=0;
  wire bus_ready,bus_rsp_valid,bus_rsp_err;
  wire [31:0] bus_rsp_data;
  accel_icb_slave dut(.clk(clk),.rst_n(rst_n),.cmd_valid(bus_valid),.cmd_read(bus_read),
    .cmd_addr(bus_addr),.cmd_wdata(bus_data),.cmd_wmask(bus_mask),.cmd_ready(bus_ready),
    .rsp_valid(bus_rsp_valid),.rsp_ready(bus_rsp_ready),.rsp_err(bus_rsp_err),.rsp_rdata(bus_rsp_data));
  `define ACCEL dut
  localparam BASE=32'ha0000000;
  reg cmd_valid=0,cmd_read=1,cmd_ready=0;
  reg [31:0] cmd_addr=BASE;
  integer cycles=0,mode=0,row,g,k,c,b,a,j,polls;
  reg [15:0] w[0:16383],x[0:6335];
  reg [39:0] bias[0:255];
  reg [47:0] golden[0:25343];
  string golden_path;
  reg [31:0] response;
  reg signed [31:0] product;
  reg signed [63:0] total;
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
  integer xu_accel_reset_clock_edges=0, xu_accel_startup_observer_edges=0;
  reg xu_accel_reset_seen=0, xu_accel_observation_ready=0;
  real xu_accel_reset_first_tick=-1.0, xu_accel_reset_last_tick=-1.0;

  // The SoC accelerator uses bus_rst_n, released by its own synchronous
  // reset chain; TB rst_n is not that pin. In particular the synchronous
  // Chisel FIFO may remain X while its actual clock has not yet run in reset.
  // Count actual reset-sampling edges without changing any reset or DUT pin.
  always @(posedge `ACCEL.clk) begin
    if (`ACCEL.rst_n===1'b0) begin
      if (xu_accel_observation_ready || xu_saif_started)
        $fatal(1,"XU_CANDIDATE_RESET_REJECT accelerator reset reasserted after observation ready");
      if (!xu_accel_reset_seen) xu_accel_reset_first_tick=$realtime*1000000.0;
      xu_accel_reset_seen=1;
      xu_accel_reset_clock_edges=xu_accel_reset_clock_edges+1;
      xu_accel_reset_last_tick=$realtime*1000000.0;
    end else if (`ACCEL.rst_n!==1'b1 && xu_accel_reset_seen)
      $fatal(1,"XU_CANDIDATE_RESET_REJECT accelerator reset unknown after known assertion");
  end

  task xu_observe_candidate_reset_window;
    reg source_request;
    begin
      source_request=cmd_valid && cmd_read && cmd_addr>=BASE && cmd_addr<BASE+'h18800;
      if (`ACCEL.rst_n===1'b1) begin
        if (!xu_accel_reset_seen || xu_accel_reset_clock_edges<=0)
          $fatal(1,"XU_CANDIDATE_RESET_REJECT no actual accelerator clock sampled asserted reset");
        if (!xu_accel_observation_ready) begin
          xu_accel_observation_ready=1;
          // This still checks every original known-commit/FIFO/clear assertion.
          xu_observe_clear_window();
          $display("XU_CANDIDATE_RESET_READY task=%0d actual_reset_clock_edges=%0d startup_observer_edges=%0d first_reset_tick=%0.0f last_reset_tick=%0.0f first_ready_cycle=%0d first_ready_tick=%0.0f actual_rst_n=1 checked_empty_fifo=1",xu_global_task,xu_accel_reset_clock_edges,xu_accel_startup_observer_edges,xu_accel_reset_first_tick,xu_accel_reset_last_tick,cycles,$realtime*1000000.0);
        end else xu_observe_clear_window();
      end else begin
        if (xu_accel_observation_ready || xu_saif_started)
          $fatal(1,"XU_CANDIDATE_RESET_REJECT reset reasserted/unknown after observation ready");
        if (`ACCEL.cmd_valid===1'b1 || source_request===1'b1)
          $fatal(1,"XU_CANDIDATE_RESET_REJECT accelerator/source request before actual reset ready");
        if (`ACCEL.rst_n!==1'b0 && xu_accel_reset_seen)
          $fatal(1,"XU_CANDIDATE_RESET_REJECT reset unknown after known assertion");
        xu_accel_startup_observer_edges=xu_accel_startup_observer_edges+1;
      end
    end
  endtask

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

  always @(posedge clk) if(rst_n) begin
    cycles=cycles+1;
    xu_observe_candidate_reset_window();
  end
  // Faults corrupt actual core inputs; the observer must see sampling-edge data.
  initial begin
    wait(rst_n);
    if(mode==2) begin
      wait(dut.stream_pending && dut.stream_second && dut.stream_is_w);
      @(negedge clk); force dut.u_linear_compute_core.io_wLoadData=16'hbad0;
    end
    if(mode==3) begin
      wait(dut.x_load_wen);
      @(negedge clk); force dut.u_linear_compute_core.io_xLoadData=16'h0001;
    end
    if(mode==9) begin
      wait(bus_valid && bus_read && bus_addr[11:0]=='h100);
      @(negedge clk); force dut.rsp_rdata=32'hbad0cafe;
    end
  end
  task automatic transfer(input bit reading,input [11:0] offset,input [31:0] data,
                          input [3:0] mask,output [31:0] result);
    integer timeout;
    reg [31:0] held;
    begin
      @(negedge clk); bus_valid=1; bus_read=reading; bus_addr={20'h10042,offset};
      bus_data=data; bus_mask=mask; bus_rsp_ready=0;
      @(posedge clk); while(!bus_ready) @(posedge clk);
      #1;
      @(negedge clk); bus_valid=0;
      timeout=0;
      while(!bus_rsp_valid) begin
        @(posedge clk); #1; timeout=timeout+1;
        if(timeout>8) $fatal(1,"driver response timeout");
      end
      if(bus_rsp_err) $fatal(1,"driver accelerator error");
      held=bus_rsp_data;
      repeat(2) begin
        @(posedge clk); #1;
        if(!bus_rsp_valid || bus_rsp_data!==held) $fatal(1,"driver response unstable");
      end
      result=held;
      @(negedge clk); bus_rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); bus_rsp_ready=0;
    end
  endtask
  task automatic put(input [11:0] offset,input [31:0] data);
    reg [31:0] ignored;
    begin transfer(0,offset,data,15,ignored); end
  endtask
  initial begin
    if(!$value$plusargs("MODE=%d",mode)) mode=0;
    xu_global_task=7;
    for(a=0;a<16384;a=a+1) w[a]=(a%17==0)?16'h8000:((a%19==0)?16'h7fff:a*7-1000);
    for(a=0;a<6336;a=a+1) x[a]=(a%13==0)?16'h8000:((a%11==0)?16'h7fff:a*3-64);
    for(c=0;c<256;c=c+1) begin
      bias[c]=c%2 ? 40'h7fffffffff-c : 40'h8000000000+c;
      xu_bias_seen[c]=0; xu_clear_bias_committed[c]=0;
    end
    if(!$value$plusargs("GOLDEN=%s",golden_path)) $fatal(1,"explicit independent golden required");
    $readmemh(golden_path,golden);
    repeat(4) @(negedge clk); rst_n=1;
    put('h040,0);
    for(b=0;b<8;b=b+1) begin
      put('h01c,b);
      for(a=0;a<2048;a=a+1) begin put('h020,a); put('h024,0); end
    end
    for(a=0;a<256;a=a+1) begin put('h044,a); put('h048,0); put('h04c,0); end
    for(a=0;a<8;a=a+1) begin put('h028,a); put('h02c,0); put('h030,0); end
    for(a=0;a<64;a=a+1) begin put('h014,a); put('h018,0); end
    // Match the real clear wrapper + frozen S2c firmware's capability probes.
    transfer(1,'h000,0,0,response); if(response!==32'hacce2030) $fatal(1,"ID");
    transfer(1,'h00c,0,0,response); if(response!==0) $fatal(1,"STATUS");
    transfer(1,'h050,0,0,response); if(response!==32'h58550003) $fatal(1,"CAP");
    transfer(1,'h078,0,0,response); if(response!==32'h58410001) $fatal(1,"AUTO_CAP");
    transfer(1,'h070,0,0,response); if(response!==32'h58530003) $fatal(1,"STREAM_CAP");
    transfer(1,'h074,0,0,response); if(response!==32'h58500003) $fatal(1,"PACKED_CAP");
    if(mode==7) transfer(1,'h0cc,0,0,response);
    if(mode==1) put('h054,0);
    @(negedge clk); cmd_valid=1;
    repeat(3) @(negedge clk);
    if(mode==4) cmd_addr=BASE+4;
    if(mode==5) cmd_valid=0;
    @(negedge clk); cmd_ready=1;
    @(negedge clk); cmd_valid=0;
    if(xu_initial_wait!=4) $fatal(1,"driver initial source wait differs");
    put('h054,0);
    if(mode==8) put('h054,0);
    for(a=0;a<16384;a=a+2) put('h05c,{w[a+1],w[a]});
    put('h040,0);
    for(c=0;c<256;c=c+1) begin
      put('h044,c); put('h048,bias[c][31:0]); put('h04c,{24'b0,bias[c][39:32]});
    end
    put('h040,1);
    for(row=0;row<99;row=row+1) begin
      put('h060,0);
      for(k=0;k<64;k=k+2) put('h068,{x[row*64+k+1],x[row*64+k]});
      put('hc0,1);
      for(g=0;g<32;g=g+1) begin
        response=0; polls=0;
        while(!response[1]) begin
          transfer(1,'hc4,0,0,response); polls=polls+1;
          if(polls>30) $fatal(1,"driver FIFO timeout");
        end
        for(j=0;j<16;j=j+1) if(!(mode==6 && row==0 && g==0 && j==15)) begin
          transfer(1,'h100+4*j,0,0,response);
          if(response!==(j%2 ? {16'b0,golden[row*256+g*8+j/2][47:32]} :
                                    golden[row*256+g*8+j/2][31:0]))
            $fatal(1,"driver result mismatch");
        end
        put('hc8,1);
      end
    end
    if(xu_clear_writes!=33697 || xu_clear_w_commits!=16384 || xu_clear_x_commits!=64 ||
       xu_clear_bias_commits!=256 || xu_w_count!=16384 || xu_bias_count!=256 || xu_x_count!=6336 ||
       xu_rows!=99 || xu_starts!=3168 || xu_dones!=3168 || xu_pops!=3168 ||
       xu_w_pairs!=8192 || xu_x_pairs!=3168 || xu_result_words!=0 ||
       xu_w_cursor_setups!=1 || xu_x_cursor_setups!=99 || xu_cache_mode_writes!=2 ||
       xu_result_response_pending ||
       dut.row_active || dut.row_count || dut.row_running || dut.row_produced!=32 || dut.row_retired!=32)
      $fatal(1,"driver final coverage differs");
    $display("XU_S2C_OBSERVER_RTL_PASS clear=33697 w_actual=16384 x_actual=6336 bias_actual=256 rows=99 groups=3168 retired_pops=3168 words=50688 wait=4 signed16_40_48=1");
    $finish;
  end
endmodule
