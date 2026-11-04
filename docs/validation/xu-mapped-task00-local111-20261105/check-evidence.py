#!/usr/bin/env python3
"""Rehash archived111 bytes and inspect existing local records; runs no EDA job."""
from pathlib import Path
import hashlib,json,re
B=Path(__file__).resolve().parent
def need(ok,message):
 if not ok:raise ValueError(message)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name):return json.loads((B/name).read_text())
manifest=load('manifest.json');rows=manifest['files']
need(len({r['path']for r in rows})==len(rows),'duplicate archived payload identity')
actual={str(p.relative_to(B))for p in B.rglob('*')if p.is_file()and p.name!='manifest.json'}
need(actual=={r['path']for r in rows},'archived payload membership differs')
for row in rows:
 path=B/row['path'];need(path.stat().st_size==row['bytes']and sha(path)==row['sha256'],'raw archived bytes differ: '+row['path'])
helper=load('tools/helper-manifest111.json')
for row in helper['files']:
 path=B/'tools'/row['name'];need(path.stat().st_size==row['bytes']and sha(path)==row['sha256'],'archived helper identity differs')
review=load('local-checks-v4/review.json');need(review['qualification']=='NOT_QUALIFIED','host review scope promoted')
checks={r['name']:r for r in review['checks']}
expected={'public-compile','shared-compile','clock-compile','geometry-compile'}
expected|={'public-mode-%d'%i for i in range(6)}|{'shared-mode-%d'%i for i in range(12)}|{'clock-mode-%d'%i for i in range(6)}|{'geometry-mode-%d'%i for i in range(10)}
need(set(checks)==expected and len(checks)==38,'complete existing local command records missing')
for name,row in checks.items():
 log=B/'local-checks-v4'/(name+'.log');need(sha(log)==row['log_sha256'],'recorded command raw log mismatch: '+name)
 wanted=1 if (name.startswith('public-mode-')and int(name.rsplit('-',1)[1])in range(1,6))or(name.startswith('shared-mode-')and int(name.rsplit('-',1)[1])in range(1,10))else 0
 need(row['returncode']==wanted,'recorded native mechanism outcome differs: '+name)
 text=log.read_text(errors='replace')
 if name.startswith('public-mode-'):
  need(('HOST_PUBLIC_CONTRACT_PASS'in text)==(wanted==0),'public fixture outcome missing')
  if wanted:need('XU_MAPPED111_'in text and'REJECT'in text,'public fault lacked actual rejection')
 if name.startswith('shared-mode-'):
  need(('REVIEW111_HANDSHAKE_FIXTURE_SURVIVED'in text)==(wanted==0),'shared handshake outcome missing')
  if wanted:need(('unknown_MMIO_handshake'if name.endswith('-9')else'unknown_shared_handshake')in text,'shared four-state fault rejected for wrong reason')
 if name.startswith('clock-mode-'):
  mode=int(name.rsplit('-',1)[1]);need('ready=1 rejected=%d'%(1 if mode in [1,2,3,4]else 0)in text,'real callback mechanism result missing')
 if name.startswith('geometry-mode-'):
  mode=int(name.rsplit('-',1)[1]);need(('accepted=1 rejected=0'if mode<=1 else'accepted=0 rejected=1')in text,'full macro geometry fault not exercised')
  if mode>=2:need('XU_MAPPED111_ADAPTER_REJECT reason='in text,'geometry negative lacks actual rejection')
runner=load('local-checks-v4/runner-review.json');cases=runner['cases']
expected_cases={'success','compiler-exit7','missing-executable','timeout','changed-input','missing-input-with-primary-failure','interrupted'}
need({r['name']for r in cases}==expected_cases and len(cases)==7,'existing seven actual runner cases missing')
for case in cases:
 directory=B/'local-checks-v4'/('runner-'+case['name']);raw=directory/'state.json';state=json.loads(raw.read_text())
 need(sha(raw)==case['raw_state_sha256']and state==case['state'],'raw runner state differs: '+case['name'])
 need(state['qualification']=='NOT_QUALIFIED'and state['scope']=='PUBLIC_TASK00_DIAGNOSTIC_WITH_60_REQUIRED_PRIVATE_PATHS_PENDING','runner scope promoted')
 need(state['status']==('LOCAL_MECHANISM_EXECUTED_NOT_NATIVE_VCS'if case['name']=='success'else'FAIL_PUBLIC_DIAGNOSTIC_NOT_QUALIFIED'),'runner terminal outcome incorrect')
 for step in state['steps']:
  log=directory/Path(step['log']['path']).name
  need(log.stat().st_size==step['log']['bytes']and sha(log)==step['log']['sha256'],'actual runner raw child log differs')
 if case['name']=='timeout':need('SIGKILL'in state['steps'][0]['termination_signals']and state['error']['type']=='TimeoutExpired','actual timeout cleanup record missing')
 if case['name']=='interrupted':need(state['error']['type']=='KeyboardInterrupt'and state['steps'][0]['termination_reason']=='KeyboardInterrupt','actual interruption terminal missing')
 if case['name']in ['changed-input','missing-input-with-primary-failure']:need(state['identity_errors']and not state['inputs_equal_before_after'],'actual changed/missing input was accepted')
 if case['name']=='missing-input-with-primary-failure':need('returncode=9'in state['error']['message'],'primary failure was overwritten by final identity failure')
need(runner['classification_positive']['status']=='PUBLIC_TASK00_DIAGNOSTIC_COMPLETE_REQUIRED_PRIVATE_GATE_FAILED'and runner['classification_positive']['functional_qualification']=='NOT_QUALIFIED','expected private-gate fatal promoted')
expected_negative={'zero-return','duplicate-public','wrong-count','missing-pending','invented-pending-substring','missing-preload','wrong-boundary','unexpected-SOC-PASS','earlier-rejection','missing-full-geometry','wrong-row255-proof','wrong-source-count'}
need({r['name']for r in runner['classification_negative']}==expected_negative and len(runner['classification_negative'])==12 and all(r['rejection']for r in runner['classification_negative']),'existing twelve classifier rejections missing')
prepared=load('prepared-local-v3/state.json');need(prepared['status']=='PREPARED_PUBLIC_TASK00_DIAGNOSTIC_60_REQUIRED_PRIVATE_GATES_PENDING'and prepared['private_pending_count']==60 and prepared['private_reference_count']==72,'prepared scope differs')
need(prepared['inputs_equal_before_after']and prepared['inputs_before']==prepared['inputs_after']and not prepared['identity_errors'],'prepared source/config/inventory identities changed')
plan=load('prepared-local-v3/private-reference-adapter-plan.json');need(len(plan['original_references'])==72 and sum('pending'in r['handling']for r in plan['original_references'])==60,'original private path coverage was dropped')
need(sha(B/'prepared-local-v3/xu_mapped_task00_vpi111.c')==sha(B/'tools/xu_mapped_task00_vpi111.c'),'prepared adapter differs from handoff')
tb=(B/'prepared-local-v3/tb_xu_mapped_task00111.sv').read_text()
need('SOC_PASS'not in tb and tb.count('XU_MAPPED111_REQUIRED_GATE_PENDING')==1 and 'source_reads!=23232'in tb,'required private gate or full source count missing')
source=(B/'tools/xu_mapped_task00_vpi111.c').read_text()
for guard in ['for(r=0;r<256;++r)','indexed_word_not_in_exact_owning_memory','indexed_word_identity_not_repeatable','indexed_word_aliases_another_row','native_word_parent_disagrees','native_word_scope_disagrees','native_word_index_disagrees','macro_memories_alias','native_preload_4state_readback_mismatch','accelerator_clock_unknown_after_ready']:
 need(guard in source,'handoff guard absent: '+guard)
need(manifest['qualification']=='NOT_QUALIFIED'and manifest['server_execution_included']is False,'local-only archive promoted to server evidence')
print('PASS existing local111 archive: %d raw payload files; 38 command checks; 7 runner cases; 12 classifier rejections; 60 private paths pending; NOT MAPPED VCS OR QUALIFICATION'%len(rows))
