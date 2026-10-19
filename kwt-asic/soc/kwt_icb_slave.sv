`timescale 1ns/1ps

// Single-outstanding ICB adapter for the exact KWT FFN1 row-pair engine.
// See soc/include/kwt_accel_regs.h and docs/integration/ICB_CONTRACT.md.
// A Y word is removed only when the response to its HI read is accepted.
module kwt_icb_slave #(
    parameter logic [31:0] BASE_ADDR = 32'h1004_2000
) (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        icb_cmd_valid,
    output logic        icb_cmd_ready,
    input  logic [31:0] icb_cmd_addr,
    input  logic        icb_cmd_read,
    input  logic [31:0] icb_cmd_wdata,
    input  logic [3:0]  icb_cmd_wmask,
    output logic        icb_rsp_valid,
    input  logic        icb_rsp_ready,
    output logic [31:0] icb_rsp_rdata,
    output logic        icb_rsp_err
);
    localparam logic [11:0] R_ID = 12'h000, R_STATUS = 12'h004,
        R_CONTROL = 12'h008, R_ERROR = 12'h00c, R_CORE_CYCLES = 12'h010,
        R_OUTPUT_COUNT = 12'h014, R_WINDOW_CYCLES = 12'h018,
        R_LOAD_KIND = 12'h020, R_LOAD_ADDR = 12'h024,
        R_LOAD_LO = 12'h028, R_LOAD_HI = 12'h02c, R_LOAD_COMMIT = 12'h030,
        R_Y_LO = 12'h040, R_Y_HI = 12'h044, R_Y_INDEX = 12'h048;
    localparam logic [7:0] E_NONE = 8'd0, E_ADDRESS = 8'd1,
        E_ACCESS = 8'd2, E_MASK = 8'd3, E_VALUE = 8'd4,
        E_STATE = 8'd5, E_LOAD_RANGE = 8'd6, E_LOAD_SEQUENCE = 8'd7,
        E_LOAD_INCOMPLETE = 8'd8, E_OUTPUT_EMPTY = 8'd9,
        E_OUTPUT_ORDER = 8'd10, E_WRITEBACK = 8'd11;

    logic soft_reset;
    wire engine_rst_n = rst_n && !soft_reset;
    logic engine_load_valid, engine_load_ready, engine_start_valid, engine_start_ready;
    logic engine_busy, engine_done, engine_error, engine_y_valid, engine_y_ready;
    logic signed [47:0] engine_y_data;
    logic [14:0] engine_y_index;
    logic engine_y_last;
    logic [31:0] engine_cycles;
    logic [1:0] load_kind;
    logic [13:0] load_addr;
    logic [31:0] load_lo;
    logic [7:0] load_hi;
    logic kind_valid, addr_valid, lo_valid, hi_valid;
    logic [12:0] x_count;
    logic [14:0] w_count;
    logic [8:0] b_count;
    logic y_latched;
    logic [47:0] y_snapshot;
    logic [14:0] y_snapshot_index;
    logic y_snapshot_last;
    logic [14:0] output_count;
    logic task_started, core_done_sticky, software_done, protocol_error;
    logic [7:0] last_error;
    logic window_active;
    logic [31:0] window_cycles;
    logic rsp_pop_y, rsp_writeback;

    wire cmd_fire = icb_cmd_valid && icb_cmd_ready;
    wire rsp_fire = icb_rsp_valid && icb_rsp_ready;
    wire [11:0] offset = icb_cmd_addr[11:0];
    wire load_phase = !engine_busy && (!task_started || software_done);
    wire adapter_start_ready = engine_start_ready && (!task_started || software_done);
    wire [31:0] status_word = {21'b0, window_active, task_started,
        protocol_error, engine_error, software_done, core_done_sticky,
        y_latched, engine_y_valid, adapter_start_ready,
        (engine_load_ready && load_phase), engine_busy};
    logic request_ok;
    logic [7:0] request_error;
    logic [31:0] read_data;
    logic is_staging_write;

    assign icb_cmd_ready = rst_n && !soft_reset && !icb_rsp_valid;
    assign engine_load_valid = cmd_fire && request_ok && !icb_cmd_read &&
        offset == R_LOAD_COMMIT;
    assign engine_start_valid = cmd_fire && request_ok && !icb_cmd_read &&
        offset == R_CONTROL && icb_cmd_wdata == 32'd1;
    assign engine_y_ready = rst_n && rsp_fire && !icb_rsp_err && rsp_pop_y;

    kwt_linear_engine_rowpair #(.PIPE_MUL(1), .RESULT_BUFFERS(2)) u_engine (
        .clk(clk), .rst_n(engine_rst_n),
        .load_valid(engine_load_valid), .load_ready(engine_load_ready),
        .load_kind(load_kind), .load_addr(load_addr), .load_data({load_hi, load_lo}),
        .start_valid(engine_start_valid), .start_ready(engine_start_ready),
        .busy(engine_busy), .done(engine_done), .error(engine_error),
        .out_valid(engine_y_valid), .out_ready(engine_y_ready),
        .out_data(engine_y_data), .out_index(engine_y_index), .out_last(engine_y_last),
        .core_cycles(engine_cycles)
    );

    // All rejected commands are free of engine and staging side effects.
    // Read masks are ignored by ICB; writes require a full aligned CPU word.
    always_comb begin
        request_ok = 1'b1;
        request_error = E_NONE;
        read_data = 32'b0;
        is_staging_write = 1'b0;
        if (icb_cmd_addr[31:12] != BASE_ADDR[31:12] || icb_cmd_addr[1:0] != 2'b0) begin
            request_ok = 1'b0;
            request_error = E_ADDRESS;
        end else if (!icb_cmd_read && icb_cmd_wmask != 4'hf) begin
            request_ok = 1'b0;
            request_error = E_MASK;
        end else if (icb_cmd_read) begin
            case (offset)
                R_ID: read_data = 32'h4b57_5431;
                R_STATUS: read_data = status_word;
                R_ERROR: read_data = {15'b0, engine_error, 8'b0, last_error};
                R_CORE_CYCLES: read_data = engine_cycles;
                R_OUTPUT_COUNT: read_data = {17'b0, output_count};
                R_WINDOW_CYCLES: read_data = window_cycles;
                R_LOAD_KIND: read_data = {30'b0, load_kind};
                R_LOAD_ADDR: read_data = {18'b0, load_addr};
                R_LOAD_LO: read_data = load_lo;
                R_LOAD_HI: read_data = {24'b0, load_hi};
                R_Y_LO: begin
                    if (y_latched) read_data = y_snapshot[31:0];
                    else if (engine_y_valid) read_data = engine_y_data[31:0];
                    else begin request_ok = 1'b0; request_error = E_OUTPUT_EMPTY; end
                end
                R_Y_HI: begin
                    if (y_latched && engine_y_valid) read_data = {16'b0, y_snapshot[47:32]};
                    else begin request_ok = 1'b0; request_error = E_OUTPUT_ORDER; end
                end
                R_Y_INDEX: begin
                    if (y_latched) read_data = {y_snapshot_last, 16'b0, y_snapshot_index};
                    else if (engine_y_valid) read_data = {engine_y_last, 16'b0, engine_y_index};
                end
                default: begin request_ok = 1'b0; request_error = E_ACCESS; end
            endcase
        end else begin
            case (offset)
                R_CONTROL: begin
                    case (icb_cmd_wdata)
                        32'd1: if (!adapter_start_ready) begin
                            request_ok = 1'b0; request_error = E_STATE;
                        end
                        32'd2: if (!task_started || software_done || engine_busy ||
                            !(core_done_sticky || engine_done) ||
                            output_count != 15'd25344 || y_latched) begin
                            request_ok = 1'b0; request_error = E_WRITEBACK;
                        end
                        32'd4: begin end // Abort and clear engine/adapter validity.
                        default: begin request_ok = 1'b0; request_error = E_VALUE; end
                    endcase
                end
                R_LOAD_KIND, R_LOAD_ADDR, R_LOAD_LO, R_LOAD_HI: begin
                    is_staging_write = 1'b1;
                    if (!load_phase || !engine_load_ready) begin
                        request_ok = 1'b0; request_error = E_STATE;
                    end else if (offset == R_LOAD_KIND && icb_cmd_wdata > 32'd2) begin
                        request_ok = 1'b0; request_error = E_VALUE;
                    end else if (offset == R_LOAD_ADDR && icb_cmd_wdata > 32'd16383) begin
                        request_ok = 1'b0; request_error = E_LOAD_RANGE;
                    end else if (offset == R_LOAD_HI && icb_cmd_wdata[31:8] != 24'd0) begin
                        request_ok = 1'b0; request_error = E_VALUE;
                    end
                end
                R_LOAD_COMMIT: begin
                    if (icb_cmd_wdata != 32'd1) begin
                        request_ok = 1'b0; request_error = E_VALUE;
                    end else if (!load_phase || !engine_load_ready) begin
                        request_ok = 1'b0; request_error = E_STATE;
                    end else if (!kind_valid || !addr_valid || !lo_valid ||
                        (load_kind == 2'd2 && !hi_valid)) begin
                        request_ok = 1'b0; request_error = E_LOAD_INCOMPLETE;
                    end else if (load_kind != 2'd2 && load_lo[31:16] != 16'd0) begin
                        request_ok = 1'b0; request_error = E_VALUE;
                    end else begin
                        case (load_kind)
                            2'd0: begin
                                if (load_addr >= 14'd6336) begin
                                    request_ok = 1'b0; request_error = E_LOAD_RANGE;
                                end else if (load_addr != {1'b0, x_count}) begin
                                    request_ok = 1'b0; request_error = E_LOAD_SEQUENCE;
                                end
                            end
                            2'd1: begin
                                if (w_count >= 15'd16384) begin
                                    request_ok = 1'b0; request_error = E_LOAD_RANGE;
                                end else if ({1'b0, load_addr} != w_count) begin
                                    request_ok = 1'b0; request_error = E_LOAD_SEQUENCE;
                                end
                            end
                            2'd2: begin
                                if (load_addr >= 14'd256) begin
                                    request_ok = 1'b0; request_error = E_LOAD_RANGE;
                                end else if (load_addr != {5'b0, b_count}) begin
                                    request_ok = 1'b0; request_error = E_LOAD_SEQUENCE;
                                end
                            end
                            default: begin request_ok = 1'b0; request_error = E_VALUE; end
                        endcase
                    end
                end
                default: begin request_ok = 1'b0; request_error = E_ACCESS; end
            endcase
        end
        if (!request_ok) read_data = 32'b0;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            icb_rsp_valid <= 1'b0;
            icb_rsp_rdata <= '0;
            icb_rsp_err <= 1'b0;
            rsp_pop_y <= 1'b0;
            rsp_writeback <= 1'b0;
            soft_reset <= 1'b0;
            load_kind <= '0; load_addr <= '0; load_lo <= '0; load_hi <= '0;
            kind_valid <= 1'b0; addr_valid <= 1'b0; lo_valid <= 1'b0; hi_valid <= 1'b0;
            x_count <= '0; w_count <= '0; b_count <= '0;
            y_latched <= 1'b0; y_snapshot <= '0; y_snapshot_index <= '0; y_snapshot_last <= 1'b0;
            output_count <= '0;
            task_started <= 1'b0; core_done_sticky <= 1'b0; software_done <= 1'b0;
            protocol_error <= 1'b0; last_error <= E_NONE;
            window_active <= 1'b0; window_cycles <= '0;
        end else begin
            soft_reset <= 1'b0;
            if (engine_done) core_done_sticky <= 1'b1;
            if (window_active && window_cycles != 32'hffff_ffff)
                window_cycles <= window_cycles + 1'b1;
            if (rsp_fire) begin
                icb_rsp_valid <= 1'b0;
                rsp_pop_y <= 1'b0;
                rsp_writeback <= 1'b0;
                if (!icb_rsp_err && rsp_pop_y) begin
                    y_latched <= 1'b0;
                    output_count <= output_count + 1'b1;
                    if (y_snapshot_last) begin
                        x_count <= '0; w_count <= '0; b_count <= '0;
                    end
                end
                if (!icb_rsp_err && rsp_writeback) begin
                    software_done <= 1'b1;
                    window_active <= 1'b0;
                end
            end
            if (cmd_fire) begin
                icb_rsp_valid <= 1'b1;
                icb_rsp_rdata <= read_data;
                icb_rsp_err <= !request_ok;
                rsp_pop_y <= 1'b0;
                rsp_writeback <= 1'b0;
                if (!request_ok) begin
                    protocol_error <= 1'b1;
                    last_error <= request_error;
                end else if (icb_cmd_read) begin
                    if (offset == R_Y_LO && !y_latched) begin
                        y_snapshot <= engine_y_data;
                        y_snapshot_index <= engine_y_index;
                        y_snapshot_last <= engine_y_last;
                        y_latched <= 1'b1;
                    end
                    if (offset == R_Y_HI) rsp_pop_y <= 1'b1;
                end else begin
                    if (is_staging_write) begin
                        if (!window_active) begin
                            window_active <= 1'b1;
                            window_cycles <= '0;
                        end
                        if (software_done) begin
                            task_started <= 1'b0;
                            software_done <= 1'b0;
                            core_done_sticky <= 1'b0;
                            output_count <= '0;
                        end
                    end
                    case (offset)
                        R_LOAD_KIND: begin load_kind <= icb_cmd_wdata[1:0]; kind_valid <= 1'b1; end
                        R_LOAD_ADDR: begin load_addr <= icb_cmd_wdata[13:0]; addr_valid <= 1'b1; end
                        R_LOAD_LO: begin load_lo <= icb_cmd_wdata; lo_valid <= 1'b1; end
                        R_LOAD_HI: begin load_hi <= icb_cmd_wdata[7:0]; hi_valid <= 1'b1; end
                        R_LOAD_COMMIT: begin
                            lo_valid <= 1'b0; hi_valid <= 1'b0;
                            // W's final 16383->0 wrap is harmless: its count is full,
                            // and a new KIND/ADDR must be set for the next tensor.
                            load_addr <= load_addr + 1'b1;
                            case (load_kind)
                                2'd0: x_count <= x_count + 1'b1;
                                2'd1: w_count <= w_count + 1'b1;
                                2'd2: b_count <= b_count + 1'b1;
                                default: begin end
                            endcase
                        end
                        R_CONTROL: begin
                            case (icb_cmd_wdata)
                                32'd1: begin
                                    task_started <= 1'b1;
                                    software_done <= 1'b0;
                                    core_done_sticky <= 1'b0;
                                    output_count <= '0;
                                    kind_valid <= 1'b0; addr_valid <= 1'b0;
                                    lo_valid <= 1'b0; hi_valid <= 1'b0;
                                end
                                32'd2: rsp_writeback <= 1'b1;
                                32'd4: begin
                                    soft_reset <= 1'b1;
                                    load_kind <= '0; load_addr <= '0; load_lo <= '0; load_hi <= '0;
                                    kind_valid <= 1'b0; addr_valid <= 1'b0;
                                    lo_valid <= 1'b0; hi_valid <= 1'b0;
                                    x_count <= '0; w_count <= '0; b_count <= '0;
                                    y_latched <= 1'b0;
                                    output_count <= '0;
                                    task_started <= 1'b0; core_done_sticky <= 1'b0; software_done <= 1'b0;
                                    protocol_error <= 1'b0; last_error <= E_NONE;
                                    window_active <= 1'b0; window_cycles <= '0;
                                end
                                default: begin end
                            endcase
                        end
                        default: begin end
                    endcase
                end
            end
        end
    end
endmodule
