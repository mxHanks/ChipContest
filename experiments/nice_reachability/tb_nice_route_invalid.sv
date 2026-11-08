`timescale 1ns/1ps
`include "e203_defines.v"
// Minimal actual-top regression: one unsupported request, no memory response.
module tb_nice_route_invalid;
  reg nice_clk=0; always #5 nice_clk=~nice_clk;
  reg nice_rst_n=0, nice_req_valid=0, nice_rsp_ready=1;
  reg [31:0] nice_req_inst=0, nice_req_rs1=32'ha0020000, nice_req_rs2=32'h20;
  wire nice_active,nice_mem_holdup,nice_req_ready,nice_rsp_valid,nice_rsp_err;
  wire [31:0] nice_rsp_rdat,nice_icb_cmd_addr,nice_icb_cmd_wdata;
  wire nice_icb_cmd_valid,nice_icb_cmd_read,nice_icb_rsp_ready;
  wire [1:0] nice_icb_cmd_size;
  wire nice_icb_cmd_ready=1, nice_icb_rsp_valid=0, nice_icb_rsp_err=0;
  wire [31:0] nice_icb_rsp_rdata=0;
  e203_subsys_nice_core dut(.*);
  // The same preserved old demo observes the same request independently.
  // This is classification evidence, never a replacement for the actual top.
  wire old_ready,old_response,old_error,old_command;
  e203_subsys_nice_demo old_demo (
    .nice_clk(nice_clk),.nice_rst_n(nice_rst_n),.nice_active(),.nice_mem_holdup(),
    .nice_req_valid(nice_req_valid),.nice_req_ready(old_ready),.nice_req_inst(nice_req_inst),
    .nice_req_rs1(nice_req_rs1),.nice_req_rs2(nice_req_rs2),
    .nice_rsp_valid(old_response),.nice_rsp_ready(1'b1),.nice_rsp_rdat(),.nice_rsp_err(old_error),
    .nice_icb_cmd_valid(old_command),.nice_icb_cmd_ready(1'b1),.nice_icb_cmd_addr(),
    .nice_icb_cmd_read(),.nice_icb_cmd_wdata(),.nice_icb_cmd_size(),
    .nice_icb_rsp_valid(1'b0),.nice_icb_rsp_ready(),.nice_icb_rsp_rdata(32'b0),.nice_icb_rsp_err(1'b0));
  integer selected=0,commands=0,elapsed=0,requests=0;
  always @(posedge nice_clk) if(nice_rst_n) begin
    if(nice_req_valid&&nice_req_ready) requests=requests+1;
    if(nice_icb_cmd_valid) commands=commands+1;
    if(old_command || nice_icb_cmd_valid)
      $fatal(1,"NICE_ROUTE_INVALID_MEMORY_ACCESS case=%0d",selected);
  end
  initial begin
    if(!$value$plusargs("CASE=%d",selected)) selected=0;
    case(selected)
      0: nice_req_inst=32'h0000707b; // unsupported custom3
      1: nice_req_inst=32'h4200707b; // one-bit drain funct7 near miss
      2: nice_req_inst=32'h4000607b; // drain funct3 near miss
      3: nice_req_inst=32'h4000705b; // drain opcode near miss
      4: nice_req_inst=32'h0600207b; // legacy funct7 between sbuf and rowsum
      default:$fatal(1,"Invalid minimal probe case");
    endcase
    repeat(3) @(negedge nice_clk);nice_rst_n=1;
    @(negedge nice_clk);nice_req_valid=1;
    @(posedge nice_clk);
    if(!nice_req_ready || !old_ready) $fatal(1,"Unsupported request was not accepted");
    @(negedge nice_clk);nice_req_valid=0;
    while(!nice_rsp_valid && elapsed<16) begin @(negedge nice_clk);elapsed=elapsed+1;end
    if(!nice_rsp_valid) begin
      $display("NICE_ROUTE_REPRO case=%0d inst=%h requests=%0d commands=%0d owner_valid=%b owner_drain=%b top_ready=%b top_rsp=%b child_rsp=%b old_ready=%b old_rsp=%b elapsed=%0d",
        selected,nice_req_inst,requests,commands,dut.owner_valid,dut.owner_drain,nice_req_ready,nice_rsp_valid,dut.demo_rsp_valid,old_ready,old_response,elapsed);
      $fatal(1,"NICE_ROUTE_UNSUPPORTED_NO_COMPLETION");
    end
    if(!nice_rsp_err || nice_rsp_rdat!==1 || commands!=0 || requests!=1)
      $fatal(1,"NICE_ROUTE_UNSUPPORTED_WRONG_COMPLETION err=%b data=%h",nice_rsp_err,nice_rsp_rdat);
    @(posedge nice_clk);#1;
    if(dut.owner_valid || !nice_req_ready) $fatal(1,"Error completion did not release owner");
    $display("NICE_ROUTE_INVALID_PASS case=%0d code=1 commands=0 requests=1",selected);
    $finish;
  end
  initial begin #10000;$fatal(1,"Invalid-route probe global timeout");end
endmodule
