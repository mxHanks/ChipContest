
`timescale 1ns/1fs
module xu_clear_mock_accel;
  reg cmd_valid=0,cmd_ready=1,cmd_read=0,busy=0,cache_enable=0,core_start=0;
  reg w_load_wen=0,x_load_wen=0,rsp_valid=0;
  reg [31:0] cmd_addr=0,cmd_wdata=0;
  reg [3:0] cmd_wmask=15;
  reg [2:0] w_bank_reg=0,bias_index_reg=0;
  reg [10:0] w_addr_reg=0;
  reg [7:0] cache_addr_reg=0;
  reg [5:0] x_addr_reg=0;
  reg [4:0] group_reg=0;
endmodule
module tb_xu_clear_request_probe;
  xu_clear_mock_accel accel();
  `define ACCEL accel
  localparam BASE=32'h90000000;
  reg cmd_valid=0,cmd_read=1,cmd_ready=0;
  reg [31:0] cmd_addr=BASE;
  integer cycles=0;
  reg [15:0] w[0:16383],x[0:6335];
  reg [39:0] bias[0:255];

  integer xu_global_task, xu_saif_started=0, xu_saif_stopped=0;
  integer xu_w_count=0, xu_bias_count=0, xu_x_count=0, xu_rows=0, xu_starts=0;
  reg xu_w_seen [0:16383];
  reg [4:0] xu_bias_seen [0:255];
  reg [63:0] xu_x_seen=0;

  task xu_observe_upload;
    integer a, logical_index, row_index;
    reg [4:0] old_mask, new_mask;
    begin
      if (`ACCEL.cmd_valid && `ACCEL.cmd_ready && !`ACCEL.cmd_read) begin
        case (`ACCEL.cmd_addr[11:0])
          12'h024: begin
            if (!xu_saif_started || xu_saif_stopped)
              $fatal(1,"W upload outside activity window");
            if ((^{`ACCEL.w_bank_reg,`ACCEL.w_addr_reg})===1'bx)
              $fatal(1,"unknown W upload address");
            a=`ACCEL.w_bank_reg*2048+`ACCEL.w_addr_reg;
            logical_index=(`ACCEL.w_addr_reg%64)*256+
                          (`ACCEL.w_addr_reg/64)*8+`ACCEL.w_bank_reg;
            if (`ACCEL.cmd_wmask[1:0]!==2'b11 ||
                `ACCEL.cmd_wdata[15:0]!==w[logical_index] || xu_w_seen[a])
              $fatal(1,"incomplete/duplicate/incorrect W upload address=%0d",a);
            xu_w_seen[a]=1;
            xu_w_count=xu_w_count+1;
          end
          12'h048,12'h04c: begin
            if (!xu_saif_started || xu_saif_stopped || `ACCEL.cache_enable!==1'b0)
              $fatal(1,"bias cache upload outside disabled-cache task window");
            if ((^`ACCEL.cache_addr_reg)===1'bx)
              $fatal(1,"unknown bias upload address");
            a=`ACCEL.cache_addr_reg;
            old_mask=xu_bias_seen[a];
            if (`ACCEL.cmd_addr[11:0]==12'h048) begin
              if (`ACCEL.cmd_wmask!==4'hf || `ACCEL.cmd_wdata!==bias[a][31:0] ||
                  old_mask[3:0]!=0) $fatal(1,"incomplete/duplicate/incorrect bias low upload");
              new_mask=old_mask|5'b01111;
            end else begin
              if (`ACCEL.cmd_wmask[0]!==1'b1 || `ACCEL.cmd_wdata[7:0]!==bias[a][39:32] ||
                  old_mask[4]) $fatal(1,"incomplete/duplicate/incorrect bias high upload");
              new_mask=old_mask|5'b10000;
            end
            xu_bias_seen[a]=new_mask;
            if (new_mask==5'b11111 && old_mask!=5'b11111) xu_bias_count=xu_bias_count+1;
          end
          12'h018: begin
            if (!xu_saif_started || xu_saif_stopped || xu_rows>=99)
              $fatal(1,"X upload outside activity window/row range");
            if ((^`ACCEL.x_addr_reg)===1'bx) $fatal(1,"unknown X upload address");
            a=`ACCEL.x_addr_reg;
            row_index=xu_rows;
            if (`ACCEL.cmd_wmask[1:0]!==2'b11 ||
                `ACCEL.cmd_wdata[15:0]!==x[row_index*64+a] || xu_x_seen[a])
              $fatal(1,"incomplete/duplicate/incorrect X upload row=%0d addr=%0d",row_index,a);
            xu_x_seen[a]=1;
            xu_x_count=xu_x_count+1;
          end
          12'h008: if (`ACCEL.cmd_wdata[0] && !`ACCEL.busy) begin
            if (!xu_saif_started || xu_saif_stopped || xu_w_count!=16384 ||
                xu_bias_count!=256 || xu_x_seen!==64'hffffffffffffffff ||
                `ACCEL.cache_enable!==1'b1 || `ACCEL.group_reg!==xu_starts%32)
              $fatal(1,"START before complete W/bias/current-X upload or group order");
            xu_starts=xu_starts+1;
            if (xu_starts%32==0) begin
              xu_rows=xu_rows+1;
              xu_x_seen=0;
            end
          end
          default: begin end
        endcase
      end
    end
  endtask

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

  reg xu_payload_phase=0;
  integer xu_request_cycle=-1, xu_accept_cycle=-1, xu_initial_wait=0;
  integer xu_formal_cycles=0, xu_clear_first_cycle=-1, xu_clear_last_cycle=-1;
  reg [31:0] xu_request_addr;

  task xu_observe_clear_window;
    reg source_request, source_accept, clear_write;
    begin
      source_request=cmd_valid && cmd_read && cmd_addr>=BASE && cmd_addr<BASE+'h18800;
      source_accept=source_request && cmd_ready;
      clear_write=!xu_clear_complete && xu_clear_writes<33697 &&
                  `ACCEL.cmd_valid && `ACCEL.cmd_ready && !`ACCEL.cmd_read;
      if (clear_write) begin
        if (xu_clear_first_cycle<0) begin
          xu_clear_first_cycle=cycles;
          $display("XU_TASK_CLEAR_BEGIN task=%0d cycle=%0d tick=%0.0f",xu_global_task,cycles,$realtime*1000000.0);
        end
        xu_clear_last_cycle=cycles;
      end
      // Once per post-reset edge, before any payload observation or SAIF start.
      xu_observe_task_clear(source_request,xu_payload_phase);
      if (clear_write && xu_clear_writes==33697)
        $display("XU_TASK_CLEAR_LAST_WRITE task=%0d cycle=%0d tick=%0.0f writes=33697",xu_global_task,cycles,$realtime*1000000.0);
      if (source_request && xu_request_cycle<0) begin
        if (!xu_clear_complete || xu_saif_started || xu_saif_stopped ||
            xu_w_count!=0 || xu_bias_count!=0 || xu_x_count!=0 || xu_starts!=0)
          $fatal(1,"clear recipe did not begin from verified empty payload state");
        xu_request_cycle=cycles;
        xu_request_addr=cmd_addr;
        xu_saif_started=1;
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
        $toggle_start();
`endif
        $display("XU_SOURCE_REQUEST task=%0d cycle=%0d tick=%0.0f",xu_global_task,cycles,$realtime*1000000.0);
        $display("XU_ACTIVITY_BEGIN task=%0d tick=%0.0f",xu_global_task,$realtime*1000000.0);
        $display("XU_CACHE_INITIAL task=%0d fresh_process=1 cache_enable=0 busy=0 prior_uploads=0 prior_starts=0",xu_global_task);
      end
      if (xu_request_cycle>=0 && xu_accept_cycle<0) begin
        if (!source_request || cmd_addr!==xu_request_addr)
          $fatal(1,"first source request changed before acceptance");
        if (source_accept) begin
          xu_accept_cycle=cycles;
          if (xu_initial_wait!=xu_accept_cycle-xu_request_cycle)
            $fatal(1,"initial source wait count differs");
          $display("XU_SOURCE_ACCEPT task=%0d cycle=%0d tick=%0.0f",xu_global_task,cycles,$realtime*1000000.0);
        end else xu_initial_wait=xu_initial_wait+1;
      end
      if (xu_saif_started && !xu_saif_stopped) xu_formal_cycles=xu_formal_cycles+1;
      if (xu_payload_phase) xu_observe_upload();
    end
  endtask

  integer i,b,a,r,g,index,mode;
  task step;
    begin #6.666667; cycles=cycles+1; xu_observe_clear_window(); end
  endtask
  task put(input [11:0] address,input [31:0] data);
    begin accel.cmd_addr=address;accel.cmd_wdata=data;accel.cmd_valid=1;step();end
  endtask
  initial begin
    if (!$value$plusargs("MODE=%d",mode)) mode=0;
    xu_global_task=7;
    for(i=0;i<16384;i=i+1) begin w[i]=i*7;xu_w_seen[i]=0;end
    for(i=0;i<6336;i=i+1) x[i]=i*3;
    for(i=0;i<256;i=i+1) begin bias[i]=40'h1230000000+i;xu_bias_seen[i]=0;end
    put('h040,0);
    for(b=0;b<8;b=b+1) begin
      put('h01c,b);accel.w_bank_reg=b;
      for(a=0;a<2048;a=a+1) begin
        put('h020,a);accel.w_addr_reg=a;put('h024,0);
      end
    end
    for(a=0;a<256;a=a+1) begin
      put('h044,a);accel.cache_addr_reg=a;put('h048,0);put('h04c,0);
    end
    for(a=0;a<8;a=a+1) begin
      put('h028,a);accel.bias_index_reg=a;put('h02c,0);put('h030,0);
    end
    for(a=0;a<64;a=a+1) begin
      put('h014,a);accel.x_addr_reg=a;put('h018,0);
    end
    accel.cmd_valid=0;
    if(xu_w_count!=0 || xu_bias_count!=0 || xu_x_count!=0 || xu_saif_started)
      $fatal(1,"clear writes leaked into payload/activity window");
    put('h01c,0);accel.w_bank_reg=0;
    if(mode!=4) begin put('h020,0);accel.w_addr_reg=0;end
    if(mode==3) put('h024,0);
    accel.cmd_valid=0;
    cmd_valid=1;
    step();
    if(!xu_saif_started || !xu_payload_phase || xu_request_cycle!=cycles || xu_accept_cycle!=-1)
      $fatal(1,"blocked first request did not open formal window");
    if(mode==1) cmd_addr=BASE+4;
    if(mode==2) cmd_valid=0;
    step();step();
    cmd_ready=1;step();cmd_valid=0;
    if(xu_initial_wait!=3 || xu_accept_cycle-xu_request_cycle!=3)
      $fatal(1,"initial source waiting was not counted");
    for(b=0;b<8;b=b+1) for(a=0;a<2048;a=a+1) begin
      accel.w_bank_reg=b;accel.w_addr_reg=a;
      index=(a%64)*256+(a/64)*8+b;put('h024,w[index]);
    end
    for(i=0;i<256;i=i+1) begin
      accel.cache_addr_reg=i;put('h048,bias[i][31:0]);put('h04c,bias[i][39:32]);
    end
    accel.cache_enable=1;
    for(r=0;r<99;r=r+1) begin
      for(a=0;a<64;a=a+1) begin
        accel.x_addr_reg=a;put('h018,x[r*64+a]);
      end
      for(g=0;g<32;g=g+1) begin accel.group_reg=g;put('h008,1);end
    end
    if(xu_clear_writes!=33697 || xu_w_count!=16384 || xu_bias_count!=256 ||
       xu_x_count!=6336 || xu_rows!=99 || xu_starts!=3168)
      $fatal(1,"clear/payload coverage changed");
    $display("XU_CLEAR_REQUEST_UPLOAD_PROBE_PASS task=7 clear_writes=33697 initial_wait_cycles=3 w=16384 bias=256 x=6336 rows=99 starts=3168");
    $finish;
  end
endmodule
