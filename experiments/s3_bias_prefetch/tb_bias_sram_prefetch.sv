`timescale 1ns/1ps
module tb_bias_sram_prefetch;
  reg clock=0, reset=1;
  always #5 clock=~clock;
  reg compute_active=0, invalidate=0, clear_valid=0;
  wire clear_ready, clear_done;
  reg cmd_valid=0, cmd_read=0, rsp_ready=0;
  wire cmd_ready, rsp_valid, rsp_err;
  reg [7:0] cmd_addr=0;
  reg [39:0] cmd_wdata=0;
  reg [4:0] cmd_wmask=0;
  wire [39:0] rsp_rdata;
  reg group_req_valid=0, group_take=0;
  reg [4:0] group_req_tag=0;
  wire group_req_ready, group_valid;
  wire [4:0] group_tag;
  wire [31:0] group_epoch, epoch;
  wire [319:0] group_data;
  reg [39:0] expected_bias [0:255];
  reg [31:0] rng=32'h20261105;
  integer cycles=0, transactions=0, group_checks=0, clear_writes=0;
  integer source_reads=0, physical_writes=0, rmw_reads=0;
  string vectors;
  bias_sram_prefetch dut (.*);

  // Observe the REAL SRAM wrapper port, independently of the adapter's response.
  // This proves each response follows all physical writes and checks the RMW
  // result; a count-only implementation cannot pass these value/address checks.
  reg host_live=0, live_read, live_active;
  reg [7:0] live_addr;
  reg [4:0] live_mask;
  reg [39:0] live_expected;
  reg [2:0] observed_writes=0, observed_reads=0;
  integer physical_word;
  reg [15:0] expected_word;
  always @(posedge clock) begin
    cycles=cycles+1;
    if (cycles>200000) $fatal(1,"prototype watchdog");
    if (!reset) begin
      if (rsp_valid && rsp_ready) begin
        if (!host_live) $fatal(1,"orphan host response");
        host_live=0;
      end
      if (cmd_valid && cmd_ready) begin
        if (host_live) $fatal(1,"second unretired host command");
        host_live=1; observed_reads=0; observed_writes=0;
        live_read=cmd_read; live_active=compute_active;
        live_addr=cmd_addr; live_mask=cmd_wmask;
      end
      if (dut.mem_en) begin
        if (dut.mem_addr>=768) $fatal(1,"SRAM access outside 768 bias words");
        if (dut.mem_write && dut.mem_addr%3==2 && dut.mem_wdata[15:8]!==0)
          $fatal(1,"high-word padding must be zero");
        if (dut.state==5) begin
          if (!dut.mem_write || dut.mem_addr!=clear_writes || dut.mem_wdata!==0)
            $fatal(1,"clear order/data mismatch word=%0d",clear_writes);
          clear_writes=clear_writes+1;
        end else if (dut.owner!=2) begin
          if (!host_live) $fatal(1,"unowned host memory operation");
          if (dut.mem_addr/3!=live_addr) $fatal(1,"host command address changed after accept");
          physical_word=dut.mem_addr%3;
          if (dut.mem_write) begin
            if (live_read || live_active || observed_writes[physical_word])
              $fatal(1,"unexpected or duplicate physical write");
            if ((physical_word==0 && live_mask[1:0]==0) ||
                (physical_word==1 && live_mask[3:2]==0) ||
                (physical_word==2 && !live_mask[4])) $fatal(1,"unselected word written");
            case (physical_word)
              0: expected_word=live_expected[15:0];
              1: expected_word=live_expected[31:16];
              2: expected_word={8'b0,live_expected[39:32]};
            endcase
            if (dut.mem_wdata!==expected_word) $fatal(1,"physical RMW data mismatch");
            observed_writes[physical_word]=1; physical_writes=physical_writes+1;
          end else begin
            if (observed_reads[physical_word]) $fatal(1,"duplicate physical read");
            observed_reads[physical_word]=1; source_reads=source_reads+1;
            if (!live_read) rmw_reads=rmw_reads+1;
          end
        end
      end
    end else host_live=0;
  end

  function [31:0] random_step;
    begin rng=rng*32'd1664525+32'd1013904223; random_step=rng; end
  endfunction

  task transaction(input integer read_op, active_op, input reg [7:0] addr,
                   input reg [4:0] mask, input reg [39:0] data, expected,
                   input integer error);
    integer accepted, waits, hold_cycles, i;
    reg [2:0] required_writes, required_reads;
    begin
      @(negedge clock);
      compute_active=active_op; cmd_valid=1; cmd_read=read_op;
      cmd_addr=addr; cmd_wdata=data; cmd_wmask=mask; rsp_ready=0;
      live_expected=expected;
      accepted=0; waits=0;
      while (!accepted) begin
        @(posedge clock); if (cmd_ready) accepted=1;
        #1; waits=waits+1;
        if (waits>150) $fatal(1,"host command starvation");
      end
      @(negedge clock);
      cmd_valid=0; cmd_addr=~addr; cmd_wdata=~data; cmd_wmask=~mask;
      waits=0;
      while (!rsp_valid) begin
        @(negedge clock); waits=waits+1;
        if (waits>150) $fatal(1,"host response timeout");
      end
      required_writes=0; required_reads=0;
      if (read_op) required_reads=7;
      else if (!error) begin
        required_writes={mask[4],|mask[3:2],|mask[1:0]};
        required_reads={1'b0,(mask[3:2]==1 || mask[3:2]==2),
                                (mask[1:0]==1 || mask[1:0]==2)};
      end
      if (observed_writes!==required_writes || observed_reads!==required_reads)
        $fatal(1,"response preceded complete memory work read=%b/%b write=%b/%b",
          observed_reads,required_reads,observed_writes,required_writes);
      hold_cycles=3+(random_step()%8);
      for (i=0; i<hold_cycles; i=i+1) begin
        if (rsp_valid!==1'b1 || rsp_err!==(error!=0) ||
            rsp_rdata!==(read_op ? expected : 40'b0))
          $fatal(1,"held response mismatch transaction=%0d",transactions);
        @(negedge clock);
      end
      rsp_ready=1;
      @(posedge clock); #1;
      @(negedge clock); rsp_ready=0; compute_active=0;
      transactions=transactions+1;
    end
  endtask

  task consecutive_reads;
    integer accepted;
    begin
      @(negedge clock);
      cmd_valid=1; cmd_read=1; cmd_addr=0; cmd_wmask=0; cmd_wdata=0;
      rsp_ready=0; live_expected=expected_bias[0]; accepted=0;
      while (!accepted) begin
        @(posedge clock); if (cmd_ready) accepted=1; #1;
      end
      @(negedge clock); cmd_valid=0;
      while (!rsp_valid) @(negedge clock);
      if (rsp_err || rsp_rdata!==expected_bias[0] || observed_reads!==3'b111)
        $fatal(1,"first consecutive read mismatch");
      // Retire the old snapshot and accept a new descriptor on the same edge.
      @(negedge clock);
      cmd_valid=1; cmd_addr=255; live_expected=expected_bias[255]; rsp_ready=1;
      @(posedge clock);
      if (!cmd_ready || !rsp_valid || rsp_rdata!==expected_bias[0])
        $fatal(1,"consecutive read turnover lost old response");
      #1;
      @(negedge clock); cmd_valid=0; rsp_ready=0; cmd_addr=77;
      while (!rsp_valid) @(negedge clock);
      if (rsp_err || rsp_rdata!==expected_bias[255] || observed_reads!==3'b111)
        $fatal(1,"second consecutive read descriptor was not latched");
      repeat (5) begin
        @(negedge clock);
        if (rsp_valid!==1'b1 || rsp_rdata!==expected_bias[255])
          $fatal(1,"second consecutive response changed under backpressure");
      end
      rsp_ready=1; @(posedge clock); #1;
      @(negedge clock); rsp_ready=0; transactions=transactions+2;
    end
  endtask

  task request_group(input reg [4:0] tag);
    integer accepted, waits;
    begin
      @(negedge clock); group_req_tag=tag; group_req_valid=1;
      accepted=0; waits=0;
      while (!accepted) begin
        @(posedge clock); if (group_req_ready) accepted=1;
        #1; waits=waits+1;
        if (waits>150) $fatal(1,"group request starvation");
      end
      @(negedge clock); group_req_valid=0;
    end
  endtask

  task check_group(input reg [4:0] tag, input integer hold_cycles, output integer latency);
    integer lane, i;
    reg [319:0] snapshot;
    reg [31:0] snapshot_epoch;
    begin
      latency=0;
      while (!group_valid) begin
        @(negedge clock); latency=latency+1;
        if (latency>160) $fatal(1,"group demand timeout tag=%0d",tag);
      end
      snapshot=group_data; snapshot_epoch=group_epoch;
      for (lane=0; lane<8; lane=lane+1)
        if (group_data[40*lane+:40]!==expected_bias[tag*8+lane])
          $fatal(1,"group data mismatch tag=%0d lane=%0d",tag,lane);
      for (i=0; i<hold_cycles; i=i+1) begin
        if (group_valid!==1'b1 || group_tag!==tag || group_epoch!==snapshot_epoch ||
            group_data!==snapshot) $fatal(1,"owned group changed while waiting for take");
        @(negedge clock);
      end
      group_checks=group_checks+1;
    end
  endtask

  task take_group;
    begin
      @(negedge clock); group_take=1;
      @(posedge clock); #1;
      @(negedge clock); group_take=0;
    end
  endtask

  task clear_memory;
    integer accepted, waits;
    begin
      @(negedge clock); clear_writes=0; clear_valid=1;
      accepted=0;
      while (!accepted) begin
        @(posedge clock); if (clear_ready) accepted=1; #1;
      end
      @(negedge clock); clear_valid=0; waits=0;
      while (!clear_done) begin
        @(negedge clock); waits=waits+1;
        if (waits>800) $fatal(1,"clear timeout");
      end
      if (clear_writes!=768) $fatal(1,"clear did not cover every physical bias word");
    end
  endtask

  initial begin : stimulus
    integer file, count, rd, active_op, err, addr_i, tag, latency, records;
    reg [7:0] addr;
    reg [4:0] mask;
    reg [39:0] data, expected;
    reg [31:0] old_epoch;
    if (!$value$plusargs("VECTORS=%s",vectors)) $fatal(1,"missing VECTORS");
    $readmemh({vectors,"/final_bias.mem"},expected_bias);
    repeat (3) @(negedge clock); reset=0;
    clear_memory();
    file=$fopen({vectors,"/transactions.txt"},"r");
    if (!file) $fatal(1,"missing transactions");
    records=0;
    while (!$feof(file)) begin
      count=$fscanf(file,"%d %d %h %h %h %h %d\n",rd,active_op,addr,mask,data,expected,err);
      if (count!=7) $fatal(1,"malformed transaction record");
      transaction(rd,active_op,addr,mask,data,expected,err); records=records+1;
    end
    $fclose(file);
    if (records!=3072 || rmw_reads==0) $fatal(1,"incomplete mask/RMW stimulus");
    consecutive_reads();
    // Hold every current group long enough for the next group to prefetch.
    for (tag=0; tag<32; tag=tag+1) begin
      request_group(tag); check_group(tag,64,latency);
      if (tag!=0 && latency>2) $fatal(1,"sequential prefetched group missed tag=%0d",tag);
      take_group();
    end
    // Invalidate while a synchronous demand is in flight. The accepted request
    // must finish using the new epoch, never a partially filled old staging set.
    request_group(17);
    while (!(dut.state==2 && dut.fill_word==6)) @(negedge clock);
    old_epoch=epoch; invalidate=1;
    @(posedge clock); #1;
    @(negedge clock); invalidate=0;
    check_group(17,5,latency);
    if (group_epoch!=old_epoch+1) $fatal(1,"inflight stale epoch published");
    take_group();
    // A host read contends with demand/prefetch; arbitration must serve both.
    request_group(10);
    transaction(1,1,80,0,0,expected_bias[80],0);
    check_group(10,64,latency); old_epoch=epoch;
    transaction(0,1,80,31,40'hffffffffff,expected_bias[80],1);
    check_group(10,4,latency);
    if (epoch!=old_epoch) $fatal(1,"rejected parameter write invalidated current data");
    take_group();
    expected_bias[91]={expected_bias[91][39:8],8'h5a};
    transaction(0,0,91,1,40'h5a,expected_bias[91],0);
    request_group(11); check_group(11,5,latency);
    if (group_epoch!=old_epoch+1 || latency==0) $fatal(1,"write reused stale prefetch");
    take_group();
    @(negedge clock); compute_active=1; clear_valid=1;
    repeat (3) begin @(negedge clock); if (clear_ready) $fatal(1,"clear accepted during compute"); end
    clear_valid=0; compute_active=0;
    clear_memory();
    for (addr_i=0; addr_i<256; addr_i=addr_i+1) begin
      expected_bias[addr_i]=0; transaction(1,0,addr_i,0,0,0,0);
    end
    request_group(0); check_group(0,4,latency); take_group();
    // Reset invalidates staging/ownership but preserves SRAM payloads.
    expected_bias[255]=40'h8001234567;
    transaction(0,0,255,31,expected_bias[255],expected_bias[255],0);
    request_group(31); check_group(31,2,latency);
    @(negedge clock); reset=1;
    repeat (3) @(negedge clock);
    if (group_valid || rsp_valid || dut.slot_valid!=0) $fatal(1,"reset retained ownership");
    reset=0;
    transaction(1,0,255,0,0,expected_bias[255],0);
    request_group(31); check_group(31,4,latency); take_group();
    $display("BIAS_PREFETCH_PASS transactions=%0d groups=%0d rmw_reads=%0d physical_writes=%0d source_reads=%0d cycles=%0d",
      transactions,group_checks,rmw_reads,physical_writes,source_reads,cycles);
    $finish;
  end
endmodule
