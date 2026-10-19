`timescale 1ns/1ps

// CATS-R4 IF_V2 local AXI beat-direct Q/K/V bank bridge candidate.
//
// This file is not yet a production wrapper: it remains behind the C2
// entry gate while its ownership, burst, and CDC behavior are audited against
// docs/CATS_R4_INTERFACE_COMMIT.md.
//
// This block is deliberately separate from cats_r4_qkv_banked_mem: the
// latter is the frozen core-clock ownership/service model, while this block
// is the AXI-clock fill endpoint and the independent-clock BRAM service.
// One accepted AXI beat always carries four BF16 values and is written in
// the same AXI cycle; there is no 64-to-16 serializer in this production
// path.  Ownership FIFOs are outside this block and must carry the done token
// across the AXI/core CDC boundary.
module cats_r4_qkv_axi_bank_bridge #(
    parameter int SEQ_LEN   = 128,
    parameter int HEAD_DIM  = 128,
    parameter int CONTEXTS  = 16
) (
    // AXI/DDR-side write stream (one 64-bit beat per cycle).
    input  logic         axi_clk,
    input  logic         axi_rst_n,
    input  logic         wr_valid,
    output logic         wr_ready,
    input  logic [1:0]   wr_kind,       // 0=Q, 1=K, 2=V
    input  logic         wr_buffer,
    input  logic [15:0]  wr_epoch,
    input  logic [2:0]   wr_group,
    input  logic [4:0]   wr_global_q_head,
    input  logic [2:0]   wr_row_window,
    input  logic [11:0]  wr_beat_index,
    input  logic [63:0]  wr_data,
    input  logic [7:0]   wr_strb,
    input  logic         wr_last,

    // Logical descriptor completion.  Held until ready.
    output logic         done_valid,
    input  logic         done_ready,
    output logic [1:0]   done_kind,
    output logic         done_buffer,
    output logic [15:0]  done_epoch,
    output logic [2:0]   done_group,
    output logic [4:0]   done_global_q_head,
    output logic [2:0]   done_row_window,

    // Core-side read services.  Responses are fixed two core-clock edges
    // after an accepted request and have no response backpressure.
    input  logic         core_clk,
    input  logic         core_rst_n,
    // KV group and Q slab have independent lifetimes (IF_V2).
    // All selectors/valids are core-domain ownership-controller outputs.
    input  logic         active_valid,       // KV active
    input  logic         active_buffer,      // KV half
    input  logic         q_active_valid,
    input  logic         q_active_buffer,

    input  logic         q_req_valid,
    output logic         q_req_ready,
    input  logic [3:0]   q_req_context_tag,
    input  logic [6:0]   q_req_d,
    output logic         q_rsp_valid,
    output logic [3:0]   q_rsp_context_tag,
    output logic [15:0]  q_rsp_bf16,

    input  logic         k_req_valid,
    output logic         k_req_ready,
    input  logic [3:0]   k_req_context_tag,
    input  logic [1:0]   k_req_key_block,
    input  logic [6:0]   k_req_d,
    output logic         k_rsp_valid,
    output logic [3:0]   k_rsp_context_tag,
    output logic [511:0] k_rsp_vec,

    input  logic         v_req_valid,
    output logic         v_req_ready,
    input  logic [3:0]   v_req_context_tag,
    input  logic [6:0]   v_req_key,
    input  logic [1:0]   v_req_feature_block,
    output logic         v_rsp_valid,
    output logic [3:0]   v_rsp_context_tag,
    output logic [511:0] v_rsp_vec,

    // Accepted-beat and protocol counters are AXI-clocked.
    output logic [63:0]  q_beats_accepted,
    output logic [63:0]  k_beats_accepted,
    output logic [63:0]  v_beats_accepted,
    output logic [63:0]  protocol_errors,
    output logic         protocol_error_sticky
);
    localparam int Q_BANKS  = 4;
    localparam int KV_BANKS = 32;
    localparam int Q_AW     = 10; // 2 buffers x 512 BF16 words/bank
    localparam int KV_AW_A  = 8; // 2 buffers x 128 64-bit words/key bank
    localparam int KV_AW_B  = 10; // 2 buffers x 512 16-bit words/bank

    logic desc_active;
    logic [1:0]  desc_kind;
    logic        desc_buffer;
    logic [15:0] desc_epoch;
    logic [2:0]  desc_group;
    logic [4:0]  desc_head;
    logic [2:0]  desc_window;
    logic [11:0] desc_next_index;

    logic token_match;
    logic [11:0] expected_last;
    logic wr_accept;

    assign expected_last = (wr_kind == 2'd0) ? 12'd511 : 12'd4095;
    assign token_match = !desc_active ||
                         ((wr_kind == desc_kind) &&
                          (wr_buffer == desc_buffer) &&
                          (wr_epoch == desc_epoch) &&
                          (wr_group == desc_group) &&
                          (wr_global_q_head == desc_head) &&
                          (wr_row_window == desc_window) &&
                          (wr_beat_index == desc_next_index));
    // A completion must be drained before accepting another descriptor.  A
    // malformed descriptor makes the endpoint sticky-stopped until reset.
    assign wr_ready = axi_rst_n && !done_valid && !protocol_error_sticky && token_match;
    assign wr_accept = wr_valid && wr_ready;

    // XPM bank ports.  Q and V use one 16-bit write per physical bank;
    // K uses the asymmetric 64-bit-write/16-bit-read primitive, preserving
    // one AXI beat/cycle while exposing BF16 reads to the core.
    logic [15:0] q_dina [0:Q_BANKS-1];
    logic [1:0]  q_wea  [0:Q_BANKS-1];
    logic [Q_AW-1:0] q_addra [0:Q_BANKS-1];
    logic [15:0] q_doutb [0:Q_BANKS-1];

    logic [63:0] k_dina [0:KV_BANKS-1];
    logic [7:0]  k_wea  [0:KV_BANKS-1];
    logic [KV_AW_A-1:0] k_addra [0:KV_BANKS-1];
    logic [15:0] k_doutb [0:KV_BANKS-1];

    logic [15:0] v_dina [0:KV_BANKS-1];
    logic [1:0]  v_wea  [0:KV_BANKS-1];
    logic [KV_AW_B-1:0] v_addra [0:KV_BANKS-1];
    logic [15:0] v_doutb [0:KV_BANKS-1];

    logic [Q_AW-1:0] q_addrb;
    logic [KV_AW_B-1:0] k_addrb, v_addrb;
    logic q_enb [0:Q_BANKS-1];
    logic k_enb [0:KV_BANKS-1];
    logic v_enb [0:KV_BANKS-1];

    integer init_i, en_i, rsp_i;
`ifndef CATS_R4_PROTOCOL_ONLY
    // The buffer selector is an address bit, not a second set of RAMs.
    // Port A fills the inactive buffer while port B reads the active buffer.
    // External ownership logic must prevent reads of a buffer being filled.
    always_comb begin
        for (init_i = 0; init_i < Q_BANKS; init_i = init_i + 1) begin
            q_dina[init_i] = wr_data[init_i*16 +: 16];
            q_wea[init_i] = 2'b00;
            q_addra[init_i] = {wr_buffer,wr_beat_index[8:0]};
        end
        for (init_i = 0; init_i < KV_BANKS; init_i = init_i + 1) begin
            k_dina[init_i] = wr_data;
            k_wea[init_i] = 8'h00;
            k_addra[init_i] = {wr_buffer,wr_beat_index[11:10],wr_beat_index[4:0]};
            v_dina[init_i] = '0;
            v_wea[init_i] = 2'b00;
            v_addra[init_i] = {wr_buffer,wr_beat_index[4:3],wr_beat_index[11:5]};
        end
        if (wr_accept) begin
            if (wr_kind == 2'd0) begin
                for (init_i = 0; init_i < Q_BANKS; init_i = init_i + 1)
                    q_wea[init_i] = wr_strb[init_i*2 +: 2];
            end else if (wr_kind == 2'd1) begin
                k_wea[wr_beat_index[9:5]] = wr_strb;
            end else if (wr_kind == 2'd2) begin
                for (init_i = 0; init_i < 4; init_i = init_i + 1) begin
                    // d_base=(beat[4:0]<<2); four adjacent feature banks.
                    v_wea[{wr_beat_index[2:0], 2'b00} + 5'(init_i)]
                        = wr_strb[init_i*2 +: 2];
                    v_dina[{wr_beat_index[2:0], 2'b00} + 5'(init_i)]
                        = wr_data[init_i*16 +: 16];
                end
            end
        end
    end
`endif

`ifndef CATS_R4_PROTOCOL_ONLY
    genvar gi;
    generate
            for (gi = 0; gi < Q_BANKS; gi = gi + 1) begin : G_QBANK
                xpm_memory_sdpram #(
                    .ADDR_WIDTH_A(Q_AW), .ADDR_WIDTH_B(Q_AW),
                    .AUTO_SLEEP_TIME(0), .BYTE_WRITE_WIDTH_A(8),
                    .CLOCKING_MODE("independent_clock"),
                    .ECC_MODE("no_ecc"), .MEMORY_PRIMITIVE("block"),
                    .MEMORY_SIZE(16384), .READ_DATA_WIDTH_B(16),
                    .READ_LATENCY_B(2), .WRITE_DATA_WIDTH_A(16),
                    .WRITE_MODE_B("read_first")
                ) u_q (
                    .clka(axi_clk), .ena(wr_accept && wr_kind == 2'd0),
                    .wea(q_wea[gi]), .addra(q_addra[gi]),
                    .dina(q_dina[gi]), .injectsbiterra(1'b0),
                    .injectdbiterra(1'b0), .sleep(1'b0),
                    .clkb(core_clk), .enb(q_enb[gi]),
                    .addrb(q_addrb), .doutb(q_doutb[gi]),
                    .regceb(1'b1), .rstb(!core_rst_n),
                    .sbiterrb(), .dbiterrb()
                );
            end
            for (gi = 0; gi < KV_BANKS; gi = gi + 1) begin : G_KBANK
                xpm_memory_sdpram #(
                    .ADDR_WIDTH_A(KV_AW_A), .ADDR_WIDTH_B(KV_AW_B),
                    .AUTO_SLEEP_TIME(0), .BYTE_WRITE_WIDTH_A(8),
                    .CLOCKING_MODE("independent_clock"),
                    .ECC_MODE("no_ecc"), .MEMORY_PRIMITIVE("block"),
                    .MEMORY_SIZE(16384), .READ_DATA_WIDTH_B(16),
                    .READ_LATENCY_B(2), .WRITE_DATA_WIDTH_A(64),
                    .WRITE_MODE_B("read_first")
                ) u_k (
                    .clka(axi_clk), .ena(wr_accept && wr_kind == 2'd1),
                    .wea(k_wea[gi]), .addra(k_addra[gi]),
                    .dina(k_dina[gi]), .injectsbiterra(1'b0),
                    .injectdbiterra(1'b0), .sleep(1'b0),
                    .clkb(core_clk), .enb(k_enb[gi]),
                    .addrb(k_addrb), .doutb(k_doutb[gi]),
                    .regceb(1'b1), .rstb(!core_rst_n),
                    .sbiterrb(), .dbiterrb()
                );
                xpm_memory_sdpram #(
                    .ADDR_WIDTH_A(KV_AW_B), .ADDR_WIDTH_B(KV_AW_B),
                    .AUTO_SLEEP_TIME(0), .BYTE_WRITE_WIDTH_A(8),
                    .CLOCKING_MODE("independent_clock"),
                    .ECC_MODE("no_ecc"), .MEMORY_PRIMITIVE("block"),
                    .MEMORY_SIZE(16384), .READ_DATA_WIDTH_B(16),
                    .READ_LATENCY_B(2), .WRITE_DATA_WIDTH_A(16),
                    .WRITE_MODE_B("read_first")
                ) u_v (
                    .clka(axi_clk), .ena(wr_accept && wr_kind == 2'd2),
                    .wea(v_wea[gi]), .addra(v_addra[gi]),
                    .dina(v_dina[gi]), .injectsbiterra(1'b0),
                    .injectdbiterra(1'b0), .sleep(1'b0),
                    .clkb(core_clk), .enb(v_enb[gi]),
                    .addrb(v_addrb), .doutb(v_doutb[gi]),
                    .regceb(1'b1), .rstb(!core_rst_n),
                    .sbiterrb(), .dbiterrb()
                );
            end
    endgenerate
`endif

    assign q_req_ready = core_rst_n && q_active_valid;
    assign k_req_ready = core_rst_n && active_valid;
    assign v_req_ready = core_rst_n && active_valid;
    assign q_addrb = {q_active_buffer,q_req_context_tag,q_req_d[6:2]};
    // Retiming: move the K/V fabric output register to the RAM request side.
    // Keep XPM READ_LATENCY_B=2 and the external N+2 response contract.
    // Capture buffer ownership together with the accepted logical address.
    logic k_read_en, v_read_en;
    always_ff @(posedge core_clk) begin
        if (!core_rst_n) begin
            k_read_en <= 1'b0;
            v_read_en <= 1'b0;
        end else begin
            k_read_en <= k_req_valid && k_req_ready;
            v_read_en <= v_req_valid && v_req_ready;
        end
        if (k_req_valid && k_req_ready)
            k_addrb <= {active_buffer,k_req_key_block,k_req_d};
        if (v_req_valid && v_req_ready)
            v_addrb <= {active_buffer,v_req_feature_block,v_req_key};
    end

`ifndef CATS_R4_PROTOCOL_ONLY
    always_comb begin
        for (en_i = 0; en_i < Q_BANKS; en_i = en_i + 1)
            q_enb[en_i] = q_req_valid && q_req_ready && (q_req_d[1:0] == en_i[1:0]);
        for (en_i = 0; en_i < KV_BANKS; en_i = en_i + 1) begin
            k_enb[en_i] = k_read_en;
            v_enb[en_i] = v_read_en;
        end
    end

    for (genvar read_lane=0; read_lane<KV_BANKS; read_lane=read_lane+1) begin : G_KV_READ_DATA
        assign k_rsp_vec[read_lane*16 +: 16] = k_doutb[read_lane];
        assign v_rsp_vec[read_lane*16 +: 16] = v_doutb[read_lane];
    end

    // Q: XPM latency 2 plus fabric output register. K/V: registered request
    // plus XPM latency 2, with no additional fabric data output register.
    // Latency 1 corrupts back-to-back reads: the data advances ahead of tags.
    logic q_p0, q_p1, k_p0, k_p1, v_p0, v_p1;
    logic [3:0] q_t0, q_t1, k_t0, k_t1, v_t0, v_t1;
    logic [1:0] q_bank0, q_bank1;

    always_ff @(posedge core_clk) begin
        if (!core_rst_n) begin
            q_p0 <= 1'b0; q_p1 <= 1'b0; q_rsp_valid <= 1'b0;
            k_p0 <= 1'b0; k_p1 <= 1'b0; k_rsp_valid <= 1'b0;
            v_p0 <= 1'b0; v_p1 <= 1'b0; v_rsp_valid <= 1'b0;
            q_t0 <= '0; q_t1 <= '0; k_t0 <= '0; k_t1 <= '0;
            v_t0 <= '0; v_t1 <= '0; q_bank0 <= '0; q_bank1 <= '0;
            q_rsp_context_tag <= '0;
            q_rsp_bf16 <= '0; k_rsp_context_tag <= '0; v_rsp_context_tag <= '0;
        end else begin
            q_p0 <= q_req_valid && q_req_ready; q_p1 <= q_p0;
            q_rsp_valid <= q_p1; q_t1 <= q_t0; q_t0 <= q_req_context_tag;
            q_bank1 <= q_bank0; q_bank0 <= q_req_d[1:0];
            q_rsp_context_tag <= q_t1;
            q_rsp_bf16 <= q_doutb[q_bank1];

            k_p0 <= k_req_valid && k_req_ready; k_p1 <= k_p0;
            k_rsp_valid <= k_p1; k_t1 <= k_t0; k_t0 <= k_req_context_tag;
            k_rsp_context_tag <= k_t1;


            v_p0 <= v_req_valid && v_req_ready; v_p1 <= v_p0;
            v_rsp_valid <= v_p1; v_t1 <= v_t0; v_t0 <= v_req_context_tag;
            v_rsp_context_tag <= v_t1;

        end
    end

`endif
    always_ff @(posedge axi_clk) begin
        if (!axi_rst_n) begin
            desc_active <= 1'b0; desc_kind <= '0; desc_buffer <= 1'b0;
            desc_epoch <= '0; desc_group <= '0; desc_head <= '0;
            desc_window <= '0; desc_next_index <= '0;
            done_valid <= 1'b0; done_kind <= '0; done_buffer <= 1'b0;
            done_epoch <= '0; done_group <= '0; done_global_q_head <= '0;
            done_row_window <= '0; q_beats_accepted <= '0;
            k_beats_accepted <= '0; v_beats_accepted <= '0;
            protocol_errors <= '0; protocol_error_sticky <= 1'b0;
        end else begin
            if (done_valid && done_ready) done_valid <= 1'b0;
            if (wr_valid && !wr_ready && !done_valid && !protocol_error_sticky) begin
                protocol_errors <= protocol_errors + 1'b1;
                protocol_error_sticky <= 1'b1;
            end
            if (wr_accept) begin
                if (!desc_active) begin
                    desc_active <= 1'b1; desc_kind <= wr_kind; desc_buffer <= wr_buffer;
                    desc_epoch <= wr_epoch; desc_group <= wr_group; desc_head <= wr_global_q_head;
                    desc_window <= wr_row_window; desc_next_index <= 12'd1;
                    if (wr_beat_index != 12'd0) begin
                        protocol_errors <= protocol_errors + 1'b1;
                        protocol_error_sticky <= 1'b1;
                    end
                end else begin
                    desc_next_index <= desc_next_index + 1'b1;
                end
                case (wr_kind)
                    2'd0: q_beats_accepted <= q_beats_accepted + 1'b1;
                    2'd1: k_beats_accepted <= k_beats_accepted + 1'b1;
                    2'd2: v_beats_accepted <= v_beats_accepted + 1'b1;
                    default: begin
                        protocol_errors <= protocol_errors + 1'b1;
                        protocol_error_sticky <= 1'b1;
                    end
                endcase
                if (wr_last) begin
                    if (wr_beat_index != expected_last) begin
                        protocol_errors <= protocol_errors + 1'b1;
                        protocol_error_sticky <= 1'b1;
                    end else begin
                        desc_active <= 1'b0;
                        done_valid <= 1'b1; done_kind <= wr_kind; done_buffer <= wr_buffer;
                        done_epoch <= wr_epoch; done_group <= wr_group;
                        done_global_q_head <= wr_global_q_head;
                        done_row_window <= wr_row_window;
                    end
                end else if (wr_beat_index == expected_last) begin
                    protocol_errors <= protocol_errors + 1'b1;
                    protocol_error_sticky <= 1'b1;
                end
            end
        end
    end

    initial begin
        if ((SEQ_LEN != 128) || (HEAD_DIM != 128) || (CONTEXTS != 16))
            $error("cats_r4_qkv_axi_bank_bridge: requires S=D=128,R=16");
    end
endmodule
