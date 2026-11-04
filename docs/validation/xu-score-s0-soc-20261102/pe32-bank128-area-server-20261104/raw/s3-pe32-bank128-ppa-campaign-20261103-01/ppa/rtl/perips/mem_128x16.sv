// xu experiment: compile instead of generated mem_128x16, never beside it.
// Requires the actual designated RAMSP128X16 cell/model. EMA settings and PVT
// remain independently qualified; this adapter is not a technology model.
module mem_128x16 #(
  parameter [2:0] XU_EMA = 3'b010,
  parameter [1:0] XU_EMAW = 2'b00
)(
  input [6:0] RW0_addr,
  input RW0_en, RW0_clk, RW0_wmode,
  input [15:0] RW0_wdata,
  output [15:0] RW0_rdata
);
  wire [15:0] macro_q;
  wire writing = RW0_en & RW0_wmode;
  reg valid_read;
  always @(posedge RW0_clk) valid_read <= RW0_en & ~RW0_wmode;
  RAMSP128X16 macro (
    .Q(macro_q), .CLK(RW0_clk), .CEN(~RW0_en),
    .WEN(writing ? 16'h0000 : 16'hffff), .GWEN(~writing), .A(RW0_addr),
    .D(RW0_wdata), .EMA(XU_EMA), .EMAW(XU_EMAW), .RET1N(1'b1)
  );
  // Physical retained Q is not a defined logical read on idle/write cycles.
  assign RW0_rdata = valid_read ? macro_q : 16'bx;
endmodule
