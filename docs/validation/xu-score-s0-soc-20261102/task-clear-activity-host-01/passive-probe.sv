
`timescale 1ns/1fs
module xu_mock_accel;
  reg cmd_valid=1,cmd_ready=1,cmd_read=0,busy=0,cache_enable=0;
  reg [31:0] cmd_addr=0,cmd_wdata=0;
  reg [3:0] cmd_wmask=15;
  reg [2:0] w_bank_reg=0;
  reg [10:0] w_addr_reg=0;
  reg [7:0] cache_addr_reg=0;
  reg [5:0] x_addr_reg=0;
  reg [4:0] group_reg=0;
endmodule
module xu_monitor_test;
  xu_mock_accel accel();
  `define ACCEL accel
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

  integer i,b,a,r,g,index,mode;
  initial begin
    if (!$value$plusargs("MODE=%d",mode)) mode=0;
    for(i=0;i<16384;i=i+1) begin w[i]=i*7;xu_w_seen[i]=0;end
    for(i=0;i<6336;i=i+1) x[i]=i*3;
    for(i=0;i<256;i=i+1) begin bias[i]=40'h1230000000+i;xu_bias_seen[i]=0;end
    xu_saif_started=(mode!=5);
    for(b=0;b<8;b=b+1) for(a=0;a<2048;a=a+1) begin
      accel.w_bank_reg=b;accel.w_addr_reg=a;accel.cmd_addr='h024;
      index=(a%64)*256+(a/64)*8+b;
      accel.cmd_wdata=w[index];
      if(mode==4 && b==7 && a==2047) accel.cmd_wdata=accel.cmd_wdata^1;
      #1;if(!(mode==1 && b==7 && a==2047)) xu_observe_upload();
    end
    for(i=0;i<256;i=i+1) begin
      accel.cache_addr_reg=i;
      accel.cmd_addr='h048;accel.cmd_wdata=bias[i][31:0];#1;xu_observe_upload();
      accel.cmd_addr='h04c;accel.cmd_wdata=bias[i][39:32];#1;
      if(!(mode==2 && i==255)) xu_observe_upload();
    end
    accel.cache_enable=1;
    for(r=0;r<99;r=r+1) begin
      for(a=0;a<64;a=a+1) begin
        accel.x_addr_reg=a;accel.cmd_addr='h018;accel.cmd_wdata=x[r*64+a];#1;
        if(!(mode==3 && r==0 && a==63)) xu_observe_upload();
      end
      for(g=0;g<32;g=g+1) begin
        accel.group_reg=g;accel.cmd_addr='h008;accel.cmd_wdata=1;#1;xu_observe_upload();
      end
    end
    if(xu_w_count!=16384 || xu_bias_count!=256 || xu_x_count!=6336 ||
       xu_rows!=99 || xu_starts!=3168) $fatal(1,"bad completion");
    $display("XU_PASSIVE_UPLOAD_PROBE_PASS");$finish;
  end
endmodule
