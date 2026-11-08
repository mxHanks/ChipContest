`timescale 1ns/1ps
module tb_bias_group_pipeline;
  reg clock=0, reset=1;
  always #5 clock=~clock;
  reg io_computeActive=0, io_invalidate=0, io_clearValid=0;
  wire io_clearReady, io_clearDone;
  reg io_hostValid=0, io_hostRead=0, io_rspReady=0;
  reg [7:0] io_hostAddr=0;
  reg [39:0] io_hostData=0;
  reg [4:0] io_hostMask=31;
  wire io_hostReady, io_rspValid, io_rspError, io_hostIdle;
  wire [39:0] io_rspData;
  reg io_groupReqValid=0, io_groupTake=0;
  reg [4:0] io_groupReqTag=0;
  wire io_groupValid;
  wire [4:0] io_groupTag;
  wire [39:0] bias [0:7];
  BiasSramPrefetch dut(.clock(clock), .reset(reset),
    .io_computeActive(io_computeActive), .io_invalidate(io_invalidate),
    .io_clearValid(io_clearValid), .io_clearReady(io_clearReady), .io_clearDone(io_clearDone),
    .io_hostValid(io_hostValid), .io_hostReady(io_hostReady), .io_hostRead(io_hostRead),
    .io_hostAddr(io_hostAddr), .io_hostData(io_hostData), .io_hostMask(io_hostMask),
    .io_rspValid(io_rspValid), .io_rspReady(io_rspReady), .io_rspError(io_rspError),
    .io_rspData(io_rspData), .io_hostIdle(io_hostIdle),
    .io_groupReqValid(io_groupReqValid), .io_groupReqTag(io_groupReqTag),
    .io_groupValid(io_groupValid), .io_groupTag(io_groupTag), .io_groupTake(io_groupTake),
    .io_groupBias_0(bias[0]), .io_groupBias_1(bias[1]), .io_groupBias_2(bias[2]),
    .io_groupBias_3(bias[3]), .io_groupBias_4(bias[4]), .io_groupBias_5(bias[5]),
    .io_groupBias_6(bias[6]), .io_groupBias_7(bias[7]));
  reg [39:0] expected [0:255];
  integer cycles=0, stream_cycles=0, reads=0, completed=0, physical_reads=0;
  integer last_read_cycle=0, clear_words=0, invalidations=0, resets=0;
  reg [2:0] previous_state=0;
  reg monitoring_clear=0;
  always @(posedge clock) begin
    cycles=cycles+1;
    if(cycles>100000) $fatal(1,"pipeline test watchdog");
    if(reset) begin stream_cycles=0; reads=0; previous_state=0; end
    else begin
      if(dut.memory.io_en && dut.memory.io_addr>=768) $fatal(1,"out of range memory address");
      if(dut.state==6) begin
        if(previous_state!=6) begin stream_cycles=0; reads=0; end
        stream_cycles=stream_cycles+1;
        if(io_invalidate && dut.memory.io_en) $fatal(1,"read issued during invalidate");
        if(dut.memory.io_en) begin
          if(dut.memory.io_isWrite || dut.memory.io_addr!==dut.fillTag*24+reads)
            $fatal(1,"nonsequential group read tag=%d read=%d addr=%d",dut.fillTag,reads,dut.memory.io_addr);
          if(reads>0 && cycles!=last_read_cycle+1) $fatal(1,"bubble in continuous group reads");
          reads=reads+1; physical_reads=physical_reads+1; last_read_cycle=cycles;
        end
        if(dut.fillReadPending && !io_invalidate && dut.fillEpoch==dut.epoch) begin
          if(!dut.memory.io_rvalid) $fatal(1,"capture lacked synchronous return");
          if(dut.fillReturnWord==23) begin
            if(reads!=24 || stream_cycles!=25 || dut.memory.io_en)
              $fatal(1,"group completed early/late reads=%d cycles=%d",reads,stream_cycles);
            completed=completed+1;
          end
        end
      end
      if(monitoring_clear && dut.memory.io_en) begin
        if(!dut.memory.io_isWrite || dut.memory.io_addr!=clear_words || dut.memory.io_wdata!==0)
          $fatal(1,"physical clear order/data failed word=%d",clear_words);
        clear_words=clear_words+1;
      end
      previous_state=dut.state;
    end
  end
  task tick; begin @(posedge clock); #1; @(negedge clock); end endtask
  task hard_reset; begin
    reset=1; io_hostValid=0; io_rspReady=0; io_groupReqValid=0; io_groupTake=0;
    io_invalidate=0; io_clearValid=0; tick(); tick(); reset=0;
    if(io_groupValid || io_rspValid) $fatal(1,"reset retained protocol ownership");
  end endtask
  task host(input bit read_op, input integer addr, input [39:0] data, input bit error);
    integer waits; reg [39:0] held;
    begin
      io_hostValid=1; io_hostRead=read_op; io_hostAddr=addr; io_hostData=data; #1;
      waits=0;
      while(!io_hostReady) begin tick(); waits=waits+1; if(waits>70) $fatal(1,"host starvation"); end
      tick(); io_hostValid=0; io_hostAddr=~addr; io_hostData=~data;
      waits=0;
      while(!io_rspValid) begin tick(); waits=waits+1; if(waits>70) $fatal(1,"host timeout"); end
      if(io_rspError!==error) $fatal(1,"host error mismatch");
      held=io_rspData;
      repeat(3) begin tick(); if(!io_rspValid || io_rspData!==held || io_rspError!==error)
        $fatal(1,"host response changed while stalled"); end
      if(read_op && !error && held!==expected[addr]) $fatal(1,"host read data mismatch addr=%d",addr);
      io_rspReady=1; tick(); io_rspReady=0;
    end
  endtask
  task request(input integer tag);
    begin
      if(dut.wantedPending) $fatal(1,"overlapping group requests in test");
      io_groupReqTag=tag; io_groupReqValid=1; tick(); io_groupReqValid=0;
    end
  endtask
  task check_group(input integer tag);
    integer waits,lane; begin
      waits=0;
      while(!io_groupValid) begin tick(); waits=waits+1; if(waits>90) $fatal(1,"group starvation tag=%d",tag); end
      if(io_groupTag!=tag) $fatal(1,"wrong group tag");
      for(lane=0;lane<8;lane=lane+1)
        if(bias[lane]!==expected[tag*8+lane]) $fatal(1,"bias mismatch tag=%d lane=%d",tag,lane);
    end
  endtask
  task take; begin io_groupTake=1; tick(); io_groupTake=0; end endtask
  task wait_stage(input integer stage);
    integer waits; begin
      waits=0;
      while(!(dut.state==6 && ((stage==0 && !dut.fillReadPending && dut.fillIssueWord==0) ||
           (stage>0 && dut.fillReadPending && dut.fillReturnWord==stage-1)))) begin
        tick(); waits=waits+1; if(waits>30) $fatal(1,"stage unreachable %d",stage);
      end
    end
  endtask
  integer addr,tag,stage,k;
  initial begin
    @(negedge clock); hard_reset();
    for(addr=0;addr<256;addr=addr+1) begin
      expected[addr]=(40'h9123456789 ^ (40'h100010001*addr));
      if(addr==0) expected[addr]=40'h8000000000;
      if(addr==255) expected[addr]=40'h7fffffffff;
      host(0,addr,expected[addr],0);
    end
    for(tag=0;tag<32;tag=tag+1) begin
      hard_reset(); request(tag); check_group(tag);
      repeat(30) begin tick(); check_group(tag); end // current stable through next-tag prefetch
      take();
    end
    for(stage=0;stage<=24;stage=stage+1) begin
      hard_reset(); request(31); wait_stage(stage);
      io_invalidate=1; tick(); invalidations=invalidations+1;
      if(io_groupValid || dut.slotValid_0 || dut.slotValid_1) $fatal(1,"stale slot published on invalidate");
      io_invalidate=0; check_group(31); take();
    end
    for(stage=0;stage<=24;stage=stage+1) begin
      hard_reset(); request(31); wait_stage(stage);
      hard_reset(); resets=resets+1;
      repeat(2) begin tick(); if(io_groupValid) $fatal(1,"stale response after reset"); end
      request(31); check_group(31); take();
    end
    // A stalled host response cannot stop a demand or its next-tag prefetch.
    hard_reset(); io_hostValid=1; io_hostRead=1; io_hostAddr=91; #1;
    while(!io_hostReady) tick(); tick(); io_hostValid=0;
    while(!io_rspValid) tick();
    request(0); check_group(0); repeat(30) tick(); check_group(0);
    if(!io_rspValid || io_rspData!==expected[91]) $fatal(1,"stalled response corrupted");
    io_rspReady=1; tick(); io_rspReady=0; take();
    // Simultaneous demand plus host traffic must let each side progress.
    hard_reset(); request(0); host(1,219,0,0); check_group(0);
    io_computeActive=1; host(0,0,0,1); check_group(0); io_computeActive=0; take();
    // Clear is blocked by an owned group and then writes every physical word.
    hard_reset(); request(31); check_group(31); io_clearValid=1;
    repeat(3) begin if(io_clearReady) $fatal(1,"clear accepted while group owned"); tick(); end
    io_clearValid=0; take();
    while(!io_clearReady) tick(); monitoring_clear=1; io_clearValid=1; tick(); io_clearValid=0;
    k=0; while(!io_clearDone) begin tick(); k=k+1; if(k>770) $fatal(1,"clear timeout"); end
    monitoring_clear=0; if(clear_words!=768) $fatal(1,"incomplete physical clear");
    for(addr=0;addr<256;addr=addr+1) expected[addr]=0;
    for(tag=0;tag<32;tag=tag+1) begin request(tag); check_group(tag); take(); end
    host(1,0,0,0); host(1,255,0,0);
    $display("BIAS_GROUP_PIPELINE_PASS tags=32 words_per_fill=24 stream_cycles=25 invalidation_stages=%0d reset_stages=%0d complete_fills=%0d physical_reads=%0d clear_words=%0d",invalidations,resets,completed,physical_reads,clear_words);
    $finish;
  end
endmodule
