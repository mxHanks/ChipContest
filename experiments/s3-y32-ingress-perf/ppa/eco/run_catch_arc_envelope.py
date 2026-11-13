#!/usr/bin/env python3
"""Guarded reset/AON delay ECO on an explicitly bound completed native seed.
No transport, credentials, shared-terminal control, compile, clock-tree or RTL edits.
"""
import argparse,csv,json,os,re,shutil,signal,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
from run_stage import baseline,bind_outputs,dump,heavy_jobs,require,sha,tcl,verify,TOP,PROFILE
from plan import catalog
STAGES={
 'discover':('pt','pt_catch_arc_envelope.tcl','RESET_DISCOVERY_COLLECTED_NOT_TIMING_CLOSURE.txt'),
 'diagnose':('pt','pt_catch_arc_envelope.tcl','RESET_DIAGNOSIS_COLLECTED_NOT_TIMING_CLOSURE.txt'),
 'edit':('pt','pt_catch_arc_envelope.tcl','RESET_EDIT_COLLECTED_NOT_TIMING_CLOSURE.txt'),
 'apply':('dc','dc_apply.tcl','DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt'),
 'reload':('pt','pt_catch_arc_envelope.tcl','RESET_RELOAD_COLLECTED_NOT_TIMING_CLOSURE.txt')}
SCHEMA='ingress1064-n3-catch-arc-envelope-v1'
ORIGINAL_MAP='882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e'
def clean(root,stage,base_hash):
 r=json.loads((root/'execution.json').read_text())
 require(r.get('stage')==stage and r.get('returncode')==0 and r.get('status')=='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE' and
         r.get('completion_marker') is True and r.get('tool_timed_out') is False and r.get('source_drift')==[] and r.get('native_tool_errors')==[] and r.get('missing_outputs')==[] and
         r.get('baseline_execution_sha256')==base_hash,'incomplete/foreign native stage: '+str(root))
 return r
def source_seed(a,base_hash,chain):
 apath=a.seed_apply.resolve();rpath=a.seed_reload.resolve()
 ap=clean(apath,'apply',base_hash);rp=clean(rpath,'reload',base_hash)
 require(ap.get('schema') in {'ingress1064-n3-bounded-eco-stage-v1','ingress1064-n3-clock-eco-stage-v1','ingress1064-n3-electrical-eco-stage-v1','ingress1064-n3-dead-cone-stage-v1','ingress1064-n3-zero-clock-buffer-cleanup-v1','ingress1064-n3-bounded-reset-eco-stage-v1',SCHEMA},'unsupported seed lineage')
 require(rp.get('schema')==ap.get('schema') and rp.get('package_sha256')==ap.get('package_sha256') and rp.get('prior_execution_sha256')==sha(apath/'execution.json') and
         ap.get('libraries')==rp.get('libraries')==chain['libraries'],'seed apply/fresh reload chain mismatch')
 require(sha(apath/'mapped.v')==a.seed_mapped_sha256,'explicit seed mapped SHA mismatch')
 require(all(any(Path(x['path']).resolve()==(apath/name).resolve() and x.get('sha256')==sha(apath/name) and x.get('bytes')==(apath/name).stat().st_size for x in rp.get('inputs',[])) for name in ['mapped.v','mapped.ddc']),'seed fresh PT does not bind exact applied V/DDC bytes')
 for key in set(ap)|set(rp):
  if key.endswith('_plan_sha256') or key in {'seed_identity','seed_apply_execution_sha256','seed_reload_execution_sha256'}:require(ap.get(key)==rp.get(key),'seed apply/reload ancestor or plan mismatch: '+key)
 inputs=bind_outputs(ap,apath,['DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt'])
 inputs+=bind_outputs(ap,apath,['mapped.v','mapped.ddc','mapped.sdc','eco.svf','original-clock-association.tsv'])
 if ap.get('schema')=='ingress1064-n3-bounded-reset-eco-stage-v1':require(ap.get('report_guard_errors')==rp.get('report_guard_errors')==[],'reset seed full-report guard failed')
 marker='RESET_ECO_RELOAD_COMPLETE_NOT_QUALIFIED.txt' if rp['schema']=='ingress1064-n3-bounded-reset-eco-stage-v1' else 'CLOCK_CLEANUP_RELOAD_COMPLETE_NOT_TIMING_CLOSURE.txt' if rp['schema']=='ingress1064-n3-zero-clock-buffer-cleanup-v1' else 'PRUNE_RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt' if rp['schema']=='ingress1064-n3-dead-cone-stage-v1' else ('RESET_RELOAD_COLLECTED_NOT_TIMING_CLOSURE.txt' if rp['schema']==SCHEMA else 'RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt')
 inputs+=bind_outputs(rp,rpath,[marker])
 inputs+=bind_outputs(rp,rpath,['persisted-coverage.rpt','persisted-all_violators.rpt','original-clock-association.tsv'])
 inputs += [verify(apath/'execution.json',sha(apath/'execution.json')),verify(rpath/'execution.json',sha(rpath/'execution.json'))]
 return apath,rpath,inputs,dict(apply_execution_sha256=sha(apath/'execution.json'),reload_execution_sha256=sha(rpath/'execution.json'),mapped_sha256=a.seed_mapped_sha256,ddc_sha256=sha(apath/'mapped.ddc'),svf_sha256=sha(apath/'eco.svf'))
def electrical_checks(path):
    raw=path.read_text();rows={}
    for block in re.split(r'(?m)^    Pin: ',raw)[1:]:
        name=block.splitlines()[0].strip()
        kinds=re.findall(r'\b(max_capacitance|min_capacitance|max_transition)\b',block)
        slack=re.search(r'(?m)^    Slack\s+(-?[0-9.eE+-]+) \(VIOLATED\)',block)
        require(len(kinds)==1 and slack is not None,'unparsed electrical constraint block: '+name)
        key=(name,kinds[0]);require(key not in rows,'duplicate electrical check: '+str(key));rows[key]=float(slack[1])
    require(len(rows)==len(re.findall(r'(?m)^    Slack\s+.*\(VIOLATED\)',raw)),'electrical violation reconciliation failed')
    return rows
def review_electrical(before,after):
    b=electrical_checks(before);a=electrical_checks(after)
    require(set(a)<=set(b),'new electrical violation introduced')
    require(all(a[k]>=b[k]-0.00001 for k in a),'existing electrical violation worsened')
    return dict(before_violations=len(b),after_violations=len(a),new_violations=0,worsened_violations=0,comparison_tolerance_ns_or_library_cap=0.00001)
def unknown_checks(path):
 result=set()
 raw=path.read_text()
 for m in re.finditer(r'(?m)^(\S+)\n((?:[ \t].*\n|\n)+)',raw):
  if 'untested' in m[0]:result.add((m[1],re.sub(r'\s+',' ',m[2]).strip()))
 return result
def review_coverage(before,after):
 b,bc=catalog(before.read_text());a,ac=catalog(after.read_text())
 require({k:v['total']for k,v in b.items()}=={k:v['total']for k,v in a.items()},'coverage total/check-type count changed')
 # Coverage report sorts by slack; compare check identities and reasons, never row positions.
 key=lambda r:(r['pin'],r['kind'],re.sub(r'-?[0-9]+(?:\.[0-9]+)?\s+-\s*$','<slack>',re.sub(r'\s+',' ',r['native_block']).strip()))
 before_viol={key(r)for r in bc};after_viol={key(r)for r in ac}
 require(after_viol<=before_viol,'new timing violation introduced')
 require(unknown_checks(after)==unknown_checks(before),'untested identity/reason changed or removed')
 return dict(before=b['All Checks'],after=a['All Checks'],new_violated_checks=0,new_untested_checks=0)

def wait_process(command,cwd,env,timeout,record,receipt,logfile):
    timed_out=False
    with logfile.open('w') as log:
        proc=subprocess.Popen(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        record['pid']=proc.pid;dump(receipt,record)
        try:code=proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(proc.pid,signal.SIGTERM)
            try:code=proc.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);code=proc.wait()
    return code,timed_out



def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=STAGES,required=True)
    for n in ['baseline','baseline-pt-dir','seed-apply','seed-reload','out']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--seed-mapped-sha256',required=True)
    p.add_argument('--prior',type=Path)
    p.add_argument('--selection',choices=['reset_catch','pmu','aon','all'],default='reset_catch')
    p.add_argument('--expansion-discovery',type=Path,help='clean native discover stage required for any expansion override')
    p.add_argument('--waveform-setting',action='append',default=[],metavar='NATIVE_VARIABLE=INTEGER')
    p.add_argument('--run',action='store_true')
    p.add_argument('--timeout-seconds',type=int,default=1800)
    p.add_argument('--allow-coordinated-busy-jobs',action='store_true')
    p.add_argument('--coordination-note')
    a=p.parse_args();require(0<a.timeout_seconds<=3600,'timeout outside bounded range')
    package=Path(__file__).resolve().parent;seal=package/'package-files.json';inputs=[verify(seal,sha(seal))]
    entries=json.loads(seal.read_text())
    require({'run_catch_arc_envelope.py','parallel_reset_gpio_helpers.tcl','pt_catch_arc_envelope.tcl'}<=set(entries),'unsealed extension')
    for name,digest in entries.items():
        q=Path(name);require(not q.is_absolute()and'..'not in q.parts,'unsafe package path');inputs.append(verify(package/q,digest))
    base=a.baseline.resolve();ptroot=a.baseline_pt_dir.resolve()
    more,br,chain=baseline(base,ptroot);inputs+=more;require(sha(base/'mapped.v')==ORIGINAL_MAP,'not original1064 baseline')
    base_hash=sha(base/'execution.json');seed_apply,seed_reload,more,seed=source_seed(a,base_hash,chain);inputs+=more
    mapped=seed_apply/'mapped.v';ddc=seed_apply/'mapped.ddc'
    settings={}
    for pair in a.waveform_setting:
        name,sep,value=pair.partition('=')
        require(sep and re.fullmatch(r'timing_[A-Za-z0-9_]*(waveform|expand)[A-Za-z0-9_]*',name)and value.isdigit()and 0<int(value)<=2000000,'invalid bounded native expansion setting')
        require(name not in settings,'duplicate expansion setting');settings[name]=int(value)
    require(not settings or (a.stage!='discover'and a.expansion_discovery),'native discovery mandatory before expansion change')
    if settings:
        eroot=a.expansion_discovery.resolve();er=clean(eroot,'discover',base_hash)
        require(er.get('schema')==SCHEMA and er.get('package_sha256')==sha(seal)and er.get('seed_identity')==seed,'expansion discovery foreign to this seed/package')
        more=bind_outputs(er,eroot,['waveform-discovery.rpt','expansion-discovery.rpt','pte052-manual.rpt']);inputs+=more+[verify(eroot/'execution.json',sha(eroot/'execution.json'))]
        text=' '.join(Path(x['path']).read_text()for x in more)
        require(all(re.search(r'\b'+re.escape(n)+r'\b',text)for n in settings),'override absent from actual native discovery')
    if a.stage in {'edit','apply','reload'}:
        require(a.prior is not None,'prior diagnose/edit/apply stage required')
        expected={'edit':'diagnose','apply':'edit','reload':'apply'}[a.stage];prior_root=a.prior.resolve();prior=clean(prior_root,expected,base_hash)
        require(prior.get('schema')==SCHEMA and prior.get('package_sha256')==sha(seal)and prior.get('seed_identity')==seed and prior.get('selection')==a.selection and prior.get('waveform_settings')==settings,'prior stage selection/package/seed/settings mismatch')
        names={'diagnose':['target-topology.tsv','endpoint-paths.tsv','original-clock-association.tsv','diagnostic-coverage.rpt'],
                                    'edit':['changes.dctcl','changes.ptsh','changes.text','original-clock-association.tsv','before-coverage.rpt','after-coverage.rpt','endpoint-summary.tsv'],
                                    'apply':['mapped.v','mapped.ddc','mapped.sdc','eco.svf','original-clock-association.tsv']}[expected]
        inputs+=bind_outputs(prior,prior_root,names+[STAGES[expected][2]])+[verify(prior_root/'execution.json',sha(prior_root/'execution.json'))]
        if a.stage=='apply':
            review_coverage(prior_root/'before-coverage.rpt',prior_root/'after-coverage.rpt')
            inputs+=bind_outputs(prior,prior_root,['before-all_violators.rpt','after-all_violators.rpt'])
            review_electrical(prior_root/'before-all_violators.rpt',prior_root/'after-all_violators.rpt')
    else:require(a.prior is None,'discover/diagnose start from explicit seed')
    if a.stage=='reload':mapped=prior_root/'mapped.v';ddc=prior_root/'mapped.ddc'
    record=dict(schema=SCHEMA,stage=a.stage,status='SEALED_INPUTS_REVIEWED_NOT_EXECUTED',mode='catch_arc_envelope',async_edge_envelope_only=True,unknown_required_time_must_remain_unknown=True,max_propagation_increment_ns=0.5,max_propagation_upper_bound_only=True,native_arc_sum_upper_bound_not_path_slack=True,exact_target_scope="EXACT_THREE_AON_RESET_CATCH_RDN_NATIVE_ARC_UPPER_BOUND",package_sha256=sha(seal),baseline_execution_sha256=base_hash,
            baseline_mapped_sha256=sha(base/'mapped.v'),baseline_pt_execution_sha256=sha(ptroot/'execution.json'),seed_identity=seed,selection=a.selection,waveform_settings=settings,
            source_mapped_sha256=sha(mapped),source_ddc_sha256=sha(ddc),prior_execution_sha256=sha(a.prior.resolve()/'execution.json')if a.prior else None,
            top=TOP,hardware_profile=PROFILE,max_cores=8,max_buffers=24,max_per_pin=8,max_added_area_raw=100,run_requested=a.run,qualification='NOT_QUALIFIED',timing_verdict='NOT_TIMING_CLOSURE')
    if not a.run:print(json.dumps(record,sort_keys=True));return 0
    jobs=heavy_jobs()
    if jobs or a.allow_coordinated_busy_jobs:require(a.allow_coordinated_busy_jobs and a.coordination_note and len(a.coordination_note.strip())>=16,'coordinated busy-job note required')
    allowed=sorted(os.sched_getaffinity(0));require(len(allowed)>=10,'cap8 reserves at least2 allowed CPUs');os.sched_setaffinity(0,allowed[:8])
    record.update(linux_affinity=allowed[:8],online_cpus=os.cpu_count(),loadavg=list(os.getloadavg()))
    toolrole,script,marker=STAGES[a.stage];tool=chain[toolrole];identity=verify(tool['path'],tool['sha256'],external=True)
    libraries=[verify(x['path'],x['sha256'],external=True)for x in chain['libraries']];require([x['role']for x in chain['libraries']]==['standard_cell','sram'],'library roles differ')
    out=a.out.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False)
    config=['set ::eco_baseline '+tcl(base),'set ::eco_mapped '+tcl(mapped),'set ::eco_ddc '+tcl(ddc),'set ::eco_mode {catch_arc}',
        'set ::rg_stage '+tcl(a.stage),'set ::rg_selection '+tcl(a.selection),'set ::rg_waveform_settings [list '+' '.join(tcl(n)+' '+str(v)for n,v in sorted(settings.items()))+']',
        'set ::eco_selected_targets {}','set ::eco_read_only_clock_roots {}','set ::eco_buffer_reference {BUFV2_12TR40}',
        'set ::eco_max_buffers 24','set ::eco_max_per_pin 8','set ::eco_max_paths_per_query 8192','set ::eco_max_added_area 100.0','set ::eco_hold_margin 0.03','set ::eco_setup_margin 0.03',
        'set ::eco_link_libraries [list * '+' '.join(tcl(x['path'])for x in chain['libraries'])+']',
        'set ::eco_library_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256'])for x in chain['libraries'])+']',
        'set ::eco_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256'])for x in inputs)+']']
    if a.stage=='apply':
        for n in ['edge-baseline-arrivals.tsv']:
            inputs+=bind_outputs(prior,prior_root,[n]);shutil.copyfile(prior_root/n,out/n)
        seed_record=json.loads((seed_apply/'execution.json').read_text())
        for n in sorted(seed_record['outputs']):
            if n.endswith('.svf'):
                target=out/'seed-svf'/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(seed_apply/n,target);inputs+=bind_outputs(seed_record,seed_apply,[n])
        shutil.copyfile(prior_root/'original-clock-association.tsv',out/'original-clock-association.tsv')
        config+=['set ::eco_changes '+tcl(prior_root/'changes.dctcl'),'set ::eco_changes_sha '+tcl(sha(prior_root/'changes.dctcl'))]
    if a.stage=='reload':
        inputs+=bind_outputs(prior,prior_root,['edge-baseline-arrivals.tsv'])
        config+=['set ::eco_reference_clocks '+tcl(prior_root/'original-clock-association.tsv'),'set ::edge_baseline_reference '+tcl(prior_root/'edge-baseline-arrivals.tsv')]
    configuration=out/'config.tcl';configuration.write_text('\n'.join(config)+'\n')
    env=os.environ.copy();env.update(XU_ECO_PACKAGE=str(package),XU_ECO_CONFIG=str(configuration),XU_ECO_HOST_TOOL=toolrole)
    receipt=out/'execution.json'
    if toolrole=='pt':
        lc=chain['library_compiler'];verify(Path(lc['root'])/'bin/lc_shell',lc['launcher_sha256'],external=True);env['SYNOPSYS_LC_ROOT']=lc['root']
        dc=verify(chain['dc']['path'],chain['dc']['sha256'],external=True);proofroot=out/'native-library-proof';proofroot.mkdir(mode=0o700)
        proofenv=env.copy();proofenv['XU_ECO_HOST_TOOL']='dc';cmd=[chain['dc']['path'],'-f',str(package/'dc_library_proof.tcl')]
        proofrecord=dict(tool=dc,libraries=chain['libraries'],command=cmd,max_cores=8,config_sha256=sha(configuration),started_epoch=time.time())
        record.update(status='RUNNING_NATIVE_DC_FUNCTION_QUERY',native_dc_function=proofrecord)
        code,timeout=wait_process(cmd,proofroot,proofenv,min(a.timeout_seconds,300),record,receipt,proofroot/'native.log')
        errors=re.findall(r'^(?:Error:|Fatal:).*$',(proofroot/'native.log').read_text(errors='replace'),re.M)
        files={q.relative_to(proofroot).as_posix():dict(sha256=sha(q),bytes=q.stat().st_size)for q in sorted(proofroot.rglob('*'))if q.is_file()}
        complete=(proofroot/'DC_LIBRARY_FUNCTION_PROOF_COMPLETE.txt').is_file()
        drift=[x['path']for x in inputs+libraries+[dc]if not Path(x['path']).is_file()or sha(x['path'])!=x['sha256']]
        proofrecord.update(returncode=code,tool_timed_out=timeout,finished_epoch=time.time(),native_tool_errors=errors,completion_marker=complete,source_drift=drift,outputs=files)
        if code or timeout or errors or drift or not complete or not {'dc-library-proof.tsv','host-options.rpt'}<=set(files):
            record.update(status='NATIVE_STAGE_FAILED',returncode=code,completion_marker=False,native_tool_errors=errors,source_drift=drift,missing_outputs=[],failure_stage='native_dc_library_function_query')
            dump(receipt,record);print(json.dumps({'stage':a.stage,'status':record['status'],'failure_stage':record['failure_stage']}));return 1
        function=proofroot/'dc-library-proof.tsv';inputs.append(verify(function,sha(function)))
        configuration.write_text(configuration.read_text()+'set ::eco_dc_function_file '+tcl(function)+'\nset ::eco_dc_function_sha '+tcl(sha(function))+'\n')
    cmd=[tool['path'],'-f',str(package/script)]
    record.update(status='RUNNING',command=cmd,tool=identity,libraries=chain['libraries'],inputs=inputs,config_sha256=sha(configuration),started_epoch=time.time(),timeout_seconds=a.timeout_seconds,observed_jobs=jobs,coordination_note=a.coordination_note,preexisting_jobs_policy='OBSERVE_ONLY_NEVER_STOP_OR_MODIFY')
    code,timeout=wait_process(cmd,out,env,a.timeout_seconds,record,receipt,out/'native.log')
    drift=[x['path']for x in inputs+libraries+[identity]if not Path(x['path']).is_file()or sha(x['path'])!=x['sha256']]
    if sha(configuration)!=record['config_sha256']:drift.append(str(configuration))
    errors=re.findall(r'^(?:Error:|Fatal:).*$',(out/'native.log').read_text(errors='replace'),re.M)
    outputs={q.relative_to(out).as_posix():dict(sha256=sha(q),bytes=q.stat().st_size)for q in sorted(out.rglob('*'))if q.is_file()and q.name!='execution.json'}
    if a.stage=='discover':required=['waveform-discovery.rpt','expansion-discovery.rpt','pte052-manual.rpt','original-clock-association.tsv','diagnostic-coverage.rpt']
    elif a.stage=='diagnose':required=['target-topology.tsv','endpoint-paths.tsv','endpoint-query-attempts.tsv','original-clock-association.tsv','diagnostic-coverage.rpt']
    elif a.stage=='edit':required=['changes.dctcl','changes.ptsh','changes.text','cell-delta.tsv','net-delta.tsv','endpoint-summary.tsv','endpoint-paths.tsv','endpoint-query-attempts.tsv','original-clock-association.tsv','before-coverage.rpt','after-coverage.rpt','after-all_violators.rpt']
    elif a.stage=='apply':required=['mapped.v','mapped.ddc','mapped.sdc','eco.svf','area-upper-bound.tsv','original-clock-association.tsv']
    else:required=['target-topology.tsv','persisted-coverage.rpt','persisted-all_violators.rpt','persisted-setup.rpt','persisted-hold.rpt','persisted-recovery.rpt','persisted-removal.rpt','original-clock-association.tsv','buffer-functions.tsv','leaf-pin-directions.tsv','reference-metadata.tsv']
    if a.stage in {'diagnose','edit','reload'}:required+=['external-context-paths.tsv']
    if toolrole=='pt':required+=['waveform-settings.tsv','buffer-functions.tsv','leaf-pin-directions.tsv','reference-metadata.tsv']
    if a.stage in {'diagnose','edit','reload'}:required+=['edge-arrivals.tsv','edge-status.tsv']
    if a.stage in {'edit','apply'}:required+=['edge-baseline-arrivals.tsv']
    if a.stage=='apply':required+=sorted(q.relative_to(out).as_posix()for q in (out/'seed-svf').rglob('*.svf'))
    required+=['required-reports.list','host-options.rpt']
    if(out/'required-reports.list').is_file():required+=(out/'required-reports.list').read_text().splitlines()
    missing=[x for x in required if x not in outputs or(outputs[x]['bytes']==0 and x!='required-reports.list')]
    complete=(out/marker).is_file();ok=code==0 and complete and not timeout and not drift and not errors and not missing
    record.update(status='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE'if ok else'NATIVE_STAGE_FAILED',returncode=code,tool_timed_out=timeout,finished_epoch=time.time(),completion_marker=complete,source_drift=drift,native_tool_errors=errors,missing_outputs=missing,outputs=outputs)
    if ok and a.stage in {'edit','reload'}:
        try:
            before=out/'before-coverage.rpt' if a.stage=='edit' else seed_reload/'persisted-coverage.rpt'
            after=out/('after-coverage.rpt' if a.stage=='edit' else 'persisted-coverage.rpt')
            record['coverage_review']=review_coverage(before,after)
            before_electrical=out/'before-all_violators.rpt' if a.stage=='edit' else seed_reload/'persisted-all_violators.rpt'
            after_electrical=out/('after-all_violators.rpt' if a.stage=='edit' else 'persisted-all_violators.rpt')
            record['electrical_review']=review_electrical(before_electrical,after_electrical)
        except ValueError as error:
            ok=False;record.update(status='NATIVE_STAGE_FAILED',coverage_review_error=str(error))
    dump(receipt,record)
    if ok and a.stage in {'diagnose','edit','reload'}:
        dump(out/'function-proof.json',dict(schema='xu-native-buffer-function-proof-v1',native_execution=dict(path='execution.json',sha256=sha(receipt)),report=dict(path='buffer-functions.tsv',sha256=sha(out/'buffer-functions.tsv')),direction_report=dict(path='leaf-pin-directions.tsv',sha256=sha(out/'leaf-pin-directions.tsv')),reference_metadata=dict(path='reference-metadata.tsv',sha256=sha(out/'reference-metadata.tsv'))))
    print(json.dumps({k:record[k]for k in ['stage','status','returncode','completion_marker','source_drift','native_tool_errors','missing_outputs']},sort_keys=True));return 0 if ok else 1


if __name__=='__main__':
    try:sys.exit(main())
    except(OSError,ValueError,KeyError)as error:print('FAIL: '+str(error),file=sys.stderr);sys.exit(1)
