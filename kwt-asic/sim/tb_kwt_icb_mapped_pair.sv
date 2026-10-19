`timescale 1ns/1ps
// Compare actual standard-cell mapped logic with the RTL under the SAME
// requests and explicit logical SRAM contract. No precomputed result enters
// either DUT: golden is read only by the output scoreboard.
module tb_kwt_icb_mapped_pair;
  reg clk=0,rst_n=0;
  always #5 clk=~clk;
  reg valid=0,read_cmd=0,ready_rsp=0;
  reg [31:0] address=0,wdata=0;
  reg [3:0] mask=0;
  wire ready0,ready1,rsp0,rsp1,error0,error1;
  wire [31:0] data0,data1;
  integer tasks=1,outputs=0,transactions=0,cycles=0,holds=0;
  integer errors=0,soft_aborts=0,pending_resets=0,final_hi_holds=0,ack_holds=0;
  wire [31:0] trace_checks,accepted_commands,accepted_responses;
  // ABC leaves an undriven, unused engine_y_ready name in mapped.v. Observe
  // the retained rsp_pop_y FF and the real external handshake instead; actual
  // output_count transitions below prove that the retirement committed.
  wire mapped_retire = rst_n && rsp1 && ready_rsp && !error1 && mapped_dut.rsp_pop_y;
  string vectors,file_name;
  reg [15:0] xv[0:6335],wv[0:16383];
  reg [39:0] bias[0:255];
  reg [47:0] golden[0:25343];
  reg [31:0] value,lo,hi;
  kwt_icb_slave_sram #(.SRAM_BACKEND(0)) reference_dut
    (.clk(clk),.rst_n(rst_n),.icb_cmd_valid(valid),.icb_cmd_ready(ready0),
     .icb_cmd_addr(address),.icb_cmd_read(read_cmd),.icb_cmd_wdata(wdata),.icb_cmd_wmask(mask),
     .icb_rsp_valid(rsp0),.icb_rsp_ready(ready_rsp),.icb_rsp_rdata(data0),.icb_rsp_err(error0));
  kwt_icb_slave_sram_mapped mapped_dut
    (.clk(clk),.rst_n(rst_n),.icb_cmd_valid(valid),.icb_cmd_ready(ready1),
     .icb_cmd_addr(address),.icb_cmd_read(read_cmd),.icb_cmd_wdata(wdata),.icb_cmd_wmask(mask),
     .icb_rsp_valid(rsp1),.icb_rsp_ready(ready_rsp),.icb_rsp_rdata(data1),.icb_rsp_err(error1));
  kwt_icb_pair_checker checker_i
    (.clk(clk),.rst_n(rst_n),.cmd_valid(valid),.rsp_ready(ready_rsp),
     .ready0(ready0),.ready1(ready1),.rsp0(rsp0),.rsp1(rsp1),
     .error0(error0),.error1(error1),.data0(data0),.data1(data1),
     .trace_checks(trace_checks),.accepted_commands(accepted_commands),.accepted_responses(accepted_responses));
  always @(posedge clk) begin
    cycles=cycles+1;
    if(cycles>100000000) $fatal(1,"mapped pair watchdog");
  end
  task automatic xfer(input [11:0] offset,input bit reading,input [31:0] payload,
                      input integer hold_cycles,input bit want_error,output [31:0] result);
    integer count;
    reg [31:0] held;
    reg [14:0] held_count;
    reg want_pop;
    begin
      @(negedge clk);#1;address=32'h10042000+{20'b0,offset};read_cmd=reading;
      wdata=payload;mask=4'hf;valid=1;ready_rsp=0;
      count=0;
      do begin @(posedge clk);count=count+1;if(count>1000)$fatal(1,"mapped command timeout");end while(ready0!==1'b1 || ready1!==1'b1);
      @(negedge clk);#1;valid=0;
      if(rsp0!==1'b1 || rsp1!==1'b1 || error0!==want_error || error1!==want_error ||
         data0!==data1 || (^data0===1'bx)) $fatal(1,"mapped transaction response mismatch offset=%h",offset);
      held=data0;held_count=reference_dut.output_count;
      want_pop=reading && offset==12'h044 && !want_error;
      repeat(hold_cycles) begin
        @(posedge clk);@(negedge clk);#1;
        if(rsp0!==1'b1 || rsp1!==1'b1 || ready0!==1'b0 || ready1!==1'b0 ||
           error0!==want_error || error1!==want_error || data0!==held || data1!==held)
          $fatal(1,"mapped response backpressure stability");
        if(reference_dut.engine_y_ready!==1'b0 || mapped_retire!==1'b0 ||
           reference_dut.output_count!==held_count || mapped_dut.output_count!==held_count)
          $fatal(1,"mapped premature output pop");
        if(want_pop && reference_dut.y_snapshot_last &&
           (reference_dut.core_done_sticky!==1'b0 || mapped_dut.core_done_sticky!==1'b0 ||
            reference_dut.engine_busy!==1'b1 || mapped_dut.engine_busy!==1'b1))
          $fatal(1,"mapped premature final HI completion");
        if(!want_error && !reading && offset==12'h008 && payload==2 &&
           (reference_dut.software_done!==1'b0 || mapped_dut.software_done!==1'b0 ||
            reference_dut.window_active!==1'b1 || mapped_dut.window_active!==1'b1))
          $fatal(1,"mapped premature ACK completion");
        holds=holds+1;
      end
      result=held;ready_rsp=1;#1;
      if(reference_dut.engine_y_ready!==want_pop || mapped_retire!==want_pop)
        $fatal(1,"mapped retirement intent offset=%h expected=%b ref=%b mapped=%b",offset,want_pop,reference_dut.engine_y_ready,mapped_retire);
      @(posedge clk);@(negedge clk);#1;ready_rsp=0;
      if(rsp0!==1'b0 || rsp1!==1'b0 || reference_dut.output_count!==held_count+15'(want_pop) ||
         mapped_dut.output_count!==held_count+15'(want_pop))$fatal(1,"mapped retirement/pop count");
      transactions=transactions+1;
    end
  endtask
  task automatic wr(input [11:0] offset,input [31:0] payload);
    reg [31:0] ignored;
    begin xfer(offset,0,payload,0,0,ignored);end
  endtask
  task automatic rd(input [11:0] offset,output [31:0] payload);
    begin xfer(offset,1,0,0,0,payload);end
  endtask
  task automatic bad(input [11:0] offset,input bit reading,input [31:0] payload,input [7:0] code);
    reg [31:0] ignored;
    begin
      xfer(offset,reading,payload,2,1,ignored);
      if(ignored!==0)$fatal(1,"mapped error response not zero");
      rd(12'h00c,ignored);if(ignored[7:0]!==code)$fatal(1,"mapped error code");
      errors=errors+1;
    end
  endtask
  task automatic load_images(input integer task_id);
    integer fd;
    begin
      for(integer j=0;j<6336;j=j+1)xv[j]='x;
      for(integer j=0;j<16384;j=j+1)wv[j]='x;
      for(integer j=0;j<256;j=j+1)bias[j]='x;
      for(integer j=0;j<25344;j=j+1)golden[j]='x;
      // The runner separately validates exact word counts, widths and SHA.
      file_name=$sformatf("%s/layer_%02d/x.mem",vectors,task_id);
      fd=$fopen(file_name,"r");if(!fd)$fatal(1,"mapped x missing");$fclose(fd);$readmemh(file_name,xv);
      file_name=$sformatf("%s/layer_%02d/w.mem",vectors,task_id);
      fd=$fopen(file_name,"r");if(!fd)$fatal(1,"mapped w missing");$fclose(fd);$readmemh(file_name,wv);
      file_name=$sformatf("%s/layer_%02d/bias.mem",vectors,task_id);
      fd=$fopen(file_name,"r");if(!fd)$fatal(1,"mapped bias missing");$fclose(fd);$readmemh(file_name,bias);
      file_name=$sformatf("%s/layer_%02d/y.mem",vectors,task_id);
      fd=$fopen(file_name,"r");if(!fd)$fatal(1,"mapped y missing");$fclose(fd);$readmemh(file_name,golden);
      for(integer j=0;j<6336;j=j+1)if(^xv[j]===1'bx)$fatal(1,"mapped unknown x");
      for(integer j=0;j<16384;j=j+1)if(^wv[j]===1'bx)$fatal(1,"mapped unknown w");
      for(integer j=0;j<256;j=j+1)if(^bias[j]===1'bx)$fatal(1,"mapped unknown bias");
      for(integer j=0;j<25344;j=j+1)if(^golden[j]===1'bx)$fatal(1,"mapped unknown golden");
    end
  endtask
  task automatic load_full_payload;
    begin
      wr(12'h020,0);wr(12'h024,0);
      for(integer j=0;j<6336;j=j+1)begin wr(12'h028,{16'b0,xv[j]});wr(12'h030,1);end
      wr(12'h020,1);wr(12'h024,0);
      for(integer j=0;j<16384;j=j+1)begin wr(12'h028,{16'b0,wv[j]});wr(12'h030,1);end
      wr(12'h020,2);wr(12'h024,0);
      for(integer j=0;j<256;j=j+1)begin
        wr(12'h028,bias[j][31:0]);wr(12'h02c,{24'b0,bias[j][39:32]});wr(12'h030,1);
      end
    end
  endtask
  task automatic pending_reset;
    begin
      // Cancel a real pending HI response; no output is retired in this epoch.
      rd(12'h004,value);while((value&8)==0)rd(12'h004,value);
      rd(12'h040,lo);
      @(negedge clk);#1;address=32'h10042044;read_cmd=1;mask=0;valid=1;ready_rsp=0;
      do @(posedge clk);while(ready0!==1'b1 || ready1!==1'b1);
      @(negedge clk);#1;valid=0;
      if(rsp0!==1'b1 || rsp1!==1'b1 || error0!==1'b0 || error1!==1'b0)
        $fatal(1,"mapped pending reset precondition");
      repeat(3)begin
        @(posedge clk);@(negedge clk);#1;
        if(rsp0!==1'b1 || rsp1!==1'b1 || reference_dut.output_count!==0 || mapped_dut.output_count!==0)
          $fatal(1,"mapped pending HI consumed early");
      end
      rst_n=0;#1;
      if(rsp0!==1'b0 || rsp1!==1'b0 || ready0!==1'b0 || ready1!==1'b0 ||
         reference_dut.engine_y_ready!==1'b0 || mapped_retire!==1'b0)
        $fatal(1,"mapped reset pending validity");
      repeat(3)@(negedge clk);#1;rst_n=1;
      rd(12'h004,value);if(value!==2)$fatal(1,"mapped hard reset state");
      bad(12'h008,0,1,5);pending_resets=pending_resets+1;
    end
  endtask
  initial begin
    if(!$value$plusargs("VECTORS=%s",vectors))$fatal(1,"mapped vectors missing");
    if($value$plusargs("TASKS=%d",tasks))begin end
    if(tasks<1 || tasks>12)$fatal(1,"mapped tasks invalid");
    repeat(4)@(negedge clk);#1;rst_n=1;
    rd(12'h000,value);if(value!==32'h4b575431)$fatal(1,"mapped ID");
    bad(12'h005,1,0,1);bad(12'h000,0,1,2);bad(12'h034,1,0,2);
    bad(12'h008,0,1,5);bad(12'h030,0,1,8);bad(12'h044,1,0,10);
    bad(12'h040,1,0,9);bad(12'h008,0,2,11);
    load_images(0);load_full_payload();wr(12'h008,1);
    bad(12'h008,0,1,5);bad(12'h028,0,0,5);
    rd(12'h004,value);
    if(value[0]!==1'b1 || reference_dut.engine_busy!==1'b1 || mapped_dut.engine_busy!==1'b1 ||
       reference_dut.output_count!==0 || mapped_dut.output_count!==0)
      $fatal(1,"mapped busy abort precondition");
    wr(12'h008,4);rd(12'h004,value);if(value!==2)$fatal(1,"mapped soft abort state");
    bad(12'h008,0,1,5);soft_aborts=soft_aborts+1;
    load_full_payload();wr(12'h008,1);pending_reset();
    $display("MAPPED_RECOVERY_PASS soft_aborts=%0d pending_resets=%0d",soft_aborts,pending_resets);$fflush();
    for(integer task_id=0;task_id<tasks;task_id=task_id+1)begin
      load_images(task_id);load_full_payload();wr(12'h008,1);
      for(integer j=0;j<25344;j=j+1)begin
        rd(12'h004,value);while(!(value&8))rd(12'h004,value);
        rd(12'h048,value);
        if(value!==(32'(j)|((j==25343)?32'h80000000:0)))$fatal(1,"mapped output index/last");
        xfer(12'h040,1,0,(j%257==0 || j==25343)?3:0,0,lo);
        xfer(12'h044,1,0,(j==25343)?9:((j%257==0)?5:0),0,hi);
        if({hi[15:0],lo}!==golden[j] || hi[31:16]!==0)
          $fatal(1,"mapped Golden mismatch task=%0d index=%0d",task_id,j);
        outputs=outputs+1;
        if(j==25343)final_hi_holds=final_hi_holds+1;
      end
      rd(12'h014,value);if(value!==25344)$fatal(1,"mapped output count");
      rd(12'h004,value);if((value&32'he9)!==32'h20)$fatal(1,"mapped final core state");
      xfer(12'h008,0,2,7,0,value);ack_holds=ack_holds+1;
      rd(12'h004,value);if((value&32'h440)!==32'h40)$fatal(1,"mapped software done");
      $display("MAPPED_TASK_PASS task=%0d outputs=25344",task_id);$fflush();
    end
    if(accepted_responses!==32'(transactions) || accepted_commands!==accepted_responses+1)
      $fatal(1,"mapped actual handshake conservation");
    $display("MAPPED_PROTOCOL_PASS errors=%0d holds=%0d final_hi=%0d ack=%0d requests=%0d responses=%0d",
      errors,holds,final_hi_holds,ack_holds,accepted_commands,accepted_responses);$fflush();
    $display("MAPPED_PAIR_PASS tasks=%0d outputs=%0d transactions=%0d trace_checks=%0d",tasks,outputs,transactions,trace_checks);$fflush();
    $finish;
  end
endmodule
