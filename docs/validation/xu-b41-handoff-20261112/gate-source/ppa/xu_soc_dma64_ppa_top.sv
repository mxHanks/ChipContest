// Experimental full-digital PPA boundary for the frozen XU_MATRIX_DMA64 candidate.
// Preparation only: no synthesis, timing closure, or official qualification claimed.
// Keep every real SoC pad visible so peripheral logic is retained for synthesis.
// The 512 KiB ICB endpoint replaces only the original external TB RAM endpoint.
module xu_soc_dma64_ppa_top (
// This clock should comes from the crystal pad generated high speed clock (16MHz)
  input  hfextclk,
  output hfxoscen,// The signal to enable the crystal pad generated clock

  // This clock should comes from the crystal pad generated low speed clock (32.768KHz)
  input  lfextclk,
  output lfxoscen,// The signal to enable the crystal pad generated clock


  // The JTAG TCK is input, need to be pull-up
  input   io_pads_jtag_TCK_i_ival,

  // The JTAG TMS is input, need to be pull-up
  input   io_pads_jtag_TMS_i_ival,

  // The JTAG TDI is input, need to be pull-up
  input   io_pads_jtag_TDI_i_ival,

  // The JTAG TDO is output have enable
  output  io_pads_jtag_TDO_o_oval,
  output  io_pads_jtag_TDO_o_oe,

  // The GPIO are all bidir pad have enables
  input  [32-1:0] io_pads_gpioA_i_ival,
  output [32-1:0] io_pads_gpioA_o_oval,
  output [32-1:0] io_pads_gpioA_o_oe,

  input  [32-1:0] io_pads_gpioB_i_ival,
  output [32-1:0] io_pads_gpioB_o_oval,
  output [32-1:0] io_pads_gpioB_o_oe,

  //QSPI0 SCK and CS is output without enable
  output  io_pads_qspi0_sck_o_oval,
  output  io_pads_qspi0_cs_0_o_oval,

  //QSPI0 DQ is bidir I/O with enable, and need pull-up enable
  input   io_pads_qspi0_dq_0_i_ival,
  output  io_pads_qspi0_dq_0_o_oval,
  output  io_pads_qspi0_dq_0_o_oe,
  input   io_pads_qspi0_dq_1_i_ival,
  output  io_pads_qspi0_dq_1_o_oval,
  output  io_pads_qspi0_dq_1_o_oe,
  input   io_pads_qspi0_dq_2_i_ival,
  output  io_pads_qspi0_dq_2_o_oval,
  output  io_pads_qspi0_dq_2_o_oe,
  input   io_pads_qspi0_dq_3_i_ival,
  output  io_pads_qspi0_dq_3_o_oval,
  output  io_pads_qspi0_dq_3_o_oe,

  // Erst is input need to be pull-up by default
  input   io_pads_aon_erst_n_i_ival,

  // dbgmode are inputs need to be pull-up by default
  input  io_pads_dbgmode0_n_i_ival,
  input  io_pads_dbgmode1_n_i_ival,
  input  io_pads_dbgmode2_n_i_ival,

  // BootRom is input need to be pull-up by default
  input  io_pads_bootrom_n_i_ival,


  // dwakeup is input need to be pull-up by default
  input  io_pads_aon_pmu_dwakeup_n_i_ival,

      // PMU output is just output without enable
  output io_pads_aon_pmu_padrst_o_oval,
  output io_pads_aon_pmu_vddpaden_o_oval

);

  wire shared_mem_clk, shared_mem_rst_n;
  wire  ext_sysmem_cmd_valid;
  wire  ext_sysmem_cmd_ready;
  wire [31:0] ext_sysmem_cmd_addr;
  wire  ext_sysmem_cmd_read;
  wire [63:0] ext_sysmem_cmd_wdata;
  wire ext_sysmem_cmd_is32;
  wire [7:0] ext_sysmem_cmd_wmask;
  wire  ext_sysmem_rsp_valid;
  wire  ext_sysmem_rsp_ready;
  wire  ext_sysmem_rsp_err;
  wire [63:0] ext_sysmem_rsp_rdata;

  e203_soc_top #(.EXTERNAL_SYSMEM(1)) u_soc (
    .shared_mem_clk(shared_mem_clk),
    .shared_mem_rst_n(shared_mem_rst_n),
    .hfextclk(hfextclk),
    .hfxoscen(hfxoscen),
    .lfextclk(lfextclk),
    .lfxoscen(lfxoscen),
    .io_pads_jtag_TCK_i_ival(io_pads_jtag_TCK_i_ival),
    .io_pads_jtag_TMS_i_ival(io_pads_jtag_TMS_i_ival),
    .io_pads_jtag_TDI_i_ival(io_pads_jtag_TDI_i_ival),
    .io_pads_jtag_TDO_o_oval(io_pads_jtag_TDO_o_oval),
    .io_pads_jtag_TDO_o_oe(io_pads_jtag_TDO_o_oe),
    .io_pads_gpioA_i_ival(io_pads_gpioA_i_ival),
    .io_pads_gpioA_o_oval(io_pads_gpioA_o_oval),
    .io_pads_gpioA_o_oe(io_pads_gpioA_o_oe),
    .io_pads_gpioB_i_ival(io_pads_gpioB_i_ival),
    .io_pads_gpioB_o_oval(io_pads_gpioB_o_oval),
    .io_pads_gpioB_o_oe(io_pads_gpioB_o_oe),
    .io_pads_qspi0_sck_o_oval(io_pads_qspi0_sck_o_oval),
    .io_pads_qspi0_cs_0_o_oval(io_pads_qspi0_cs_0_o_oval),
    .io_pads_qspi0_dq_0_i_ival(io_pads_qspi0_dq_0_i_ival),
    .io_pads_qspi0_dq_0_o_oval(io_pads_qspi0_dq_0_o_oval),
    .io_pads_qspi0_dq_0_o_oe(io_pads_qspi0_dq_0_o_oe),
    .io_pads_qspi0_dq_1_i_ival(io_pads_qspi0_dq_1_i_ival),
    .io_pads_qspi0_dq_1_o_oval(io_pads_qspi0_dq_1_o_oval),
    .io_pads_qspi0_dq_1_o_oe(io_pads_qspi0_dq_1_o_oe),
    .io_pads_qspi0_dq_2_i_ival(io_pads_qspi0_dq_2_i_ival),
    .io_pads_qspi0_dq_2_o_oval(io_pads_qspi0_dq_2_o_oval),
    .io_pads_qspi0_dq_2_o_oe(io_pads_qspi0_dq_2_o_oe),
    .io_pads_qspi0_dq_3_i_ival(io_pads_qspi0_dq_3_i_ival),
    .io_pads_qspi0_dq_3_o_oval(io_pads_qspi0_dq_3_o_oval),
    .io_pads_qspi0_dq_3_o_oe(io_pads_qspi0_dq_3_o_oe),
    .io_pads_aon_erst_n_i_ival(io_pads_aon_erst_n_i_ival),
    .io_pads_dbgmode0_n_i_ival(io_pads_dbgmode0_n_i_ival),
    .io_pads_dbgmode1_n_i_ival(io_pads_dbgmode1_n_i_ival),
    .io_pads_dbgmode2_n_i_ival(io_pads_dbgmode2_n_i_ival),
    .io_pads_bootrom_n_i_ival(io_pads_bootrom_n_i_ival),
    .io_pads_aon_pmu_dwakeup_n_i_ival(io_pads_aon_pmu_dwakeup_n_i_ival),
    .io_pads_aon_pmu_padrst_o_oval(io_pads_aon_pmu_padrst_o_oval),
    .io_pads_aon_pmu_vddpaden_o_oval(io_pads_aon_pmu_vddpaden_o_oval),
    .ext_sysmem_cmd_valid(ext_sysmem_cmd_valid),
    .ext_sysmem_cmd_ready(ext_sysmem_cmd_ready),
    .ext_sysmem_cmd_addr(ext_sysmem_cmd_addr),
    .ext_sysmem_cmd_read(ext_sysmem_cmd_read),
    .ext_sysmem_cmd_is32(ext_sysmem_cmd_is32),
    .ext_sysmem_cmd_wdata(ext_sysmem_cmd_wdata),
    .ext_sysmem_cmd_wmask(ext_sysmem_cmd_wmask),
    .ext_sysmem_rsp_valid(ext_sysmem_rsp_valid),
    .ext_sysmem_rsp_ready(ext_sysmem_rsp_ready),
    .ext_sysmem_rsp_err(ext_sysmem_rsp_err),
    .ext_sysmem_rsp_rdata(ext_sysmem_rsp_rdata)
  );

  xu_shared_icb_sram64 u_shared (
    .clk(shared_mem_clk), .rst_n(shared_mem_rst_n),
    .cmd_valid(ext_sysmem_cmd_valid),
    .cmd_ready(ext_sysmem_cmd_ready),
    .cmd_addr(ext_sysmem_cmd_addr),
    .cmd_read(ext_sysmem_cmd_read),
    .cmd_is32(ext_sysmem_cmd_is32),
    .cmd_wdata(ext_sysmem_cmd_wdata),
    .cmd_wmask(ext_sysmem_cmd_wmask),
    .rsp_valid(ext_sysmem_rsp_valid),
    .rsp_ready(ext_sysmem_rsp_ready),
    .rsp_err(ext_sysmem_rsp_err),
    .rsp_rdata(ext_sysmem_rsp_rdata)
  );
endmodule
