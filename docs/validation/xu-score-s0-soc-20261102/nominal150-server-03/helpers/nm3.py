from pathlib import Path
import subprocess,json,hashlib,sys,time
D=Path.home()/'Desktop';B=D/'xu-score-optimization-20261102';R=B/'ChipContest';O=B/'full-soc-nominal-03'
if sys.argv[1]=='start':
 O.mkdir(exist_ok=False);bundle=D/'xu-s0-nominal-fix.bundle'
 if hashlib.sha256(bundle.read_bytes()).hexdigest()!='999725db6ab141650071a3e68dffb447beb3fc1d8b014dbf32edb2868e1ac2fa':raise ValueError('bundle differs')
 if subprocess.check_output(['git','status','--porcelain'],cwd=str(R)).strip():raise ValueError('source dirty')
 subprocess.check_call(['git','fetch',str(bundle),'codex/xu-score-opt'],cwd=str(R),stdin=subprocess.DEVNULL);subprocess.check_call(['git','merge','--ff-only','FETCH_HEAD'],cwd=str(R),stdin=subprocess.DEVNULL)
 with(O/'driver.log').open('x')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('STARTED_NOMINAL_RETRY',p.pid)
else:
 s=dict(status='RUNNING',started_epoch=time.time());(O/'state.json').write_text(json.dumps(s)+'\n')
 try:
  cmd=[sys.executable,str(R/'tools/ppa/xu_soc_ppa_verify.py'),'--out',str(O/'real12'),'--sim','vcs','--clock-mode','nominal150','--tasks','12','--variants','reference','macro','--firmware-schedule','bias-hw-window','--firmware-opt=-O2','--firmware-experiment','both-unroll-no-masks','--vendor-model','/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/verilog/RAMSP1024X16.v','--cross-prefix',str(D/'xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-')]
  s['command']=cmd;(O/'state.json').write_text(json.dumps(s)+'\n')
  subprocess.check_call(cmd,cwd=str(R),stdin=subprocess.DEVNULL);s['status']='PASS'
 except Exception as e:s.update(status='FAIL',error=str(e));raise
 finally:s['finished_epoch']=time.time();(O/'state.json').write_text(json.dumps(s,sort_keys=True,indent=2)+'\n')
