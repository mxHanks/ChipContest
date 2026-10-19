`timescale 1ns/1ps
// Four-state unit fixture for the observer only; no accelerator DUT is present.
module tb_kwt_icb_pair_checker;
  reg clk=0,rst_n=0,cmd_valid=0,rsp_ready=0;
  reg ready0=1,ready1=1,rsp0=0,rsp1=0,error0=0,error1=0;
  reg [31:0] data0=0,data1=0;
  wire integer trace_checks,accepted_commands,accepted_responses;
  integer case_id=0;
  reg unknown_bit;
  kwt_icb_pair_checker checker_dut(
    .clk(clk),.rst_n(rst_n),.cmd_valid(cmd_valid),.rsp_ready(rsp_ready),
    .ready0(ready0),.ready1(ready1),.rsp0(rsp0),.rsp1(rsp1),
    .error0(error0),.error1(error1),.data0(data0),.data1(data1),
    .trace_checks(trace_checks),.accepted_commands(accepted_commands),
    .accepted_responses(accepted_responses));

  task automatic sample;
    begin #2;clk=1;#1;clk=0;#1;end
  endtask
  task automatic check_counts(input integer traces,commands,responses);
    begin
      if(trace_checks!==traces || accepted_commands!==commands || accepted_responses!==responses)
        $fatal(1,"CHECKER_FIXTURE_COUNT_MISMATCH traces=%0d commands=%0d responses=%0d",
          trace_checks,accepted_commands,accepted_responses);
    end
  endtask
  task automatic complete_positive;
    begin
      $display("CHECKER_FIXTURE_PASS case=%0d traces=%0d commands=%0d responses=%0d",
        case_id,trace_checks,accepted_commands,accepted_responses);
      $finish;
    end
  endtask

  initial begin
    if(!$value$plusargs("CASE=%d",case_id))$fatal(1,"CHECKER_FIXTURE_CASE_MISSING");
    sample();check_counts(0,0,0);rst_n=1;
    case(case_id)
      0: begin
        sample();check_counts(1,0,0);
        cmd_valid=1;ready0=0;ready1=0;
        sample();check_counts(2,0,0);
        ready0=1;ready1=1;
        sample();check_counts(3,1,0);
        cmd_valid=0;rsp0=1;rsp1=1;data0=32'h80001234;data1=data0;
        sample();check_counts(4,1,0); // Backpressured response is observed, not consumed.
        rsp_ready=1;
        sample();check_counts(5,1,1);
        rsp0=0;rsp1=0;
        sample();check_counts(6,1,1);
        cmd_valid=1;rsp0=1;rsp1=1;error0=1;error1=1;
        sample();check_counts(7,2,2); // Equal, known error responses are legal.
        rst_n=0;sample();check_counts(7,2,2);
        complete_positive();
      end
      1,2: begin
        unknown_bit=(case_id==1)?1'bx:1'bz;
        data0={32{unknown_bit}};data1=data0;error0=unknown_bit;error1=unknown_bit;
        repeat(3) sample();
        check_counts(3,0,0); // Unknown response payload is irrelevant while rsp_valid=0.
        complete_positive();
      end
      10,11,12,13,14,15,16,17: begin
        unknown_bit=(case_id%2==0)?1'bx:1'bz;
        case(case_id/2)
          5:cmd_valid=unknown_bit;
          6:rsp_ready=unknown_bit;
          7:begin ready0=unknown_bit;ready1=unknown_bit;end
          8:begin rsp0=unknown_bit;rsp1=unknown_bit;end
        endcase
      end
      20,21,22,23: begin
        rsp0=1;rsp1=1;unknown_bit=(case_id%2==0)?1'bx:1'bz;
        if(case_id<22) begin data0={32{unknown_bit}};data1=data0;end
        else begin error0=unknown_bit;error1=unknown_bit;end
      end
      30:ready1=0;
      31:rsp1=1;
      32:begin rsp0=1;rsp1=1;data1=32'h1;end
      33:begin rsp0=1;rsp1=1;error1=1;end
      40:rst_n=1'bx;
      41:rst_n=1'bz;
      default:$fatal(1,"CHECKER_FIXTURE_UNSUPPORTED_CASE case=%0d",case_id);
    endcase
    sample();
    $fatal(1,"CHECKER_FIXTURE_EXPECTED_REJECTION_MISSING case=%0d",case_id);
  end
endmodule
