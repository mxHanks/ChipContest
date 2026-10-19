// Passive prototype, not a member of the frozen C4 candidate manifest.
// The input lifetime counters must be direct aliases in this common core clock
// domain: jobs += 1 on QK start; words += WORDS_PER_TRANSFER on normal PV out_fire.
// Their register-observation delays must match. capture must be quiescent and
// shared with the existing held-data capture edge; old outputs are sampled then.
// No output may feed admission, ready, arithmetic, or canonical commit control.
module cats_r4_core_service_from_counters #(
    parameter integer CLUSTERS = 4,
    parameter integer ROWS_PER_CLUSTER = 1024,
    parameter integer WORDS_PER_ROW = 128,
    parameter integer WORDS_PER_TRANSFER = 32,
    parameter integer COUNTER_BITS = 64
) (
    input wire clk, rst_n, capture,
    input wire [CLUSTERS-1:0][63:0] job_count, context_words,
    input wire [CLUSTERS-1:0][15:0] core_epoch,
    output wire [63:0] elapsed_cycles,
    output wire [15:0] epoch,
    output wire running, finished, fault, overflow, valid
);
    localparam integer REM_BITS = (WORDS_PER_ROW < 2) ? 1 : $clog2(WORDS_PER_ROW);
    logic [CLUSTERS-1:0][63:0] previous_jobs, previous_words;
    logic [CLUSTERS-1:0][REM_BITS-1:0] remainder, next_remainder;
    logic [CLUSTERS-1:0] job_pulse, row_pulse, child_started;
    logic in_epoch, counter_fault, next_counter_fault, begin_epoch;
    wire observer_fault, observer_valid;
    wire [CLUSTERS-1:0][15:0] job_epoch = core_epoch;
    wire [CLUSTERS-1:0][15:0] row_epoch = core_epoch;

    assign fault = observer_fault || counter_fault;
    assign valid = observer_valid && !counter_fault;

    initial begin
        if (WORDS_PER_ROW < 1 || WORDS_PER_TRANSFER < 1 ||
            WORDS_PER_TRANSFER > WORDS_PER_ROW || WORDS_PER_ROW % WORDS_PER_TRANSFER != 0)
            $fatal(1, "Invalid core service counter geometry");
    end

    always_comb begin
        job_pulse = '0;
        for (integer c=0; c<CLUSTERS; c=c+1)
            job_pulse[c] = job_count[c] > previous_jobs[c];
        begin_epoch = !in_epoch && !fault && (|job_pulse);
        row_pulse = '0;
        next_remainder = remainder;
        next_counter_fault = counter_fault;
        for (integer c=0; c<CLUSTERS; c=c+1) begin
            if (job_pulse[c] && job_count[c] - previous_jobs[c] != 64'd1)
                next_counter_fault = 1'b1;
            if (in_epoch && job_count[c] < previous_jobs[c])
                next_counter_fault = 1'b1;
            if (begin_epoch) begin
                next_remainder[c] = '0;
                // There cannot be accepted PV output at the first QK start.
                // Refuse an ambiguous baseline rather than dropping that delta.
                if (context_words[c] != previous_words[c])
                    next_counter_fault = 1'b1;
            end else if (in_epoch) begin
                if (context_words[c] < previous_words[c])
                    next_counter_fault = 1'b1;
                else if (context_words[c] > previous_words[c]) begin
                    if (finished || core_epoch[c] != epoch ||
                        !(child_started[c] || job_pulse[c]) ||
                        context_words[c] - previous_words[c] != WORDS_PER_TRANSFER)
                        next_counter_fault = 1'b1;
                    else if (remainder[c] + WORDS_PER_TRANSFER >= WORDS_PER_ROW) begin
                        row_pulse[c] = 1'b1;
                        next_remainder[c] = '0;
                    end else
                        next_remainder[c] = remainder[c] + WORDS_PER_TRANSFER;
                end
            end else if (context_words[c] > previous_words[c])
                next_counter_fault = 1'b1;
            // Idle counter decreases may be a legitimate producer clear.
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            previous_jobs <= '0;
            previous_words <= '0;
            remainder <= '0;
            child_started <= '0;
            in_epoch <= 1'b0;
            counter_fault <= 1'b0;
        end else begin
            previous_jobs <= job_count;
            previous_words <= context_words;
            if (capture) begin
                remainder <= '0;
                child_started <= '0;
                in_epoch <= 1'b0;
                counter_fault <= 1'b0;
            end else begin
                remainder <= next_remainder;
                counter_fault <= next_counter_fault;
                if (begin_epoch) begin
                    in_epoch <= 1'b1;
                    child_started <= job_pulse;
                end else if (in_epoch)
                    child_started <= child_started | job_pulse;
            end
        end
    end

    cats_r4_core_service_observer #(
        .CLUSTERS(CLUSTERS), .ROWS_PER_CLUSTER(ROWS_PER_CLUSTER), .COUNTER_BITS(COUNTER_BITS)
    ) u_observer (
        .clk, .rst_n, .capture, .job_start(job_pulse), .row_release(row_pulse),
        .job_epoch, .row_epoch, .elapsed_cycles, .epoch, .running, .finished,
        .fault(observer_fault), .overflow, .valid(observer_valid)
    );
endmodule
