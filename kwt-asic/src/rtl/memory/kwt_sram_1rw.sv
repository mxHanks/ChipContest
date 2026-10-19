`timescale 1ns/1ps

// Logical single-port SRAM contract. A read samples rd_addr at a rising edge;
// rd_data and rd_valid are then available for the following cycle. Q holds
// when no read is requested. Reset never clears SRAM payload.
// BACKEND: 0 behavioral simulation, 1 opaque synthesis macro, 2 FF fallback,
//          3 externally supplied official adapter (not supplied by this repo).
module kwt_sram_1rw #(
    parameter integer WIDTH = 16,
    parameter integer DEPTH = 128,
    parameter integer BACKEND = 0,
    parameter integer CHECKS = 1,
    parameter INIT_FILE = "",
    parameter integer ADDR_WIDTH = (DEPTH <= 1 ? 1 : $clog2(DEPTH))
) (
    input wire clk,
    input wire rst_n,
    input wire wr_en,
    input wire [ADDR_WIDTH-1:0] wr_addr,
    input wire [WIDTH-1:0] wr_data,
    input wire rd_en,
    input wire [ADDR_WIDTH-1:0] rd_addr,
    output wire [WIDTH-1:0] rd_data,
    output reg rd_valid
);
    always @(posedge clk or negedge rst_n)
        if (!rst_n) rd_valid <= 1'b0;
        else rd_valid <= rd_en;

    generate
        if (WIDTH < 1 || DEPTH < 1 || ADDR_WIDTH < (DEPTH <= 1 ? 1 : $clog2(DEPTH))) begin : g_bad_geometry
            KWT_SRAM_INVALID_GEOMETRY invalid_geometry();
        end
        if (BACKEND == 0) begin : g_behavioral
`ifdef SYNTHESIS
            KWT_BEHAVIORAL_SRAM_IS_SIMULATION_ONLY choose_blackbox_or_ff_fallback();
`else
            kwt_sram_behavioral #(.WIDTH(WIDTH), .DEPTH(DEPTH), .ADDR_WIDTH(ADDR_WIDTH), .INIT_FILE(INIT_FILE)) u_model
                (.clk(clk), .rst_n(rst_n), .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),
                 .rd_en(rd_en), .rd_addr(rd_addr), .rd_data(rd_data));
`endif
        end else if (BACKEND == 1) begin : g_blackbox
            kwt_sram_1rw_blackbox #(.WIDTH(WIDTH), .DEPTH(DEPTH), .ADDR_WIDTH(ADDR_WIDTH)) u_macro
                (.clk(clk), .wr_en(wr_en && rst_n), .wr_addr(wr_addr), .wr_data(wr_data),
                 .rd_en(rd_en && rst_n), .rd_addr(rd_addr), .rd_data(rd_data));
        end else if (BACKEND == 2) begin : g_ff_fallback
            kwt_sram_array #(.WIDTH(WIDTH), .DEPTH(DEPTH), .ADDR_WIDTH(ADDR_WIDTH), .INIT_FILE(INIT_FILE)) u_ff
                (.clk(clk), .rst_n(rst_n), .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),
                 .rd_en(rd_en), .rd_addr(rd_addr), .rd_data(rd_data));
        end else if (BACKEND == 3) begin : g_official
            // The adapter has the logical ports below; its implementation must
            // be provided only after the official pins/timing are documented.
            // No official pins, collision behavior, area or timing are assumed.
            kwt_official_sram_adapter #(.WIDTH(WIDTH), .DEPTH(DEPTH), .ADDR_WIDTH(ADDR_WIDTH)) u_macro
                (.clk(clk), .wr_en(wr_en && rst_n), .wr_addr(wr_addr), .wr_data(wr_data),
                 .rd_en(rd_en && rst_n), .rd_addr(rd_addr), .rd_data(rd_data));
        end else begin : g_bad_backend
            KWT_SRAM_BACKEND_MUST_BE_0_1_2_OR_3 invalid_backend();
        end
    endgenerate

`ifndef SYNTHESIS
    // A known bitmap is simulation-only. Like payload it survives reset.
    // INIT_FILE is a complete DEPTH-word image; task loading remains explicit.
    reg known [0:DEPTH-1];
    integer i;
    initial begin
        for (i = 0; i < DEPTH; i = i + 1) known[i] = (INIT_FILE != "");
        if (BACKEND == 1) $fatal(1, "KWT_SRAM_BLACKBOX_IS_NOT_A_FUNCTIONAL_MODEL");
    end
    always @(posedge clk) begin
        if (rst_n && CHECKS != 0) begin
            if ((wr_en !== 1'b0 && wr_en !== 1'b1) || (rd_en !== 1'b0 && rd_en !== 1'b1))
                $fatal(1, "KWT_SRAM_UNKNOWN_ENABLE");
            if (wr_en && rd_en) $fatal(1, "KWT_SRAM_SINGLE_PORT_CONFLICT");
            if (wr_en && ((^wr_addr === 1'bx) || wr_addr >= DEPTH))
                $fatal(1, "KWT_SRAM_WRITE_ADDRESS_INVALID");
            if (rd_en && ((^rd_addr === 1'bx) || rd_addr >= DEPTH))
                $fatal(1, "KWT_SRAM_READ_ADDRESS_INVALID");
            if (rd_en && rd_addr < DEPTH && (^rd_addr !== 1'bx) && !known[rd_addr])
                $fatal(1, "KWT_SRAM_UNINITIALIZED_READ");
            if (wr_en && (^wr_data === 1'bx)) $fatal(1, "KWT_SRAM_UNKNOWN_WRITE_DATA");
        end
        if (rst_n && wr_en && wr_addr < DEPTH && (^wr_addr !== 1'bx)) known[wr_addr] <= 1'b1;
    end
`endif
endmodule

`ifndef SYNTHESIS
module kwt_sram_behavioral #(
    parameter integer WIDTH = 16,
    parameter integer DEPTH = 128,
    parameter integer ADDR_WIDTH = (DEPTH <= 1 ? 1 : $clog2(DEPTH)),
    parameter INIT_FILE = ""
) (
    input wire clk, input wire rst_n,
    input wire wr_en, input wire [ADDR_WIDTH-1:0] wr_addr, input wire [WIDTH-1:0] wr_data,
    input wire rd_en, input wire [ADDR_WIDTH-1:0] rd_addr,
    output logic [WIDTH-1:0] rd_data
);
    logic [WIDTH-1:0] storage [0:DEPTH-1];
    integer init_fd, init_index;
    initial if (INIT_FILE != "") begin
        init_fd = $fopen(INIT_FILE, "r");
        if (init_fd == 0) $fatal(1, "KWT_SRAM_INIT_FILE_MISSING");
        $fclose(init_fd);
        $readmemh(INIT_FILE, storage);
        for (init_index = 0; init_index < DEPTH; init_index = init_index + 1)
            if (^storage[init_index] === 1'bx) $fatal(1, "KWT_SRAM_INIT_INCOMPLETE_OR_UNKNOWN address=%0d", init_index);
    end
    always_ff @(posedge clk) begin
        if (rst_n && wr_en && wr_addr < DEPTH) storage[wr_addr] <= wr_data;
        if (rst_n && rd_en && rd_addr < DEPTH) rd_data <= storage[rd_addr];
    end
endmodule
`endif

// Deliberately retained FF+MUX baseline backend. memory_map in an explicit FF
// synthesis run expands this array. It is never used by BLACKBOX mode.
module kwt_sram_array #(
    parameter integer WIDTH = 16,
    parameter integer DEPTH = 128,
    parameter integer ADDR_WIDTH = (DEPTH <= 1 ? 1 : $clog2(DEPTH)),
    parameter INIT_FILE = ""
) (
    input wire clk, input wire rst_n,
    input wire wr_en, input wire [ADDR_WIDTH-1:0] wr_addr, input wire [WIDTH-1:0] wr_data,
    input wire rd_en, input wire [ADDR_WIDTH-1:0] rd_addr,
    output reg [WIDTH-1:0] rd_data
);
    reg [WIDTH-1:0] mem [0:DEPTH-1];
    integer init_fd, init_index;
    initial if (INIT_FILE != "") begin
`ifndef SYNTHESIS
        init_fd = $fopen(INIT_FILE, "r");
        if (init_fd == 0) $fatal(1, "KWT_SRAM_INIT_FILE_MISSING");
        $fclose(init_fd);
`endif
        $readmemh(INIT_FILE, mem);
`ifndef SYNTHESIS
        for (init_index = 0; init_index < DEPTH; init_index = init_index + 1)
            if (^mem[init_index] === 1'bx) $fatal(1, "KWT_SRAM_INIT_INCOMPLETE_OR_UNKNOWN address=%0d", init_index);
`endif
    end
    always @(posedge clk) begin
        if (rst_n && wr_en && wr_addr < DEPTH) mem[wr_addr] <= wr_data;
        if (rst_n && rd_en && rd_addr < DEPTH) rd_data <= mem[rd_addr];
    end
endmodule
