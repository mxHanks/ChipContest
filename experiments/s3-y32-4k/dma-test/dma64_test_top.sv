module dma64_test_top (
 input clk,rst_n,
 input cfg_cmd_valid,output cfg_cmd_ready,input [31:0] cfg_cmd_addr,
 input cfg_cmd_read,input [31:0] cfg_cmd_wdata,input [3:0] cfg_cmd_wmask,
 output cfg_rsp_valid,input cfg_rsp_ready,output cfg_rsp_err,output [31:0] cfg_rsp_rdata,
 input cpu_cmd_valid,output cpu_cmd_ready,input [31:0] cpu_cmd_addr,
 input cpu_cmd_read,input [31:0] cpu_cmd_wdata,input [3:0] cpu_cmd_wmask,
 output cpu_rsp_valid,input cpu_rsp_ready,output cpu_rsp_err,output [31:0] cpu_rsp_rdata,
 input response_enable,inject_error,
 output dma_accept,dma_retire,output dma_read,output [31:0] dma_addr,
 output [31:0] debug_state,debug_pending,debug_locked,debug_coreactive,
 output debug_busy,debug_done,debug_error
);
 wire dma_cmd_valid,dma_cmd_ready,dma_cmd_read;
 wire [31:0] dma_cmd_addr;
 wire [63:0] dma_cmd_wdata,dma_rsp_rdata;
 wire [7:0] dma_cmd_wmask;
 wire dma_rsp_valid,dma_rsp_ready,dma_rsp_err;
 wire mem_cmd_valid,mem_cmd_ready,mem_cmd_read,mem_cmd_is32;
 wire [31:0] mem_cmd_addr;
 wire [63:0] mem_cmd_wdata,mem_rsp_rdata;
 wire [7:0] mem_cmd_wmask;
 wire mem_rsp_valid,mem_rsp_ready,mem_rsp_err;
 wire endpoint_rsp_valid,endpoint_rsp_ready;
 assign mem_rsp_valid=endpoint_rsp_valid&&response_enable;
 assign endpoint_rsp_ready=mem_rsp_ready&&response_enable;
 assign dma_accept=dma_cmd_valid&&dma_cmd_ready;
 assign dma_retire=dma_rsp_valid&&dma_rsp_ready;
 assign dma_read=dma_cmd_read;assign dma_addr=dma_cmd_addr;
 assign debug_state=dma.state;assign debug_pending={31'b0,dma.pending};
 assign debug_locked={31'b0,dma.locked};assign debug_coreactive={31'b0,dma.core_active};
 assign debug_busy=dma.busy;assign debug_done=dma.done;assign debug_error=dma.error;
 xu_matrix_dma64 dma (
  .clk(clk),.rst_n(rst_n),.cfg_cmd_valid(cfg_cmd_valid),.cfg_cmd_ready(cfg_cmd_ready),
  .cfg_cmd_addr(cfg_cmd_addr),.cfg_cmd_read(cfg_cmd_read),.cfg_cmd_wdata(cfg_cmd_wdata),
  .cfg_cmd_wmask(cfg_cmd_wmask),.cfg_rsp_valid(cfg_rsp_valid),.cfg_rsp_ready(cfg_rsp_ready),
  .cfg_rsp_err(cfg_rsp_err),.cfg_rsp_rdata(cfg_rsp_rdata),
  .mem_cmd_valid(dma_cmd_valid),.mem_cmd_ready(dma_cmd_ready),.mem_cmd_addr(dma_cmd_addr),
  .mem_cmd_read(dma_cmd_read),.mem_cmd_wdata(dma_cmd_wdata),.mem_cmd_wmask(dma_cmd_wmask),
  .mem_rsp_valid(dma_rsp_valid),.mem_rsp_ready(dma_rsp_ready),
  .mem_rsp_err(dma_rsp_err||inject_error),.mem_rsp_rdata(dma_rsp_rdata)
 );
 xu_dma64_shared_arb arb (
  .clk(clk),.rst_n(rst_n),.cpu_cmd_valid(cpu_cmd_valid),.cpu_cmd_ready(cpu_cmd_ready),
  .cpu_cmd_addr(cpu_cmd_addr),.cpu_cmd_read(cpu_cmd_read),.cpu_cmd_wdata(cpu_cmd_wdata),
  .cpu_cmd_wmask(cpu_cmd_wmask),.cpu_rsp_valid(cpu_rsp_valid),.cpu_rsp_ready(cpu_rsp_ready),
  .cpu_rsp_err(cpu_rsp_err),.cpu_rsp_rdata(cpu_rsp_rdata),
  .dma_cmd_valid(dma_cmd_valid),.dma_cmd_ready(dma_cmd_ready),.dma_cmd_addr(dma_cmd_addr),
  .dma_cmd_read(dma_cmd_read),.dma_cmd_is32(1'b0),.dma_cmd_wdata(dma_cmd_wdata),
  .dma_cmd_wmask(dma_cmd_wmask),.dma_rsp_valid(dma_rsp_valid),.dma_rsp_ready(dma_rsp_ready),
  .dma_rsp_err(dma_rsp_err),.dma_rsp_rdata(dma_rsp_rdata),
  .mem_cmd_valid(mem_cmd_valid),.mem_cmd_ready(mem_cmd_ready),.mem_cmd_addr(mem_cmd_addr),
  .mem_cmd_read(mem_cmd_read),.mem_cmd_wdata(mem_cmd_wdata),.mem_cmd_wmask(mem_cmd_wmask),
  .mem_cmd_is32(mem_cmd_is32),.mem_rsp_valid(mem_rsp_valid),.mem_rsp_ready(mem_rsp_ready),
  .mem_rsp_err(mem_rsp_err),.mem_rsp_rdata(mem_rsp_rdata)
 );
 xu_shared_icb_sram64 #(.THROTTLE_PERIOD(7),.THROTTLE_RESET_PHASE(2)) endpoint (
  .clk(clk),.rst_n(rst_n),.cmd_valid(mem_cmd_valid),.cmd_ready(mem_cmd_ready),
  .cmd_addr(mem_cmd_addr),.cmd_read(mem_cmd_read),.cmd_wdata(mem_cmd_wdata),
  .cmd_wmask(mem_cmd_wmask),.cmd_is32(mem_cmd_is32),.rsp_valid(endpoint_rsp_valid),
  .rsp_ready(endpoint_rsp_ready),.rsp_err(mem_rsp_err),.rsp_rdata(mem_rsp_rdata)
 );
endmodule
