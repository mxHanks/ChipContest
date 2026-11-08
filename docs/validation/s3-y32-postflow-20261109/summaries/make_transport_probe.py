from pathlib import Path
import subprocess,tarfile,io,json
root=Path('/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest'); b=root/'build/postflow-20261108';repo=b/'transport-observed-repo';repo.mkdir(exist_ok=False)
for src,dest in [(root,repo),(root/'third-party/e203_hbirdv2',repo/'third-party/e203_hbirdv2')]:
 dest.mkdir(parents=True,exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive','HEAD'],cwd=src))) as t:t.extractall(dest,filter='data')
p=repo/'tests/e203/tb_accel_soc.sv';s=p.read_text()
anchor='  task report_performance;'
assert s.count(anchor)==1
probe='''  // Passive diagnostic: no DUT or fabric input is driven.
  integer diag_state_cycles[0:15];
  integer diag_i;
  initial for(diag_i=0;diag_i<16;diag_i=diag_i+1) diag_state_cycles[diag_i]=0;
  integer diag_y_commands=0,diag_y_responses=0,diag_y_service_sum=0;
  integer diag_y_service_min=999999,diag_y_service_max=0,diag_y_pending=0,diag_y_accept=0;
  integer diag_bias_wait=0,diag_free_slot_wait=0,diag_claim_cycles=0,diag_bundle_hold=0;
  integer diag_y_cmd_stall=0,diag_y_rsp_stall=0;
  task observe_transport_diagnostic;
    integer latency;
    begin
      diag_state_cycles[`NICE.u_drain8.state]=diag_state_cycles[`NICE.u_drain8.state]+1;
      if(`ACCEL.row_active && !`ACCEL.row_running && `ACCEL.row_produced<32 && `ACCEL.row_count<2 &&
          !`ACCEL.u_linear_compute_core.biasReady) diag_bias_wait=diag_bias_wait+1;
      if(`ACCEL.row_active && !`ACCEL.row_running && `ACCEL.row_produced<32 && `ACCEL.row_count==2)
        diag_free_slot_wait=diag_free_slot_wait+1;
      if(`ACCEL.xu_direct_claim) diag_claim_cycles=diag_claim_cycles+1;
      if(`ACCEL.xu_direct_valid && !`ACCEL.xu_direct_ready) diag_bundle_hold=diag_bundle_hold+1;
      if(diag_y_pending && rsp_valid && !rsp_ready) diag_y_rsp_stall=diag_y_rsp_stall+1;
      if(diag_y_pending && rsp_valid && rsp_ready) begin
        latency=cycles-diag_y_accept+1;
        diag_y_service_sum=diag_y_service_sum+latency;
        if(latency<diag_y_service_min)diag_y_service_min=latency;
        if(latency>diag_y_service_max)diag_y_service_max=latency;
        diag_y_responses=diag_y_responses+1;diag_y_pending=0;
      end
      if(cmd_valid && !cmd_read && cmd_addr>=BASE+YOFF && cmd_addr<BASE+YOFF+25344*4) begin
        if(!cmd_ready)diag_y_cmd_stall=diag_y_cmd_stall+1;
        if(cmd_ready)begin
          if(diag_y_pending)$fatal(1,"diagnostic observed overlapping Y requests");
          diag_y_commands=diag_y_commands+1;diag_y_pending=1;diag_y_accept=cycles;
        end
      end
    end
  endtask
'''
s=s.replace(anchor,probe+anchor)
anchor='        perf_active=1;';assert s.count(anchor)==1
s=s.replace(anchor,anchor+'\n        observe_transport_diagnostic();')
anchor='      $display("PERF_TASK layer='
assert s.count(anchor)==1
report='''      if(diag_y_commands!=25344 || diag_y_responses!=25344 || diag_y_pending)
        $fatal(1,"transport diagnostic omitted Y responses");
      $display("TRANSPORT_DIAGNOSTIC layer=%0d y_commands=%0d y_responses=%0d y_service_sum=%0d y_service_min=%0d y_service_max=%0d y_command_stall=%0d y_response_stall=%0d bias_wait_free_slot=%0d fifo_full_wait=%0d claim_cycles=%0d bundle_hold=%0d",
        layer,diag_y_commands,diag_y_responses,diag_y_service_sum,diag_y_service_min,diag_y_service_max,
        diag_y_cmd_stall,diag_y_rsp_stall,diag_bias_wait,diag_free_slot_wait,diag_claim_cycles,diag_bundle_hold);
      for(diag_i=0;diag_i<16;diag_i=diag_i+1)
        $display("NICE_STATE_DIAGNOSTIC layer=%0d state=%0d cycles=%0d",layer,diag_i,diag_state_cycles[diag_i]);
'''
s=s.replace(anchor,report+anchor)
# Establish the actual instance name from the frozen subsystem source.
nice=(repo/'third-party/e203_hbirdv2/rtl/e203/subsys/e203_subsys_nice_core.v').read_text()
assert 'u_drain8' in nice
p.write_text(s)
print(repo)
