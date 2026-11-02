from pathlib import Path
import hashlib,json,subprocess,sys,time,os
D=Path.home()/'Desktop';B=D/'xu-score-optimization-20261102';R=B/'ChipContest';O=B/'full-soc-campaign-01'
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
 O.mkdir(exist_ok=False);bundle=D/'xu-s0-soc-ready.bundle'
 if sha(bundle)!='8856c17529d27293fc0ec182aadc20a615d72890061387fa12c08be7d40a8fbb':raise ValueError('bundle SHA differs')
 if subprocess.check_output(['git','status','--porcelain'],cwd=str(R)).strip():raise ValueError('server independent clone not clean')
 run(['git','fetch',str(bundle),'codex/xu-score-opt']);run(['git','merge','--ff-only','FETCH_HEAD'])
 main=subprocess.check_output(['git','rev-parse','HEAD'],cwd=str(R)).decode().strip()
 if not main.startswith('e998479'):raise ValueError('deployment HEAD differs')
 ids={k:child(k)for k in ['functional','ppa']};save(O/'launch.json',dict(main_commit=main,pids=ids,started_epoch=time.time(),bundle_sha256=sha(bundle)))
 print('STARTED_FULL_SOC',json.dumps(ids,sort_keys=True))
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
