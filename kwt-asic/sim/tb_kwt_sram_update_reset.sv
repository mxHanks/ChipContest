`timescale 1ns/1ps

// Additional logical-contract coverage; a development adapter is not an
// official macro. No initialization file or unknown initial Q is assumed.
module tb_kwt_sram_update_reset #(
    parameter integer WIDTH = 16,
    parameter integer DEPTH = 128,
    parameter integer BACKEND = 0,
    parameter integer USE_BANK = 0
);
    localparam integer AW = DEPTH <= 1 ? 1 : $clog2(DEPTH);
    localparam integer N4096 = DEPTH / 4096;
    localparam integer N1024 = (DEPTH % 4096) / 1024;
    localparam integer N128 = ((DEPTH % 1024) + 127) / 128;
    localparam integer NTILES = N4096 + N1024 + N128;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0, wr_en = 0, rd_en = 0;
    reg [AW-1:0] wr_addr = 0, rd_addr = 0;
    reg [WIDTH-1:0] wr_data = 0;
    wire [WIDTH-1:0] rd_data;
    wire rd_valid;

    generate
        if (USE_BANK == 0) begin : g_unit
            kwt_sram_1rw #(.WIDTH(WIDTH), .DEPTH(DEPTH), .BACKEND(BACKEND)) dut
                (.clk(clk), .rst_n(rst_n), .wr_en(wr_en), .wr_addr(wr_addr),
                 .wr_data(wr_data), .rd_en(rd_en), .rd_addr(rd_addr),
                 .rd_data(rd_data), .rd_valid(rd_valid));
        end else begin : g_bank
            kwt_sram_bank #(.WIDTH(WIDTH), .DEPTH(DEPTH), .BACKEND(BACKEND)) dut
                (.clk(clk), .rst_n(rst_n), .wr_en(wr_en), .wr_addr(wr_addr),
                 .wr_data(wr_data), .rd_en(rd_en), .rd_addr(rd_addr),
                 .rd_data(rd_data), .rd_valid(rd_valid));
        end
    endgenerate

    integer addresses [0:DEPTH-1];
    integer address_count = 0;
    reg [WIDTH-1:0] expected [0:DEPTH-1];
    reg [WIDTH-1:0] last_q, observed_a, changed_word;
    reg [WIDTH-1:0] flipped_bits = '0;
    reg q_known = 0;
    reg [63:0] signature = 64'h8614_c2e9_5b37_a10d;
    integer overwrite_checks = 0;
    integer reset_write_checks = 0;
    integer reset_read_checks = 0;
    integer async_reset_checks = 0;
    integer release_checks = 0;
    integer posedge_count = 0;
    integer pulse_edge_count, i, tile, boundary;
    always @(posedge clk) posedge_count = posedge_count + 1;

    function automatic [WIDTH-1:0] pattern_a(input integer address);
        reg [63:0] wide;
        begin
            wide = 64'hc79a_51d6_e3b0_248f ^ (64'h1000_0000_01b3 * (address + 1));
            pattern_a = wide[WIDTH-1:0];
        end
    endfunction

    task automatic add_address(input integer address);
        integer j;
        reg found;
        begin
            found = 0;
            for (j = 0; j < address_count; j = j + 1)
                if (addresses[j] == address) found = 1;
            if (!found && address >= 0 && address < DEPTH) begin
                if (address_count >= DEPTH) $fatal(1, "UPDATE_RESET_ADDRESS_SET_OVERFLOW");
                addresses[address_count] = address;
                address_count = address_count + 1;
            end
        end
    endtask

    task automatic fold_signature(input integer address, input integer tag);
        reg [63:0] wide_data;
        begin
            wide_data = rd_data;
            signature = (signature << 3) ^ (signature >> 1) ^ wide_data ^ address ^ tag;
        end
    endtask

    task automatic expect_hold(input integer address, input integer tag, input string phase);
        begin
            if (!q_known) $fatal(1, "UPDATE_RESET_CHECK_BEFORE_KNOWN_Q");
            if (rd_valid !== 1'b0 || rd_data !== last_q)
                $fatal(1, "UPDATE_RESET_HOLD phase=%s address=%0d valid=%b got=%h expected=%h",
                       phase, address, rd_valid, rd_data, last_q);
            fold_signature(address, tag);
        end
    endtask

    task automatic expect_read(input integer address, input [WIDTH-1:0] value,
                               input integer tag, input string phase);
        begin
            if (rd_valid !== 1'b1 || rd_data !== value)
                $fatal(1, "UPDATE_RESET_READ phase=%s address=%0d valid=%b got=%h expected=%h",
                       phase, address, rd_valid, rd_data, value);
            last_q = rd_data;
            q_known = 1;
            fold_signature(address, tag);
        end
    endtask

    task automatic write_word(input integer address, input [WIDTH-1:0] value);
        begin
            @(negedge clk);
            rd_en = 0; wr_en = 1; wr_addr = AW'(address); wr_data = value;
            @(posedge clk); #1;
            if (rd_valid !== 1'b0) $fatal(1, "UPDATE_RESET_WRITE_HAS_READ_VALID");
            if (q_known && rd_data !== last_q) $fatal(1, "UPDATE_RESET_WRITE_CHANGED_Q");
            expected[address] = value;
        end
    endtask

    task automatic read_word(input integer address, input integer tag, input string phase);
        begin
            @(negedge clk);
            wr_en = 0; rd_en = 1; rd_addr = AW'(address);
            @(posedge clk); #1;
            expect_read(address, expected[address], tag, phase);
        end
    endtask

    initial begin
        if (WIDTH < 1 || WIDTH > 64 || DEPTH < 1 || (USE_BANK != 0 && USE_BANK != 1))
            $fatal(1, "UPDATE_RESET_UNSUPPORTED_TEST_PARAMETERS");
        add_address(0);
        add_address(DEPTH - 1);
        if (USE_BANK == 1) begin
            // Both sides of each actual greedy 4096/1024/128 tile boundary.
            for (tile = 1; tile < NTILES; tile = tile + 1) begin
                boundary = tile < N4096 ? tile * 4096 :
                    tile < N4096 + N1024 ? N4096 * 4096 + (tile - N4096) * 1024 :
                    N4096 * 4096 + N1024 * 1024 + (tile - N4096 - N1024) * 128;
                add_address(boundary - 1);
                add_address(boundary);
            end
        end
        repeat (2) @(negedge clk);
        if (rd_valid !== 1'b0) $fatal(1, "UPDATE_RESET_INITIAL_VALID");
        rst_n = 1;

        // Observe A, then overwrite with its full-width complement B. Reading
        // both proves every bit changed, including padded-bank bits 39/40.
        for (i = 0; i < address_count; i = i + 1) begin
            write_word(addresses[i], pattern_a(addresses[i]));
            read_word(addresses[i], 1, "overwrite-A");
            observed_a = rd_data;
            overwrite_checks = overwrite_checks + 1;
            write_word(addresses[i], ~pattern_a(addresses[i]));
            read_word(addresses[i], 2, "overwrite-B");
            flipped_bits = flipped_bits | (observed_a ^ rd_data);
            overwrite_checks = overwrite_checks + 1;
        end
        if (flipped_bits !== {WIDTH{1'b1}}) $fatal(1, "UPDATE_RESET_INCOMPLETE_BIT_FLIPS");

        // Keep write enable high continuously during reset. Attempt a different
        // word at every selected address for two rising edges per address.
        @(negedge clk);
        rst_n = 0; rd_en = 0; wr_en = 1;
        for (i = 0; i < address_count; i = i + 1) begin
            if (i != 0) @(negedge clk);
            wr_addr = AW'(addresses[i]); wr_data = ~expected[addresses[i]];
            repeat (2) begin
                @(posedge clk); #1;
                expect_hold(addresses[i], 3, "reset-write");
                reset_write_checks = reset_write_checks + 1;
            end
        end
        // Withdraw enable a complete half-cycle/edge before reset release.
        @(negedge clk); wr_en = 0;
        @(negedge clk); rst_n = 1;
        @(posedge clk); #1;
        expect_hold(0, 4, "release-with-enables-low");
        release_checks = release_checks + 1;
        for (i = 0; i < address_count; i = i + 1) begin
            read_word(addresses[i], 5, "payload-after-reset-write");
            reset_write_checks = reset_write_checks + 1;
        end

        // Keep read enable high throughout reset while changing addresses.
        // Q must hold the last known response, not expose a reset-time read.
        @(negedge clk);
        rst_n = 0; wr_en = 0; rd_en = 1;
        for (i = 0; i < address_count; i = i + 1) begin
            if (i != 0) @(negedge clk);
            rd_addr = AW'(addresses[i]);
            repeat (2) begin
                @(posedge clk); #1;
                expect_hold(addresses[i], 6, "reset-read");
                reset_read_checks = reset_read_checks + 1;
            end
        end
        // Read enable is already high when reset is released. The very first
        // rising edge must accept this request with the normal one-edge latency.
        @(negedge clk); rd_addr = AW'(addresses[0]); rst_n = 1;
        @(posedge clk); #1;
        expect_read(addresses[0], expected[addresses[0]], 7, "release-read-enabled");
        release_checks = release_checks + 1;

        // Exercise the corresponding high-write-enable release separately.
        // Low-reset cycles must hold Q; the first active edge must write C.
        @(negedge clk);
        rst_n = 0; rd_en = 0; wr_en = 1;
        wr_addr = AW'(addresses[address_count - 1]);
        changed_word = ~expected[addresses[address_count - 1]];
        wr_data = changed_word;
        repeat (2) begin
            @(posedge clk); #1;
            expect_hold(addresses[address_count - 1], 8, "reset-before-enabled-write-release");
            reset_write_checks = reset_write_checks + 1;
        end
        @(negedge clk); rst_n = 1;
        @(posedge clk); #1;
        expect_hold(addresses[address_count - 1], 9, "release-write-enabled");
        release_checks = release_checks + 1;
        expected[addresses[address_count - 1]] = changed_word;
        read_word(addresses[address_count - 1], 10, "first-enabled-release-write-payload");
        release_checks = release_checks + 1;

        // Prime valid=1, then pulse reset entirely between two rising edges.
        // Valid clears asynchronously; Q and every selected payload survive.
        read_word(addresses[0], 11, "async-reset-prime");
        async_reset_checks = async_reset_checks + 1;
        @(negedge clk);
        wr_en = 0; rd_en = 0; pulse_edge_count = posedge_count; rst_n = 0;
        #1;
        expect_hold(addresses[0], 12, "async-reset-asserted");
        async_reset_checks = async_reset_checks + 1;
        #1; rst_n = 1;
        #1;
        expect_hold(addresses[0], 13, "async-reset-released-before-clock");
        async_reset_checks = async_reset_checks + 1;
        if (posedge_count != pulse_edge_count) $fatal(1, "UPDATE_RESET_ASYNC_PULSE_CROSSED_POSEDGE");
        for (i = 0; i < address_count; i = i + 1) begin
            read_word(addresses[i], 14, "payload-after-async-reset");
            async_reset_checks = async_reset_checks + 1;
        end

        // N is the unique first/last/boundary address count. These counters
        // count the checks in the named groups, not all auxiliary assertions.
        if (overwrite_checks != 2 * address_count ||
            reset_write_checks != 3 * address_count + 2 ||
            reset_read_checks != 2 * address_count ||
            async_reset_checks != address_count + 3 || release_checks != 4)
            $fatal(1, "UPDATE_RESET_COUNTER_MISMATCH");
        @(negedge clk); wr_en = 0; rd_en = 0;
        $display("PASS KWT_SRAM_UPDATE_RESET backend=%0d bank=%0d width=%0d depth=%0d overwrite_checks=%0d reset_write_checks=%0d reset_read_checks=%0d async_reset_checks=%0d release_checks=%0d signature=%016h",
                 BACKEND, USE_BANK, WIDTH, DEPTH, overwrite_checks, reset_write_checks,
                 reset_read_checks, async_reset_checks, release_checks, signature);
        $finish;
    end

    initial begin #2000000; $fatal(1, "KWT_SRAM_UPDATE_RESET_TIMEOUT"); end
endmodule
