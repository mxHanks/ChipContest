#!/usr/bin/env python3
"""Recheck actual full12 request/clear boundary logs; no power/STA qualification."""
import argparse,hashlib,importlib.util,json,re,sys
from pathlib import Path
H=Path(__file__).resolve().parent;ROOT=next(p for p in H.parents if(p/'tools/ppa/xu_soc_task_activity.py').is_file())
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path);a=p.parse_args()
def need(v,m):
 if not v:raise ValueError(m)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sel=read(H/'selected-manifest.json');orig=read(H/'original-export-manifest.json');need(len(sel)==13 and len({r['path']for r in sel})==13,'raw set differs')
for r in sel:
 need([x for x in orig if x['path']==r['path']]==[r],'selection differs');q=H/'raw'/r['path'];need(q.stat().st_size==r['bytes']and sha(q)==r['sha256'],'raw bytes differ')
B=H/'raw/clear-power-campaign-20261103-01/activity12';j=read(B/'result.json')
need(j['status']=='COLLECTED_12_TASKS_REVIEW_PENDING'and j['taskset_complete']is True and j['requested_task_ids']==list(range(12))and [t['task_id']for t in j['tasks']]==list(range(12)),'complete taskset missing')
need(j['clear_task_before_window']is True and j['sram_pin_alias']is True and j['nominal_hz']==150000000 and j['clock_mode']=='nominal150','formal activity recipe differs')
need(j['e203_commit']=='f49a5fc914971426bd4530db39e270a84b41139f'and j['main_commit']=='26f14f64c4f0d58822412932f365d086ed0d273c','capture source commit differs')
for r in j['helpers']+[j['runner']]:
 relative=r['path'].split('/ChipContest-clear-alias-20261103/',1)[1];need(sha(ROOT/relative)==r['sha256'],'unchanged capture/checker source differs')
spec=importlib.util.spec_from_file_location('xu_actual_full12',ROOT/'tools/ppa/xu_soc_task_activity.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
need(m.activity.canonical_hash(j['configuration'])==j['configuration_sha256'],'configuration identity differs')
rows=[];rejected=[]
for task in j['tasks']:
 i=task['task_id'];D=B/('task_%02d'%i);q=D/'simulation.log';text=q.read_text();need(sha(q)==task['boundary_log']['sha256'],'boundary log digest differs');layer,window=m.checked_log(text,i,'bias-hw-window',True)
 need(task['status']=='COLLECTED_REVIEW_PENDING'and task['configuration_sha256']==j['configuration_sha256']and task['layer']==layer and task['activity_window']==window,'actual TASK/PERF/window differs')
 need(window['formal_elapsed_cycles']==1370856 and window['formal_inclusive_cycles']==1370857 and window['duration_ticks']==9139040000000,'formal cycle/duration differs')
 need(all(task['cache_policy'][k]is True for k in ['fresh_process','reset_cache_enable_zero_observed','complete_fixture_matched_uploads_inside_window_observed','no_prior_task_in_process','physical_initial_clearing_proven']),'clear/cache receipt differs')
 need(task['saif']['duration_ticks']==window['duration_ticks']and task['saif']['timescale_seconds']=='1E-15','SAIF declared duration differs')
 groups=task['saif']['macro_inventory'];need({k:v['observed_count']for k,v in groups.items()}==dict(shared=256,itcm=32,dtcm=32,accelerator_weights=16),'macro inventory differs')
 capture=task['sram_pin_alias_capture'];need(capture['status']=='NORMALIZED_REVIEW_PENDING','pin normalization status differs')
 rows.append(dict(task_id=i,formal_elapsed_cycles=window['formal_elapsed_cycles'],formal_inclusive_cycles=window['formal_inclusive_cycles'],duration_fs=window['duration_ticks'],legacy_accept_cycles=window['legacy_accept_window']['inclusive_cycles']if'inclusive_cycles'in window['legacy_accept_window']else layer['cycles'],source_wait_cycles=window['initial_source_wait_cycles'],pretask_clear_writes=window['pretask_clear']['accepted_writes'],raw_saif=capture['raw_saif'],normalized_saif=capture['normalized_saif'],log_sha256=sha(q)))
 for label,bad in [('missing_request',re.sub(r'^XU_SOURCE_REQUEST.*\n','',text,flags=re.M)),('missing_clear',re.sub(r'^XU_TASK_CLEAR_OBSERVED.*\n','',text,flags=re.M)),('wrong_clear_count',text.replace('writes=33697','writes=33696',1)),('wrong_macro_work',text.replace('mac_fire=202752','mac_fire=202751',1)),('fatal',text+'\nFATAL: injected corruption\n')]:
  try:m.checked_log(bad,i,'bias-hw-window',True)
  except ValueError:rejected.append(str(i)+':'+label)
  else:raise ValueError('accepted corrupt actual capture log: '+label)
result=dict(status='RECHECKED_ACTUAL_FORMAL_CLEAR_REQUEST12_METADATA_NOT_QUALIFIED',task_count=12,total_formal_elapsed_cycles=sum(r['formal_elapsed_cycles']for r in rows),total_duration_fs=sum(r['duration_fs']for r in rows),total_formal_inclusive_cycles=sum(r['formal_inclusive_cycles']for r in rows),rows=rows,rejected_corruptions=rejected,limitations=['Full raw/normalized SAIF files and simulation binaries remain on server; local checker revalidates captured logs,identities,metadata only','No PT conversion/unknown/Liberty/standardcell activity or full150MHz timing qualification','These formal task windows differ from historical development accept windows and cannot be spliced with another candidate configuration'])
if a.out:a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
print('PASS actual12 clear/request logs, allTASK/PERF/macro identities,60 rejected corruptions; NOT_QUALIFIED')
