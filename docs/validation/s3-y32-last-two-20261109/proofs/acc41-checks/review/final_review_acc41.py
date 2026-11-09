#!/usr/bin/env python3
"""Read-only independent saved-result checks; does not execute simulations."""
from pathlib import Path
import copy, hashlib, importlib.util, json, re, sys
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent
R=H.parents[1]
A=R/'acc41-repo'
V=R/'verification'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def must(v,msg):
 if not v:raise AssertionError(msg)
full=read(H/'full12-comparison-independent.json')
task=read(H/'task0-comparison-independent.json')
bp=Path(full['baseline_identity']['result_path']);cp=Path(full['candidate_identity']['result_path'])
b,c=read(bp),read(cp)
must([t['original_layer'] for t in b['task_results']]==list(range(12)),'baseline coverage')
must([t['original_layer'] for t in c['task_results']]==list(range(12)),'candidate coverage')
must(b['outputs']==c['outputs']==304128,'all output count')
rows=[]
for bb,cc in zip(b['task_results'],c['task_results']):
 for key in ('cycles','performance','window','clear','measured_clocks','startup_observations','nice_activity','stream_activity','ready_activity','vectors'):
  must(bb[key]==cc[key],f'raw result layer {bb["original_layer"]}: {key}')
 idx=cc['original_layer']; logs=[]
 for source in (bp.parent,cp.parent):
  p=source/f'task-{idx:02d}'/'simulation.log'; text=p.read_text()
  must(re.findall(r'^TASK_PASS layer=0 outputs=25344 writes=25344 cycles=422768 firmware_cycles=422855$',text,re.M)==['TASK_PASS layer=0 outputs=25344 writes=25344 cycles=422768 firmware_cycles=422855'],'TASK_PASS exact once')
  must(re.findall(r'^SOC_PASS tasks=1 outputs=25344 writes=25344$',text,re.M)==['SOC_PASS tasks=1 outputs=25344 writes=25344'],'SOC_PASS exact once')
  logs.append({'path':str(p),'sha256':sha(p)})
 rows.append({'layer':idx,'payload':cc['cycles'],'clear':int(cc['clear']['clear_cycles']),'gap':int(cc['clear']['gap_to_source_request']),'work_and_windows_equal':True,'raw_pass_logs':logs})
bs,cs=b['original_source_sha256'],c['original_source_sha256']
diffs={p:[bs.get(p),cs.get(p)] for p in set(bs)|set(cs) if bs.get(p)!=cs.get(p)}
must(diffs==read(V/'reviewed-sourcepairs.json'),'only reviewed MacPE pair')
must(len(bs)==len(cs)==171,'171 source membership')
cpus=[p for p in bs if p.startswith('rtl/core/')]
must(all(bs[p]==cs[p] for p in cpus),'CPU/fabric preserved')
# Independently derive product extrema using exact endpoint arithmetic.
pmin=-(2**15)*(2**15-1);pmax=2**30;bmin=-(2**39);bmax=2**39-1
proof=read(H.parent/'full-domain-proof.json'); intervals=[]
for n in range(65):
 lo=bmin+n*pmin;hi=bmax+n*pmax
 must(-(2**40)<=lo<=hi<2**40,'41 bit bound')
 must(proof['prefixes'][n]=={'products':n,'lower':lo,'upper':hi,'fits_signed41':True},'independent prefix value')
 intervals.append([n,lo,hi])
must(bmax+1==2**39 and (bmax+1)>=2**39,'40 bit counterexample')
# v2 guard differs only in Scala, not any tested/generated SV.
first=read(H.parent/'production-source-frozen.json');second=read(H.parent/'production-source-frozen-v2.json')
changed=[p for p in first['files'] if first['files'][p]!=second['files'][p]]
must(changed==['src/main/scala/dotproduct/DotProductEngine.scala'],'guard change only')
must(all(sha(A/p)==v for p,v in second['files'].items()),'source freeze no drift')
base_map=read(R/'baseline-source-freeze.json')['source_sha256']
struct={}
for name in ('LinearAutoGroupCore','LinearAutoGroupCore41'):
 files={p.name:sha(p) for p in (A/'generated'/name).glob('*.sv')}
 saved=read(H.parent/f'guard-v2-{name}-unchanged.json')['generated_sv_sha256_before_and_after']
 must(files==saved,'guard after/before hash unchanged')
 diff=[p for p,d in files.items() if d!=base_map['rtl/perips/'+p]]
 must(diff==([] if name=='LinearAutoGroupCore' else ['MacPE.sv']),'only generated ACC variant')
 struct[name]={'files':len(files),'differences_from_baseline':diff,'guard_sv_unchanged':True}
# Unit fixtures prove final comparator rejects cross-layer cancellation and
# absolute-window/clear differences. They mutate only loaded Python objects.
spec=importlib.util.spec_from_file_location('final_acc41_comparator',V/'compare_acc41.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
pairs=read(V/'reviewed-sourcepairs.json');before=mod.load_campaign(bp,mod.baseline_pins());after=mod.load_campaign(cp,mod.candidate_pins(pairs))
mode='full12-to-full12';before=mod.V.project_layers(before,list(range(12)),mode);after=mod.V.project_layers(after,list(range(12)),mode)
negative=[]
for label in ('cross-layer-phase-cancellation','absolute-window','absolute-clear-response'):
 altered=copy.deepcopy(after)
 if label=='cross-layer-phase-cancellation':
  altered['rows'][0]['phases']['other']+=1;altered['rows'][1]['phases']['other']-=1
 elif label=='absolute-window':altered['rows'][0]['window']['first_request']+=1
 else:altered['rows'][0]['clear']['response_end_cycle']=str(int(altered['rows'][0]['clear']['response_end_cycle'])+1)
 try:mod.compare(before,altered,pairs)
 except ValueError as error:negative.append({'case':label,'rejection':str(error)})
 else:raise AssertionError('comparator accepted '+label)
neg=read(V/'acc41-full12-negatives/result.json')
must(neg['status']=='ALL_EXPECTED_REJECTIONS' and len(neg['cases'])==20,'20 saved corruption negatives')
must(neg['verifier_sha256']==sha(V/'compare_acc41.py'),'negatives final comparator SHA')
out={'status':'PASS','review_scope':'Read-only independent comparator rerun, raw-result/log/source identity, analytic bounds, generated RTL identity; no simulation, synthesis, or PPA claim.','full12_outputs_exact':304128,'layers':rows,'totals':full['totals'],'source_change':diffs,'source_count':171,'unchanged_cpu_core_source_count':len(cpus),'unchanged_all_other_measured_sources':True,'full_domain_independent_prefixes':intervals,'guard_only_scala_update':changed,'generated_structure':struct,'source_drift_v2':[],'independent_comparator_guard_fixtures':negative,'root_saved_corruption_negatives':{'cases':20,'status':neg['status'],'result_sha256':sha(V/'acc41-full12-negatives/result.json')},'artifacts':{str(p):sha(p) for p in (V/'compare_acc41.py',H/'full12-comparison-independent.json',H/'task0-comparison-independent.json',H.parent/'full-domain-proof.json',H.parent/'production-source-frozen-v2.json')},'production_integration_note':'Root will retain installed baseline48 RTL and integrate optional Scala parameter chain separately; this review verifies isolated measured41 candidate only.','limits':{'clear_policy':'REVIEW_PENDING','fifo_payload_physical_zero':'UNPROVEN','performance_gain':0,'PPA':'UNMEASURED'}}
(H/'final-acc41-review.json').write_text(json.dumps(out,indent=2)+'\n')
print('FINAL_ACC41_INDEPENDENT_REVIEW_PASS full12=304128 totals=5874840 layer_cycles=422768+66802 unchanged_sources=170 proof_prefixes=65 corruption_negatives=20 extra_guard_negatives=3')
