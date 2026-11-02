
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
        if (`ACCEL.cache_enable!==1'b0 || `ACCEL.busy!==1'b0 ||
            `ACCEL.core_start!==1'b0)
          $fatal(1,"XU_CLEAR_REJECT non-idle/enabled clear phase");
        if (source_request) begin
          if (xu_clear_writes!=33697 || xu_clear_disable_count!=1 ||
              xu_clear_w_count!=16384 || xu_clear_bias_count!=256 ||
              xu_clear_legacy_count!=8 || xu_clear_x_count!=64)
            $fatal(1,"XU_CLEAR_REJECT incomplete clear before first source request");
          // W/X stores are committed one clock after MMIO acceptance.
          if (`ACCEL.w_load_wen!==1'b0 || `ACCEL.x_load_wen!==1'b0 || `ACCEL.rsp_valid!==1'b0)
            $fatal(1,"XU_CLEAR_REJECT undrained W/X clear strobe");
          if (xu_task_setup_writes!=2)
            $fatal(1,"XU_CLEAR_REJECT missing original task destination setup before source request");
          xu_clear_complete=1;
          $display("XU_TASK_CLEAR_OBSERVED writes=33697 w=16384 bias=256 legacy_bias=8 x=64 drained=1 cache_enable=0 idle=1 source_request=1 task_setup_writes=2");
        end else if (`ACCEL.cmd_valid && `ACCEL.cmd_ready) begin
          if (`ACCEL.cmd_read) begin
            if (`ACCEL.cmd_addr[11:0]!=12'h000 &&
                `ACCEL.cmd_addr[11:0]!=12'h00c &&
                `ACCEL.cmd_addr[11:0]!=12'h050)
              $fatal(1,"XU_CLEAR_REJECT unexpected pretask MMIO read");
          end else if (xu_clear_writes==33697 && xu_clear_w_count==16384 &&
                       xu_clear_bias_count==256 && xu_clear_legacy_count==8 &&
                       xu_clear_x_count==64 && xu_clear_disable_count==1) begin
            if (`ACCEL.cmd_wmask!==4'hf || `ACCEL.cmd_wdata!==32'b0 ||
                !((xu_task_setup_writes==0 && `ACCEL.cmd_addr[11:0]==12'h01c) ||
                  (xu_task_setup_writes==1 && `ACCEL.cmd_addr[11:0]==12'h020)))
              $fatal(1,"XU_CLEAR_REJECT unexpected task data/setup before first source request");
            xu_task_setup_writes=xu_task_setup_writes+1;
          end else begin
            if (`ACCEL.cmd_wmask!==4'hf ||
                (^`ACCEL.cmd_wdata)===1'bx)
              $fatal(1,"XU_CLEAR_REJECT incomplete/unknown clear word");
            xu_clear_writes=xu_clear_writes+1;
            case (`ACCEL.cmd_addr[11:0])
              12'h040: begin
                if (`ACCEL.cmd_wdata!==32'b0 || xu_clear_disable_count!=0)
                  $fatal(1,"XU_CLEAR_REJECT cache disable");
                xu_clear_disable_count=xu_clear_disable_count+1;
              end
              12'h01c: if (`ACCEL.cmd_wdata>7)
                $fatal(1,"XU_CLEAR_REJECT W bank");
              12'h020: if (`ACCEL.cmd_wdata>2047)
                $fatal(1,"XU_CLEAR_REJECT W address");
              12'h044: if (`ACCEL.cmd_wdata>255)
                $fatal(1,"XU_CLEAR_REJECT bias address");
              12'h028: if (`ACCEL.cmd_wdata>7)
                $fatal(1,"XU_CLEAR_REJECT legacy bias address");
              12'h014: if (`ACCEL.cmd_wdata>63)
                $fatal(1,"XU_CLEAR_REJECT X address");
              12'h024: begin
                if ((^{`ACCEL.w_bank_reg,`ACCEL.w_addr_reg})===1'bx)
                  $fatal(1,"XU_CLEAR_REJECT unknown W destination");
                a=`ACCEL.w_bank_reg*2048+`ACCEL.w_addr_reg;
                if (`ACCEL.cmd_wdata!==32'b0 || xu_clear_w_seen[a])
                  $fatal(1,"XU_CLEAR_REJECT nonzero/duplicate W clear");
                xu_clear_w_seen[a]=1;
                xu_clear_w_count=xu_clear_w_count+1;
              end
              12'h018: begin
                if ((^`ACCEL.x_addr_reg)===1'bx)
                  $fatal(1,"XU_CLEAR_REJECT unknown X destination");
                a=`ACCEL.x_addr_reg;
                if (`ACCEL.cmd_wdata!==32'b0 || xu_clear_x_seen[a])
                  $fatal(1,"XU_CLEAR_REJECT nonzero/duplicate X clear");
                xu_clear_x_seen[a]=1;
                xu_clear_x_count=xu_clear_x_count+1;
              end
              12'h048,12'h04c,12'h02c,12'h030: begin
                if (`ACCEL.cmd_wdata!==32'b0)
                  $fatal(1,"XU_CLEAR_REJECT nonzero bias clear");
                if (`ACCEL.cmd_addr[11:0]==12'h048 ||
                    `ACCEL.cmd_addr[11:0]==12'h04c) begin
                  if ((^`ACCEL.cache_addr_reg)===1'bx)
                    $fatal(1,"XU_CLEAR_REJECT unknown bias destination");
                  a=`ACCEL.cache_addr_reg;
                  old_mask=xu_clear_bias_seen[a];
                end else begin
                  if ((^`ACCEL.bias_index_reg)===1'bx)
                    $fatal(1,"XU_CLEAR_REJECT unknown legacy bias destination");
                  a=`ACCEL.bias_index_reg;
                  old_mask=xu_clear_legacy_seen[a];
                end
                if (`ACCEL.cmd_addr[11:0]==12'h048 ||
                    `ACCEL.cmd_addr[11:0]==12'h02c) begin
                  if (old_mask[3:0]!=0)
                    $fatal(1,"XU_CLEAR_REJECT duplicate bias low clear");
                  new_mask=old_mask|5'b01111;
                end else begin
                  if (old_mask[4])
                    $fatal(1,"XU_CLEAR_REJECT duplicate bias high clear");
                  new_mask=old_mask|5'b10000;
                end
                if (`ACCEL.cmd_addr[11:0]==12'h048 ||
                    `ACCEL.cmd_addr[11:0]==12'h04c) begin
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
