`timescale 1ns/1ps
// Compare with the actual generated logical memory and external vendor macro.
// The runner renames mem_32x40 in the generated reference without editing it.
`ifndef XU_VENDOR_SRAM_MODEL
  `error "The bias SRAM contract requires the caller-supplied vendor model"
`endif
module tb_xu_bias_sram_adapter;
  reg clk=0;
  always #5 clk=~clk;
  reg en=0, wmode=0;
  reg [4:0] addr=0, wmask=0;
  reg [39:0] wdata=0;
  wire [39:0] got, want;
  mem_32x40 dut (.RW0_addr(addr), .RW0_en(en), .RW0_clk(clk),
    .RW0_wmode(wmode), .RW0_wdata(wdata), .RW0_wmask(wmask), .RW0_rdata(got));
  xu_reference_mem_32x40 reference (.RW0_addr(addr), .RW0_en(en), .RW0_clk(clk),
    .RW0_wmode(wmode), .RW0_wdata(wdata), .RW0_wmask(wmask), .RW0_rdata(want));

  integer cycles=0, read_checks=0, invalid_checks=0;
  integer a, mask, byte_index, i;
  integer seed=32'h5875b1a5;
  reg [39:0] previous;

  function automatic [39:0] pattern(input integer address, input integer iteration);
    pattern=(40'h1d355983a7 * (address+1)) ^ (40'hc17ba9532f * (iteration+1));
  endfunction

  // Check the physical pins independently of the logical reference. This
  // includes the unused upper byte: its write enables must always stay high.
  genvar lane;
  generate for (lane=0; lane<3; lane=lane+1) begin: pin_contract
    wire [15:0] expected_d, expected_wen;
    if (lane<2) begin: full_slice
      assign expected_d=wdata[16*lane+:16];
      assign expected_wen={{8{~wmask[2*lane+1]}},{8{~wmask[2*lane]}}};
    end else begin: last_slice
      assign expected_d={8'b0,wdata[39:32]};
      assign expected_wen={8'hff,{8{~wmask[4]}}};
    end
    always @(posedge clk) begin
      if (dut.width_lane[lane].macro.A !== {2'b0,addr} ||
          dut.width_lane[lane].macro.CEN !== ~en ||
          dut.width_lane[lane].macro.GWEN !== ~wmode ||
          dut.width_lane[lane].macro.D !== expected_d ||
          dut.width_lane[lane].macro.WEN !== expected_wen ||
          dut.width_lane[lane].macro.EMA !== 3'b010 ||
          dut.width_lane[lane].macro.EMAW !== 2'b00 ||
          dut.width_lane[lane].macro.RET1N !== 1'b1)
        $fatal(1,"physical pin contract differs in slice %0d",lane);
    end
  end endgenerate

  task step(input enable, input write_mode, input [4:0] address,
            input [39:0] data, input [4:0] byte_mask);
    begin
      @(negedge clk);
      previous=got;
      en=enable; wmode=write_mode; addr=address; wdata=data; wmask=byte_mask;
      #0.1;
      if (got !== previous)
        $fatal(1,"read output changed before the clock edge at cycle %0d",cycles);
      @(posedge clk); #1;
      cycles=cycles+1;
      if (got !== want)
        $fatal(1,"bias contract mismatch cycle=%0d en=%b wr=%b a=%0d mask=%b got=%h want=%h",
               cycles,en,wmode,addr,wmask,got,want);
      if (enable && !write_mode) begin
        read_checks=read_checks+1;
        // Padding starts unknown and must never be written, even when every
        // logical byte is selected. Observe the actual vendor Q on reads.
        if (dut.width_lane[2].q[15:8] !== 8'hxx)
          $fatal(1,"unused physical upper byte was modified at cycle %0d",cycles);
      end else begin
        invalid_checks=invalid_checks+1;
        if (got !== 40'hxxxxxxxxxx)
          $fatal(1,"disabled/write output must be unknown at cycle %0d",cycles);
      end
    end
  endtask

  initial begin
    // Every unwritten address must retain four-state unknown contents.
    for (a=0;a<32;a=a+1) begin
      step(1,0,a,0,0);
      if (got !== 40'hxxxxxxxxxx) $fatal(1,"unwritten read became known a=%0d",a);
    end
    for (a=0;a<32;a=a+1) step(1,1,a,pattern(a,0),5'b11111);
    // Consecutive reads and address noise before the edge check read latency.
    for (a=31;a>=0;a=a-1) step(1,0,a,0,0);
    // Every byte mask at every logical address, including a zero mask and
    // writes crossing the two 16-bit slice boundaries.
    for (a=0;a<32;a=a+1)
      for (mask=0;mask<32;mask=mask+1) begin
        step(1,1,a,pattern(a,mask+1),mask);
        step(1,0,a,0,0);
        step(0,1,a,~pattern(a,mask+1),5'b11111);
        step(1,0,a,0,0);
      end
    // Unknown data in each selected byte must propagate without poisoning
    // the other four bytes; then overwrite it with known data again.
    for (a=0;a<32;a=a+1)
      for (byte_index=0;byte_index<5;byte_index=byte_index+1) begin
        step(1,1,a,40'hxxxxxxxxxx,1<<byte_index);
        step(1,0,a,0,0);
        step(1,1,a,pattern(a,byte_index+40),1<<byte_index);
        step(1,0,a,0,0);
      end
    for (i=0;i<512;i=i+1)
      step($random(seed)&1,$random(seed)&1,$random(seed)&31,
           {$random(seed),$random(seed)},$random(seed)&31);
    for (a=0;a<32;a=a+1) step(1,0,a,0,0);
    step(0,0,0,0,0);
    $display("XU_BIAS_SRAM_CONTRACT_PASS addresses=32 masks_per_address=32 exhaustive_mask_writes=1024 x_byte_writes=160 cycles=%0d read_checks=%0d invalid_checks=%0d model=vendor-functional",
             cycles,read_checks,invalid_checks);
    $finish;
  end
  initial begin #100000;$fatal(1,"bias contract timeout");end
endmodule
