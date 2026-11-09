`timescale 1ns/1ps
`include "e203_defines.v"
// Compile-time wrapper disable cannot advertise live metadata or enable it.
module tb_ready_wrapper_disabled;
  reg clk=0,rst_n=0;
  always #5 clk=~clk;
  reg cmd_valid=0,cmd_read=0,rsp_ready=0;
  reg [31:0] cmd_addr=32'h100420f4,cmd_wdata=1;
  reg [3:0] cmd_wmask=15;
  wire cmd_ready,rsp_valid,rsp_err;
  wire [31:0] rsp_rdata;
  wire xu_direct_capable,xu_direct_claim,xu_direct_valid,xu_direct_ready;
  wire xu_direct_commit,xu_direct_commit_ready,xu_direct_commit_err;
  wire [255:0] xu_direct_payload;
  wire [31:0] xu_direct_status;
  reg nice_req_valid=0;
  wire nice_req_ready,nice_rsp_valid,nice_rsp_err,nice_cmd_valid;
  wire [31:0] nice_rsp_data;
  accel_icb_slave #(.DIRECT_ENABLE(0)) dut(.*);
  xu_nice_drain8 #(.DIRECT_ENABLE(1)) nice(
    .nice_clk(clk),.nice_rst_n(rst_n),.nice_active(),.nice_mem_holdup(),
    .nice_req_valid(nice_req_valid),.nice_req_ready(nice_req_ready),
    .nice_req_inst(32'h4800707b),.nice_req_rs1(32'ha0020000),.nice_req_rs2(32'h7e0),
    .nice_rsp_valid(nice_rsp_valid),.nice_rsp_ready(1'b0),
    .nice_rsp_rdat(nice_rsp_data),.nice_rsp_err(nice_rsp_err),
    .nice_icb_cmd_valid(nice_cmd_valid),.nice_icb_cmd_ready(1'b1),
    .nice_icb_cmd_addr(),.nice_icb_cmd_read(),.nice_icb_cmd_wdata(),.nice_icb_cmd_size(),
    .nice_icb_rsp_valid(1'b0),.nice_icb_rsp_ready(),.nice_icb_rsp_rdata(32'b0),.nice_icb_rsp_err(1'b0),
    .xu_direct_capable(xu_direct_capable),.xu_direct_claim(xu_direct_claim),
    .xu_direct_valid(xu_direct_valid),.xu_direct_ready(xu_direct_ready),
    .xu_direct_payload(xu_direct_payload),.xu_direct_status(xu_direct_status),
    .xu_direct_commit(xu_direct_commit),.xu_direct_commit_ready(xu_direct_commit_ready),
    .xu_direct_commit_err(xu_direct_commit_err));
  initial begin
    repeat(3)@(negedge clk);rst_n=1;
    if(xu_direct_capable || xu_direct_status[31])$fatal(1,"disabled wrapper advertised live capability");
    @(negedge clk);cmd_valid=1;
    @(posedge clk);if(!cmd_ready)$fatal(1,"disabled CTRL request not ready");#1;
    @(negedge clk);cmd_valid=0;
    if(!rsp_valid || !rsp_err || xu_direct_capable || xu_direct_status[31])
      $fatal(1,"disabled wrapper accepted direct enable");
    rsp_ready=1;@(posedge clk);#1;@(negedge clk);rsp_ready=0;
    nice_req_valid=1;@(posedge clk);if(!nice_req_ready)$fatal(1,"request not ready");#1;
    @(negedge clk);nice_req_valid=0;
    repeat(7)begin
      @(negedge clk);
      if(!nice_rsp_valid || !nice_rsp_err || nice_rsp_data!=1 ||
         nice_cmd_valid || xu_direct_claim || xu_direct_commit || xu_direct_status[31])
        $fatal(1,"disabled wrapper ready operation side effect");
    end
    $display("READY_WRAPPER_DISABLED_PASS compile_time_enable=0 rejected_enable=1 rejected_ready_instruction=1 no_side_effect=1");
    $finish;
  end
  initial begin #10000;$fatal(1,"disabled wrapper timeout");end
endmodule
