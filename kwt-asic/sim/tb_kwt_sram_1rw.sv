`timescale 1ns/1ps
module tb_kwt_sram_1rw;
    parameter integer WIDTH = 16;
    parameter integer DEPTH = 128;
    parameter integer BACKEND = 0;
    localparam integer AW = (DEPTH <= 1 ? 1 : $clog2(DEPTH));
    logic clk = 0;
    always #5 clk = ~clk;
    logic rst_n = 0, wr_en = 0, rd_en = 0;
    logic [AW-1:0] wr_addr = 0, rd_addr = 0;
    logic [WIDTH-1:0] wr_data = 0;
    wire [WIDTH-1:0] rd_data;
    wire rd_valid;
    integer checks = 0, error_case = 0;
    logic [WIDTH-1:0] held;
    logic [63:0] signature = 64'h7193a5c7;
    kwt_sram_1rw #(.WIDTH(WIDTH), .DEPTH(DEPTH), .BACKEND(BACKEND)) dut(.*);

    function automatic [WIDTH-1:0] pattern(input integer a);
        reg [63:0] wide;
        begin
            wide = 64'h9e3779b97f4a7c15 ^ (64'h100000001b3 * (a+1));
            pattern = wide[WIDTH-1:0];
        end
    endfunction
    task automatic request(input bit we, input integer wa, input [WIDTH-1:0] wd,
                           input bit re, input integer ra);
        reg [WIDTH-1:0] before_data;
        reg before_valid;
        begin
            @(negedge clk);
            before_data = rd_data;
            before_valid = rd_valid;
            wr_en = we; wr_addr = AW'(wa); wr_data = wd;
            rd_en = re; rd_addr = AW'(ra);
            #1;
            if (rd_data !== before_data || rd_valid !== before_valid)
                $fatal(1, "ASYNCHRONOUS_READ_OR_VALID_CHANGE");
            @(posedge clk); #1;
        end
    endtask
    task automatic check_read(input integer a);
        begin
            request(0, 0, 0, 1, a);
            if (rd_valid !== 1 || rd_data !== pattern(a))
                $fatal(1, "MEMORY_READ_MISMATCH address=%0d got=%h expected=%h valid=%b", a, rd_data, pattern(a), rd_valid);
            signature = (signature << 3) ^ (signature >> 1) ^ rd_data ^ a;
            checks = checks + 1;
        end
    endtask
    initial begin
        if (WIDTH > 64) $fatal(1, "test pattern supports widths <=64");
        if ($value$plusargs("ERROR_CASE=%d", error_case)) begin end
        repeat (2) @(negedge clk);
        if (rd_valid !== 0) $fatal(1, "RESET_VALID_NOT_ZERO");
        rst_n = 1;
        if (error_case != 0) begin
            case (error_case)
                1: request(1, 0, pattern(0), 1, 0);
                2: request(1, 0, pattern(0), 1, 1);
                3: request(0, 0, 0, 1, 0);
                4: request(0, 0, 0, 1, DEPTH);
                5: request(1, DEPTH, pattern(0), 0, 0);
                6: begin @(negedge clk); rd_en = 1'bx; @(posedge clk); #1; end
                7: begin @(negedge clk); rd_en = 1; rd_addr = 'x; @(posedge clk); #1; end
                8: begin @(negedge clk); wr_en = 1; wr_data = 'x; @(posedge clk); #1; end
                9: begin @(negedge clk); wr_en = 1; wr_addr = 'x; wr_data = 16'h1234; @(posedge clk); #1; end
                default: $fatal(1, "unknown test ERROR_CASE");
            endcase
            $fatal(1, "EXPECTED_DIAGNOSTIC_NOT_TRIGGERED");
        end

        // Task loading is explicit. No memory-wide reset is used.
        for (integer a=0; a<DEPTH; a=a+1) begin
            request(1, a, pattern(a), 0, 0);
            if (rd_valid !== 0) $fatal(1, "WRITE_HAS_READ_VALID");
        end
        // Continuous read requests include the first/last and all boundaries.
        for (integer a=0; a<DEPTH; a=a+1) check_read(a);
        check_read(0); check_read(DEPTH-1); check_read(DEPTH-1);
        held = rd_data;
        repeat (3) begin
            request(0, 0, 0, 0, 0);
            if (rd_valid !== 0 || rd_data !== held) $fatal(1, "IDLE_Q_NOT_HELD");
            checks = checks + 1;
        end
        // Alternating writes and reads prove back-to-back direction changes.
        for (integer a=0; a<8; a=a+1) begin
            request(1, a%DEPTH, pattern(a%DEPTH), 0, 0);
            check_read(a%DEPTH);
        end
        held = rd_data;
        @(negedge clk); rst_n = 0; wr_en = 0; rd_en = 0; #1;
        if (rd_valid !== 0) $fatal(1, "ASYNC_RESET_VALID_NOT_ZERO");
        repeat (2) @(negedge clk);
        if (rd_data !== held) $fatal(1, "RESET_CHANGED_Q");
        rst_n = 1;
        check_read(0); check_read(DEPTH-1);
        request(0, 0, 0, 0, 0);
        $display("PASS KWT_SRAM_UNIT width=%0d depth=%0d checks=%0d signature=%016h", WIDTH, DEPTH, checks, signature);
        $finish;
    end
    initial begin #2000000; $fatal(1, "MEMORY_TEST_TIMEOUT"); end
endmodule
