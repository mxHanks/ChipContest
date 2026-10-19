// Logical opaque SRAM boundary only. This is not an official macro model,
// contains no timing arcs/area/power, and must not be used for simulation.
(* blackbox *)
module kwt_sram_1rw_blackbox #(
    parameter integer WIDTH = 16,
    parameter integer DEPTH = 128,
    parameter integer ADDR_WIDTH = (DEPTH <= 1 ? 1 : $clog2(DEPTH))
) (
    input wire clk,
    input wire wr_en,
    input wire [ADDR_WIDTH-1:0] wr_addr,
    input wire [WIDTH-1:0] wr_data,
    input wire rd_en,
    input wire [ADDR_WIDTH-1:0] rd_addr,
    output wire [WIDTH-1:0] rd_data
);
endmodule
