`timescale 1ns/1fs
// INDEPENDENT GENERIC FUNCTIONAL PROTOTYPE. NOT a vendor SCC40 model.
// No Liberty area, timing, power, retention or PVT eligibility is represented.
// The 64x256 interleaving is explicit solely for the existing preload seam.
module RAMSP1024X16 (
  output reg [15:0] Q,
  input CLK,CEN,GWEN,
  input [15:0] WEN,
  input [9:0] A,
  input [15:0] D,
  input [2:0] EMA,
  input [1:0] EMAW,
  input RET1N
);
  reg [63:0] mem [0:255];
  integer bit_index;
  initial $display("S3_GENERIC_NON_PPA_MACRO_INSTANCE %m");
  always @(posedge CLK) begin
    if(CEN===1'b0) begin
      if((^A)===1'bx || RET1N!==1'b1 || (GWEN!==1'b0&&GWEN!==1'b1)) Q<=16'bx;
      else if(GWEN) begin
        for(bit_index=0;bit_index<16;bit_index=bit_index+1)
          Q[bit_index]<=mem[A[9:2]][4*bit_index+A[1:0]];
      end else begin
        for(bit_index=0;bit_index<16;bit_index=bit_index+1)
          if(WEN[bit_index]===1'b0) mem[A[9:2]][4*bit_index+A[1:0]]<=D[bit_index];
          else if(WEN[bit_index]!==1'b1) mem[A[9:2]][4*bit_index+A[1:0]]<=1'bx;
      end
    end
  end
endmodule
