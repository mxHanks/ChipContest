// xu public mapped diagnostic observer. Never drives the DUT.
// These prove interface transactions, not direct X/bias/FIFO physical state.
integer clear_writes=0,clear_w=0,clear_x=0,clear_bias=0,clear_legacy=0,clear_disable=0;
integer bank_sel=-1,w_addr_sel=-1,x_addr_sel=-1,bias_sel=-1,legacy_sel=-1;
reg[16383:0] clear_w_seen=0;reg[63:0]clear_x_seen=0;
reg[4:0]clear_bias_seen[0:255],clear_legacy_seen[0:7],payload_bias_seen[0:255];
integer payload_w_pairs=0,payload_x_pairs=0,payload_bias=0,payload_rows=0,payload_pops=0;
integer payload_w_setup=0,payload_x_setup=0,payload_cache_setup=0;
integer result_reads=0;reg[15:0]result_word_mask=0;
integer request_cycle=-1,accept_cycle=-1,end_cycle=-1,clear_first=-1,clear_last=-1;
real request_tick=-1,end_tick=-1;
integer mmio_outstanding=0;reg pending_result=0;
reg[31:0]pending_addr=0,pending_data=0;reg[3:0]pending_mask=0;reg pending_read=0;
reg activity_started=0,activity_stopped=0;
integer s_reads=0,s_writes=0,source_reads=0;
reg[31:0]first_source_addr;

task observe_clear_write;
 integer address;reg[4:0]mask;
 begin
  if(a_cmd_wmask!==4'hf || (^a_cmd_wdata)===1'bx)$fatal(1,"XU_MAPPED111_CLEAR_REJECT mask_or_unknown_data");
  if(clear_first<0)clear_first=cycles;clear_last=cycles;clear_writes=clear_writes+1;
  case(a_cmd_addr[11:0])
   12'h040:begin if(a_cmd_wdata!==0 || clear_disable!=0)$fatal(1,"XU_MAPPED111_CLEAR_REJECT cache_disable");clear_disable=clear_disable+1;end
   12'h01c:begin if(a_cmd_wdata>7)$fatal(1,"XU_MAPPED111_CLEAR_REJECT bank");bank_sel=a_cmd_wdata;end
   12'h020:begin if(a_cmd_wdata>2047)$fatal(1,"XU_MAPPED111_CLEAR_REJECT W_address");w_addr_sel=a_cmd_wdata;end
   12'h024:begin address=bank_sel*2048+w_addr_sel;if(bank_sel<0||w_addr_sel<0||a_cmd_wdata!==0||clear_w_seen[address])$fatal(1,"XU_MAPPED111_CLEAR_REJECT W_data_or_duplicate");clear_w_seen[address]=1;clear_w=clear_w+1;end
   12'h014:begin if(a_cmd_wdata>63)$fatal(1,"XU_MAPPED111_CLEAR_REJECT X_address");x_addr_sel=a_cmd_wdata;end
   12'h018:begin if(x_addr_sel<0||a_cmd_wdata!==0||clear_x_seen[x_addr_sel])$fatal(1,"XU_MAPPED111_CLEAR_REJECT X_data_or_duplicate");clear_x_seen[x_addr_sel]=1;clear_x=clear_x+1;end
   12'h044:begin if(a_cmd_wdata>255)$fatal(1,"XU_MAPPED111_CLEAR_REJECT bias_address");bias_sel=a_cmd_wdata;end
   12'h028:begin if(a_cmd_wdata>7)$fatal(1,"XU_MAPPED111_CLEAR_REJECT legacy_address");legacy_sel=a_cmd_wdata;end
   12'h048,12'h04c,12'h02c,12'h030:begin
    if(a_cmd_wdata!==0)$fatal(1,"XU_MAPPED111_CLEAR_REJECT bias_nonzero");
    mask=(a_cmd_addr[11:0]==12'h048 || a_cmd_addr[11:0]==12'h02c)?5'b01111:5'b10000;
    if(a_cmd_addr[11:0]==12'h048 || a_cmd_addr[11:0]==12'h04c)begin
     if(bias_sel<0 ||(clear_bias_seen[bias_sel]&mask)!=0)$fatal(1,"XU_MAPPED111_CLEAR_REJECT bias_duplicate");
     clear_bias_seen[bias_sel]=clear_bias_seen[bias_sel]|mask;if(clear_bias_seen[bias_sel]==31)clear_bias=clear_bias+1;
    end else begin
     if(legacy_sel<0 ||(clear_legacy_seen[legacy_sel]&mask)!=0)$fatal(1,"XU_MAPPED111_CLEAR_REJECT legacy_duplicate");
     clear_legacy_seen[legacy_sel]=clear_legacy_seen[legacy_sel]|mask;if(clear_legacy_seen[legacy_sel]==31)clear_legacy=clear_legacy+1;
    end
   end
   default:$fatal(1,"XU_MAPPED111_CLEAR_REJECT unexpected_write");
  endcase
 end
endtask

task observe_payload_write;
 integer i,column;reg[31:0]expected;reg[4:0]mask;
 begin
  if(a_cmd_wmask!==4'hf || (^a_cmd_wdata)===1'bx)$fatal(1,"XU_MAPPED111_UPLOAD_REJECT mask_or_unknown_data");
  case(a_cmd_addr[11:0])
   12'h054:begin if(a_cmd_wdata!==0||payload_w_setup!=0||payload_w_pairs!=0)$fatal(1,"XU_MAPPED111_UPLOAD_REJECT W_cursor");payload_w_setup=1;end
   12'h05c:begin
    if(payload_w_setup!=1||payload_w_pairs>=8192||payload_rows!=0)$fatal(1,"XU_MAPPED111_UPLOAD_REJECT W_pair_phase");
    for(i=0;i<2;i=i+1)begin column=2*payload_w_pairs+i;if(a_cmd_wdata[16*i+:16]!==w[column])$fatal(1,"XU_MAPPED111_UPLOAD_REJECT W_packed_data");end
    payload_w_pairs=payload_w_pairs+1;
   end
   12'h040:begin if(payload_w_pairs!=8192||payload_cache_setup>=2||a_cmd_wdata!==payload_cache_setup||payload_bias!=(payload_cache_setup==0?0:256))$fatal(1,"XU_MAPPED111_UPLOAD_REJECT cache_mode");payload_cache_setup=payload_cache_setup+1;end
   12'h044:begin if(a_cmd_wdata>255||payload_cache_setup!=1)$fatal(1,"XU_MAPPED111_UPLOAD_REJECT bias_cursor");bias_sel=a_cmd_wdata;end
   12'h048,12'h04c:begin
    if(bias_sel<0||payload_cache_setup!=1)$fatal(1,"XU_MAPPED111_UPLOAD_REJECT bias_phase");
    mask=a_cmd_addr[11:0]==12'h048 ?5'b01111:5'b10000;
    if((payload_bias_seen[bias_sel]&mask)!=0)$fatal(1,"XU_MAPPED111_UPLOAD_REJECT bias_duplicate");
    expected=a_cmd_addr[11:0]==12'h048 ?bias[bias_sel][31:0]:{24'b0,bias[bias_sel][39:32]};
    if(a_cmd_addr[11:0]==12'h048 ?a_cmd_wdata!==expected:a_cmd_wdata[7:0]!==expected[7:0])$fatal(1,"XU_MAPPED111_UPLOAD_REJECT bias_data");
    payload_bias_seen[bias_sel]=payload_bias_seen[bias_sel]|mask;if(payload_bias_seen[bias_sel]==31)payload_bias=payload_bias+1;
   end
   12'h060:begin if(a_cmd_wdata!==0||payload_cache_setup!=2||payload_x_setup!=payload_rows||payload_x_pairs!=payload_rows*32)$fatal(1,"XU_MAPPED111_UPLOAD_REJECT X_cursor");payload_x_setup=payload_x_setup+1;end
   12'h068:begin
    if(payload_x_setup!=payload_rows+1||payload_x_pairs>=3168||payload_x_pairs/32!=payload_rows)$fatal(1,"XU_MAPPED111_UPLOAD_REJECT X_pair_phase");
    if(a_cmd_wdata!=={x[payload_rows*64+2*(payload_x_pairs%32)+1],x[payload_rows*64+2*(payload_x_pairs%32)]})$fatal(1,"XU_MAPPED111_UPLOAD_REJECT X_packed_data");
    payload_x_pairs=payload_x_pairs+1;
   end
   12'h0c0:begin if(a_cmd_wdata!==1||payload_rows>=99||payload_x_pairs!=(payload_rows+1)*32||payload_pops!=payload_rows*32||result_word_mask!=0)$fatal(1,"XU_MAPPED111_UPLOAD_REJECT row_start");payload_rows=payload_rows+1;end
   12'h0c8:begin if(a_cmd_wdata!==1||result_word_mask!==16'hffff||payload_pops>=payload_rows*32)$fatal(1,"XU_MAPPED111_UPLOAD_REJECT row_pop");payload_pops=payload_pops+1;result_word_mask=0;end
   default:$fatal(1,"XU_MAPPED111_UPLOAD_REJECT unexpected_write");
  endcase
 end
endtask

task observe_mmio;
 integer index;reg[63:0]expected;
 begin
  if((^{a_cmd_valid,a_cmd_ready,a_rsp_valid,a_rsp_ready})===1'bx)$fatal(1,"XU_MAPPED111_PROTOCOL_REJECT unknown_MMIO_handshake");
  if(a_rsp_valid)begin
   if(mmio_outstanding!=1||a_rsp_err!==0)$fatal(1,"XU_MAPPED111_PROTOCOL_REJECT orphan_or_error_MMIO_response");
   if(pending_result)begin
    index=(pending_addr[11:0]-12'h100)/4;expected={16'b0,golden[(payload_pops/32)*256+(payload_pops%32)*8+index/2]};
    if(a_rsp_rdata!==(index%2?expected[63:32]:expected[31:0]))$fatal(1,"XU_MAPPED111_RESULT_REJECT MMIO_data");
   end
  end
  if(a_rsp_valid&&a_rsp_ready)begin
   if(pending_result)begin index=(pending_addr[11:0]-12'h100)/4;if(result_word_mask[index])$fatal(1,"XU_MAPPED111_RESULT_REJECT duplicate_word");result_word_mask[index]=1;result_reads=result_reads+1;end
   mmio_outstanding=0;pending_result=0;
  end
  if(a_cmd_valid&&a_cmd_ready)begin
   if(mmio_outstanding!=0 || (^{a_cmd_addr,a_cmd_read})===1'bx || a_cmd_addr<32'h10042000 || a_cmd_addr>=32'h10043000)$fatal(1,"XU_MAPPED111_PROTOCOL_REJECT outstanding_or_unknown_MMIO_command");
   mmio_outstanding=1;pending_addr=a_cmd_addr;pending_data=a_cmd_wdata;pending_mask=a_cmd_wmask;pending_read=a_cmd_read;
   if(!a_cmd_read)begin if(!activity_started)observe_clear_write();else if(!activity_stopped)observe_payload_write();else $fatal(1,"XU_MAPPED111_PROTOCOL_REJECT MMIO_write_after_window");end
   else if(!activity_started)begin if(a_cmd_addr[11:0]!=12'h000&&a_cmd_addr[11:0]!=12'h00c&&a_cmd_addr[11:0]!=12'h050&&a_cmd_addr[11:0]!=12'h070&&a_cmd_addr[11:0]!=12'h074&&a_cmd_addr[11:0]!=12'h078)$fatal(1,"XU_MAPPED111_CLEAR_REJECT unexpected_read");end
   else if(a_cmd_addr[11:0]>=12'h100&&a_cmd_addr[11:0]<=12'h13c&&a_cmd_addr[1:0]==0)pending_result=1;
   else if(a_cmd_addr[11:0]!=12'h0c4)$fatal(1,"XU_MAPPED111_UPLOAD_REJECT unexpected_task_MMIO_read");
  end
 end
endtask

task start_window;
 begin
  if(activity_started||activity_stopped||clear_writes!=33697||clear_disable!=1||clear_w!=16384||clear_x!=64||clear_bias!=256||clear_legacy!=8||clear_w_seen!=={16384{1'b1}}||clear_x_seen!==64'hffffffffffffffff||mmio_outstanding!=0)$fatal(1,"XU_MAPPED111_CLEAR_REJECT incomplete_public_clear_or_not_drained");
  if(a_reset_seen!=1||a_reset_ready!=1||a_reset_edges!=4594||a_rst_n!==1)$fatal(1,"XU_MAPPED111_RESET_REJECT actual_reset_sampling_differs");
  request_cycle=cycles;request_tick=$realtime*1000000.0;first_source_addr=cmd_addr;activity_started=1;
`ifdef XU_MAPPED111_CAPTURE
  $toggle_start();
`endif
  $display("XU_MAPPED111_SOURCE_REQUEST cycle=%0d tick=%0.0f clear_writes=33697 PUBLIC_CLEAR_ONLY_PHYSICAL_FF_GATE_PENDING",cycles,request_tick);
 end
endtask

task end_window;
 begin
  if(!activity_started||activity_stopped||payload_w_pairs!=8192||payload_x_pairs!=3168||payload_bias!=256||payload_rows!=99||payload_pops!=3168||result_reads!=50688||source_reads!=23232||result_word_mask!=0||mmio_outstanding!=0)$fatal(1,"XU_MAPPED111_WINDOW_REJECT incomplete_public_transaction_counts");
  end_cycle=cycles;end_tick=$realtime*1000000.0;activity_stopped=1;
`ifdef XU_MAPPED111_CAPTURE
  $toggle_stop();$toggle_report("mapped-task00.saif",1.0e-15,"tb_xu_soc_ppa.dut");
`endif
  $display("XU_MAPPED111_FINAL_Y_RETIRE cycle=%0d tick=%0.0f elapsed=%0d",cycles,end_tick,end_cycle-request_cycle);
  if(request_cycle!=1403985||accept_cycle!=1403985||end_cycle!=2394641||request_tick!=9359903333333.0||end_tick!=15964276666667.0||end_tick-request_tick!=6604373333334.0)$fatal(1,"XU_MAPPED111_WINDOW_REJECT frozen_task00_boundary_mismatch");
 end
endtask
