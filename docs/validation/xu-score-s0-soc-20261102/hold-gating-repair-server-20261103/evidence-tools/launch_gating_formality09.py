from pathlib import Path
import subprocess,json,hashlib,sys,time,re
B=Path.home()/'Desktop/xu-score-optimization-20261102';O=B/'full-soc-gating-formality-20261103-09';P=B/'full-soc-campaign-03-ppa/ppa-ss-01';N=B/'full-soc-gating-margin-repair-20261103-09';H=B/'full-soc-hold-repair-20261103-08'
def identity(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def save(j):(O/'state.json').write_text(json.dumps(j,sort_keys=True,indent=2)+'\n')
if len(sys.argv)==1:
 O.mkdir(exist_ok=False)
 with(O/'driver.log').open('x')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
 print('GATING09_FORMALITY_STARTED',p.pid);sys.exit(0)
j=dict(status='RUNNING_NOT_QUALIFIED',started_epoch=time.time());save(j)
try:
 h=json.loads((N/'state.json').read_text())
 if h['status']!='EXECUTED_NOT_QUALIFIED':raise ValueError('exact new mapped repair must be terminal')
 if identity(N/'mapped.v')['sha256']!=h['mapped_netlist_sha256']:raise ValueError('new mapped repair identity differs')
 original=B/'full-soc-formality-02/verify.tcl';text=original.read_text();old='set_svf {'+str(P/'default.svf')+'}'
 if text.count(old)!=1 or text.count('read_verilog -i {'+str(P/'mapped.v')+'}')!=1:raise ValueError('frozen successful baseline FM template differs')
 text=text.replace(old,'set_svf [list '+' '.join('{'+str(x)+'}'for x in [P/'default.svf',H/'repair.svf',N/'repair.svf'])+']').replace('read_verilog -i {'+str(P/'mapped.v')+'}','read_verilog -i {'+str(N/'mapped.v')+'}')
 (O/'verify.tcl').write_text(text)
 inputs=[original,P/'default.svf',H/'repair.svf',N/'repair.svf',N/'mapped.v',P/'rtl.f']+sorted(p for p in(P/'rtl').rglob('*')if p.is_file());j['frozen_before']={str(p):identity(p)for p in inputs};j['command']=['fm_shell','-f','verify.tcl'];j['target_state']=identity(N/'state.json');save(j)
 with(O/'fm.log').open('x')as f:r=subprocess.run(j['command'],cwd=str(O),stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=4200)
 log=(O/'fm.log').read_text(errors='replace');j.update(returncode=r.returncode,log=identity(O/'fm.log'),script=identity(O/'verify.tcl'),frozen_after={str(p):identity(p)for p in inputs})
 if j['frozen_after']!=j['frozen_before']:raise ValueError('input changed during proof')
 if r.returncode or log.splitlines().count('XU_FULL_SOC_FORMALITY_PASS')!=1:raise ValueError('new mapped fullSoC equivalence not verified')
 j['status']='VERIFIED_REVIEW_PENDING_NOT_QUALIFIED'
except Exception as e:j.update(status='FAIL',error=str(e));raise
finally:j['finished_epoch']=time.time();save(j)
