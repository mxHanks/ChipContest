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
