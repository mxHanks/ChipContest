`timescale 1ns/1ps
// Reduced from the accepted mapped y_snapshot connectivity. The DFFR behavior
// matches the Yosys Liberty-derived Nangate functional model; no gate delay.
module kwt_alias_dffr(input D, CK, RN, output Q);
  reg state_bit;
  always @(posedge CK or negedge RN)
    if (!RN) state_bit <= 1'b0;
    else state_bit <= D;
  assign Q = state_bit;
endmodule

module kwt_mapped_alias(input clk, rst_n, enable,
                        input [40:0] data, output [47:0] result);
  wire [47:0] y_snapshot
`ifdef KWT_ALIAS_SPLIT
    /* verilator split_var */
`endif
    ;
  for (genvar i=0; i<41; i=i+1) begin: g_bit
    wire next_bit = enable ? data[i] : y_snapshot[i];
    kwt_alias_dffr storage(.D(next_bit),.CK(clk),.RN(rst_n),.Q(y_snapshot[i]));
  end
  assign y_snapshot[47:41] = {7{y_snapshot[40]}};
  assign result = y_snapshot;
endmodule

module tb_kwt_mapped_alias;
  reg clk=0, rst_n=1, enable=0;
  reg [40:0] data=0;
  wire [47:0] result;
  reg [40:0] expected=0;
  integer checks=0,positive_loads=0,negative_loads=0,holds=0,resets=0;
  kwt_mapped_alias dut(.clk(clk),.rst_n(rst_n),.enable(enable),.data(data),.result(result));

  task automatic check_result;
    reg [47:0] sign_extended;
    begin
      sign_extended={{7{expected[40]}},expected};
      if (result !== sign_extended)
        $fatal(1,"alias result mismatch: actual=%h expected=%h",result,sign_extended);
      checks=checks+1;
    end
  endtask

  task automatic cycle(input bit load,input [40:0] payload);
    begin
      clk=0;enable=load;data=payload;
      #2;
      check_result(); // Input activity does not change the stored output.
      clk=1;
      if (load) begin
        expected=payload;
        if(payload[40])negative_loads=negative_loads+1;
        else positive_loads=positive_loads+1;
      end else holds=holds+1;
      #2;check_result();clk=0;#2;check_result();
    end
  endtask

  task automatic assert_reset;
    begin
      clk=0;rst_n=1;#1;rst_n=0;expected=0;resets=resets+1;
      #1;check_result(); // Asynchronous reset works without a clock edge.
      clk=1;#1;check_result();clk=0;#1;
      rst_n=1;#1;check_result();
    end
  endtask

  initial begin
    assert_reset();
    cycle(1,41'h00000000000);
    cycle(1,41'h00000000001);
    cycle(0,41'h1ffffffffff);
    cycle(1,41'h0ffffffffff); // Largest positive signed41.
    cycle(0,41'h10000000000);
    cycle(1,41'h1ffffffffff); // -1.
    cycle(0,41'h00000000000);
    cycle(1,41'h10000000000); // Smallest negative signed41.
    cycle(0,41'h0ffffffffff);
    cycle(1,41'h15555555555);
    cycle(0,41'h0aaaaaaaaaa);
    assert_reset();
    cycle(0,41'h1ffffffffff);
    cycle(1,41'h05555555555);
    cycle(0,41'h1aaaaaaaaaa);
    if(positive_loads!=4 || negative_loads!=3 || holds!=7 || resets!=2 || checks!=48)
      $fatal(1,"alias fixture coverage counters differ");
    $display("KWT_MAPPED_ALIAS_PASS checks=%0d positive_loads=%0d negative_loads=%0d holds=%0d resets=%0d",
      checks,positive_loads,negative_loads,holds,resets);
    $finish;
  end
endmodule
