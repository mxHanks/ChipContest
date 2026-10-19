`timescale 1ns/1ps
module tb_kwt_sram_init;
    parameter integer BACKEND = 0;
    parameter INIT_FILE = "sim/vectors/sram-init-8.mem";
    logic clk = 0;
    always #5 clk = ~clk;
    logic rst_n = 0, wr_en = 0, rd_en = 0;
    logic [2:0] wr_addr = 0, rd_addr = 0;
    logic [15:0] wr_data = 0;
    wire [15:0] rd_data;
    wire rd_valid;
    kwt_sram_1rw #(.WIDTH(16), .DEPTH(8), .BACKEND(BACKEND), .INIT_FILE(INIT_FILE)) dut(.*);
    initial begin
        repeat (2) @(negedge clk);
        rst_n = 1;
        for (integer a=0; a<8; a=a+1) begin
            @(negedge clk); rd_en = 1; rd_addr = 3'(a);
            @(posedge clk); #1;
            if (rd_valid !== 1 || rd_data !== 16'(16'h1200+a)) $fatal(1, "INIT_FILE_READ_MISMATCH address=%0d", a);
        end
        $display("PASS KWT_SRAM_INIT words=8");
        $finish;
    end
endmodule
