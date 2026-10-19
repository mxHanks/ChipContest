`timescale 1ns/1ps

// Simulation-only binary32 reference. Integer significands with guard/round/
// sticky bits implement round-to-nearest-even, including subnormals. This is
// not a timing model or a substitute for Xilinx FP IP/XSim signoff.
package cats_r4_mock_fp32;
    function automatic [63:0] shift_jam(input reg [63:0] x, input integer n);
        begin
            if (n <= 0) shift_jam = x;
            else if (n >= 64) shift_jam = {63'd0, |x};
            else shift_jam = (x >> n) | ((x << (64-n)) != 0);
        end
    endfunction

    // Pack unsigned integer m * 2**power, rounded once to binary32.
    function automatic [31:0] pack_rne(
        input reg sign_bit, input reg [63:0] m, input integer power);
        integer top_bit, exponent, shift, i;
        reg [63:0] q, remainder_bits, half_ulp;
        reg [7:0] biased;
        begin
            top_bit = -1;
            for (i=0; i<64; i=i+1) if (m[i]) top_bit = i;
            if (top_bit < 0) pack_rne = {sign_bit,31'd0};
            else begin
                exponent = top_bit + power;
                shift = (exponent < -126) ? (-149-power) : (top_bit-23);
                q = m;
                if (shift > 0 && shift < 64) begin
                    q = m >> shift;
                    half_ulp = 64'd1 << (shift-1);
                    remainder_bits = m & ((64'd1 << shift)-1);
                    if (remainder_bits > half_ulp ||
                        (remainder_bits == half_ulp && q[0])) q = q+1;
                end else if (shift >= 64) begin
                    q = (shift == 64 && m > 64'h8000000000000000) ? 1 : 0;
                end else if (shift < 0) q = m << (-shift);
                if (exponent < -126) begin
                    // q==2**23 rounds a subnormal up to minimum normal.
                    pack_rne = {sign_bit,7'd0,q[23:0]};
                end else begin
                    if (q[24]) begin q = q >> 1; exponent = exponent+1; end
                    biased = exponent+127;
                    if (exponent > 127) pack_rne = {sign_bit,8'hff,23'd0};
                    else pack_rne = {sign_bit,biased,q[22:0]};
                end
            end
        end
    endfunction

    function automatic [31:0] multiply(input reg [31:0] a, b);
        reg [63:0] ma, mb;
        integer ea, eb;
        reg sign_bit;
        begin
            sign_bit = a[31]^b[31];
            ma = {a[30:23]!=0,a[22:0]};
            mb = {b[30:23]!=0,b[22:0]};
            ea = (a[30:23]==0) ? -126 : integer'(a[30:23])-127;
            eb = (b[30:23]==0) ? -126 : integer'(b[30:23])-127;
            if ((a[30:23]==255 && a[22:0]!=0) ||
                (b[30:23]==255 && b[22:0]!=0) ||
                (a[30:23]==255 && b[30:0]==0) ||
                (b[30:23]==255 && a[30:0]==0)) multiply = 32'h7fc00000;
            else if (a[30:23]==255 || b[30:23]==255)
                multiply = {sign_bit,8'hff,23'd0};
            else multiply = pack_rne(sign_bit,ma*mb,ea+eb-46);
        end
    endfunction

    function automatic [31:0] add(input reg [31:0] a, b);
        reg [63:0] ma, mb, result_m;
        integer ea, eb, emax;
        reg sign_bit;
        begin
            ma = {a[30:23]!=0,a[22:0]};
            mb = {b[30:23]!=0,b[22:0]};
            ea = (a[30:23]==0) ? -126 : integer'(a[30:23])-127;
            eb = (b[30:23]==0) ? -126 : integer'(b[30:23])-127;
            emax = (ea > eb) ? ea : eb;
            ma = shift_jam(ma << 3,emax-ea);
            mb = shift_jam(mb << 3,emax-eb);
            if (a[31] == b[31]) begin
                result_m = ma+mb; sign_bit = a[31];
            end else if (ma >= mb) begin
                result_m = ma-mb; sign_bit = a[31];
            end else begin
                result_m = mb-ma; sign_bit = b[31];
            end
            if ((a[30:23]==255 && a[22:0]!=0) ||
                (b[30:23]==255 && b[22:0]!=0) ||
                (a[30:23]==255 && b[30:23]==255 && a[31]!=b[31]))
                add = 32'h7fc00000;
            else if (a[30:23]==255) add = a;
            else if (b[30:23]==255) add = b;
            else if (result_m == 0)
                add = {(a[31] & b[31]),31'd0};
            else add = pack_rne(sign_bit,result_m,emax-26);
        end
    endfunction
endpackage

module fp32_mul_ip #(parameter IP_ID = 0) (
    input logic clk, input logic rst_n,
    input logic a_valid, output logic a_ready, input logic [31:0] a_data,
    input logic b_valid, output logic b_ready, input logic [31:0] b_data,
    output logic result_valid, input logic result_ready,
    output logic [31:0] result_data
);
    assign a_ready = !result_valid || result_ready;
    assign b_ready = a_ready;
    always_ff @(posedge clk) begin
        if (!rst_n) begin result_valid <= 0; result_data <= 0; end
        else begin
            if (result_valid && result_ready) result_valid <= 0;
            if (a_valid && b_valid && a_ready && b_ready) begin
                result_valid <= 1;
                result_data <= cats_r4_mock_fp32::multiply(a_data,b_data);
            end
        end
    end
endmodule

module fp32_add_ip (
    input logic clk, input logic rst_n,
    input logic a_valid, output logic a_ready, input logic [31:0] a_data,
    input logic b_valid, output logic b_ready, input logic [31:0] b_data,
    output logic result_valid, input logic result_ready,
    output logic [31:0] result_data
);
    assign a_ready = !result_valid || result_ready;
    assign b_ready = a_ready;
    always_ff @(posedge clk) begin
        if (!rst_n) begin result_valid <= 0; result_data <= 0; end
        else begin
            if (result_valid && result_ready) result_valid <= 0;
            if (a_valid && b_valid && a_ready && b_ready) begin
                result_valid <= 1;
                result_data <= cats_r4_mock_fp32::add(a_data,b_data);
            end
        end
    end
endmodule
