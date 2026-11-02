from pathlib import Path
import hashlib,json,subprocess,sys,time,os
D=Path.home()/'Desktop';B=D/'xu-score-optimization-20261102';R=B/'ChipContest-ppa-03';O=B/'full-soc-campaign-03-ppa'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,log=None):
 if log:
  with log.open('x')as f:subprocess.run(cmd,cwd=str(R),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=21600)
 else:subprocess.run(cmd,cwd=str(R),stdin=subprocess.DEVNULL,check=True,timeout=120)
def save(p,j):p.write_text(json.dumps(j,sort_keys=True,indent=2)+'\n')
def child(action):
 with (O/(action+'-driver.log')).open('x')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),action],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 return p.pid
if sys.argv[1]=='start':
 O.mkdir(exist_ok=False);bundle=D/'xu-s0-ppa-retry3.bundle'
 if sha(bundle)!='dd02850c6ef7707810f2d18af02ce571a5688311465bfb3b7045b8f8246afdfa':raise ValueError('bundle SHA differs')
 subprocess.check_call(['git','clone','--no-hardlinks','--no-checkout',str(B/'ChipContest'),str(R)],stdin=subprocess.DEVNULL)
 run(['git','fetch',str(bundle),'codex/xu-score-opt']);run(['git','checkout','-b','codex/xu-score-ppa3','FETCH_HEAD'])
 sub=R/'third-party/e203_hbirdv2';sub.rmdir()
 subprocess.check_call(['git','clone','--no-hardlinks','--no-checkout',str(B/'ChipContest/third-party/e203_hbirdv2'),str(sub)],stdin=subprocess.DEVNULL)
 subprocess.check_call(['git','checkout','-b','codex/xu-score-ppa3','f49a5fc914971426bd4530db39e270a84b41139f'],cwd=str(sub),stdin=subprocess.DEVNULL)
 main=subprocess.check_output(['git','rev-parse','HEAD'],cwd=str(R)).decode().strip()
 if not main.startswith('664186d'):raise ValueError('deployment HEAD differs')
 ids={'ppa':child('ppa')};save(O/'launch.json',dict(main_commit=main,pids=ids,started_epoch=time.time(),bundle_sha256=sha(bundle)))
 print('STARTED_FULL_SOC_PPA3',json.dumps(ids,sort_keys=True))
elif sys.argv[1]=='functional':
 s=dict(status='RUNNING',stage='real1',started_epoch=time.time());save(O/'functional-state.json',s)
 try:
  prefix=str(D/'xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-')
  common=[sys.executable,str(R/'tools/ppa/xu_soc_ppa_verify.py'),'--sim','vcs','--cross-prefix',prefix,'--firmware-schedule','bias-hw-window','--firmware-opt=-O2','--firmware-experiment','both-unroll-no-masks','--vendor-model','/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/verilog/RAMSP1024X16.v','--run-timeout','10800']
  for name,clock,tasks,variants in [('reference4ns-real1','reference4ns',1,['reference','harness','macro']),('reference4ns-real12','reference4ns',12,['reference','macro']),('nominal150-real12','nominal150',12,['reference','macro'])]:
   s['stage']=name;save(O/'functional-state.json',s)
   cmd=common+['--out',str(O/name),'--clock-mode',clock,'--tasks',str(tasks),'--variants']+variants
   run(cmd,O/(name+'-driver.log'))
   j=json.loads((O/name/'result.json').read_text())
   if j['status']!='PASS':raise ValueError(name+' did not PASS')
   s.setdefault('completed',[]).append(dict(name=name,result_sha256=sha(O/name/'result.json'),cycles=sum(x['cycles']for x in j['variants'][0]['layers'])));save(O/'functional-state.json',s)
  s.update(status='PASS',stage='complete')
 except Exception as e:s.update(status='FAIL',error=str(e));raise
 finally:s['finished_epoch']=time.time();save(O/'functional-state.json',s)
elif sys.argv[1]=='ppa':
 s=dict(status='RUNNING_NOT_QUALIFIED',stage='prepare',started_epoch=time.time());save(O/'ppa-state.json',s)
 try:
  m=json.loads((D/'xu-hw-optimization-20261102/ppa/candidate-ss-02/manifest.json').read_text());std=next(n for n in m['libraries']if n.endswith('_basic.db'));ram=next(n for n in m['libraries']if n.endswith('.db')and n!=std)
  cfg=O/'ppa-config';out=O/'ppa-ss-01'
  run([sys.executable,str(R/'tools/ppa/xu_soc_implementation.py'),'--out',str(cfg),'--standard-cell-db',std,'--standard-cell-sha256',m['libraries'][std]['sha256'],'--sram-db',ram,'--sram-sha256',m['libraries'][ram]['sha256']],O/'ppa-config.log')
  run([sys.executable,str(R/'tools/scripts/xu_soc_ppa.py'),'prepare','--implementation',str(cfg/'implementation.json'),'--out',str(out),'--allow-unqualified-mapping'],O/'ppa-prepare.log')
  s['stage']='dc-pt';save(O/'ppa-state.json',s)
  run([sys.executable,str(R/'tools/scripts/xu_soc_ppa.py'),'run','--out',str(out)],O/'ppa-run.log')
  s.update(status='EXECUTED_NOT_QUALIFIED',stage='complete',execution_sha256=sha(out/'execution.json'))
 except Exception as e:s.update(status='FAIL',error=str(e));raise
 finally:s['finished_epoch']=time.time();save(O/'ppa-state.json',s)
