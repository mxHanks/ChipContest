#!/usr/bin/env python3
"""Read-only native proof of the final DC-persisted clock tree, after fresh PT.

Accepts only completed same-baseline clock/electrical/prune apply+reload chains.
Missing r7 clock buffers require an explicit completed prune cleanup ledger.
No edit, synthesis, clock exception, transport, or credential code is present.
"""
import argparse,gzip,hashlib,json,os,re,signal,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
from clock_persisted_contract import (PLAN_SCHEMA,ORIGINAL_MAP_SHA,CLOCK_SCHEMA,SEED_SCHEMAS,require,literal,tsv,static_contract,emit)

SCHEMA='ingress1064-persisted-clock-read-only-diagnostic-v1'


def clocks(path):
    rows=tsv(path);require(rows and set(rows[0])=={'pin','clocks'},'invalid native clock columns')
    result={r['pin']:sorted(r['clocks'].split())for r in rows}
    require(len(result)==len(rows),'duplicate native clock association');return result


def clean(root,stage,base_hash,chain):
    r=json.loads((root/'execution.json').read_text())
    require(r.get('schema')in SEED_SCHEMAS and r.get('stage')==stage and
        r.get('status')=='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE'and r.get('returncode')==0 and
        r.get('completion_marker')is True and r.get('tool_timed_out')is False and
        r.get('source_drift')==[]and r.get('native_tool_errors')==[]and r.get('missing_outputs')==[]and
        r.get('baseline_execution_sha256')==base_hash and r.get('libraries')==chain['libraries'],
        'final/ancestor native stage incomplete or baseline/library differs')
    marker='DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt'if stage=='apply'else'PRUNE_RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt'if r['schema']=='ingress1064-n3-dead-cone-stage-v1'else'RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt'
    bind_outputs(r,root,[marker]);return r


def prune_partition(apply,reload,ap,rp,inputs):
    names=['deleted-leaves.tsv','removed-added-buffers.tsv','dead-output-visibility.tsv']
    inputs+=bind_outputs(ap,apply,names)
    inputs+=bind_outputs(rp,reload,['retained-clock-association.tsv','removed-clock-association.tsv'])
    old=clocks(apply/'original-clock-association.tsv');retained=clocks(reload/'retained-clock-association.tsv');actual=clocks(reload/'original-clock-association.tsv')
    gone=tsv(reload/'removed-clock-association.tsv');deleted=tsv(apply/'deleted-leaves.tsv')
    require(len(deleted)==1796 and len({r['instance']for r in deleted})==1796,'prune original leaf deletion whitelist differs')
    require(set(deleted[0])=={'wave','instance','reference','is_sequential'}and all(r['is_sequential']in{'true','false'}for r in deleted),'invalid prune deletion columns/state classification')
    state={r['instance']for r in deleted if r['is_sequential']=='true'}
    require(len(state)==36 and all(not r['reference'].startswith('RAMSP')for r in deleted),'prune dead-state count/SRAM preservation differs')
    require(set(gone[0])=={'pin','clocks','proven_deleted_parent'}if gone else False,'invalid removed clock ledger')
    removed={r['pin']:sorted(r['clocks'].split())for r in gone}
    require(len(removed)==len(gone)and not(set(retained)&set(removed))and set(old)==set(retained)|set(removed)and actual==retained,'prune apply clock set is not exact retained+removed partition')
    require(all(old[k]==v for k,v in {**retained,**removed}.items()),'prune original clock association value changed')
    require({r['proven_deleted_parent']for r in gone}==state and all(r['pin'].rsplit('/',1)[0]==r['proven_deleted_parent']and not r['pin'].endswith('/CLK')for r in gone),'removed clocks not exactly explained by36 proven dead state parents')


def seed_chain(apply,reload,base_hash,chain,plan,allow_cleanup):
    ap=clean(apply,'apply',base_hash,chain);rp=clean(reload,'reload',base_hash,chain)
    require(ap['schema']==rp['schema']and ap['package_sha256']==rp['package_sha256']and rp.get('prior_execution_sha256')==sha(apply/'execution.json')and ap.get('seed_identity')==rp.get('seed_identity'),'final apply/reload lineage mismatch')
    for field in ['clock_plan_sha256','electrical_plan_sha256','prune_plan_sha256']:
        require(ap.get(field)==rp.get(field),'final plan differs: '+field)
    inputs=bind_outputs(ap,apply,['mapped.v','mapped.ddc','mapped.sdc','eco.svf','original-clock-association.tsv'])
    inputs+=bind_outputs(rp,reload,['persisted-coverage.rpt','persisted-all_violators.rpt','original-clock-association.tsv'])
    require(any(Path(x['path']).resolve()==(apply/'mapped.v').resolve()and x['sha256']==sha(apply/'mapped.v')and x['bytes']==(apply/'mapped.v').stat().st_size for x in rp.get('inputs',[])),'final fresh PT receipt does not bind applied map bytes')
    if ap['schema']=='ingress1064-n3-dead-cone-stage-v1':prune_partition(apply,reload,ap,rp,inputs)
    else:require(clocks(apply/'original-clock-association.tsv')==clocks(reload/'original-clock-association.tsv'),'final clock association changed during fresh reload')
    inputs +=[verify(p/'execution.json',sha(p/'execution.json'))for p in [apply,reload]]
    removed={};ancestors=[];current=ap;currentroot=apply;seen=set()
    for depth in range(16):
        require(currentroot not in seen,'cyclic apply ancestry');seen.add(currentroot)
        ancestors.append(dict(schema=current['schema'],apply_dir=str(currentroot),execution_sha256=sha(currentroot/'execution.json')))
        if current['schema']=='ingress1064-n3-dead-cone-stage-v1':
            inputs+=bind_outputs(current,currentroot,['removed-added-buffers.tsv'])
            for row in tsv(currentroot/'removed-added-buffers.tsv'):
                require(set(row)=={'round','instance','reference'}and row['reference']=='BUFV2_12TR40'and '/XU_ECO_'in row['instance'],'invalid native newly-dead-buffer cleanup ledger')
                if re.search(r'/XU_ECO_clock_g\d{4}$',row['instance']):
                    require(allow_cleanup and current.get('cleanup_new_dead_buffers')is True and row['instance']in plan['clock_buffers']and row['instance']not in removed,'missing clock buffer not explicitly allowed by completed cleanup ledger')
                    removed[row['instance']]=dict(ledger=str(currentroot/'removed-added-buffers.tsv'),round=row['round'])
        if current['schema']==CLOCK_SCHEMA:
            require(current['package_sha256']==plan['clock_package_sha256']and current.get('clock_groups')==1560,'ancestor clock tree is not sealed r7 package/1560 groups')
            treehash=current.get('prior_execution_sha256');matches=[Path(x['path'])for x in current.get('inputs',[])if x.get('sha256')==treehash and Path(x['path']).name=='execution.json']
            require(len(set(matches))==1,'cannot locate exact completed ancestor native clock tree receipt')
            treeroot=matches[0].resolve().parent;tr=json.loads(matches[0].read_text())
            require(sha(matches[0])==treehash and tr.get('schema')==CLOCK_SCHEMA and tr.get('stage')=='tree'and tr.get('status')=='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE'and tr.get('returncode')==0 and tr.get('completion_marker')is True and tr.get('source_drift')==[]and tr.get('native_tool_errors')==[]and tr.get('missing_outputs')==[]and tr.get('baseline_execution_sha256')==base_hash and tr.get('libraries')==chain['libraries']and tr.get('package_sha256')==plan['clock_package_sha256'],'ancestor native clock tree not completed cleanly')
            inputs+=bind_outputs(tr,treeroot,['clock-root-metrics.tsv']);inputs.append(verify(matches[0],treehash))
            metrics=tsv(treeroot/'clock-root-metrics.tsv');after=[r for r in metrics if r['phase']=='after']
            require(len(after)==1 and int(after[0]['flattened_sink_count'])==18,'ancestor tree metrics not exact r7 root18')
            ref=dict(capacitance=float(after[0]['native_max_capacitance']),transition_ns=float(after[0]['native_max_transition_ns']))
            require(0<ref['capacitance']<1 and 0<ref['transition_ns']<1,'invalid native r7 post-tree cap/slew')
            break
        seed=current.get('seed_identity');require(seed and seed.get('apply_dir')and seed.get('apply_execution_sha256'),'completed final ancestry does not reach r7 clock apply')
        parentroot=Path(seed['apply_dir']).resolve();inputs.append(verify(parentroot/'execution.json',seed['apply_execution_sha256']));parent=clean(parentroot,'apply',base_hash,chain)
        require(seed.get('ddc_sha256')==parent['outputs']['mapped.ddc']['sha256']and current.get('source_ddc_sha256')==parent['outputs']['mapped.ddc']['sha256'],'ancestor repaired seed DDC was not retained by next apply')
        currentroot=parentroot;current=parent
    else:raise ValueError('clock ancestry cap reached')
    return ap,rp,inputs,removed,ancestors,ref


def main():
    global bind_outputs,sha,verify
    from run_stage import baseline,bind_outputs,dump,heavy_jobs,sha,tcl,verify,TOP,PROFILE
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['baseline','baseline-pt-dir','seed-apply','seed-reload','out']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--allow-pruned-clock-buffers',action='store_true');p.add_argument('--run',action='store_true')
    p.add_argument('--timeout-seconds',type=int,default=1200);p.add_argument('--allow-coordinated-busy-jobs',action='store_true');p.add_argument('--coordination-note')
    a=p.parse_args();require(0<a.timeout_seconds<=3600,'diagnostic timeout bound exceeded')
    package=Path(__file__).resolve().parent;seal=package/'package-files.json';entries=json.loads(seal.read_text());inputs=[]
    for name,digest in entries.items():
        q=Path(name);require(not q.is_absolute()and'..'not in q.parts,'unsafe sealed path');inputs.append(verify(package/q,digest))
    require({'run_clock_persisted.py','clock_persisted_contract.py','pt_clock_persisted.tcl','clock-persisted-plan.json.gz'}<=set(entries),'persisted clock diagnostic tools/plan not sealed')
    plan=json.loads(gzip.decompress((package/'clock-persisted-plan.json.gz').read_bytes()));require(plan['schema']==PLAN_SCHEMA and plan['mutation_authorized']is False,'not read-only clock plan')
    base=a.baseline.resolve();ptroot=a.baseline_pt_dir.resolve();more,br,chain=baseline(base,ptroot);inputs+=more
    require(sha(base/'mapped.v')==ORIGINAL_MAP_SHA and sha(ptroot/'execution.json')==plan['baseline_pt_execution_sha256'],'diagnostic source baseline differs')
    apply=a.seed_apply.resolve();reload=a.seed_reload.resolve();ap,rp,more,removed,ancestors,ref=seed_chain(apply,reload,sha(base/'execution.json'),chain,plan,a.allow_pruned_clock_buffers);inputs+=more
    contract=static_contract(apply/'mapped.v',plan,removed);payload=emit(contract)
    record=dict(schema=SCHEMA,status='SEALED_INPUTS_REVIEWED_NOT_EXECUTED',stage='read_only_clock_persistence',mutation_authorized=False,
        package_sha256=sha(seal),diagnostic_plan_sha256=sha(package/'clock-persisted-plan.json.gz'),baseline_execution_sha256=sha(base/'execution.json'),
        final_apply_execution_sha256=sha(apply/'execution.json'),final_reload_execution_sha256=sha(reload/'execution.json'),source_mapped_sha256=sha(apply/'mapped.v'),
        source_ddc_sha256=sha(apply/'mapped.ddc'),ancestor_clock_lineage=ancestors,clock_cleanup_ledger=removed,expected_retained_clock_buffers=len(contract['expected_clock_buffers']),
        expected_root_fanout=len(contract['root_sinks']),native_tree_reference=ref,top=TOP,hardware_profile=PROFILE,max_cores=8,user_authorized_cap=8,
        run_requested=a.run,qualification='NOT_QUALIFIED',timing_verdict='NOT_TIMING_CLOSURE')
    if not a.run:print(json.dumps(record,sort_keys=True));return 0
    jobs=heavy_jobs()
    if jobs or a.allow_coordinated_busy_jobs:require(a.allow_coordinated_busy_jobs and a.coordination_note and len(a.coordination_note.strip())>=16,'coordinated busy-job note required')
    allowed=sorted(os.sched_getaffinity(0));require(len(allowed)>=10,'cap8 reserves at least2 CPUs');os.sched_setaffinity(0,allowed[:8])
    record.update(linux_affinity=allowed[:8],observed_jobs=jobs,coordination_note=a.coordination_note)
    tool=verify(chain['pt']['path'],chain['pt']['sha256'],external=True);libraries=[verify(x['path'],x['sha256'],external=True)for x in chain['libraries']]
    out=a.out.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False);cf=out/'clock-persisted-contract.tcl';cf.write_bytes(payload);inputs.append(verify(cf,sha(cf)))
    dump(out/'clock-persisted-contract.json',contract)
    config=['set ::eco_baseline '+tcl(base),'set ::eco_mapped '+tcl(apply/'mapped.v'),'set ::eco_ddc '+tcl(apply/'mapped.ddc'),
        'set ::eco_reference_clocks '+tcl(reload/'original-clock-association.tsv'),'set ::clock_persist_contract_file '+tcl(cf),'set ::clock_persist_contract_sha '+tcl(sha(cf)),
        'set ::clock_persist_ref_cap '+repr(ref['capacitance']),'set ::clock_persist_ref_slew '+repr(ref['transition_ns']),
        'set ::eco_mode {read_only_clock_persistence}','set ::eco_selected_targets {}','set ::eco_read_only_clock_roots {}',
        'set ::eco_link_libraries [list * '+' '.join(tcl(x['path'])for x in chain['libraries'])+']',
        'set ::eco_library_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256'])for x in chain['libraries'])+']',
        'set ::eco_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256'])for x in inputs)+']']
    configuration=out/'config.tcl';configuration.write_text('\n'.join(config)+'\n')
    lc=chain['library_compiler'];verify(Path(lc['root'])/'bin/lc_shell',lc['launcher_sha256'],external=True)
    env=os.environ.copy();env.update(XU_ECO_PACKAGE=str(package),XU_ECO_CONFIG=str(configuration),XU_ECO_HOST_TOOL='pt',SYNOPSYS_LC_ROOT=lc['root'])
    command=[chain['pt']['path'],'-f',str(package/'pt_clock_persisted.tcl')]
    record.update(status='RUNNING_READ_ONLY_NATIVE_PT',tool=tool,libraries=chain['libraries'],inputs=inputs,command=command,config_sha256=sha(configuration),started_epoch=time.time(),timeout_seconds=a.timeout_seconds)
    receipt=out/'execution.json';timeout=False
    with(out/'native.log').open('x')as log:
        proc=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);record['pid']=proc.pid;dump(receipt,record)
        try:code=proc.wait(timeout=a.timeout_seconds)
        except subprocess.TimeoutExpired:
            timeout=True;os.killpg(proc.pid,signal.SIGTERM)
            try:code=proc.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);code=proc.wait()
    drift=[x['path']for x in inputs+libraries+[tool]if not Path(x['path']).is_file()or sha(x['path'])!=x['sha256']]
    if sha(configuration)!=record['config_sha256']:drift.append(str(configuration))
    errors=re.findall(r'^(?:Error:|Fatal:).*$',(out/'native.log').read_text(errors='replace'),re.M)
    outputs={q.relative_to(out).as_posix():dict(sha256=sha(q),bytes=q.stat().st_size)for q in sorted(out.rglob('*'))if q.is_file()and q.name!='execution.json'}
    required=['persisted-clock-root-metrics.tsv','persisted-clock-output-fanout.tsv','persisted-clock-sram-association.tsv','original-clock-association.tsv','persisted-coverage.rpt','persisted-all_violators.rpt','persisted-setup.rpt','persisted-hold.rpt','required-reports.list','host-options.rpt']
    if(out/'required-reports.list').is_file():required+=(out/'required-reports.list').read_text().splitlines()
    missing=[x for x in required if x not in outputs or not outputs[x]['bytes']];complete=(out/'PERSISTED_CLOCK_DIAGNOSTICS_COMPLETE_NOT_TIMING_CLOSURE.txt').is_file()
    ok=code==0 and not timeout and complete and not drift and not errors and not missing
    record.update(status='NATIVE_READ_ONLY_CLOCK_DIAGNOSTICS_COMPLETE_NOT_TIMING_CLOSURE'if ok else'NATIVE_STAGE_FAILED',returncode=code,tool_timed_out=timeout,finished_epoch=time.time(),completion_marker=complete,source_drift=drift,native_tool_errors=errors,missing_outputs=missing,outputs=outputs)
    dump(receipt,record);print(json.dumps({k:record[k]for k in ['status','returncode','source_drift','native_tool_errors','missing_outputs']},sort_keys=True));return 0 if ok else 1


if __name__=='__main__':
    try:sys.exit(main())
    except(OSError,ValueError,KeyError)as error:print('FAIL: '+str(error),file=sys.stderr);sys.exit(1)
