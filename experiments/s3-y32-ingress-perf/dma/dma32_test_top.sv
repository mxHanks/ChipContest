// Development unit: original32 arbiter and endpoint over256 real RAMSP macros.
// No CPU/SystemBus execution or official timing/area claim.
module dma32_test_top (
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
 output[2:0]debug_pending_count,
 output debug_busy,debug_done,debug_error
);
 wire dma_cmd_valid,dma_cmd_ready,dma_cmd_read;
 wire [31:0] dma_cmd_addr;
 wire [31:0] dma_cmd_wdata,dma_rsp_rdata;
 wire [3:0] dma_cmd_wmask;
 wire dma_rsp_valid,dma_rsp_ready,dma_rsp_err;
 wire raw_dma_rsp_valid,raw_dma_rsp_ready;
 assign dma_rsp_valid=raw_dma_rsp_valid&&response_enable;
 assign raw_dma_rsp_ready=dma_rsp_ready&&response_enable;
 wire mem_cmd_valid,mem_cmd_ready,mem_cmd_read;
 wire [31:0] mem_cmd_addr;
 wire [31:0] mem_cmd_wdata,mem_rsp_rdata;
 wire [3:0] mem_cmd_wmask;
 wire mem_rsp_valid,mem_rsp_ready,mem_rsp_err;
 wire endpoint_rsp_valid,endpoint_rsp_ready;
 assign mem_rsp_valid=endpoint_rsp_valid&&response_enable;
 assign endpoint_rsp_ready=mem_rsp_ready&&response_enable;
 assign dma_accept=dma_cmd_valid&&dma_cmd_ready;
 assign dma_retire=dma_rsp_valid&&dma_rsp_ready;
 assign dma_read=dma_cmd_read;assign dma_addr=dma_cmd_addr;
 assign debug_pending_count=dma.pending_count;
 assign debug_state=dma.state;assign debug_pending={31'b0,dma.pending};
 assign debug_locked={31'b0,dma.locked};assign debug_coreactive={31'b0,dma.core_active};
 assign debug_busy=dma.busy;assign debug_done=dma.done;assign debug_error=dma.error;
 xu_matrix_dma_sysbus32 dma (
  .clk(clk),.rst_n(rst_n),.cfg_cmd_valid(cfg_cmd_valid),.cfg_cmd_ready(cfg_cmd_ready),
  .cfg_cmd_addr(cfg_cmd_addr),.cfg_cmd_read(cfg_cmd_read),.cfg_cmd_wdata(cfg_cmd_wdata),
  .cfg_cmd_wmask(cfg_cmd_wmask),.cfg_rsp_valid(cfg_rsp_valid),.cfg_rsp_ready(cfg_rsp_ready),
  .cfg_rsp_err(cfg_rsp_err),.cfg_rsp_rdata(cfg_rsp_rdata),
  .mem_cmd_valid(dma_cmd_valid),.mem_cmd_ready(dma_cmd_ready),.mem_cmd_addr(dma_cmd_addr),
  .mem_cmd_read(dma_cmd_read),.mem_cmd_wdata(dma_cmd_wdata),.mem_cmd_wmask(dma_cmd_wmask),
  .mem_rsp_valid(dma_rsp_valid),.mem_rsp_ready(dma_rsp_ready),
  .mem_rsp_err(dma_rsp_err||inject_error),.mem_rsp_rdata(dma_rsp_rdata)
 );
 wire bus_cmd_valid,bus_cmd_ready,bus_cmd_read,bus_rsp_valid,bus_rsp_ready,bus_rsp_err;
 wire[31:0]bus_cmd_addr,bus_cmd_wdata,bus_rsp_rdata;wire[3:0]bus_cmd_wmask;
 xu_systembus_ingress32 #(.TEST_LOADER(0)) arb (
  .clk(clk),.rst_n(rst_n),.cpu_cmd_valid(cpu_cmd_valid),.cpu_cmd_ready(cpu_cmd_ready),
  .cpu_cmd_addr(cpu_cmd_addr),.cpu_cmd_read(cpu_cmd_read),.cpu_cmd_wdata(cpu_cmd_wdata),
  .cpu_cmd_wmask(cpu_cmd_wmask),.cpu_rsp_valid(cpu_rsp_valid),.cpu_rsp_ready(cpu_rsp_ready),
  .cpu_rsp_err(cpu_rsp_err),.cpu_rsp_rdata(cpu_rsp_rdata),
  .dma_cmd_valid(dma_cmd_valid),.dma_cmd_ready(dma_cmd_ready),.dma_cmd_addr(dma_cmd_addr),
  .dma_cmd_read(dma_cmd_read),.dma_cmd_wdata(dma_cmd_wdata),
  .dma_cmd_wmask(dma_cmd_wmask),.dma_rsp_valid(raw_dma_rsp_valid),.dma_rsp_ready(raw_dma_rsp_ready),
  .dma_rsp_err(dma_rsp_err),.dma_rsp_rdata(dma_rsp_rdata),
  .load_cmd_valid(1'b0),.load_cmd_ready(),.load_cmd_addr(32'b0),.load_cmd_read(1'b0),
  .load_cmd_wdata(32'b0),.load_cmd_wmask(4'b0),.load_rsp_valid(),.load_rsp_ready(1'b1),.load_rsp_err(),.load_rsp_rdata(),
  .bus_cmd_valid(bus_cmd_valid),.bus_cmd_ready(bus_cmd_ready),.bus_cmd_addr(bus_cmd_addr),
  .bus_cmd_read(bus_cmd_read),.bus_cmd_wdata(bus_cmd_wdata),.bus_cmd_wmask(bus_cmd_wmask),
  .bus_rsp_valid(bus_rsp_valid),.bus_rsp_ready(bus_rsp_ready),.bus_rsp_err(bus_rsp_err),.bus_rsp_rdata(bus_rsp_rdata)
 );
 // Exact existing mem_fab primitive and frozen parameter values.
 sirv_icb1to8_bus #(.ICB_FIFO_DP(2),.ICB_FIFO_CUT_READY(1),.SPLT_FIFO_OUTS_NUM(1),.SPLT_FIFO_CUT_READY(1),
   .O4_BASE_ADDR(32'h80000000),.O4_BASE_REGION_LSB(31)) fabric (
  .clk(clk),.rst_n(rst_n),.o0_icb_enable(1'b0),.o1_icb_enable(1'b0),.o2_icb_enable(1'b0),.o3_icb_enable(1'b0),
  .o4_icb_enable(1'b1),.o5_icb_enable(1'b0),.o6_icb_enable(1'b0),.o7_icb_enable(1'b0),
  .i_icb_cmd_valid(bus_cmd_valid),.i_icb_cmd_ready(bus_cmd_ready),.i_icb_cmd_addr(bus_cmd_addr),
  .i_icb_cmd_read(bus_cmd_read),.i_icb_cmd_wdata(bus_cmd_wdata),.i_icb_cmd_wmask(bus_cmd_wmask),
  .i_icb_cmd_burst(2'b0),.i_icb_cmd_beat(2'b0),.i_icb_cmd_lock(1'b0),.i_icb_cmd_excl(1'b0),.i_icb_cmd_size(2'b10),
  .i_icb_rsp_valid(bus_rsp_valid),.i_icb_rsp_ready(bus_rsp_ready),.i_icb_rsp_err(bus_rsp_err),.i_icb_rsp_rdata(bus_rsp_rdata),
  .o4_icb_cmd_valid(mem_cmd_valid),.o4_icb_cmd_ready(mem_cmd_ready),.o4_icb_cmd_addr(mem_cmd_addr),
  .o4_icb_cmd_read(mem_cmd_read),.o4_icb_cmd_wdata(mem_cmd_wdata),.o4_icb_cmd_wmask(mem_cmd_wmask),
  .o4_icb_rsp_valid(mem_rsp_valid),.o4_icb_rsp_ready(mem_rsp_ready),.o4_icb_rsp_err(mem_rsp_err),
  .o4_icb_rsp_excl_ok(1'b0),.o4_icb_rsp_rdata(mem_rsp_rdata));
 xu_shared_icb_sram #(.THROTTLE_RESET_PHASE(2)) endpoint (
  .clk(clk),.rst_n(rst_n),.cmd_valid(mem_cmd_valid),.cmd_ready(mem_cmd_ready),
  .cmd_addr(mem_cmd_addr),.cmd_read(mem_cmd_read),.cmd_wdata(mem_cmd_wdata),
  .cmd_wmask(mem_cmd_wmask),.rsp_valid(endpoint_rsp_valid),
  .rsp_ready(endpoint_rsp_ready),.rsp_err(mem_rsp_err),.rsp_rdata(mem_rsp_rdata)
 );
endmodule
