`timescale 1ns/1fs
// Capability experiment only. No VCS SAIF support is presumed until the host
// runner validates DURATION, TC, T0 and T1 against this deterministic circuit.
module xu_activity_probe_dut(input wire clk);
  reg q = 1'b0;
  reg [3:0] count = 4'b0;
  always @(posedge clk) begin
    q <= ~q;
    count <= count + 1'b1;
  end
endmodule

module xu_activity_probe;
  reg clk = 1'b0;
  always #5 clk = ~clk;
  xu_activity_probe_dut u_probe(.clk(clk));
  string mode, policy;
  initial begin
    if (!$value$plusargs("PROBE_MODE=%s", mode)) mode = "all";
    if (mode != "all" && mode != "combined" && mode != "second")
      $fatal(1, "invalid PROBE_MODE");
    if (!$value$plusargs("PROBE_POLICY=%s", policy)) policy = "union";
    $display("XU_PROBE_POLICY policy=%s", policy);
    // Policies are capability experiments. Never accept a clk-only SAIF.
    // A repeated set_toggle_region in union may or may not retain both kinds;
    // the host requires clk plus every internal reg bit before accepting it.
`ifdef XU_PROBE_VCD
    $dumpfile("probe.vcd");
    $dumpvars(0, xu_activity_probe.u_probe);
`else
    case (policy)
      "default": begin end
      "rtl_on": $set_gate_level_monitoring("rtl_on");
      "rtl_sv": $set_gate_level_monitoring("rtl_on", "sv");
      "on_sv": $set_gate_level_monitoring("on", "sv");
      "union": begin
        $set_gate_level_monitoring("rtl_on", "sv");
        $set_toggle_region(xu_activity_probe.u_probe);
        $set_gate_level_monitoring("on", "sv");
      end
      default: $fatal(1, "invalid PROBE_POLICY");
    endcase
    $set_toggle_region(xu_activity_probe.u_probe);
`endif
    #22;
    if (mode != "second") begin
      $display("XU_PROBE_BEGIN window=0 time_ps=%0d", $time * 1000);
`ifndef XU_PROBE_VCD
      $toggle_start();
`endif
    end
    #40;
    if (mode != "second") begin
`ifndef XU_PROBE_VCD
      $toggle_stop();
`endif
      $display("XU_PROBE_END window=0 time_ps=%0d", $time * 1000);
      if (mode == "all") begin
`ifndef XU_PROBE_VCD
        $toggle_report("first.saif", 1.0e-15, "xu_activity_probe.u_probe");
        $toggle_report("first_repeat.saif", 1.0e-15, "xu_activity_probe.u_probe");
`endif
      end
    end
    #20;
    $display("XU_PROBE_BEGIN window=1 time_ps=%0d", $time * 1000);
`ifndef XU_PROBE_VCD
    $toggle_start();
`endif
    #40;
`ifndef XU_PROBE_VCD
    $toggle_stop();
`endif
    $display("XU_PROBE_END window=1 time_ps=%0d", $time * 1000);
`ifndef XU_PROBE_VCD
    $toggle_report("final.saif", 1.0e-15, "xu_activity_probe.u_probe");
`endif
    #1;
`ifndef XU_PROBE_VCD
    $toggle_report("after_idle.saif", 1.0e-15, "xu_activity_probe.u_probe");
`endif
    $display("XU_ACTIVITY_PROBE_FINISHED mode=%s", mode);
    $finish;
  end
endmodule
