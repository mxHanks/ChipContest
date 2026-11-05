// PPA-only replacement for the generated, masked single-RW mem_32x40.
// Compile instead of its behavioral definition, with the real RAMSP128X16
// technology model/cell. EMA/EMAW still require selected-corner qualification.
module mem_32x40 #(
  parameter [2:0] XU_EMA = 3'b010,
  parameter [1:0] XU_EMAW = 2'b00
)(
  input [4:0] RW0_addr,
  input RW0_en, RW0_clk, RW0_wmode,
  input [39:0] RW0_wdata,
  input [4:0] RW0_wmask,
  output [39:0] RW0_rdata
);
  wire [39:0] macro_q;
  reg valid_read;
  always @(posedge RW0_clk) valid_read <= RW0_en & ~RW0_wmode;

  genvar lane, bit_index;
  generate
    for (lane=0; lane<3; lane=lane+1) begin: width_lane
      wire [15:0] d, q, wen;
      for (bit_index=0; bit_index<16; bit_index=bit_index+1) begin: bitslice
        if (16*lane+bit_index<40) begin: present
          assign d[bit_index] = RW0_wdata[16*lane+bit_index];
          assign wen[bit_index] = ~RW0_wmask[(16*lane+bit_index)/8];
          assign macro_q[16*lane+bit_index] = q[bit_index];
        end else begin: padding
          assign d[bit_index] = 1'b0;
          assign wen[bit_index] = 1'b1;
        end
      end
      RAMSP128X16 macro (
        .Q(q), .CLK(RW0_clk), .CEN(~RW0_en),
        .WEN(wen), .GWEN(~RW0_wmode), .A({2'b0, RW0_addr}),
        .D(d), .EMA(XU_EMA), .EMAW(XU_EMAW), .RET1N(1'b1)
      );
    end
  endgenerate

  // The generated logical memory defines only enabled reads. Do not expose
  // the physical macro's retained Q during writes or disabled cycles.
  assign RW0_rdata = valid_read ? macro_q : 40'bx;
endmodule
