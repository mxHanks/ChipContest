#!/usr/bin/env python3
"""xu prepared mapped task00 public diagnostic. Required private-state gates fail.

Never changes original capture/source/firmware/vectors/netlist/model files.
The diagnostic cannot emit complete SOC_PASS or qualification PASS because the
original physical FF/FIFO/clock-control observations lack mapped state adapters.
"""
import argparse,hashlib,json,re,shutil,subprocess,time,os,signal,traceback,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TB_SHA='d39016ea50fafe7df8c97dd209702fbc3c4e7eb0e2bb8fded570e427fde6d850'
CONFIG='5b5cf619e8b0e5c2fc050abe8b589d5f7544a98eed174f4fc979bffe60fa6018'
NET='9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
INV='721ce0773570c54a8757a32165a47f399cd5c1ee9e3a57eab612dbeeeea15d8d'
LIB='9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581'
RAM='81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51'
def need(ok,msg):
 if not ok:raise ValueError(msg)
def identity(path):
 original=Path(os.path.abspath(str(path)));p=original.resolve(strict=True)
 before=p.stat();h=hashlib.sha256()
 with p.open('rb')as f:
  while True:
   data=f.read(1024*1024)
   if not data:break
   h.update(data)
 after=p.stat()
 need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'input changed while hashing: '+str(original))
 return dict(input_path=str(original),path=str(p),bytes=before.st_size,sha256=h.hexdigest(),device=before.st_dev,inode=before.st_ino,mtime_ns=before.st_mtime_ns,ctime_ns=before.st_ctime_ns)
def dump(path,value):
 p=Path(path);temporary=p.with_name(p.name+'.tmp');temporary.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n');os.replace(str(temporary),str(p))
def generated_tb(original,observer):
 clock=original[original.index('  initial forever begin'):original.index('  wire cmd_valid')]
 pads=re.findall(r'  xu_soc_ppa_top dut \(.*?\n  \);',original,re.S);need(len(pads)==1,'original exact pad instance differs')
 prefix='''`timescale 1ns/1fs
module tb_xu_soc_ppa;
 reg clk=0,lfclk=0,rst_n=0;
 integer xu_half_index=0,xu_reset_edges=0,xu_static_checks=0;
 real xu_target_ns;
 always @(posedge clk)begin if(!rst_n)xu_reset_edges=xu_reset_edges+1;else xu_static_checks=xu_static_checks+1;end
'''
 declarations='''
 reg cmd_valid,cmd_ready,cmd_read,rsp_valid,rsp_ready,rsp_err;
 reg[31:0]cmd_addr,cmd_wdata,rsp_rdata;reg[3:0]cmd_wmask;
 reg a_cmd_valid,a_cmd_ready,a_cmd_read,a_rsp_valid,a_rsp_ready,a_rsp_err,a_clk,a_rst_n;
 reg[31:0]a_cmd_addr,a_cmd_wdata,a_rsp_rdata;reg[3:0]a_cmd_wmask;
 integer a_reset_edges=0,a_reset_seen=0,a_reset_ready=0;
 reg[31:0]ram[0:131071];reg[15:0]x[0:6335],w[0:16383];reg[39:0]bias[0:255];reg[47:0]golden[0:25343];
 reg[7:0]program_bytes[0:65535];reg[63:0]xu_program_words[0:8191];
 string testcase,vectors;integer tasks,xu_global_task,cycles=0,max_cycles,writes=0,completed=0,outstanding=0,firmware_cycles=0;
 reg final_write_pending=0;localparam BASE=32'ha0000000,YOFF=32'h20000,HOST=32'h7f000;
'''
 initialize='''
 initial begin:initialize
  integer i;string directory;
  if(!$value$plusargs("TESTCASE=%s",testcase)||!$value$plusargs("VECTORS=%s",vectors)||!$value$plusargs("TASKS=%d",tasks)||!$value$plusargs("XU_GLOBAL_TASK=%d",xu_global_task)||tasks!=1||xu_global_task!=0)$fatal(1,"XU_MAPPED111_REJECT only_frozen_task00");
  if(!$value$plusargs("MAX_CYCLES=%d",max_cycles))max_cycles=4000000;
  for(i=0;i<256;i=i+1)begin clear_bias_seen[i]=0;payload_bias_seen[i]=0;end
  for(i=0;i<8;i=i+1)clear_legacy_seen[i]=0;
  $xu_mapped111_prepare();
  #1;
  for(i=0;i<65536;i=i+1)program_bytes[i]=0;
  $readmemh({testcase,".verilog"},program_bytes);
  for(i=0;i<8192;i=i+1)xu_program_words[i]={program_bytes[8*i+7],program_bytes[8*i+6],program_bytes[8*i+5],program_bytes[8*i+4],program_bytes[8*i+3],program_bytes[8*i+2],program_bytes[8*i+1],program_bytes[8*i]};
  directory={vectors,"/layer_00/"};
  $readmemh({directory,"x.mem"},x);$readmemh({directory,"w.mem"},w);$readmemh({directory,"bias.mem"},bias);$readmemh({directory,"y.mem"},golden);
  ram[HOST/4]=tasks;
  for(i=0;i<6336;i=i+1)ram[i]={16'b0,x[i]};
  for(i=0;i<16384;i=i+1)ram['h8000/4+i]={16'b0,w[i]};
  for(i=0;i<256;i=i+1)begin ram['h18000/4+2*i]=bias[i][31:0];ram['h18000/4+2*i+1]={{24{bias[i][39]}},bias[i][39:32]};end
  for(i=0;i<50688;i=i+1)ram[YOFF/4+i]=32'hdeadbeef;
  $xu_mapped111_preload();
  #(200-$realtime);if(xu_reset_edges!=30)$fatal(1,"XU_MAPPED111_RESET_REJECT nominal_HF_edge_count");rst_n=1;
  $display("XU_MAPPED111_INITIAL_FIXED pads_original=1 HF150=1 LF32768=1 reset200ns=1 init_only_ITCM_SHARED=1 Q_init=0 OTHER_DUT_FF_init=0");
 end
 always @(posedge clk)begin:public_scoreboard
  integer offset,word_index;reg[63:0]expected;
  cycles<=cycles+1;
  $xu_mapped111_sample();
  if(cycles>max_cycles)$fatal(1,"XU_MAPPED111_TIMEOUT writes=%0d",writes);
  if(cycles>0&&cycles%1000000==0)begin $display("XU_MAPPED111_PROGRESS cycles=%0d writes=%0d",cycles,writes);$fflush();end
  if(rst_n)begin
   if(a_reset_ready==1)begin
    if(a_rst_n!==1)$fatal(1,"XU_MAPPED111_RESET_REJECT reset_unknown_or_reasserted");
    if((^{cmd_valid,cmd_ready,rsp_valid,rsp_ready})===1'bx)$fatal(1,"XU_MAPPED111_PROTOCOL_REJECT unknown_shared_handshake");
    observe_mmio();
   end else if(a_cmd_valid===1 ||(cmd_valid===1&&cmd_read===1&&cmd_addr>=BASE&&cmd_addr<BASE+'h18800))$fatal(1,"XU_MAPPED111_RESET_REJECT source_before_actual_reset_ready");
   if(cmd_valid===1&&cmd_read===1&&cmd_addr>=BASE&&cmd_addr<BASE+'h18800&&request_cycle<0)start_window();
   if(request_cycle>=0&&accept_cycle<0)begin
    if(cmd_valid!==1||cmd_read!==1||cmd_addr!==first_source_addr)$fatal(1,"XU_MAPPED111_PROTOCOL_REJECT first_request_changed_before_accept");
    if(cmd_ready===1)accept_cycle=cycles;
   end
   if(rsp_valid===1)begin if(outstanding!=1||rsp_err!==0)$fatal(1,"XU_MAPPED111_PROTOCOL_REJECT shared_orphan_or_error");end
   if(rsp_valid===1&&rsp_ready===1)begin
    outstanding=outstanding-1;
    if(final_write_pending)begin final_write_pending=0;end_window();end
   end
   if(cmd_valid===1&&cmd_ready===1)begin
    if((^{cmd_addr,cmd_read,cmd_wmask})===1'bx||cmd_addr<BASE||cmd_addr>=BASE+'h80000||cmd_addr[1:0]!=0)$fatal(1,"XU_MAPPED111_PROTOCOL_REJECT shared_unknown_or_bad_address");
    outstanding=outstanding+1;if(outstanding!=1)$fatal(1,"XU_MAPPED111_PROTOCOL_REJECT shared_outstanding");offset=cmd_addr-BASE;word_index=offset/4;
    if(cmd_read)begin s_reads=s_reads+1;if(offset<'h18800)source_reads=source_reads+1;end
    else begin
     s_writes=s_writes+1;
     if(cmd_wmask!==4'hf)$fatal(1,"XU_MAPPED111_PROTOCOL_REJECT partial_shared_write");
     if(offset>=YOFF&&offset<YOFF+50688*4)begin
      if(offset!=YOFF+writes*4)$fatal(1,"XU_MAPPED111_GOLDEN_REJECT write_order");expected={{16{golden[writes/2][47]}},golden[writes/2]};
      if(cmd_wdata!==(writes%2?expected[63:32]:expected[31:0]))$fatal(1,"XU_MAPPED111_GOLDEN_REJECT data word=%0d got=%h",writes,cmd_wdata);
      ram[word_index]=cmd_wdata;writes=writes+1;if(writes==50688)final_write_pending=1;
     end else if(offset==HOST+8)firmware_cycles=cmd_wdata;
     else if(offset==HOST+4)begin
      if(cmd_wdata!==1||writes!=50688||final_write_pending||!activity_stopped||outstanding!=1)$fatal(1,"XU_MAPPED111_GOLDEN_REJECT premature_public_HOST_ACK");
      completed=1;
      $display("XU_MAPPED111_PUBLIC_DIAGNOSTIC_COMPLETE tasks=1 outputs=25344 writes=50688 w_pairs=%0d x_pairs=%0d rows=%0d pops=%0d result_reads=%0d source_reads=%0d elapsed_cycles=%0d NOT_FULL_FUNCTIONAL_OR_ACTIVITY_OR_ENERGY_QUALIFIED",payload_w_pairs,payload_x_pairs,payload_rows,payload_pops,result_reads,source_reads,end_cycle-request_cycle);
      // Required original private observations are NOT silently deleted.
      // An interface-only clear is never promoted to physical FF/FIFO proof.
      $fatal(1,"XU_MAPPED111_REQUIRED_GATE_PENDING physical_X_bias_FF_clear FIFO_ownership_PLL_controls_EXU_FM_state_adapter missing_native_warning_review conditional_SRAM_energy_unknownQ");
     end else $fatal(1,"XU_MAPPED111_PROTOCOL_REJECT unexpected_shared_write");
    end
   end
   if(outstanding<0||outstanding>1)$fatal(1,"XU_MAPPED111_PROTOCOL_REJECT shared_outstanding_count");
   // Native endpoint backpressure phase must match the original live cycle.
   if(a_reset_ready==1&&cmd_ready!==((!rsp_valid||rsp_ready)&&(cycles%7!=0)))$fatal(1,"XU_MAPPED111_PROTOCOL_REJECT original_shared_backpressure_phase");
  end
 end
endmodule
'''
 text=prefix+clock+declarations+observer+'\n'+pads[0]+'\n'+initialize
 need(not re.search(r'`(?:ACCEL|EXU|CPU|ITCM|XU_HCLK)\b|dut\.[A-Za-z_]\w*\.',text),'unadapted private hierarchical signal remains')
 need('SOC_PASS'not in text and 'XU_MAPPED111_REQUIRED_GATE_PENDING'in text,'private-state gate must prevent complete functional qualification')
 return text

PUBLIC_STATUS='PUBLIC_TASK00_DIAGNOSTIC_COMPLETE_REQUIRED_PRIVATE_GATE_FAILED'
FAIL_STATUS='FAIL_PUBLIC_DIAGNOSTIC_NOT_QUALIFIED'
FW='919df46282e114317e2cbf30d7606f67ec2e00a7e3c22803aa14bfb360b0a128'
TASK00_MANIFEST='f43b656edc75548dbd0bf577266e2a29183f2e31fbb208c3dd7a096f03b5d9a6'
PRIMITIVE_STATUS='EXECUTED_READONLY_GEOMETRY_VENDOR_VPI_PRELOAD_AND_TWO_REJECTIONS_NOT_FULL_SOC_ACTIVITY_OR_ENERGY'
PUBLIC_LINE=re.compile(r'^XU_MAPPED111_PUBLIC_DIAGNOSTIC_COMPLETE tasks=1 outputs=25344 writes=50688 w_pairs=8192 x_pairs=3168 rows=99 pops=3168 result_reads=50688 source_reads=(\d+) elapsed_cycles=990656 NOT_FULL_FUNCTIONAL_OR_ACTIVITY_OR_ENERGY_QUALIFIED$',re.M)
PENDING_TEXT='XU_MAPPED111_REQUIRED_GATE_PENDING physical_X_bias_FF_clear FIFO_ownership_PLL_controls_EXU_FM_state_adapter missing_native_warning_review conditional_SRAM_energy_unknownQ'

def classify_public_log(raw,returncode):
 text=raw.decode('utf-8',errors='replace')
 markers=list(PUBLIC_LINE.finditer(text));pending=[]
 for row in text.splitlines():
  stripped=row.strip()
  if stripped==PENDING_TEXT or re.match(r'^(?:FATAL|Fatal):[^\n]*:\s*'+re.escape(PENDING_TEXT)+r'$',stripped):pending.append(row)
 need(returncode!=0,'required private gate unexpectedly returned zero')
 need(len(markers)==1 and len(re.findall(r'^XU_MAPPED111_PUBLIC_DIAGNOSTIC_COMPLETE\b',text,re.M))==1 and len(pending)==1 and text.count('XU_MAPPED111_REQUIRED_GATE_PENDING')==1,'unique complete public diagnostic and exact pending-private failure missing')
 required=[
 'XU_MAPPED111_ADAPTER_READY macros=336 interface_bits_preserve_4state=1 preload_allowed=288 Q_WRITES=0 OTHER_DUT_FF_WRITES=0',
 'XU_MAPPED111_PRELOAD_DONE itcm=32 shared=256 words_per_macro=256 bits_per_row=64 arbitrary_XZ_preserved=1 Q_WRITES=0',
 'XU_MAPPED111_SOURCE_REQUEST cycle=1403985 tick=9359903333333 clear_writes=33697 PUBLIC_CLEAR_ONLY_PHYSICAL_FF_GATE_PENDING',
 'XU_MAPPED111_FINAL_Y_RETIRE cycle=2394641 tick=15964276666667 elapsed=990656']
 positions=[]
 for line in required:
  matches=list(re.finditer('^'+re.escape(line)+'$',text,re.M));need(len(matches)==1,'exact unique actual public boundary/preload marker missing');positions.append(matches[0].start())
 positions.extend([markers[0].start(),text.index(pending[0])]);need(positions==sorted(positions)and len(set(positions))==len(positions),'actual public diagnostic markers out of order')
 geometry=list(re.finditer(r'^XU_MAPPED111_GEOMETRY tag=(\d+) role=([012]) status=PASS rows=256 row_bits=64 unique=256 memory_type=(29|116) reg_words=(\d+) memoryword_words=(\d+) parent_present=(\d+) scope_present=(\d+) index_present=(\d+) name=(\S+)$',text,re.M))
 need(len(geometry)==336 and sorted(int(r.group(1))for r in geometry)==list(range(336)),'each mapped macro needs its own actual full256-row native geometry proof')
 need(sum(r.group(2)=='1'for r in geometry)==32 and sum(r.group(2)=='2'for r in geometry)==256 and len(set(r.group(9)for r in geometry))==336,'actual full macro ownership/roles differ')
 for row in geometry:need(int(row.group(4))+int(row.group(5))==256 and all(0<=int(row.group(i))<=256 for i in [6,7,8]),'actual full macro native type/optional metadata totals differ')
 need(max(r.start()for r in geometry)<positions[0],'actual geometry must precede adapter/preload readiness')
 need('SOC_PASS'not in text and re.search(r'XU_MAPPED111_[A-Z_]*(?:REJECT|TIMEOUT)\b',text)is None,'unexpected full-pass/rejection in public diagnostic')
 need(int(markers[0].group(1))==23232,'frozen full X/W/bias source-read count differs')
 return dict(public_diagnostic_marker_count=1,required_gate_failure_count=1,source_reads=int(markers[0].group(1)),functional_qualification='NOT_QUALIFIED',status=PUBLIC_STATUS)

class EvidenceRun:
 """Records real child handles and fails closed on errors and input changes."""
 def __init__(self,out):
  self.out=Path(out).resolve();self.out.mkdir(parents=True,exist_ok=False)
  self.state=dict(status='RUNNING_PREPARATION',qualification='NOT_QUALIFIED',scope='PUBLIC_TASK00_DIAGNOSTIC_WITH_60_REQUIRED_PRIVATE_PATHS_PENDING',pid=os.getpid(),started_epoch=time.time(),inputs_before=[],steps=[],runtime_trees=[])
  self.inputs={};self.save()
 def save(self):dump(self.out/'state.json',self.state)
 def freeze(self,path):
  row=identity(path);key=row['input_path']
  if key in self.inputs:need(self.inputs[key]==row,'previously frozen input changed: '+key)
  else:self.inputs[key]=row;self.state['inputs_before']=list(self.inputs.values());self.save()
  return row
 def freeze_tree(self,path):
  root=Path(os.path.abspath(str(path)))
  need(root.is_dir(),'runtime tree absent: '+str(root))
  names=sorted(str(p.absolute())for p in root.rglob('*')if p.is_file())
  for name in names:self.freeze(name)
  self.state['runtime_trees'].append(dict(root=str(root),files=names));self.save()
 def _stop(self,p,row,reason):
  row['termination_reason']=reason;row['termination_signals']=[]
  # start_new_session=True established this dedicated process group. Signal it
  # even if its leader just exited: native compiler/simulator descendants may
  # still own the same group and must not survive interruption/timeout.
  try:os.killpg(p.pid,signal.SIGTERM);row['termination_signals'].append('SIGTERM')
  except ProcessLookupError:pass
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:pass
  try:os.killpg(p.pid,signal.SIGKILL);row['termination_signals'].append('SIGKILL')
  except ProcessLookupError:pass
  p.wait(timeout=5);row['termination_returncode']=p.returncode
 def step(self,name,command,timeout,require_zero=True):
  log=self.out/(name+'.log');row=dict(name=name,command=list(command),timeout_seconds=timeout,status='STARTING',started_epoch=time.time());self.state['steps'].append(row);self.state['status']='RUNNING_CHILD';self.save();p=None
  try:
   with log.open('xb')as f:
    try:
     p=subprocess.Popen(command,cwd=str(self.out),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
     row.update(status='RUNNING',pid=p.pid,process_group=p.pid);self.save()
     code=p.wait(timeout=timeout);row.update(returncode=code,status='EXITED')
    except BaseException as exc:
     if p is not None:
      try:self._stop(p,row,type(exc).__name__)
      except BaseException as stop_error:row['cleanup_error']=type(stop_error).__name__+': '+str(stop_error)
     f.write(traceback.format_exc().encode('utf-8',errors='backslashreplace'));row.update(status='EXCEPTION',error=type(exc).__name__+': '+str(exc));raise
  finally:
   row['finished_epoch']=time.time()
   if log.exists():row['log']=identity(log)
   self.save()
  if require_zero:need(code==0,'native child failed: '+name+' returncode='+str(code))
  return code,log.read_bytes()
 def __enter__(self):return self
 def __exit__(self,kind,value,tb):
  identity_errors=[];after=[]
  if value is not None:
   self.state.update(status=FAIL_STATUS,error=dict(type=kind.__name__,message=str(value),traceback=''.join(traceback.format_exception(kind,value,tb))))
  for path,before in self.inputs.items():
   try:
    row=identity(path);after.append(row)
    if row!=before:identity_errors.append(dict(path=path,error='INPUT_IDENTITY_CHANGED'))
   except BaseException as exc:identity_errors.append(dict(path=path,error=type(exc).__name__+': '+str(exc)))
  for tree in self.state['runtime_trees']:
   current=sorted(str(p.absolute())for p in Path(tree['root']).rglob('*')if p.is_file())
   if current!=tree['files']:identity_errors.append(dict(path=tree['root'],error='RUNTIME_TREE_MEMBERS_CHANGED',files_after=current))
  self.state['inputs_after']=after;self.state['identity_errors']=identity_errors
  self.state['inputs_equal_before_after']=not identity_errors
  if identity_errors:
   self.state['status']=FAIL_STATUS
   if value is None:self.state['error']=dict(type='ValueError',message='frozen input identity verification failed')
  self.state['finished_epoch']=time.time();self.save()
  if value is None and identity_errors:raise ValueError('frozen input identity verification failed; state.json preserves details')
  return False

def verify_preload_proof(path,run):
 """Accept actual105 raw execution evidence, never an arbitrary PASS receipt."""
 root=Path(path).resolve();state_path=root/'state.json';run.freeze(state_path);proof=json.loads(state_path.read_text())
 need(proof.get('status')==PRIMITIVE_STATUS,'actual preload105 terminal success missing')
 before=proof.get('input_sha256_before');after=proof.get('input_sha256_after')
 need(isinstance(before,dict)and len(before)==7 and before==after,'preload105 immutable seven-input proof missing')
 need(RAM in before.values()and'40586e4c46e1ee52f8cdf50dc4f681b5fdb4b4ffa8f1d48d179b868b23facc83'in before.values(),'actual original vendor105/launcher identity missing')
 for name,sha in before.items():need(run.freeze(name)['sha256']==sha,'preload105 actual input no longer matches: '+name)
 cases=proof.get('cases',[]);names=['diagnostic_only','reference','wrong_bit_column_packing','swapped_handle_tags']
 expected_codes=['9d8cca663a9d1a19d2fcf6f111eb1c63fac9c95087b37f39f6171749b98b2587']*2+['b5526463957d0d818f1308f34bea621bd04961e7eb32a6aae935a96f6c85e1a2','d5638f269e162357b65353791d230805af5f5e36e817d0ea066a0b37d74039bd']
 need([r.get('name')for r in cases]==names,'preload105 four actual cases missing or reordered')
 for i,row in enumerate(cases):
  expected=i<2;need(row.get('code_sha256')==expected_codes[i]and row.get('testbench_sha256')=='71204ce4815d393e731742599458144a694273fb1594191828a717c949bb0403','actual105 checked source identity differs');need(row.get('expected_pass')is expected and row.get('actual_pass')is expected,'preload105 actual case outcome differs')
  directory=root/row['name'];need(run.freeze(directory/'probe.c')['sha256']==row['code_sha256'],'preload105 case C changed');need(run.freeze(directory/'tb.sv')['sha256']==row['testbench_sha256'],'preload105 case TB changed')
  steps=row.get('runs',[]);need(len(steps)==3 and [r['command']['name']for r in steps]==['cc','vcs','sim'],'preload105 actual compile/run steps missing')
  for index,step in enumerate(steps):
   native=directory/(step['command']['name']+'.log');need(run.freeze(native)['sha256']==step['log_sha256'],'preload105 raw log changed')
   if index<2:need(step['returncode']==0,'preload105 mutant/reference was not compiled')
  log=(directory/'sim.log').read_text(errors='replace')
  if i==0:
   need(steps[-1]['returncode']==0 and log.count('XU_PRIMITIVE105_DIAGNOSTIC status=PASS')==1 and log.count('role=indexed_word ')==512 and 'XU_PRIMITIVE105_PRELOAD'not in log and 'writes=0'in log and 'XU_PRIMITIVE105_ERROR'not in log,'preload105 read-only native geometry incomplete')
  elif i==1:
   need(steps[-1]['returncode']==0 and log.count('XU_PRIMITIVE105_RESULT status=PASS')==1 and log.count('XU_PRIMITIVE105_READ ')==8 and log.count('XU_PRIMITIVE105_PRELOAD ')==2 and log.count('XU_PRIMITIVE105_EDGES ')==2 and 'XU_PRIMITIVE105_ERROR'not in log,'preload105 vendor readback/hold/edges incomplete')
  else:need('XU_PRIMITIVE105_ERROR'in log and 'XU_PRIMITIVE105_RESULT status=PASS'not in log,'preload105 negative lacks actual rejection')
 run.state['preload_proof']=dict(root=str(root),state=identity(state_path),status=proof['status'],scope='NATIVE_TWO_MACRO_PRIMITIVE_ONLY_NOT_FULL_SOC_OR_ENERGY');run.save()

def work(a,run):
 out=run.out;capture=a.capture.resolve()
 # Freeze source provenance before reading/transforming it.
 for source in [Path(__file__),ROOT/'xu_mapped_task00_vpi111.c',ROOT/'xu_public_observer111.svh',capture/'result.json',capture/'simulator/tb_xu_s2c_task_activity.sv',a.inventory]:run.freeze(source)
 activity=json.loads((capture/'result.json').read_text());tb=capture/'simulator/tb_xu_s2c_task_activity.sv'
 need(identity(tb)['sha256']==TB_SHA,'exact original generated TB differs')
 need(activity['configuration_sha256']==CONFIG and hashlib.sha256(json.dumps(activity['configuration'],sort_keys=True,separators=(',',':')).encode()).hexdigest()==CONFIG,'original capture configuration differs')
 need(identity(a.inventory)['sha256']==INV,'exact mapped macro inventory differs');inv=json.loads(a.inventory.read_text());need(inv['netlist']['sha256']==NET,'inventory actual mapped identity differs')
 original=tb.read_text();observer=(ROOT/'xu_public_observer111.svh').read_text();generated=generated_tb(original,observer)
 (out/'tb_xu_mapped_task00111.sv').write_text(generated);(out/'xu_mapped_task00_vpi111.c').write_bytes((ROOT/'xu_mapped_task00_vpi111.c').read_bytes())
 records=[]
 for row in inv['macros']:
  name=row['instance'];role=0;bank=lane=0
  if name.startswith('u_shared/')or'/u_e203_itcm_ram/'in name:
   pair=re.search(r'depth_bank\[(\d+)\]\.width_lane\[(\d+)\]\.macro$',name);need(pair,'original preload macro geometry differs');bank,lane=map(int,pair.groups());role=2 if name.startswith('u_shared/')else 1
   need((role==1 and 0<=bank<8 and 0<=lane<4)or(role==2 and 0<=bank<128 and 0<=lane<2),'original preload bank/lane range differs')
  records.append(dict(name='tb_xu_soc_ppa.dut.'+name.replace('/','.'),role=role,bank=bank,lane=lane))
 need(len(records)==336 and len(set(r['name']for r in records))==336 and sum(r['role']==1 for r in records)==32 and sum(r['role']==2 for r in records)==256,'mapped preload exact32+256 geometry differs')
 need(len(set((r['role'],r['bank'],r['lane'])for r in records if r['role']))==288,'preload roles/banks/lanes alias')
 header='struct xu_expected111_t {const char *name;int role;int bank;int lane;};\nstatic const struct xu_expected111_t xu_expected111[336]={\n'+',\n'.join('{%s,%d,%d,%d}'%(json.dumps(r['name']),r['role'],r['bank'],r['lane'])for r in records)+'\n};\n';(out/'xu_mapped_expected111.h').write_text(header)
 dependencies={key:sorted(set(re.findall('`'+key+r'\.([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)',original)))for key in ['ACCEL','EXU','XU_HCLK']};adapter=[]
 for category,names in dependencies.items():
  for name in names:
   if category=='ACCEL'and name in ['cmd_valid','cmd_ready','cmd_addr','cmd_read','cmd_wdata','cmd_wmask','rsp_valid','rsp_ready','rsp_rdata','rsp_err','clk','rst_n']:handling='VPI actual named module public port; four-state preserved'
   elif category=='EXU':handling='Required private state adapter pending; public HOST+4 diagnostic stop cannot discharge original EXU check'
   elif category=='XU_HCLK':handling='Required private clock-control state mapping pending; original HF/LF/pads preserved only'
   else:handling='Required physical commit/FIFO/stream state adapter pending; MMIO transcript/golden is interface evidence only'
   adapter.append(dict(original_macro=category,original_path=name,handling=handling))
 need(len(adapter)==72 and sum('pending'in r['handling']for r in adapter)==60,'all60 original private scope gaps must remain explicit')
 dump(out/'private-reference-adapter-plan.json',dict(original_references=adapter,original_preload_statements=288,replacement='VPI checked native mem words only, original packed4-state data',qualification_gate='Mandatory final $fatal;60 required private state paths remain pending; no bypass option'))
 for path in [out/'tb_xu_mapped_task00111.sv',out/'xu_mapped_task00_vpi111.c',out/'xu_mapped_expected111.h',out/'private-reference-adapter-plan.json']:run.freeze(path)
 run.state.update(original_tb=identity(tb),original_capture_configuration_sha256=CONFIG,mapped_inventory=identity(a.inventory),original_task00_window=activity['tasks'][0]['activity_window'],original_firmware_build=activity['firmware_build'],task00_input_manifest=activity['tasks'][0]['input_manifest'],private_reference_count=72,private_pending_count=60,memory_preload=dict(itcm=32,shared=256,no_other_DUT_state_writes=True,preserves_XZ=True),capture_mode='disabled; native gate-monitor and macro joint/unknown-Q model require separate proof')
 run.save()
 if not a.run_vcs:
  run.state['status']='PREPARED_PUBLIC_TASK00_DIAGNOSTIC_60_REQUIRED_PRIVATE_GATES_PENDING';return
 need(a.mapped and a.vendor and a.standard and a.vpi_include and a.preload_proof,'run requires actual mapped/vendor/standard/VCS SDK and successful actual preload105 proof')
 verify_preload_proof(a.preload_proof,run)
 need([run.freeze(x)['sha256']for x in [a.mapped,a.vendor,a.standard]]==[NET,RAM,LIB],'exact actual mapped/model source differs')
 fw=activity['firmware_build']['image'];need(fw['sha256']==FW and run.freeze(fw['path'])['sha256']==FW,'original frozen firmware image changed')
 reference=activity['tasks'][0]['input_manifest'];manifest_path=reference['path'];need(reference['sha256']==TASK00_MANIFEST and run.freeze(manifest_path)['sha256']==TASK00_MANIFEST,'original frozen task00 manifest changed');manifest=json.loads(Path(manifest_path).read_text())
 for tensor in manifest['files']:
  for role in ['materialized','original']:need(run.freeze(tensor[role]['path'])['sha256']==tensor[role]['sha256'],'original tensor bytes changed')
 cc=shutil.which('gcc');need(cc,'native gcc missing');run.freeze(cc);run.freeze(a.run_vcs)
 headers=sorted(a.vpi_include.resolve().rglob('*.h'));need((a.vpi_include/'vpi_user.h').is_file()and headers,'native VPI SDK headers missing')
 for header in headers:run.freeze(header)
 library=out/'adapter.so';command=[cc,'-std=gnu99','-fPIC','-shared','-Wall','-Wextra','-Werror','-isystem',str(a.vpi_include.resolve()),'-I'+str(out),str(out/'xu_mapped_task00_vpi111.c'),'-o',str(library)]
 filelist=out/'mapped.f';filelist.write_text('\n'.join(str(Path(x).resolve())for x in [a.mapped,a.vendor,a.standard,out/'tb_xu_mapped_task00111.sv'])+'\n');run.freeze(filelist)
 run.step('vpi-build',command,1800);run.freeze(library)
 vcs=[str(a.run_vcs.resolve()),'-full64','-sverilog','-timescale=1ns/1fs','-top','tb_xu_soc_ppa','-debug_access+all','-debug_region+cell','+vpi','+define+ARM_UD_MODEL','+define+DISABLE_SV_ASSERTION=1','+lint=TFIPC-L','-load',str(library)+':xu_mapped_task00_register111','-f',str(filelist),'-Mdir='+str(out/'csrc'),'-o',str(out/'task00')]
 run.step('vcs-build',vcs,1800);run.freeze(out/'task00')
 if(out/'task00.daidir').is_dir():run.freeze_tree(out/'task00.daidir')
 command=[str(out/'task00')]+activity['tasks'][0]['run_command'][1:];need('+TASKS=1'in command and '+XU_GLOBAL_TASK=0'in command,'frozen task00 arguments differ')
 code,raw=run.step('simulation',command,21600,require_zero=False);run.state.update(classify_public_log(raw,code));run.save()

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['capture','inventory','out']:p.add_argument('--'+name,required=True,type=Path)
 for name in ['run-vcs','mapped','vendor','standard','vpi-include','preload-proof']:p.add_argument('--'+name,type=Path)
 a=p.parse_args()
 with EvidenceRun(a.out)as run:work(a,run)
 print(run.state['status'],flush=True)
if __name__=='__main__':main()
