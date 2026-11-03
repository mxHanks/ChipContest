#!/usr/bin/env python3
"""Read-only audit of actual S2b server payloads; no EDA/contest qualification."""
import argparse,hashlib,json,re,tarfile,tempfile,types,sys
from pathlib import Path
H=Path(__file__).resolve().parent
ROOT=next(p for p in H.parents if (p/'tests/e203/vectors/kwt-silence-v1.json').is_file())
a=argparse.ArgumentParser(description=__doc__);a.add_argument('--out',type=Path);args=a.parse_args()
def need(v,m):
 if not v:raise ValueError(m)
def read(p):return json.loads(p.read_text())
def digest(b):return hashlib.sha256(b).hexdigest()
def sha(p):return digest(p.read_bytes())
original=read(H/'original-export-manifest.json');selected=read(H/'selected-manifest.json')
need(len(selected)==len({r['path']for r in selected})==95,'unique raw set differs')
for r in selected:
 need([x for x in original if x['path']==r['path']]==[r],'original selection differs')
 p=H/'raw'/r['path'];need(p.stat().st_size==r['bytes']and sha(p)==r['sha256'],'raw digest differs: '+r['path'])
need({p.relative_to(H/'raw').as_posix()for p in(H/'raw').rglob('*')if p.is_file()}=={r['path']for r in selected},'raw file set differs')
audit=read(H/'git-source-audit.json')
with tarfile.open(H/'frozen-git-sources.tar.xz','r:xz')as t:
 ms=t.getmembers();need(all(m.isfile()and not Path(m.name).is_absolute()and '..'not in Path(m.name).parts for m in ms)and len(ms)==len({m.name for m in ms}),'unsafe source archive')
 sources={m.name:t.extractfile(m).read()for m in ms}
need({n:digest(b)for n,b in sources.items()}==audit['source_sha256'],'source archive differs')
need(audit['child_changed_from_f49']==['rtl/e203/perips/accel_icb_slave.v'],'hardware delta scope differs')
contract=types.ModuleType('xu_firmware_contract');exec(compile(sources['tools/scripts/xu_firmware_contract.py'],'<frozen-contract>','exec'),contract.__dict__);sys.modules['xu_firmware_contract']=contract
soc=types.ModuleType('xu_frozen_s2b');soc.__file__=str(ROOT/'tools/scripts/e203_soc.py');exec(compile(sources['tools/scripts/e203_soc.py'],'<frozen-runner>','exec'),soc.__dict__)
R=H/'raw/s2b-accept-01';state=read(R/'state.json');accept=read(R/'acceptance/acceptance.json');schedule='bias-hw-pack32-window';steps=['host','numeric','vectors','doctor','baseline','synthetic1','synthetic2','real12']
need(state['status']=='VCS_ACCEPTED_NOT_RETAINED'and accept['status']=='PASS','acceptance incomplete')
need(state['steps']==accept['steps']and [s['name']for s in accept['steps']]==steps and all(s['status']=='PASS'for s in accept['steps']),'eight steps differ')
need(accept['firmware_configuration']==contract.configuration(schedule,'-O2','both-unroll-no-masks'),'acceptance config differs')
for s in accept['steps']:
 need((R/'acceptance'/(s['name']+'.log')).is_file(),'missing actual step log')
 if s['name']in steps[2:]:
  c=s['command'];need(c[c.index('--sim')+1]=='vcs'and c[c.index('--firmware-schedule')+1]==schedule and '--firmware-opt=-O2'in c and c[c.index('--firmware-experiment')+1]=='both-unroll-no-masks','step argv differs')
need(re.search(r'Ran 54 tests in [0-9.]+s\s+OK \(skipped=2\)\s*$',(R/'acceptance/host.log').read_text())is not None,'host completion/count differs')
need(re.search(r'Ran 42 tests in [0-9.]+s\s+OK\s*$',(R/'acceptance/numeric.log').read_text())is not None,'numeric completion/count differs')
need(state['steps'][0]['tests']==54 and state['steps'][0]['skipped']==2,'host receipt differs')
logs_verified=0;source_checks=0;missing=[];negatives=[];real=None
fixture=read(ROOT/'tests/e203/vectors/kwt-silence-v1.json');need(sha(ROOT/'tests/e203/vectors/kwt-silence-v1.tar.gz')==fixture['archive_sha256'],'fixture archive differs')
with tempfile.TemporaryDirectory(prefix='xu-s2b-fixed-vectors-')as tmp:
 soc.load_fixture(Path(tmp),12);vectors=soc.check_vectors(Path(tmp),12)
for mode in ['vectors','doctor','baseline','synthetic1','synthetic2','real12']:
 D=R/'acceptance'/mode;j=read(D/'result.json')
 need(j['status']=='PASS'and j['main_commit']==audit['main_commit']and (mode=='vectors' or j['e203_commit']==audit['e203_commit']),'result identity/status differs: '+mode)
 need(j['simulator']=='vcs'and j['firmware_schedule']==schedule and j['firmware_opt']=='-O2'and j['firmware_experiment']=='both-unroll-no-masks','result backend/config differs')
 for name,value in j.get('log_sha256',{}).items():
  if(D/name).is_file():need(sha(D/name)==value,'declared raw log differs');logs_verified+=1
  else:missing.append(mode+'/'+name)
 for name,value in j.get('source_sha256',{}).items():need(digest(sources[name])==value,'RTL/TB identity differs');source_checks+=1
 if'runner_sha256'in j:need(digest(sources['tools/scripts/e203_soc.py'])==j['runner_sha256'],'runner differs')
 need(digest(sources['tools/scripts/xu_firmware_contract.py'])==j['contract_sha256'],'contract differs')
 if'firmware_build'in j:
  need(j['firmware_sha256']==j['firmware_build']['source_sha256']and all(digest(sources['tests/e203/firmware/'+n])==v for n,v in j['firmware_sha256'].items()),'firmware source differs')
  need(j['firmware_elf_sha256']==j['firmware_build']['elf_sha256']and j['firmware_image_sha256']==j['firmware_build']['image_sha256'],'ELF/image declarations disagree')
 if mode=='vectors':need(j['layers']==vectors,'integer vector recomputation differs')
 if mode=='baseline':need(j['tests']==['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'],'legacy set differs')
 if mode not in ['synthetic1','synthetic2','real12']:continue
 tasks={'synthetic1':1,'synthetic2':2,'real12':12}[mode];log=(D/'simulation.log').read_text();layers=soc.check_log(log,tasks);perf=soc.check_performance(log,layers,schedule)
 for l,p in zip(layers,perf):l['performance']=p
 need(layers==j['layers']and len(j['source_sha256'])==151 and j['tasks']==tasks and j['outputs']==tasks*25344 and j['write_words']==tasks*50688,'actual TASK/PERF/result differs')
 if mode=='real12':need(j['fixture']==fixture and j['vectors']==fixture['files'],'real vectors differ');real=j
 bads=[('missing_TASK',re.sub(r'^TASK_PASS[^\n]*\n','',log,count=1,flags=re.M)),('duplicate_TASK',log+next(l for l in log.splitlines()if l.startswith('TASK_PASS '))+'\n'),('missing_PERF',re.sub(r'^PERF_TASK[^\n]*\n','',log,count=1,flags=re.M)),('duplicate_PERF',log+next(l for l in log.splitlines()if l.startswith('PERF_TASK '))+'\n'),('wrong_MMIO',log.replace('mmio_writes=21734','mmio_writes=21733',1)),('wrong_MAC',log.replace('mac_fire=202752','mac_fire=202751',1)),('wrong_shared_reads',log.replace('shared_reads=23232','shared_reads=23231',1)),('missing_SOC',re.sub(r'^SOC_PASS[^\n]*\n','',log,flags=re.M)),('appended_FATAL',log+'\nFATAL: corruption\n')]
 for label,bad in bads:
  try:l=soc.check_log(bad,tasks);soc.check_performance(bad,l,schedule)
  except ValueError:negatives.append(mode+'/'+label)
  else:raise ValueError('corrupt log accepted: '+label)
for mode,expected,marker in [('packed',[9653,9653,16457,16390,67,33],'XU_PACKED_WRAPPER_PASS'),('stream',[17828,17828,16454,16387,67,33],'XU_STREAM_WRAPPER_PASS')]:
 d=state['direct_vcs'][mode];need(d['status']=='PASS'and d['counts']==expected,'mandatory direct receipt differs')
 for n,v in d['log_sha256'].items():need(sha(R/('direct-'+mode+'-vcs')/n)==v,'mandatory direct log differs');logs_verified+=1
 for n,v in d['source_sha256'].items():need(digest(sources[n])==v,'mandatory direct source differs')
 log=(R/('direct-'+mode+'-vcs')/'simulation.log').read_text();compiled=(R/('direct-'+mode+'-vcs')/'compile.log').read_text();need(Path(json.loads(compiled.splitlines()[0])['argv'][0]).name=='vcs'and 'Compiler version Q-2020.03-SP2-6_Full64' in log,'mandatory direct backend differs');values=re.findall(r'^'+marker+r' accepted=(\d+) retired=(\d+) writes=(\d+) W=(\d+) X=(\d+) starts=(\d+)$',log,re.M);need(len(values)==1 and list(map(int,values[0]))==expected,'mandatory direct actual counters differ');need(len(re.findall(r'^'+marker+r'\b',log,re.M))==1 and not re.search(r'\b(?:FATAL|Error-|FAIL:)\b',log),'mandatory direct log incomplete')
need(not missing,'declared raw log missing: '+str(missing))
need(sum(l['cycles']for l in real['layers'])==14532449,'real12 total differs')
report=dict(status='VERIFIED_VCS_DEVELOPMENT_RESULTS_NOT_QUALIFIED',main_commit=audit['main_commit'],e203_commit=audit['e203_commit'],unique_payloads=95,frozen_source_paths=len(sources),rtl_tb_paths_per_simulation=151,declared_logs_verified=logs_verified,integer_outputs_recomputed=304128,host=dict(tests=54,skipped=2),numeric_tests=42,real12=real,cycle_total=14532449,rejected_actual_log_corruptions=negatives,limitations=['No firmware/ELF/image/simulator binary bytes or actual server vector files retrieved; their declared SHA values are not independently rehashed','Development TB 4ns HF/66ns LF; no candidate formal clear/request, mapped equivalence,150MHz STA,energy,retention or contest score qualification'])
if args.out:args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print('PASS: 95 unique payloads; 151 RTL/TB paths; actual 8 steps,2 mandatory direct VCS,27 rejected corruptions; real12=14532449; NOT_QUALIFIED')
