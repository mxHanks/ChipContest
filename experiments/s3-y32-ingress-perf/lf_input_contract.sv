`ifndef XU_LF_INPUT_CONTRACT_SV
`define XU_LF_INPUT_CONTRACT_SV
`timescale 1ns/1fs
// External environment obligations, not a property implemented by the DUT.
// This checks digital edges/windows only; no analog CDC/RDC or pulse proof.
module xu_lf_input_contract #(
  parameter realtime LF_PERIOD_NS = 30517.578125
)(
  input wire lfclk,
  input wire bootrom_n,
  input wire dwakeup_n,
  input wire erst_n,
  input wire startup_complete
);
  integer samples = 0, boot_samples = 0, wake_samples = 0, reset_samples = 0;
  integer releases = 0, wake_changes = 0;
  realtime last_fall = -1.0, wake_change_at = 0.0, reset_assert_at = 0.0;
  reg initialized = 0, initial_boot;

  task automatic reject(input string reason);
    $fatal(1, "LF_INPUT_CONTRACT_REJECT reason=%s time_ns=%0.6f", reason, $realtime);
  endtask

  initial begin
    #0.000001;
    if ($isunknown(bootrom_n) || $isunknown(dwakeup_n) || $isunknown(erst_n)) reject("INITIAL_INPUT_X");
    initial_boot = bootrom_n;
    initialized = 1;
  end
  always @(posedge lfclk) begin
    samples = samples + 1;
    if (!$isunknown(bootrom_n) && bootrom_n === initial_boot) boot_samples = boot_samples + 1;
    else boot_samples = 0;
    if (!$isunknown(dwakeup_n)) wake_samples = wake_samples + 1;
    if (erst_n === 1'b0) reset_samples = reset_samples + 1;
  end
  always @(negedge lfclk) last_fall = $realtime;

  always @(bootrom_n) if (initialized) begin
    if ($isunknown(bootrom_n)) reject("BOOTROM_X");
    if (bootrom_n !== initial_boot) reject("BOOTROM_CHANGED");
  end
  always @(dwakeup_n) if (initialized) begin
    if ($isunknown(dwakeup_n)) reject("DWAKEUP_X");
    if (last_fall < 0 || $realtime - last_fall < 1.0 || $realtime - last_fall > 2.0)
      reject("DWAKEUP_EDGE_WINDOW");
    if (wake_samples < 4 || $realtime - wake_change_at < 4.0 * LF_PERIOD_NS)
      reject("DWAKEUP_MIN_HOLD");
    wake_samples = 0;
    wake_change_at = $realtime;
    wake_changes = wake_changes + 1;
  end
  always @(erst_n) if (initialized) begin
    if ($isunknown(erst_n)) reject("ERST_X");
    if (erst_n === 1'b0) begin
      reset_assert_at = $realtime;
      reset_samples = 0;
    end else begin
      if (last_fall < 0 || $realtime - last_fall < 1.0 || $realtime - last_fall > 2.0)
        reject("ERST_RELEASE_WINDOW");
      if (reset_samples < 8 || $realtime - reset_assert_at < 8.0 * LF_PERIOD_NS)
        reject("ERST_MIN_LOW");
      if (boot_samples < 8) reject("BOOTROM_STARTUP_SAMPLES");
      releases = releases + 1;
      $display("LF_INPUT_CONTRACT_RELEASE samples=%0d boot_samples=%0d low_ns=%0.6f fall_offset_ns=%0.6f",
               reset_samples, boot_samples, $realtime - reset_assert_at, $realtime - last_fall);
    end
  end
  always @(posedge startup_complete) begin
    if (!initialized || boot_samples < 8 || releases < 1 || erst_n !== 1'b1)
      reject("STARTUP_BEFORE_INPUT_CONTRACT");
    $display("LF_INPUT_CONTRACT_STARTUP_PASS boot_samples=%0d releases=%0d", boot_samples, releases);
  end
endmodule
`endif
