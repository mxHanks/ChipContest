`timescale 1ns/1ps
module tb_xu_uart_path;
  reg clk=0,corerst=0,test_mode=0;
  always #5 clk=~clk;
  reg cmd_valid=0,cmd_read=0,rsp_ready=1,rx_i=1;
  reg [31:0] cmd_addr=32'h10013000,cmd_wdata=0;
  reg [3:0] cmd_wmask=4'hf;
  wire cmd_ready,rsp_valid,rsp_err,tx_o,event_o,main_rst_n;
  wire [31:0] rsp_rdata;
  xu_uart_boundary dut(.*);
  reg [7:0] xu_invalid_data=8'hxx;
  reg [31:0] poison_rng=32'hd00dbeef;
  wire shadow_cmd_ready,shadow_rsp_valid,shadow_rsp_err,shadow_tx_o,shadow_event_o,shadow_main_rst_n;
  wire [31:0] shadow_rsp_rdata;
  xu_counterfactual_boundary shadow(
    .clk(clk),.corerst(corerst),.test_mode(test_mode),.cmd_valid(cmd_valid),.cmd_read(cmd_read),
    .cmd_addr(cmd_addr),.cmd_wdata(cmd_wdata),.cmd_wmask(cmd_wmask),.rsp_ready(rsp_ready),.rx_i(rx_i),
    .cmd_ready(shadow_cmd_ready),.rsp_valid(shadow_rsp_valid),.rsp_err(shadow_rsp_err),
    .rsp_rdata(shadow_rsp_rdata),.tx_o(shadow_tx_o),.event_o(shadow_event_o),
    .main_rst_n(shadow_main_rst_n),.xu_invalid_data(xu_invalid_data));
  integer cycles=0,requests=0,writes=0,dlab_writes=0,full_drops=0,clears=0;
  integer invalid_cycles=0,stalls=0,rsp_stalls=0,continuous=0,resets=0,unknown_closed=0;
  integer back_to_back_commands=0,poison_changes=0;
  integer release_edges=0,release_checks=0;
  reg release_pending=1;
  reg [31:0] rng=32'h9e3779b9;
  integer rsp_mode=1;
  reg previous_stalled=0,previous_accepted=0;
  reg [68:0] previous_payload;
  integer ref_elements=0,ref_in=0,ref_out=0;
  reg [7:0] ref_buffer[0:15];
  integer i,j,put,pop,clr;
  reg [3:0] address_choice;
  function [31:0] random_word;
    begin rng=rng*32'd1664525+32'd1013904223;random_word=rng;end
  endfunction
  always @(negedge clk) begin
    if(cycles>45)begin
      poison_rng=poison_rng*32'd1664525+32'd1013904223;
      xu_invalid_data=poison_rng[23:16];poison_changes=poison_changes+1;
    end
    if(rsp_mode==0) rsp_ready=0;
    else if(rsp_mode==1) rsp_ready=1;
    else rsp_ready=(random_word()%5)!=0;
  end
  always @(negedge main_rst_n) begin
    ref_elements=0;ref_in=0;ref_out=0;
    for(j=0;j<16;j=j+1) ref_buffer[j]=0;
    previous_stalled=0;previous_accepted=0;resets=resets+1;
  end
  always @(negedge corerst)begin release_edges=0;release_pending=1;end
  always @(posedge clk) begin
    cycles=cycles+1;
    if(!corerst && main_rst_n===1'b0)release_edges=release_edges+1;
    if(cycles>30000) $fatal(1,"watchdog requests=%0d valid=%b ready=%b rspvalid=%b rspready=%b rst=%b mode=%0d rng=%h",requests,cmd_valid,cmd_ready,rsp_valid,rsp_ready,main_rst_n,rsp_mode,rng);
    if(main_rst_n===1'b1) begin
      if(previous_stalled && (!cmd_valid || {cmd_read,cmd_addr,cmd_wdata,cmd_wmask}!==previous_payload))
        $fatal(1,"illegal stimulus changed a stalled ICB request cycle=%0d",cycles);
      previous_stalled=cmd_valid&&!cmd_ready;
      previous_payload={cmd_read,cmd_addr,cmd_wdata,cmd_wmask};
      if(cmd_valid&&cmd_ready) begin requests=requests+1;if(previous_accepted)continuous=continuous+1;end
      previous_accepted=cmd_valid&&cmd_ready;
      if(cmd_valid&&!cmd_ready) stalls=stalls+1;
      if(rsp_valid&&!rsp_ready) rsp_stalls=rsp_stalls+1;
      if(rsp_err!==1'b0) $fatal(1,"unexpected response error");
      if(dut.uart.uart_tx_fifo_i.elements!==ref_elements[4:0] ||
         dut.uart.uart_tx_fifo_i.pointer_in!==ref_in[3:0] ||
         dut.uart.uart_tx_fifo_i.pointer_out!==ref_out[3:0])
        $fatal(1,"FIFO control mismatch cycle=%0d",cycles);
      put=dut.uart.fifo_tx_valid && ref_elements!=16;
      pop=dut.uart.tx_ready && ref_elements!=0;
      clr=dut.uart.tx_fifo_clr_q;
      if(dut.uart.fifo_tx_valid !== (cmd_valid&&cmd_ready&&!cmd_read&&cmd_addr[4:2]==0&&!dut.uart.regs_q[31]))
        $fatal(1,"TX valid is not exactly an accepted non-DLAB THR write cycle=%0d",cycles);
      if(dut.uart.fifo_tx_valid) begin
        if(!(cmd_valid&&cmd_ready&&!cmd_read&&cmd_addr[4:2]==0&&!dut.uart.regs_q[31]))
          $fatal(1,"FIFO valid without current accepted THR request cycle=%0d",cycles);
        if(dut.uart.fifo_tx_data!==cmd_wdata[7:0])
          $fatal(1,"FIFO sampled stale byte cycle=%0d",cycles);
        if(ref_elements==16) full_drops=full_drops+1;
      end else begin
        invalid_cycles=invalid_cycles+1;
        if((^dut.uart.fifo_tx_data)===1'bx) unknown_closed=unknown_closed+1;
      end
      if(cmd_valid&&cmd_ready&&!cmd_read&&cmd_addr[4:2]==0&&dut.uart.regs_q[31])begin
        dlab_writes=dlab_writes+1;
        if(dut.uart.fifo_tx_valid!==0) $fatal(1,"DLAB write entered TX FIFO");
      end
      // Mirror the actual FIFO's documented corner: clear resets pointers and
      // occupancy, but its memory write is still valid_i&&!full on that edge.
      if(put)begin ref_buffer[ref_in]=cmd_wdata[7:0];writes=writes+1;end
      if(clr)begin ref_elements=0;ref_in=0;ref_out=0;clears=clears+1;end
      else begin
        ref_elements=ref_elements+put-pop;
        if(put)ref_in=(ref_in+1)%16;
        if(pop)ref_out=(ref_out+1)%16;
      end
    end else if(main_rst_n===1'b0) begin
      ref_elements=0;ref_in=0;ref_out=0;
      for(i=0;i<16;i=i+1)ref_buffer[i]=0;
      previous_stalled=0;previous_accepted=0;
    end
    #2;
    if(!corerst && main_rst_n===1'b1 && release_pending)begin
      if(release_edges!=20)$fatal(1,"reset catch released after %0d edges instead of real 20-stage chain",release_edges);
      release_pending=0;release_checks=release_checks+1;
    end
    if({cmd_ready,rsp_valid,rsp_err,rsp_rdata,tx_o,event_o,main_rst_n} !==
       {shadow_cmd_ready,shadow_rsp_valid,shadow_rsp_err,shadow_rsp_rdata,shadow_tx_o,shadow_event_o,shadow_main_rst_n})
      $fatal(1,"invalid-data counterfactual changed UART boundary observable cycle=%0d",cycles);
    if(dut.uart.regs_q !== shadow.uart.regs_q)
      $fatal(1,"invalid-data counterfactual changed UART register state cycle=%0d",cycles);
    if(main_rst_n===1'b1 || main_rst_n===1'b0)begin
      for(i=0;i<16;i=i+1)
        if(dut.uart.uart_tx_fifo_i.buffer[i]!==ref_buffer[i] || shadow.uart.uart_tx_fifo_i.buffer[i]!==ref_buffer[i])
          $fatal(1,"FIFO memory mismatch cycle=%0d slot=%0d expected=%h actual=%h",cycles,i,ref_buffer[i],dut.uart.uart_tx_fifo_i.buffer[i]);
    end
  end
  task issue(input reg rd,input reg [2:0] adr,input reg [31:0] value);
    begin
      @(negedge clk);if(cmd_valid)back_to_back_commands=back_to_back_commands+1;
      cmd_valid=1;cmd_read=rd;cmd_addr=32'h10013000+{27'b0,adr,2'b0};cmd_wdata=value;cmd_wmask=4'hf;
      @(posedge clk);while(!cmd_ready)@(posedge clk);
    end
  endtask
  task idle(input integer n);
    begin @(negedge clk);cmd_valid=0;repeat(n)@(posedge clk);end
  endtask
  task reset_system;
    begin
      @(negedge clk);corerst=1;cmd_valid=0;
      repeat(3)@(posedge clk);
      @(negedge clk);corerst=0;
      wait(main_rst_n===1'b1);repeat(2)@(posedge clk);
    end
  endtask
  initial begin
    if($value$plusargs("SEED=%d",rng))begin end
    #1 corerst=1;
    repeat(3)@(posedge clk);@(negedge clk);corerst=0;
    wait(main_rst_n===1'b1);repeat(3)@(posedge clk);
    // Real divisor programming makes the transmitter busy. Never force ready,
    // FIFO occupancy, state, reset catch or the data latch.
    issue(0,3,32'h80);issue(0,0,32'hff);issue(0,1,32'hff);issue(0,3,32'h03);
    for(integer k=0;k<26;k=k+1)issue(0,0,32'h100+k);
    issue(1,5,0);issue(0,2,4);idle(4);
    if(full_drops<5) $fatal(1,"full FIFO path not reached");
    // Hold response while a following request waits, then use the real common
    // reset source to cancel both channels and both peripheral reset domains.
    rsp_mode=0;issue(0,0,32'ha5);
    @(negedge clk);cmd_valid=1;cmd_addr=32'h10013000;cmd_wdata=32'h5a;
    repeat(2)@(posedge clk);
    @(negedge clk);if($test$plusargs("XU_CORRUPT_STALLED"))cmd_wdata=cmd_wdata^1;
    repeat(3)@(posedge clk);reset_system();rsp_mode=2;
    for(integer k=0;k<400;k=k+1)begin
      address_choice=random_word()%8;
      issue((random_word()%4)==0,address_choice[2:0],random_word());
      if(k%79==78)reset_system();
      else if(k%13==12)idle(random_word()%4);
    end
    idle(30);
    if(writes<20||dlab_writes<2||clears<2||stalls<20||rsp_stalls<4||resets<3||unknown_closed<1||back_to_back_commands<100||poison_changes<100||release_checks!=7)
      $fatal(1,"coverage incomplete writes=%0d dlab=%0d clears=%0d stalls=%0d rspstalls=%0d resets=%0d unknown=%0d",writes,dlab_writes,clears,stalls,rsp_stalls,resets,unknown_closed);
    $display("XU_UART_REAL_SOURCE_PASS cycles=%0d requests=%0d writes=%0d full_drops=%0d dlab_writes=%0d clears=%0d stalls=%0d response_stalls=%0d reset_assertions=%0d invalid_cycles=%0d initial_unknown_closed=%0d back_to_back_commands=%0d poison_changes=%0d reset20_checks=%0d",cycles,requests,writes,full_drops,dlab_writes,clears,stalls,rsp_stalls,resets,invalid_cycles,unknown_closed,back_to_back_commands,poison_changes,release_checks);
    $finish;
  end
endmodule
