`timescale 1ns/1ps
`include "e203_defines.v"
// Actual routing top; legacy compatibility uses the preserved demo as a peer.
module tb_xu_nice_route_wrapper;
  reg nice_clk=0;always #5 nice_clk=~nice_clk;
  reg nice_rst_n=0,nice_req_valid=0,nice_rsp_ready=0;
  reg [31:0] nice_req_inst=0,nice_req_rs1=0,nice_req_rs2=0;
  wire nice_active,nice_mem_holdup,nice_req_ready,nice_rsp_valid,nice_rsp_err;
  wire [31:0] nice_rsp_rdat,nice_icb_cmd_addr,nice_icb_cmd_wdata;
  wire nice_icb_cmd_valid,nice_icb_cmd_read,nice_icb_rsp_ready;
  wire [1:0] nice_icb_cmd_size;
  reg nice_icb_cmd_ready=0,nice_icb_rsp_valid=0,nice_icb_rsp_err=0;
  reg [31:0] nice_icb_rsp_rdata=0;
  e203_subsys_nice_core dut(.*);
  reg compare_legacy=0,no_memory=0;
  wire legacy_ready,legacy_valid,legacy_error,legacy_hold,legacy_cmd,legacy_read,legacy_bus_ready;
  wire [31:0] legacy_data,legacy_addr,legacy_wdata;
  wire [1:0] legacy_size;
  e203_subsys_nice_demo legacy (
    .nice_clk(nice_clk),.nice_rst_n(nice_rst_n),.nice_active(),.nice_mem_holdup(legacy_hold),
    .nice_req_valid(nice_req_valid&&compare_legacy),.nice_req_ready(legacy_ready),
    .nice_req_inst(nice_req_inst),.nice_req_rs1(nice_req_rs1),.nice_req_rs2(nice_req_rs2),
    .nice_rsp_valid(legacy_valid),.nice_rsp_ready(nice_rsp_ready),.nice_rsp_rdat(legacy_data),.nice_rsp_err(legacy_error),
    .nice_icb_cmd_valid(legacy_cmd),.nice_icb_cmd_ready(nice_icb_cmd_ready),
    .nice_icb_cmd_addr(legacy_addr),.nice_icb_cmd_read(legacy_read),.nice_icb_cmd_wdata(legacy_wdata),.nice_icb_cmd_size(legacy_size),
    .nice_icb_rsp_valid(nice_icb_rsp_valid&&compare_legacy),.nice_icb_rsp_ready(legacy_bus_ready),
    .nice_icb_rsp_rdata(nice_icb_rsp_rdata),.nice_icb_rsp_err(nice_icb_rsp_err));
  integer requests=0,completions=0,commands=0,responses=0,unsupported=0,descriptor_errors=0;
  integer legacy_cases=0,drain_cases=0,func3,func7,op,wait_cycles,index;
  reg [31:0] instruction;
  wire [66:0] bus_payload={nice_icb_cmd_addr,nice_icb_cmd_read,nice_icb_cmd_wdata,nice_icb_cmd_size};

  always @(posedge nice_clk) if(nice_rst_n) begin
    if(nice_req_valid&&nice_req_ready) requests=requests+1;
    if(nice_rsp_valid&&nice_rsp_ready) completions=completions+1;
    if(nice_icb_cmd_valid&&nice_icb_cmd_ready) commands=commands+1;
    if(nice_icb_rsp_valid&&nice_icb_rsp_ready) responses=responses+1;
    if(no_memory&&nice_icb_cmd_valid) $fatal(1,"Unsupported/descriptor-error instruction issued memory command");
  end
  always @(negedge nice_clk) begin
    #2;
    if(nice_rst_n&&compare_legacy) begin
      if(nice_icb_cmd_valid!==legacy_cmd || nice_rsp_valid!==legacy_valid || nice_mem_holdup!==legacy_hold)
        $fatal(1,"Legacy top/reference control differs");
      if(nice_icb_cmd_valid&&bus_payload!=={legacy_addr,legacy_read,legacy_wdata,legacy_size})
        $fatal(1,"Legacy top/reference command differs");
      if(nice_rsp_valid&&{nice_rsp_err,nice_rsp_rdat}!=={legacy_error,legacy_data})
        $fatal(1,"Legacy top/reference completion differs");
    end
  end

  function automatic [31:0] lane_data(input integer lane);
    lane_data=32'hf0000011+32'h01020304*lane;
  endfunction
  function automatic [31:0] legacy_word(input integer lane);
    legacy_word=11*(lane+1);
  endfunction
  function automatic [31:0] legacy_stored_word(input integer lane,input integer scale);
    legacy_stored_word=scale*legacy_word(lane);
    // Preserve the original demo's completion-clear behavior: clear also
    // raises rcv_data_buf_valid, replaying the last word into rowbuf[0].
    // The unchanged reference independently checks this same inherited quirk.
    if(scale==2&&lane==0) legacy_stored_word=legacy_stored_word+legacy_word(2);
  endfunction

  task automatic finish_checked(input [31:0] expected_code,input integer stall);
    integer timeout,j;
    begin
      timeout=0;
      while(!nice_rsp_valid&&timeout<16) begin @(negedge nice_clk);timeout=timeout+1;end
      if(!nice_rsp_valid) $fatal(1,"NICE_ROUTE_COMPLETION_TIMEOUT code=%0d owner=%b drain=%b",expected_code,dut.owner_valid,dut.owner_drain);
      repeat(stall+1) begin
        if(!dut.owner_valid || !dut.owner_drain || nice_req_ready || nice_icb_cmd_valid ||
           !nice_rsp_valid || nice_rsp_rdat!==expected_code || nice_rsp_err!==(expected_code!=0))
          $fatal(1,"Checked completion/owner changed under backpressure code=%0d",expected_code);
        @(negedge nice_clk);
      end
      nice_rsp_ready=1;
      @(posedge nice_clk);#2;
      if(dut.owner_valid) $fatal(1,"Checked completion did not release owner");
      @(negedge nice_clk);nice_req_valid=0;nice_rsp_ready=0;nice_req_inst=0;
      no_memory=0;
      #2;
      if(nice_icb_cmd_valid || !nice_req_ready) $fatal(1,"Router did not return to idle");
    end
  endtask

  task automatic checked_error(input [31:0] inst,input [31:0] destination,input [31:0] code);
    integer before_cmd,before_req;
    begin
      before_cmd=commands;before_req=requests;
      @(negedge nice_clk);no_memory=1;nice_req_inst=inst;
      nice_req_rs1=destination;nice_req_rs2=32'h40;nice_req_valid=1;
      nice_rsp_ready=0;nice_icb_cmd_ready=0;
      @(posedge nice_clk);
      if(!nice_req_ready) $fatal(1,"Checked instruction not accepted");
      @(negedge nice_clk);
      // A different pending instruction must not steal the current owner.
      nice_req_inst=32'h0400207b;nice_req_rs1=32'hdeadbeef;nice_req_rs2=0;
      finish_checked(code,unsupported%8);
      if(commands!=before_cmd || requests!=before_req+1 || commands!=responses)
        $fatal(1,"Checked error leaked bus work or accepted another request");
      if(code==1) unsupported=unsupported+1;else descriptor_errors=descriptor_errors+1;
    end
  endtask

  task automatic service_drain(input integer position);
    integer j,lane;
    reg [31:0] address,data,reply;
    reg reading;
    reg [66:0] snapshot;
    begin
      reading=1;data=0;reply=0;
      if(position==0) begin address=32'h100420c4;reply=(3<<6)|3;end
      else if(position<9) begin lane=position-1;address=32'h10042180+4*lane;reply=lane_data(lane);end
      else if(position<16) begin lane=position-9;address=32'ha0020000+4*lane;data=lane_data(lane);reading=0;end
      else if(position==16) begin address=32'h100420c8;data=1;reading=0;end
      else begin address=32'ha002001c;data=lane_data(7);reading=0;end
      if(!nice_icb_cmd_valid || nice_icb_cmd_addr!==address || nice_icb_cmd_read!==reading ||
         nice_icb_cmd_size!==2 || (!reading&&nice_icb_cmd_wdata!==data))
        $fatal(1,"Wrong top-routed drain command position=%0d",position);
      snapshot=bus_payload;
      repeat(1+position%4) begin
        @(negedge nice_clk);
        if(!dut.owner_valid || !dut.owner_drain || nice_req_ready ||
           !nice_icb_cmd_valid || bus_payload!==snapshot || nice_rsp_valid)
          $fatal(1,"Drain owner/command changed under command backpressure");
      end
      nice_icb_cmd_ready=1;
      @(posedge nice_clk);#2;
      @(negedge nice_clk);nice_icb_cmd_ready=0;
      repeat(1+position%3) @(negedge nice_clk);
      nice_icb_rsp_valid=1;nice_icb_rsp_rdata=reply;
      if(!nice_icb_rsp_ready || nice_icb_cmd_valid) $fatal(1,"Drain lost its one outstanding response");
      @(posedge nice_clk);#2;
      @(negedge nice_clk);nice_icb_rsp_valid=0;
    end
  endtask

  task automatic drain_success;
    integer before_cmd,before_req,p;
    begin
      before_cmd=commands;before_req=requests;
      @(negedge nice_clk);nice_req_inst=32'h4000707b;nice_req_rs1=32'ha0020000;
      nice_req_rs2=(2<<5)|3;nice_req_valid=1;nice_rsp_ready=0;
      @(posedge nice_clk);if(!nice_req_ready) $fatal(1,"Drain request not accepted");
      @(negedge nice_clk);nice_req_inst=32'h0200207b;nice_req_rs1=32'hbad00000;
      for(p=0;p<18;p=p+1) service_drain(p);
      finish_checked(0,7);
      if(commands!=before_cmd+18 || responses!=commands || requests!=before_req+1)
        $fatal(1,"Top-routed drain accounting differs");
      drain_cases=drain_cases+1;
    end
  endtask

  task automatic check_legacy_command(input integer operation,input integer lane,input integer scale);
    begin
      if(!nice_icb_cmd_valid || nice_icb_cmd_addr!==32'ha0001000+4*lane ||
         nice_icb_cmd_read!==(operation!=2) || nice_icb_cmd_size!==2 ||
         (operation==2&&nice_icb_cmd_wdata!==legacy_stored_word(lane,scale)))
        $fatal(1,"Legacy command mismatch operation=%0d lane=%0d addr=%h read=%b data=%h reference_data=%h expected=%h requests=%0d completions=%0d",
          operation,lane,nice_icb_cmd_addr,nice_icb_cmd_read,nice_icb_cmd_wdata,legacy_wdata,
          legacy_stored_word(lane,scale),requests,completions);
    end
  endtask
  task automatic legacy_transaction(input integer operation,input integer scale);
    integer before_cmd,before_req,p,timeout;
    begin
      before_cmd=commands;before_req=requests;
      @(negedge nice_clk);compare_legacy=1;nice_req_valid=1;
      nice_rsp_ready=1;nice_icb_cmd_ready=1;nice_req_rs1=32'ha0001000;nice_req_rs2=0;
      case(operation)
        1:nice_req_inst=32'h0200207b;
        2:nice_req_inst=32'h0400207b;
        3:nice_req_inst=32'h0c00607b;
      endcase
      #2;
      @(posedge nice_clk);
      if(!nice_req_ready || dut.request_drain) $fatal(1,"Legacy request not selected");
      check_legacy_command(operation,0,scale);
      @(negedge nice_clk);nice_req_valid=0;nice_icb_cmd_ready=0;
      // A one-outstanding fabric permits command replacement exactly as its
      // preceding response retires. Known legacy withdrawal cases are separate.
      for(p=0;p<2;p=p+1) begin
        repeat(2) @(negedge nice_clk);
        nice_icb_rsp_valid=1;nice_icb_rsp_rdata=legacy_word(p);nice_icb_cmd_ready=1;
        #2;
        @(posedge nice_clk);
        check_legacy_command(operation,p+1,scale);
        if(!nice_icb_rsp_ready) $fatal(1,"Legacy response not consumed");
        @(negedge nice_clk);nice_icb_rsp_valid=0;nice_icb_cmd_ready=0;
      end
      repeat(2) @(negedge nice_clk);
      nice_icb_rsp_valid=1;nice_icb_rsp_rdata=legacy_word(2);
      #2;
      if(operation!=3&&(!nice_rsp_valid||nice_rsp_err||nice_rsp_rdat!==0))
        $fatal(1,"Legacy load/store completion differs");
      @(posedge nice_clk);#2;
      @(negedge nice_clk);nice_icb_rsp_valid=0;
      if(operation==3) begin
        timeout=0;
        while(!nice_rsp_valid&&timeout<8) begin @(negedge nice_clk);timeout=timeout+1;end
        if(!nice_rsp_valid || nice_rsp_err || nice_rsp_rdat!==66)
          $fatal(1,"Legacy rowsum completion differs got=%h",nice_rsp_rdat);
        @(posedge nice_clk);#2;
        @(negedge nice_clk);
      end
      compare_legacy=0;nice_rsp_ready=0;nice_req_inst=0;
      if(dut.owner_valid || commands!=before_cmd+3 || responses!=commands || requests!=before_req+1)
        $fatal(1,"Legacy owner/accounting mismatch operation=%0d",operation);
      legacy_cases=legacy_cases+1;
      $display("NICE_ROUTE_LEGACY_COMPAT_PASS operation=%0d commands=3 completion_ready=1",operation);
    end
  endtask

  initial begin
    repeat(3) @(negedge nice_clk);nice_rst_n=1;
    legacy_transaction(1,1);legacy_transaction(2,1);legacy_transaction(3,1);
    checked_error(32'h0000707b,32'ha0020000,1);
    drain_success();
    checked_error(32'h4000707b,32'ha0020004,2);
    for(func7=0;func7<128;func7=func7+1)
      for(func3=0;func3<8;func3=func3+1) begin
        instruction=(func7<<25)|(func3<<12)|32'h7b;
        if(instruction!=32'h0200207b && instruction!=32'h0400207b &&
           instruction!=32'h0c00607b && instruction!=32'h4000707b && instruction!=32'h0000707b)
          checked_error(instruction,32'ha0020000,1);
      end
    for(op=0;op<4;op=op+1) begin
      case(op)
        0:instruction=32'h4000700b;
        1:instruction=32'h4000702b;
        2:instruction=32'h4000705b;
        3:instruction=32'h4000707f;
      endcase
      checked_error(instruction,32'ha0020000,1);
    end
    legacy_transaction(2,2); // retained demo state survived checked/drain work
    if(unsupported!=1024 || descriptor_errors!=1 || legacy_cases!=4 || drain_cases!=1 ||
       requests!=1030 || completions!=requests || commands!=30 || responses!=commands)
      $fatal(1,"Final route accounting wrong unsupported=%0d requests=%0d completions=%0d commands=%0d responses=%0d",
        unsupported,requests,completions,commands,responses);
    $display("XU_NICE_ROUTE_WRAPPER_PASS unsupported=1024 descriptor_errors=1 legacy=4 drain=1 requests=1030 completions=1030 commands=30 responses=30");
    $finish;
  end
  initial begin #2000000;$fatal(1,"Nice routing global timeout");end
endmodule
