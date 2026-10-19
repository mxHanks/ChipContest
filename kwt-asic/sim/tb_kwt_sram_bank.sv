`timescale 1ns/1ps
module tb_kwt_sram_bank #(
    parameter integer WIDTH=41, DEPTH=3200, BACKEND=0,
    parameter integer AW=$clog2(DEPTH)
);
    reg clk=0, rst_n=0, wr_en=0, rd_en=0;
    reg [AW-1:0] wr_addr=0, rd_addr=0;
    reg [WIDTH-1:0] wr_data=0;
    wire [WIDTH-1:0] rd_data;
    wire rd_valid;
    reg [WIDTH-1:0] held;
    reg [WIDTH-1:0] seen_zero='0, seen_one='0;
    integer checks=0, error_case=0;
    always #5 clk=~clk;
    kwt_sram_bank #(.WIDTH(WIDTH),.DEPTH(DEPTH),.BACKEND(BACKEND)) dut (.*);
    function automatic [WIDTH-1:0] pattern(input integer address);
        reg [63:0] value;
        begin
            value=64'hd61b_927a_f5a3_0c19 ^ (64'h1357_9bd1*address);
            // Toggle the upper width slice, including bit40 of the result word.
            // The old address-product pattern left that bit constantly zero.
            pattern=WIDTH'(value ^ (address[0] ? 64'hffff_ffff_0000_0000 : 64'b0));
        end
    endfunction
    task automatic read_check(input integer address);
        @(negedge clk); rd_en=1; rd_addr=AW'(address);
        @(posedge clk); #1;
        if (rd_valid !== 1'b1 || rd_data !== pattern(address))
            $fatal(1,"BANK read address=%0d expected=%h actual=%h valid=%b",address,pattern(address),rd_data,rd_valid);
        seen_zero=seen_zero | ~rd_data;
        seen_one=seen_one | rd_data;
        checks=checks+1;
    endtask
    initial begin
        repeat(2) @(negedge clk);
        if (rd_valid !== 0) $fatal(1,"BANK reset valid");
        rst_n=1;
        if ($value$plusargs("ERROR_CASE=%d",error_case)) begin
            if (error_case == 5) begin
                // Isolate the bank conflict: both addresses are initialized,
                // so an unrelated primitive uninitialized-read check cannot
                // hide the cross-tile single-port violation.
                @(negedge clk); wr_en=1;wr_addr=AW'(1024);wr_data='0;
                @(negedge clk); wr_en=0;
            end
            @(negedge clk);
            wr_addr=AW'(DEPTH); rd_addr=AW'(DEPTH);
            case(error_case)
                1: wr_en=1'bx;
                2: wr_en=1'bz;
                3: rd_en=1'bx;
                4: rd_en=1'bz;
                5: begin wr_en=1;rd_en=1;wr_addr=0;rd_addr=AW'(1024);end
                6: wr_en=1;
                7: rd_en=1;
                8: begin
                    // Keep the upper address bits outside all logical tiles,
                    // isolating the bank's original-address check from the
                    // primitive's independent unknown-enable diagnostics.
                    rd_en=1;rd_addr='1;rd_addr[0]=1'bx;
                end
                default:$fatal(1,"invalid test ERROR_CASE");
            endcase
            @(posedge clk); #1;
            $fatal(1,"EXPECTED_DIAGNOSTIC_NOT_TRIGGERED");
        end
        // Fill through the normal write interface, not reset or backdoor init.
        for(integer i=0;i<DEPTH;i=i+1) begin
            @(negedge clk); wr_en=1; wr_addr=AW'(i); wr_data=pattern(i);
        end
        @(negedge clk); wr_en=0;
        for(integer i=0;i<DEPTH;i=i+1) read_check(i);
        // Reverse order forces bank selection changes at all physical boundaries.
        for(integer i=DEPTH-1;i>=0;i=i-1) read_check(i);
        read_check(0); read_check(0); read_check(DEPTH-1);
        @(negedge clk); rd_en=0; held=rd_data;
        repeat(3) begin
            @(posedge clk); #1;
            if (rd_valid !== 0 || rd_data !== held) $fatal(1,"BANK disabled Q not held");
        end
        // Reset invalidates responses but deliberately preserves payload.
        @(negedge clk); rst_n=0;
        @(negedge clk); rst_n=1;
        read_check(0); read_check(DEPTH-1);
        if (seen_zero !== {WIDTH{1'b1}} || seen_one !== {WIDTH{1'b1}})
            $fatal(1,"BANK test did not cover both values of every width bit");
        $display("PASS KWT_SRAM_BANK_WIDTH_COVERAGE width=%0d bits_both=%0d",WIDTH,WIDTH);
        $display("PASS KWT_SRAM_BANK backend=%0d width=%0d depth=%0d checks=%0d",BACKEND,WIDTH,DEPTH,checks);
        $finish;
    end
endmodule
