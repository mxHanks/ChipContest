// xu actual S2c wrapper + actual fixed-platform 20-stage reset chain.
// Deliberately release the external TB reset while the core clock is stopped:
// the synchronous FIFO remains X until its own clock samples asserted reset.
`timescale 1ns/1fs
module tb_xu_s2c_reset_guard;
  reg clk=0,rst_n=0,clock_enabled=0,reset_request=1;
  always #5 clk=~clk;
  wire accel_clk=clk && clock_enabled;
  wire synchronized_reset,accel_rst_n=~synchronized_reset;
  sirv_ResetCatchAndSync_2 actual_platform_reset(.clock(accel_clk),.reset(reset_request),
      .test_mode(1'b0),.io_sync_reset(synchronized_reset));
  reg bus_valid=0;
  wire bus_ready,bus_rsp_valid,bus_rsp_err;
  wire [31:0] bus_rsp_data;
  accel_icb_slave dut(.clk(accel_clk),.rst_n(accel_rst_n),.cmd_valid(bus_valid),
      .cmd_read(1'b1),.cmd_addr(32'h10042000),.cmd_wdata(32'b0),.cmd_wmask(4'b0),
      .cmd_ready(bus_ready),.rsp_valid(bus_rsp_valid),.rsp_ready(1'b0),
      .rsp_err(bus_rsp_err),.rsp_rdata(bus_rsp_data));
  `define ACCEL dut
  localparam BASE=32'ha0000000;
  reg cmd_valid=0,cmd_read=1,cmd_ready=0;
  reg [31:0] cmd_addr=BASE;
  integer cycles=0,mode=0,i;
  reg [15:0] w[0:16383],x[0:6335];
  reg [39:0] bias[0:255];
  reg [47:0] golden[0:25343];
@DECLARATIONS@
  always @(posedge clk) begin
    cycles=cycles+1;
    if(rst_n) begin
      if(mode==8) xu_observe_clear_window();
      else xu_observe_candidate_reset_window();
    end
  end
  initial begin
    if(!$value$plusargs("MODE=%d",mode)) mode=0;
    xu_global_task=7;
    for(i=0;i<256;i=i+1) begin xu_bias_seen[i]=0;xu_clear_bias_committed[i]=0;end
    repeat(4) @(negedge clk);
    if((^{dut.row_active,dut.row_running,dut.row_count,dut.row_produced,dut.row_retired})!==1'bx)
      $fatal(1,"fixture did not expose unclocked synchronous FIFO startup X");
    $display("XU_RESET_FIXTURE_UNCLOCKED_FIFO_X actual_rst_n=%b sampled_reset_edges=%0d",dut.rst_n,xu_accel_reset_clock_edges);
    rst_n=1;
    if(mode==1) bus_valid=1;
    if(mode==2) cmd_valid=1;
    if(mode==3) force dut.rst_n=1'b1;
    repeat(4) @(negedge clk);
    clock_enabled=1;
    repeat(3) @(negedge clk);
    reset_request=0;
    wait(dut.rst_n===1'b1);
    if(mode==6) force dut.u_linear_compute_core.head=1'b1;
    wait(xu_accel_observation_ready);
    @(negedge clk);
    if(mode==4) reset_request=1;
    if(mode==5) force dut.rst_n=1'bx;
    if(mode==7) force dut.u_linear_compute_core.io_wLoadWen=1'bx;
    repeat(3) @(negedge clk);
    if(xu_accel_reset_clock_edges<23 || xu_accel_startup_observer_edges<4 ||
       !xu_reset_checked || !xu_accel_observation_ready || xu_saif_started || xu_clear_writes!=0)
      $fatal(1,"fixture reset readiness proof incomplete");
    $display("XU_RESET_GUARD_PASS actual_20stage_chain=1 wrapper_sync_fifo=1 stopped_clock_startup_x=1 actual_reset_clock_edges=%0d startup_observer_edges=%0d clear_writes=0 saif_started=0",xu_accel_reset_clock_edges,xu_accel_startup_observer_edges);
    $finish;
  end
  initial begin #1000; $fatal(1,"fixture timeout");end
endmodule
