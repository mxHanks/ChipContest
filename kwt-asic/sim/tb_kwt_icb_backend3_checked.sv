`timescale 1ns/1ps

// Independent observation of the preserved ICB stimulus and real SRAM core.
// BACKEND=3 must be supplied explicitly by the runner. A development adapter
// qualifies this flow only; this top does not establish official macro/PPA
// acceptance. Verilator runs remain two-state even with these X/Z checks.
module tb_kwt_icb_backend3_checked;
    tb_kwt_icb_slave_sram #(.SRAM_BACKEND(3)) bench ();

    localparam integer EXPECTED_OUTPUTS = 4 + 99 * 256;
    localparam integer EXPECTED_HOLDS = 19 * 2 + 4 * (3 + 5) + 9 + 7;
    // Two full payload loads, four transfers per full-task output, and 85
    // fixed control/abort transfers. Additional STATUS polling is legal.
    localparam integer MIN_TRANSACTIONS =
        2 * (6 + 2 * 6336 + 2 * 16384 + 3 * 256) + 4 * 25344 + 85;

    // These totals deliberately survive every reset in the preserved bench.
    integer accepted_outputs = 0;
    integer accepted_commands = 0;
    integer accepted_responses = 0;
    integer response_holds = 0;
    integer reset_discarded_responses = 0;
    reg response_was_stalled = 0;
    reg [31:0] held_response_data = 0;
    reg held_response_error = 0;
    reg monitor_failed = 0;

    // The final raw ID request is accepted, then reset discards its pending
    // response before any response-acceptance edge. It is not an xfer().
    // NBA reset assignments leave the pre-reset pending flag visible here.
    always @(negedge bench.rst_n) begin
        if (bench.rsp_valid === 1'b1)
            reset_discarded_responses = reset_discarded_responses + 1;
    end

    // Observe handshakes before the DUT's NBA updates, at their actual edge.
    // Reset clears only the response stability history, never the totals.
    always @(posedge bench.clk or negedge bench.rst_n) begin
        if (bench.rst_n === 1'b0) begin
            response_was_stalled = 0;
        end else if (bench.rst_n === 1'b1) begin
            if ((^{bench.cmd_valid, bench.cmd_ready, bench.cmd_read,
                   bench.rsp_valid, bench.rsp_ready, bench.rsp_err,
                   bench.dut.engine_y_valid, bench.dut.engine_y_ready}) === 1'bx) begin
                monitor_failed = 1;
                $fatal(1, "ICB_BACKEND3_MONITOR_UNKNOWN_CONTROL");
            end

            if (response_was_stalled &&
                (bench.rsp_valid !== 1'b1 ||
                 bench.rsp_rdata !== held_response_data ||
                 bench.rsp_err !== held_response_error)) begin
                monitor_failed = 1;
                $fatal(1, "ICB_BACKEND3_MONITOR_RESPONSE_CHANGED_UNDER_BACKPRESSURE");
            end

            if (bench.cmd_valid === 1'b1 && bench.cmd_ready === 1'b1) begin
                if ((^{bench.cmd_addr, bench.cmd_read, bench.cmd_wdata,
                       bench.cmd_wmask}) === 1'bx) begin
                    monitor_failed = 1;
                    $fatal(1, "ICB_BACKEND3_MONITOR_UNKNOWN_COMMAND_PAYLOAD");
                end
                accepted_commands = accepted_commands + 1;
            end

            // Also require known payload while stalled: comparing two X
            // payloads for stability must never qualify a valid response.
            if (bench.rsp_valid === 1'b1) begin
                if ((^{bench.rsp_rdata, bench.rsp_err}) === 1'bx) begin
                    monitor_failed = 1;
                    $fatal(1, "ICB_BACKEND3_MONITOR_UNKNOWN_RESPONSE_PAYLOAD");
                end
                if (bench.rsp_ready === 1'b1)
                    accepted_responses = accepted_responses + 1;
            end

            response_was_stalled =
                (bench.rsp_valid === 1'b1 && bench.rsp_ready === 1'b0);
            if (response_was_stalled) begin
                held_response_data = bench.rsp_rdata;
                held_response_error = bench.rsp_err;
                response_holds = response_holds + 1;
            end

            if (bench.dut.engine_y_valid === 1'b1 &&
                bench.dut.engine_y_ready === 1'b1) begin
                if ((^{bench.dut.engine_y_data, bench.dut.engine_y_index,
                       bench.dut.engine_y_last}) === 1'bx) begin
                    monitor_failed = 1;
                    $fatal(1, "ICB_BACKEND3_MONITOR_UNKNOWN_ACCEPTED_OUTPUT");
                end
                accepted_outputs = accepted_outputs + 1;
            end
        end else begin
            monitor_failed = 1;
            $fatal(1, "ICB_BACKEND3_MONITOR_UNKNOWN_RESET");
        end
    end

    // The preserved bench owns $finish and its watchdog. A partial finish,
    // failed assertion or watchdog cannot obtain this completion marker.
    final begin
        if (monitor_failed !== 1'b0 ||
            accepted_outputs !== EXPECTED_OUTPUTS ||
            response_holds !== EXPECTED_HOLDS ||
            bench.protocol_checks !== EXPECTED_HOLDS ||
            (bench.transactions >= MIN_TRANSACTIONS) !== 1'b1 ||
            accepted_responses !== bench.transactions ||
            accepted_commands !== accepted_responses + 1 ||
            reset_discarded_responses !== 1 ||
            bench.rst_n !== 1'b1 || bench.cmd_valid !== 1'b0 ||
            bench.rsp_valid !== 1'b0 || bench.rsp_ready !== 1'b0 ||
            bench.result !== 32'h00000002 ||
            bench.dut.output_count !== 15'd0 ||
            bench.dut.engine_y_ready !== 1'b0) begin
            $fatal(1, "ICB_BACKEND3_MONITOR_INCOMPLETE accepted_outputs=%0d response_holds=%0d protocol_checks=%0d transactions=%0d accepted_commands=%0d accepted_responses=%0d reset_discarded_responses=%0d",
                   accepted_outputs, response_holds, bench.protocol_checks,
                   bench.transactions, accepted_commands, accepted_responses,
                   reset_discarded_responses);
        end else begin
            $display("PASS ICB_BACKEND3_MONITOR accepted_outputs=%0d response_holds=%0d accepted_commands=%0d accepted_responses=%0d reset_discarded_responses=%0d",
                     accepted_outputs, response_holds, accepted_commands,
                     accepted_responses, reset_discarded_responses);
        end
    end
endmodule
