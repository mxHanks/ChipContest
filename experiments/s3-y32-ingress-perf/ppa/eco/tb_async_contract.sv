`timescale 1fs/1fs
// Real production modules, digital four-state contracts only. No timing/MTBF proof.
module tb_async_contract;
  localparam time HF_HALF = 3333333;
  localparam time LF_HALF = 15258789063;
  reg hfclk = 0, lfclk = 0, lf_enable = 1;
  reg por = 0, erst = 0, wdog = 0;
  reg boot_d = 0, wake_d = 0;
  wire boot_q, wake_q, aon_reset;
  wire [31:0] cause;
  integer hf_edges = 0, lf_edges = 0;
  integer checks = 0, cases = 0, phase_index;
  time phase;
  always #(HF_HALF) hfclk = ~hfclk;
  always #(LF_HALF) begin
    if (lf_enable) lfclk = ~lfclk;
    else lfclk = 0;
  end
  always @(posedge hfclk) hf_edges = hf_edges + 1;
  always @(posedge lfclk) lf_edges = lf_edges + 1;

  sirv_DeglitchShiftRegister bootrom_deglitch
    (.clock(lfclk), .reset(1'b1), .io_d(boot_d), .io_q(boot_q));
  sirv_DeglitchShiftRegister dwakeup_deglitch
    (.clock(lfclk), .reset(1'b1), .io_d(wake_d), .io_q(wake_q));
  sirv_ResetCatchAndSync aonrst_catch
    (.clock(lfclk), .reset(por | erst | wdog), .test_mode(1'b0), .io_sync_reset(aon_reset));
  // All unused PMU software/wakeup inputs tied inactive; no stub/copy of PMU RTL.
  sirv_pmu pmu (
    .clock(lfclk),
    .reset(aon_reset),
    .io_wakeup_awakeup('0),
    .io_wakeup_dwakeup('0),
    .io_wakeup_rtc('0),
    .io_wakeup_reset('0),
    .io_regs_ie_write_valid('0),
    .io_regs_ie_write_bits('0),
    .io_regs_cause_write_valid('0),
    .io_regs_cause_write_bits('0),
    .io_regs_sleep_write_valid('0),
    .io_regs_sleep_write_bits('0),
    .io_regs_key_write_valid('0),
    .io_regs_key_write_bits('0),
    .io_regs_wakeupProgram_0_write_valid('0),
    .io_regs_wakeupProgram_0_write_bits('0),
    .io_regs_wakeupProgram_1_write_valid('0),
    .io_regs_wakeupProgram_1_write_bits('0),
    .io_regs_wakeupProgram_2_write_valid('0),
    .io_regs_wakeupProgram_2_write_bits('0),
    .io_regs_wakeupProgram_3_write_valid('0),
    .io_regs_wakeupProgram_3_write_bits('0),
    .io_regs_wakeupProgram_4_write_valid('0),
    .io_regs_wakeupProgram_4_write_bits('0),
    .io_regs_wakeupProgram_5_write_valid('0),
    .io_regs_wakeupProgram_5_write_bits('0),
    .io_regs_wakeupProgram_6_write_valid('0),
    .io_regs_wakeupProgram_6_write_bits('0),
    .io_regs_wakeupProgram_7_write_valid('0),
    .io_regs_wakeupProgram_7_write_bits('0),
    .io_regs_sleepProgram_0_write_valid('0),
    .io_regs_sleepProgram_0_write_bits('0),
    .io_regs_sleepProgram_1_write_valid('0),
    .io_regs_sleepProgram_1_write_bits('0),
    .io_regs_sleepProgram_2_write_valid('0),
    .io_regs_sleepProgram_2_write_bits('0),
    .io_regs_sleepProgram_3_write_valid('0),
    .io_regs_sleepProgram_3_write_bits('0),
    .io_regs_sleepProgram_4_write_valid('0),
    .io_regs_sleepProgram_4_write_bits('0),
    .io_regs_sleepProgram_5_write_valid('0),
    .io_regs_sleepProgram_5_write_bits('0),
    .io_regs_sleepProgram_6_write_valid('0),
    .io_regs_sleepProgram_6_write_bits('0),
    .io_regs_sleepProgram_7_write_valid('0),
    .io_regs_sleepProgram_7_write_bits('0),
    .io_resetCauses_wdogrst(wdog),
    .io_resetCauses_erst(erst),
    .io_resetCauses_porrst(por),
    .io_regs_cause_read(cause)
  );

  task automatic check(input logic good, input string description);
    begin
      checks = checks + 1;
      if (good !== 1'b1)
        $fatal(1, "ASYNC_CONTRACT_FAIL time_fs=%0t check=%0d description=%s", $time, checks, description);
    end
  endtask
  task automatic lf_step;
    begin @(posedge lfclk); #1; end
  endtask
  task automatic mark(input string name);
    begin
      cases = cases + 1;
      $display("ASYNC_CONTRACT_CASE PASS index=%0d name=%s", cases, name);
    end
  endtask
  task automatic initialize_por;
    begin
      @(negedge lfclk); #2;
      por = 1; erst = 0; wdog = 0;
      #1; check(aon_reset === 1'b1, "POR asynchronously asserts AON reset");
      repeat (4) lf_step;
      check(cause[9:8] === 2'b00, "public PMU cause reports POR");
      @(negedge lfclk); #2; por = 0;
      repeat (4) lf_step;
      check(aon_reset === 1'b0, "AON releases after three LF edges");
    end
  endtask

  // A release may occur on either side of an LF edge, never on the same
  // simulator timestep. This exercises event ordering, not analog recovery.
  task automatic release_phase(input time offset, input integer index);
    begin
      @(negedge lfclk); #2; erst = 1;
      #1;
      check(pmu.erst_reset_r === 1'b1 && pmu.erst_reset_r_r === 1'b1,
            "ERST asynchronously sets both real PMU capture flops");
      check(aon_reset === 1'b1, "ERST asynchronously asserts real reset catcher output");
      repeat (2) lf_step;
      @(negedge lfclk); #(offset); erst = 0; #1;
      check(pmu.erst_reset_r_r === 1'b1, "ERST deassertion alone does not clear second stage");
      lf_step;
      check(pmu.erst_reset_r === 1'b0 && pmu.erst_reset_r_r === 1'b1,
            "ERST event held through first returning LF edge");
      check(aon_reset === 1'b1, "AON release catcher holds through first LF edge");
      lf_step;
      check(pmu.erst_reset_r === 1'b0 && pmu.erst_reset_r_r === 1'b0,
            "ERST capture chain releases on second LF edge");
      check(aon_reset === 1'b1, "AON release catcher holds through second LF edge");
      lf_step;
      check(aon_reset === 1'b0, "AON reset releases on third LF edge");
      check(cause[9:8] === 2'b01, "public PMU cause retains ERST");
      $display("ASYNC_CONTRACT_PHASE index=%0d release_offset_fs=%0t", index, offset);
      mark("ERST_release_phase");
    end
  endtask

  task automatic stopped_clock_pulse(input time width, input integer index);
    integer old_hf, old_lf;
    begin
      @(negedge lfclk); lf_enable = 0;
      old_hf = hf_edges; old_lf = lf_edges;
      #(HF_HALF * 3 + 11); erst = 1;
      #(width); erst = 0; #1;
      check(pmu.erst_reset_r === 1'b1 && pmu.erst_reset_r_r === 1'b1,
            "ERST pulse captured by actual PMU without LF clock");
      check(aon_reset === 1'b1, "actual reset catcher captures pulse without LF clock");
      #(LF_HALF * 2 + 17);
      check(lf_edges == old_lf && hf_edges > old_hf, "LF stays stopped while independent HF runs");
      check(pmu.erst_reset_r_r === 1'b1 && aon_reset === 1'b1,
            "stopped-clock event remains pending after ERST pulse has ended");
      lf_enable = 1;
      lf_step;
      check(pmu.erst_reset_r === 1'b0 && pmu.erst_reset_r_r === 1'b1,
            "pending event survives first restarted LF edge");
      lf_step;
      check(pmu.erst_reset_r_r === 1'b0 && aon_reset === 1'b1,
            "PMU event releases after two restarted edges but AON still held");
      lf_step;
      check(aon_reset === 1'b0 && cause[9:8] === 2'b01,
            "AON releases after third edge and public ERST cause is retained");
      $display("ASYNC_CONTRACT_STOPPED index=%0d pulse_width_fs=%0t", index, width);
      mark("LF_stopped_ERST_capture");
    end
  endtask

  task automatic priority_mask(input integer mask);
    reg [1:0] expected;
    begin
      expected = mask[0] ? 2'b00 : (mask[1] ? 2'b01 : 2'b10);
      @(negedge lfclk); #2; {wdog,erst,por} = mask[2:0];
      repeat (2) lf_step;
      check(cause[9:8] === expected, "public cause respects POR > ERST > WDOG while asserted");
      @(negedge lfclk); #2; {wdog,erst,por} = 3'b000;
      repeat (4) lf_step;
      check(cause[9:8] === expected, "public cause remains sticky after pulse retirement");
      $display("ASYNC_CONTRACT_PRIORITY mask=%0d public_cause=%0d", mask, expected);
      mark("reset_cause_priority_and_retention");
    end
  endtask

  initial begin
    // No force, initialization backdoor, two-state simulator, or X-to-zero cast.
    #1;
    check($isunknown(boot_q) && $isunknown(wake_q), "real unreset deglitch starts unknown");
    check($isunknown(pmu.erst_reset_r_r), "real PMU capture state is unknown before reset event");
    mark("four_state_initial_unknown_preserved");
    initialize_por;
    check(boot_q === 1'b0 && wake_q === 1'b0, "four LF samples establish stable inactive deglitch outputs");

    // Pulse entirely between LF sampling edges: intentionally filtered.
    @(negedge lfclk); #2; boot_d = 1; wake_d = 1;
    #(HF_HALF * 2); boot_d = 0; wake_d = 0;
    repeat (6) begin lf_step; check(boot_q === 1'b0 && wake_q === 1'b0, "sub-LF unsampled pulse is rejected"); end
    mark("deglitch_unsampled_short_pulse");

    // A high sampled on only one LF edge must not escape the two-sample filter.
    @(negedge lfclk); #2; boot_d = 1; wake_d = 1;
    lf_step;
    @(negedge lfclk); #2; boot_d = 0; wake_d = 0;
    repeat (6) begin lf_step; check(boot_q === 1'b0 && wake_q === 1'b0, "single-sample pulse is rejected"); end
    mark("deglitch_single_sample_pulse");

    @(negedge lfclk); #2; boot_d = 1; wake_d = 1;
    repeat (3) begin lf_step; check(boot_q === 1'b0 && wake_q === 1'b0, "stable active input waits through third sample"); end
    lf_step; check(boot_q === 1'b1 && wake_q === 1'b1, "stable active input propagates on fourth sample");
    @(negedge lfclk); #2; boot_d = 0; wake_d = 0;
    repeat (2) begin lf_step; check(boot_q === 1'b1 && wake_q === 1'b1, "inactive input preserves prior output through second sample"); end
    lf_step; check(boot_q === 1'b0 && wake_q === 1'b0, "inactive input propagates on third sample");
    mark("deglitch_stable_window_latency");

    // Four-state contamination remains observable and the other channel stays isolated.
    @(negedge lfclk); #2; boot_d = 1'bx;
    repeat (4) lf_step;
    check($isunknown(boot_q) && wake_q === 1'b0, "injected X propagates without contaminating independent channel");
    @(negedge lfclk); #2; boot_d = 0;
    repeat (4) lf_step;
    check(boot_q === 1'b0, "known input recovers unreset synchronizer");
    mark("four_state_X_propagation_and_recovery");

    for (phase_index = 0; phase_index < 10; phase_index = phase_index + 1) begin
      case (phase_index)
        0: phase = 2;
        1: phase = 1000;
        2: phase = HF_HALF;
        3: phase = LF_HALF / 3;
        4: phase = LF_HALF - 1000;
        5: phase = LF_HALF - 2;
        6: phase = LF_HALF + 2;
        7: phase = LF_HALF + 1000;
        8: phase = LF_HALF + HF_HALF;
        9: phase = 2 * LF_HALF - 2;
      endcase
      release_phase(phase, phase_index);
    end
    stopped_clock_pulse(1, 0);
    stopped_clock_pulse(1000, 1);
    stopped_clock_pulse(1000000, 2);
    stopped_clock_pulse(HF_HALF * 2, 3);
    for (phase_index = 1; phase_index < 8; phase_index = phase_index + 1)
      priority_mask(phase_index);
    for (phase_index = 7; phase_index > 0; phase_index = phase_index - 1)
      priority_mask(phase_index);

    // Release higher-priority causes while lower-priority sources stay asserted.
    @(negedge lfclk); #2; {wdog,erst,por} = 3'b111;
    repeat (2) lf_step; check(cause[9:8] === 2'b00, "overlap initially prioritizes POR");
    @(negedge lfclk); #2; por = 0;
    repeat (3) lf_step; check(cause[9:8] === 2'b01, "remaining ERST wins after POR retires");
    @(negedge lfclk); #2; erst = 0;
    repeat (3) lf_step; check(cause[9:8] === 2'b10, "remaining WDOG wins after ERST retires");
    @(negedge lfclk); #2; wdog = 0;
    repeat (4) lf_step; check(cause[9:8] === 2'b10, "WDOG cause retained after all release");
    mark("overlapping_cause_sequential_release");
    check(hf_edges > lf_edges * 1000, "independent HF and LF clocks both ran");
    $display("ASYNC_CONTRACT_PASS cases=%0d checks=%0d release_phases=10 stopped_pulses=4 priority_masks=14 hf_edges=%0d lf_edges=%0d", cases, checks, hf_edges, lf_edges);
    $display("ASYNC_CONTRACT_LIMIT digital_four_state_only unknown_STA_not_met no_analog_metastability_MTBF_or_physical_min_pulse_proof");
    $finish;
  end
  initial begin
    #(LF_HALF * 2000);
    $fatal(1, "ASYNC_CONTRACT_FAIL watchdog");
  end
endmodule
