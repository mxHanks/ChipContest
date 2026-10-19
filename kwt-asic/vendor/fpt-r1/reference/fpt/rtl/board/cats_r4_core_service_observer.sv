// Passive core-domain elapsed-service meter; not connected to the frozen C4 candidate.
// Pulses must be real accepted handshakes in clk's domain. row_release excludes
// error releases. capture is the quiescent held-data snapshot capture edge;
// the snapshot samples the old outputs while this observer re-arms via NBA.
// No output may feed arithmetic, admission, ready, or canonical commit control.
module cats_r4_core_service_observer #(
    parameter integer CLUSTERS = 4,
    parameter integer ROWS_PER_CLUSTER = 1024,
    parameter integer COUNTER_BITS = 64
) (
    input wire clk, rst_n, capture,
    input wire [CLUSTERS-1:0] job_start, row_release,
    input wire [CLUSTERS-1:0][15:0] job_epoch, row_epoch,
    output wire [63:0] elapsed_cycles,
    output logic [15:0] epoch,
    output logic running, finished, fault, overflow,
    output wire valid
);
    localparam integer ROW_BITS = (ROWS_PER_CLUSTER < 2) ? 1 : $clog2(ROWS_PER_CLUSTER+1);
    logic [COUNTER_BITS-1:0] elapsed;
    logic [CLUSTERS-1:0][ROW_BITS-1:0] rows, next_rows;
    logic starting, seed_seen, next_fault, all_complete;
    logic [15:0] seed_epoch, compare_epoch;
    assign elapsed_cycles = elapsed;
    assign valid = finished && !fault && !overflow;

    initial begin
        if (CLUSTERS < 1 || ROWS_PER_CLUSTER < 1 || COUNTER_BITS < 1 || COUNTER_BITS > 64)
            $fatal(1, "Invalid core service observer geometry");
    end

    always_comb begin
        seed_seen = 1'b0;
        seed_epoch = '0;
        for (integer c=0; c<CLUSTERS; c=c+1) begin
            if (job_start[c] && !seed_seen) begin
                seed_epoch = job_epoch[c];
                seed_seen = 1'b1;
            end
        end
        starting = !running && !finished && !fault && seed_seen;
        compare_epoch = starting ? seed_epoch : epoch;
        next_rows = rows;
        next_fault = fault;
        all_complete = 1'b1;
        for (integer c=0; c<CLUSTERS; c=c+1) begin
            if (job_start[c] &&
                (!(running || starting) || job_epoch[c] != compare_epoch))
                next_fault = 1'b1;
            if (row_release[c]) begin
                if (!(running || starting) || row_epoch[c] != compare_epoch ||
                    rows[c] >= ROWS_PER_CLUSTER)
                    next_fault = 1'b1;
                else
                    next_rows[c] = rows[c] + 1'b1;
            end
            if (next_rows[c] != ROWS_PER_CLUSTER)
                all_complete = 1'b0;
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            elapsed <= '0;
            epoch <= '0;
            rows <= '0;
            running <= 1'b0;
            finished <= 1'b0;
            fault <= 1'b0;
            overflow <= 1'b0;
        end else if (capture) begin
            elapsed <= '0;
            epoch <= '0;
            rows <= '0;
            running <= 1'b0;
            finished <= 1'b0;
            fault <= 1'b0;
            overflow <= 1'b0;
        end else begin
            rows <= next_rows;
            fault <= next_fault;
            if (starting) begin
                epoch <= seed_epoch;
                elapsed <= '0;
                running <= !all_complete;
                finished <= all_complete;
            end else if (running) begin
                if (&elapsed)
                    overflow <= 1'b1;
                else
                    elapsed <= elapsed + 1'b1;
                if (all_complete) begin
                    running <= 1'b0;
                    finished <= 1'b1;
                end
            end
        end
    end
endmodule
