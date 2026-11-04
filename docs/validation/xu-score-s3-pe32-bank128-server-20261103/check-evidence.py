#!/usr/bin/env python3
"""xu: offline replay of actual bank128 VCS evidence; no PPA/energy claim."""
import argparse,csv,hashlib,io,json,re,subprocess,sys,tarfile,tempfile,types
from pathlib import Path
H=Path(__file__).resolve().parent
MAIN='f75880d4f06ccb7f1c16115bee501f53d9a2abb7'
CHILD='52cfbea1f79f10e44f7d1696f54015797f886b96'
SUB='third-party/e203_hbirdv2'
S32='bias-hw-pe32-autogroup-window';S8='bias-hw-autogroup-window'
FULL=['real12','old32-wide-real12','bank128-oldauto-real12']
MODEL=dict(path='/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP128X16/verilog/RAMSP128X16.v',bytes=89548,sha256='f9d6d881746681dacd4f3851467561e441ee7190776ab566b1f0a729aa3ddb4d')
def need(ok,message):
 if not ok:raise ValueError(message)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_bytes())
def sources(path):
 with tarfile.open(path,'r:xz')as t:
  m=t.getmembers();need(len({x.name for x in m})==len(m)and all(x.isfile()and not Path(x.name).is_absolute()and '..'not in Path(x.name).parts for x in m),'unsafe source archive')
  return {x.name:t.extractfile(x).read()for x in m}
def audit(git_root=None):
 manifest=read(H/'original-export-manifest.json');selected=read(H/'selected-manifest.json')
 need(sha((H/'original-export-manifest.json').read_bytes())=='6a4ee140ad3a2740589d1bef0b70e00dd0cf7b1cae8397ccd92d9047e3ac2c38','original export identity')
 need(len(manifest)==167 and len(selected)==150 and len({x['path']for x in selected})==150,'export count')
 expected={x['path']:x for x in manifest if x['path'].startswith(('s3-pe32-bank128-accept-02/','bank128-deploy-20261103-38/'))}
 need({x['path']:x for x in selected}==expected,'selection differs')
 for r in selected:
  p=H/'raw'/r['path'];need(p.is_file()and not p.is_symlink()and p.stat().st_size==r['bytes']and sha(p.read_bytes())==r['sha256'],'raw identity '+r['path'])
 need({str(p.relative_to(H/'raw'))for p in(H/'raw').rglob('*')if p.is_file()}==set(expected),'extra or missing raw')
 src=sources(H/'frozen-git-sources.tar.xz');sa=read(H/'git-source-audit.json');full=read(H/'full-git-objects.json');listed=read(H/'deployment/source-files.json')
 need(sa['main_commit']==MAIN and sa['e203_commit']==CHILD and len(listed)==sa['full_manifest_blobs']==2637,'source pins')
 need({n:sha(b)for n,b in src.items()}==sa['source_sha256']and len(src)==sa['archived_source_count'],'source snapshot')
 mapped={};git_records={}
 for label,commit,prefix in [('main',MAIN,''),('child',CHILD,SUB+'/')]:
  group=full[label];need(group['commit']==commit,'Git commit differs')
  need(len(group['entries'])==sa[label+'_entries'],'Git entry count')
  repo=None if git_root is None else git_root/(SUB if label=='child'else'')
  for n,r in group['entries'].items():
   name=prefix+n
   if r['kind']=='commit':need(n==SUB and r['mode']=='160000'and r['oid']==CHILD,'gitlink differs');continue
   entry=listed[name];need(entry['git_mode']==r['mode'],'source mode differs');git_records[name]=r
   if repo:
    b=subprocess.check_output(['git','--no-replace-objects','cat-file','blob',r['oid']],cwd=repo)
    need(len(b)==entry['bytes']and sha(b)==entry['sha256'],'immutable Git blob differs '+name)
   mapped[name]=entry
 need(set(mapped)==set(listed),'full tracked source set differs')
 for n,b in src.items():
  original=n.replace(SUB+'/vsim/install/rtl/',SUB+'/rtl/e203/');e=mapped[original]
  need(len(b)==e['bytes']and sha(b)==e['sha256'],'measured source identity '+n)
  need(hashlib.sha1(('blob %d\0'%len(b)).encode()+b).hexdigest()==git_records[original]['oid'],'source Git OID '+n)
 package=read(H/'deployment/package-files.json')
 for n in ['launch.py','README.md','source-files.json','source-identity.json']:
  b=(H/'deployment'/n).read_bytes();need(len(b)==package[n]['bytes']and sha(b)==package[n]['sha256'],'packaged input '+n)
 need((H/'deployment/launch.py').read_bytes()==src['docs/validation/xu-score-s3-pe32-bank128-local-20261103/server_launch.py'],'launcher source')
 r=H/'raw/s3-pe32-bank128-accept-02';s=read(r/'state.json');accept=read(r/'acceptance/acceptance.json')
 names=['host','numeric','vectors','doctor','baseline','synthetic1','synthetic2',*FULL]
 need(s['status']==accept['status']=='VCS_ACCEPTED_NOT_RETAINED'and s['acceptance_status']==accept['acceptance_status']=='PASS','terminal gate')
 need(s['main_commit']==MAIN and s['e203_commit']==CHILD and s['verified_source_paths']==2637,'accepted source')
 need(s['designated_ramsp128_model']==MODEL,'official model identity')
 need(s['steps']==accept['steps']and [x['name']for x in s['steps']]==names and all(x['status']=='PASS'for x in s['steps']),'complete ordered steps')
 boot=read(H/'raw/bank128-deploy-20261103-38/state.json')
 need(boot['status']=='EXECUTED_REVIEW_PENDING_NOT_QUALIFIED'and boot['returncode']==0 and boot['vendor_model']==MODEL and boot['receipt_sha256']==sha((r/'state.json').read_bytes()),'outer execution receipt')
 need(re.search(r'Ran 69 tests in [0-9.]+s\s+OK \(skipped=3\)\s*$',(r/'acceptance/host.log').read_text()),'host69 actual')
 need(re.search(r'Ran 42 tests in [0-9.]+s\s+OK\s*$',(r/'acceptance/numeric.log').read_text()),'numeric42 actual')
 contract=types.ModuleType('xu_firmware_contract');exec(compile(src['tools/scripts/xu_firmware_contract.py'],'<frozen-contract>','exec'),contract.__dict__);sys.modules[contract.__name__]=contract
 soc=types.ModuleType('xu_frozen_bank128_soc');soc.__file__=str(H/'_frozen/tools/scripts/e203_soc.py');exec(compile(src['tools/scripts/e203_soc.py'],'<frozen-soc>','exec'),soc.__dict__)
 fixture=json.loads(src['tests/e203/vectors/kwt-silence-v1.json'])
 with tempfile.TemporaryDirectory(prefix='xu-bank128-golden-')as d:
  p=Path(d);v=p/'tests/e203/vectors';v.mkdir(parents=True)
  for n in ['kwt-silence-v1.json','kwt-silence-v1.tar.gz']:(v/n).write_bytes(src['tests/e203/vectors/'+n])
  soc.TESTS=p/'tests/e203';soc.load_fixture(p/'vectors',12);golden=soc.check_vectors(p/'vectors',12)
 logs=0;source_checks=0;runs={}
 def replay(text,tasks,schedule,variant):
  layers=soc.check_log(text,tasks)
  for row,perf in zip(layers,soc.check_performance(text,layers,schedule,variant)):row['performance']=perf
  return layers,soc.check_autogroup_activity(text,layers,schedule),soc.check_pe_activity(text,layers,schedule,variant)
 for step in s['steps'][2:]:
  n=step['name'];p=r/'acceptance'/n;j=read(p/'result.json');schedule=S8 if n=='bank128-oldauto-real12'else S32;variant='pe32'if n=='old32-wide-real12'else'pe32-bank128';argv=step['argv']
  need(j['status']=='PASS'and j['main_commit']==MAIN and(n=='vectors'or j['e203_commit']==CHILD),'result status/source')
  need(j['simulator']=='vcs'and j['accel_variant']==variant and j['firmware_schedule']==schedule and j['firmware_opt']=='-O2'and j['firmware_experiment']=='both-unroll-no-masks','configuration')
  need(argv[argv.index('--sim')+1]=='vcs'and argv[argv.index('--accel-variant')+1]==variant and argv[argv.index('--firmware-schedule')+1]==schedule,'actual invocation')
  need(j['contract_sha256']==sha(src['tools/scripts/xu_firmware_contract.py'])and j['transaction_contract']==contract.task_contract(schedule),'contract identity')
  for name,want in j.get('source_sha256',{}).items():need(sha(src[name])==want,'measured source');source_checks+=1
  for name,want in j.get('log_sha256',{}).items():need(sha((p/name).read_bytes())==want,'declared log');logs+=1
  if 'firmware_build'in j:
   need(j['firmware_build']['configuration']==contract.configuration(schedule,'-O2','both-unroll-no-masks')and j['firmware_build']['source_sha256']==j['firmware_sha256'],'firmware configuration/source')
   need(j['firmware_elf_sha256']==j['firmware_build']['elf_sha256']and j['firmware_image_sha256']==j['firmware_build']['image_sha256'],'ELF/image receipt')
   need(all(sha(src['tests/e203/firmware/'+k])==v for k,v in j['firmware_sha256'].items()),'firmware bytes')
  if n=='vectors':need(j['layers']==golden and j['outputs']==304128 and j['fixture']==fixture,'independent golden');continue
  if n=='doctor':continue
  if n=='baseline':
   need(j['tests']==['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'],'legacy5')
   for test in j['tests']:
    text=(p/(test+'.log')).read_text();need('SIM=vcs'in text.splitlines()[0]and 'XU_ACCEL_PE32_BANK128=1'in text.splitlines()[0]and 'TEST_PASS'in text and not re.search(r'TEST_FAIL|Time Out|FATAL|ERROR:',text),'actual compact128 legacy')
   continue
  tasks={'synthetic1':1,'synthetic2':2}.get(n,12);text=(p/'simulation.log').read_text();need('Compiler version Q-2020.03-SP2-6_Full64; Runtime version Q-2020.03-SP2-6_Full64'in text,'actual VCS version')
  layers,auto,pe=replay(text,tasks,schedule,variant)
  need(j['layers']==layers and j['autogroup_activity']==auto and j['pe_activity']==pe and j['outputs']==tasks*25344 and j['write_words']==tasks*50688 and step['total_cycles']==sum(x['cycles']for x in layers),'actual full work replay')
  if tasks==12:need(j['fixture']==fixture and j['vectors']==fixture['files'],'real vectors')
  runs[n]=j
 direct={}
 for name,declared in s['direct_vcs'].items():
  p=r/'direct-bank128-vcs'/name
  for file,want in declared.items():need(sha((p/file).read_bytes())==want,'direct raw hash');logs+=1
  cmd=read_line((p/'compile.log').read_text());text=(p/'simulation.log').read_text();args=cmd['argv'];designated='designated-macro'in name
  need(Path(args[0]).name=='vcs'and'Q-2020.03-SP2-6_Full64'in text and not re.search(r'\bFATAL\b|\bFAIL(?:ED)?\b',text),'direct backend')
  need((MODEL['path']in args)==designated and ('+define+ARM_UD_MODEL'in args)==designated,'actual designated model invocation')
  need(not designated or not any(Path(x).name=='mem_128x16.sv'for x in args),'designated behavioral shadow')
  if name.startswith('bank-'):marker='XU_PE32_BANK128_PASS logical_words=512 depths=4 writes=520 reads=524 unknown_reads=4 selected_enable=1 latency=1'
  elif name.startswith('wide'):marker='XU_PE32_WRAPPER_PASS rows=2 groups=16 lanes=512 overlap=190 launches=27 dones=27 accepted=11124 retired=11124'
  else:marker='XU_PE32_COMPAT_WRAPPER_PASS rows=2 groups=64 lanes=512 overlap=958 launches=99 dones=99 accepted=11737 retired=11737'
  need(text.splitlines().count(marker)==1,'direct exact work marker');direct[name]=marker
 need(len(direct)==6,'six mandatory generated/designated paths')
 comparison=read(r/'full12-comparison.json');rows=[]
 for i in range(12):rows.append(dict(layer=i,bank128_wide_cycles=runs[FULL[0]]['layers'][i]['cycles'],old32_wide_cycles=runs[FULL[1]]['layers'][i]['cycles'],bank128_oldauto_cycles=runs[FULL[2]]['layers'][i]['cycles']))
 totals={k:sum(x[k]for x in rows)for k in rows[0]if k!='layer'}
 need(totals=={'bank128_wide_cycles':11376501,'old32_wide_cycles':11376501,'bank128_oldauto_cycles':11842200}and comparison['rows']==rows and comparison['totals']==totals,'three full12 totals')
 need(comparison['designated_model']==MODEL and comparison['result_sha256']=={n:sha((r/'acceptance'/n/'result.json').read_bytes())for n in FULL},'comparison model/results')
 for key in comparison['common_identity']:need(all(runs[n][key]==runs[FULL[0]][key]for n in FULL),'three-way common identity '+key)
 need(runs[FULL[0]]['firmware_image_sha256']==runs[FULL[1]]['firmware_image_sha256']and runs[FULL[0]]['simulator_sha256']==runs[FULL[2]]['simulator_sha256']and runs[FULL[0]]['simulator_sha256']!=runs[FULL[1]]['simulator_sha256'],'physical/firmware control isolation')
 negative=[];j=runs['real12'];text=(r/'acceptance/real12/simulation.log').read_text()
 for label,bad in [('missing_task',re.sub(r'^TASK_PASS[^\n]*\n','',text,count=1,flags=re.M)),('wrong_mac',text.replace('lane_macs=1622016','lane_macs=1622015',1)),('missing_soc',re.sub(r'^SOC_PASS[^\n]*\n','',text,flags=re.M)),('late_fatal',text+'\nFATAL corruption\n')]:
  need(bad!=text,'ineffective negative')
  try:replay(bad,12,S32,'pe32-bank128')
  except ValueError:negative.append(label)
  else:raise ValueError('accepted corrupted evidence '+label)
 return dict(status='ACTUAL_VCS_DEVELOPMENT_REPLAY_PASS_NOT_PHYSICAL_OR_ENERGY_QUALIFICATION',main_commit=MAIN,e203_commit=CHILD,raw_files=len(selected),raw_bytes=sum(x['bytes']for x in selected),source_blobs=2637,archived_source_blobs=len(src),immutable_git_rechecked=git_root is not None,declared_logs_verified=logs,source_hash_checks=source_checks,integer_golden_outputs=304128,direct_paths=direct,full12_totals=totals,rows=rows,semantic_negatives_rejected=negative,limitations=['Actual Y bytes were compared in the frozen TB, not exported individually.','Whole-SoC development simulations use generated SRAM; designated macro proof is the six directed VCS paths.','No mapped equivalence, complete150MHz, PPA or energy qualification.'])
def read_line(text):return json.loads(text.split('\n',1)[0])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--git-root',type=Path);p.add_argument('--out',type=Path);a=p.parse_args();v=audit(a.git_root)
 if a.out:a.out.write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
 print(json.dumps({k:v[k]for k in ['status','raw_files','source_blobs','integer_golden_outputs','full12_totals','semantic_negatives_rejected']},indent=2))
