// PPA-only implementation candidate for the unchanged sirv_sim_ram interface.
// Requires the exact vendor RAMSP1024X16 functional/timing model before qualification.
// Every 16-bit macro uses bit write enables, preserving each caller's byte mask.
module sirv_sim_ram #(
  parameter DP=512, FORCE_X2ZERO=0, DW=32, MW=4, AW=32,
  parameter [2:0] XU_EMA=3'b010,
  parameter [1:0] XU_EMAW=2'b00
)(
  input clk,
  input [DW-1:0] din,
  input [AW-1:0] addr,
  input cs, we,
  input [MW-1:0] wem,
  output [DW-1:0] dout
);
  wire [DW-1:0] raw_data;
  genvar b,l,k;
  generate if (DP>=1024 && AW>=10) begin: macro_storage
  localparam BANKS=(DP+1023)/1024;
  localparam LANES=(DW+15)/16;
  localparam BANK_AW=(BANKS>1)?$clog2(BANKS):1;
  wire [DW-1:0] bank_data [0:BANKS-1];
  reg [BANK_AW-1:0] read_bank;
  reg [AW-1:0] read_addr;
  reg forward_valid;
  reg [DW-1:0] forward_data;
  wire [DW-1:0] held_data=forward_valid ? forward_data : bank_data[read_bank];
  assign raw_data=held_data;
  integer bit_index;
  // Original behavioral RAM retains its read address. A later byte write to
  // that same address updates dout even with no new read. Macro Q normally
  // holds during writes, so forward merged bytes to preserve that behavior.
  always @(posedge clk) begin
    if (cs && !we) begin
      read_bank <= addr >> 10;
      read_addr <= addr;
      forward_valid <= 1'b0;
    end else if (cs && we && addr==read_addr) begin
      forward_valid <= 1'b1;
      for (bit_index=0;bit_index<DW;bit_index=bit_index+1)
        forward_data[bit_index] <= wem[bit_index/8] ? din[bit_index] : held_data[bit_index];
    end
  end
    for (b=0;b<BANKS;b=b+1) begin: depth_bank
      for (l=0;l<LANES;l=l+1) begin: width_lane
        wire [15:0] d,q,wen;
        for (k=0;k<16;k=k+1) begin: bitslice
          if (16*l+k<DW) begin: present
            assign d[k]=din[16*l+k];
            assign wen[k]=~wem[(16*l+k)/8];
            assign bank_data[b][16*l+k]=q[k];
          end else begin: padding
            assign d[k]=1'b0;
            assign wen[k]=1'b1;
          end
        end
        RAMSP1024X16 macro (
          .Q(q),.CLK(clk),.CEN(~(cs && (addr>>10)==b)),
          .WEN(wen),.GWEN(~we),.A(addr[9:0]),.D(d),
          .EMA(XU_EMA),.EMAW(XU_EMAW),.RET1N(1'b1)
        );
      end
    end
  end else begin: small_storage
    // The fixed debug module has a seven-word RAM. Preserve its original
    // register implementation instead of inventing an unsupported macro.
    // Semantics follow Nuclei sirv_sim_ram (Apache-2.0, 2018-2020).
    reg [DW-1:0] mem_r [0:DP-1];
    reg [AW-1:0] addr_r;
    always @(posedge clk) if (cs && !we) addr_r <= addr;
    for (l=0;l<MW;l=l+1) begin: byte_lane
      if (8*l+8>DW) begin: partial_byte
        always @(posedge clk) if (cs && we && wem[l])
          mem_r[addr][DW-1:8*l] <= din[DW-1:8*l];
      end else begin: full_byte
        always @(posedge clk) if (cs && we && wem[l])
          mem_r[addr][8*l+:8] <= din[8*l+:8];
      end
    end
    assign raw_data=mem_r[addr_r];
  end
    for (k=0;k<DW;k=k+1) begin: output_bits
      `ifndef SYNTHESIS
        if (FORCE_X2ZERO==1) begin: force_zero
          assign dout[k]=(raw_data[k]===1'bx)?1'b0:raw_data[k];
        end else begin: raw
          assign dout[k]=raw_data[k];
        end
      `else
        assign dout[k]=raw_data[k];
      `endif
    end
  endgenerate
  `ifndef SYNTHESIS
  initial begin
    if (MW*8<DW || MW>(DW+7)/8 || DP<1 || AW<$clog2(DP))
      $fatal(1,"unsupported xu SRAM geometry");
  end
  always @(posedge clk) if (cs && addr>=DP) $fatal(1,"xu SRAM address outside logical depth");
  `endif
endmodule
