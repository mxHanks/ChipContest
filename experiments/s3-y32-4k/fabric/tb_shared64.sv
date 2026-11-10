`timescale 1ns/1fs
module tb_shared64;
  reg clk=0, rst_n=0;
  always #3.333333 clk=~clk;
  reg cpu_cmd_valid=0,cpu_cmd_read=1,cpu_rsp_ready=1;
  reg [31:0] cpu_cmd_addr=0,cpu_cmd_wdata=0;
  reg [3:0] cpu_cmd_wmask=4'hf;
  wire cpu_cmd_ready,cpu_rsp_valid,cpu_rsp_err;
  wire [31:0] cpu_rsp_rdata;
  reg dma_cmd_valid=0,dma_cmd_read=1,dma_rsp_ready=1,dma_cmd_is32=0;
  reg [31:0] dma_cmd_addr=0;
  reg [63:0] dma_cmd_wdata=0;
  reg [7:0] dma_cmd_wmask=8'hff;
  wire dma_cmd_ready,dma_rsp_valid,dma_rsp_err;
  wire [63:0] dma_rsp_rdata;
  wire mem_cmd_valid,mem_cmd_ready,mem_cmd_read,mem_cmd_is32;
  wire [31:0] mem_cmd_addr;
  wire [63:0] mem_cmd_wdata;
  wire [7:0] mem_cmd_wmask;
  wire mem_rsp_valid,mem_rsp_ready,mem_rsp_err;
  wire [63:0] mem_rsp_rdata;
  xu_dma64_shared_arb arb(.*);
  xu_shared_icb_sram64 #(.THROTTLE_PERIOD(7),.THROTTLE_RESET_PHASE(2)) endpoint (
    .clk(clk),.rst_n(rst_n),.cmd_valid(mem_cmd_valid),.cmd_ready(mem_cmd_ready),
    .cmd_addr(mem_cmd_addr),.cmd_read(mem_cmd_read),.cmd_wdata(mem_cmd_wdata),
    .cmd_wmask(mem_cmd_wmask),.cmd_is32(mem_cmd_is32),
    .rsp_valid(mem_rsp_valid),.rsp_ready(mem_rsp_ready),.rsp_err(mem_rsp_err),.rsp_rdata(mem_rsp_rdata)
  );
  // Observe only real macro pins, never their storage arrays. Source setup and
  // readback below use the CPU/DMA public interfaces exclusively.
  wire [255:0] actual_macro_reads,actual_macro_writes;
  genvar gb,gl;
  generate for(gb=0;gb<64;gb=gb+1)begin: observe_bank
    for(gl=0;gl<4;gl=gl+1)begin: observe_lane
      assign actual_macro_reads[4*gb+gl]=!endpoint.banks[gb].lanes[gl].u_macro.CEN &&
          endpoint.banks[gb].lanes[gl].u_macro.GWEN;
      assign actual_macro_writes[4*gb+gl]=!endpoint.banks[gb].lanes[gl].u_macro.CEN &&
          !endpoint.banks[gb].lanes[gl].u_macro.GWEN;
      always @(posedge clk) if(rst_n && !endpoint.banks[gb].lanes[gl].u_macro.CEN)begin
        if(endpoint.banks[gb].lanes[gl].u_macro.A!==mem_cmd_addr[12:3]) $fatal(1,"physical macro address");
        if(endpoint.banks[gb].lanes[gl].u_macro.EMA!==3'b010 ||
           endpoint.banks[gb].lanes[gl].u_macro.EMAW!==2'b00 ||
           endpoint.banks[gb].lanes[gl].u_macro.RET1N!==1'b1) $fatal(1,"macro mode changed");
        if(!mem_cmd_read && (endpoint.banks[gb].lanes[gl].u_macro.D!==mem_cmd_wdata[16*gl+:16] ||
           endpoint.banks[gb].lanes[gl].u_macro.WEN!==~{{8{mem_cmd_wmask[2*gl+1]}},{8{mem_cmd_wmask[2*gl]}}}))
          $fatal(1,"physical macro mask/data");
      end
    end
  end endgenerate
  localparam [31:0] BASE=32'ha0000000;
  reg [31:0] expected [0:131071];
  reg initialized [0:131071];
  reg [255:0] macros_read_seen=0,macros_write_seen=0;
  integer cycles=0,accepted=0,retired=0,cancelled=0,error_responses=0,replace_edges=0;
  integer physical_reads=0,physical_writes=0;
  integer measured=0,m_accepted=0,m_retired=0,m_cpu=0;
  // Keep shared process timestamps observable; otherwise Verilator can localize
  // the write-only resets independently in the timing coroutine and scoreboard.
  integer m_start /*verilator public_flat_rw*/ =0;
  integer m_finish /*verilator public_flat_rw*/ =0;
  integer m_last_accept=0,m_interval_sum=0,m_interval_min=1000000,m_interval_max=0;
  integer m_latency_sum=0,m_latency_max=0,m_read_lanes=0,m_write_lanes=0;
  integer m_replacements=0,minimum_accept_gap,maximum_accept_gap;
  reg pending=0,p_owner=0,p_high=0,p_error=0;
  reg [63:0] p_expected=0;
  integer p_accept_cycle=0;
  reg cmd_held=0,rsp_held=0,cpu_held=0,dma_held=0;
  reg [105:0] saved_cmd=0,saved_dma=0;
  reg [68:0] saved_cpu=0;
  reg [64:0] saved_rsp=0;
  wire mem_fire=mem_cmd_valid&&mem_cmd_ready;
  wire cpu_fire=cpu_cmd_valid&&cpu_cmd_ready;
  wire dma_fire=dma_cmd_valid&&dma_cmd_ready;
  wire response_fire=mem_rsp_valid&&mem_rsp_ready;
  wire legal_addr=mem_cmd_addr>=BASE &&
      mem_cmd_addr<=(mem_cmd_is32?32'ha007fffc:32'ha007fff8) &&
      (mem_cmd_is32?mem_cmd_addr[1:0]==0:mem_cmd_addr[2:0]==0);
  wire legal_mask=mem_cmd_read||!mem_cmd_is32||
      (mem_cmd_addr[2]?mem_cmd_wmask[3:0]==0:mem_cmd_wmask[7:4]==0);
  always @(posedge clk)begin: score
    integer index,byte_index,latency,interval,read_ops,write_ops,expected_ops;
    reg [63:0] wanted;
    cycles=cycles+1;
    if(cycles>3000000)$fatal(1,"timeout");
    read_ops=$countones(actual_macro_reads);write_ops=$countones(actual_macro_writes);
    if(!rst_n)begin
      if(pending)cancelled=cancelled+1;
      pending=0;cmd_held=0;rsp_held=0;cpu_held=0;dma_held=0;
      if(cpu_rsp_valid||dma_rsp_valid||mem_cmd_valid||read_ops||write_ops)$fatal(1,"reset interface activity");
    end else begin
      if(cmd_held && (!mem_cmd_valid || saved_cmd!=={mem_cmd_addr,mem_cmd_read,mem_cmd_wdata,mem_cmd_wmask,mem_cmd_is32}))
        $fatal(1,"held shared command changed");
      if(rsp_held && (!mem_rsp_valid || saved_rsp!=={mem_rsp_err,mem_rsp_rdata}))$fatal(1,"held response changed");
      if(cpu_held && (!cpu_cmd_valid || saved_cpu!=={cpu_cmd_addr,cpu_cmd_read,cpu_cmd_wdata,cpu_cmd_wmask}))
        $fatal(1,"held CPU command changed");
      if(dma_held && (!dma_cmd_valid || saved_dma!=={dma_cmd_addr,dma_cmd_read,dma_cmd_wdata,dma_cmd_wmask,dma_cmd_is32}))
        $fatal(1,"held DMA command changed");
      cmd_held=mem_cmd_valid&&!mem_cmd_ready;saved_cmd={mem_cmd_addr,mem_cmd_read,mem_cmd_wdata,mem_cmd_wmask,mem_cmd_is32};
      rsp_held=mem_rsp_valid&&!mem_rsp_ready;saved_rsp={mem_rsp_err,mem_rsp_rdata};
      cpu_held=cpu_cmd_valid&&!cpu_cmd_ready;saved_cpu={cpu_cmd_addr,cpu_cmd_read,cpu_cmd_wdata,cpu_cmd_wmask};
      dma_held=dma_cmd_valid&&!dma_cmd_ready;saved_dma={dma_cmd_addr,dma_cmd_read,dma_cmd_wdata,dma_cmd_wmask,dma_cmd_is32};
      if(cpu_rsp_valid&&dma_rsp_valid)$fatal(1,"two response owners");
      if(mem_rsp_valid)begin
        if(!pending)$fatal(1,"orphan response");
        if(cpu_rsp_valid!==!p_owner || dma_rsp_valid!==p_owner)$fatal(1,"wrong response owner");
        if(mem_rsp_err!==p_error || mem_rsp_rdata!==p_expected)$fatal(1,"response err/data mismatch cyc=%0d got=%h expected=%h",cycles,mem_rsp_rdata,p_expected);
        if(p_owner && (dma_rsp_err!==p_error || dma_rsp_rdata!==p_expected))$fatal(1,"DMA route mismatch");
        if(!p_owner && (cpu_rsp_err!==p_error || cpu_rsp_rdata!==(p_high?p_expected[63:32]:p_expected[31:0])))
          $fatal(1,"CPU half route mismatch");
      end
      if(response_fire)begin
        retired=retired+1;
        if(p_error)error_responses=error_responses+1;
        if(measured!=0 && p_owner)begin
          m_retired=m_retired+1;m_finish=cycles;
          latency=cycles-p_accept_cycle;m_latency_sum=m_latency_sum+latency;
          if(latency>m_latency_max)m_latency_max=latency;
        end
        pending=0;
      end
      if(mem_fire)begin
        if(pending || (cpu_fire&&dma_fire) || (!cpu_fire&&!dma_fire))$fatal(1,"request ownership/occupancy");
        if(response_fire)begin replace_edges=replace_edges+1;if(measured!=0)m_replacements=m_replacements+1;end
        accepted=accepted+1;pending=1;p_owner=dma_fire;p_high=cpu_cmd_addr[2];p_accept_cycle=cycles;
        p_error=!(legal_addr&&legal_mask);p_expected=0;
        if(mem_cmd_is32!==(dma_fire?dma_cmd_is32:1'b1))$fatal(1,"width metadata route");
        if(!dma_fire && (mem_cmd_wdata!==(cpu_cmd_addr[2]?{cpu_cmd_wdata,32'b0}:{32'b0,cpu_cmd_wdata}) ||
           mem_cmd_wmask!==(cpu_cmd_addr[2]?{cpu_cmd_wmask,4'b0}:{4'b0,cpu_cmd_wmask})))$fatal(1,"CPU width adapter");
        if(!p_error)begin
          index=((mem_cmd_addr-BASE)>>2)&32'hfffffffe;
          if(mem_cmd_read)begin
            if(!mem_cmd_is32 || !mem_cmd_addr[2])begin
              if(!initialized[index])$fatal(1,"uninitialized low source read");
              p_expected[31:0]=expected[index];
            end
            if(!mem_cmd_is32 || mem_cmd_addr[2])begin
              if(!initialized[index+1])$fatal(1,"uninitialized high source read");
              p_expected[63:32]=expected[index+1];
            end
            expected_ops=mem_cmd_is32?2:4;
            if(read_ops!=expected_ops || write_ops!=0)$fatal(1,"not a parallel physical read ops=%0d expected=%0d",read_ops,expected_ops);
          end else begin
            expected_ops=0;
            for(byte_index=0;byte_index<4;byte_index=byte_index+1)
              if(|mem_cmd_wmask[2*byte_index+:2])expected_ops=expected_ops+1;
            if(write_ops!=expected_ops || read_ops!=0)$fatal(1,"physical write count/mask");
            for(byte_index=0;byte_index<8;byte_index=byte_index+1)if(mem_cmd_wmask[byte_index])
              expected[index+byte_index/4][8*(byte_index%4)+:8]=mem_cmd_wdata[8*byte_index+:8];
            if(mem_cmd_wmask[3:0]==4'hf)initialized[index]=1;
            if(mem_cmd_wmask[7:4]==4'hf)initialized[index+1]=1;
          end
        end else if(read_ops||write_ops)$fatal(1,"illegal request touched a physical macro");
        if(measured!=0)begin
          if(dma_fire)begin
            if(m_accepted==0)m_start=cycles;
            else begin
              interval=cycles-m_last_accept;m_interval_sum=m_interval_sum+interval;
              if(interval<m_interval_min)m_interval_min=interval;
              if(interval>m_interval_max)m_interval_max=interval;
            end
            m_last_accept=cycles;m_accepted=m_accepted+1;
            m_read_lanes=m_read_lanes+read_ops;m_write_lanes=m_write_lanes+write_ops;
          end else m_cpu=m_cpu+1;
        end
      end else if(read_ops||write_ops)$fatal(1,"physical access without accepted public request");
      physical_reads=physical_reads+read_ops;physical_writes=physical_writes+write_ops;
      macros_read_seen=macros_read_seen|actual_macro_reads;
      macros_write_seen=macros_write_seen|actual_macro_writes;
    end
  end
  function automatic [31:0] init_word(input integer i);
    init_word=32'h9e3779b9*i ^ 32'h6d5a4c31 ^ (i<<11);
  endfunction
  function automatic [31:0] stream_addr(input integer kind,input integer i);
    if(kind==0)stream_addr=i<4096 ? BASE+'h8000+8*i : BASE+'h18000+8*(i-4096);
    else stream_addr=(i%5==0) ? BASE+8*(i/5) : BASE+'h20000+8*(i-i/5-1);
  endfunction
  function automatic stream_read(input integer kind,input integer i);
    stream_read=kind==0 || i%5==0;
  endfunction
  function automatic [63:0] stream_data(input integer i);
    stream_data={init_word(2*i+1),init_word(2*i)}^64'hcafef00d2357abcd;
  endfunction
  task automatic cpu_one(input bit rd,input [31:0] addr,input [31:0] data,input [3:0] mask,input bit err);
    @(negedge clk);cpu_cmd_valid=1;cpu_cmd_read=rd;cpu_cmd_addr=addr;cpu_cmd_wdata=data;cpu_cmd_wmask=mask;
    do @(posedge clk);while(!cpu_cmd_ready);
    @(negedge clk);cpu_cmd_valid=0;
    do @(posedge clk);while(!cpu_rsp_valid);
    if(cpu_rsp_err!==err)$fatal(1,"CPU expected error mismatch");
    @(negedge clk);
  endtask
  task automatic dma_one(input bit rd,input [31:0] addr,input [63:0] data,input [7:0] mask,input bit is32,input bit err);
    @(negedge clk);dma_cmd_valid=1;dma_cmd_read=rd;dma_cmd_addr=addr;dma_cmd_wdata=data;dma_cmd_wmask=mask;dma_cmd_is32=is32;
    do @(posedge clk);while(!dma_cmd_ready);
    @(negedge clk);dma_cmd_valid=0;
    do @(posedge clk);while(!dma_rsp_valid);
    if(dma_rsp_err!==err)$fatal(1,"DMA expected error mismatch");
    @(negedge clk);
  endtask
  task automatic stream(input integer kind,input integer words,input bit contention,input bit backpressure);
    integer duration;
    @(negedge clk);
    measured=kind+1;m_accepted=0;m_retired=0;m_cpu=0;m_start=0;m_finish=0;
    m_last_accept=0;m_interval_sum=0;m_interval_min=1000000;m_interval_max=0;
    m_latency_sum=0;m_latency_max=0;m_read_lanes=0;m_write_lanes=0;m_replacements=0;
    dma_cmd_valid=1;dma_cmd_addr=stream_addr(kind,0);dma_cmd_read=stream_read(kind,0);
    dma_cmd_wdata=stream_data(0);dma_cmd_wmask=8'hff;dma_cmd_is32=0;
    while(m_retired<words || (contention && m_cpu<words) || pending)begin
      @(negedge clk);
      dma_cmd_valid=m_accepted<words;
      dma_cmd_addr=stream_addr(kind,m_accepted);dma_cmd_read=stream_read(kind,m_accepted);dma_cmd_wdata=stream_data(m_accepted);
      // A held CPU request must not disappear when the final DMA beat retires.
      // Submit a bounded independent CPU stream and drain both response owners.
      cpu_cmd_valid=contention && m_cpu<words;cpu_cmd_read=1;cpu_cmd_addr=BASE+'h70004;cpu_cmd_wmask=4'hf;
      dma_rsp_ready=!backpressure || cycles%13<8;
      cpu_rsp_ready=!backpressure || cycles%11<7;
    end
    dma_cmd_valid=0;cpu_cmd_valid=0;dma_rsp_ready=1;cpu_rsp_ready=1;
    while(pending)@(negedge clk);
    duration=m_finish-m_start+1;
    $display("METRIC kind=%0d contention=%0d backpressure=%0d cycles=%0d beats=%0d accepted=%0d retired=%0d cpu_accepted=%0d interval_min=%0d interval_max=%0d interval_sum=%0d latency_sum=%0d latency_max=%0d max_outstanding=1 physical_read_lanes=%0d physical_write_lanes=%0d simultaneous_replace=%0d",kind,contention,backpressure,duration,words,m_accepted,m_retired,m_cpu,m_interval_min,m_interval_max,m_interval_sum,m_latency_sum,m_latency_max,m_read_lanes,m_write_lanes,m_replacements);
    if(m_accepted!=words || m_retired!=words)$fatal(1,"stream incomplete");
    if(!contention&&!backpressure && duration*4>words*5)$fatal(1,"wide fabric exceeds 1.25 cycles/beat");
    if(!contention&&!backpressure && (m_interval_max>2 || m_latency_max!=1))$fatal(1,"unexpected direct endpoint service");
    measured=0;
  endtask
  initial begin: stimulus
    integer i;
    for(i=0;i<131072;i=i+1)begin expected[i]=0;initialized[i]=0;end
    repeat(4)@(negedge clk);rst_n=1;
    // Every physical address is initialized via public CPU32 writes.
    for(i=0;i<131072;i=i+1)cpu_one(0,BASE+4*i,init_word(i),4'hf,0);
    for(i=0;i<65536;i=i+1)dma_one(1,BASE+8*i,0,8'hff,0,0);
    if(macros_read_seen!=={256{1'b1}} || macros_write_seen!=={256{1'b1}})$fatal(1,"macro geometry not covered");
    $display("GEOMETRY_PASS macros=256 bits=4194304 cpu_initialized_words=131072 dma64_readback_beats=65536");
    // All byte masks, both CPU half selections, and routed size32 on wide input.
    for(i=0;i<256;i=i+1)begin
      dma_one(0,BASE+'h70000+8*i,stream_data(i),8'(i),0,0);
      cpu_one(1,BASE+'h70000+8*i,0,4'hf,0);cpu_one(1,BASE+'h70004+8*i,0,4'hf,0);
    end
    for(i=0;i<16;i=i+1)begin
      cpu_one(0,BASE+'h71000+4*i,init_word(i+222),4'(i),0);
      dma_one(1,(BASE+'h71000+4*i)&32'hfffffff8,0,8'hff,0,0);
    end
    dma_one(0,BASE+'h72004,64'h13579bdf00000000,8'hf0,1,0);
    dma_one(1,BASE+'h72004,0,8'h00,1,0);cpu_one(1,BASE+'h72004,0,4'hf,0);
    dma_one(0,BASE+'h72000,64'h000000002468ace0,8'h0f,1,0);
    dma_one(1,BASE+'h72000,0,8'h00,1,0);
    cpu_one(1,BASE+'h7fffc,0,4'hf,0);dma_one(1,BASE+'h7fff8,0,8'hff,0,0);
    cpu_one(0,BASE+2,32'hbadbad01,4'hf,1);cpu_one(1,BASE-4,0,4'hf,1);
    dma_one(0,BASE+4,64'hbadbad02badbad03,8'hff,0,1);
    dma_one(0,BASE+'h7fffc,64'hbadbad04badbad05,8'hff,0,1);
    dma_one(1,BASE+'h80000,0,8'hff,0,1);
    dma_one(0,32'hfffffff8,64'hbadbad06badbad07,8'hff,0,1);
    dma_one(0,BASE+'h72004,64'hbadbad08badbad09,8'hff,1,1);
    cpu_one(1,BASE,0,4'hf,0);cpu_one(1,BASE+4,0,4'hf,0);cpu_one(1,BASE+'h7fffc,0,4'hf,0);
    $display("MASK_ERROR_PASS cpu_masks=16 dma_masks=256 invalid_transactions=7 size32_passthrough=1");
    stream(0,4352,0,0);stream(1,15840,0,0);
    for(i=0;i<25344;i=i+1)cpu_one(1,BASE+'h20000+4*i,0,4'hf,0);
    $display("Y_PUBLIC_READBACK_PASS words=25344");
    stream(0,4352,1,0);stream(1,15840,1,1);
    // Cancel a real held response by resetting endpoint and owner together.
    @(negedge clk);dma_rsp_ready=0;dma_cmd_valid=1;dma_cmd_read=1;dma_cmd_addr=BASE;
    dma_cmd_wmask=8'hff;dma_cmd_is32=0;
    do @(posedge clk);while(!dma_cmd_ready);
    @(negedge clk);dma_cmd_valid=0;
    repeat(4)@(negedge clk);
    if(!dma_rsp_valid)$fatal(1,"held response missing");
    rst_n=0;repeat(3)@(negedge clk);dma_rsp_ready=1;rst_n=1;
    repeat(3)@(negedge clk);
    if(cpu_rsp_valid||dma_rsp_valid||pending)$fatal(1,"stale response after reset");
    cpu_one(1,BASE+4,0,4'hf,0);dma_one(1,BASE,0,8'hff,0,0);
    // Reset a backpressured command before its acceptance; no macro touched.
    @(negedge clk);while(endpoint.phase!=0)@(negedge clk);
    dma_cmd_valid=1;dma_cmd_read=0;dma_cmd_addr=BASE+'h72000;dma_cmd_wdata=64'h1111222233334444;
    @(posedge clk);if(dma_cmd_ready)$fatal(1,"expected throttle hold");
    @(negedge clk);rst_n=0;dma_cmd_valid=0;
    repeat(3)@(negedge clk);rst_n=1;repeat(2)@(negedge clk);
    dma_one(1,BASE+'h72000,0,8'hff,0,0);
    if(pending || accepted-retired!=cancelled || cancelled!=1 || error_responses!=7)
      $fatal(1,"final ownership accounting accept=%0d retire=%0d cancel=%0d errors=%0d",accepted,retired,cancelled,error_responses);
    $display("SHARED64_PROTOCOL_PASS accepted=%0d retired=%0d cancelled=%0d errors=%0d physical_read_lanes=%0d physical_write_lanes=%0d simultaneous_replace=%0d",accepted,retired,cancelled,error_responses,physical_reads,physical_writes,replace_edges);
    $finish;
  end
endmodule
