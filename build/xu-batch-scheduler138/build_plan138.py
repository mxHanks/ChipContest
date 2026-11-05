#!/usr/bin/env python3
"""Materialize self-contained remote queue inputs from exact returned receipts."""
from pathlib import Path
import json,lzma,hashlib
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
S='/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102'
L='docs/validation/xu-score-s0-soc-20261102'
def load(p):
 b=(ROOT/p).read_bytes();return json.loads(lzma.decompress(b) if p.endswith('.xz') else b)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
inv=load('build/xu-batch-candidates137/candidates137.json')
old=load(L+'/s1-formality-server-20261103/raw/candidate-formality-campaign-20261103-01/state.json')
rep=load(L+'/candidate-formal-completion-20261104/raw/candidate-repaired-formality-20261103-27/state.json.xz')
pe64=load(L+'/candidate-formal-completion-20261104/raw/pe64-formality-campaign-20261103-37/state.json.xz')
bank=load('build/xu-batch-scheduler138/receipts/pe32-bank128-formality57-state.json')
def findrun(obj,key):
 if isinstance(obj,dict):
  if obj.get('candidate')==key:return obj
  for v in obj.values():
   r=findrun(v,key)
   if r:return r
 elif isinstance(obj,list):
  for v in obj:
   r=findrun(v,key)
   if r:return r
 return None
rows=[]
for c in inv['candidates']:
 records={}
 def add(x,sha256=None,role='INPUT'):
  if isinstance(x,str):x={'path':x,'sha256':sha256}
  path=x.get('path');h=x.get('sha256')
  if not path or not h:return
  assert Path(path).is_absolute() and len(h)==64
  row={'path':path,'sha256':h,'role':role}
  if 'bytes' in x:row['bytes']=x['bytes']
  if path in records:assert records[path]['sha256']==h,path
  else:records[path]=row
 p=load(c['ppa']['prepared_local'])
 if c['id']=='baseline_h1_h2':
  for path,h in p['input_sha256'].items():add(path,h,'BASELINE_POWER06_FROZEN_INPUT')
  bf=load(L+'/formality-and-area-server-20261103/raw/full-soc-formality-02/state.json')
  for path,h in bf['input_sha256'].items():add(path,h,'ORIGINAL_FM_INPUT')
  fmroot=S+'/full-soc-formality-02'
  log={'path':fmroot+'/fm.log','sha256':bf['log_sha256']}
  add(fmroot+'/verify.tcl',bf['script_sha256'],'OWN_FM_SCRIPT')
 elif c['id'] in ['s2d','pe32','pe64','compact32_128']:
  r=bank if c['id']=='compact32_128' else findrun(pe64 if c['id']=='pe64' else rep,c['id'])
  assert r,c['id']
  for row in r['frozen_before'].values():add(row,role='OWN_FM_FROZEN_INPUT')
  log=r['log']
  if isinstance(r.get('script'),dict):add(r['script'],role='OWN_FM_SCRIPT')
 else:
  key={'s1_h2_only':'h2-only','s1_sram_bias':'sram-bias','s2b':'s2b'}[c['id']]
  r=findrun(old,key);assert r
  for row in r['frozen_before'].values():add(row,role='OWN_FM_FROZEN_INPUT')
  log=r['log']
 if c['id']!='baseline_h1_h2':
  for rel,row in p['source_files'].items():
   add(row,role='ORIGINAL_SOURCE_BODY')
   add(str(Path(c['ppa']['server_root'])/rel),row['sha256'],'PREPARED_RTL_BODY')
  for name,h in p['generated_sha256'].items():add(c['ppa']['server_root']+'/'+name,h,'PREPARED_CONTROL')
  add(c['ppa']['server_root']+'/prepared.json',sha(ROOT/c['ppa']['prepared_local']) if not c['ppa']['prepared_local'].endswith('.xz') else hashlib.sha256(lzma.decompress((ROOT/c['ppa']['prepared_local']).read_bytes())).hexdigest(),'ORIGINAL_PREPARED_RECEIPT')
  add(c['ppa']['server_root']+'/execution.json',sha(ROOT/c['ppa']['execution_local']),'ORIGINAL_EXECUTION_RECEIPT')
 add(log,role='OWN_FM_NATIVE_LOG')
 for row in c['ppa']['libraries']:add(row,role='LIBRARY')
 add(c['ppa']['analysis_sdc'],role='ORIGINAL_ANALYSIS_SDC')
 add(c['ppa']['original_mapped'],role='ORIGINAL_PPA_MAPPED')
 add(c['formal']['mapped'],role='SELECTED_OWN_FM_MAPPED')
 for row in c['formal']['ordered_svf_inputs']:add(row,role='OWN_FM_ORDERED_SVF')
 for row in c['tool']['producer_files'].values():add(row,role='ORIGINAL_PPA_PRODUCER')
 inputs=sorted(records.values(),key=lambda r:r['path'])
 rows.append({'id':c['id'],'profile':c['profile'],'source':c['source'],'tool':c['tool'],'selected_mapped':c['formal']['mapped'],'original_mapped':c['ppa']['original_mapped'],'ordered_svf_inputs':c['formal']['ordered_svf_inputs'],'freeze_inputs':inputs,'formal_log':log,'formal_expected_passing':(c['formal'].get('passing_points') or {'s1_h2_only':31213,'s1_sram_bias':32748,'s2b':41550}.get(c['id'])),'macro_groups':c['ppa']['memory_groups'],'phases':[
  {'id':'freeze','kind':'freeze','depends':[],'native':False},
  {'id':'adopt_own_fm','kind':'adopt_fm','depends':['freeze'],'native':False},
  {'id':'formal_activity12','kind':'command','depends':['adopt_own_fm'],'native':True,'argv':None,'blocked_reason':'MISSING_CANDIDATE_FORMAL_ACTIVITY_ADAPTER_AND_FROZEN_MODEL_VECTORS_FIRMWARE'},
  {'id':'full_soc_power12','kind':'command','depends':['formal_activity12'],'native':True,'argv':None,'blocked_reason':'MISSING_OWN_ACTIVITY_MAP_SCHEMA_AND_VALIDATED_POWER_ADAPTER'},
  {'id':'qualification','kind':'command','depends':['full_soc_power12'],'native':True,'argv':None,'blocked_reason':'MISSING_CANDIDATE_TIMING_RDC_MACRO_MODE_NUMERIC_QUALIFICATION_COMMANDS'}],
  'missing':c['missing'],'qualification':'NOT_QUALIFIED'})
plan={'schema':'xu-batch-scheduler138-plan-v1','qualification':'NOT_QUALIFIED','inventory137_sha256':sha(ROOT/'build/xu-batch-candidates137/candidates137.json'),'candidate_count':8,'candidates':rows,'guards':{'min_mem_available_bytes':16*1024**3,'min_disk_available_bytes':100*1024**3,'max_native_jobs':1,'native_license_features':[],'license_command':None,'unknown_license_policy':'exclusive_single','license_timeout_seconds':15,'license_known_required_for_native':False,'native_timeout_seconds':21600},'external_adoptions':[{'id':'s2e130','state_path':S+'/s2e-full-soc-power12-20261105-130/execution.json','command_contains':S+'/s2e-full-soc-power-launch-20261105-130/xu_s2e_full_soc_power130.py','action':'READ_ONLY_ADOPT_NEVER_RESTART'},{'id':'s2e134','state_path':S+'/s2e-own-timing-repair-20261105-134/state.json','command_contains':'xu_s2e_timing134.py','action':'READ_ONLY_ADOPT_NEVER_RESTART'},{'id':'s2c57','state_path':S+'/s2c-full-soc-power12-20261104-57/execution.json','command_contains':'xu_candidate_full_soc_power.py','action':'READ_ONLY_ADOPT_NEVER_RESTART'}],'policy':['No network or remote launch within this bundle. Run only after deployment to the original host.','Freeze/adopt run without license guard. Unknown license permits only explicit exclusive_single after all adopted jobs exit; no multi-seat availability is claimed.','Missing formal activity/power/qualification adapters remain pending; no placeholder argv executes.','Existing mappings and ownFM are reused. No remapping or redundant DC/PT replay is enqueued.','Installing phase argv requires an explicit new frozen plan; no loose command injection or source edits.','Native rc0 is diagnostic; all task/activity/energy/qualification review remains required.']}
write(OUT/'queue-plan138.json',plan)
(OUT/'inventory137.snapshot.json').write_bytes((ROOT/'build/xu-batch-candidates137/candidates137.json').read_bytes())
print(json.dumps({'candidates':8,'frozen_input_counts':{r['id']:len(r['freeze_inputs']) for r in rows},'status':'READY_FOR_READ_ONLY_SERVER_PREFLIGHT'}))
