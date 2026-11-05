`timescale 1ns/1fs
// Check phase accuracy of absolute-target 150MHz TB clock scheduling.
module tb_xu_nominal_clock_probe;
  reg clk=0,lfclk=0,rst_n=0;
  integer half_index=0,edges=0,reset_edges=0;
  real target_ns,phase_error_ns,max_phase_error_ns=0.0;
  initial forever begin
    half_index=half_index+1;
    target_ns=half_index*(10.0/3.0);
    #(target_ns-$realtime);
    clk=~clk;
    phase_error_ns=$realtime-target_ns;
    if (phase_error_ns<0) phase_error_ns=-phase_error_ns;
    if (phase_error_ns>max_phase_error_ns) max_phase_error_ns=phase_error_ns;
    if (phase_error_ns>0.000000501)
      $fatal(1,"150MHz accumulated phase error half=%0d ns=%0.12f",half_index,phase_error_ns);
    if (half_index==2000000) begin
      if (reset_edges!=30) $fatal(1,"reset edge count=%0d",reset_edges);
      $display("XU_NOMINAL_CLOCK_PASS half_edges=%0d reset_edges=%0d max_phase_error_ns=%0.12f end_time_ns=%0.12f",half_index,reset_edges,max_phase_error_ns,$realtime);
      $finish;
    end
  end
  always #15258.7890625 lfclk=~lfclk;
  initial #200 rst_n=1;
  always @(posedge clk) begin
    edges=edges+1;
    if (!rst_n) reset_edges=reset_edges+1;
  end
endmodule
