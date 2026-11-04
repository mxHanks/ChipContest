from pathlib import Path
import hashlib,json,subprocess,sys,os,time
B=Path.home()/'Desktop/xu-score-optimization-20261102';O=B/'mapped-elaboration-probe-20261104-97';L=B/'mapped-elaboration-launch-20261104-97';T=Path.home()/'Desktop/xu_prepare_mapped_probe74.py';C=Path.home()/'Desktop/xu_mapped_inventory74.c';M=B/'standard-cell-model-private-20261104-90/scc40nll_vhsc40_rvt.v'
if len(sys.argv)==1:
 L.mkdir(exist_ok=False);assert not O.exists()
 with(L/'driver.log').open('xb')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('MAPPED97_STARTED',p.pid,flush=True);sys.exit(0)
s=dict(status='RUNNING_STRUCTURE_ONLY_NOT_QUALIFIED',pid=os.getpid(),started_epoch=time.time())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save():(L/'state.json').write_text(json.dumps(s,sort_keys=True,indent=2)+'\n')
save()
try:
 expected={str(T):'db2898f0e2f11537eb8868b53e6e8eb7f5eab94e499e72ff7b1d23a148617b50',str(C):'3febc2f02a59514d78d6e9358988b8b4aabdc3d383c0db7e058fa5192acb42ce',str(M):'9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581'}
 assert {p:sha(Path(p))for p in expected}==expected;s['fixed_inputs']=expected
 cmd=[sys.executable,str(T),'--tb',str(B/'s2c-formal-activity12-20261103-23/simulator/tb_xu_s2c_task_activity.sv'),'--activity',str(B/'s2c-formal-activity12-20261103-23/result.json'),'--inventory',str(B/'s2c-pt-macro-pin-inventory-20261103-20/inventory.json'),'--mapped',str(B/'s2c-ppa-campaign-20261103-01/s2c/ppa/mapped.v'),'--vendor','/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/verilog/RAMSP1024X16.v','--standard-model',str(M),'--out',str(O),'--run-vcs','/eda/synopsys/vcs/vcs_2020.03-SP2-6/bin/vcs']
 s['command']=cmd;save()
 with(L/'probe.log').open('xb')as f:r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
 s['returncode']=r.returncode;assert r.returncode==0
 review=json.loads((O/'review.json').read_text());assert review['status']=='EXECUTED_STRUCTURE_PROBE_ONLY';assert {p:sha(Path(p))for p in expected}==expected;s['status']='EXECUTED_STRUCTURE_PROBE_ONLY_NOT_FUNCTIONAL_ACTIVITY_OR_ENERGY';s['review_sha256']=sha(O/'review.json')
except BaseException as e:s.update(status='FAIL_STRUCTURE_PROBE_NOT_QUALIFIED',error=type(e).__name__+': '+str(e));raise
finally:s['finished_epoch']=time.time();save()
print('MAPPED97_DONE',s['status'],flush=True)
