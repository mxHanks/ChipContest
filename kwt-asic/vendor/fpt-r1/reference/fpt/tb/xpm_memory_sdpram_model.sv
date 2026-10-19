`timescale 1ns/1ps

// Small behavioral XPM replacement used only by the Icarus contract test.
// It models the mixed-width 64-bit-write/16-bit-read and 16-bit-write/read
// configurations instantiated by cats_r4_qkv_axi_bank_bridge.  Vivado runs
// continue to use the vendor xpm library.
module xpm_memory_sdpram #(
    parameter integer ADDR_WIDTH_A = 9,
    parameter integer ADDR_WIDTH_B = 9,
    parameter integer BYTE_WRITE_WIDTH_A = 8,
    parameter string CLOCKING_MODE = "independent_clock",
    parameter string ECC_MODE = "no_ecc",
    parameter integer MEMORY_SIZE = 8192,
    parameter string MEMORY_PRIMITIVE = "block",
    parameter integer READ_DATA_WIDTH_B = 16,
    parameter integer READ_LATENCY_B = 2,
    parameter string WRITE_MODE_B = "read_first",
    parameter integer WRITE_DATA_WIDTH_A = 16,
    parameter integer AUTO_SLEEP_TIME = 0
) (
    input logic clka,
    input logic ena,
    input logic [WRITE_DATA_WIDTH_A/BYTE_WRITE_WIDTH_A-1:0] wea,
    input logic [ADDR_WIDTH_A-1:0] addra,
    input logic [WRITE_DATA_WIDTH_A-1:0] dina,
    input logic injectsbiterra,
    input logic injectdbiterra,
    input logic sleep,
    input logic clkb,
    input logic enb,
    input logic [ADDR_WIDTH_B-1:0] addrb,
    output logic [READ_DATA_WIDTH_B-1:0] doutb,
    input logic regceb,
    input logic rstb,
    output logic sbiterrb,
    output logic dbiterrb
);
    localparam integer WORDS16 = MEMORY_SIZE / 16;
    localparam integer LANES16 = WRITE_DATA_WIDTH_A / 16;
    logic [15:0] mem16 [0:WORDS16-1];
    logic [READ_DATA_WIDTH_B-1:0] read_stage = '0;

    initial begin
        doutb = '0;
        sbiterrb = 1'b0;
        dbiterrb = 1'b0;
        // This is a deliberately limited bridge model, not a general XPM.
        if ((READ_LATENCY_B != 1 && READ_LATENCY_B != 2) ||
            READ_DATA_WIDTH_B != 16 || BYTE_WRITE_WIDTH_A != 8 ||
            (WRITE_DATA_WIDTH_A != 16 && WRITE_DATA_WIDTH_A != 64))
            $fatal(1, "Unsupported bridge XPM model configuration");
    end

    always @(posedge clka) begin
        if (!sleep && ena) begin
            for (integer lane = 0; lane < LANES16; lane = lane + 1) begin
                for (integer byte_lane = 0; byte_lane < 2; byte_lane = byte_lane + 1) begin
                    if (wea[lane*2+byte_lane])
                        mem16[addra*LANES16+lane][byte_lane*8 +: 8] <=
                            dina[lane*16+byte_lane*8 +: 8];
                end
            end
        end
    end

    generate
        if (READ_LATENCY_B == 1) begin : g_latency_one
            always @(posedge clkb) begin
                if (rstb) doutb <= '0;
                else if (!sleep && enb) doutb <= mem16[addrb];
            end
        end else begin : g_latency_two
            // XPM latency counts the memory sample itself. A request at N
            // samples data at N and reaches doutb at N+1; the bridge's
            // output register then returns it with the token at N+2.
            // enb enables the memory sample; regceb enables the final reg.
            // Do not delay only the address and read a later memory value.
            always @(posedge clkb) begin
                if (!sleep && enb) read_stage <= mem16[addrb];
                if (rstb) doutb <= '0;
                else if (!sleep && regceb) doutb <= read_stage;
            end
        end
    endgenerate
endmodule
