"""Full original-RTL FM for exact actual49, cleanup50, or reset-buffer55.
Upload beside the other Desktop helpers. Stage arguments: 49, 50, 55-49-N,
55-50-N. All implementation SVFs are replayed from the original DC mapping.
"""
from pathlib import Path
import subprocess,json,hashlib,sys,time,re,os
B=Path.home()/'Desktop/xu-score-optimization-20261102'
P=B/'full-soc-campaign-03-ppa/ppa-ss-01'
ACTUAL49='5df0b568d1751d19388edb33d244f8b19051a9fa7c77b24a2e023bf1e2ee4b4c'
STAGES={'49':B/'full-soc-cap-size-repair-20261103-49','50':B/'full-soc-unloaded-cell-cleanup-20261103-50'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ident(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
def choose(stage):
 if stage in STAGES:return STAGES[stage],[STAGES['49']]+([STAGES['50']]if stage=='50'else [])
 m=re.fullmatch(r'55-(49|50)-([1-9][0-9]?)',stage)
 if not m or int(m[2])>32:raise ValueError('stage must be49,50,55-49-N,55-50-N;1<=N<=32')
 target=B/('full-soc-reset-buffer-20261104-55-from'+m[1]+'-n'+m[2])
 return target,[STAGES['49']]+([STAGES['50']]if m[1]=='50'else [])+[target]
worker=len(sys.argv)==3 and sys.argv[1]=='run'
stage=sys.argv[2]if worker else (sys.argv[1]if len(sys.argv)==2 else '50')
N,edits=choose(stage);O=B/('full-soc-electrical-formality-20261104-54-'+stage)
def save(j):(O/'state.json').write_text(json.dumps(j,sort_keys=True,indent=2)+'\n')
if not worker:
 O.mkdir(exist_ok=False)
 with(O/'driver.log').open('x')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run',stage],stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
 print('XU_ELECTRICAL_FULL_FORMALITY_STARTED',stage,p.pid);sys.exit(0)
j=dict(status='RUNNING_NOT_QUALIFIED',stage=stage,started_epoch=time.time(),pid=os.getpid());save(j)
try:
 prior=B/'full-soc-gating-formality-20261103-09/state.json'
 if sha(prior)!='2ef7222edd4b7504c9607e789906c27cea08c1812eaaaf7b49b4925607c61de1':raise ValueError('successful original09 full-RTL proof identity differs')
 old=json.loads(prior.read_text())
 if old['status']!='VERIFIED_REVIEW_PENDING_NOT_QUALIFIED' or old['returncode']!=0 or old['frozen_before']!=old['frozen_after']:raise ValueError('original09 FM was not successful')
 for name,evidence in old['frozen_before'].items():
  p=Path(name)
  if ident(p)!=evidence:raise ValueError('original RTL/SVF/template changed: '+name)
 if sha(STAGES['49']/'mapped.v')!=ACTUAL49 or sha(STAGES['49']/'state.json')!='3d9f222369a19b48eeec69ab63405d6aea579aa3f99d2b7a16ef2458f8cbaf28':raise ValueError('only actual49 is permitted')
 states=[]
 for edit in edits:
  state=json.loads((edit/'state.json').read_text())
  if state['status']!='EXECUTED_NOT_QUALIFIED' or sha(edit/'mapped.v')!=state['mapped_netlist_sha256']:raise ValueError('new mapped edit is not terminal with exact identity: '+str(edit))
  if len(state.get('runs',[]))!=2 or any(r['returncode'] or r['errors'] or r['marker_count']!=1 for r in state['runs']):raise ValueError('DC/PT execution evidence incomplete')
  for run,label in zip(state['runs'],('dc','pt')):
   if sha(edit/(label+'.log'))!=run['log_sha256']:raise ValueError('DC/PT log identity changed')
   if sha(edit/('repair.tcl'if label=='dc'else 'sta.tcl'))!=run['script_sha256']:raise ValueError('DC/PT script identity changed')
  states.append(state)
 for index in range(1,len(edits)):
  if states[index]['input_sha256'].get(str(edits[index-1]/'mapped.v'))!=states[index-1]['mapped_netlist_sha256']:raise ValueError('mapped electrical ancestry differs')
 if len(edits)>=2 and edits[1]==STAGES['50'] and states[1]['input_sha256'].get(str(STAGES['49']/'mapped.v'))!=ACTUAL49:raise ValueError('50 is not a descendant of exact actual49')
 original=B/'full-soc-formality-02/verify.tcl';script=original.read_text()
 if sha(original)!='d964b03a0eda4ed884cd0f8d6c2cd50be045e6085e0ffdb8865d840055aa1fba':raise ValueError('original successful full-RTL FM template differs')
 svfs=[P/'default.svf',B/'full-soc-hold-repair-20261103-08/repair.svf',B/'full-soc-gating-margin-repair-20261103-09/repair.svf']+[e/'repair.svf'for e in edits]
 old_svf='set_svf {'+str(P/'default.svf')+'}';old_net='read_verilog -i {'+str(P/'mapped.v')+'}'
 if script.count(old_svf)!=1 or script.count(old_net)!=1:raise ValueError('expected original template commands differ')
 script=script.replace(old_svf,'set_svf [list '+' '.join('{'+str(p)+'}'for p in svfs)+']').replace(old_net,'read_verilog -i {'+str(N/'mapped.v')+'}')
 (O/'verify.tcl').write_text(script)
 dbs=[Path(p)for p in re.findall(r'read_db -technology_library \{([^}]+)\}',script)]
 if len(dbs)!=2 or {sha(p)for p in dbs}!={'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723','c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'}:raise ValueError('two original SS technology libraries differ')
 inputs=list(dict.fromkeys([Path(p)for p in old['frozen_before']]+[Path(__file__).resolve(),prior,original]+dbs+svfs+[e/n for e in edits for n in ('state.json','mapped.v','repair.tcl','sta.tcl','repair.svf','dc.log','pt.log')]))
 j.update(frozen_before={str(p):ident(p)for p in inputs},svf_chain=[str(p)for p in svfs],command=['fm_shell','-f','verify.tcl'],target_netlist=ident(N/'mapped.v'));save(j)
 with(O/'fm.log').open('x')as f:r=subprocess.run(j['command'],cwd=str(O),stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=4200)
 log=(O/'fm.log').read_text(errors='replace');j.update(returncode=r.returncode,log=ident(O/'fm.log'),script=ident(O/'verify.tcl'),frozen_after={str(p):ident(p)for p in inputs})
 if j['frozen_before']!=j['frozen_after']:raise ValueError('a frozen input changed during full FM')
 if r.returncode or log.splitlines().count('XU_FULL_SOC_FORMALITY_PASS')!=1 or re.search(r'^\s*(?:Error:|Error-|XU_FULL_SOC_FORMALITY_FAIL|XU_FULL_SOC_FORMALITY_SCRIPT_ERROR)',log,re.M):raise ValueError('full original RTL equivalence did not pass')
 j.update(status='VERIFIED_REVIEW_PENDING_NOT_QUALIFIED',scope='same original fullSoC RTL, original SS libraries; default+08+09 plus every mapped electrical edit; electrical qualification remains separately required')
except Exception as e:j.update(status='FAIL',error=str(e));raise
finally:j['finished_epoch']=time.time();save(j)
