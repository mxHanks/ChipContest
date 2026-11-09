
  // Public PACK32 passive physical-clear proof. No force, DUT assignment, or task-data preloading.
  integer s3_clear_ticks=0, s3_clear_first=-1, s3_clear_last_response=-1;
  integer s3_clear_writes=0, s3_clear_commands=0, s3_clear_responses=0;
  integer s3_clear_w_count=0, s3_clear_x_count=0, s3_clear_legacy_count=0;
  integer s3_clear_bias_count=0, s3_clear_disable_count=0, s3_clear_reads=0;
  integer s3_clear_w_addr_count=0, s3_clear_x_addr_count=0;
  integer s3_clear_legacy_addr_count=0, s3_clear_bias_addr_count=0;
  integer s3_clear_sram_commands=0, s3_clear_sram_done=0, s3_clear_sram_start=-1;
  integer s3_clear_proof_reads=0, s3_preflight_commands=0, s3_preflight_responses=0;
  integer s3_clear_w_packs=0, s3_clear_x_packs=0, s3_clear_stream_proofs=0;
  reg s3_clear_stream_verified=0;

  reg [16383:0] s3_physical_w_seen=0;
  reg [767:0] s3_physical_bias_seen=0;
  integer s3_physical_w_count=0, s3_physical_bias_count=0;
  task s3_check_physical_w;
    input integer bank, half;
    input [9:0] address;
    input [15:0] data;
    integer flat;
    begin
      if ((^{address,data})===1'bx || data!==0)
        $fatal(1,"S3_CLEAR_REJECT nonzero/unknown physical W write");
      flat=bank*2048+half*1024+address;
      if (s3_physical_w_seen[flat])
        $fatal(1,"S3_CLEAR_REJECT duplicate physical W write");
      if (`ACCEL.u_linear_compute_core.io_wLoadWen!==1'b1 ||
          `ACCEL.u_linear_compute_core.io_wLoadBank!==bank ||
          `ACCEL.u_linear_compute_core.io_wLoadAddr!==half*1024+address ||
          `ACCEL.u_linear_compute_core.io_wLoadData!==data)
        $fatal(1,"S3_CLEAR_REJECT physical W/core mismatch");
      s3_physical_w_seen[flat]=1;
      s3_physical_w_count=s3_physical_w_count+1;
    end
  endtask

  task s3_observe_physical_clear;
    integer p, row, column, bank, address, macros_this_edge;
    begin
      macros_this_edge=0;
      if ((^{`ACCEL.u_linear_compute_core.io_wLoadWen,
             `ACCEL.u_linear_compute_core.io_xLoadWen})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown actual core strobe");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.io_ren!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT compute memory read during clear");
      if (`ACCEL.u_linear_compute_core.io_wLoadWen) begin
        if (!s3_clear_pending || s3_clear_pending_read ||
            s3_clear_response_address!=12'h05c || s3_clear_w_count>=16384 ||
            s3_clear_w_count>=2*s3_clear_w_packs)
          $fatal(1,"S3_CLEAR_REJECT unexpected actual W write");
        p=s3_clear_w_count; row=p/256; column=p%256;
        bank=column%8; address=(column/8)*64+row;
        if (`ACCEL.u_linear_compute_core.io_wLoadBank!==bank ||
            `ACCEL.u_linear_compute_core.io_wLoadAddr!==address ||
            `ACCEL.u_linear_compute_core.io_wLoadData!==0 ||
            s3_clear_w_seen[bank*2048+address])
          $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate/misordered actual W write");
        s3_clear_w_seen[bank*2048+address]=1;
        s3_clear_bank_seen[bank]=1;
        s3_clear_w_count=s3_clear_w_count+1;
      end
      if (`ACCEL.u_linear_compute_core.io_xLoadWen) begin
        address=`ACCEL.u_linear_compute_core.io_xLoadAddr;
        if (!s3_clear_pending || s3_clear_pending_read ||
            s3_clear_response_address!=12'h068 || s3_clear_x_count>=64 ||
            s3_clear_x_count>=2*s3_clear_x_packs ||
            address!=s3_clear_x_count || s3_clear_x_seen[address] ||
            `ACCEL.u_linear_compute_core.io_xLoadData!==0)
          $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate/misordered actual X write");
        s3_clear_x_seen[address]=1;
        s3_clear_x_count=s3_clear_x_count+1;
      end
      if (`ACCEL.u_linear_compute_core.core.xBuffer.io_wen !==
          `ACCEL.u_linear_compute_core.io_xLoadWen ||
          (`ACCEL.u_linear_compute_core.core.xBuffer.io_wen &&
           (`ACCEL.u_linear_compute_core.core.xBuffer.io_waddr !==
            `ACCEL.u_linear_compute_core.io_xLoadAddr ||
            `ACCEL.u_linear_compute_core.core.xBuffer.io_wdata!==0)))
        $fatal(1,"S3_CLEAR_REJECT physical X/core mismatch");

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(0,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(0,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(1,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(1,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(2,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(2,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(3,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(3,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(4,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(4,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(5,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(5,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(6,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(6,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_wmode) begin
        s3_check_physical_w(7,0,`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if ((^{`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_en && `ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_wmode) begin
        s3_check_physical_w(7,1,`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_addr,`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end

      if (macros_this_edge != (`ACCEL.u_linear_compute_core.io_wLoadWen ? 1 : 0))
        $fatal(1,"S3_CLEAR_REJECT physical W strobe cardinality");

      if ((^{`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_en,`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_wmode})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical bias control");
      if (`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_en) begin
        address=`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_addr;
        if (`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_wmode!==1'b1 || `ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_wdata!==0 ||
            s3_clear_sram_commands!=1 || s3_clear_sram_done!=0 ||
            address>=768 || address!=s3_physical_bias_count || s3_physical_bias_seen[address])
          $fatal(1,"S3_CLEAR_REJECT invalid physical bias clear write");
        s3_physical_bias_seen[address]=1;
        s3_physical_bias_count=s3_physical_bias_count+1;
      end

    end
  endtask

  task s3_require_physical_clear_coverage;
    integer a;
    begin
      s3_require_physical_clear_idle();
      if (s3_physical_w_count!=0 || s3_physical_w_seen!=={16384{1'b1}} ||
          s3_clear_w_seen!=={16384{1'b1}} || s3_clear_x_seen!=={64{1'b1}} ||
          `ACCEL.w_cursor!==16384 || `ACCEL.x_cursor!==64)
        $fatal(1,"S3_CLEAR_REJECT incomplete physical W/X coverage");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=0 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=0 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=1 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=1 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=2 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=2 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=3 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=3 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=4 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=4 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=5 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=5 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=6 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=6 half=1");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=7 half=0");

      for (a=0;a<1024;a=a+1)
        if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank=7 half=1");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_0!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=0");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_1!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=1");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_2!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=2");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_3!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=3");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_4!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=4");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_5!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=5");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_6!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=6");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_7!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=7");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_8!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=8");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_9!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=9");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_10!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=10");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_11!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=11");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_12!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=12");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_13!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=13");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_14!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=14");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_15!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=15");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_16!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=16");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_17!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=17");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_18!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=18");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_19!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=19");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_20!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=20");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_21!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=21");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_22!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=22");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_23!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=23");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_24!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=24");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_25!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=25");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_26!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=26");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_27!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=27");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_28!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=28");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_29!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=29");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_30!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=30");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_31!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=31");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_32!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=32");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_33!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=33");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_34!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=34");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_35!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=35");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_36!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=36");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_37!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=37");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_38!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=38");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_39!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=39");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_40!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=40");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_41!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=41");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_42!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=42");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_43!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=43");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_44!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=44");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_45!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=45");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_46!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=46");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_47!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=47");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_48!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=48");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_49!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=49");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_50!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=50");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_51!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=51");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_52!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=52");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_53!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=53");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_54!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=54");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_55!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=55");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_56!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=56");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_57!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=57");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_58!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=58");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_59!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=59");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_60!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=60");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_61!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=61");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_62!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=62");

      if (`ACCEL.u_linear_compute_core.core.xBuffer.data_63!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address=63");

      if (`ACCEL.bias_regs[0]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=0");

      if (`ACCEL.bias_regs[1]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=1");

      if (`ACCEL.bias_regs[2]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=2");

      if (`ACCEL.bias_regs[3]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=3");

      if (`ACCEL.bias_regs[4]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=4");

      if (`ACCEL.bias_regs[5]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=5");

      if (`ACCEL.bias_regs[6]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=6");

      if (`ACCEL.bias_regs[7]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane=7");

      if (!s3_clear_is_sram || s3_physical_bias_count!=768 ||
          s3_physical_bias_seen!=={768{1'b1}} ||
          `ACCEL.u_linear_compute_core.biasCache.slotValid_0!==1'b0 ||
          `ACCEL.u_linear_compute_core.biasCache.slotValid_1!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT incomplete physical bias coverage");
      for (a=0;a<768;a=a+1)
        if (`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical bias poststate");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_0!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=0");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_1!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=1");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_2!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=2");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_3!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=3");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_4!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=4");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_5!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=5");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_6!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=6");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_0_7!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=0 lane=7");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_0!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=0");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_1!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=1");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_2!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=2");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_3!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=3");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_4!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=4");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_5!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=5");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_6!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=6");

      if (`ACCEL.u_linear_compute_core.biasCache.slotData_1_7!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot=1 lane=7");

    end
  endtask
  task s3_require_physical_clear_idle;
    begin
      if (`ACCEL.u_linear_compute_core.core.xBuffer.io_wen!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X write still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");

      if (`ACCEL.u_linear_compute_core.biasCache.memory.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias port still active at proof");

    end
  endtask

  reg [16383:0] s3_clear_w_seen=0;
  reg [63:0] s3_clear_x_seen=0;
  reg [7:0] s3_clear_bank_seen=0;
  reg [4:0] s3_clear_bias_seen [0:255];
  reg [4:0] s3_clear_legacy_seen [0:7];
  reg [5:0] s3_clear_read_seen=0;
  reg s3_clear_complete=0, s3_clear_pending=0, s3_clear_pending_read=0;
  reg [11:0] s3_clear_response_address=0;
  reg s3_clear_cap_seen=0, s3_clear_is_sram=0;
  reg s3_clear_verified=0, s3_clear_pending_proof=0, s3_clear_pending_preflight=0;
  reg s3_clear_held_response=0, s3_clear_held_error=0;
  reg [31:0] s3_clear_held_data=0;
  integer s3_clear_init;
  initial begin
    for (s3_clear_init=0;s3_clear_init<256;s3_clear_init=s3_clear_init+1)
      s3_clear_bias_seen[s3_clear_init]=0;
    for (s3_clear_init=0;s3_clear_init<8;s3_clear_init=s3_clear_init+1)
      s3_clear_legacy_seen[s3_clear_init]=0;
  end

  task s3_require_clear_coverage;
    integer expected_writes;
    begin
      expected_writes=s3_clear_is_sram ? 8252 : 9019;
      if (!s3_clear_cap_seen || s3_clear_read_seen!==6'h3f ||
          s3_clear_writes!=expected_writes || s3_clear_disable_count!=1 ||
          s3_clear_w_count!=16384 || s3_clear_x_count!=64 || s3_clear_legacy_count!=8 ||
          s3_clear_bank_seen!==8'hff || s3_clear_w_addr_count!=1 ||
          s3_clear_x_addr_count!=1 || s3_clear_w_packs!=8192 || s3_clear_x_packs!=32 || s3_clear_legacy_addr_count!=8 ||
          (s3_clear_is_sram && (s3_clear_sram_commands!=1 ||
            s3_clear_sram_done!=1 || s3_clear_bias_count!=0 || s3_clear_bias_addr_count!=0)) ||
          (!s3_clear_is_sram && (s3_clear_bias_count!=256 ||
            s3_clear_bias_addr_count!=256 || s3_clear_sram_commands!=0 || s3_clear_sram_done!=0)))
        $fatal(1,"S3_CLEAR_REJECT incomplete clear before first source request");
      s3_require_physical_clear_coverage();
    end
  endtask

  task s3_observe_task_clear;
    input first_source_request;
    input nice_idle;
    output payload_phase;
    integer a, read_index;
    reg [4:0] old_mask, new_mask;
    begin
      s3_clear_ticks=s3_clear_ticks+1;
      if (!s3_clear_complete) begin
        if (first_source_request!==1'b0 && first_source_request!==1'b1)
          $fatal(1,"S3_CLEAR_REJECT unknown source-request predicate");
        if (nice_idle!==1'b1)
          $fatal(1,"S3_CLEAR_REJECT NICE not idle before task request");
        if (`ACCEL.cache_enable!==1'b0 || `ACCEL.busy!==1'b0 ||
            `ACCEL.core_start!==1'b0 || `ACCEL.row_count!==0)
          $fatal(1,"S3_CLEAR_REJECT non-idle/enabled clear phase");

        // Check BEFORE consuming anything on this edge. A simultaneous pending
        // write or response is not proof of clear before the first request.
        if (first_source_request) begin
          if (s3_clear_pending || s3_clear_commands!=s3_clear_responses ||
              s3_preflight_commands!=s3_preflight_responses ||
              `ACCEL.rsp_valid!==1'b0 || `ACCEL.cmd_valid!==1'b0 ||
              `ACCEL.cache_pending!==1'b0 || `ACCEL.stream_pending!==1'b0 ||
              `ACCEL.cache_idle!==1'b1 || `ACCEL.w_load_wen!==1'b0 ||
              `ACCEL.x_load_wen!==1'b0 ||
              `ACCEL.u_linear_compute_core.io_wLoadWen!==1'b0 ||
              `ACCEL.u_linear_compute_core.io_xLoadWen!==1'b0)
            $fatal(1,"S3_CLEAR_REJECT undrained clear before first source request");
          s3_require_clear_coverage();
          if (!s3_clear_verified || s3_clear_proof_reads!=1 || s3_clear_reads!=8 ||
              s3_clear_stream_proofs!=1 || !s3_clear_stream_verified)
            $fatal(1,"S3_CLEAR_REJECT missing clear completion proof before first source request");
          s3_clear_complete=1;
          $display("S3_TASK_CLEAR_OBSERVED mode_sram=%0d writes=%0d reads=%0d w=16384 x=64 legacy_bias=8 bias_entries=%0d physical_w=%0d physical_x=%0d physical_bias=%0d w_packs=%0d x_packs=%0d sram_clear_commands=%0d sram_done=%0d commands=%0d responses=%0d clear_cycles=%0d response_end_cycle=%0d gap_to_source_request=%0d preflight_commands=%0d preflight_responses=%0d nice_idle=1 fifo_payload_physical_zero=UNPROVEN policy=REVIEW_PENDING clear_transport=public-pack32",
            s3_clear_is_sram,s3_clear_writes,s3_clear_reads,s3_clear_bias_count,
            s3_physical_w_count,s3_clear_x_count,s3_physical_bias_count,
            s3_clear_w_packs,s3_clear_x_packs,s3_clear_sram_commands,s3_clear_sram_done,s3_clear_commands,s3_clear_responses,
            s3_clear_last_response-s3_clear_first+1,s3_clear_last_response,
            s3_clear_ticks-s3_clear_last_response,s3_preflight_commands,s3_preflight_responses);
        end else begin
          s3_observe_physical_clear();
          if (`ACCEL.cmd_valid && s3_clear_first<0) s3_clear_first=s3_clear_ticks;
          if (s3_clear_held_response && (`ACCEL.rsp_valid!==1'b1 ||
              `ACCEL.rsp_err!==s3_clear_held_error || `ACCEL.rsp_rdata!==s3_clear_held_data))
            $fatal(1,"S3_CLEAR_REJECT unstable held MMIO response");
          s3_clear_held_response=`ACCEL.rsp_valid && !`ACCEL.rsp_ready;
          s3_clear_held_error=`ACCEL.rsp_err;
          s3_clear_held_data=`ACCEL.rsp_rdata;

          if (`ACCEL.cache_clear_done) begin
            if (!s3_clear_is_sram || s3_clear_sram_commands!=1 || s3_clear_sram_done ||
                s3_clear_ticks-s3_clear_sram_start<768 || s3_physical_bias_count!=768)
              $fatal(1,"S3_CLEAR_REJECT invalid or premature physical bias clear done");
            s3_clear_sram_done=s3_clear_sram_done+1;
          end
          // Retire old response before accepting a replacement command.
          if (`ACCEL.rsp_valid && `ACCEL.rsp_ready) begin
            if (!s3_clear_pending || `ACCEL.rsp_err!==1'b0)
              $fatal(1,"S3_CLEAR_REJECT orphan/error clear response");
            if (!s3_clear_pending_read && s3_clear_response_address==12'h05c &&
                (s3_clear_w_count!=2*s3_clear_w_packs ||
                 s3_physical_w_count!=s3_clear_w_count || `ACCEL.stream_pending!==1'b0 ||
                 `ACCEL.u_linear_compute_core.io_wLoadWen!==1'b0))
              $fatal(1,"S3_CLEAR_REJECT W packed response preceded both physical writes");
            if (!s3_clear_pending_read && s3_clear_response_address==12'h068 &&
                (s3_clear_x_count!=2*s3_clear_x_packs || `ACCEL.stream_pending!==1'b0 ||
                 `ACCEL.u_linear_compute_core.io_xLoadWen!==1'b0))
              $fatal(1,"S3_CLEAR_REJECT X packed response preceded both physical writes");
            if (s3_clear_pending_preflight) begin
              if (!s3_clear_pending_read || (^`ACCEL.rsp_rdata)===1'bx)
                $fatal(1,"S3_CLEAR_REJECT unknown/non-read ABI preflight response");
              s3_preflight_responses=s3_preflight_responses+1;
            end else if (s3_clear_pending_read) begin
              case (s3_clear_response_address)
                12'h000: if (`ACCEL.rsp_rdata!==32'hacce2030)
                  $fatal(1,"S3_CLEAR_REJECT bad ID response");
                12'h050: if (`ACCEL.rsp_rdata!==32'h58550003)
                  $fatal(1,"S3_CLEAR_REJECT bad legacy capability response");
                12'h00c: begin
                  if (`ACCEL.rsp_rdata!==0)
                    $fatal(1,"S3_CLEAR_REJECT non-fresh status response");
                  if (s3_clear_pending_proof) begin
                    s3_clear_verified=1; s3_clear_proof_reads=s3_clear_proof_reads+1;
                  end
                end
                12'h070: if (`ACCEL.rsp_rdata!==32'h58530003)
                  $fatal(1,"S3_CLEAR_REJECT bad stream capability response");
                12'h074: if (`ACCEL.rsp_rdata!==32'h58500003)
                  $fatal(1,"S3_CLEAR_REJECT bad packed capability response");
                12'h06c: begin
                  if (`ACCEL.rsp_rdata!==0)
                    $fatal(1,"S3_CLEAR_REJECT nonzero stream completion status");
                  s3_clear_stream_verified=1;
                end
                12'h0ec: begin
                  if (`ACCEL.rsp_rdata!==0 && `ACCEL.rsp_rdata!==32'h42530001)
                    $fatal(1,"S3_CLEAR_REJECT unsupported bias capability response");
                  s3_clear_cap_seen=1;
                  s3_clear_is_sram=`ACCEL.rsp_rdata===32'h42530001;
                end
                default: $fatal(1,"S3_CLEAR_REJECT untracked clear read response");
              endcase
            end else if (s3_clear_response_address==12'h0e8 && s3_clear_sram_done!=1)
              $fatal(1,"S3_CLEAR_REJECT bias response without physical clear done");
            s3_clear_pending=0;
            if (!s3_clear_pending_preflight) begin
              s3_clear_responses=s3_clear_responses+1;
              s3_clear_last_response=s3_clear_ticks;
            end
          end
          if (`ACCEL.cmd_valid && `ACCEL.cmd_ready) begin
            if (s3_clear_pending) $fatal(1,"S3_CLEAR_REJECT multiple clear commands in flight");
            s3_clear_pending=1; s3_clear_pending_read=`ACCEL.cmd_read;
            s3_clear_response_address=`ACCEL.cmd_addr[11:0];
            s3_clear_pending_proof=0; s3_clear_pending_preflight=s3_clear_verified;
            if (s3_clear_verified) begin
              if (!`ACCEL.cmd_read)
                $fatal(1,"S3_CLEAR_REJECT parameter write before first source request");
              case (`ACCEL.cmd_addr[11:0])
                12'h000,12'h00c,12'h050,12'h070,12'h074,12'h078,12'h0e0,12'h0e4: begin end
                default: $fatal(1,"S3_CLEAR_REJECT unexpected ABI preflight read");
              endcase
              s3_preflight_commands=s3_preflight_commands+1;
            end else if (`ACCEL.cmd_read) begin
              s3_clear_commands=s3_clear_commands+1;
              case (`ACCEL.cmd_addr[11:0])
                12'h000: read_index=0;
                12'h050: read_index=1;
                12'h00c: read_index=2;
                12'h0ec: read_index=3;
                12'h070: read_index=4;
                12'h074: read_index=5;
                12'h06c: begin
                  if (s3_clear_reads!=6 || s3_clear_stream_proofs!=0)
                    $fatal(1,"S3_CLEAR_REJECT invalid stream completion proof order");
                  s3_require_clear_coverage();
                  if (`ACCEL.stream_pending!==1'b0 || `ACCEL.cache_pending!==1'b0 ||
                      `ACCEL.u_linear_compute_core.io_wLoadWen!==1'b0 ||
                      `ACCEL.u_linear_compute_core.io_xLoadWen!==1'b0)
                    $fatal(1,"S3_CLEAR_REJECT undrained clear before stream proof");
                  s3_clear_stream_proofs=s3_clear_stream_proofs+1;
                  read_index=6;
                end
                default: $fatal(1,"S3_CLEAR_REJECT unexpected pretask MMIO read");
              endcase
              if (read_index==6) begin end
              else if (s3_clear_read_seen[read_index]) begin
                if (read_index!=2 || s3_clear_reads!=7 || !s3_clear_stream_verified)
                  $fatal(1,"S3_CLEAR_REJECT repeated ABI read");
                s3_require_clear_coverage();
                if (`ACCEL.cache_pending!==1'b0 || `ACCEL.stream_pending!==1'b0 ||
                    `ACCEL.cache_idle!==1'b1 || `ACCEL.w_load_wen!==1'b0 ||
                    `ACCEL.x_load_wen!==1'b0 ||
                    `ACCEL.u_linear_compute_core.io_wLoadWen!==1'b0 ||
                    `ACCEL.u_linear_compute_core.io_xLoadWen!==1'b0)
                  $fatal(1,"S3_CLEAR_REJECT undrained clear before completion proof");
                s3_clear_pending_proof=1;
              end else s3_clear_read_seen[read_index]=1;
              s3_clear_reads=s3_clear_reads+1;
            end else begin
              s3_clear_commands=s3_clear_commands+1;
              if (!s3_clear_cap_seen || s3_clear_read_seen!==6'h3f ||
                  `ACCEL.cmd_wmask!==4'hf || (^`ACCEL.cmd_wdata)===1'bx)
                $fatal(1,"S3_CLEAR_REJECT missing ABI or incomplete/unknown clear word");
              s3_clear_writes=s3_clear_writes+1;
              case (`ACCEL.cmd_addr[11:0])
                12'h040: begin
                  if (`ACCEL.cmd_wdata!==0 || s3_clear_disable_count!=0)
                    $fatal(1,"S3_CLEAR_REJECT cache disable");
                  s3_clear_disable_count=s3_clear_disable_count+1;
                end
                12'h054: begin
                  if (`ACCEL.cmd_wdata!==0 || s3_clear_w_addr_count!=0 || s3_clear_w_packs!=0)
                    $fatal(1,"S3_CLEAR_REJECT W cursor initialization");
                  s3_clear_w_addr_count=s3_clear_w_addr_count+1;
                end
                12'h060: begin
                  if (`ACCEL.cmd_wdata!==0 || s3_clear_x_addr_count!=0 || s3_clear_x_packs!=0)
                    $fatal(1,"S3_CLEAR_REJECT X cursor initialization");
                  s3_clear_x_addr_count=s3_clear_x_addr_count+1;
                end
                12'h05c: begin
                  if (`ACCEL.cmd_wdata!==0 || s3_clear_w_addr_count!=1 ||
                      `ACCEL.w_cursor!==2*s3_clear_w_packs || s3_clear_w_packs>=8192)
                    $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate W packed command");
                  s3_clear_w_packs=s3_clear_w_packs+1;
                end
                12'h068: begin
                  if (`ACCEL.cmd_wdata!==0 || s3_clear_x_addr_count!=1 ||
                      `ACCEL.x_cursor!==2*s3_clear_x_packs || s3_clear_x_packs>=32)
                    $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate X packed command");
                  s3_clear_x_packs=s3_clear_x_packs+1;
                end
                12'h028: begin
                  if (`ACCEL.cmd_wdata>7) $fatal(1,"S3_CLEAR_REJECT legacy bias address");
                  s3_clear_legacy_addr_count=s3_clear_legacy_addr_count+1;
                end
                12'h044: begin
                  if (s3_clear_is_sram || `ACCEL.cmd_wdata>255)
                    $fatal(1,"S3_CLEAR_REJECT register bias address");
                  s3_clear_bias_addr_count=s3_clear_bias_addr_count+1;
                end
                12'h0e8: begin
                  if (!s3_clear_is_sram || `ACCEL.cmd_wdata!==1 || s3_clear_sram_commands)
                    $fatal(1,"S3_CLEAR_REJECT SRAM bias clear command");
                  s3_clear_sram_commands=1; s3_clear_sram_start=s3_clear_ticks;
                end
                12'h048,12'h04c,12'h02c,12'h030: begin
                  if (`ACCEL.cmd_wdata!==0) $fatal(1,"S3_CLEAR_REJECT nonzero bias clear");
                  if (`ACCEL.cmd_addr[11:0]==12'h048 || `ACCEL.cmd_addr[11:0]==12'h04c) begin
                    if (s3_clear_is_sram || (^`ACCEL.cache_addr_reg)===1'bx)
                      $fatal(1,"S3_CLEAR_REJECT invalid register bias clear");
                    a=`ACCEL.cache_addr_reg; old_mask=s3_clear_bias_seen[a];
                  end else begin
                    if ((^`ACCEL.bias_index_reg)===1'bx)
                      $fatal(1,"S3_CLEAR_REJECT unknown legacy bias destination");
                    a=`ACCEL.bias_index_reg; old_mask=s3_clear_legacy_seen[a];
                  end
                  if (`ACCEL.cmd_addr[11:0]==12'h048 || `ACCEL.cmd_addr[11:0]==12'h02c) begin
                    if (old_mask[3:0]!=0) $fatal(1,"S3_CLEAR_REJECT duplicate bias low clear");
                    new_mask=old_mask|5'b01111;
                  end else begin
                    if (old_mask[4]) $fatal(1,"S3_CLEAR_REJECT duplicate bias high clear");
                    new_mask=old_mask|5'b10000;
                  end
                  if (`ACCEL.cmd_addr[11:0]==12'h048 || `ACCEL.cmd_addr[11:0]==12'h04c) begin
                    s3_clear_bias_seen[a]=new_mask;
                    if (new_mask==5'b11111) s3_clear_bias_count=s3_clear_bias_count+1;
                  end else begin
                    s3_clear_legacy_seen[a]=new_mask;
                    if (new_mask==5'b11111) s3_clear_legacy_count=s3_clear_legacy_count+1;
                  end
                end
                default: $fatal(1,"S3_CLEAR_REJECT unexpected pretask MMIO write");
              endcase
            end
          end
        end
      end
      payload_phase=s3_clear_complete;
    end
  endtask
