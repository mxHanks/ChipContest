// Small syntax/inference probe; NOT a replacement for core synthesis.
module probe_banked_memory #(
    parameter integer LANES = 2,
    parameter integer WORDS = 16
) (
    input wire clk,
    input wire en,
    input wire wr_en,
    input wire [4:0] wr_addr,
    input wire signed [15:0] wr_data,
    input wire [3:0] rd_addr,
    output wire signed [15:0] out0,
    output wire signed [15:0] out1
);
    logic signed [15:0] bank [0:LANES-1][0:WORDS-1];
    logic signed [15:0] rd [0:LANES-1];
    for (genvar lane=0; lane<LANES; lane=lane+1) begin: g_lane
        always @(posedge clk) begin
            if (wr_en && $signed(32'(wr_addr)) % LANES == lane)
                bank[lane][$signed(32'(wr_addr))/LANES] <= wr_data;
            if (en)
                rd[lane] <= bank[lane][rd_addr];
        end
    end
    assign out0=rd[0];
    assign out1=rd[1];
endmodule
