`timescale 1ns/1ps
module tb_xu_pe32_bank128;
  reg clock=0;
  always #5 clock=~clock;
  reg reset=0, io_wen=0, io_ren=0;
  reg [8:0] io_addr=0;
  reg [15:0] io_data=0;
  wire [15:0] io_result;
  XuParallelWeightBank32Bank128 dut(.*);
  integer writes=0, reads=0, unknown_reads=0, low, depth, i, addr;
  reg [15:0] expected;
  wire [3:0] enables={dut.rams_3.io_en,dut.rams_2.io_en,dut.rams_1.io_en,dut.rams_0.io_en};

  function automatic [15:0] word(input integer address);
    if(address==0)word=16'h8000;
    else if(address==511)word=16'h7fff;
    else word=(address*31337+12345)-32768;
  endfunction
  function automatic integer boundary(input integer index);
    case(index)
      0:boundary=0;1:boundary=127;2:boundary=128;3:boundary=255;
      4:boundary=256;5:boundary=383;6:boundary=384;default:boundary=511;
    endcase
  endfunction

  always @(posedge clock) begin
    if(io_wen && io_ren)$fatal(1,"single-RW collision is illegal");
    if(enables !== ((io_wen||io_ren)?(4'b1 << io_addr[8:7]):4'b0))
      $fatal(1,"access enabled an unselected macro");
    if(io_wen)writes=writes+1;
    if(io_ren)reads=reads+1;
  end
  genvar bank;
  // Direct named pins are observed by the actual test; they are not counters
  // reconstructed from firmware or a second memory port.
  `define CHECK_QUIET(n) \
    always @(posedge clock) begin \
      if(io_addr[8:7] != n && (dut.rams_``n.io_addr !== 0 || dut.rams_``n.io_wdata !== 0 || dut.rams_``n.io_isWrite !== 0)) \
        $fatal(1,"inactive macro inputs toggle"); \
    end
  `CHECK_QUIET(0)
  `CHECK_QUIET(1)
  `CHECK_QUIET(2)
  `CHECK_QUIET(3)
  `undef CHECK_QUIET

  task automatic write_word(input integer address,input [15:0] data);
    begin
      @(negedge clock);io_wen=1;io_ren=0;io_addr=address;io_data=data;
      @(posedge clock);#1;io_wen=0;
      if((^io_result)!==1'bx)$fatal(1,"write-cycle Q was exposed as logical read");
    end
  endtask
  task automatic read_word(input integer address,input [15:0] data,input bit uninitialized);
    begin
      @(negedge clock);io_wen=0;io_ren=1;io_addr=address;
      @(posedge clock);#1;io_addr=address^384;
      if(uninitialized) begin
        if((^io_result)!==1'bx)$fatal(1,"uninitialized W was assumed known");
        unknown_reads=unknown_reads+1;
      end else if(io_result!==data)$fatal(1,"read/registered depth mismatch addr=%0d expected=%h got=%h",address,data,io_result);
      io_ren=0;
    end
  endtask
  initial begin
    for(depth=0;depth<4;depth=depth+1)read_word(depth*128,0,1);
    for(low=0;low<128;low=low+1)
      for(depth=0;depth<4;depth=depth+1)write_word(depth*128+low,word(depth*128+low));
    for(i=0;i<512;i=i+1)begin
      addr=(197*i+83)&511;read_word(addr,word(addr),0);
    end
    for(i=0;i<8;i=i+1)begin
      addr=boundary(i);write_word(addr,~word(addr));read_word(addr,~word(addr),0);
    end
    repeat(3)@(negedge clock);
    if(writes!=520 || reads!=524 || unknown_reads!=4)$fatal(1,"bank test work count changed");
    $display("XU_PE32_BANK128_PASS logical_words=512 depths=4 writes=520 reads=524 unknown_reads=4 selected_enable=1 latency=1");
    $finish;
  end
endmodule
