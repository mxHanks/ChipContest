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
@DECLARATIONS@
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
