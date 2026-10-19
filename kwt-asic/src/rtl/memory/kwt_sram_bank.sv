`timescale 1ns/1ps
// Logical 1RW bank assembled from opaque-capable 16-bit storage primitives.
// This is a capacity/port adapter, not a claim about an official macro's pins.
// Greedy depth packing: 4096, then 1024, then 128 words. Width is padded to 16.
module kwt_sram_bank #(
    parameter integer WIDTH = 16,
    parameter integer DEPTH = 1024,
    parameter integer BACKEND = 0,
    parameter integer CHECKS = 1,
    parameter integer AW = DEPTH > 1 ? $clog2(DEPTH) : 1
) (
    input wire clk, rst_n,
    input wire wr_en,
    input wire [AW-1:0] wr_addr,
    input wire [WIDTH-1:0] wr_data,
    input wire rd_en,
    input wire [AW-1:0] rd_addr,
    output wire [WIDTH-1:0] rd_data,
    output reg rd_valid
);
    localparam integer N4096 = DEPTH / 4096;
    localparam integer N1024 = (DEPTH % 4096) / 1024;
    localparam integer N128 = ((DEPTH % 1024) + 127) / 128;
    localparam integer NTILES = N4096 + N1024 + N128;
    localparam integer NSLICES = (WIDTH + 15) / 16;
    localparam integer TW = NTILES > 1 ? $clog2(NTILES) : 1;
    wire [NSLICES*16-1:0] padded_write = {{(NSLICES*16-WIDTH){1'b0}},wr_data};
    wire [NSLICES*16-1:0] tile_data [0:NTILES-1];
    reg [TW-1:0] returned_tile;
    assign rd_data = tile_data[returned_tile][WIDTH-1:0];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) rd_valid <= 1'b0;
        else rd_valid <= rd_en;
    end
    always @(posedge clk) if (rst_n && rd_en && rd_addr < DEPTH) begin
        if (rd_addr < N4096*4096)
            returned_tile <= TW'(rd_addr / 4096);
        else if (rd_addr < N4096*4096+N1024*1024)
            returned_tile <= TW'(N4096+(rd_addr-N4096*4096)/1024);
        else
            returned_tile <= TW'(N4096+N1024+(rd_addr-N4096*4096-N1024*1024)/128);
    end
    for (genvar t=0; t<NTILES; t=t+1) begin : g_tile
        localparam integer TD = t < N4096 ? 4096 : t < N4096+N1024 ? 1024 : 128;
        localparam integer BASE = t < N4096 ? t*4096 :
            t < N4096+N1024 ? N4096*4096+(t-N4096)*1024 :
            N4096*4096+N1024*1024+(t-N4096-N1024)*128;
        localparam integer TA = $clog2(TD);
        wire tile_write = rst_n && wr_en && wr_addr >= BASE && wr_addr < BASE+TD && wr_addr < DEPTH;
        wire tile_read = rst_n && rd_en && rd_addr >= BASE && rd_addr < BASE+TD && rd_addr < DEPTH;
        for (genvar s=0; s<NSLICES; s=s+1) begin : g_slice
            wire unused_valid;
            kwt_sram_1rw #(.WIDTH(16), .DEPTH(TD), .BACKEND(BACKEND), .CHECKS(CHECKS)) storage (
                .clk(clk), .rst_n(rst_n),
                .wr_en(tile_write), .wr_addr(TA'(wr_addr-BASE)), .wr_data(padded_write[s*16+:16]),
                .rd_en(tile_read), .rd_addr(TA'(rd_addr-BASE)),
                .rd_data(tile_data[t][s*16+:16]), .rd_valid(unused_valid)
            );
        end
    end
`ifndef SYNTHESIS
    initial if (WIDTH < 1 || DEPTH < 1) $fatal(1,"KWT_SRAM_BANK invalid shape");
    always @(posedge clk) if (rst_n && CHECKS) begin
        // Decode can mask X/Z enables when the address lies in padding. Check
        // the original request, not only the enables observed by each tile.
        if ((wr_en !== 1'b0 && wr_en !== 1'b1) || (rd_en !== 1'b0 && rd_en !== 1'b1))
            $fatal(1,"KWT_SRAM_BANK_UNKNOWN_ENABLE");
        if ((wr_en && $isunknown(wr_addr)) || (rd_en && $isunknown(rd_addr)))
            $fatal(1,"KWT_SRAM_BANK unknown address");
        if ((wr_en && wr_addr >= DEPTH) || (rd_en && rd_addr >= DEPTH))
            $fatal(1,"KWT_SRAM_BANK address out of logical range");
        if (wr_en && rd_en) $fatal(1,"KWT_SRAM_BANK simultaneous read/write forbidden");
    end
`endif
endmodule
