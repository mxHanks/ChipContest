`timescale 1ns/1ps

// Standalone 32-bit transport proof for the B41 64PE/41-bit tile.
// The memory model exposes only one native 32-bit beat per request and one
// ordered response.  It checks the real X/W/bias load counts and every Y32
// write against the frozen software golden.
module tb_dma32_tile;
  localparam [31:0] CFG_BASE = 32'h10042300;
  localparam [31:0] SHARED  = 32'ha0000000;
  localparam [31:0] X_OFF   = 32'h00000;
  localparam [31:0] W_OFF   = 32'h08000;
  localparam [31:0] B_OFF   = 32'h18000;
  localparam [31:0] Y_OFF   = 32'h20000;

  reg clk=0, rst_n=0;
  always #3.333333 clk = ~clk;

  reg cfg_valid=0, cfg_read=0;
  reg [31:0] cfg_addr=0, cfg_wdata=0;
  reg [3:0] cfg_wmask=4'hf;
  wire cfg_ready, cfg_rsp_valid, cfg_rsp_err;
  wire [31:0] cfg_rsp_rdata;

  wire mem_cmd_valid, mem_cmd_ready, mem_cmd_read;
  wire [31:0] mem_cmd_addr, mem_cmd_wdata;
  wire [3:0] mem_cmd_wmask;
  wire mem_rsp_valid, mem_rsp_ready, mem_rsp_err;
  wire [31:0] mem_rsp_rdata;

  reg [15:0] x [0:6335];
  reg [31:0] packed_w [0:8191];
  reg [39:0] bias [0:255];
  reg [31:0] golden [0:25343];
  reg [31:0] y_mem [0:25343];
  reg y_seen [0:25343];

  reg rsp_pending=0, rsp_read=0, rsp_err_r=0;
  reg [31:0] rsp_addr=0, rsp_wdata=0, rsp_rdata_r=0;
  reg [2:0] phase=3'd2;
  integer cycles=0, reads=0, writes=0, x_reads=0, w_reads=0, b_reads=0, y_writes=0;
  integer max_cycles=6000000;

  assign mem_cmd_ready = (!rsp_pending || mem_rsp_ready) && (phase!=3'd0);
  assign mem_rsp_valid = rsp_pending;
  assign mem_rsp_err = rsp_err_r;
  assign mem_rsp_rdata = rsp_rdata_r;

  xu_matrix_dma32_tile dut (
    .clk(clk), .rst_n(rst_n),
    .cfg_cmd_valid(cfg_valid), .cfg_cmd_ready(cfg_ready),
    .cfg_cmd_addr(cfg_addr), .cfg_cmd_read(cfg_read),
    .cfg_cmd_wdata(cfg_wdata), .cfg_cmd_wmask(cfg_wmask),
    .cfg_rsp_valid(cfg_rsp_valid), .cfg_rsp_ready(1'b1),
    .cfg_rsp_err(cfg_rsp_err), .cfg_rsp_rdata(cfg_rsp_rdata),
    .mem_cmd_valid(mem_cmd_valid), .mem_cmd_ready(mem_cmd_ready),
    .mem_cmd_addr(mem_cmd_addr), .mem_cmd_read(mem_cmd_read),
    .mem_cmd_wdata(mem_cmd_wdata), .mem_cmd_wmask(mem_cmd_wmask),
    .mem_rsp_valid(mem_rsp_valid), .mem_rsp_ready(mem_rsp_ready),
    .mem_rsp_err(mem_rsp_err), .mem_rsp_rdata(mem_rsp_rdata)
  );

  function automatic [31:0] read_word(input [31:0] addr, output reg err);
    integer off, idx;
    begin
      err=0; read_word=32'b0;
      if (addr>=SHARED+X_OFF && addr<SHARED+W_OFF) begin
        off=addr-(SHARED+X_OFF); idx=off>>2;
        if (idx<0 || idx>=3168) err=1;
        else read_word={x[2*idx+1],x[2*idx]};
      end else if (addr>=SHARED+W_OFF && addr<SHARED+B_OFF) begin
        off=addr-(SHARED+W_OFF); idx=off>>2;
        if (idx<0 || idx>=8192) err=1;
        else read_word=packed_w[idx];
      end else if (addr>=SHARED+B_OFF && addr<SHARED+Y_OFF) begin
        off=addr-(SHARED+B_OFF); idx=off>>3;
        if (idx<0 || idx>=256) err=1;
        else if (off[2]) read_word={{24{bias[idx][39]}},bias[idx][39:32]};
        else read_word=bias[idx][31:0];
      end else begin
        err=1;
      end
    end
  endfunction

  always @(posedge clk) begin : memory_model
    reg e;
    integer idx;
    if (!rst_n) begin
      rsp_pending<=0; rsp_err_r<=0; phase<=3'd2;
    end else begin
      cycles<=cycles+1;
      phase <= (phase==3'd6) ? 3'd0 : phase+1'b1;
      if (rsp_pending && mem_rsp_ready) rsp_pending<=0;
      if (mem_cmd_valid && mem_cmd_ready) begin
        if (mem_cmd_wmask!==4'hf) $fatal(1,"non-4-bit mask %h",mem_cmd_wmask);
        rsp_pending<=1; rsp_addr<=mem_cmd_addr; rsp_read<=mem_cmd_read;
        rsp_wdata<=mem_cmd_wdata;
        if (mem_cmd_read) begin
          rsp_rdata_r<=read_word(mem_cmd_addr,e); rsp_err_r<=e;
          if (e) $display("MEM_READ_ERR addr=%h read=%0d state=%0d kind=%0d index=%0d xrow=%0d xissue=%0d xlimit=%0d yaddr=%h run_y=%h",mem_cmd_addr,mem_cmd_read,dut.state,dut.pending_kind,dut.pending_index,dut.x_row,dut.x_issue,dut.x_limit,dut.y_address,dut.run_y);
        end else begin
          rsp_rdata_r<=32'b0; rsp_err_r<=1'b0;
        end
        if (mem_cmd_read) begin
          reads<=reads+1;
          if (mem_cmd_addr>=SHARED+X_OFF && mem_cmd_addr<SHARED+W_OFF) x_reads<=x_reads+1;
          else if (mem_cmd_addr>=SHARED+W_OFF && mem_cmd_addr<SHARED+B_OFF) w_reads<=w_reads+1;
          else if (mem_cmd_addr>=SHARED+B_OFF && mem_cmd_addr<SHARED+Y_OFF) b_reads<=b_reads+1;
        end else begin
          writes<=writes+1;
          if (mem_cmd_addr>=SHARED+Y_OFF && mem_cmd_addr<SHARED+Y_OFF+25344*4) begin
            idx=(mem_cmd_addr-(SHARED+Y_OFF))>>2;
            y_mem[idx]<=mem_cmd_wdata; y_seen[idx]<=1; y_writes<=y_writes+1;
          end else $fatal(1,"unexpected write addr=%h data=%h",mem_cmd_addr,mem_cmd_wdata);
        end
      end
      if (cycles>max_cycles) $fatal(1,"timeout state=%0d reads=%0d writes=%0d",dut.state,reads,writes);
    end
  end

  task automatic cfg_write(input [6:0] off, input [31:0] data);
    begin
      @(negedge clk); cfg_valid=1; cfg_read=0; cfg_addr=CFG_BASE+off; cfg_wdata=data;
      do @(posedge clk); while (!cfg_ready);
      @(negedge clk); cfg_valid=0;
      do @(posedge clk); while (!cfg_rsp_valid);
      if (cfg_rsp_err) $fatal(1,"cfg write error off=%h",off);
    end
  endtask

  task automatic cfg_read_word(input [6:0] off, output [31:0] value);
    begin
      @(negedge clk); cfg_valid=1; cfg_read=1; cfg_addr=CFG_BASE+off; cfg_wdata=0;
      do @(posedge clk); while (!cfg_ready);
      @(negedge clk); cfg_valid=0;
      do @(posedge clk); while (!cfg_rsp_valid);
      if (cfg_rsp_err) $fatal(1,"cfg read error off=%h",off);
      value=cfg_rsp_rdata;
    end
  endtask

  initial begin : test
    integer i, tries; reg [31:0] status;
    string vectors;
    if (!$value$plusargs("VECTORS=%s",vectors)) $fatal(1,"missing +VECTORS");
    $readmemh({vectors,"/x.mem"},x);
    $readmemh({vectors,"/w_packed16.mem"},packed_w);
    $readmemh({vectors,"/bias.mem"},bias);
    $readmemh({vectors,"/y32.mem"},golden);
    for (i=0;i<25344;i=i+1) begin y_mem[i]=32'hdeadbeef; y_seen[i]=0; end
    repeat (8) @(posedge clk);
    rst_n=1;
    cfg_write(7'h04,32'h1);
    for (tries=0;tries<100000;tries=tries+1) begin
      cfg_read_word(7'h08,status);
      if (status[3] && !status[0]) break;
    end
    if (tries==100000) $fatal(1,"clear timeout");
    cfg_write(7'h04,32'h802);
    for (tries=0;tries<max_cycles;tries=tries+1) begin
      cfg_read_word(7'h08,status);
      if (status[2]) begin
        cfg_read_word(7'h0c,status);
        $fatal(1,"DMA error code=%h",status);
      end
      if (status[1] && !status[0]) break;
    end
    if (tries==max_cycles) $fatal(1,"done timeout");
    if (x_reads!=3168 || w_reads!=8192 || b_reads!=512 || y_writes!=25344)
      $fatal(1,"counts x=%0d w=%0d b=%0d y=%0d",x_reads,w_reads,b_reads,y_writes);
    for (i=0;i<25344;i=i+1) begin
      if (!y_seen[i]) $fatal(1,"missing Y %0d",i);
      if (y_mem[i]!==golden[i]) $fatal(1,"Y mismatch %0d got=%h exp=%h",i,y_mem[i],golden[i]);
    end
    $display("DMA32_TILE_PASS cycles=%0d reads=%0d writes=%0d x=%0d w=%0d bias=%0d y=%0d",cycles,reads,writes,x_reads,w_reads,b_reads,y_writes);
    $finish;
  end
endmodule
