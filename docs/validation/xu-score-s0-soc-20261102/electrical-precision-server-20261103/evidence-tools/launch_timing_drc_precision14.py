from pathlib import Path
import subprocess,json,hashlib,time,sys,re,os
B=Path.home()/'Desktop/xu-score-optimization-20261102';N=B/'full-soc-gating-margin-repair-20261103-09';O=B/'full-soc-gating-drc-precision-20261103-14'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(j):(O/'state.json').write_text(json.dumps(j,sort_keys=True,indent=2)+'\n')
if len(sys.argv)==1:
 O.mkdir(exist_ok=False)
 with(O/'driver.log').open('x')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('DRC_PRECISION_STARTED',p.pid);sys.exit(0)
j=dict(status='RUNNING_NOT_QUALIFIED',started_epoch=time.time());save(j)
try:
 n=json.loads((N/'state.json').read_text());net=N/'mapped.v';assert sha(net)==n['mapped_netlist_sha256']=='5610f32b23220c87d39b45f24133adbf867d7faeb7284eed5f75d84b77ef4fca'
 s=(N/'sta.tcl').read_text();assert s.count('read_verilog mapped.v')==1;s=s.replace('read_verilog mapped.v','read_verilog {'+str(net)+'}')
 old='report_constraint -all_violators -verbose';assert s.count(old)==1;s=s.replace(old,old+' -significant_digits 8');(O/'sta.tcl').write_text(s)
 inputs=[net,N/'sta.tcl']+[Path(x)for x in n['input_sha256']];j['frozen_before']={str(p):sha(p)for p in inputs};j['command']=['pt_shell','-f','sta.tcl'];save(j)
 env=os.environ.copy();env['SYNOPSYS_LC_ROOT']='/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5';env['PATH']=env['SYNOPSYS_LC_ROOT']+'/bin:'+env.get('PATH','');j['env_setup']=dict(SYNOPSYS_LC_ROOT=env['SYNOPSYS_LC_ROOT'],path_prefix=env['SYNOPSYS_LC_ROOT']+'/bin');save(j)
 with(O/'pt.log').open('x')as f:r=subprocess.run(j['command'],cwd=str(O),env=env,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=3600)
 text=(O/'pt.log').read_text(errors='replace');errors=[x for x in text.splitlines()if re.match(r'^\s*(?:Error:|Error-|XU_FATAL:)',x)];j.update(returncode=r.returncode,errors=errors,frozen_after={str(p):sha(p)for p in inputs},reports={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))for p in O.glob('*.rpt')});assert j['frozen_before']==j['frozen_after'];assert r.returncode==0 and not errors and text.splitlines().count('XU_FULL_SOC_HOLD_REPAIR_PT_DONE_NOT_QUALIFIED')==1;j['status']='DIAGNOSTIC_EXECUTED_NOT_QUALIFIED'
except Exception as e:j.update(status='FAIL',error=str(e));raise
finally:j['finished_epoch']=time.time();save(j)
