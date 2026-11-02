
`timescale 1ns/1ps
module tb_xu_task_clear_protocol;
  reg clk=0, rst_n=0, cmd_valid=0, cmd_read=0, rsp_ready=0;
  always #5 clk=~clk;
  reg [31:0] cmd_addr=0, cmd_wdata=0;
  reg [3:0] cmd_wmask=0;
  wire cmd_ready, rsp_valid, rsp_err;
  wire [31:0] rsp_rdata;
  accel_icb_slave dut(.*);
  reg source_request=0, payload_phase=0;
  integer bank, a, lane, polls, mode=0, accepted=0, retired=0;
  reg [31:0] response;
  reg [39:0] bias_value;
  reg [47:0] expected;

  // xu passive clear observer: no force, no DUT assignment, no task payload.
  integer xu_task_setup_writes=0;
  integer xu_clear_writes=0, xu_clear_w_count=0, xu_clear_bias_count=0;
  integer xu_clear_legacy_count=0, xu_clear_x_count=0, xu_clear_disable_count=0;
  reg [16383:0] xu_clear_w_seen=0;
  reg [63:0] xu_clear_x_seen=0;
  reg [4:0] xu_clear_bias_seen [0:255];
  reg [4:0] xu_clear_legacy_seen [0:7];
  reg xu_clear_complete=0;
  integer xu_clear_init;
  initial begin
    for (xu_clear_init=0;xu_clear_init<256;xu_clear_init=xu_clear_init+1)
      xu_clear_bias_seen[xu_clear_init]=0;
    for (xu_clear_init=0;xu_clear_init<8;xu_clear_init=xu_clear_init+1)
      xu_clear_legacy_seen[xu_clear_init]=0;
  end

  task xu_observe_task_clear;
    input source_request;
    output payload_phase;
    integer a;
    reg [4:0] old_mask, new_mask;
    begin
      if (!xu_clear_complete) begin
        if (dut.cache_enable!==1'b0 || dut.busy!==1'b0 ||
            dut.core_start!==1'b0)
          $fatal(1,"XU_CLEAR_REJECT non-idle/enabled clear phase");
        if (source_request) begin
          if (xu_clear_writes!=33697 || xu_clear_disable_count!=1 ||
              xu_clear_w_count!=16384 || xu_clear_bias_count!=256 ||
              xu_clear_legacy_count!=8 || xu_clear_x_count!=64)
            $fatal(1,"XU_CLEAR_REJECT incomplete clear before first source request");
          // W/X stores are committed one clock after MMIO acceptance.
          if (dut.w_load_wen!==1'b0 || dut.x_load_wen!==1'b0 || dut.rsp_valid!==1'b0)
            $fatal(1,"XU_CLEAR_REJECT undrained W/X clear strobe");
          if (xu_task_setup_writes!=2)
            $fatal(1,"XU_CLEAR_REJECT missing original task destination setup before source request");
          xu_clear_complete=1;
          $display("XU_TASK_CLEAR_OBSERVED writes=33697 w=16384 bias=256 legacy_bias=8 x=64 drained=1 cache_enable=0 idle=1 source_request=1 task_setup_writes=2");
        end else if (dut.cmd_valid && dut.cmd_ready) begin
          if (dut.cmd_read) begin
            if (dut.cmd_addr[11:0]!=12'h000 &&
                dut.cmd_addr[11:0]!=12'h00c &&
                dut.cmd_addr[11:0]!=12'h050)
              $fatal(1,"XU_CLEAR_REJECT unexpected pretask MMIO read");
          end else if (xu_clear_writes==33697 && xu_clear_w_count==16384 &&
                       xu_clear_bias_count==256 && xu_clear_legacy_count==8 &&
                       xu_clear_x_count==64 && xu_clear_disable_count==1) begin
            if (dut.cmd_wmask!==4'hf || dut.cmd_wdata!==32'b0 ||
                !((xu_task_setup_writes==0 && dut.cmd_addr[11:0]==12'h01c) ||
                  (xu_task_setup_writes==1 && dut.cmd_addr[11:0]==12'h020)))
              $fatal(1,"XU_CLEAR_REJECT unexpected task data/setup before first source request");
            xu_task_setup_writes=xu_task_setup_writes+1;
          end else begin
            if (dut.cmd_wmask!==4'hf ||
                (^dut.cmd_wdata)===1'bx)
              $fatal(1,"XU_CLEAR_REJECT incomplete/unknown clear word");
            xu_clear_writes=xu_clear_writes+1;
            case (dut.cmd_addr[11:0])
              12'h040: begin
                if (dut.cmd_wdata!==32'b0 || xu_clear_disable_count!=0)
                  $fatal(1,"XU_CLEAR_REJECT cache disable");
                xu_clear_disable_count=xu_clear_disable_count+1;
              end
              12'h01c: if (dut.cmd_wdata>7)
                $fatal(1,"XU_CLEAR_REJECT W bank");
              12'h020: if (dut.cmd_wdata>2047)
                $fatal(1,"XU_CLEAR_REJECT W address");
              12'h044: if (dut.cmd_wdata>255)
                $fatal(1,"XU_CLEAR_REJECT bias address");
              12'h028: if (dut.cmd_wdata>7)
                $fatal(1,"XU_CLEAR_REJECT legacy bias address");
              12'h014: if (dut.cmd_wdata>63)
                $fatal(1,"XU_CLEAR_REJECT X address");
              12'h024: begin
                if ((^{dut.w_bank_reg,dut.w_addr_reg})===1'bx)
                  $fatal(1,"XU_CLEAR_REJECT unknown W destination");
                a=dut.w_bank_reg*2048+dut.w_addr_reg;
                if (dut.cmd_wdata!==32'b0 || xu_clear_w_seen[a])
                  $fatal(1,"XU_CLEAR_REJECT nonzero/duplicate W clear");
                xu_clear_w_seen[a]=1;
                xu_clear_w_count=xu_clear_w_count+1;
              end
              12'h018: begin
                if ((^dut.x_addr_reg)===1'bx)
                  $fatal(1,"XU_CLEAR_REJECT unknown X destination");
                a=dut.x_addr_reg;
                if (dut.cmd_wdata!==32'b0 || xu_clear_x_seen[a])
                  $fatal(1,"XU_CLEAR_REJECT nonzero/duplicate X clear");
                xu_clear_x_seen[a]=1;
                xu_clear_x_count=xu_clear_x_count+1;
              end
              12'h048,12'h04c,12'h02c,12'h030: begin
                if (dut.cmd_wdata!==32'b0)
                  $fatal(1,"XU_CLEAR_REJECT nonzero bias clear");
                if (dut.cmd_addr[11:0]==12'h048 ||
                    dut.cmd_addr[11:0]==12'h04c) begin
                  if ((^dut.cache_addr_reg)===1'bx)
                    $fatal(1,"XU_CLEAR_REJECT unknown bias destination");
                  a=dut.cache_addr_reg;
                  old_mask=xu_clear_bias_seen[a];
                end else begin
                  if ((^dut.bias_index_reg)===1'bx)
                    $fatal(1,"XU_CLEAR_REJECT unknown legacy bias destination");
                  a=dut.bias_index_reg;
                  old_mask=xu_clear_legacy_seen[a];
                end
                if (dut.cmd_addr[11:0]==12'h048 ||
                    dut.cmd_addr[11:0]==12'h02c) begin
                  if (old_mask[3:0]!=0)
                    $fatal(1,"XU_CLEAR_REJECT duplicate bias low clear");
                  new_mask=old_mask|5'b01111;
                end else begin
                  if (old_mask[4])
                    $fatal(1,"XU_CLEAR_REJECT duplicate bias high clear");
                  new_mask=old_mask|5'b10000;
                end
                if (dut.cmd_addr[11:0]==12'h048 ||
                    dut.cmd_addr[11:0]==12'h04c) begin
                  xu_clear_bias_seen[a]=new_mask;
                  if (new_mask==5'b11111) xu_clear_bias_count=xu_clear_bias_count+1;
                end else begin
                  xu_clear_legacy_seen[a]=new_mask;
                  if (new_mask==5'b11111) xu_clear_legacy_count=xu_clear_legacy_count+1;
                end
              end
              default: $fatal(1,"XU_CLEAR_REJECT unexpected pretask MMIO write");
            endcase
          end
        end
      end
      payload_phase=xu_clear_complete;
    end
  endtask

  always @(posedge clk) if (rst_n) begin
    xu_observe_task_clear(source_request,payload_phase);
    if (cmd_valid && cmd_ready) accepted=accepted+1;
    if (rsp_valid && rsp_ready) retired=retired+1;
  end

  // The target stalls each response for one cycle; the driver checks stability.
  task automatic transfer(input bit read_access, input [11:0] address,
                          input [31:0] data, input [3:0] mask,
                          output [31:0] word);
    reg [31:0] held;
    begin
      @(negedge clk);
      cmd_valid=1; cmd_read=read_access; cmd_addr={20'h10042,address};
      cmd_wdata=data; cmd_wmask=mask; rsp_ready=0;
      @(posedge clk);
      if (!cmd_ready) $fatal(1,"probe driver unexpected blocked command");
      #1;
      if (!rsp_valid || rsp_err) $fatal(1,"probe driver missing/error response");
      held=rsp_rdata;
      @(negedge clk); cmd_valid=0;
      @(posedge clk); #1;
      if (!rsp_valid || cmd_ready || rsp_rdata!==held)
        $fatal(1,"probe stalled response changed");
      word=held;
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
    end
  endtask
  task automatic put(input [11:0] address,input [31:0] data,input [3:0] mask);
    reg [31:0] ignored;
    begin transfer(0,address,data,mask,ignored); end
  endtask
  task automatic expect_read(input [11:0] address,input [31:0] expected_word);
    reg [31:0] word;
    begin
      transfer(1,address,0,0,word);
      if (word!==expected_word)
        $fatal(1,"probe read mismatch address=%h actual=%h expected=%h",address,word,expected_word);
    end
  endtask
  initial begin
    if (!$value$plusargs("MODE=%d",mode)) mode=0;
    repeat (4) @(negedge clk);
    rst_n=1;
    @(negedge clk);
    // No reset/default-zero assumption: these actual storage elements are X.
    if ((^dut.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.Memory[0])!==1'bx ||
        (^dut.u_linear_compute_core.core.xBuffer.data_0)!==1'bx ||
        (^dut.u_linear_compute_core.biasCache.banks_0_0)!==1'bx)
      $fatal(1,"probe requires uninitialized task memories");
    $display("XU_CLEAR_PROBE_TRACE initial_sampled_w_x_bias=unknown reset_cache_enable=%0d",dut.cache_enable);
    expect_read('h000,32'hacce2030);
    expect_read('h050,32'h58550003);
    expect_read('h00c,0);
    put('h040,0,15);
    for (bank=0;bank<8;bank=bank+1) begin
      put('h01c,bank,15);
      for (a=0;a<2048;a=a+1) begin
        put('h020,a,15);
        if (!(mode==1 && bank==7 && a==2047))
          put('h024,(mode==3 && bank==0 && a==0)?1:0,15);
      end
    end
    for (a=0;a<256;a=a+1) begin
      put('h044,a,15); put('h048,0,15);
      put('h04c,0,(mode==2 && a==0)?0:15);
    end
    for (lane=0;lane<8;lane=lane+1) begin
      put('h028,lane,15); put('h02c,0,15); put('h030,0,15);
    end
    for (a=0;a<64;a=a+1) begin
      put('h014,a,15);
      if (mode==4 && a==63) begin
        @(negedge clk);
        cmd_valid=1; cmd_read=0; cmd_addr=32'h10042018;
        cmd_wdata=0; cmd_wmask=15; rsp_ready=1;
        @(posedge clk); #1;
        @(negedge clk); cmd_valid=0; source_request=1;
        @(posedge clk); #1;
        $fatal(1,"undrained negative probe unexpectedly accepted");
      end else put('h018,0,15);
    end
    put('h01c,0,15); put('h020,0,15);
    @(negedge clk); source_request=1;
    @(posedge clk); #1;
    if (!payload_phase || !xu_clear_complete)
      $fatal(1,"payload observer was not enabled at first source request");
    @(negedge clk); source_request=0;
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=0 half=0 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_0.sram1.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=0 half=1 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=1 half=0 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_1.sram1.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=1 half=1 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_2.sram0.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=2 half=0 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_2.sram1.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=2 half=1 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_3.sram0.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=3 half=0 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_3.sram1.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=3 half=1 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_4.sram0.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=4 half=0 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_4.sram1.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=4 half=1 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_5.sram0.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=5 half=0 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_5.sram1.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=5 half=1 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_6.sram0.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=6 half=0 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_6.sram1.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=6 half=1 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_7.sram0.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=7 half=0 address=%0d",a);
    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_7.sram1.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=7 half=1 address=%0d",a);
    if (dut.u_linear_compute_core.core.xBuffer.data_0!==16'b0)
      $fatal(1,"physical X content not zero address=0");
    if (dut.u_linear_compute_core.core.xBuffer.data_1!==16'b0)
      $fatal(1,"physical X content not zero address=1");
    if (dut.u_linear_compute_core.core.xBuffer.data_2!==16'b0)
      $fatal(1,"physical X content not zero address=2");
    if (dut.u_linear_compute_core.core.xBuffer.data_3!==16'b0)
      $fatal(1,"physical X content not zero address=3");
    if (dut.u_linear_compute_core.core.xBuffer.data_4!==16'b0)
      $fatal(1,"physical X content not zero address=4");
    if (dut.u_linear_compute_core.core.xBuffer.data_5!==16'b0)
      $fatal(1,"physical X content not zero address=5");
    if (dut.u_linear_compute_core.core.xBuffer.data_6!==16'b0)
      $fatal(1,"physical X content not zero address=6");
    if (dut.u_linear_compute_core.core.xBuffer.data_7!==16'b0)
      $fatal(1,"physical X content not zero address=7");
    if (dut.u_linear_compute_core.core.xBuffer.data_8!==16'b0)
      $fatal(1,"physical X content not zero address=8");
    if (dut.u_linear_compute_core.core.xBuffer.data_9!==16'b0)
      $fatal(1,"physical X content not zero address=9");
    if (dut.u_linear_compute_core.core.xBuffer.data_10!==16'b0)
      $fatal(1,"physical X content not zero address=10");
    if (dut.u_linear_compute_core.core.xBuffer.data_11!==16'b0)
      $fatal(1,"physical X content not zero address=11");
    if (dut.u_linear_compute_core.core.xBuffer.data_12!==16'b0)
      $fatal(1,"physical X content not zero address=12");
    if (dut.u_linear_compute_core.core.xBuffer.data_13!==16'b0)
      $fatal(1,"physical X content not zero address=13");
    if (dut.u_linear_compute_core.core.xBuffer.data_14!==16'b0)
      $fatal(1,"physical X content not zero address=14");
    if (dut.u_linear_compute_core.core.xBuffer.data_15!==16'b0)
      $fatal(1,"physical X content not zero address=15");
    if (dut.u_linear_compute_core.core.xBuffer.data_16!==16'b0)
      $fatal(1,"physical X content not zero address=16");
    if (dut.u_linear_compute_core.core.xBuffer.data_17!==16'b0)
      $fatal(1,"physical X content not zero address=17");
    if (dut.u_linear_compute_core.core.xBuffer.data_18!==16'b0)
      $fatal(1,"physical X content not zero address=18");
    if (dut.u_linear_compute_core.core.xBuffer.data_19!==16'b0)
      $fatal(1,"physical X content not zero address=19");
    if (dut.u_linear_compute_core.core.xBuffer.data_20!==16'b0)
      $fatal(1,"physical X content not zero address=20");
    if (dut.u_linear_compute_core.core.xBuffer.data_21!==16'b0)
      $fatal(1,"physical X content not zero address=21");
    if (dut.u_linear_compute_core.core.xBuffer.data_22!==16'b0)
      $fatal(1,"physical X content not zero address=22");
    if (dut.u_linear_compute_core.core.xBuffer.data_23!==16'b0)
      $fatal(1,"physical X content not zero address=23");
    if (dut.u_linear_compute_core.core.xBuffer.data_24!==16'b0)
      $fatal(1,"physical X content not zero address=24");
    if (dut.u_linear_compute_core.core.xBuffer.data_25!==16'b0)
      $fatal(1,"physical X content not zero address=25");
    if (dut.u_linear_compute_core.core.xBuffer.data_26!==16'b0)
      $fatal(1,"physical X content not zero address=26");
    if (dut.u_linear_compute_core.core.xBuffer.data_27!==16'b0)
      $fatal(1,"physical X content not zero address=27");
    if (dut.u_linear_compute_core.core.xBuffer.data_28!==16'b0)
      $fatal(1,"physical X content not zero address=28");
    if (dut.u_linear_compute_core.core.xBuffer.data_29!==16'b0)
      $fatal(1,"physical X content not zero address=29");
    if (dut.u_linear_compute_core.core.xBuffer.data_30!==16'b0)
      $fatal(1,"physical X content not zero address=30");
    if (dut.u_linear_compute_core.core.xBuffer.data_31!==16'b0)
      $fatal(1,"physical X content not zero address=31");
    if (dut.u_linear_compute_core.core.xBuffer.data_32!==16'b0)
      $fatal(1,"physical X content not zero address=32");
    if (dut.u_linear_compute_core.core.xBuffer.data_33!==16'b0)
      $fatal(1,"physical X content not zero address=33");
    if (dut.u_linear_compute_core.core.xBuffer.data_34!==16'b0)
      $fatal(1,"physical X content not zero address=34");
    if (dut.u_linear_compute_core.core.xBuffer.data_35!==16'b0)
      $fatal(1,"physical X content not zero address=35");
    if (dut.u_linear_compute_core.core.xBuffer.data_36!==16'b0)
      $fatal(1,"physical X content not zero address=36");
    if (dut.u_linear_compute_core.core.xBuffer.data_37!==16'b0)
      $fatal(1,"physical X content not zero address=37");
    if (dut.u_linear_compute_core.core.xBuffer.data_38!==16'b0)
      $fatal(1,"physical X content not zero address=38");
    if (dut.u_linear_compute_core.core.xBuffer.data_39!==16'b0)
      $fatal(1,"physical X content not zero address=39");
    if (dut.u_linear_compute_core.core.xBuffer.data_40!==16'b0)
      $fatal(1,"physical X content not zero address=40");
    if (dut.u_linear_compute_core.core.xBuffer.data_41!==16'b0)
      $fatal(1,"physical X content not zero address=41");
    if (dut.u_linear_compute_core.core.xBuffer.data_42!==16'b0)
      $fatal(1,"physical X content not zero address=42");
    if (dut.u_linear_compute_core.core.xBuffer.data_43!==16'b0)
      $fatal(1,"physical X content not zero address=43");
    if (dut.u_linear_compute_core.core.xBuffer.data_44!==16'b0)
      $fatal(1,"physical X content not zero address=44");
    if (dut.u_linear_compute_core.core.xBuffer.data_45!==16'b0)
      $fatal(1,"physical X content not zero address=45");
    if (dut.u_linear_compute_core.core.xBuffer.data_46!==16'b0)
      $fatal(1,"physical X content not zero address=46");
    if (dut.u_linear_compute_core.core.xBuffer.data_47!==16'b0)
      $fatal(1,"physical X content not zero address=47");
    if (dut.u_linear_compute_core.core.xBuffer.data_48!==16'b0)
      $fatal(1,"physical X content not zero address=48");
    if (dut.u_linear_compute_core.core.xBuffer.data_49!==16'b0)
      $fatal(1,"physical X content not zero address=49");
    if (dut.u_linear_compute_core.core.xBuffer.data_50!==16'b0)
      $fatal(1,"physical X content not zero address=50");
    if (dut.u_linear_compute_core.core.xBuffer.data_51!==16'b0)
      $fatal(1,"physical X content not zero address=51");
    if (dut.u_linear_compute_core.core.xBuffer.data_52!==16'b0)
      $fatal(1,"physical X content not zero address=52");
    if (dut.u_linear_compute_core.core.xBuffer.data_53!==16'b0)
      $fatal(1,"physical X content not zero address=53");
    if (dut.u_linear_compute_core.core.xBuffer.data_54!==16'b0)
      $fatal(1,"physical X content not zero address=54");
    if (dut.u_linear_compute_core.core.xBuffer.data_55!==16'b0)
      $fatal(1,"physical X content not zero address=55");
    if (dut.u_linear_compute_core.core.xBuffer.data_56!==16'b0)
      $fatal(1,"physical X content not zero address=56");
    if (dut.u_linear_compute_core.core.xBuffer.data_57!==16'b0)
      $fatal(1,"physical X content not zero address=57");
    if (dut.u_linear_compute_core.core.xBuffer.data_58!==16'b0)
      $fatal(1,"physical X content not zero address=58");
    if (dut.u_linear_compute_core.core.xBuffer.data_59!==16'b0)
      $fatal(1,"physical X content not zero address=59");
    if (dut.u_linear_compute_core.core.xBuffer.data_60!==16'b0)
      $fatal(1,"physical X content not zero address=60");
    if (dut.u_linear_compute_core.core.xBuffer.data_61!==16'b0)
      $fatal(1,"physical X content not zero address=61");
    if (dut.u_linear_compute_core.core.xBuffer.data_62!==16'b0)
      $fatal(1,"physical X content not zero address=62");
    if (dut.u_linear_compute_core.core.xBuffer.data_63!==16'b0)
      $fatal(1,"physical X content not zero address=63");
    if (dut.u_linear_compute_core.biasCache.banks_0_0!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=0");
    if (dut.u_linear_compute_core.biasCache.banks_0_1!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=1");
    if (dut.u_linear_compute_core.biasCache.banks_0_2!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=2");
    if (dut.u_linear_compute_core.biasCache.banks_0_3!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=3");
    if (dut.u_linear_compute_core.biasCache.banks_0_4!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=4");
    if (dut.u_linear_compute_core.biasCache.banks_0_5!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=5");
    if (dut.u_linear_compute_core.biasCache.banks_0_6!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=6");
    if (dut.u_linear_compute_core.biasCache.banks_0_7!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=7");
    if (dut.u_linear_compute_core.biasCache.banks_0_8!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=8");
    if (dut.u_linear_compute_core.biasCache.banks_0_9!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=9");
    if (dut.u_linear_compute_core.biasCache.banks_0_10!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=10");
    if (dut.u_linear_compute_core.biasCache.banks_0_11!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=11");
    if (dut.u_linear_compute_core.biasCache.banks_0_12!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=12");
    if (dut.u_linear_compute_core.biasCache.banks_0_13!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=13");
    if (dut.u_linear_compute_core.biasCache.banks_0_14!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=14");
    if (dut.u_linear_compute_core.biasCache.banks_0_15!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=15");
    if (dut.u_linear_compute_core.biasCache.banks_0_16!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=16");
    if (dut.u_linear_compute_core.biasCache.banks_0_17!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=17");
    if (dut.u_linear_compute_core.biasCache.banks_0_18!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=18");
    if (dut.u_linear_compute_core.biasCache.banks_0_19!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=19");
    if (dut.u_linear_compute_core.biasCache.banks_0_20!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=20");
    if (dut.u_linear_compute_core.biasCache.banks_0_21!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=21");
    if (dut.u_linear_compute_core.biasCache.banks_0_22!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=22");
    if (dut.u_linear_compute_core.biasCache.banks_0_23!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=23");
    if (dut.u_linear_compute_core.biasCache.banks_0_24!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=24");
    if (dut.u_linear_compute_core.biasCache.banks_0_25!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=25");
    if (dut.u_linear_compute_core.biasCache.banks_0_26!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=26");
    if (dut.u_linear_compute_core.biasCache.banks_0_27!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=27");
    if (dut.u_linear_compute_core.biasCache.banks_0_28!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=28");
    if (dut.u_linear_compute_core.biasCache.banks_0_29!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=29");
    if (dut.u_linear_compute_core.biasCache.banks_0_30!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=30");
    if (dut.u_linear_compute_core.biasCache.banks_0_31!==40'b0)
      $fatal(1,"physical bias content not zero bank=0 group=31");
    if (dut.u_linear_compute_core.biasCache.banks_1_0!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=0");
    if (dut.u_linear_compute_core.biasCache.banks_1_1!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=1");
    if (dut.u_linear_compute_core.biasCache.banks_1_2!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=2");
    if (dut.u_linear_compute_core.biasCache.banks_1_3!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=3");
    if (dut.u_linear_compute_core.biasCache.banks_1_4!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=4");
    if (dut.u_linear_compute_core.biasCache.banks_1_5!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=5");
    if (dut.u_linear_compute_core.biasCache.banks_1_6!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=6");
    if (dut.u_linear_compute_core.biasCache.banks_1_7!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=7");
    if (dut.u_linear_compute_core.biasCache.banks_1_8!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=8");
    if (dut.u_linear_compute_core.biasCache.banks_1_9!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=9");
    if (dut.u_linear_compute_core.biasCache.banks_1_10!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=10");
    if (dut.u_linear_compute_core.biasCache.banks_1_11!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=11");
    if (dut.u_linear_compute_core.biasCache.banks_1_12!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=12");
    if (dut.u_linear_compute_core.biasCache.banks_1_13!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=13");
    if (dut.u_linear_compute_core.biasCache.banks_1_14!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=14");
    if (dut.u_linear_compute_core.biasCache.banks_1_15!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=15");
    if (dut.u_linear_compute_core.biasCache.banks_1_16!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=16");
    if (dut.u_linear_compute_core.biasCache.banks_1_17!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=17");
    if (dut.u_linear_compute_core.biasCache.banks_1_18!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=18");
    if (dut.u_linear_compute_core.biasCache.banks_1_19!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=19");
    if (dut.u_linear_compute_core.biasCache.banks_1_20!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=20");
    if (dut.u_linear_compute_core.biasCache.banks_1_21!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=21");
    if (dut.u_linear_compute_core.biasCache.banks_1_22!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=22");
    if (dut.u_linear_compute_core.biasCache.banks_1_23!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=23");
    if (dut.u_linear_compute_core.biasCache.banks_1_24!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=24");
    if (dut.u_linear_compute_core.biasCache.banks_1_25!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=25");
    if (dut.u_linear_compute_core.biasCache.banks_1_26!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=26");
    if (dut.u_linear_compute_core.biasCache.banks_1_27!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=27");
    if (dut.u_linear_compute_core.biasCache.banks_1_28!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=28");
    if (dut.u_linear_compute_core.biasCache.banks_1_29!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=29");
    if (dut.u_linear_compute_core.biasCache.banks_1_30!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=30");
    if (dut.u_linear_compute_core.biasCache.banks_1_31!==40'b0)
      $fatal(1,"physical bias content not zero bank=1 group=31");
    if (dut.u_linear_compute_core.biasCache.banks_2_0!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=0");
    if (dut.u_linear_compute_core.biasCache.banks_2_1!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=1");
    if (dut.u_linear_compute_core.biasCache.banks_2_2!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=2");
    if (dut.u_linear_compute_core.biasCache.banks_2_3!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=3");
    if (dut.u_linear_compute_core.biasCache.banks_2_4!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=4");
    if (dut.u_linear_compute_core.biasCache.banks_2_5!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=5");
    if (dut.u_linear_compute_core.biasCache.banks_2_6!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=6");
    if (dut.u_linear_compute_core.biasCache.banks_2_7!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=7");
    if (dut.u_linear_compute_core.biasCache.banks_2_8!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=8");
    if (dut.u_linear_compute_core.biasCache.banks_2_9!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=9");
    if (dut.u_linear_compute_core.biasCache.banks_2_10!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=10");
    if (dut.u_linear_compute_core.biasCache.banks_2_11!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=11");
    if (dut.u_linear_compute_core.biasCache.banks_2_12!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=12");
    if (dut.u_linear_compute_core.biasCache.banks_2_13!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=13");
    if (dut.u_linear_compute_core.biasCache.banks_2_14!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=14");
    if (dut.u_linear_compute_core.biasCache.banks_2_15!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=15");
    if (dut.u_linear_compute_core.biasCache.banks_2_16!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=16");
    if (dut.u_linear_compute_core.biasCache.banks_2_17!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=17");
    if (dut.u_linear_compute_core.biasCache.banks_2_18!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=18");
    if (dut.u_linear_compute_core.biasCache.banks_2_19!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=19");
    if (dut.u_linear_compute_core.biasCache.banks_2_20!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=20");
    if (dut.u_linear_compute_core.biasCache.banks_2_21!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=21");
    if (dut.u_linear_compute_core.biasCache.banks_2_22!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=22");
    if (dut.u_linear_compute_core.biasCache.banks_2_23!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=23");
    if (dut.u_linear_compute_core.biasCache.banks_2_24!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=24");
    if (dut.u_linear_compute_core.biasCache.banks_2_25!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=25");
    if (dut.u_linear_compute_core.biasCache.banks_2_26!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=26");
    if (dut.u_linear_compute_core.biasCache.banks_2_27!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=27");
    if (dut.u_linear_compute_core.biasCache.banks_2_28!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=28");
    if (dut.u_linear_compute_core.biasCache.banks_2_29!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=29");
    if (dut.u_linear_compute_core.biasCache.banks_2_30!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=30");
    if (dut.u_linear_compute_core.biasCache.banks_2_31!==40'b0)
      $fatal(1,"physical bias content not zero bank=2 group=31");
    if (dut.u_linear_compute_core.biasCache.banks_3_0!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=0");
    if (dut.u_linear_compute_core.biasCache.banks_3_1!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=1");
    if (dut.u_linear_compute_core.biasCache.banks_3_2!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=2");
    if (dut.u_linear_compute_core.biasCache.banks_3_3!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=3");
    if (dut.u_linear_compute_core.biasCache.banks_3_4!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=4");
    if (dut.u_linear_compute_core.biasCache.banks_3_5!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=5");
    if (dut.u_linear_compute_core.biasCache.banks_3_6!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=6");
    if (dut.u_linear_compute_core.biasCache.banks_3_7!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=7");
    if (dut.u_linear_compute_core.biasCache.banks_3_8!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=8");
    if (dut.u_linear_compute_core.biasCache.banks_3_9!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=9");
    if (dut.u_linear_compute_core.biasCache.banks_3_10!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=10");
    if (dut.u_linear_compute_core.biasCache.banks_3_11!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=11");
    if (dut.u_linear_compute_core.biasCache.banks_3_12!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=12");
    if (dut.u_linear_compute_core.biasCache.banks_3_13!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=13");
    if (dut.u_linear_compute_core.biasCache.banks_3_14!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=14");
    if (dut.u_linear_compute_core.biasCache.banks_3_15!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=15");
    if (dut.u_linear_compute_core.biasCache.banks_3_16!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=16");
    if (dut.u_linear_compute_core.biasCache.banks_3_17!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=17");
    if (dut.u_linear_compute_core.biasCache.banks_3_18!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=18");
    if (dut.u_linear_compute_core.biasCache.banks_3_19!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=19");
    if (dut.u_linear_compute_core.biasCache.banks_3_20!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=20");
    if (dut.u_linear_compute_core.biasCache.banks_3_21!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=21");
    if (dut.u_linear_compute_core.biasCache.banks_3_22!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=22");
    if (dut.u_linear_compute_core.biasCache.banks_3_23!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=23");
    if (dut.u_linear_compute_core.biasCache.banks_3_24!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=24");
    if (dut.u_linear_compute_core.biasCache.banks_3_25!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=25");
    if (dut.u_linear_compute_core.biasCache.banks_3_26!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=26");
    if (dut.u_linear_compute_core.biasCache.banks_3_27!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=27");
    if (dut.u_linear_compute_core.biasCache.banks_3_28!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=28");
    if (dut.u_linear_compute_core.biasCache.banks_3_29!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=29");
    if (dut.u_linear_compute_core.biasCache.banks_3_30!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=30");
    if (dut.u_linear_compute_core.biasCache.banks_3_31!==40'b0)
      $fatal(1,"physical bias content not zero bank=3 group=31");
    if (dut.u_linear_compute_core.biasCache.banks_4_0!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=0");
    if (dut.u_linear_compute_core.biasCache.banks_4_1!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=1");
    if (dut.u_linear_compute_core.biasCache.banks_4_2!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=2");
    if (dut.u_linear_compute_core.biasCache.banks_4_3!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=3");
    if (dut.u_linear_compute_core.biasCache.banks_4_4!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=4");
    if (dut.u_linear_compute_core.biasCache.banks_4_5!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=5");
    if (dut.u_linear_compute_core.biasCache.banks_4_6!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=6");
    if (dut.u_linear_compute_core.biasCache.banks_4_7!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=7");
    if (dut.u_linear_compute_core.biasCache.banks_4_8!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=8");
    if (dut.u_linear_compute_core.biasCache.banks_4_9!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=9");
    if (dut.u_linear_compute_core.biasCache.banks_4_10!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=10");
    if (dut.u_linear_compute_core.biasCache.banks_4_11!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=11");
    if (dut.u_linear_compute_core.biasCache.banks_4_12!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=12");
    if (dut.u_linear_compute_core.biasCache.banks_4_13!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=13");
    if (dut.u_linear_compute_core.biasCache.banks_4_14!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=14");
    if (dut.u_linear_compute_core.biasCache.banks_4_15!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=15");
    if (dut.u_linear_compute_core.biasCache.banks_4_16!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=16");
    if (dut.u_linear_compute_core.biasCache.banks_4_17!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=17");
    if (dut.u_linear_compute_core.biasCache.banks_4_18!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=18");
    if (dut.u_linear_compute_core.biasCache.banks_4_19!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=19");
    if (dut.u_linear_compute_core.biasCache.banks_4_20!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=20");
    if (dut.u_linear_compute_core.biasCache.banks_4_21!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=21");
    if (dut.u_linear_compute_core.biasCache.banks_4_22!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=22");
    if (dut.u_linear_compute_core.biasCache.banks_4_23!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=23");
    if (dut.u_linear_compute_core.biasCache.banks_4_24!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=24");
    if (dut.u_linear_compute_core.biasCache.banks_4_25!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=25");
    if (dut.u_linear_compute_core.biasCache.banks_4_26!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=26");
    if (dut.u_linear_compute_core.biasCache.banks_4_27!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=27");
    if (dut.u_linear_compute_core.biasCache.banks_4_28!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=28");
    if (dut.u_linear_compute_core.biasCache.banks_4_29!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=29");
    if (dut.u_linear_compute_core.biasCache.banks_4_30!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=30");
    if (dut.u_linear_compute_core.biasCache.banks_4_31!==40'b0)
      $fatal(1,"physical bias content not zero bank=4 group=31");
    if (dut.u_linear_compute_core.biasCache.banks_5_0!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=0");
    if (dut.u_linear_compute_core.biasCache.banks_5_1!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=1");
    if (dut.u_linear_compute_core.biasCache.banks_5_2!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=2");
    if (dut.u_linear_compute_core.biasCache.banks_5_3!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=3");
    if (dut.u_linear_compute_core.biasCache.banks_5_4!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=4");
    if (dut.u_linear_compute_core.biasCache.banks_5_5!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=5");
    if (dut.u_linear_compute_core.biasCache.banks_5_6!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=6");
    if (dut.u_linear_compute_core.biasCache.banks_5_7!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=7");
    if (dut.u_linear_compute_core.biasCache.banks_5_8!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=8");
    if (dut.u_linear_compute_core.biasCache.banks_5_9!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=9");
    if (dut.u_linear_compute_core.biasCache.banks_5_10!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=10");
    if (dut.u_linear_compute_core.biasCache.banks_5_11!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=11");
    if (dut.u_linear_compute_core.biasCache.banks_5_12!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=12");
    if (dut.u_linear_compute_core.biasCache.banks_5_13!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=13");
    if (dut.u_linear_compute_core.biasCache.banks_5_14!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=14");
    if (dut.u_linear_compute_core.biasCache.banks_5_15!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=15");
    if (dut.u_linear_compute_core.biasCache.banks_5_16!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=16");
    if (dut.u_linear_compute_core.biasCache.banks_5_17!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=17");
    if (dut.u_linear_compute_core.biasCache.banks_5_18!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=18");
    if (dut.u_linear_compute_core.biasCache.banks_5_19!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=19");
    if (dut.u_linear_compute_core.biasCache.banks_5_20!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=20");
    if (dut.u_linear_compute_core.biasCache.banks_5_21!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=21");
    if (dut.u_linear_compute_core.biasCache.banks_5_22!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=22");
    if (dut.u_linear_compute_core.biasCache.banks_5_23!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=23");
    if (dut.u_linear_compute_core.biasCache.banks_5_24!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=24");
    if (dut.u_linear_compute_core.biasCache.banks_5_25!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=25");
    if (dut.u_linear_compute_core.biasCache.banks_5_26!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=26");
    if (dut.u_linear_compute_core.biasCache.banks_5_27!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=27");
    if (dut.u_linear_compute_core.biasCache.banks_5_28!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=28");
    if (dut.u_linear_compute_core.biasCache.banks_5_29!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=29");
    if (dut.u_linear_compute_core.biasCache.banks_5_30!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=30");
    if (dut.u_linear_compute_core.biasCache.banks_5_31!==40'b0)
      $fatal(1,"physical bias content not zero bank=5 group=31");
    if (dut.u_linear_compute_core.biasCache.banks_6_0!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=0");
    if (dut.u_linear_compute_core.biasCache.banks_6_1!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=1");
    if (dut.u_linear_compute_core.biasCache.banks_6_2!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=2");
    if (dut.u_linear_compute_core.biasCache.banks_6_3!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=3");
    if (dut.u_linear_compute_core.biasCache.banks_6_4!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=4");
    if (dut.u_linear_compute_core.biasCache.banks_6_5!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=5");
    if (dut.u_linear_compute_core.biasCache.banks_6_6!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=6");
    if (dut.u_linear_compute_core.biasCache.banks_6_7!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=7");
    if (dut.u_linear_compute_core.biasCache.banks_6_8!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=8");
    if (dut.u_linear_compute_core.biasCache.banks_6_9!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=9");
    if (dut.u_linear_compute_core.biasCache.banks_6_10!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=10");
    if (dut.u_linear_compute_core.biasCache.banks_6_11!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=11");
    if (dut.u_linear_compute_core.biasCache.banks_6_12!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=12");
    if (dut.u_linear_compute_core.biasCache.banks_6_13!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=13");
    if (dut.u_linear_compute_core.biasCache.banks_6_14!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=14");
    if (dut.u_linear_compute_core.biasCache.banks_6_15!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=15");
    if (dut.u_linear_compute_core.biasCache.banks_6_16!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=16");
    if (dut.u_linear_compute_core.biasCache.banks_6_17!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=17");
    if (dut.u_linear_compute_core.biasCache.banks_6_18!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=18");
    if (dut.u_linear_compute_core.biasCache.banks_6_19!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=19");
    if (dut.u_linear_compute_core.biasCache.banks_6_20!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=20");
    if (dut.u_linear_compute_core.biasCache.banks_6_21!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=21");
    if (dut.u_linear_compute_core.biasCache.banks_6_22!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=22");
    if (dut.u_linear_compute_core.biasCache.banks_6_23!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=23");
    if (dut.u_linear_compute_core.biasCache.banks_6_24!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=24");
    if (dut.u_linear_compute_core.biasCache.banks_6_25!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=25");
    if (dut.u_linear_compute_core.biasCache.banks_6_26!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=26");
    if (dut.u_linear_compute_core.biasCache.banks_6_27!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=27");
    if (dut.u_linear_compute_core.biasCache.banks_6_28!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=28");
    if (dut.u_linear_compute_core.biasCache.banks_6_29!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=29");
    if (dut.u_linear_compute_core.biasCache.banks_6_30!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=30");
    if (dut.u_linear_compute_core.biasCache.banks_6_31!==40'b0)
      $fatal(1,"physical bias content not zero bank=6 group=31");
    if (dut.u_linear_compute_core.biasCache.banks_7_0!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=0");
    if (dut.u_linear_compute_core.biasCache.banks_7_1!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=1");
    if (dut.u_linear_compute_core.biasCache.banks_7_2!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=2");
    if (dut.u_linear_compute_core.biasCache.banks_7_3!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=3");
    if (dut.u_linear_compute_core.biasCache.banks_7_4!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=4");
    if (dut.u_linear_compute_core.biasCache.banks_7_5!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=5");
    if (dut.u_linear_compute_core.biasCache.banks_7_6!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=6");
    if (dut.u_linear_compute_core.biasCache.banks_7_7!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=7");
    if (dut.u_linear_compute_core.biasCache.banks_7_8!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=8");
    if (dut.u_linear_compute_core.biasCache.banks_7_9!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=9");
    if (dut.u_linear_compute_core.biasCache.banks_7_10!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=10");
    if (dut.u_linear_compute_core.biasCache.banks_7_11!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=11");
    if (dut.u_linear_compute_core.biasCache.banks_7_12!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=12");
    if (dut.u_linear_compute_core.biasCache.banks_7_13!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=13");
    if (dut.u_linear_compute_core.biasCache.banks_7_14!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=14");
    if (dut.u_linear_compute_core.biasCache.banks_7_15!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=15");
    if (dut.u_linear_compute_core.biasCache.banks_7_16!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=16");
    if (dut.u_linear_compute_core.biasCache.banks_7_17!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=17");
    if (dut.u_linear_compute_core.biasCache.banks_7_18!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=18");
    if (dut.u_linear_compute_core.biasCache.banks_7_19!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=19");
    if (dut.u_linear_compute_core.biasCache.banks_7_20!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=20");
    if (dut.u_linear_compute_core.biasCache.banks_7_21!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=21");
    if (dut.u_linear_compute_core.biasCache.banks_7_22!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=22");
    if (dut.u_linear_compute_core.biasCache.banks_7_23!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=23");
    if (dut.u_linear_compute_core.biasCache.banks_7_24!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=24");
    if (dut.u_linear_compute_core.biasCache.banks_7_25!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=25");
    if (dut.u_linear_compute_core.biasCache.banks_7_26!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=26");
    if (dut.u_linear_compute_core.biasCache.banks_7_27!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=27");
    if (dut.u_linear_compute_core.biasCache.banks_7_28!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=28");
    if (dut.u_linear_compute_core.biasCache.banks_7_29!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=29");
    if (dut.u_linear_compute_core.biasCache.banks_7_30!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=30");
    if (dut.u_linear_compute_core.biasCache.banks_7_31!==40'b0)
      $fatal(1,"physical bias content not zero bank=7 group=31");
    for (lane=0;lane<8;lane=lane+1)
      if (dut.bias_regs[lane]!==40'b0) $fatal(1,"legacy bias was not cleared");
    $display("XU_CLEAR_PROBE_TRACE all_w_x_bias_storage_zero=1 accepted_clear_writes=%0d",xu_clear_writes);

    // A small post-clear arithmetic witness uses public MMIO and signed data.
    // Unchanged zero W entries must participate correctly in the dot product.
    for (bank=0;bank<8;bank=bank+1) begin
      put('h01c,bank,15); put('h020,31*64,15); put('h024,bank+1,15);
      bias_value=-5*(bank+1);
      put('h044,248+bank,15); put('h048,bias_value[31:0],15);
      put('h04c,{24'b0,bias_value[39:32]},15);
    end
    for (a=0;a<64;a=a+1) begin
      put('h014,a,15); put('h018,3,15);
    end
    put('h040,1,15); put('h010,31,15); put('h00c,2,15); put('h008,1,15);
    polls=0; response=0;
    while (!response[1]) begin
      transfer(1,'h00c,0,0,response); polls=polls+1;
      if (polls>32) $fatal(1,"probe compute timeout");
    end
    if (response[0]) $fatal(1,"probe completion remains busy");
    for (lane=0;lane<8;lane=lane+1) begin
      expected=-2*(lane+1);
      expect_read('h080+8*lane,expected[31:0]);
      expect_read('h084+8*lane,{16'b0,expected[47:32]});
    end
    if (accepted!=retired) $fatal(1,"probe response retirement mismatch");
    $display("XU_CLEAR_MMIO_PROBE_PASS clear_writes=33697 checked_w_words=16384 checked_bias_entries=256 checked_legacy_bias=8 checked_x_words=64 result_lanes=8 accepted=%0d retired=%0d",accepted,retired);
    $finish;
  end
  initial begin #10000000; $fatal(1,"probe timeout"); end
endmodule
