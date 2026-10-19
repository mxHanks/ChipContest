`timescale 1ns/1ps
// Drivers use negedge; sample actual handshakes before NBA at posedge.
// Separate four-state tests prove that two equal unknowns are rejected.
module kwt_icb_pair_checker (
  input wire clk,rst_n,cmd_valid,rsp_ready,
  input wire ready0,ready1,rsp0,rsp1,error0,error1,
  input wire [31:0] data0,data1,
  output integer trace_checks=0,
  output integer accepted_commands=0,
  output integer accepted_responses=0
);
  always @(posedge clk) begin
    if(rst_n !== 1'b0 && rst_n !== 1'b1) $fatal(1,"MAPPED_CHECKER_UNKNOWN_RESET");
    if(rst_n === 1'b1) begin
      if((^{cmd_valid,rsp_ready,ready0,ready1,rsp0,rsp1}) === 1'bx)
        $fatal(1,"MAPPED_CHECKER_UNKNOWN_CONTROL");
      if(ready0 !== ready1 || rsp0 !== rsp1) $fatal(1,"MAPPED_CHECKER_PROTOCOL_MISMATCH");
      if(rsp0 === 1'b1) begin
        if((^{error0,error1,data0,data1}) === 1'bx) $fatal(1,"MAPPED_CHECKER_UNKNOWN_RESPONSE");
        if(error0 !== error1 || data0 !== data1) $fatal(1,"MAPPED_CHECKER_RESPONSE_MISMATCH");
      end
      trace_checks=trace_checks+1;
      if(cmd_valid && ready0) accepted_commands=accepted_commands+1;
      if(rsp0 && rsp_ready) accepted_responses=accepted_responses+1;
    end
  end
endmodule
