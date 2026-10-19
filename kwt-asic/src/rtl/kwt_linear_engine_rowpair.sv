`timescale 1ns/1ps

// Two-row, eight-column KWT-1 FFN1 engine. Sixteen exact 16x16 MACs share
// eight W reads; odd final row disables the second row's datapath entirely.
// The external fixed16_acc48_v1 contract and task-fresh loading are unchanged.
// Internal sums/results use 41 bits: |bias + partial sum| <= 2^39+2^36 < 2^40.
// Explicit logical banks await mapping to the designated physical SRAM macros.
module kwt_linear_engine_rowpair #(
    parameter int PIPE_MUL = 1,
    parameter int RESULT_BUFFERS = 2
) (
    input  logic               clk,
    input  logic               rst_n,
    input  logic               load_valid,
    output logic               load_ready,
    input  logic [1:0]         load_kind,
    input  logic [13:0]        load_addr,
    input  logic [39:0]        load_data,
    input  logic               start_valid,
    output logic               start_ready,
    output logic               busy,
    output logic               done,
    output logic               error,
    output logic               out_valid,
    input  logic               out_ready,
    output logic signed [47:0] out_data,
    output logic [14:0]        out_index,
    output logic               out_last,
    output logic [31:0]        core_cycles
);
    localparam int ACTIVE_BUFFERS = RESULT_BUFFERS == 2 ? 2 : 1;
    generate
        if (PIPE_MUL != 0 && PIPE_MUL != 1) begin : g_invalid_pipe
            KWT_INVALID_PIPE_MUL_must_be_zero_or_one invalid_configuration();
        end
        if (RESULT_BUFFERS != 1 && RESULT_BUFFERS != 2) begin : g_invalid_buffers
            KWT_INVALID_RESULT_BUFFERS_must_be_one_or_two invalid_configuration();
        end
    endgenerate

    typedef enum logic [2:0] {C_IDLE, C_RUN, C_DRAIN, C_STORE, C_FLUSH, C_WAIT, C_DONE} compute_state_t;
    compute_state_t compute_state;
    logic active;
    logic [12:0] x_loaded;
    logic [14:0] w_loaded;
    logic [8:0] b_loaded;
    logic load_legal, load_fire, start_fire;
    logic [5:0] pair_index;
    logic [4:0] block_index;
    logic [5:0] k_issue;
    logic compute_buffer, output_buffer;
    logic [ACTIVE_BUFFERS-1:0] result_full;
    logic compute_active, compute_wait_buffer;
    logic x0_rd_en, x1_rd_en, w_rd_en, b_rd_en;
    logic row1_active, row1_mac_en;
    logic read_valid, read_first, read_last;
    logic accumulate_valid, accumulate_first, accumulate_last;
    logic signed [15:0] x_read [0:1];
    logic signed [15:0] w_read [0:7];
    logic signed [39:0] b_read [0:7];
    logic signed [31:0] product [0:1][0:7];
    logic signed [31:0] accumulate_product [0:1][0:7];
    logic signed [40:0] acc [0:1][0:7];

    // A 16-word snapshot drains serially while the next tile computes. This
    // avoids padding 16 shallow banks to the minimum physical SRAM depth.
    logic result_capture_en, result_wr_en, result_rd_en;
    logic signed [40:0] result_snapshot [0:1][0:7];
    logic signed [40:0] result_read [0:ACTIVE_BUFFERS-1];
    logic writer_active, writer_buffer, writer_two_rows, writer_final_block;
    logic [3:0] writer_index;
    logic [4:0] writer_block;
    logic writer_last;
    logic [5:0] output_pair_index;
    logic [8:0] read_index;
    logic read_all_issued;
    logic rd_pending, rd_buffer;
    logic [14:0] rd_index;
    logic signed [40:0] rd_data;
    logic signed [40:0] q0_data, q1_data;
    logic [14:0] q0_index, q1_index;
    logic [1:0] q_count;
    logic [2:0] queue_after_edge;
    logic out_fire, buffer_release, pair_complete;

    assign busy = active;
    assign load_ready = rst_n && !active && !error && !start_valid;
    assign start_ready = rst_n && !active && !error &&
        (x_loaded == 13'd6336) && (w_loaded == 15'd16384) && (b_loaded == 9'd256);
    assign load_fire = load_valid && load_ready;
    assign start_fire = start_valid && start_ready;
    always_comb begin
        load_legal = 1'b0;
        case (load_kind)
            2'd0: load_legal = (load_addr < 14'd6336) && (load_addr == {1'b0,x_loaded});
            2'd1: load_legal = ({1'b0,load_addr} == w_loaded) && (w_loaded < 15'd16384);
            2'd2: load_legal = (load_addr < 14'd256) && (load_addr == {5'b0,b_loaded});
            default: load_legal = 1'b0;
        endcase
    end

    assign compute_active = active && ((compute_state == C_RUN) ||
        (compute_state == C_DRAIN) || (compute_state == C_STORE) || (compute_state == C_FLUSH));
    assign compute_wait_buffer = active && (compute_state == C_WAIT) && result_full[compute_buffer];
    assign row1_active = (pair_index != 6'd49);
    assign x0_rd_en = active && (compute_state == C_RUN);
    assign x1_rd_en = x0_rd_en && row1_active;
    assign w_rd_en = x0_rd_en;
    assign b_rd_en = w_rd_en && (k_issue == 6'd0);
    assign row1_mac_en = accumulate_valid && row1_active;
    assign result_capture_en = active && (compute_state == C_STORE);
    assign result_wr_en = active && writer_active;
    assign writer_last = writer_index == (writer_two_rows ? 4'd15 : 4'd7);
    assign pair_complete = result_wr_en && writer_last && writer_final_block;

    assign out_valid = rst_n && active && (q_count != 2'd0);
    assign out_data = $signed({{7{q0_data[40]}},q0_data});
    assign out_index = q0_index;
    assign out_last = out_valid && (q0_index == 15'd25343);
    assign out_fire = out_valid && out_ready;
    assign buffer_release = out_fire && ((q0_index[8:0] == 9'd511) || out_last);
    // Credit includes both resident queue words and the outstanding RAM read.
    // Pop at this edge frees a slot immediately, enabling one word/cycle.
    assign queue_after_edge = {1'b0,q_count} + {2'b0,rd_pending} - {2'b0,out_fire};
    assign result_rd_en = active && result_full[output_buffer] && !read_all_issued &&
        (queue_after_edge < 3'd2);
    assign rd_data = result_read[rd_buffer];

    // X row parity is a physical bank; the final odd bank has only 49 rows.
    for (genvar row = 0; row < 2; row = row + 1) begin : g_x_row
        localparam int X_WORDS = row == 0 ? 3200 : 3136;
        logic signed [15:0] x_mem [0:X_WORDS-1];
        always_ff @(posedge clk) begin
            if (load_fire && load_legal && load_kind == 2'd0 && load_addr[6] == 1'(row))
                x_mem[{load_addr[12:7],load_addr[5:0]}] <= $signed(load_data[15:0]);
            if ((row == 0 && x0_rd_en) || (row == 1 && x1_rd_en))
                x_read[row] <= x_mem[{pair_index,k_issue}];
        end
    end

    generate
        if (PIPE_MUL == 1) begin : g_pipe_metadata
            always_ff @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    accumulate_valid <= 1'b0;
                    accumulate_first <= 1'b0;
                    accumulate_last <= 1'b0;
                end else begin
                    accumulate_valid <= read_valid;
                    if (read_valid) begin
                        accumulate_first <= read_first;
                        accumulate_last <= read_last;
                    end
                end
            end
        end else begin : g_comb_metadata
            assign accumulate_valid = read_valid;
            assign accumulate_first = read_first;
            assign accumulate_last = read_last;
        end
    endgenerate

    for (genvar lane = 0; lane < 8; lane = lane + 1) begin : g_lane
        logic signed [15:0] w_mem [0:2047];
        logic signed [39:0] b_mem [0:31];
        always_ff @(posedge clk) begin
            if (load_fire && load_legal && load_addr[2:0] == 3'(lane)) begin
                if (load_kind == 2'd1) w_mem[load_addr[13:3]] <= $signed(load_data[15:0]);
                if (load_kind == 2'd2) b_mem[load_addr[7:3]] <= $signed(load_data);
            end
            if (w_rd_en) w_read[lane] <= w_mem[{k_issue,block_index}];
            if (b_rd_en) b_read[lane] <= b_mem[block_index];
        end
        for (genvar row = 0; row < 2; row = row + 1) begin : g_row
            // Gate multiplier input as well as register enables on row 98's
            // absent partner; no stale odd-row values participate in a MAC.
            wire signed [15:0] multiply_x = (row == 0 || row1_active) ? x_read[row] : 16'sd0;
            assign product[row][lane] = multiply_x * w_read[lane];
            if (PIPE_MUL == 1) begin : g_pipe_product
                always_ff @(posedge clk) begin
                    if (read_valid && (row == 0 || row1_active))
                        accumulate_product[row][lane] <= product[row][lane];
                end
            end else begin : g_comb_product
                assign accumulate_product[row][lane] = product[row][lane];
            end
            always_ff @(posedge clk) begin
                if (result_capture_en && (row == 0 || row1_active))
                    result_snapshot[row][lane] <= acc[row][lane];
                if (accumulate_valid && (row == 0 || row1_active)) begin
                    if (accumulate_first)
                        acc[row][lane] <= $signed({b_read[lane][39],b_read[lane]}) +
                            $signed({{9{accumulate_product[row][lane][31]}},accumulate_product[row][lane]});
                    else
                        acc[row][lane] <= acc[row][lane] +
                            $signed({{9{accumulate_product[row][lane][31]}},accumulate_product[row][lane]});
                end
            end
        end
    end

    for (genvar buf_id = 0; buf_id < ACTIVE_BUFFERS; buf_id = buf_id + 1) begin : g_result_buffer
        logic signed [40:0] result_mem [0:511];
        always_ff @(posedge clk) begin
            if (result_wr_en && writer_buffer == 1'(buf_id))
                result_mem[{writer_index[3],writer_block,writer_index[2:0]}] <=
                    result_snapshot[writer_index[3]][writer_index[2:0]];
            if (result_rd_en && output_buffer == 1'(buf_id))
                result_read[buf_id] <= result_mem[read_index];
        end
    end

    // The response tags and queue payload are reset-free, just like SRAM.
    // Reset clears their validity/occupancy instead of resetting stored data.
    always_ff @(posedge clk) begin
        if (result_rd_en) begin
            rd_buffer <= output_buffer;
            rd_index <= {output_pair_index,read_index};
        end
        case ({out_fire,rd_pending})
            2'b01: begin
                if (q_count == 2'd0) begin q0_data <= rd_data; q0_index <= rd_index; end
                else begin q1_data <= rd_data; q1_index <= rd_index; end
            end
            2'b10: begin q0_data <= q1_data; q0_index <= q1_index; end
            2'b11: begin
                if (q_count == 2'd1) begin q0_data <= rd_data; q0_index <= rd_index; end
                else begin
                    q0_data <= q1_data; q0_index <= q1_index;
                    q1_data <= rd_data; q1_index <= rd_index;
                end
            end
            default: begin end
        endcase
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active <= 1'b0;
            compute_state <= C_IDLE;
            x_loaded <= '0; w_loaded <= '0; b_loaded <= '0;
            pair_index <= '0; block_index <= '0; k_issue <= '0;
            compute_buffer <= 1'b0; output_buffer <= 1'b0;
            result_full <= '0;
            output_pair_index <= '0; read_index <= '0; read_all_issued <= 1'b0;
            rd_pending <= 1'b0; q_count <= '0;
            writer_active <= 1'b0; writer_index <= '0; writer_block <= '0;
            writer_buffer <= 1'b0; writer_two_rows <= 1'b0; writer_final_block <= 1'b0;
            read_valid <= 1'b0; read_first <= 1'b0; read_last <= 1'b0;
            done <= 1'b0; error <= 1'b0; core_cycles <= '0;
        end else begin
            done <= 1'b0;
            read_valid <= 1'b0;
            rd_pending <= result_rd_en;
            q_count <= queue_after_edge[1:0];
            if (active && core_cycles != 32'hffffffff) core_cycles <= core_cycles + 1'b1;
            if (result_wr_en) begin
                if (writer_last) writer_active <= 1'b0;
                else writer_index <= writer_index + 1'b1;
            end
            if (result_capture_en) begin
                writer_active <= 1'b1;
                writer_index <= '0;
                writer_block <= block_index;
                writer_buffer <= compute_buffer;
                writer_two_rows <= row1_active;
                writer_final_block <= (block_index == 5'd31);
            end
            if (load_fire) begin
                if (!load_legal) error <= 1'b1;
                else case (load_kind)
                    2'd0: x_loaded <= x_loaded + 1'b1;
                    2'd1: w_loaded <= w_loaded + 1'b1;
                    2'd2: b_loaded <= b_loaded + 1'b1;
                    default: error <= 1'b1;
                endcase
            end
            if (result_rd_en) begin
                if (read_index == 9'd511 || (output_pair_index == 6'd49 && read_index == 9'd255))
                    read_all_issued <= 1'b1;
                else read_index <= read_index + 1'b1;
            end
            if (buffer_release) begin
                result_full[output_buffer] <= 1'b0;
                output_buffer <= RESULT_BUFFERS == 2 ? !output_buffer : 1'b0;
                output_pair_index <= output_pair_index + 1'b1;
                read_index <= '0;
                read_all_issued <= 1'b0;
            end
            if (pair_complete) result_full[compute_buffer] <= 1'b1;
            if (start_fire) begin
                active <= 1'b1;
                compute_state <= C_RUN;
                pair_index <= '0; block_index <= '0; k_issue <= '0;
                compute_buffer <= 1'b0; output_buffer <= 1'b0;
                result_full <= '0;
                output_pair_index <= '0; read_index <= '0; read_all_issued <= 1'b0;
                rd_pending <= 1'b0; q_count <= '0;
                writer_active <= 1'b0;
                core_cycles <= '0;
            end else case (compute_state)
                C_IDLE: begin end
                C_RUN: begin
                    read_valid <= 1'b1;
                    read_first <= (k_issue == 6'd0);
                    read_last <= (k_issue == 6'd63);
                    if (k_issue == 6'd63) compute_state <= C_DRAIN;
                    else k_issue <= k_issue + 1'b1;
                end
                C_DRAIN: if (accumulate_valid && accumulate_last) compute_state <= C_STORE;
                C_STORE: begin
                    k_issue <= '0;
                    if (block_index == 5'd31) begin
                        block_index <= '0;
                        compute_state <= C_FLUSH;
                    end else begin
                        block_index <= block_index + 1'b1;
                        compute_state <= C_RUN;
                    end
                end
                C_FLUSH: if (pair_complete) begin
                    if (pair_index == 6'd49) compute_state <= C_DONE;
                    else begin
                        pair_index <= pair_index + 1'b1;
                        compute_buffer <= RESULT_BUFFERS == 2 ? !compute_buffer : 1'b0;
                        compute_state <= C_WAIT;
                    end
                end
                C_WAIT: if (!result_full[compute_buffer]) compute_state <= C_RUN;
                C_DONE: begin end
                default: begin compute_state <= C_IDLE; error <= 1'b1; end
            endcase
            // Completion is the final external acceptance, never mere MAC or
            // result-RAM completion. No parameter/input survives as fresh data.
            if (out_fire && out_last) begin
                active <= 1'b0;
                compute_state <= C_IDLE;
                done <= 1'b1;
                x_loaded <= '0; w_loaded <= '0; b_loaded <= '0;
            end
        end
    end
endmodule
