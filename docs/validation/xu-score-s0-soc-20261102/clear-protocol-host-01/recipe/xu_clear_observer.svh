
  // xu passive clear observer: no force, no DUT assignment, no task payload.
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
    input source_accept;
    output payload_phase;
    integer a;
    reg [4:0] old_mask, new_mask;
    begin
      if (!xu_clear_complete) begin
        if (dut.cache_enable!==1'b0 || dut.busy!==1'b0 ||
            dut.core_start!==1'b0)
          $fatal(1,"XU_CLEAR_REJECT non-idle/enabled clear phase");
        if (source_accept) begin
          if (xu_clear_writes!=33697 || xu_clear_disable_count!=1 ||
              xu_clear_w_count!=16384 || xu_clear_bias_count!=256 ||
              xu_clear_legacy_count!=8 || xu_clear_x_count!=64)
            $fatal(1,"XU_CLEAR_REJECT incomplete clear before first source accept");
          // W/X stores are committed one clock after MMIO acceptance.
          if (dut.w_load_wen!==1'b0 || dut.x_load_wen!==1'b0)
            $fatal(1,"XU_CLEAR_REJECT undrained W/X clear strobe");
          xu_clear_complete=1;
          $display("XU_TASK_CLEAR_OBSERVED writes=33697 w=16384 bias=256 legacy_bias=8 x=64 drained=1 cache_enable=0 idle=1");
        end else if (dut.cmd_valid && dut.cmd_ready) begin
          if (dut.cmd_read) begin
            if (dut.cmd_addr[11:0]!=12'h000 &&
                dut.cmd_addr[11:0]!=12'h00c &&
                dut.cmd_addr[11:0]!=12'h050)
              $fatal(1,"XU_CLEAR_REJECT unexpected pretask MMIO read");
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
