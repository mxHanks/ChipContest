`timescale 1ns/1ps
// Exercise the actual generated scheduler, SRAM and MAC datapaths. No force,
// memory preload or mock completion is used. Demand/take are observed at the
// same edges as the real BiasSramPrefetch command interface.
module tb_bias_demand_schedule;
  reg clock=0; always #5 clock=~clock;
  reg reset=1, start=0, row_start=0, row_pop=0, cache_enable=1;
  reg [4:0] group_id=0;
  reg x_wen=0, w_wen=0, cache_wen=0, cache_clear=0;
  wire cache_clear_ready,cache_clear_done;
  reg [5:0] x_addr=0;
  reg [10:0] w_addr=0;
  reg [2:0] w_bank=0;
  reg signed [15:0] x_data=0,w_data=0;
  reg [7:0] cache_addr=0;
  reg [39:0] cache_data=0;
  wire cache_ready, cache_rsp_valid, cache_rsp_error, cache_idle;
  wire row_active,row_running,row_valid,done,compute_start;
  wire [1:0] row_count;
  wire [5:0] row_produced,row_retired;
  wire [4:0] row_group;
  wire [47:0] row_result[0:7],result[0:7];
  wire [31:0] sram_cap;
  LinearAutoGroupCore dut(
    .clock(clock),
    .reset(reset),
    .io_start(start),
    .io_group(group_id),
    .io_xLoadWen(x_wen),
    .io_xLoadAddr(x_addr),
    .io_xLoadData(x_data),
    .io_wLoadWen(w_wen),
    .io_wLoadBank(w_bank),
    .io_wLoadAddr(w_addr),
    .io_wLoadData(w_data),
    .io_bias_0(40'd0),
    .io_bias_1(40'd0),
    .io_bias_2(40'd0),
    .io_bias_3(40'd0),
    .io_bias_4(40'd0),
    .io_bias_5(40'd0),
    .io_bias_6(40'd0),
    .io_bias_7(40'd0),
    .io_done(done),
    .io_result_0(result[0]),
    .io_result_1(result[1]),
    .io_result_2(result[2]),
    .io_result_3(result[3]),
    .io_result_4(result[4]),
    .io_result_5(result[5]),
    .io_result_6(result[6]),
    .io_result_7(result[7]),
    .io_cacheEnable(cache_enable),
    .io_cacheWriteEnable(cache_wen),
    .io_cacheWriteAddr(cache_addr),
    .io_cacheWriteData(cache_data),
    .io_cacheWriteMask(5'h1f),
    .io_cacheReadAddr(8'd0),
    .io_cacheReadData(),
    .io_cacheReadEnable(1'b0),
    .io_cacheCmdReady(cache_ready),
    .io_cacheRspValid(cache_rsp_valid),
    .io_cacheRspReady(1'b1),
    .io_cacheRspError(cache_rsp_error),
    .io_cacheIdle(cache_idle),
    .io_cacheInvalidate(1'b0),
    .io_cacheClearValid(cache_clear),
    .io_cacheClearReady(cache_clear_ready),
    .io_cacheClearDone(cache_clear_done),
    .io_biasSramCapability(sram_cap),
    .io_rowStart(row_start),
    .io_rowPop(row_pop),
    .io_rowActive(row_active),
    .io_rowRunning(row_running),
    .io_rowValid(row_valid),
    .io_rowCount(row_count),
    .io_rowProduced(row_produced),
    .io_rowRetired(row_retired),
    .io_rowGroup(row_group),
    .io_rowResult_0(row_result[0]),
    .io_rowResult_1(row_result[1]),
    .io_rowResult_2(row_result[2]),
    .io_rowResult_3(row_result[3]),
    .io_rowResult_4(row_result[4]),
    .io_rowResult_5(row_result[5]),
    .io_rowResult_6(row_result[6]),
    .io_rowResult_7(row_result[7]),
    .io_computeStart(compute_start)
  );

  function automatic signed [15:0] xv(input integer k);
    xv=k-32;
  endfunction
  function automatic signed [15:0] wv(input integer g,input integer l,input integer k);
    wv=g*9+l*3-k;
  endfunction
  function automatic signed [39:0] bv(input integer row,input integer col);
    if(col%2==0) bv=-40'sh8000000000+row*997+col;
    else bv=40'sh7fffffffff-row*997-col;
  endfunction
  function automatic signed [63:0] expected(input integer row,input integer g,input integer l);
    integer k; reg signed [31:0] product; reg signed [63:0] total;
    begin
      total=bv(row,g*8+l);
      for(k=0;k<64;k=k+1) begin
        product=xv(k)*wv(g,l,k); total=total+product;
      end
      expected=total;
    end
  endfunction

  integer cycles=0, baseline=0, recording=0, scenario=0, data_row=0;
  integer demand_count=0,launch_count=0,take_count=0,done_count=0,early_count=0;
  integer demand_seen[0:31],take_seen[0:31],launch_cycle[0:31],done_cycle[0:31];
  integer min_interval=99999,max_interval=0,last_group=-1,watchdog=0;
  integer clear_writes=0; reg clear_observe=0;
  integer i,j,k,g,l,row,phase,total_rows=0,total_resets=0,manual_checks=0;
  reg [39:0] launch_bias[0:7];
  wire [39:0] real_bias[0:7];
  assign real_bias[0]=dut.core.io_bias_0;
  assign real_bias[1]=dut.core.io_bias_1;
  assign real_bias[2]=dut.core.io_bias_2;
  assign real_bias[3]=dut.core.io_bias_3;
  assign real_bias[4]=dut.core.io_bias_4;
  assign real_bias[5]=dut.core.io_bias_5;
  assign real_bias[6]=dut.core.io_bias_6;
  assign real_bias[7]=dut.core.io_bias_7;

  task automatic reset_counters;
    begin
      demand_count=0; launch_count=0; take_count=0; done_count=0; early_count=0;
      min_interval=99999; max_interval=0; last_group=-1;
      for(i=0;i<32;i=i+1) begin
        demand_seen[i]=0; take_seen[i]=0; launch_cycle[i]=-1; done_cycle[i]=-1;
      end
    end
  endtask
  always @(posedge clock) begin
    cycles=cycles+1;
    if(!reset && clear_observe && dut.biasCache.memory.io_en && dut.biasCache.memory.io_isWrite)begin
      if(dut.biasCache.memory.io_addr!==clear_writes || dut.biasCache.memory.io_wdata!==16'd0)
        $fatal(1,"true clear wrong physical word/data");
      clear_writes=clear_writes+1;
    end
    if(!reset && recording) begin
      if(row_active && row_produced-row_retired!=row_count)
        $fatal(1,"FIFO count conservation failed");
      if(dut.biasCache.groupFire) begin
        if(dut.biasCache.io_groupReqTag!=demand_count || demand_count>=32)
          $fatal(1,"demand duplicate/missing/wrapped tag=%0d expected=%0d",dut.biasCache.io_groupReqTag,demand_count);
        if(demand_seen[dut.biasCache.io_groupReqTag]!=0)$fatal(1,"duplicate demand");
        demand_seen[dut.biasCache.io_groupReqTag]=1;
        if(demand_count>0 && !baseline) begin
          if(!row_running || dut.takeBias || dut.produced!=demand_count-1)
            $fatal(1,"next demand escaped the post-INIT RUN window");
          if(cycles-launch_cycle[demand_count-1]!=2)
            $fatal(1,"next demand was delayed beyond INIT release");
          early_count=early_count+1;
        end
        if(baseline && row_running)$fatal(1,"baseline unexpectedly requested while RUN");
        demand_count=demand_count+1;
      end
      if(compute_start && row_active) begin
        if(dut.core.io_group!==launch_count || launch_count>=32)
          $fatal(1,"launch duplicate/missing/out-of-order group");
        if(!dut.biasCache.io_groupValid || dut.biasCache.io_groupTag!==launch_count)
          $fatal(1,"launch did not own correct ready bias");
        launch_cycle[launch_count]=cycles; last_group=launch_count;
        for(j=0;j<8;j=j+1) begin
          launch_bias[j]=real_bias[j];
          if($signed(real_bias[j])!==bv(data_row,launch_count*8+j))
            $fatal(1,"launch bias corrupted row=%0d group=%0d lane=%0d",data_row,launch_count,j);
        end
        if(launch_count>0 && scenario==1) begin
          if(cycles-launch_cycle[launch_count-1]<min_interval)min_interval=cycles-launch_cycle[launch_count-1];
          if(cycles-launch_cycle[launch_count-1]>max_interval)max_interval=cycles-launch_cycle[launch_count-1];
        end
        launch_count=launch_count+1;
      end
      if(dut.takeBias) begin
        if(last_group<0 || cycles-launch_cycle[last_group]!=1 ||
           !dut.core.engine.controller.io_init ||
           !dut.biasCache.io_groupValid || dut.biasCache.io_groupTag!==last_group)
          $fatal(1,"take did not coincide with its exact INIT/tag");
        for(j=0;j<8;j=j+1)if(real_bias[j]!==launch_bias[j])
          $fatal(1,"bias changed before INIT sampled it");
        if(take_seen[last_group]!=0)$fatal(1,"duplicate bias take");
        take_seen[last_group]=1; take_count=take_count+1;
      end
      if(done && row_active) begin
        if(done_count>=launch_count || done_cycle[done_count]>=0)$fatal(1,"duplicate or early done");
        done_cycle[done_count]=cycles;
        if(cycles-launch_cycle[done_count]!=67)$fatal(1,"MAC done latency changed got=%0d",cycles-launch_cycle[done_count]);
        done_count=done_count+1;
      end
    end
  end

  task automatic tick; begin @(posedge clock); #1; end endtask
  task automatic set_reset;
    begin
      @(negedge clock); recording=0; reset=1; row_start=0; row_pop=0; start=0;
      repeat(4)tick();
      @(negedge clock); reset=0;
      tick();
      if(row_active || row_valid || row_running || row_count!=0 ||
         dut.takeBias || dut.biasCache.wantedPending)
        $fatal(1,"stale scheduler demand survived reset");
    end
  endtask
  task automatic load_bias(input integer r);
    integer col,n;
    begin
      for(col=0;col<256;col=col+1) begin
        @(negedge clock); cache_wen=1;cache_addr=col;cache_data=bv(r,col);
        n=0;
        while(!cache_ready)begin tick();n=n+1;if(n>100)$fatal(1,"bias ready timeout");end
        tick();
        @(negedge clock);cache_wen=0;
        n=0;while(!cache_rsp_valid)begin tick();n=n+1;if(n>100)$fatal(1,"bias response timeout");end
        if(cache_rsp_error)$fatal(1,"bias upload rejected");
        tick();
      end
      data_row=r;
    end
  endtask
  task automatic begin_row(input integer scen);
    begin
      @(negedge clock); reset_counters(); scenario=scen; recording=1;row_start=1;
      tick(); @(negedge clock);row_start=0;
    end
  endtask
  task automatic drain_row;
    integer group_to_pop,n,z; reg [47:0] saved[0:7];
    begin
      for(group_to_pop=0;group_to_pop<32;group_to_pop=group_to_pop+1)begin
        n=0;
        while(!row_valid)begin tick();n=n+1;if(n>180)$fatal(1,"result timeout");end
        if(row_group!==group_to_pop)$fatal(1,"FIFO group mismatch");
        for(z=0;z<8;z=z+1)begin
          if($signed(row_result[z])!==expected(data_row,group_to_pop,z))
            $fatal(1,"real MAC oracle mismatch row=%0d g=%0d lane=%0d",data_row,group_to_pop,z);
          saved[z]=row_result[z];
        end
        if(scenario==2 && group_to_pop%5==0)begin
          repeat(90)begin
            tick();for(z=0;z<8;z=z+1)if(row_result[z]!==saved[z])$fatal(1,"FIFO head moved under backpressure");
          end
        end
        @(negedge clock);row_pop=1;tick();@(negedge clock);row_pop=0;
      end
      if(row_active || row_produced!=32 || row_retired!=32 || row_count!=0 || dut.biasCache.wantedPending)
        $fatal(1,"row did not retire exactly 32 groups");
      tick();
      if(demand_count!=32 || launch_count!=32 || done_count!=32 || take_count!=32 ||
          (!baseline && early_count!=31))$fatal(1,"incomplete demand/launch/take coverage");
      for(z=0;z<32;z=z+1)begin
        if(demand_seen[z]!=1 || take_seen[z]!=1)$fatal(1,"tag exactly-once invariant");
        if(z<31)$display("BIAS_DEMAND_GAP scenario=%0d group=%0d launch=%0d done=%0d next_launch=%0d",scenario,z,launch_cycle[z],done_cycle[z],launch_cycle[z+1]);
      end
      $display("BIAS_DEMAND_ROW scenario=%0d row=%0d demands=%0d launches=%0d takes=%0d dones=%0d early=%0d min_interval=%0d max_interval=%0d",
        scenario,data_row,demand_count,launch_count,take_count,done_count,early_count,min_interval,max_interval);
      // Keep recording during a quiet interval: a wrapped tag0 would fail the
      // exact 32-tag request counter even after the last POP retired.
      repeat(10)tick();
      if(!cache_clear_ready || dut.biasCache.wantedPending || dut.takeBias)
        $fatal(1,"group31 left a demand that blocks true clear");
      recording=0;total_rows=total_rows+1;
    end
  endtask

  initial begin
    if($value$plusargs("BASELINE=%d",baseline))begin end
    reset_counters();repeat(4)tick();@(negedge clock);reset=0;tick();
    if(sram_cap!==32'h42530001)$fatal(1,"real SRAM configuration required");
    // Load all actual operand SRAMs through their real public core ports.
    for(g=0;g<32;g=g+1)for(l=0;l<8;l=l+1)for(k=0;k<64;k=k+1)begin
      @(negedge clock);w_wen=1;w_addr=g*64+k;w_bank=l;w_data=wv(g,l,k);tick();
    end
    @(negedge clock);w_wen=0;
    for(k=0;k<64;k=k+1)begin
      @(negedge clock);x_wen=1;x_addr=k;x_data=xv(k);tick();
    end
    @(negedge clock);x_wen=0;
    load_bias(0);
    begin_row(1);drain_row();
    // Adjacent rows use different bias data; no stale lookahead may survive.
    load_bias(1);begin_row(1);drain_row();
    begin_row(2);
    repeat(250)tick();
    if(row_count!=2 || row_produced!=2 || row_running)$fatal(1,"FIFO did not stop producer at two groups");
    for(j=0;j<8;j=j+1)if($signed(row_result[j])!==expected(1,0,j))$fatal(1,"blocked head changed");
    repeat(150)tick();
    if(row_produced!=2 || launch_count!=2 || done_count!=2)$fatal(1,"producer ignored FIFO backpressure");
    drain_row();
    // Abort at INIT, accepted lookahead, and full-FIFO pending demand. Reload
    // bias after reset because SRAM retains payload while controls invalidate.
    for(phase=1;phase<=3;phase=phase+1)begin
      begin_row(3);watchdog=0;
      case(phase)
        1: while(!dut.takeBias)begin tick();watchdog=watchdog+1;if(watchdog>150)$fatal(1,"INIT reset window timeout");end
        2: while(demand_count<(baseline?1:2) || !row_running || dut.takeBias)begin tick();watchdog=watchdog+1;if(watchdog>150)$fatal(1,"next demand reset window timeout");end
        3: while(row_count!=2 || row_running)begin tick();watchdog=watchdog+1;if(watchdog>300)$fatal(1,"FIFO reset window timeout");end
      endcase
      if(phase==2 && !baseline && (!dut.biasCache.fillReadPending || dut.biasCache.fillIssueWord>=24))
        $fatal(1,"reset missed accepted lookahead with outstanding SRAM return");
      set_reset();total_resets=total_resets+1;
      load_bias(phase+1);begin_row(1);drain_row();
    end
    // Exercise the real SRAM clear handshake after group31; then refresh and
    // prove both manual cached START and a new complete autonomous row work.
    @(negedge clock);clear_observe=1;clear_writes=0;cache_clear=1;
    if(!cache_clear_ready)$fatal(1,"clear not ready after final row");
    tick();@(negedge clock);cache_clear=0;
    watchdog=0;
    while(!cache_clear_done)begin tick();watchdog=watchdog+1;if(watchdog>800)$fatal(1,"physical clear timeout");end
    if(dut.biasCache.wantedPending || clear_writes!=768)$fatal(1,"clear inherited stale demand or omitted physical word");
    clear_observe=0;
    tick();load_bias(5);
    // Return to the original manual cached-start interface and compare real MAC.
    @(negedge clock);group_id=19;start=1;
    tick();@(negedge clock);start=0;
    watchdog=0;
    while(!done)begin tick();watchdog=watchdog+1;if(watchdog>180)$fatal(1,"manual start timeout");end
    for(j=0;j<8;j=j+1)if($signed(result[j])!==expected(data_row,19,j))$fatal(1,"manual result mismatch");
    manual_checks=manual_checks+1;
    repeat(3)tick();
    if(dut.biasCache.wantedPending)$fatal(1,"manual completion left stale demand");
    begin_row(1);drain_row();
    $display("BIAS_DEMAND_SCHEDULE_PASS rows=%0d groups=%0d resets=%0d manual=%0d baseline=%0d clear_words=%0d force_used=0",total_rows,total_rows*32,total_resets,manual_checks,baseline,clear_writes);
    $finish;
  end
  initial begin #5000000;$fatal(1,"global timeout");end
endmodule
