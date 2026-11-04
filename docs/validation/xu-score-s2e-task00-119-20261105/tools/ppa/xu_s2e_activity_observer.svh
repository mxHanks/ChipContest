  // xu passive S2e observer. Reads actual core inputs at their sampling edge.
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
  reg xu_result_response_packed=0;
  reg [15:0] xu_result_response_mask=0;
  integer xu_result_legacy_reads=0, xu_result_packed_reads=0, xu_result_logical_words=0;
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
    reg w_commit, x_commit, bias_commit, paired_read;
    reg [15:0] result_mask;
    reg [31:0] expected_result;
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
        if (`ACCEL.rsp_ready) begin
          xu_result_words=xu_result_words|xu_result_response_mask;
          if (xu_result_response_packed) begin
            xu_result_packed_reads=xu_result_packed_reads+1;
            xu_result_logical_words=xu_result_logical_words+2;
          end else begin
            xu_result_legacy_reads=xu_result_legacy_reads+1;
            xu_result_logical_words=xu_result_logical_words+1;
          end
          xu_result_response_pending=0;
        end
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
          `ACCEL.cmd_addr[11:0]>=12'h100 && `ACCEL.cmd_addr[11:0]<=12'h14f) begin
        paired_read=`ACCEL.cmd_addr[11:0]>=12'h140;
        lane=paired_read ? 2*`ACCEL.cmd_addr[3:2] : `ACCEL.cmd_addr[5:3];
        bit_index=2*lane;
        if (`ACCEL.cmd_addr[1:0]!=0 || (!paired_read && `ACCEL.cmd_addr[2]) ||
            `ACCEL.row_pop)
          $fatal(1,"XU_S2E_REJECT unaligned/non-LO legacy read or result during POP retirement");
        result_mask=paired_read ? (16'h000a<<bit_index) : (16'h0001<<bit_index);
        if (!xu_saif_started || xu_saif_stopped || !`ACCEL.row_valid ||
            `ACCEL.row_group!==xu_pops%32 || (xu_result_words & result_mask)!=0 ||
            `ACCEL.row_result[lane]!==golden[(xu_rows-1)*256+(xu_pops%32)*8+lane] ||
            (paired_read && `ACCEL.row_result[lane+1]!==golden[(xu_rows-1)*256+(xu_pops%32)*8+lane+1]))
          $fatal(1,"XU_CANDIDATE_REJECT incomplete/duplicate/incorrect owned FIFO result");
        if (xu_result_response_pending)
          $fatal(1,"XU_CANDIDATE_REJECT result response overlap without retirement");
        xu_result_response_pending=1;
        xu_result_response_packed=paired_read;
        xu_result_response_mask=result_mask;
        xu_result_response_word=paired_read ? {`ACCEL.row_result[lane+1][47:32],`ACCEL.row_result[lane][47:32]} :
                                            `ACCEL.row_result[lane][31:0];
      end
      if (`ACCEL.row_pop) begin
        if (!xu_saif_started || xu_saif_stopped || !`ACCEL.row_active ||
            !`ACCEL.row_valid || `ACCEL.row_group!==xu_pops%32 ||
            xu_result_words!==16'hffff || xu_result_response_pending || xu_pops>=xu_rows*32)
          $fatal(1,"XU_CANDIDATE_REJECT POP before all owned words read / wrong group");
        xu_pops=xu_pops+1; xu_result_words=0;
      end
    end
  endtask
