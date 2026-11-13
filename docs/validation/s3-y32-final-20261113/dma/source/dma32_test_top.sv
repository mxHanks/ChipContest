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
wire [53:0] sm_en,sm_wr,sm_ret;
wire [539:0] sm_addr;
wire [863:0] sm_data,sm_wen;
assign sm_en[0]=!dma.u_core.weights.banks_0.sram0.mem_ext.macro.CEN;
assign sm_wr[0]=!dma.u_core.weights.banks_0.sram0.mem_ext.macro.GWEN;
assign sm_ret[0]=dma.u_core.weights.banks_0.sram0.mem_ext.macro.RET1N;
assign sm_addr[0+:10]=dma.u_core.weights.banks_0.sram0.mem_ext.macro.A;
assign sm_data[0+:16]=dma.u_core.weights.banks_0.sram0.mem_ext.macro.D;
assign sm_wen[0+:16]=dma.u_core.weights.banks_0.sram0.mem_ext.macro.WEN;
assign sm_en[1]=!dma.u_core.weights.banks_0.sram1.mem_ext.macro.CEN;
assign sm_wr[1]=!dma.u_core.weights.banks_0.sram1.mem_ext.macro.GWEN;
assign sm_ret[1]=dma.u_core.weights.banks_0.sram1.mem_ext.macro.RET1N;
assign sm_addr[10+:10]=dma.u_core.weights.banks_0.sram1.mem_ext.macro.A;
assign sm_data[16+:16]=dma.u_core.weights.banks_0.sram1.mem_ext.macro.D;
assign sm_wen[16+:16]=dma.u_core.weights.banks_0.sram1.mem_ext.macro.WEN;
assign sm_en[2]=!dma.u_core.weights.banks_1.sram0.mem_ext.macro.CEN;
assign sm_wr[2]=!dma.u_core.weights.banks_1.sram0.mem_ext.macro.GWEN;
assign sm_ret[2]=dma.u_core.weights.banks_1.sram0.mem_ext.macro.RET1N;
assign sm_addr[20+:10]=dma.u_core.weights.banks_1.sram0.mem_ext.macro.A;
assign sm_data[32+:16]=dma.u_core.weights.banks_1.sram0.mem_ext.macro.D;
assign sm_wen[32+:16]=dma.u_core.weights.banks_1.sram0.mem_ext.macro.WEN;
assign sm_en[3]=!dma.u_core.weights.banks_1.sram1.mem_ext.macro.CEN;
assign sm_wr[3]=!dma.u_core.weights.banks_1.sram1.mem_ext.macro.GWEN;
assign sm_ret[3]=dma.u_core.weights.banks_1.sram1.mem_ext.macro.RET1N;
assign sm_addr[30+:10]=dma.u_core.weights.banks_1.sram1.mem_ext.macro.A;
assign sm_data[48+:16]=dma.u_core.weights.banks_1.sram1.mem_ext.macro.D;
assign sm_wen[48+:16]=dma.u_core.weights.banks_1.sram1.mem_ext.macro.WEN;
assign sm_en[4]=!dma.u_core.weights.banks_2.sram0.mem_ext.macro.CEN;
assign sm_wr[4]=!dma.u_core.weights.banks_2.sram0.mem_ext.macro.GWEN;
assign sm_ret[4]=dma.u_core.weights.banks_2.sram0.mem_ext.macro.RET1N;
assign sm_addr[40+:10]=dma.u_core.weights.banks_2.sram0.mem_ext.macro.A;
assign sm_data[64+:16]=dma.u_core.weights.banks_2.sram0.mem_ext.macro.D;
assign sm_wen[64+:16]=dma.u_core.weights.banks_2.sram0.mem_ext.macro.WEN;
assign sm_en[5]=!dma.u_core.weights.banks_2.sram1.mem_ext.macro.CEN;
assign sm_wr[5]=!dma.u_core.weights.banks_2.sram1.mem_ext.macro.GWEN;
assign sm_ret[5]=dma.u_core.weights.banks_2.sram1.mem_ext.macro.RET1N;
assign sm_addr[50+:10]=dma.u_core.weights.banks_2.sram1.mem_ext.macro.A;
assign sm_data[80+:16]=dma.u_core.weights.banks_2.sram1.mem_ext.macro.D;
assign sm_wen[80+:16]=dma.u_core.weights.banks_2.sram1.mem_ext.macro.WEN;
assign sm_en[6]=!dma.u_core.weights.banks_3.sram0.mem_ext.macro.CEN;
assign sm_wr[6]=!dma.u_core.weights.banks_3.sram0.mem_ext.macro.GWEN;
assign sm_ret[6]=dma.u_core.weights.banks_3.sram0.mem_ext.macro.RET1N;
assign sm_addr[60+:10]=dma.u_core.weights.banks_3.sram0.mem_ext.macro.A;
assign sm_data[96+:16]=dma.u_core.weights.banks_3.sram0.mem_ext.macro.D;
assign sm_wen[96+:16]=dma.u_core.weights.banks_3.sram0.mem_ext.macro.WEN;
assign sm_en[7]=!dma.u_core.weights.banks_3.sram1.mem_ext.macro.CEN;
assign sm_wr[7]=!dma.u_core.weights.banks_3.sram1.mem_ext.macro.GWEN;
assign sm_ret[7]=dma.u_core.weights.banks_3.sram1.mem_ext.macro.RET1N;
assign sm_addr[70+:10]=dma.u_core.weights.banks_3.sram1.mem_ext.macro.A;
assign sm_data[112+:16]=dma.u_core.weights.banks_3.sram1.mem_ext.macro.D;
assign sm_wen[112+:16]=dma.u_core.weights.banks_3.sram1.mem_ext.macro.WEN;
assign sm_en[8]=!dma.u_core.weights.banks_4.sram0.mem_ext.macro.CEN;
assign sm_wr[8]=!dma.u_core.weights.banks_4.sram0.mem_ext.macro.GWEN;
assign sm_ret[8]=dma.u_core.weights.banks_4.sram0.mem_ext.macro.RET1N;
assign sm_addr[80+:10]=dma.u_core.weights.banks_4.sram0.mem_ext.macro.A;
assign sm_data[128+:16]=dma.u_core.weights.banks_4.sram0.mem_ext.macro.D;
assign sm_wen[128+:16]=dma.u_core.weights.banks_4.sram0.mem_ext.macro.WEN;
assign sm_en[9]=!dma.u_core.weights.banks_4.sram1.mem_ext.macro.CEN;
assign sm_wr[9]=!dma.u_core.weights.banks_4.sram1.mem_ext.macro.GWEN;
assign sm_ret[9]=dma.u_core.weights.banks_4.sram1.mem_ext.macro.RET1N;
assign sm_addr[90+:10]=dma.u_core.weights.banks_4.sram1.mem_ext.macro.A;
assign sm_data[144+:16]=dma.u_core.weights.banks_4.sram1.mem_ext.macro.D;
assign sm_wen[144+:16]=dma.u_core.weights.banks_4.sram1.mem_ext.macro.WEN;
assign sm_en[10]=!dma.u_core.weights.banks_5.sram0.mem_ext.macro.CEN;
assign sm_wr[10]=!dma.u_core.weights.banks_5.sram0.mem_ext.macro.GWEN;
assign sm_ret[10]=dma.u_core.weights.banks_5.sram0.mem_ext.macro.RET1N;
assign sm_addr[100+:10]=dma.u_core.weights.banks_5.sram0.mem_ext.macro.A;
assign sm_data[160+:16]=dma.u_core.weights.banks_5.sram0.mem_ext.macro.D;
assign sm_wen[160+:16]=dma.u_core.weights.banks_5.sram0.mem_ext.macro.WEN;
assign sm_en[11]=!dma.u_core.weights.banks_5.sram1.mem_ext.macro.CEN;
assign sm_wr[11]=!dma.u_core.weights.banks_5.sram1.mem_ext.macro.GWEN;
assign sm_ret[11]=dma.u_core.weights.banks_5.sram1.mem_ext.macro.RET1N;
assign sm_addr[110+:10]=dma.u_core.weights.banks_5.sram1.mem_ext.macro.A;
assign sm_data[176+:16]=dma.u_core.weights.banks_5.sram1.mem_ext.macro.D;
assign sm_wen[176+:16]=dma.u_core.weights.banks_5.sram1.mem_ext.macro.WEN;
assign sm_en[12]=!dma.u_core.weights.banks_6.sram0.mem_ext.macro.CEN;
assign sm_wr[12]=!dma.u_core.weights.banks_6.sram0.mem_ext.macro.GWEN;
assign sm_ret[12]=dma.u_core.weights.banks_6.sram0.mem_ext.macro.RET1N;
assign sm_addr[120+:10]=dma.u_core.weights.banks_6.sram0.mem_ext.macro.A;
assign sm_data[192+:16]=dma.u_core.weights.banks_6.sram0.mem_ext.macro.D;
assign sm_wen[192+:16]=dma.u_core.weights.banks_6.sram0.mem_ext.macro.WEN;
assign sm_en[13]=!dma.u_core.weights.banks_6.sram1.mem_ext.macro.CEN;
assign sm_wr[13]=!dma.u_core.weights.banks_6.sram1.mem_ext.macro.GWEN;
assign sm_ret[13]=dma.u_core.weights.banks_6.sram1.mem_ext.macro.RET1N;
assign sm_addr[130+:10]=dma.u_core.weights.banks_6.sram1.mem_ext.macro.A;
assign sm_data[208+:16]=dma.u_core.weights.banks_6.sram1.mem_ext.macro.D;
assign sm_wen[208+:16]=dma.u_core.weights.banks_6.sram1.mem_ext.macro.WEN;
assign sm_en[14]=!dma.u_core.weights.banks_7.sram0.mem_ext.macro.CEN;
assign sm_wr[14]=!dma.u_core.weights.banks_7.sram0.mem_ext.macro.GWEN;
assign sm_ret[14]=dma.u_core.weights.banks_7.sram0.mem_ext.macro.RET1N;
assign sm_addr[140+:10]=dma.u_core.weights.banks_7.sram0.mem_ext.macro.A;
assign sm_data[224+:16]=dma.u_core.weights.banks_7.sram0.mem_ext.macro.D;
assign sm_wen[224+:16]=dma.u_core.weights.banks_7.sram0.mem_ext.macro.WEN;
assign sm_en[15]=!dma.u_core.weights.banks_7.sram1.mem_ext.macro.CEN;
assign sm_wr[15]=!dma.u_core.weights.banks_7.sram1.mem_ext.macro.GWEN;
assign sm_ret[15]=dma.u_core.weights.banks_7.sram1.mem_ext.macro.RET1N;
assign sm_addr[150+:10]=dma.u_core.weights.banks_7.sram1.mem_ext.macro.A;
assign sm_data[240+:16]=dma.u_core.weights.banks_7.sram1.mem_ext.macro.D;
assign sm_wen[240+:16]=dma.u_core.weights.banks_7.sram1.mem_ext.macro.WEN;
assign sm_en[16]=!dma.u_core.biasMemory.mem_ext.macro.CEN;
assign sm_wr[16]=!dma.u_core.biasMemory.mem_ext.macro.GWEN;
assign sm_ret[16]=dma.u_core.biasMemory.mem_ext.macro.RET1N;
assign sm_addr[160+:10]=dma.u_core.biasMemory.mem_ext.macro.A;
assign sm_data[256+:16]=dma.u_core.biasMemory.mem_ext.macro.D;
assign sm_wen[256+:16]=dma.u_core.biasMemory.mem_ext.macro.WEN;
assign sm_en[17]=!dma.u_core.xSets[0].rows[0].memory.memory.mem_ext.macro.CEN;
assign sm_wr[17]=!dma.u_core.xSets[0].rows[0].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[17]=dma.u_core.xSets[0].rows[0].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[170+:10]=dma.u_core.xSets[0].rows[0].memory.memory.mem_ext.macro.A;
assign sm_data[272+:16]=dma.u_core.xSets[0].rows[0].memory.memory.mem_ext.macro.D;
assign sm_wen[272+:16]=dma.u_core.xSets[0].rows[0].memory.memory.mem_ext.macro.WEN;
assign sm_en[18]=!dma.u_core.xSets[0].rows[1].memory.memory.mem_ext.macro.CEN;
assign sm_wr[18]=!dma.u_core.xSets[0].rows[1].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[18]=dma.u_core.xSets[0].rows[1].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[180+:10]=dma.u_core.xSets[0].rows[1].memory.memory.mem_ext.macro.A;
assign sm_data[288+:16]=dma.u_core.xSets[0].rows[1].memory.memory.mem_ext.macro.D;
assign sm_wen[288+:16]=dma.u_core.xSets[0].rows[1].memory.memory.mem_ext.macro.WEN;
assign sm_en[19]=!dma.u_core.xSets[0].rows[2].memory.memory.mem_ext.macro.CEN;
assign sm_wr[19]=!dma.u_core.xSets[0].rows[2].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[19]=dma.u_core.xSets[0].rows[2].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[190+:10]=dma.u_core.xSets[0].rows[2].memory.memory.mem_ext.macro.A;
assign sm_data[304+:16]=dma.u_core.xSets[0].rows[2].memory.memory.mem_ext.macro.D;
assign sm_wen[304+:16]=dma.u_core.xSets[0].rows[2].memory.memory.mem_ext.macro.WEN;
assign sm_en[20]=!dma.u_core.xSets[0].rows[3].memory.memory.mem_ext.macro.CEN;
assign sm_wr[20]=!dma.u_core.xSets[0].rows[3].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[20]=dma.u_core.xSets[0].rows[3].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[200+:10]=dma.u_core.xSets[0].rows[3].memory.memory.mem_ext.macro.A;
assign sm_data[320+:16]=dma.u_core.xSets[0].rows[3].memory.memory.mem_ext.macro.D;
assign sm_wen[320+:16]=dma.u_core.xSets[0].rows[3].memory.memory.mem_ext.macro.WEN;
assign sm_en[21]=!dma.u_core.xSets[0].rows[4].memory.memory.mem_ext.macro.CEN;
assign sm_wr[21]=!dma.u_core.xSets[0].rows[4].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[21]=dma.u_core.xSets[0].rows[4].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[210+:10]=dma.u_core.xSets[0].rows[4].memory.memory.mem_ext.macro.A;
assign sm_data[336+:16]=dma.u_core.xSets[0].rows[4].memory.memory.mem_ext.macro.D;
assign sm_wen[336+:16]=dma.u_core.xSets[0].rows[4].memory.memory.mem_ext.macro.WEN;
assign sm_en[22]=!dma.u_core.xSets[0].rows[5].memory.memory.mem_ext.macro.CEN;
assign sm_wr[22]=!dma.u_core.xSets[0].rows[5].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[22]=dma.u_core.xSets[0].rows[5].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[220+:10]=dma.u_core.xSets[0].rows[5].memory.memory.mem_ext.macro.A;
assign sm_data[352+:16]=dma.u_core.xSets[0].rows[5].memory.memory.mem_ext.macro.D;
assign sm_wen[352+:16]=dma.u_core.xSets[0].rows[5].memory.memory.mem_ext.macro.WEN;
assign sm_en[23]=!dma.u_core.xSets[0].rows[6].memory.memory.mem_ext.macro.CEN;
assign sm_wr[23]=!dma.u_core.xSets[0].rows[6].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[23]=dma.u_core.xSets[0].rows[6].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[230+:10]=dma.u_core.xSets[0].rows[6].memory.memory.mem_ext.macro.A;
assign sm_data[368+:16]=dma.u_core.xSets[0].rows[6].memory.memory.mem_ext.macro.D;
assign sm_wen[368+:16]=dma.u_core.xSets[0].rows[6].memory.memory.mem_ext.macro.WEN;
assign sm_en[24]=!dma.u_core.xSets[0].rows[7].memory.memory.mem_ext.macro.CEN;
assign sm_wr[24]=!dma.u_core.xSets[0].rows[7].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[24]=dma.u_core.xSets[0].rows[7].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[240+:10]=dma.u_core.xSets[0].rows[7].memory.memory.mem_ext.macro.A;
assign sm_data[384+:16]=dma.u_core.xSets[0].rows[7].memory.memory.mem_ext.macro.D;
assign sm_wen[384+:16]=dma.u_core.xSets[0].rows[7].memory.memory.mem_ext.macro.WEN;
assign sm_en[25]=!dma.u_core.xSets[1].rows[0].memory.memory.mem_ext.macro.CEN;
assign sm_wr[25]=!dma.u_core.xSets[1].rows[0].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[25]=dma.u_core.xSets[1].rows[0].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[250+:10]=dma.u_core.xSets[1].rows[0].memory.memory.mem_ext.macro.A;
assign sm_data[400+:16]=dma.u_core.xSets[1].rows[0].memory.memory.mem_ext.macro.D;
assign sm_wen[400+:16]=dma.u_core.xSets[1].rows[0].memory.memory.mem_ext.macro.WEN;
assign sm_en[26]=!dma.u_core.xSets[1].rows[1].memory.memory.mem_ext.macro.CEN;
assign sm_wr[26]=!dma.u_core.xSets[1].rows[1].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[26]=dma.u_core.xSets[1].rows[1].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[260+:10]=dma.u_core.xSets[1].rows[1].memory.memory.mem_ext.macro.A;
assign sm_data[416+:16]=dma.u_core.xSets[1].rows[1].memory.memory.mem_ext.macro.D;
assign sm_wen[416+:16]=dma.u_core.xSets[1].rows[1].memory.memory.mem_ext.macro.WEN;
assign sm_en[27]=!dma.u_core.xSets[1].rows[2].memory.memory.mem_ext.macro.CEN;
assign sm_wr[27]=!dma.u_core.xSets[1].rows[2].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[27]=dma.u_core.xSets[1].rows[2].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[270+:10]=dma.u_core.xSets[1].rows[2].memory.memory.mem_ext.macro.A;
assign sm_data[432+:16]=dma.u_core.xSets[1].rows[2].memory.memory.mem_ext.macro.D;
assign sm_wen[432+:16]=dma.u_core.xSets[1].rows[2].memory.memory.mem_ext.macro.WEN;
assign sm_en[28]=!dma.u_core.xSets[1].rows[3].memory.memory.mem_ext.macro.CEN;
assign sm_wr[28]=!dma.u_core.xSets[1].rows[3].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[28]=dma.u_core.xSets[1].rows[3].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[280+:10]=dma.u_core.xSets[1].rows[3].memory.memory.mem_ext.macro.A;
assign sm_data[448+:16]=dma.u_core.xSets[1].rows[3].memory.memory.mem_ext.macro.D;
assign sm_wen[448+:16]=dma.u_core.xSets[1].rows[3].memory.memory.mem_ext.macro.WEN;
assign sm_en[29]=!dma.u_core.xSets[1].rows[4].memory.memory.mem_ext.macro.CEN;
assign sm_wr[29]=!dma.u_core.xSets[1].rows[4].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[29]=dma.u_core.xSets[1].rows[4].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[290+:10]=dma.u_core.xSets[1].rows[4].memory.memory.mem_ext.macro.A;
assign sm_data[464+:16]=dma.u_core.xSets[1].rows[4].memory.memory.mem_ext.macro.D;
assign sm_wen[464+:16]=dma.u_core.xSets[1].rows[4].memory.memory.mem_ext.macro.WEN;
assign sm_en[30]=!dma.u_core.xSets[1].rows[5].memory.memory.mem_ext.macro.CEN;
assign sm_wr[30]=!dma.u_core.xSets[1].rows[5].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[30]=dma.u_core.xSets[1].rows[5].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[300+:10]=dma.u_core.xSets[1].rows[5].memory.memory.mem_ext.macro.A;
assign sm_data[480+:16]=dma.u_core.xSets[1].rows[5].memory.memory.mem_ext.macro.D;
assign sm_wen[480+:16]=dma.u_core.xSets[1].rows[5].memory.memory.mem_ext.macro.WEN;
assign sm_en[31]=!dma.u_core.xSets[1].rows[6].memory.memory.mem_ext.macro.CEN;
assign sm_wr[31]=!dma.u_core.xSets[1].rows[6].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[31]=dma.u_core.xSets[1].rows[6].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[310+:10]=dma.u_core.xSets[1].rows[6].memory.memory.mem_ext.macro.A;
assign sm_data[496+:16]=dma.u_core.xSets[1].rows[6].memory.memory.mem_ext.macro.D;
assign sm_wen[496+:16]=dma.u_core.xSets[1].rows[6].memory.memory.mem_ext.macro.WEN;
assign sm_en[32]=!dma.u_core.xSets[1].rows[7].memory.memory.mem_ext.macro.CEN;
assign sm_wr[32]=!dma.u_core.xSets[1].rows[7].memory.memory.mem_ext.macro.GWEN;
assign sm_ret[32]=dma.u_core.xSets[1].rows[7].memory.memory.mem_ext.macro.RET1N;
assign sm_addr[320+:10]=dma.u_core.xSets[1].rows[7].memory.memory.mem_ext.macro.A;
assign sm_data[512+:16]=dma.u_core.xSets[1].rows[7].memory.memory.mem_ext.macro.D;
assign sm_wen[512+:16]=dma.u_core.xSets[1].rows[7].memory.memory.mem_ext.macro.WEN;
assign sm_en[33]=!dma.u_core.resultSlices[0].memory.mem_ext.macro.CEN;
assign sm_wr[33]=!dma.u_core.resultSlices[0].memory.mem_ext.macro.GWEN;
assign sm_ret[33]=dma.u_core.resultSlices[0].memory.mem_ext.macro.RET1N;
assign sm_addr[330+:10]=dma.u_core.resultSlices[0].memory.mem_ext.macro.A;
assign sm_data[528+:16]=dma.u_core.resultSlices[0].memory.mem_ext.macro.D;
assign sm_wen[528+:16]=dma.u_core.resultSlices[0].memory.mem_ext.macro.WEN;
assign sm_en[34]=!dma.u_core.resultSlices[1].memory.mem_ext.macro.CEN;
assign sm_wr[34]=!dma.u_core.resultSlices[1].memory.mem_ext.macro.GWEN;
assign sm_ret[34]=dma.u_core.resultSlices[1].memory.mem_ext.macro.RET1N;
assign sm_addr[340+:10]=dma.u_core.resultSlices[1].memory.mem_ext.macro.A;
assign sm_data[544+:16]=dma.u_core.resultSlices[1].memory.mem_ext.macro.D;
assign sm_wen[544+:16]=dma.u_core.resultSlices[1].memory.mem_ext.macro.WEN;
assign sm_en[35]=!dma.u_core.resultSlices[2].memory.mem_ext.macro.CEN;
assign sm_wr[35]=!dma.u_core.resultSlices[2].memory.mem_ext.macro.GWEN;
assign sm_ret[35]=dma.u_core.resultSlices[2].memory.mem_ext.macro.RET1N;
assign sm_addr[350+:10]=dma.u_core.resultSlices[2].memory.mem_ext.macro.A;
assign sm_data[560+:16]=dma.u_core.resultSlices[2].memory.mem_ext.macro.D;
assign sm_wen[560+:16]=dma.u_core.resultSlices[2].memory.mem_ext.macro.WEN;
assign sm_en[36]=!dma.u_core.resultSlices[3].memory.mem_ext.macro.CEN;
assign sm_wr[36]=!dma.u_core.resultSlices[3].memory.mem_ext.macro.GWEN;
assign sm_ret[36]=dma.u_core.resultSlices[3].memory.mem_ext.macro.RET1N;
assign sm_addr[360+:10]=dma.u_core.resultSlices[3].memory.mem_ext.macro.A;
assign sm_data[576+:16]=dma.u_core.resultSlices[3].memory.mem_ext.macro.D;
assign sm_wen[576+:16]=dma.u_core.resultSlices[3].memory.mem_ext.macro.WEN;
assign sm_en[37]=!dma.u_core.resultSlices[4].memory.mem_ext.macro.CEN;
assign sm_wr[37]=!dma.u_core.resultSlices[4].memory.mem_ext.macro.GWEN;
assign sm_ret[37]=dma.u_core.resultSlices[4].memory.mem_ext.macro.RET1N;
assign sm_addr[370+:10]=dma.u_core.resultSlices[4].memory.mem_ext.macro.A;
assign sm_data[592+:16]=dma.u_core.resultSlices[4].memory.mem_ext.macro.D;
assign sm_wen[592+:16]=dma.u_core.resultSlices[4].memory.mem_ext.macro.WEN;
assign sm_en[38]=!dma.u_core.resultSlices[5].memory.mem_ext.macro.CEN;
assign sm_wr[38]=!dma.u_core.resultSlices[5].memory.mem_ext.macro.GWEN;
assign sm_ret[38]=dma.u_core.resultSlices[5].memory.mem_ext.macro.RET1N;
assign sm_addr[380+:10]=dma.u_core.resultSlices[5].memory.mem_ext.macro.A;
assign sm_data[608+:16]=dma.u_core.resultSlices[5].memory.mem_ext.macro.D;
assign sm_wen[608+:16]=dma.u_core.resultSlices[5].memory.mem_ext.macro.WEN;
assign sm_en[39]=!dma.u_core.resultSlices[6].memory.mem_ext.macro.CEN;
assign sm_wr[39]=!dma.u_core.resultSlices[6].memory.mem_ext.macro.GWEN;
assign sm_ret[39]=dma.u_core.resultSlices[6].memory.mem_ext.macro.RET1N;
assign sm_addr[390+:10]=dma.u_core.resultSlices[6].memory.mem_ext.macro.A;
assign sm_data[624+:16]=dma.u_core.resultSlices[6].memory.mem_ext.macro.D;
assign sm_wen[624+:16]=dma.u_core.resultSlices[6].memory.mem_ext.macro.WEN;
assign sm_en[40]=!dma.u_core.resultSlices[7].memory.mem_ext.macro.CEN;
assign sm_wr[40]=!dma.u_core.resultSlices[7].memory.mem_ext.macro.GWEN;
assign sm_ret[40]=dma.u_core.resultSlices[7].memory.mem_ext.macro.RET1N;
assign sm_addr[400+:10]=dma.u_core.resultSlices[7].memory.mem_ext.macro.A;
assign sm_data[640+:16]=dma.u_core.resultSlices[7].memory.mem_ext.macro.D;
assign sm_wen[640+:16]=dma.u_core.resultSlices[7].memory.mem_ext.macro.WEN;
assign sm_en[41]=!dma.u_core.resultSlices[8].memory.mem_ext.macro.CEN;
assign sm_wr[41]=!dma.u_core.resultSlices[8].memory.mem_ext.macro.GWEN;
assign sm_ret[41]=dma.u_core.resultSlices[8].memory.mem_ext.macro.RET1N;
assign sm_addr[410+:10]=dma.u_core.resultSlices[8].memory.mem_ext.macro.A;
assign sm_data[656+:16]=dma.u_core.resultSlices[8].memory.mem_ext.macro.D;
assign sm_wen[656+:16]=dma.u_core.resultSlices[8].memory.mem_ext.macro.WEN;
assign sm_en[42]=!dma.u_core.resultSlices[9].memory.mem_ext.macro.CEN;
assign sm_wr[42]=!dma.u_core.resultSlices[9].memory.mem_ext.macro.GWEN;
assign sm_ret[42]=dma.u_core.resultSlices[9].memory.mem_ext.macro.RET1N;
assign sm_addr[420+:10]=dma.u_core.resultSlices[9].memory.mem_ext.macro.A;
assign sm_data[672+:16]=dma.u_core.resultSlices[9].memory.mem_ext.macro.D;
assign sm_wen[672+:16]=dma.u_core.resultSlices[9].memory.mem_ext.macro.WEN;
assign sm_en[43]=!dma.u_core.resultSlices[10].memory.mem_ext.macro.CEN;
assign sm_wr[43]=!dma.u_core.resultSlices[10].memory.mem_ext.macro.GWEN;
assign sm_ret[43]=dma.u_core.resultSlices[10].memory.mem_ext.macro.RET1N;
assign sm_addr[430+:10]=dma.u_core.resultSlices[10].memory.mem_ext.macro.A;
assign sm_data[688+:16]=dma.u_core.resultSlices[10].memory.mem_ext.macro.D;
assign sm_wen[688+:16]=dma.u_core.resultSlices[10].memory.mem_ext.macro.WEN;
assign sm_en[44]=!dma.u_core.resultSlices[11].memory.mem_ext.macro.CEN;
assign sm_wr[44]=!dma.u_core.resultSlices[11].memory.mem_ext.macro.GWEN;
assign sm_ret[44]=dma.u_core.resultSlices[11].memory.mem_ext.macro.RET1N;
assign sm_addr[440+:10]=dma.u_core.resultSlices[11].memory.mem_ext.macro.A;
assign sm_data[704+:16]=dma.u_core.resultSlices[11].memory.mem_ext.macro.D;
assign sm_wen[704+:16]=dma.u_core.resultSlices[11].memory.mem_ext.macro.WEN;
assign sm_en[45]=!dma.u_core.resultSlices[12].memory.mem_ext.macro.CEN;
assign sm_wr[45]=!dma.u_core.resultSlices[12].memory.mem_ext.macro.GWEN;
assign sm_ret[45]=dma.u_core.resultSlices[12].memory.mem_ext.macro.RET1N;
assign sm_addr[450+:10]=dma.u_core.resultSlices[12].memory.mem_ext.macro.A;
assign sm_data[720+:16]=dma.u_core.resultSlices[12].memory.mem_ext.macro.D;
assign sm_wen[720+:16]=dma.u_core.resultSlices[12].memory.mem_ext.macro.WEN;
assign sm_en[46]=!dma.u_core.resultSlices[13].memory.mem_ext.macro.CEN;
assign sm_wr[46]=!dma.u_core.resultSlices[13].memory.mem_ext.macro.GWEN;
assign sm_ret[46]=dma.u_core.resultSlices[13].memory.mem_ext.macro.RET1N;
assign sm_addr[460+:10]=dma.u_core.resultSlices[13].memory.mem_ext.macro.A;
assign sm_data[736+:16]=dma.u_core.resultSlices[13].memory.mem_ext.macro.D;
assign sm_wen[736+:16]=dma.u_core.resultSlices[13].memory.mem_ext.macro.WEN;
assign sm_en[47]=!dma.u_core.resultSlices[14].memory.mem_ext.macro.CEN;
assign sm_wr[47]=!dma.u_core.resultSlices[14].memory.mem_ext.macro.GWEN;
assign sm_ret[47]=dma.u_core.resultSlices[14].memory.mem_ext.macro.RET1N;
assign sm_addr[470+:10]=dma.u_core.resultSlices[14].memory.mem_ext.macro.A;
assign sm_data[752+:16]=dma.u_core.resultSlices[14].memory.mem_ext.macro.D;
assign sm_wen[752+:16]=dma.u_core.resultSlices[14].memory.mem_ext.macro.WEN;
assign sm_en[48]=!dma.u_core.resultSlices[15].memory.mem_ext.macro.CEN;
assign sm_wr[48]=!dma.u_core.resultSlices[15].memory.mem_ext.macro.GWEN;
assign sm_ret[48]=dma.u_core.resultSlices[15].memory.mem_ext.macro.RET1N;
assign sm_addr[480+:10]=dma.u_core.resultSlices[15].memory.mem_ext.macro.A;
assign sm_data[768+:16]=dma.u_core.resultSlices[15].memory.mem_ext.macro.D;
assign sm_wen[768+:16]=dma.u_core.resultSlices[15].memory.mem_ext.macro.WEN;
assign sm_en[49]=!dma.u_core.resultSlices[16].memory.mem_ext.macro.CEN;
assign sm_wr[49]=!dma.u_core.resultSlices[16].memory.mem_ext.macro.GWEN;
assign sm_ret[49]=dma.u_core.resultSlices[16].memory.mem_ext.macro.RET1N;
assign sm_addr[490+:10]=dma.u_core.resultSlices[16].memory.mem_ext.macro.A;
assign sm_data[784+:16]=dma.u_core.resultSlices[16].memory.mem_ext.macro.D;
assign sm_wen[784+:16]=dma.u_core.resultSlices[16].memory.mem_ext.macro.WEN;
assign sm_en[50]=!dma.u_core.resultSlices[17].memory.mem_ext.macro.CEN;
assign sm_wr[50]=!dma.u_core.resultSlices[17].memory.mem_ext.macro.GWEN;
assign sm_ret[50]=dma.u_core.resultSlices[17].memory.mem_ext.macro.RET1N;
assign sm_addr[500+:10]=dma.u_core.resultSlices[17].memory.mem_ext.macro.A;
assign sm_data[800+:16]=dma.u_core.resultSlices[17].memory.mem_ext.macro.D;
assign sm_wen[800+:16]=dma.u_core.resultSlices[17].memory.mem_ext.macro.WEN;
assign sm_en[51]=!dma.u_core.resultSlices[18].memory.mem_ext.macro.CEN;
assign sm_wr[51]=!dma.u_core.resultSlices[18].memory.mem_ext.macro.GWEN;
assign sm_ret[51]=dma.u_core.resultSlices[18].memory.mem_ext.macro.RET1N;
assign sm_addr[510+:10]=dma.u_core.resultSlices[18].memory.mem_ext.macro.A;
assign sm_data[816+:16]=dma.u_core.resultSlices[18].memory.mem_ext.macro.D;
assign sm_wen[816+:16]=dma.u_core.resultSlices[18].memory.mem_ext.macro.WEN;
assign sm_en[52]=!dma.u_core.resultSlices[19].memory.mem_ext.macro.CEN;
assign sm_wr[52]=!dma.u_core.resultSlices[19].memory.mem_ext.macro.GWEN;
assign sm_ret[52]=dma.u_core.resultSlices[19].memory.mem_ext.macro.RET1N;
assign sm_addr[520+:10]=dma.u_core.resultSlices[19].memory.mem_ext.macro.A;
assign sm_data[832+:16]=dma.u_core.resultSlices[19].memory.mem_ext.macro.D;
assign sm_wen[832+:16]=dma.u_core.resultSlices[19].memory.mem_ext.macro.WEN;
assign sm_en[53]=!dma.u_core.resultSlices[20].memory.mem_ext.macro.CEN;
assign sm_wr[53]=!dma.u_core.resultSlices[20].memory.mem_ext.macro.GWEN;
assign sm_ret[53]=dma.u_core.resultSlices[20].memory.mem_ext.macro.RET1N;
assign sm_addr[530+:10]=dma.u_core.resultSlices[20].memory.mem_ext.macro.A;
assign sm_data[848+:16]=dma.u_core.resultSlices[20].memory.mem_ext.macro.D;
assign sm_wen[848+:16]=dma.u_core.resultSlices[20].memory.mem_ext.macro.WEN;
StorageMacroObserver storage_observer(
.clock(clk),.reset(!rst_n),.abort(dma.aborting),.clearFire(dma.u_core.clearFire),
.clearDone(dma.u_core.io_clearDone),.dirtyRequired(dma.done),.en(sm_en),.wr(sm_wr),.ret(sm_ret),
.address(sm_addr),.data(sm_data),.wen(sm_wen),
.datapathZero((dma.u_core.rows[0].lanes[0].pe.ACC===0)&&(dma.u_core.rows[0].lanes[1].pe.ACC===0)&&(dma.u_core.rows[0].lanes[2].pe.ACC===0)&&(dma.u_core.rows[0].lanes[3].pe.ACC===0)&&(dma.u_core.rows[0].lanes[4].pe.ACC===0)&&(dma.u_core.rows[0].lanes[5].pe.ACC===0)&&(dma.u_core.rows[0].lanes[6].pe.ACC===0)&&(dma.u_core.rows[0].lanes[7].pe.ACC===0)&&(dma.u_core.rows[1].lanes[0].pe.ACC===0)&&(dma.u_core.rows[1].lanes[1].pe.ACC===0)&&(dma.u_core.rows[1].lanes[2].pe.ACC===0)&&(dma.u_core.rows[1].lanes[3].pe.ACC===0)&&(dma.u_core.rows[1].lanes[4].pe.ACC===0)&&(dma.u_core.rows[1].lanes[5].pe.ACC===0)&&(dma.u_core.rows[1].lanes[6].pe.ACC===0)&&(dma.u_core.rows[1].lanes[7].pe.ACC===0)&&(dma.u_core.rows[2].lanes[0].pe.ACC===0)&&(dma.u_core.rows[2].lanes[1].pe.ACC===0)&&(dma.u_core.rows[2].lanes[2].pe.ACC===0)&&(dma.u_core.rows[2].lanes[3].pe.ACC===0)&&(dma.u_core.rows[2].lanes[4].pe.ACC===0)&&(dma.u_core.rows[2].lanes[5].pe.ACC===0)&&(dma.u_core.rows[2].lanes[6].pe.ACC===0)&&(dma.u_core.rows[2].lanes[7].pe.ACC===0)&&(dma.u_core.rows[3].lanes[0].pe.ACC===0)&&(dma.u_core.rows[3].lanes[1].pe.ACC===0)&&(dma.u_core.rows[3].lanes[2].pe.ACC===0)&&(dma.u_core.rows[3].lanes[3].pe.ACC===0)&&(dma.u_core.rows[3].lanes[4].pe.ACC===0)&&(dma.u_core.rows[3].lanes[5].pe.ACC===0)&&(dma.u_core.rows[3].lanes[6].pe.ACC===0)&&(dma.u_core.rows[3].lanes[7].pe.ACC===0)&&(dma.u_core.rows[4].lanes[0].pe.ACC===0)&&(dma.u_core.rows[4].lanes[1].pe.ACC===0)&&(dma.u_core.rows[4].lanes[2].pe.ACC===0)&&(dma.u_core.rows[4].lanes[3].pe.ACC===0)&&(dma.u_core.rows[4].lanes[4].pe.ACC===0)&&(dma.u_core.rows[4].lanes[5].pe.ACC===0)&&(dma.u_core.rows[4].lanes[6].pe.ACC===0)&&(dma.u_core.rows[4].lanes[7].pe.ACC===0)&&(dma.u_core.rows[5].lanes[0].pe.ACC===0)&&(dma.u_core.rows[5].lanes[1].pe.ACC===0)&&(dma.u_core.rows[5].lanes[2].pe.ACC===0)&&(dma.u_core.rows[5].lanes[3].pe.ACC===0)&&(dma.u_core.rows[5].lanes[4].pe.ACC===0)&&(dma.u_core.rows[5].lanes[5].pe.ACC===0)&&(dma.u_core.rows[5].lanes[6].pe.ACC===0)&&(dma.u_core.rows[5].lanes[7].pe.ACC===0)&&(dma.u_core.rows[6].lanes[0].pe.ACC===0)&&(dma.u_core.rows[6].lanes[1].pe.ACC===0)&&(dma.u_core.rows[6].lanes[2].pe.ACC===0)&&(dma.u_core.rows[6].lanes[3].pe.ACC===0)&&(dma.u_core.rows[6].lanes[4].pe.ACC===0)&&(dma.u_core.rows[6].lanes[5].pe.ACC===0)&&(dma.u_core.rows[6].lanes[6].pe.ACC===0)&&(dma.u_core.rows[6].lanes[7].pe.ACC===0)&&(dma.u_core.rows[7].lanes[0].pe.ACC===0)&&(dma.u_core.rows[7].lanes[1].pe.ACC===0)&&(dma.u_core.rows[7].lanes[2].pe.ACC===0)&&(dma.u_core.rows[7].lanes[3].pe.ACC===0)&&(dma.u_core.rows[7].lanes[4].pe.ACC===0)&&(dma.u_core.rows[7].lanes[5].pe.ACC===0)&&(dma.u_core.rows[7].lanes[6].pe.ACC===0)&&(dma.u_core.rows[7].lanes[7].pe.ACC===0)&&(dma.u_core.biasLow===0)&&(dma.u_core.hostData===0)&&(dma.w_low===0)&&(dma.bias_low===0)&&(dma.bias_data===0)&&(dma.lock_data===0)),
.held(dma.u_core.readHeld),.pop(dma.u_core.pop),.raw(dma.u_core.resultRaw),
.storeBlocked(dma.u_core.active&&dma.u_core.state==7&&dma.u_core.readHeld),.storeWrite(dma.u_core.storeWrite),
.resultRead(dma.u_core.resultRead),.taskDone(dma.done),
.ownersIdle(!dma.pending&&!dma.locked&&!dma.core_active&&!dma.core_out_valid));

 reg previousHeld=0,previousLastPop=0;
 reg [335:0] previousRowQ;
 reg [3:0] previousRowOwner;
 always @(posedge clk)begin
   if(!rst_n||dma.aborting)begin previousHeld<=0;previousLastPop<=0;end
   else begin
     if(previousHeld&&!previousLastPop&&dma.u_core.readHeld)begin
       assert(dma.u_core.resultRowQ===previousRowQ)else $fatal(1,"macro Q row changed before last Y response");
       assert({dma.u_core.head,dma.u_core.outRow}==previousRowOwner)else $fatal(1,"macro slot/row released before last Y response");
     end
     previousHeld<=dma.u_core.readHeld;
     previousLastPop<=dma.core_pop&&dma.core_out_column==7;
     previousRowQ<=dma.u_core.resultRowQ;
     previousRowOwner<={dma.u_core.head,dma.u_core.outRow};
   end
 end

endmodule
