`timescale 1ns/1ps
`include "e203_defines.v"
// Real generated 2x8 PE prototype + experimental RNE bridge + production NICE
// serial LSU engine. Public memory bus is a checked backpressure/error fixture.
// This is not the E203 CPU/SoC or a performance proxy for its shared fabric.
module tb_rowpair_nice_real;
  reg clk=0;always #5 clk=~clk;reg rst_n=0;
  reg start=0,second=0,xwen=0,xrow=0,wwen=0,biasvalid=0;
  reg [5:0] xaddr=0;reg [15:0] xdata=0,wdata=0;reg [2:0] wbank=0;reg [10:0] waddr=0;
  reg [7:0] biasaddr=0;reg [39:0] biasdata=0;
  wire active,done,biasready,biasrsp,biaserr,headvalid,headsecond,pop;
  wire [4:0] headgroup;wire [47:0] result[0:7];wire [383:0] raw;
  wire capable=1;wire claim,dvalid,dready,commit,commitready,commiterr;wire [255:0] payload;wire [31:0] status;
  reg req=0,rspready=0;reg [31:0] rs1=0,rs2=0;
  wire reqready,rspvalid,rsperr,cmdvalid,cmdread,busready;wire [31:0] rspdata,cmdaddr,cmddata;wire [1:0] cmdsize;
  integer tick=0,writes=0,responses=0,snapshots=0,pops=0,completions=0,requests=0;
  integer pending_delay=0,write_latency=2,cmd_period=3,fail_write=-1;
  reg pending=0,pending_err=0;
  wire cmdready=!pending&&(tick%cmd_period==0);
  wire busvalid=pending&&pending_delay==0;
  integer rowbase=0,mode=1,local_writes=0,total_cycles=0,launch_tick=0,before_writes=0;
  integer r,g,l,k,c;
  reg vector_mode=0;reg [1023:0] vector_dir;
  reg signed [15:0] vector_x[0:6335],vector_w[0:16383];
  reg signed [39:0] vector_bias[0:255];reg [31:0] vector_y32[0:25343];
  LinearRowPairPrototype core(.clock(clk),.reset(!rst_n),.io_start(start),.io_secondRow(second),
    .io_active(active),.io_done(done),.io_xLoadWen(xwen),.io_xLoadRow(xrow),.io_xLoadAddr(xaddr),.io_xLoadData(xdata),
    .io_wLoadWen(wwen),.io_wLoadBank(wbank),.io_wLoadAddr(waddr),.io_wLoadData(wdata),
    .io_biasHostValid(biasvalid),.io_biasHostReady(biasready),.io_biasHostAddr(biasaddr),.io_biasHostData(biasdata),
    .io_biasRspValid(biasrsp),.io_biasRspError(biaserr),.io_clearValid(1'b0),.io_clearReady(),.io_clearDone(),.io_clearing(),
    .io_outValid(headvalid),.io_outPop(pop),.io_outGroup(headgroup),.io_outSecond(headsecond),
    .io_outResult_0(result[0]),.io_outResult_1(result[1]),.io_outResult_2(result[2]),.io_outResult_3(result[3]),
    .io_outResult_4(result[4]),.io_outResult_5(result[5]),.io_outResult_6(result[6]),.io_outResult_7(result[7]),
    .io_computeStart(),.io_weightRead(),.io_macStep(),.io_fifoFullWait(),.io_clearWeightWrite(),.io_clearXWrite());
  for(genvar i=0;i<8;i=i+1)assign raw[48*i+:48]=result[i];
  rowpair_direct_bridge bridge(.clk(clk),.rst_n(rst_n),.active(active),.head_valid(headvalid),.head_group(headgroup),
    .head_second(headsecond),.head_result(raw),.head_pop(pop),.claim(claim),.valid(dvalid),.ready(dready),
    .payload(payload),.status(status),.commit(commit),.commit_ready(commitready),.commit_err(commiterr));
  xu_nice_drain8 #(.DIRECT_ENABLE(1),.PAIR_ENABLE(1)) nice(
    .nice_clk(clk),.nice_rst_n(rst_n),.nice_active(),.nice_mem_holdup(),.nice_req_valid(req),.nice_req_ready(reqready),
    .nice_req_inst(32'h4a00707b),.nice_req_rs1(rs1),.nice_req_rs2(rs2),.nice_rsp_valid(rspvalid),.nice_rsp_ready(rspready),
    .nice_rsp_rdat(rspdata),.nice_rsp_err(rsperr),.nice_icb_cmd_valid(cmdvalid),.nice_icb_cmd_ready(cmdready),
    .nice_icb_cmd_addr(cmdaddr),.nice_icb_cmd_read(cmdread),.nice_icb_cmd_wdata(cmddata),.nice_icb_cmd_size(cmdsize),
    .nice_icb_rsp_valid(busvalid),.nice_icb_rsp_ready(busready),.nice_icb_rsp_rdata(32'd0),.nice_icb_rsp_err(pending_err),
    .xu_direct_capable(capable),.xu_direct_claim(claim),.xu_direct_valid(dvalid),.xu_direct_ready(dready),
    .xu_direct_payload(payload),.xu_direct_status(status),.xu_direct_commit(commit),
    .xu_direct_commit_ready(commitready),.xu_direct_commit_err(commiterr));
  function automatic signed [15:0] xv(input integer row,input integer index);
    if(vector_mode)xv=vector_x[row*64+index];else if(row%3==0)xv=-32768;else if(row%3==1)xv=32767;else xv=((row*971+index*37)%65536)-32768;
  endfunction
  function automatic signed [15:0] wv(input integer col,input integer index);
    if(vector_mode)wv=vector_w[index*256+col];else if(col%8==0)wv=-32768;else if(col%8==1)wv=32767;else if(col%8>=2&&col%8<=5)wv=0;
    else wv=((col*173+index*811)%65536)-32768;
  endfunction
  function automatic signed [39:0] bv(input integer col);
    if(vector_mode)bv=vector_bias[col];else case(col%8)
      0:bv=40'sh7fffffffff;1:bv=-40'sh8000000000;
      2:bv=-256-512*(col/8);3:bv=-768-512*(col/8);4:bv=256+512*(col/8);5:bv=768+512*(col/8);
      default:bv=((col*7919)%65536)-32768;
    endcase
  endfunction
  function automatic signed [63:0] oracle(input integer row,input integer col);
    reg signed [63:0] sum;reg signed [31:0] product;
    begin sum=bv(col);for(integer i=0;i<64;i=i+1)begin product=xv(row,i)*wv(col,i);sum=sum+product;end oracle=sum;end
  endfunction
  function automatic [31:0] rne_oracle(input signed [63:0] val);
    reg signed [63:0] mag,q,remn;
    begin mag=val<0?-val:val;q=mag/512;remn=mag%512;
      if(remn>256||(remn==256&&q%2))q=q+1;rne_oracle=val<0?-q:q;end
  endfunction
  reg [66:0] held_cmd;reg was_stalled=0;integer output_row,output_col,bundle_idx;
  always @(posedge clk)if(rst_n)begin
    tick=tick+1;
    if(biasrsp&&biaserr)$fatal(1,"bias host error");
    if(req&&reqready)requests=requests+1;
    if(was_stalled&&(!cmdvalid||{cmdaddr,cmdread,cmddata,cmdsize}!==held_cmd))$fatal(1,"write changed under backpressure");
    was_stalled=cmdvalid&&!cmdready;held_cmd={cmdaddr,cmdread,cmddata,cmdsize};
    if(dvalid&&dready)begin
      bundle_idx=local_writes/8;
      if(headgroup!==(bundle_idx/(second?2:1))||headsecond!==(second&&(bundle_idx%2)))$fatal(1,"real FIFO group/row order");
      for(integer i=0;i<8;i=i+1)
        if(payload[32*i+:32]!==rne_oracle(oracle(rowbase+headsecond,headgroup*8+i)))$fatal(1,"real RNE snapshot mismatch");
      snapshots=snapshots+1;
    end
    if(pop)begin if(dvalid&&dready)$fatal(1,"same-edge snapshot/POP");pops=pops+1;end
    if(cmdvalid&&cmdready)begin
      if(cmdread||cmdsize!=2||pending)$fatal(1,"illegal shared-memory transaction");
      bundle_idx=local_writes/8;output_row=rowbase+(second?(bundle_idx%2):0);
      output_col=(bundle_idx/(second?2:1))*8+local_writes%8;
      if(cmdaddr!==32'ha0020000+output_row*1024+output_col*4)$fatal(1,"strided destination mismatch %h r%0d c%0d",cmdaddr,output_row,output_col);
      if(vector_mode&&cmddata!==vector_y32[output_row*256+output_col])$fatal(1,"published task0 Y32 mismatch");
      if(cmddata!==rne_oracle(oracle(output_row,output_col)))$fatal(1,"Y32 write mismatch row%0d col%0d",output_row,output_col);
      pending<=1;pending_delay<=write_latency+(writes%3);pending_err<=writes==fail_write;
      writes=writes+1;local_writes=local_writes+1;
    end else if(pending&&pending_delay>0)pending_delay<=pending_delay-1;
    if(busvalid&&busready)begin pending<=0;pending_err<=0;responses=responses+1;end
    if(rspvalid)begin
      if(pending||writes!=responses)$fatal(1,"completion preceded last write response");
      if((fail_write<0&&rsperr)||(fail_write>=0&&(!rsperr||rspdata!=8)))$fatal(1,"wrong real fixture completion");
    end
    if(rspvalid&&rspready)completions=completions+1;
  end
  task automatic upload_x(input integer row,input bit select);
    begin for(integer i=0;i<64;i=i+1)begin @(negedge clk);xwen=1;xrow=select;xaddr=i;xdata=xv(row,i);end
      @(negedge clk);xwen=0;end
  endtask
  task automatic launch_row(input integer row,input bit two);
    integer guard;
    begin
      rowbase=row;second=two;local_writes=0;
      upload_x(row,0);if(two)upload_x(row+1,1);
      @(negedge clk);start=1;launch_tick=tick;
      @(negedge clk);start=0;req=1;rs1=32'ha0020000+row*1024;rs2=(200000<<11)|(two<<10)|(31<<5);
      @(posedge clk);if(!reqready)$fatal(1,"NICE descriptor blocked");
      @(negedge clk);req=0;guard=0;
      while(!rspvalid)begin @(negedge clk);guard=guard+1;if(guard>200000)$fatal(1,"real fixture timeout");end
      total_cycles=total_cycles+tick-launch_tick;
      repeat(11)begin @(negedge clk);if(!rspvalid||cmdvalid||claim||commit)$fatal(1,"completion did not hold cleanly");end
      rspready=1;@(posedge clk);#1;@(negedge clk);rspready=0;
      if(fail_write<0&&(local_writes!=(two?512:256)||active||headvalid))$fatal(1,"tail/row did not finish exactly");
    end
  endtask
  initial begin
    if($value$plusargs("VECTOR_DIR=%s",vector_dir))begin
      vector_mode=1;
      $readmemh({vector_dir,"/x.mem"},vector_x);$readmemh({vector_dir,"/w.mem"},vector_w);
      $readmemh({vector_dir,"/bias.mem"},vector_bias);$readmemh({vector_dir,"/y32.mem"},vector_y32);
    end
    if($value$plusargs("MODE=%d",mode))begin end
    if($value$plusargs("WRITE_LATENCY=%d",write_latency))begin end
    if($value$plusargs("CMD_PERIOD=%d",cmd_period))begin end
    if($value$plusargs("FAIL_WRITE=%d",fail_write))begin end
    repeat(4)@(negedge clk);rst_n=1;repeat(3)@(negedge clk);
    for(g=0;g<32;g=g+1)for(l=0;l<8;l=l+1)for(k=0;k<64;k=k+1)begin
      @(negedge clk);wwen=1;wbank=l;waddr=g*64+k;wdata=wv(g*8+l,k);
    end
    @(negedge clk);wwen=0;
    for(c=0;c<256;c=c+1)begin
      @(negedge clk);biasvalid=1;biasaddr=c;biasdata=bv(c);
      @(posedge clk);while(!biasready)@(posedge clk);
      @(negedge clk);biasvalid=0;
      while(!biasrsp)@(negedge clk);
    end
    repeat(5)@(negedge clk);
    if(fail_write>=0)begin
      launch_row(0,1);
      if(writes!=fail_write+1||responses!=writes)$fatal(1,"real MAC continued after write error");
      $display("ROWPAIR_NICE_REAL_ERROR_PASS error_index=%0d writes=%0d responses=%0d snapshots=%0d pops=%0d",fail_write,writes,responses,snapshots,pops);$finish;
    end
    for(r=0;r<99;r=r+(mode?2:1))launch_row(r,mode&&r+1<99);
    if(writes!=25344||responses!=25344||snapshots!=3168||pops!=3168||requests!=(mode?50:99)||completions!=requests)
      $fatal(1,"full work count changed");
    $display("ROWPAIR_NICE_REAL_PASS rows=99 outputs=25344 mode=%0d requests=%0d completions=%0d snapshots=%0d pops=%0d writes=%0d responses=%0d compute_drain_cycles=%0d cmd_period=%0d write_latency=%0d vector_mode=%0d",mode,requests,completions,snapshots,pops,writes,responses,total_cycles,cmd_period,write_latency,vector_mode);
    $finish;
  end
  initial begin #100000000;$fatal(1,"global timeout");end
endmodule
