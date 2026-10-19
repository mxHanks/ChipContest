`timescale 1ns/1ps
// KWT_DEVELOPMENT_LOGICAL_ADAPTER_FIXTURE
// Qualification of the published logical adapter contract only. This is NOT
// an official SRAM macro, vendor pin model, or synthesis implementation.
module kwt_official_sram_adapter #(
    parameter integer WIDTH=16,
    parameter integer DEPTH=128,
    parameter integer ADDR_WIDTH=(DEPTH<=1 ? 1 : $clog2(DEPTH))
) (
    input wire clk,
    input wire wr_en,
    input wire [ADDR_WIDTH-1:0] wr_addr,
    input wire [WIDTH-1:0] wr_data,
    input wire rd_en,
    input wire [ADDR_WIDTH-1:0] rd_addr,
    output wire [WIDTH-1:0] rd_data
);
`ifdef SYNTHESIS
    KWT_DEVELOPMENT_ADAPTER_IS_NOT_SYNTHESIZABLE forbidden();
`else
    if (WIDTH!=16 || (DEPTH!=128 && DEPTH!=1024 && DEPTH!=4096)) begin : invalid
        KWT_QUALIFICATION_REQUIRES_DECLARED_CAPACITY_SHAPE invalid_shape();
    end
    wire [WIDTH-1:0] q;
    // Parent wrapper gates requests during reset; no invented macro reset pin.
    kwt_sram_behavioral #(.WIDTH(WIDTH),.DEPTH(DEPTH),.ADDR_WIDTH(ADDR_WIDTH)) model
        (.clk(clk),.rst_n(1'b1),.wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data),
         .rd_en(rd_en),.rd_addr(rd_addr),.rd_data(q));
`ifdef KWT_QUALIFICATION_BAD_READ_DATA
    assign rd_data=q ^ {{(WIDTH-1){1'b0}},1'b1};
`else
    assign rd_data=q;
`endif
`endif
endmodule
