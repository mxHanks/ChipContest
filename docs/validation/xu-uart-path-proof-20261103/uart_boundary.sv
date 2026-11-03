// xu: actual selected-UART boundary, matching fixed non-lockstep SoC wiring.
// This is not a CPU/fabric/full-SoC replacement or a timing model.
module xu_uart_boundary(
  input wire clk, corerst, test_mode,
  input wire cmd_valid, cmd_read,
  input wire [31:0] cmd_addr, cmd_wdata,
  input wire [3:0] cmd_wmask,
  input wire rsp_ready, rx_i,
  output wire cmd_ready, rsp_valid, rsp_err,
  output wire [31:0] rsp_rdata,
  output wire tx_o, event_o, main_rst_n
);
  wire main_rst;
  sirv_ResetCatchAndSync_2 reset_catch(
    .clock(clk), .reset(corerst), .test_mode(test_mode), .io_sync_reset(main_rst));
  assign main_rst_n=~main_rst;
  wire [31:0] paddr,pwdata,prdata;
  wire pwrite,psel,penable;
  sirv_gnrl_icb2apb #(.AW(32),.DW(32)) bridge(
    .i_icb_cmd_valid(cmd_valid),.i_icb_cmd_ready(cmd_ready),
    .i_icb_cmd_read(cmd_read),.i_icb_cmd_addr(cmd_addr),
    .i_icb_cmd_wdata(cmd_wdata),.i_icb_cmd_wmask(cmd_wmask),.i_icb_cmd_size(2'b00),
    .i_icb_rsp_valid(rsp_valid),.i_icb_rsp_ready(rsp_ready),
    .i_icb_rsp_err(rsp_err),.i_icb_rsp_rdata(rsp_rdata),
    .apb_paddr(paddr),.apb_pwrite(pwrite),.apb_pselx(psel),.apb_penable(penable),
    .apb_pwdata(pwdata),.apb_prdata(prdata),.clk(clk),.rst_n(main_rst_n));
  apb_uart_sv #(.APB_ADDR_WIDTH(32)) uart(
    .CLK(clk),.RSTN(main_rst_n),.PADDR(paddr),.PWDATA(pwdata),.PWRITE(pwrite),
    .PSEL(psel),.PENABLE(penable),.PRDATA(prdata),.PREADY(),.PSLVERR(),
    .rx_i(rx_i),.tx_o(tx_o),.event_o(event_o));
endmodule
