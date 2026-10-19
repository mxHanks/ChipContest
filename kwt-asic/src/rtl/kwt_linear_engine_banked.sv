`timescale 1ns/1ps

// Pipelined KWT-1 first-feedforward engine: Y[99,256] = X[99,64] W[64,256] + B.
// Arithmetic contract: fixed16_acc48_v1. X/W signed 16, bias signed 40,
// exact signed 48-bit accumulation, no intermediate rounding or saturation.
//
// Bank-local storage candidate; official SRAM macro wrappers are still required.
// Optimization candidate derived from kwt_linear_engine (unchanged baseline).
// PIPE_MUL=1 separates the multiplier output and accumulator feedback paths;
// PIPE_MUL=0 retains the combinational multiplier-to-accumulator path.
// Bias is fetched once for each output group and held until its first MAC.
// Control ideas adapted from the FPT service/engine in vendor/fpt-r1:
// reset-free payload RAM, first/last tags following synchronous reads, and
// output ownership retained until a ready/valid transfer. No FPT arithmetic,
// causal, GQA, AMD IP, or external-memory logic is instantiated here.
module kwt_linear_engine_banked #(
    parameter int LANES = 8,
    parameter int PIPE_MUL = 1
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
    localparam int ROWS = 99;
    localparam int IN_DIM = 64;
    localparam int OUT_DIM = 256;
    // Keep illegal parameter values well formed until the elaboration check.
    localparam int ACTIVE_LANES = (LANES < 1 || LANES > OUT_DIM) ? 1 :
        ((OUT_DIM % LANES == 0) ? LANES : 1);
    localparam int BLOCKS = OUT_DIM / ACTIVE_LANES;
    localparam int BLOCK_BITS = (BLOCKS > 1) ? $clog2(BLOCKS) : 1;
    localparam int LANE_BITS = (ACTIVE_LANES > 1) ? $clog2(ACTIVE_LANES) : 1;
    localparam int W_BANK_WORDS = IN_DIM * BLOCKS;

    generate
        if (LANES != ACTIVE_LANES) begin : g_invalid_lanes
            // Deliberately undefined: reject invalid configurations during
            // elaboration in both simulation and synthesis, not only at t=0.
            KWT_INVALID_LANES_must_be_positive_divisor_of_256 invalid_configuration();
        end
        if (PIPE_MUL != 0 && PIPE_MUL != 1) begin : g_invalid_pipe_mul
            KWT_INVALID_PIPE_MUL_must_be_zero_or_one invalid_configuration();
        end
    endgenerate

    typedef enum logic [1:0] {IDLE, COMPUTE, DRAIN, EMIT} state_t;
    state_t state;
    logic [12:0] x_loaded;
    logic [14:0] w_loaded;
    logic [8:0] b_loaded;
    logic load_legal;
    logic load_fire;
    logic start_fire;
    logic [6:0] row_index;
    logic [BLOCK_BITS-1:0] block_index;
    logic [5:0] k_issue;
    logic [LANE_BITS-1:0] emit_lane;
    logic read_valid, read_first, read_last;
    logic accumulate_valid, accumulate_first, accumulate_last;
    // Named enables support activity accounting and later SRAM CE mapping.
    logic x_rd_en, w_rd_en, b_rd_en;

    // Address at the load port is always the original row-major word index.
    // W[k,c] maps to bank c % LANES, word k * BLOCKS + c / LANES.
    // B[c] maps to the same bank and word c / LANES. Each bank has one
    // synchronous read per cycle, and loading is excluded during compute.
    logic signed [15:0] x_mem [0:ROWS*IN_DIM-1];
    logic signed [15:0] x_read;
    logic signed [15:0] w_read [0:ACTIVE_LANES-1];
    logic signed [39:0] b_read [0:ACTIVE_LANES-1];
    logic signed [31:0] product [0:ACTIVE_LANES-1];
    logic signed [31:0] accumulate_product [0:ACTIVE_LANES-1];
    logic signed [47:0] acc [0:ACTIVE_LANES-1];

    assign x_rd_en = (state == COMPUTE);
    assign w_rd_en = (state == COMPUTE);
    assign b_rd_en = (state == COMPUTE) && (k_issue == 6'd0);
    assign busy = (state != IDLE);
    assign load_ready = rst_n && !busy && !error && !start_valid;
    assign start_ready = rst_n && !busy && !error &&
        (x_loaded == 13'd6336) && (w_loaded == 15'd16384) &&
        (b_loaded == 9'd256);
    assign load_fire = load_valid && load_ready;
    assign start_fire = start_valid && start_ready;

    always_comb begin
        load_legal = 1'b0;
        case (load_kind)
            2'd0: load_legal = (load_addr < 14'd6336) &&
                (load_addr == {1'b0, x_loaded});
            2'd1: load_legal = ({1'b0, load_addr} == w_loaded) &&
                (w_loaded < 15'd16384);
            2'd2: load_legal = (load_addr < 14'd256) &&
                (load_addr == {5'b0, b_loaded});
            default: load_legal = 1'b0;
        endcase
    end

    assign out_valid = rst_n && (state == EMIT);
    assign out_data = acc[emit_lane];
    assign out_index = {row_index, 8'b0} +
        15'(int'(block_index) * ACTIVE_LANES + int'(emit_lane));
    assign out_last = out_valid && (out_index == 15'd25343);

    // No reset or bulk clearing on any payload memory. Validity is established
    // only by receiving every word in a fresh task before permitting start.
    always_ff @(posedge clk) begin
        if (load_fire && load_legal && load_kind == 2'd0)
            x_mem[load_addr[12:0]] <= $signed(load_data[15:0]);
        if (x_rd_en)
            x_read <= x_mem[{row_index, k_issue}];
    end

    // Metadata crosses the same optional register boundary as the product.
    // Reset invalidates in-flight work; arithmetic payload registers need no reset.
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

    for (genvar lane = 0; lane < ACTIVE_LANES; lane = lane + 1) begin : g_lane
        // Distinct one-read/one-write logical banks; do not flatten lane into a memory address.
        logic signed [15:0] w_mem [0:W_BANK_WORDS-1];
        logic signed [39:0] b_mem [0:BLOCKS-1];
        assign product[lane] = x_read * w_read[lane];
        if (PIPE_MUL == 1) begin : g_pipe_product
            always_ff @(posedge clk) begin
                if (read_valid)
                    accumulate_product[lane] <= product[lane];
            end
        end else begin : g_comb_product
            assign accumulate_product[lane] = product[lane];
        end
        always_ff @(posedge clk) begin
            if (load_fire && load_legal) begin
                if (load_kind == 2'd1 && int'(load_addr) % ACTIVE_LANES == lane)
                    w_mem[int'(load_addr) / ACTIVE_LANES] <=
                        $signed(load_data[15:0]);
                if (load_kind == 2'd2 && int'(load_addr) % ACTIVE_LANES == lane)
                    b_mem[int'(load_addr) / ACTIVE_LANES] <=
                        $signed(load_data);
            end
            if (w_rd_en) begin
                w_read[lane] <= w_mem[int'(k_issue)*BLOCKS + int'(block_index)];
                // Only the first product uses bias. A synchronous first-issue
                // read is ready before either accumulation variant consumes it.
                if (b_rd_en)
                    b_read[lane] <= b_mem[block_index];
            end
            if (accumulate_valid) begin
                if (accumulate_first)
                    acc[lane] <= $signed({{8{b_read[lane][39]}}, b_read[lane]}) +
                        $signed({{16{accumulate_product[lane][31]}}, accumulate_product[lane]});
                else
                    acc[lane] <= acc[lane] +
                        $signed({{16{accumulate_product[lane][31]}}, accumulate_product[lane]});
            end
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            x_loaded <= '0;
            w_loaded <= '0;
            b_loaded <= '0;
            row_index <= '0;
            block_index <= '0;
            k_issue <= '0;
            emit_lane <= '0;
            read_valid <= 1'b0;
            read_first <= 1'b0;
            read_last <= 1'b0;
            done <= 1'b0;
            error <= 1'b0;
            core_cycles <= '0;
        end else begin
            done <= 1'b0;
            read_valid <= 1'b0;
            // Count elapsed cycles after start acceptance through final output
            // acceptance, including output stalls. Saturation prevents wrapping.
            if (busy && core_cycles != 32'hffffffff)
                core_cycles <= core_cycles + 1'b1;

            if (load_fire) begin
                if (!load_legal)
                    error <= 1'b1;
                else begin
                    case (load_kind)
                        2'd0: x_loaded <= x_loaded + 1'b1;
                        2'd1: w_loaded <= w_loaded + 1'b1;
                        2'd2: b_loaded <= b_loaded + 1'b1;
                        default: error <= 1'b1;
                    endcase
                end
            end

            case (state)
                IDLE: if (start_fire) begin
                    row_index <= '0;
                    block_index <= '0;
                    k_issue <= '0;
                    emit_lane <= '0;
                    core_cycles <= '0;
                    state <= COMPUTE;
                end
                COMPUTE: begin
                    read_valid <= 1'b1;
                    read_first <= (k_issue == 6'd0);
                    read_last <= (k_issue == 6'd63);
                    if (k_issue == 6'd63)
                        state <= DRAIN;
                    else
                        k_issue <= k_issue + 1'b1;
                end
                DRAIN: if (accumulate_valid && accumulate_last) begin
                    // The last product commits at this edge; the complete
                    // accumulator vector then owns the output until accepted.
                    emit_lane <= '0;
                    state <= EMIT;
                end
                EMIT: if (out_valid && out_ready) begin
                    if (int'(emit_lane) == ACTIVE_LANES-1) begin
                        emit_lane <= '0;
                        k_issue <= '0;
                        if (int'(block_index) == BLOCKS-1) begin
                            block_index <= '0;
                            if (row_index == 7'd98) begin
                                state <= IDLE;
                                done <= 1'b1;
                                x_loaded <= '0;
                                w_loaded <= '0;
                                b_loaded <= '0;
                            end else begin
                                row_index <= row_index + 1'b1;
                                state <= COMPUTE;
                            end
                        end else begin
                            block_index <= block_index + 1'b1;
                            state <= COMPUTE;
                        end
                    end else
                        emit_lane <= emit_lane + 1'b1;
                end
                default: begin
                    state <= IDLE;
                    error <= 1'b1;
                end
            endcase
        end
    end
endmodule
