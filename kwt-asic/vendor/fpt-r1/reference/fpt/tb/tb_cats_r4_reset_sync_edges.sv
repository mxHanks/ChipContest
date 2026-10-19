`timescale 1ns/1ps
module tb_cats_r4_reset_sync_edges #(
    parameter integer STAGES = 3,
    parameter integer HOLD_CYCLES = 16,
    parameter integer HALF = 5
);
    logic clk = 0, clock_enable = 1, arst_n = 1;
    wire srst_n;
    integer active_edges = 0;
    integer checks = 0;
    integer assertions = 0;
    always #(HALF) if (clock_enable) clk = ~clk;
    cats_r4_reset_sync #(.STAGES(STAGES), .HOLD_CYCLES(HOLD_CYCLES)) dut (.*);
    always @(posedge clk or negedge arst_n) begin
        if (!arst_n) active_edges = 0;
        else active_edges = active_edges + 1;
        #0.1;
        if (srst_n !== (arst_n && active_edges >= STAGES + HOLD_CYCLES))
            $fatal(1, "reset edge mismatch S=%0d H=%0d edges=%0d reset=%b output=%b",
                   STAGES, HOLD_CYCLES, active_edges, arst_n, srst_n);
        checks = checks + 1;
    end
    task automatic assert_reset;
        begin
            arst_n = 0;
            #0.2;
            if (srst_n !== 0) $fatal(1, "asynchronous assertion failed");
            assertions = assertions + 1;
        end
    endtask
    initial begin
        #1000000;
        $fatal(1, "reset edge watchdog");
    end
    initial begin
        #1;
        assert_reset();
        for (integer phase = 0; phase < 2 * HALF; phase = phase + 1) begin
            @(negedge clk);
            #0.3;
            #(phase);
            arst_n = 1;
            wait (srst_n);
            repeat (3) @(negedge clk);
            #0.7;
            assert_reset();
        end
        // A pulse shorter than one period restarts both synchronizer and hold.
        arst_n = 1;
        repeat (STAGES + HOLD_CYCLES/2) @(negedge clk);
        #0.4;
        assert_reset();
        #0.3;
        arst_n = 1;
        wait (srst_n);
        @(negedge clk);
        clock_enable = 0;
        #0.7;
        assert_reset();
        #(HALF * 4);
        arst_n = 1;
        #(HALF * 9);
        if (srst_n !== 0) $fatal(1, "reset released without clock");
        clock_enable = 1;
        wait (srst_n);
        repeat (2) @(negedge clk);
        $display("PASS RESET_SYNC_EDGES stages=%0d hold=%0d half=%0d checks=%0d assertions=%0d stopped_clock=1",
                 STAGES,HOLD_CYCLES,HALF,checks,assertions);
        $finish;
    end
endmodule
