from pathlib import Path
import subprocess,hashlib,json,importlib.util,sys,os,signal,time,traceback
B=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('builder111',B/'xu_build_mapped_task00111.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def terminal_or_missing(pid):
 try:return Path('/proc/%d/stat'%pid).read_text().split()[2]=='Z'
 except FileNotFoundError:return True
if len(sys.argv)>1 and sys.argv[1]=='--interrupt-worker':
 out=Path(sys.argv[2])
 with m.EvidenceRun(out)as run:run.step('interrupt-child',[sys.executable,'-c','import time;time.sleep(30)'],60)
 raise AssertionError('worker unexpectedly survived')
O=B/'local-checks-v4';O.mkdir(exist_ok=False);checks=[]
def command(name,argv,expected=0):
 log=O/(name+'.log')
 with log.open('xb')as f:p=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,timeout=30)
 if p.returncode!=expected:raise AssertionError((name,p.returncode,log.read_text()))
 checks.append(dict(name=name,command=argv,returncode=p.returncode,log_sha256=sha(log)));return log.read_text()
# Existing complete public transaction contract remains unchanged apart from111 marker names.
command('public-compile',['iverilog','-g2012','-I'+str(B),'-s','tb_xu_soc_ppa','-o',str(O/'public.vvp'),str(B/'test_public_observer111.sv')])
for mode in range(6):
 text=command('public-mode-%d'%mode,['vvp',str(O/'public.vvp'),'+MODE='+str(mode)],0 if mode==0 else 1)
 if mode==0:assert 'HOST_PUBLIC_CONTRACT_PASS'in text
 else:assert 'XU_MAPPED111_'in text and 'REJECT'in text and 'HOST_PUBLIC_CONTRACT_PASS'not in text
# Copy the actual generated111 scoreboard. Only its VPI sample call becomes a
# comment; all port registers in this mechanism fixture are driven below.
generated=(B/'prepared-local-v1/tb_xu_mapped_task00111.sv').read_text();score=generated[generated.index(' always @(posedge clk)begin:public_scoreboard'):generated.rindex('endmodule')];assert score.count('$xu_mapped111_sample();')==1;score=score.replace('$xu_mapped111_sample();','/* Mechanism-only fixture, no DUT or VPI. */')
decl='''`timescale 1ns/1fs
module tb_xu_soc_ppa;
reg clk=0,rst_n=1;
reg cmd_valid=0,cmd_read=0,rsp_valid=0,rsp_ready=1,rsp_err=0;
integer ready_override=0;
wire cmd_ready=ready_override==1?1'bx:ready_override==2?1'bz:(!rsp_valid||rsp_ready)&&(cycles%7!=0);
reg[31:0]cmd_addr=0,cmd_wdata=0,rsp_rdata=0;reg[3:0]cmd_wmask=15;
reg a_cmd_valid=0,a_cmd_ready=1,a_cmd_read=0,a_rsp_valid=0,a_rsp_ready=1,a_rsp_err=0,a_clk=0,a_rst_n=1;
reg[31:0]a_cmd_addr=0,a_cmd_wdata=0,a_rsp_rdata=0;reg[3:0]a_cmd_wmask=15;
integer a_reset_edges=4594,a_reset_seen=1,a_reset_ready=1;
reg[31:0]ram[0:131071];reg[15:0]x[0:6335],w[0:16383];reg[39:0]bias[0:255];reg[47:0]golden[0:25343];
integer cycles=0,max_cycles=1000,writes=0,completed=0,outstanding=0,firmware_cycles=0;
reg final_write_pending=0;localparam BASE=32'ha0000000,YOFF=32'h20000,HOST=32'h7f000;
'''
tail='''
integer mode=0;
initial begin
 if(!$value$plusargs("MODE=%d",mode))mode=0;
 #1;
 case(mode)
 1:cmd_valid=1'bx;2:cmd_valid=1'bz;3:rsp_valid=1'bx;4:rsp_valid=1'bz;
 5:rsp_ready=1'bx;6:rsp_ready=1'bz;7:ready_override=1;8:ready_override=2;
 9:a_cmd_valid=1'bx;10:begin cmd_addr=32'hxxxxxxxx;cmd_wdata=32'hxxxxxxxx;end
 11:begin a_reset_ready=0;cmd_valid=1'bx;end
 endcase
 repeat(5)begin #5;clk=1;#5;clk=0;end
 $display("REVIEW111_HANDSHAKE_FIXTURE_SURVIVED mode=%0d NO_DUT_OR_FUNCTIONAL_CLAIM",mode);$finish;
end
endmodule
'''
fixture=O/'shared-handshake.sv';fixture.write_text(decl+(B/'xu_public_observer111.svh').read_text()+'\n'+score+tail)
command('shared-compile',['iverilog','-g2012','-s','tb_xu_soc_ppa','-o',str(O/'shared.vvp'),str(fixture)])
for mode in range(12):
 expected=0 if mode in [0,10,11]else 1;text=command('shared-mode-%d'%mode,['vvp',str(O/'shared.vvp'),'+MODE='+str(mode)],expected)
 if expected:assert ('unknown_shared_handshake'if mode<9 else'unknown_MMIO_handshake')in text
 else:assert 'REVIEW111_HANDSHAKE_FIXTURE_SURVIVED'in text
# Execute the real unchanged callback function from the111 adapter with scalar
# VPI stubs. This tests guard behavior, not actual VCS event scheduling.
c=O/'clock-callback.c';c.write_text('''#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include "../../xu_mapped_task00_vpi111.c"
void vpi_get_value(vpiHandle h,p_vpi_value v){v->value.scalar=*(PLI_INT32 *)h;}
PLI_INT32 vpi_printf(const char *fmt,...){PLI_INT32 r;va_list ap;va_start(ap,fmt);r=vprintf(fmt,ap);va_end(ap);return r;}
void vpi_control(PLI_INT32 operation,...){(void)operation;}
int main(int argc,char **argv){
 unsigned n;int mode=argc>1?atoi(argv[1]):0;PLI_INT32 clock=vpi0,reset=vpi0;
 accel_clk=(vpiHandle)&clock;accel_reset=(vpiHandle)&reset;previous_clk=vpi0;
 if(mode==5){clock=vpiX;clock_callback(NULL);clock=vpi0;clock_callback(NULL);}
 for(n=0;n<4594;++n){clock=vpi1;clock_callback(NULL);clock=vpi0;clock_callback(NULL);}
 reset=vpi1;clock=vpi1;clock_callback(NULL);clock=vpi0;clock_callback(NULL);
 if(clock_reset_edges!=4594||clock_ready!=1||failed)return 2;
 if(mode==1){clock=vpiX;}if(mode==2){clock=vpiZ;}
 if(mode==3){reset=vpiX;}if(mode==4){reset=vpi0;}
 if(mode>=1&&mode<=4){if(mode>=3)clock=vpi1;clock_callback(NULL);}
 printf("REVIEW111_CLOCK mode=%d reset_edges=%u ready=%u rejected=%d NO_NATIVE_VCS_EVENT_PROOF\\n",mode,clock_reset_edges,clock_ready,failed);
 return (failed!=((mode>=1&&mode<=4)?1:0));
}
'''.replace('#include "../../xu_mapped_task00_vpi111.c"','#include "../xu_mapped_task00_vpi111.c"'))
command('clock-compile',['cc','-std=gnu99','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections','-isystem','/usr/include/iverilog','-I'+str(B/'prepared-local-v1'),str(c),'-Wl,--gc-sections','-o',str(O/'clock-callback')])
for mode in range(6):command('clock-mode-%d'%mode,[str(O/'clock-callback'),str(mode)])
# Execute the real full-macro geometry checker with mechanism-only VPI objects.
# Deliberate row255 faults prove the guard does not merely inspect row0.
g=O/'geometry.c';g.write_text(r'''#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include "../xu_mapped_task00_vpi111.c"
typedef struct {int kind,index;} Obj;
static Obj module_object={0,0},memory_object={1,0},words[256],indices[256],different={2,255};
static int mode,reads255;
static Obj *obj(vpiHandle h){return(Obj*)h;}
void vpi_get_value(vpiHandle h,p_vpi_value v){v->value.integer=obj(h)->index;}
PLI_INT32 vpi_printf(const char *fmt,...){PLI_INT32 r;va_list ap;va_start(ap,fmt);r=vprintf(fmt,ap);va_end(ap);return r;}
void vpi_control(PLI_INT32 operation,...){(void)operation;}
PLI_INT32 vpi_get(PLI_INT32 property,vpiHandle h){Obj*o=obj(h);if(property==vpiType){if(o->kind==0)return vpiModule;if(o->kind==1)return mode==1?vpiMemory:vpiRegArray;return mode==1?vpiMemoryWord:mode==4&&o->index==255?vpiNet:vpiReg;}if(property==vpiSize)return o->kind==1?256:mode==3&&o->index==255?63:64;return -1;}
PLI_BYTE8 *vpi_get_str(PLI_INT32 property,vpiHandle h){static char buffers[8][8300];static unsigned next;char *out=buffers[(next++)%8];Obj *o=obj(h);if(property!=vpiFullName)return NULL;if(o->kind==0)snprintf(out,8300,"%s",xu_expected111[0].name);else if(o->kind==1)snprintf(out,8300,"%s.%s",xu_expected111[0].name,mode==5?"wrong":"mem");else snprintf(out,8300,"%s.mem[%d]",xu_expected111[0].name,o->index);return(PLI_BYTE8*)out;}
vpiHandle vpi_handle_by_index(vpiHandle h,PLI_INT32 row){if(h!=(vpiHandle)&memory_object||row<0||row>255)return NULL;if(row==255){++reads255;if(mode==2)return NULL;if(mode==6)return(vpiHandle)&words[0];if(mode==7&&reads255>1)return(vpiHandle)&different;}return(vpiHandle)&words[row];}
vpiHandle vpi_handle(PLI_INT32 relation,vpiHandle h){Obj*o=obj(h);if(relation==vpiParent){if(o->kind==1)return(vpiHandle)&module_object;if(o->kind==2)return mode==8&&o->index==255?(vpiHandle)&words[1]:(vpiHandle)&memory_object;}if(relation==vpiScope)return(vpiHandle)&module_object;if(relation==vpiIndex&&o->kind==2){if(mode==9&&o->index==255)return(vpiHandle)&indices[254];return(vpiHandle)&indices[o->index];}return NULL;}
PLI_INT32 vpi_compare_objects(vpiHandle a,vpiHandle b){return a==b;}
int main(int argc,char **argv){unsigned i;mode=argc>1?atoi(argv[1]):0;for(i=0;i<256;++i){words[i].kind=2;words[i].index=(int)i;indices[i].kind=3;indices[i].index=(int)i;}macro_mod[0]=(vpiHandle)&module_object;macro_mem[0]=(vpiHandle)&memory_object;int ok=geometry(0);printf("REVIEW111_GEOMETRY mode=%d accepted=%d rejected=%d row255_lookups=%d MECHANISM_ONLY_NOT_NATIVE_VCS\n",mode,ok,failed,reads255);return (mode<=1)?!(ok&&!failed):(ok||!failed);}
''')
command('geometry-compile',['cc','-std=gnu99','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections','-isystem','/usr/include/iverilog','-I'+str(B/'prepared-local-v1'),str(g),'-Wl,--gc-sections','-o',str(O/'geometry')])
for mode in range(10):
 text=command('geometry-mode-%d'%mode,[str(O/'geometry'),str(mode)])
 assert ('accepted=1 rejected=0'if mode<=1 else'accepted=0 rejected=1')in text

# Real subprocess failure/timeout/interruption and actual input-change checks.
runner=[]
def case(name,body,expect_error):
 out=O/('runner-'+name);error=None
 try:
  with m.EvidenceRun(out)as run:body(run);run.state['status']='LOCAL_MECHANISM_EXECUTED_NOT_NATIVE_VCS'
 except BaseException as exc:error=type(exc).__name__
 assert error==expect_error,(name,error,expect_error)
 state=json.loads((out/'state.json').read_text());assert (state['status']==m.FAIL_STATUS)==(expect_error is not None)
 assert state['qualification']=='NOT_QUALIFIED';runner.append(dict(name=name,error=error,state=state,raw_state_sha256=sha(out/'state.json')));return state
case('success',lambda r:r.step('ok',[sys.executable,'-c','print("ordinary-child")'],5),None)
case('compiler-exit7',lambda r:r.step('compiler',[sys.executable,'-c','import sys;sys.exit(7)'],5),'ValueError')
case('missing-executable',lambda r:r.step('compiler',[str(O/'missing-compiler')],5),'FileNotFoundError')
child_pid=O/'timeout-descendant.pid'
code='import subprocess,signal,time,pathlib;signal.signal(signal.SIGTERM,signal.SIG_IGN);p=subprocess.Popen(["'+sys.executable+'","-c","import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)"]);pathlib.Path('+repr(str(child_pid))+').write_text(str(p.pid));time.sleep(30)'
timed=case('timeout',lambda r:r.step('hung-compiler',[sys.executable,'-c',code],0.5),'TimeoutExpired');pid=int(child_pid.read_text());assert terminal_or_missing(pid);assert terminal_or_missing(timed['steps'][0]['pid'])
input_file=O/'mutable-input.txt';input_file.write_text('before')
def mutate(run):
 run.freeze(input_file);run.step('mutator',[sys.executable,'-c','from pathlib import Path;Path('+repr(str(input_file))+').write_text("after")'],5)
changed=case('changed-input',mutate,'ValueError');assert changed['identity_errors']and not changed['inputs_equal_before_after']
missing_file=O/'missing-input.txt';missing_file.write_text('before')
def delete_then_fail(run):
 run.freeze(missing_file);run.step('compiler',[sys.executable,'-c','from pathlib import Path;import sys;Path('+repr(str(missing_file))+').unlink();sys.exit(9)'],5)
missing=case('missing-input-with-primary-failure',delete_then_fail,'ValueError');assert 'returncode=9'in missing['error']['message']and missing['identity_errors']
interrupt_out=O/'runner-interrupted'
with(O/'interrupt-worker.log').open('xb')as log:
 p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--interrupt-worker',str(interrupt_out)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 deadline=time.monotonic()+5;state=None
 while time.monotonic()<deadline:
  if(interrupt_out/'state.json').exists():
   state=json.loads((interrupt_out/'state.json').read_text())
   if state.get('steps')and state['steps'][0]['status']=='RUNNING':break
  time.sleep(0.02)
 assert state and state['steps'][0]['status']=='RUNNING';live_child=state['steps'][0]['pid'];assert not terminal_or_missing(live_child);os.kill(p.pid,signal.SIGINT);p.wait(timeout=10)
 assert p.returncode!=0 and terminal_or_missing(live_child)
state=json.loads((interrupt_out/'state.json').read_text());assert state['status']==m.FAIL_STATUS and state['error']['type']=='KeyboardInterrupt';runner.append(dict(name='interrupted',returncode=p.returncode,state=state,raw_state_sha256=sha(interrupt_out/'state.json')))
# Expected final fatal never becomes functional qualification; malformed receipts fail.
lines=[
'XU_MAPPED111_ADAPTER_READY macros=336 interface_bits_preserve_4state=1 preload_allowed=288 Q_WRITES=0 OTHER_DUT_FF_WRITES=0',
'XU_MAPPED111_PRELOAD_DONE itcm=32 shared=256 words_per_macro=256 bits_per_row=64 arbitrary_XZ_preserved=1 Q_WRITES=0',
'XU_MAPPED111_SOURCE_REQUEST cycle=1403985 tick=9359903333333 clear_writes=33697 PUBLIC_CLEAR_ONLY_PHYSICAL_FF_GATE_PENDING',
'XU_MAPPED111_FINAL_Y_RETIRE cycle=2394641 tick=15964276666667 elapsed=990656',
'XU_MAPPED111_PUBLIC_DIAGNOSTIC_COMPLETE tasks=1 outputs=25344 writes=50688 w_pairs=8192 x_pairs=3168 rows=99 pops=3168 result_reads=50688 source_reads=23232 elapsed_cycles=990656 NOT_FULL_FUNCTIONAL_OR_ACTIVITY_OR_ENERGY_QUALIFIED',m.PENDING_TEXT]
geometry_lines=['XU_MAPPED111_GEOMETRY tag=%d role=%d status=PASS rows=256 row_bits=64 unique=256 memory_type=116 reg_words=256 memoryword_words=0 parent_present=256 scope_present=256 index_present=256 name=tb_xu_soc_ppa.dut.macro%d'%(i,1 if i<32 else 2 if i<288 else 0,i)for i in range(336)];raw=('\n'.join(geometry_lines+lines)+'\n').encode();classified=m.classify_public_log(raw,1);assert classified['status']==m.PUBLIC_STATUS and classified['functional_qualification']=='NOT_QUALIFIED'
negatives=[('zero-return',raw,0),('duplicate-public',raw+lines[-2].encode()+b'\n',1),('wrong-count',raw.replace(b'w_pairs=8192',b'w_pairs=8191'),1),('missing-pending',raw.replace(m.PENDING_TEXT.encode(),b''),1),('invented-pending-substring',raw.replace(m.PENDING_TEXT.encode(),('ECHO '+m.PENDING_TEXT).encode()),1),('missing-preload',raw.replace(lines[1].encode(),b''),1),('wrong-boundary',raw.replace(b'cycle=2394641',b'cycle=2394640'),1),('unexpected-SOC-PASS',raw+b'SOC_PASS\n',1),('earlier-rejection',b'XU_MAPPED111_RESET_REJECT failed\n'+raw,1),('missing-full-geometry',raw.replace(geometry_lines[-1].encode(),b''),1),('wrong-row255-proof',raw.replace(b'row_bits=64 unique=256',b'row_bits=64 unique=255',1),1),('wrong-source-count',raw.replace(b'source_reads=23232',b'source_reads=23231'),1)]
classified_negative=[]
for name,data,code in negatives:
 try:m.classify_public_log(data,code)
 except ValueError as exc:classified_negative.append(dict(name=name,rejection=str(exc)))
 else:raise AssertionError('classification accepted '+name)
(O/'runner-review.json').write_text(json.dumps(dict(status='LOCAL_RUNNER_AND_CLASSIFIER_MECHANISMS_ONLY_NOT_VCS',cases=runner,classification_positive=classified,classification_negative=classified_negative),sort_keys=True,indent=2)+'\n')
(O/'review.json').write_text(json.dumps(dict(status='LOCAL_PUBLIC_CALLBACK_RUNNER_MECHANISM_CHECKS_NOT_MAPPED_VCS_OR_QUALIFICATION',checks=checks,runner_cases=len(runner),classifier_negative_cases=len(negatives),qualification='NOT_QUALIFIED'),sort_keys=True,indent=2)+'\n')
print('LOCAL111_DONE checks=%d runner_cases=%d classifier_rejections=%d'%(len(checks),len(runner),len(negatives)))
