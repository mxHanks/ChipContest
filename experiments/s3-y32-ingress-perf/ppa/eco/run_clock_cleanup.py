#!/usr/bin/env python3
"""Exact newly dead clock-buffer cleanup, DC persistence and fresh full PT.
No original leaf/macros, optimization, constraint changes, or transport code.
"""
import argparse,collections,gzip,hashlib,json,os,re,shutil,signal,subprocess,sys,tempfile,time
from pathlib import Path
sys.dont_write_bytecode=True
from clock_persisted_contract import scalar_graph,literal,require,tsv,ORIGINAL_MAP_SHA
SCHEMA='ingress1064-n3-zero-clock-buffer-cleanup-v1'
SEED_SCHEMA='ingress1064-n3-dead-cone-stage-v1'
ASYNC_SCHEMA='ingress1064-n3-async-edge-envelope-v1'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def static_plan(mapped,clock_plan,review):
    require(clock_plan['schema']=='ingress1064-persisted-clock-diagnostic-plan-v1'and len(clock_plan['clock_buffers'])==1560,'exact original1560 clock whitelist required')
    raw=Path(mapped).read_text();allowed=set(clock_plan['clock_buffers']);waves=[];initial=None
    for rnd in range(64):
        with tempfile.TemporaryDirectory(prefix='clock-cleanup-static-')as td:
            q=Path(td)/'map.v';q.write_text(raw);instances,fanout=scalar_graph(q)
        live=allowed&set(instances);require(all(instances[n]=='BUFV2_12TR40'for n in live),'clock whitelist reference changed')
        ready=sorted(n for n in live if not fanout(n+'/Z'))
        if initial is None:initial=ready
        if not ready:break
        waves.append(ready)
        # Remove exact named BUFV2 statements in their mapped hierarchy modules.
        # Names gNNNN are globally unique, so one match per allowed instance.
        for name in ready:
            leaf=name.rsplit('/',1)[1];pattern=r'\bBUFV2_12TR40\s+'+re.escape(leaf)+r'\s*\(.*?\)\s*;'
            raw,count=re.subn(pattern,'',raw,count=0,flags=re.S);require(count==1,'static exact buffer statement ambiguous: '+name)
    else:raise ValueError('static zero-clock cleanup exceeded64 rounds')
    require(len(initial)==34 and set(initial)=={x['instance']for x in review['outside_1_to_32']if x['count']==0},'static initial zero whitelist differs from exact34review')
    removed=[n for w in waves for n in w];require(len(removed)==len(set(removed))<=1560,'cleanup duplicate/out-of-bounds')
    macros=sorted(n for n,r in instances.items()if r=='RAMSP1024X16');require(macros==sorted(clock_plan['original_macro_instances'])and len(macros)==353,'cleanup static original353 macro set changed')
    output={n:fanout(n+'/Z')for n in sorted(live)};require(all(1<=len(s)<=32 for s in output.values()),'cleanup remaining static clock output outside1..32')
    root=fanout(clock_plan['root_driver']);require(1<=len(root)<=32,'cleanup static root outside1..32')
    return dict(schema='ingress1064-zero-clock-cleanup-static-plan-v1',source_map_sha256=sha(mapped),original_mapped_sha256=ORIGINAL_MAP_SHA,
        allowed_clock_buffers=sorted(allowed),waves=waves,initial_zero_count=34,removed=removed,remaining_clock_outputs=[dict(instance=n,sinks=s)for n,s in output.items()],
        root_driver=clock_plan['root_driver'],root_sinks=root,original_macros=macros,removed_original_leaves=0,qualification=False)


def emit(plan):
    lines=['set ::clock_cleanup_waves {}']
    for wave in plan['waves']:lines.append('lappend ::clock_cleanup_waves '+literal(wave))
    lines+=['set ::clock_cleanup_allowed '+literal(plan['allowed_clock_buffers']),
        'set ::clock_cleanup_removed '+literal(plan['removed']),
        'set ::clock_cleanup_root '+literal(plan['root_driver']),
        'set ::clock_cleanup_root_sinks '+literal(plan['root_sinks']),
        'set ::clock_cleanup_macros '+literal(plan['original_macros']),'set ::clock_cleanup_remaining {}']
    for row in plan['remaining_clock_outputs']:lines.append('lappend ::clock_cleanup_remaining [dict create instance '+literal(row['instance'])+' sinks '+literal(row['sinks'])+']')
    return ('\n'.join(lines)+'\n').encode()


def clean_seed(apply,reload,base_hash,chain,verify_bytes=True):
    ap=json.loads((apply/'execution.json').read_text());rp=json.loads((reload/'execution.json').read_text())
    for r,stage in [(ap,'apply'),(rp,'reload')]:
        require(r.get('schema')in{SEED_SCHEMA,ASYNC_SCHEMA} and r.get('stage')==stage and r.get('status')=='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE'and r.get('returncode')==0 and r.get('completion_marker')is True and r.get('tool_timed_out')is False and r.get('source_drift')==[]and r.get('native_tool_errors')==[]and r.get('missing_outputs')==[]and r.get('baseline_execution_sha256')==base_hash and r.get('libraries')==chain['libraries'],'final prune apply/reload incomplete or different original/library')
    require(ap.get('schema')==rp.get('schema'),'seed apply/reload schema mismatch')
    require(ap.get('package_sha256')==rp.get('package_sha256')and ap.get('prune_plan_sha256')==rp.get('prune_plan_sha256')and ap.get('seed_identity')==rp.get('seed_identity')and rp.get('prior_execution_sha256')==sha(apply/'execution.json'),'final prune lineage mismatch')
    if rp.get('source_ddc_sha256'):require(rp['source_ddc_sha256']==ap['outputs']['mapped.ddc']['sha256'],'fresh PT source DDC identity differs')
    inputs=[]
    names=['mapped.v','mapped.ddc','mapped.sdc','eco.svf','original-clock-association.tsv','DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt']
    if ap['schema']==SEED_SCHEMA:names+=['deleted-leaves.tsv','dead-output-visibility.tsv','removed-added-buffers.tsv']
    names+=sorted(n for n in ap['outputs']if n.endswith('.svf')and n!='eco.svf')
    if verify_bytes:
        inputs+=bind_outputs(ap,apply,names)
        marker='PRUNE_RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt'if ap['schema']==SEED_SCHEMA else next((n for n in ['RESET_RELOAD_COLLECTED_NOT_TIMING_CLOSURE.txt','RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt','ASYNC_EDGE_RELOAD_COMPLETE_NOT_QUALIFIED.txt','ASYNC_EDGE_RELOAD_COMPLETE_NOT_TIMING_CLOSURE.txt']if n in rp['outputs']),None)
        require(marker,'supported exact async reload marker absent')
        inputs+=bind_outputs(rp,reload,['original-clock-association.tsv','persisted-coverage.rpt','persisted-all_violators.rpt',marker])
        from run_clock_persisted import prune_partition,clocks
        if ap['schema']==SEED_SCHEMA:
            inputs+=bind_outputs(rp,reload,['retained-clock-association.tsv','removed-clock-association.tsv'])
            prune_partition.__globals__['bind_outputs']=bind_outputs
            prune_partition(apply,reload,ap,rp,inputs)
        else:require(clocks(apply/'original-clock-association.tsv')==clocks(reload/'original-clock-association.tsv'),'async seed changed retained clock association')
    inputs +=[verify(p/'execution.json',sha(p/'execution.json'))for p in [apply,reload]]
    require(any(Path(x['path']).name=='mapped.v'and x['sha256']==ap['outputs']['mapped.v']['sha256']for x in rp['inputs']),'fresh prune PT does not bind source map')
    if ap['schema']==ASYNC_SCHEMA:
        seed=ap.get('seed_identity',{});parenthash=seed.get('apply_execution_sha256')
        matches={Path(x['path']).resolve()for x in ap.get('inputs',[])if Path(x['path']).name=='execution.json'and x.get('sha256')==parenthash}
        require(len(matches)==1,'async seed exact prune ancestor receipt not located')
        parentpath=next(iter(matches));parent=json.loads(parentpath.read_text());require(sha(parentpath)==parenthash and parent.get('schema')==SEED_SCHEMA and parent.get('stage')=='apply'and parent.get('status')=='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE'and parent.get('baseline_execution_sha256')==base_hash and parent.get('libraries')==chain['libraries']and parent.get('returncode')==0 and parent.get('completion_marker')is True and parent.get('source_drift')==[]and parent.get('native_tool_errors')==[],'async seed does not retain completed same-original prune ancestor')
        require(ap.get('source_ddc_sha256')==parent['outputs']['mapped.ddc']['sha256']and seed.get('ddc_sha256')==parent['outputs']['mapped.ddc']['sha256'],'async apply did not load exact prune ancestor DDC')
        inputs.append(verify(parentpath,parenthash))
    return ap,rp,inputs,names


def parent_map_sha(ap):
    seed=ap.get('seed_identity',{});require(seed.get('mapped_sha256'),'async seed source-map identity missing');return seed['mapped_sha256']

def main():
    global bind_outputs,verify
    from run_stage import baseline,bind_outputs,dump,heavy_jobs,verify,tcl,TOP,PROFILE
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=['apply','reload'],required=True)
    for n in ['baseline','baseline-pt-dir','seed-apply','seed-reload','out']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--prior',type=Path);p.add_argument('--run',action='store_true');p.add_argument('--timeout-seconds',type=int,default=1200)
    p.add_argument('--allow-coordinated-busy-jobs',action='store_true');p.add_argument('--coordination-note');a=p.parse_args()
    require(0<a.timeout_seconds<=3600,'cleanup timeout bound exceeded')
    pkg=Path(__file__).resolve().parent;seal=pkg/'package-files.json';entries=json.loads(seal.read_text());inputs=[]
    for n,d in entries.items():
        require(not Path(n).is_absolute()and'..'not in Path(n).parts,'unsafe package path');inputs.append(verify(pkg/n,d))
    plan=json.loads(gzip.decompress((pkg/'clock-cleanup-plan.json.gz').read_bytes()));require(plan['initial_zero_count']==34 and len(plan['waves'])<=64 and plan['removed_original_leaves']==0,'not exact34 zero-clock plan')
    base=a.baseline.resolve();pt=a.baseline_pt_dir.resolve();more,br,chain=baseline(base,pt);inputs+=more
    apply=a.seed_apply.resolve();reload=a.seed_reload.resolve();ap,rp,more,svfs=clean_seed(apply,reload,sha(base/'execution.json'),chain);inputs+=more
    if ap['schema']==SEED_SCHEMA:require(sha(apply/'mapped.v')==plan['source_map_sha256'],'cleanup source finalmap differs')
    # Recompute exact static proof from source bytes, not solely sealed PASS flags.
    cp=json.loads(gzip.decompress((pkg/'clock-persisted-plan.json.gz').read_bytes()));review=json.loads(gzip.decompress((pkg/'zero-clock-review.json.gz').read_bytes()))
    actual_plan=static_plan(apply/'mapped.v',cp,review)
    require({**actual_plan,'source_map_sha256':plan['source_map_sha256']}==plan,'cleanup clock structure/waves changed from source proof')
    if ap['schema']==ASYNC_SCHEMA:require(parent_map_sha(ap)==plan['source_map_sha256'],'async seed prune ancestor map differs from cleanup proof')
    plan=actual_plan
    prior=None
    if a.stage=='reload':
        require(a.prior,'reload requires explicit own cleanup apply');prior=a.prior.resolve();pr=json.loads((prior/'execution.json').read_text())
        require(pr.get('schema')==SCHEMA and pr.get('stage')=='apply'and pr.get('status')=='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE'and pr.get('returncode')==0 and pr.get('completion_marker')is True and pr.get('tool_timed_out')is False and pr.get('source_drift')==[]and pr.get('native_tool_errors')==[]and pr.get('missing_outputs')==[]and pr.get('package_sha256')==sha(seal)and pr.get('seed_apply_execution_sha256')==sha(apply/'execution.json')and pr.get('cleanup_plan_sha256')==sha(pkg/'clock-cleanup-plan.json.gz'),'prior cleanup apply incomplete/differentseed')
        inputs+=bind_outputs(pr,prior,['mapped.v','mapped.ddc','mapped.sdc','eco.svf','clock-cleanup-visibility.tsv','clock-cleanup-deleted.tsv','original-clock-association.tsv','DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt'])
        inputs.append(verify(prior/'execution.json',sha(prior/'execution.json')))
    else:require(a.prior is None,'cleanup apply starts onlyfromcompleted prune seed')
    record=dict(schema=SCHEMA,stage=a.stage,status='SEALED_INPUTS_REVIEWED_NOT_EXECUTED',package_sha256=sha(seal),cleanup_plan_sha256=sha(pkg/'clock-cleanup-plan.json.gz'),baseline_execution_sha256=sha(base/'execution.json'),seed_apply_execution_sha256=sha(apply/'execution.json'),seed_reload_execution_sha256=sha(reload/'execution.json'),prior_execution_sha256=sha(prior/'execution.json')if prior else None,source_map_sha256=plan['source_map_sha256'],removed_new_clock_buffer_count=len(plan['removed']),remaining_clock_buffers=len(plan['remaining_clock_outputs']),root_fanout=len(plan['root_sinks']),removed_original_leaves=0,preserved_SRAM=353,max_cores=8,user_authorized_cap=8,run_requested=a.run,qualification='NOT_QUALIFIED')
    if not a.run:print(json.dumps(record,sort_keys=True));return 0
    jobs=heavy_jobs()
    if jobs or a.allow_coordinated_busy_jobs:require(a.allow_coordinated_busy_jobs and a.coordination_note and len(a.coordination_note)>=16,'coordinated busy-job note required')
    allowed=sorted(os.sched_getaffinity(0));require(len(allowed)>=10,'cap8 reserves2 CPUs');os.sched_setaffinity(0,allowed[:8])
    record.update(linux_affinity=allowed[:8],observed_jobs=jobs,coordination_note=a.coordination_note)
    role='dc'if a.stage=='apply'else'pt';tool=verify(chain[role]['path'],chain[role]['sha256'],external=True);libs=[verify(x['path'],x['sha256'],external=True)for x in chain['libraries']]
    out=a.out.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False);pf=out/'clock-cleanup-plan.tcl';pf.write_bytes(emit(plan));inputs.append(verify(pf,sha(pf)))
    changes=out/'cleanup-changes.tcl';changes.write_text('source '+literal(pf)+'\nclock_cleanup_apply\n');inputs.append(verify(changes,sha(changes)))
    source=apply if a.stage=='apply'else prior
    config=['set ::eco_baseline '+tcl(base),'set ::eco_ddc '+tcl(source/'mapped.ddc'),'set ::eco_mapped '+tcl(source/'mapped.v'),'set ::eco_changes '+tcl(changes),'set ::eco_changes_sha '+tcl(sha(changes)),
        'set ::clock_cleanup_plan_file '+tcl(pf),'set ::clock_cleanup_plan_sha '+tcl(sha(pf)),'set ::eco_reference_clocks '+tcl(reload/'original-clock-association.tsv'),'set ::eco_mode {clock_cleanup}',
        'set ::eco_selected_targets {}','set ::eco_read_only_clock_roots {}','set ::eco_link_libraries [list * '+' '.join(tcl(x['path'])for x in chain['libraries'])+']',
        'set ::eco_library_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256'])for x in chain['libraries'])+']','set ::eco_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256'])for x in inputs)+']']
    if a.stage=='apply':
        shutil.copyfile(reload/'original-clock-association.tsv',out/'original-clock-association.tsv')
        for n in svfs:
            if not n.endswith('.svf'):continue
            target=out/'seed-svf'/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(apply/n,target)
    cfg=out/'config.tcl';cfg.write_text('\n'.join(config)+'\n');env=os.environ.copy();env.update(XU_ECO_PACKAGE=str(pkg),XU_ECO_CONFIG=str(cfg),XU_ECO_HOST_TOOL=role)
    if role=='pt':
        lc=chain['library_compiler'];verify(Path(lc['root'])/'bin/lc_shell',lc['launcher_sha256'],external=True);env['SYNOPSYS_LC_ROOT']=lc['root']
    cmd=[chain[role]['path'],'-f',str(pkg/('dc_clock_cleanup.tcl'if role=='dc'else'pt_clock_cleanup_reload.tcl'))]
    record.update(status='RUNNING',tool=tool,libraries=chain['libraries'],inputs=inputs,command=cmd,config_sha256=sha(cfg),started_epoch=time.time());receipt=out/'execution.json';timeout=False
    with(out/'native.log').open('x')as log:
        proc=subprocess.Popen(cmd,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);record['pid']=proc.pid;dump(receipt,record)
        try:code=proc.wait(timeout=a.timeout_seconds)
        except subprocess.TimeoutExpired:
            timeout=True;os.killpg(proc.pid,signal.SIGTERM)
            try:code=proc.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);code=proc.wait()
    drift=[x['path']for x in inputs+libs+[tool]if not Path(x['path']).is_file()or sha(x['path'])!=x['sha256']]
    if sha(cfg)!=record['config_sha256']:drift.append(str(cfg))
    errors=re.findall(r'^(?:Error:|Fatal:).*$',(out/'native.log').read_text(errors='replace'),re.M)
    outputs={q.relative_to(out).as_posix():dict(sha256=sha(q),bytes=q.stat().st_size)for q in sorted(out.rglob('*'))if q.is_file()and q.name!='execution.json'}
    required=['required-reports.list','host-options.rpt']+(['mapped.v','mapped.ddc','mapped.sdc','eco.svf','clock-cleanup-deleted.tsv','clock-cleanup-visibility.tsv','area-upper-bound.tsv','original-clock-association.tsv']if role=='dc'else['persisted-coverage.rpt','persisted-all_violators.rpt','clock-cleanup-final-fanout.tsv','clock-cleanup-root-fanout.tsv','original-clock-association.tsv'])
    if role=='dc':required+=['seed-svf/'+n for n in svfs if n.endswith('.svf')]
    if(out/'required-reports.list').is_file():required+=(out/'required-reports.list').read_text().splitlines()
    missing=[n for n in required if n not in outputs or not outputs[n]['bytes']];marker='DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt'if role=='dc'else'CLOCK_CLEANUP_RELOAD_COMPLETE_NOT_TIMING_CLOSURE.txt';complete=(out/marker).is_file()
    ok=code==0 and not timeout and complete and not drift and not errors and not missing
    record.update(status='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE'if ok else'NATIVE_STAGE_FAILED',returncode=code,tool_timed_out=timeout,completion_marker=complete,source_drift=drift,native_tool_errors=errors,missing_outputs=missing,outputs=outputs,finished_epoch=time.time());dump(receipt,record)
    print(json.dumps({k:record[k]for k in ['stage','status','returncode','source_drift','native_tool_errors','missing_outputs']},sort_keys=True));return 0 if ok else 1


if __name__=='__main__':
    try:sys.exit(main())
    except(OSError,ValueError,KeyError)as error:print('FAIL: '+str(error),file=sys.stderr);sys.exit(1)
