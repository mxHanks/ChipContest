`timescale 1ns/1ps

// QK multi-context multiply/add pipeline; candidate pending integration.
module cats_r4_qk_32lane_fp32_service #(
    parameter int CONTEXTS = 16,
    parameter int LANES    = 32,
    parameter int HEAD_DIM = 128
) (
    input  logic clk,
    input  logic rst_n,
    input  logic clear,

    input  logic req_valid,
    output logic req_ready,
    input  logic [15:0] req_epoch,
    input  logic [2:0] req_group,
    input  logic [4:0] req_global_q_head,
    input  logic [6:0] req_row,
    input  logic [1:0] req_key_block,
    input  logic [3:0] req_context_tag,
    input  logic [6:0] req_d,
    input  logic [LANES-1:0] req_lane_valid,
    input  logic req_first,
    input  logic req_last,
    input  logic [15:0] req_q_bf16,
    input  logic [LANES*16-1:0] req_k_vec,

    output logic rsp_valid,
    input logic rsp_ready,
    output logic [15:0] rsp_epoch,
    output logic [2:0] rsp_group,
    output logic [4:0] rsp_global_q_head,
    output logic [6:0] rsp_row,
    output logic [1:0] rsp_key_block,
    output logic [3:0] rsp_context_tag,
    output logic [6:0] rsp_d,
    output logic rsp_score_valid,
    output logic [LANES-1:0] rsp_lane_valid,
    output logic [LANES*32-1:0] rsp_score_fp32,

    output logic [63:0] requests_accepted,
    output logic [63:0] mul_products_completed,
    output logic [63:0] add_results_completed,
    output logic [63:0] response_transfers,
    output logic [63:0] protocol_errors,
    output logic protocol_error_sticky
);
    // An outstanding request owns its context through response acceptance.
    // Different contexts may occupy the multiplier and adder concurrently.
    // Per-stage metadata includes lane masks: absent lanes never enter FP IP.
    localparam int DEPTH = 16;
    typedef struct packed {
        logic [15:0] epoch;
        logic [2:0] group_id;
        logic [4:0] head;
        logic [6:0] row_id;
        logic [1:0] key_block;
        logic [3:0] context_id;
        logic [6:0] d;
        logic [LANES-1:0] lanes;
        logic first, last;
    } token_t;
    localparam int TOKEN_W = $bits(token_t);
    (* ram_style = "distributed" *) logic [TOKEN_W-1:0] mul_meta [0:DEPTH-1];
    (* ram_style = "distributed" *) logic [TOKEN_W-1:0] add_meta [0:DEPTH-1];
    token_t request_token, mul_head, add_head, response_token, context_owner;
    logic [3:0] mul_wr, mul_rd, add_wr, add_rd;
    logic [4:0] mul_count, add_count;
    logic [CONTEXTS-1:0] context_busy, context_initialized;
    logic [6:0] context_last_d [0:CONTEXTS-1];
    logic [TOKEN_W-1:0] context_identity [0:CONTEXTS-1];
    (* ram_style = "distributed" *) logic [LANES*32-1:0] accum_mem [0:CONTEXTS-1];
    logic [LANES*32-1:0] committed_sum;
    logic [LANES-1:0] mul_a_ready, mul_b_ready, mul_valid, mul_ready;
    logic [LANES-1:0] add_a_ready, add_b_ready, add_valid, add_ready;
    logic [LANES*32-1:0] mul_data, add_data;
    logic arithmetic_rst_n, request_legal, request_fire, input_fire;
    logic mul_to_add_fire, add_commit_fire, output_room;
    logic [3:0] safe_context;

    function automatic [6:0] count_lanes(input logic [LANES-1:0] lanes);
        integer i;
        begin
            count_lanes = 0;
            for (i=0; i<LANES; i=i+1) count_lanes = count_lanes + lanes[i];
        end
    endfunction

    assign arithmetic_rst_n = rst_n && !clear;
    assign safe_context = req_context_tag < CONTEXTS ? req_context_tag : 4'd0;
    assign context_owner = context_identity[safe_context];
    assign request_token = {req_epoch,req_group,req_global_q_head,req_row,
        req_key_block,req_context_tag,req_d,req_lane_valid,req_first,req_last};
    assign mul_head = mul_meta[mul_rd];
    assign add_head = add_meta[add_rd];
    assign request_legal = req_context_tag < CONTEXTS && req_d < HEAD_DIM &&
        req_first == (req_d == 0) && req_last == (req_d == HEAD_DIM-1) &&
        (req_first || (context_initialized[safe_context] &&
            req_d == context_last_d[safe_context] + 1'b1 &&
            req_epoch == context_owner.epoch && req_group == context_owner.group_id &&
            req_global_q_head == context_owner.head && req_row == context_owner.row_id &&
            req_key_block == context_owner.key_block && req_lane_valid == context_owner.lanes));
    assign req_ready = arithmetic_rst_n && !protocol_error_sticky &&
        !context_busy[safe_context] && mul_count < DEPTH &&
        ((mul_a_ready & req_lane_valid) == req_lane_valid) &&
        ((mul_b_ready & req_lane_valid) == req_lane_valid);
    assign request_fire = req_valid && req_ready;
    assign input_fire = request_fire && request_legal;
    assign mul_to_add_fire = arithmetic_rst_n && mul_count != 0 && add_count < DEPTH &&
        ((mul_valid & mul_head.lanes) == mul_head.lanes) &&
        ((add_a_ready & mul_head.lanes) == mul_head.lanes) &&
        ((add_b_ready & mul_head.lanes) == mul_head.lanes);
    assign output_room = !rsp_valid || rsp_ready;
    assign add_commit_fire = arithmetic_rst_n && add_count != 0 && output_room &&
        ((add_valid & add_head.lanes) == add_head.lanes);

    assign rsp_epoch = response_token.epoch;
    assign rsp_group = response_token.group_id;
    assign rsp_global_q_head = response_token.head;
    assign rsp_row = response_token.row_id;
    assign rsp_key_block = response_token.key_block;
    assign rsp_context_tag = response_token.context_id;
    assign rsp_d = response_token.d;
    assign rsp_score_valid = response_token.last;
    assign rsp_lane_valid = response_token.lanes;

    for (genvar lane=0; lane<LANES; lane=lane+1) begin : GEN_FP_LANE
        fp32_mul_ip #(.IP_ID(0)) u_mul (
            .clk(clk), .rst_n(arithmetic_rst_n),
            .a_valid(input_fire && req_lane_valid[lane]), .a_ready(mul_a_ready[lane]),
            .a_data({req_q_bf16,16'd0}),
            .b_valid(input_fire && req_lane_valid[lane]), .b_ready(mul_b_ready[lane]),
            .b_data({req_k_vec[lane*16 +: 16],16'd0}),
            .result_valid(mul_valid[lane]), .result_ready(mul_ready[lane]),
            .result_data(mul_data[lane*32 +: 32]));
        fp32_add_ip u_add (
            .clk(clk), .rst_n(arithmetic_rst_n),
            .a_valid(mul_to_add_fire && mul_head.lanes[lane]), .a_ready(add_a_ready[lane]),
            .a_data(mul_head.first ? 32'd0 : accum_mem[mul_head.context_id][lane*32 +: 32]),
            .b_valid(mul_to_add_fire && mul_head.lanes[lane]), .b_ready(add_b_ready[lane]),
            .b_data(mul_data[lane*32 +: 32]),
            .result_valid(add_valid[lane]), .result_ready(add_ready[lane]),
            .result_data(add_data[lane*32 +: 32]));
        assign mul_ready[lane] = mul_to_add_fire && mul_head.lanes[lane];
        assign add_ready[lane] = add_commit_fire && add_head.lanes[lane];
        assign committed_sum[lane*32 +: 32] = add_head.lanes[lane] ?
            add_data[lane*32 +: 32] : 32'd0;
    end

    // Reset-free payload RAM; validity/owners are reset in the control block.
    always_ff @(posedge clk) begin
        if (arithmetic_rst_n) begin
            if (input_fire) begin
                mul_meta[mul_wr] <= request_token;
                if (req_first) context_identity[safe_context] <= request_token;
            end
            if (mul_to_add_fire) add_meta[add_wr] <= mul_head;
            if (add_commit_fire) begin
                accum_mem[add_head.context_id] <= committed_sum;
                context_last_d[add_head.context_id] <= add_head.d;
            end
        end
    end

    always_ff @(posedge clk) begin
        if (!rst_n || clear) begin
            mul_wr <= 0; mul_rd <= 0; mul_count <= 0;
            add_wr <= 0; add_rd <= 0; add_count <= 0;
            context_busy <= 0; context_initialized <= 0;
            rsp_valid <= 0; response_token <= '0; rsp_score_fp32 <= '0;
            requests_accepted <= 0; mul_products_completed <= 0;
            add_results_completed <= 0; response_transfers <= 0;
            protocol_errors <= 0; protocol_error_sticky <= 0;
        end else begin
            if (rsp_valid && rsp_ready) begin
                rsp_valid <= 0;
                context_busy[response_token.context_id] <= 0;
                response_transfers <= response_transfers + 1'b1;
            end
            if (request_fire) begin
                requests_accepted <= requests_accepted + 1'b1;
                if (!request_legal) begin
                    protocol_errors <= protocol_errors + 1'b1;
                    protocol_error_sticky <= 1;
                end
            end
            if (input_fire) begin
                mul_wr <= mul_wr + 1'b1;
                context_busy[safe_context] <= 1;
            end
            if (mul_to_add_fire) begin
                mul_rd <= mul_rd + 1'b1;
                add_wr <= add_wr + 1'b1;
                mul_products_completed <= mul_products_completed + count_lanes(mul_head.lanes);
            end
            if (add_commit_fire) begin
                add_rd <= add_rd + 1'b1;
                context_initialized[add_head.context_id] <= 1;
                rsp_valid <= 1;
                response_token <= add_head;
                rsp_score_fp32 <= committed_sum;
                add_results_completed <= add_results_completed + count_lanes(add_head.lanes);
            end
            case ({input_fire,mul_to_add_fire})
                2'b10: mul_count <= mul_count + 1'b1;
                2'b01: mul_count <= mul_count - 1'b1;
                default: ;
            endcase
            case ({mul_to_add_fire,add_commit_fire})
                2'b10: add_count <= add_count + 1'b1;
                2'b01: add_count <= add_count - 1'b1;
                default: ;
            endcase
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) if (rst_n && !clear) begin
        if (mul_count > DEPTH || add_count > DEPTH)
            $fatal(1,"QK metadata FIFO overflow");
        if (input_fire && context_busy[safe_context])
            $fatal(1,"QK context reused before response release");
        if (add_commit_fire && !context_busy[add_head.context_id])
            $fatal(1,"QK result has no context owner");
    end
`endif
    initial begin
        if (CONTEXTS != 16 || LANES != 32 || HEAD_DIM < 1 || HEAD_DIM > 128)
            $error("QK pipeline requires R=16, lanes=32, 1<=D<=128");
    end
endmodule
