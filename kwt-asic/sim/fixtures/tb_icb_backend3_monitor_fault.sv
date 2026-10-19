`timescale 1ns/1ps
// Checker qualification only. Never a production/official source file.
module tb_icb_backend3_monitor_fault;
    tb_kwt_icb_backend3_checked observed ();
    integer fault;
    initial begin
        if (!$value$plusargs("MONITOR_FAULT=%d", fault))
            $fatal(1, "ICB_MONITOR_PROBE_REQUIRES_EXPLICIT_FAULT");
        wait (observed.bench.rst_n === 1'b1);
        case (fault)
            1: begin
                wait (observed.bench.rsp_valid === 1'b1);
                #1;
                force observed.bench.rsp_rdata = 32'hxxxx_xxxx;
            end
            2: begin
                @(negedge observed.bench.clk);
                $finish;
            end
            default: $fatal(1, "ICB_MONITOR_PROBE_INVALID_FAULT");
        endcase
        repeat (8) @(posedge observed.bench.clk);
        $fatal(1, "ICB_MONITOR_PROBE_NOT_DETECTED");
    end
endmodule
