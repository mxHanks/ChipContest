// Exhaustive check of the only cast transformation used by run_structural.py.
module check_cast_lowering;
    logic [13:0] load_addr;
    logic [7:0] block_index, emit_lane;
    logic [5:0] k_issue;
    integer i;
    initial begin
        for (i=0; i<16384; i=i+1) begin
            load_addr=14'(i);
            if (int'(load_addr) !== $signed(32'(load_addr))) $fatal(1,"load_addr cast");
        end
        for (i=0; i<256; i=i+1) begin
            block_index=8'(i); emit_lane=8'(255-i);
            if (int'(block_index) !== $signed(32'(block_index))) $fatal(1,"block_index cast");
            if (int'(emit_lane) !== $signed(32'(emit_lane))) $fatal(1,"emit_lane cast");
        end
        for (i=0; i<64; i=i+1) begin
            k_issue=6'(i);
            if (int'(k_issue) !== $signed(32'(k_issue))) $fatal(1,"k_issue cast");
        end
        // Do not claim four-state equivalence: Icarus 12 int' converts X/Z
        // bits to zero while its sized casts preserve them. This check covers
        // every initialized index value used in synthesized valid behavior.
        $display("PASS CAST_LOWERING_BINARY values=16960");
        $finish;
    end
endmodule
