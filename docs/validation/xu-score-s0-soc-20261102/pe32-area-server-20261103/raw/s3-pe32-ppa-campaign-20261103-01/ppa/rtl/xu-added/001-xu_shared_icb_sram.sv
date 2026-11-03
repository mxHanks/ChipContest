// Independent PPA harness endpoint; fixed platform/TB remain untouched.
// 131072x32 = 512 KiB, one registered response and up to one outstanding request.
// THROTTLE_RESET_PHASE=2 aligns the existing TB's 30 pre-reset clock edges at
// absolute 120ns reset release (4ns clock), or 200ns at nominal 150MHz,
// with cycles%7. Other reset schedules must
// explicitly revalidate the phase; this is not a claim of physical bus timing.
module xu_shared_icb_sram #(
  parameter THROTTLE_RESET_PHASE=2
)(
  input clk,rst_n,
  input cmd_valid,
  output cmd_ready,
  input [31:0] cmd_addr,
  input cmd_read,
  input [31:0] cmd_wdata,
  input [3:0] cmd_wmask,
  output reg rsp_valid,
  input rsp_ready,
  output reg rsp_err,
  output [31:0] rsp_rdata
);
  reg [2:0] phase;
  wire accept=cmd_valid && cmd_ready;
  wire in_range=cmd_addr>=32'ha0000000 && cmd_addr<32'ha0080000 && cmd_addr[1:0]==0;
  wire [31:0] ram_data;
  assign cmd_ready=(~rsp_valid || rsp_ready) && phase!=0;
  sirv_sim_ram #(.DP(131072),.DW(32),.MW(4),.AW(17),.FORCE_X2ZERO(0)) storage (
    .clk(clk),.din(cmd_wdata),.addr(cmd_addr[18:2]),
    .cs(accept && in_range),.we(~cmd_read),.wem(cmd_wmask),.dout(ram_data)
  );
  assign rsp_rdata=rsp_err?32'b0:ram_data;
  always @(posedge clk) begin
    if (!rst_n) begin
      phase<=THROTTLE_RESET_PHASE;
      rsp_valid<=0;
      rsp_err<=0;
    end else begin
      phase<=phase==6?0:phase+1'b1;
      if (rsp_valid && rsp_ready) rsp_valid<=0;
      if (accept) begin
        rsp_valid<=1;
        rsp_err<=~in_range;
      end
    end
  end
endmodule
