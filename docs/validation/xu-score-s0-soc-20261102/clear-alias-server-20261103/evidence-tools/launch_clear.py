from pathlib import Path
import subprocess,json,hashlib,sys,time
D=Path.home()/'Desktop';B=D/'xu-score-optimization-20261102';R=B/'ChipContest-clear-alias-20261103';O=B/'task-activity-clear-alias-20261103-01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(args,cwd):return subprocess.check_output(['git']+args,cwd=str(cwd),stdin=subprocess.DEVNULL).decode().strip()
def save(j):(O/'state.json').write_text(json.dumps(j,sort_keys=True,indent=2)+'\n')
if len(sys.argv)==1:
 if R.exists()or O.exists():raise ValueError('output orsourceexists')
 O.mkdir()
 with(O/'driver.log').open('x')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('CLEAR_ALIAS_STARTED',p.pid);sys.exit(0)
j=dict(status='RUNNING_REVIEW_PENDING',started_epoch=time.time());save(j)
try:
 bundle=D/'xu-clear-alias-20261103.bundle'
 if sha(bundle)!='2d410734c59d31248ff1458ecc719ed5a4c4695b61e1f6444e5c79fe7a0ef284':raise ValueError('bundleSHA')
 git(['clone','--no-hardlinks',str(B/'ChipContest'),str(R)],B);git(['fetch',str(bundle),'codex/xu-score-opt'],R);git(['checkout','--detach','854164105f1ab7a9aac79ceaadddad41a1bb6c5f'],R)
 E=R/'third-party/e203_hbirdv2';E.rmdir();git(['clone','--no-hardlinks',str(B/'ChipContest/third-party/e203_hbirdv2'),str(E)],R);git(['checkout','--detach','f49a5fc914971426bd4530db39e270a84b41139f'],E)
 if git(['status','--porcelain'],R)or git(['status','--porcelain'],E):raise ValueError('sourcefreeze')
 P=B/'full-soc-campaign-03-ppa/ppa-ss-01';S=B/'full-soc-pt-compatible-05/constraints.sdc'
 if sha(P/'mapped.v')!='0f4898ba5ab6571c2125978cdce0a9984a87d4df9901757cb1c00662e4ef3616'or sha(S)!='404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98':raise ValueError('netlistSDCbinding')
 cmd=[sys.executable,str(R/'tools/ppa/xu_soc_task_activity.py'),'--out',str(O/'task00'),'--vendor-model','/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/verilog/RAMSP1024X16.v','--netlist',str(P/'mapped.v'),'--constraints',str(S),'--cross-prefix',str(D/'xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-'),'--clear-task-before-window','--sram-pin-alias','--task-ids','0','--max-cycles','4000000']
 j['command']=cmd;save(j)
 with(O/'collector.log').open('x')as f:r=subprocess.run(cmd,cwd=str(R),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=10800)
 j.update(status='COLLECTED_REVIEW_PENDING'if r.returncode==0 else'FAIL',returncode=r.returncode)
except Exception as e:j.update(status='FAIL',error=str(e));raise
finally:j['finished_epoch']=time.time();save(j)
print('CLEAR_ALIAS_DONE',j['status'])
