`timescale 1ns/1fs
`include "lf_input_contract.sv"
module tb_lf_input_contract;
  localparam realtime HALF_LF = 15258.7890625;
  reg hfclk = 0, lfclk = 0, lf_enable = 1;
  reg bootrom_n = 0, dwakeup_n = 1, erst_n = 0, startup_complete = 0;
  wire boot_q, wake_q, reset_out;
  string bad_case;
  integer cases = 0;
  always #3.333333333 hfclk = ~hfclk;
  always #(HALF_LF) lfclk = lf_enable ? ~lfclk : 1'b0;
  xu_lf_input_contract environment(.*);
  sirv_DeglitchShiftRegister bootrom_deglitch
    (.clock(lfclk), .reset(1'b1), .io_d(~bootrom_n), .io_q(boot_q));
  sirv_DeglitchShiftRegister dwakeup_deglitch
    (.clock(lfclk), .reset(1'b1), .io_d(~dwakeup_n), .io_q(wake_q));
  sirv_ResetCatchAndSync reset_catcher
    (.clock(lfclk), .reset(~erst_n), .test_mode(1'b0), .io_sync_reset(reset_out));

  task automatic require(input logic good, input string detail);
    if (good !== 1'b1) $fatal(1, "LF_CONTRACT_DUT_FAIL %s", detail);
  endtask
  task automatic sampled;
    @(posedge lfclk); #0.000001;
  endtask
  task automatic safe_release;
    repeat (9) sampled;
    @(negedge lfclk); #1.5; erst_n = 1;
    repeat (3) sampled;
    require(reset_out === 1'b0, "real three-stage catcher releases");
    require(boot_q === 1'b1 && wake_q === 1'b0, "strap/wakeup known before startup");
    #0.000001; startup_complete = 1;
  endtask
  task automatic safe_wake(input reg value);
    @(negedge lfclk); #1.5; dwakeup_n = value;
    repeat (4) sampled;
    require(wake_q === ~value, "stable LF wake propagates through real deglitch");
    cases = cases + 1;
  endtask

  initial begin
    if (!$value$plusargs("BAD_CASE=%s", bad_case)) bad_case = "none";
    #0.000002;
    require($isunknown(boot_q) && $isunknown(wake_q), "unreset production state retains X");
    if (bad_case == "bootrom-change") begin #2; bootrom_n = 1; end
    else if (bad_case == "input-x") begin #2; dwakeup_n = 1'bx; end
    else if (bad_case == "early-release") begin
      repeat (2) sampled; @(negedge lfclk); #1.5; erst_n = 1;
    end else begin
      safe_release;
      cases = cases + 1;
      if (bad_case == "wake-wrong-edge") begin @(posedge lfclk); #1.5; dwakeup_n = 0; end
      else if (bad_case == "wake-short-hold") begin
        safe_wake(0);
        @(negedge lfclk); #1.5; dwakeup_n = 1;
        @(negedge lfclk); #1.5; dwakeup_n = 0;
      end else if (bad_case == "reset-wrong-edge") begin
        @(posedge hfclk); #0.000002; erst_n = 0;
        repeat (9) sampled; @(posedge lfclk); #1.5; erst_n = 1;
      end else if (bad_case == "reset-short-low") begin
        @(negedge lfclk); #1.5; erst_n = 0;
        repeat (2) sampled; @(negedge lfclk); #1.5; erst_n = 1;
      end else if (bad_case == "reset-stopped-release") begin
        @(negedge lfclk); lf_enable = 0;
        @(posedge hfclk); #0.000002; erst_n = 0;
        #(20.0 * HALF_LF); erst_n = 1;
      end else if (bad_case == "none") begin
        safe_wake(0); safe_wake(1); safe_wake(0);
        // Event remains asserted across a stopped LF; neither time alone nor HF
        // edges count as LF sampling. Resume and complete four real samples.
        @(negedge lfclk); lf_enable = 0;
        #(12.0 * HALF_LF);
        require(wake_q === 1'b1, "asserted wake retained while LF stopped");
        lf_enable = 1;
        repeat (4) sampled;
        safe_wake(1);
        @(posedge hfclk); #0.000002; erst_n = 0; // asynchronous assertion allowed
        repeat (9) sampled;
        @(negedge lfclk); #1.5; erst_n = 1;
        repeat (3) sampled;
        require(reset_out === 1'b0, "safe arbitrary assertion and LF-aligned release");
        cases = cases + 1;
        require(environment.releases == 2 && environment.wake_changes == 4,
                "monitor observed both resets and every wake transition");
        $display("LF_INPUT_CONTRACT_PASS cases=%0d releases=%0d wake_changes=%0d", cases, environment.releases, environment.wake_changes);
        $finish;
      end else $fatal(1, "unknown BAD_CASE");
    end
    #2;
    $fatal(1, "LF_CONTRACT_NEGATIVE_WAS_NOT_REJECTED case=%s", bad_case);
  end
  initial begin #(HALF_LF * 1000.0); $fatal(1, "LF_CONTRACT_DUT_FAIL watchdog"); end
endmodule
