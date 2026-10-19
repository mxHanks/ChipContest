`timescale 1ns/1ps

// Protocol regression with the real row-pair core (no behavioral MAC mock).
// Full zero X/W payloads produce known signed bias results; the SoC regression
// separately checks nonzero real-model products and actual external writeback.
module tb_kwt_icb_slave;
    reg clk = 0;
    always #5 clk = !clk;
    reg rst_n = 0;
    reg cmd_valid = 0;
    wire cmd_ready;
    reg [31:0] cmd_addr = 0;
    reg cmd_read = 0;
    reg [31:0] cmd_wdata = 0;
    reg [3:0] cmd_wmask = 4'hf;
    wire rsp_valid;
    reg rsp_ready = 0;
    wire [31:0] rsp_rdata;
    wire rsp_err;
    integer transactions = 0;
    integer protocol_checks = 0;
    integer i;
    reg [31:0] result;
    reg [39:0] bias_payload;
    reg [31:0] expected;

    kwt_icb_slave dut (
        .clk(clk), .rst_n(rst_n), .icb_cmd_valid(cmd_valid), .icb_cmd_ready(cmd_ready),
        .icb_cmd_addr(cmd_addr), .icb_cmd_read(cmd_read), .icb_cmd_wdata(cmd_wdata),
        .icb_cmd_wmask(cmd_wmask), .icb_rsp_valid(rsp_valid), .icb_rsp_ready(rsp_ready),
        .icb_rsp_rdata(rsp_rdata), .icb_rsp_err(rsp_err)
    );

    task automatic xfer(input [31:0] addr, input bit is_read,
        input [31:0] data, input [3:0] mask, input bit want_error,
        input integer hold_cycles, input bit want_pop, output [31:0] value);
        reg [31:0] held_data;
        reg held_error;
        reg [14:0] held_count;
        integer n;
        begin
            @(negedge clk);
            cmd_addr = addr; cmd_read = is_read; cmd_wdata = data;
            cmd_wmask = mask; cmd_valid = 1; rsp_ready = 0;
            do @(posedge clk); while (!cmd_ready);
            @(negedge clk);
            cmd_valid = 0;
            if (!rsp_valid) $fatal(1, "missing response addr=%h", addr);
            if (rsp_err !== want_error)
                $fatal(1, "response error addr=%h actual=%b expected=%b", addr, rsp_err, want_error);
            held_data = rsp_rdata; held_error = rsp_err;
            held_count = dut.output_count;
            for (n = 0; n < hold_cycles; n = n + 1) begin
                @(posedge clk); @(negedge clk);
                if (!rsp_valid || cmd_ready || rsp_rdata !== held_data || rsp_err !== held_error)
                    $fatal(1, "response changed under backpressure addr=%h", addr);
                if (dut.engine_y_ready || dut.output_count != held_count)
                    $fatal(1, "Y popped before response acceptance");
                if (want_pop && dut.y_snapshot_last && (dut.core_done_sticky || !dut.engine_busy))
                    $fatal(1, "core completion preceded final HI response acceptance");
                if (!want_error && !is_read && addr == 32'h10042008 && data == 2 &&
                    (dut.software_done || !dut.window_active))
                    $fatal(1, "software completion preceded ACK response acceptance");
                protocol_checks = protocol_checks + 1;
            end
            value = held_data;
            rsp_ready = 1;
            #1;
            if (dut.engine_y_ready !== want_pop)
                $fatal(1, "unexpected Y ready addr=%h actual=%b expected=%b", addr, dut.engine_y_ready, want_pop);
            @(posedge clk); @(negedge clk);
            rsp_ready = 0;
            if (rsp_valid) $fatal(1, "response did not retire");
            if (dut.output_count != held_count + (want_pop ? 1 : 0))
                $fatal(1, "incorrect Y pop count");
            transactions = transactions + 1;
        end
    endtask

    task automatic load_full_payload;
        integer j;
        reg [39:0] payload;
        begin
            wr(12'h020, 0); wr(12'h024, 0);
            for (j = 0; j < 6336; j = j + 1) begin wr(12'h028, 0); wr(12'h030, 1); end
            wr(12'h020, 1); wr(12'h024, 0);
            for (j = 0; j < 16384; j = j + 1) begin wr(12'h028, 0); wr(12'h030, 1); end
            wr(12'h020, 2); wr(12'h024, 0);
            for (j = 0; j < 256; j = j + 1) begin
                payload = 40'(j - 128);
                wr(12'h028, payload[31:0]); wr(12'h02c, {24'b0,payload[39:32]}); wr(12'h030, 1);
            end
        end
    endtask

    task automatic wr(input [11:0] offset, input [31:0] data);
        reg [31:0] unused;
        begin xfer(32'h10042000 + {20'b0, offset}, 0, data, 4'hf, 0, 0, 0, unused); end
    endtask

    task automatic rd(input [11:0] offset, output [31:0] data);
        begin xfer(32'h10042000 + {20'b0, offset}, 1, 0, 0, 0, 0, offset == 12'h044, data); end
    endtask

    task automatic bad(input [31:0] addr, input bit is_read,
        input [31:0] data, input [3:0] mask, input [7:0] code);
        reg [31:0] unused;
        begin
            xfer(addr, is_read, data, mask, 1, 2, 0, unused);
            rd(12'h00c, unused);
            if (unused[7:0] != code) $fatal(1, "incorrect error diagnostic");
        end
    endtask

    task automatic reset_command;
        reg [31:0] status;
        begin
            wr(12'h008, 4);
            rd(12'h004, status);
            if (status !== 32'h00000002) $fatal(1, "abort reset did not clear adapter/core status=%h", status);
            if (dut.u_engine.x_loaded != 0 || dut.u_engine.w_loaded != 0 || dut.u_engine.b_loaded != 0)
                $fatal(1, "abort reset did not invalidate core payload");
        end
    endtask

    initial begin
        repeat (4) @(negedge clk);
        rst_n = 1;
        rd(12'h000, result);
        if (result != 32'h4b575431) $fatal(1, "wrong adapter ID");
        bad(32'h10042005, 1, 0, 0, 1); // unaligned
        bad(32'h10043000, 1, 0, 0, 1); // outside selected 4 KiB
        bad(32'h10042020, 0, 1, 4'h1, 3); // partial write
        bad(32'h10042000, 0, 1, 4'hf, 2); // write RO
        bad(32'h10042034, 1, 0, 0, 2); // undefined register
        bad(32'h10042008, 0, 1, 4'hf, 5); // early start
        bad(32'h10042030, 0, 1, 4'hf, 8); // incomplete load
        bad(32'h10042044, 1, 0, 0, 10); // HI before LO
        bad(32'h10042040, 1, 0, 0, 9); // output empty
        bad(32'h10042008, 0, 2, 4'hf, 11); // early writeback ack
        bad(32'h10042020, 0, 3, 4'hf, 4); // invalid kind
        wr(12'h020, 0); wr(12'h024, 1); wr(12'h028, 16'h1234);
        bad(32'h10042030, 0, 1, 4'hf, 7); // out-of-sequence word
        if (dut.u_engine.x_loaded != 0) $fatal(1, "invalid commit changed core load count");
        wr(12'h024, 0); wr(12'h028, 32'hffff8000);
        bad(32'h10042030, 0, 1, 4'hf, 4); // noncanonical int16 encoding
        reset_command();
        wr(12'h020, 2); wr(12'h024, 0); wr(12'h028, 32'hffffff80);
        bad(32'h10042030, 0, 1, 4'hf, 8); // missing fresh high bias byte
        wr(12'h02c, 255); wr(12'h030, 1);
        if (dut.u_engine.b_loaded != 1 || dut.load_addr != 1 || dut.lo_valid || dut.hi_valid)
            $fatal(1, "bias commit did not atomically load/auto-increment/invalidate payload");
        bad(32'h10042030, 0, 1, 4'hf, 8); // cannot reuse payload
        reset_command();

        // First task aborts while busy after four outputs.
        load_full_payload();
        rd(12'h004, result);
        if (!(result & 32'h4)) $fatal(1, "legal payload did not make START ready");
        wr(12'h008, 1);
        bad(32'h10042008, 0, 1, 4'hf, 5); // duplicate start
        bad(32'h10042028, 0, 0, 4'hf, 5); // busy load
        wait (dut.engine_y_valid);
        for (i = 0; i < 4; i = i + 1) begin
            expected = 32'(i - 128);
            xfer(32'h10042040, 1, 0, 0, 0, 3, 0, result);
            if (result !== expected) $fatal(1, "wrong signed bias result LO");
            rd(12'h040, result);
            if (result !== expected) $fatal(1, "repeat LO changed snapshot");
            rd(12'h048, result);
            if (result !== 32'(i)) $fatal(1, "snapshot index changed");
            xfer(32'h10042044, 1, 0, 0, 0, 5, 1, result);
            if (result !== 32'h0000ffff) $fatal(1, "wrong sign-extended 48-bit HI");
        end
        rd(12'h014, result);
        if (result != 4) $fatal(1, "wrong number of accepted output words");
        reset_command();

        // A fresh task reaches the final output and software ACK. It proves
        // adapter completion semantics, but contains no external memory model.
        load_full_payload();
        wr(12'h008, 1);
        wait (dut.engine_y_valid);
        for (i = 0; i < 25344; i = i + 1) begin
            expected = 32'((i % 256) - 128);
            rd(12'h040, result);
            if (result !== expected) $fatal(1, "full task LO mismatch index=%0d", i);
            rd(12'h048, result);
            if (result !== (32'(i) | ((i == 25343) ? 32'h80000000 : 32'b0)))
                $fatal(1, "full task index/last mismatch index=%0d", i);
            xfer(32'h10042044, 1, 0, 0, 0, (i == 25343) ? 9 : 0, 1, result);
            if (result !== ((i % 256 < 128) ? 32'h0000ffff : 32'b0))
                $fatal(1, "full task HI mismatch index=%0d", i);
        end
        rd(12'h004, result);
        if ((result & 32'h000000e9) !== 32'h00000020)
            $fatal(1, "wrong final core/software status=%h", result);
        rd(12'h014, result);
        if (result != 25344) $fatal(1, "full output count mismatch");
        xfer(32'h10042008, 0, 2, 4'hf, 0, 7, 0, result);
        rd(12'h004, result);
        if (!(result & 32'h40) || (result & 32'h400)) $fatal(1, "software ACK did not stop local window");
        rd(12'h018, result);
        if (!result) $fatal(1, "full local window was not measured");
        wr(12'h020, 0);
        rd(12'h004, result);
        if ((result & 32'h00000260) || !(result & 32'h400))
            $fatal(1, "next task did not clear old completion/start new local window");
        bad(32'h10042008, 0, 1, 4'hf, 5); // prior payload cannot be reused
        bad(32'h10042030, 0, 1, 4'hf, 8);
        reset_command();

        // Asynchronous reset must discard a pending, backpressured response.
        @(negedge clk); cmd_valid = 1; cmd_read = 1; cmd_addr = 32'h10042000;
        @(posedge clk); @(negedge clk); cmd_valid = 0;
        if (!rsp_valid) $fatal(1, "test did not create pending response");
        rst_n = 0; #1;
        if (rsp_valid || cmd_ready || dut.engine_y_ready) $fatal(1, "reset left protocol validity asserted");
        repeat (2) @(negedge clk);
        rst_n = 1;
        rd(12'h004, result);
        if (result !== 32'h2) $fatal(1, "external reset did not restore empty load phase");
        $display("ICB_ADAPTER_PASS transactions=%0d hold_checks=%0d actual_core_outputs=25348 complete_tasks=1 aborted_tasks=1", transactions, protocol_checks);
        $finish;
    end

    initial begin
        #20000000;
        $fatal(1, "ICB adapter protocol timeout");
    end
endmodule
