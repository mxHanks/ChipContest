#!/usr/bin/env python3
"""Bounded seventeen-net reset distribution scopeprobe, split, DC replay and fresh PT.

No transport code. Original SDC/libraries fixed. A completed integrated seed is
mandatory. Query only root/group representative native async min/max contexts;
complete coverage and DRC comparisons retain all unknown/no_clock reasons.
Engineering candidate only; external pulse/physical reset signoff unresolved.
"""
import argparse
import csv
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
sys.dont_write_bytecode=True
from run_stage import (baseline,bind_outputs,dump,heavy_jobs,require,sha,tcl,verify,TOP,PROFILE)
from reset_eco_plan import emit, validate, report_guard
from run_reset_stage import prune_clock_partition,clock_table

STAGES={'probe':('pt','pt_reset_eco.tcl','RESET_ECO_EDIT_COMPLETE_NOT_QUALIFIED.txt'),
        'split':('pt','pt_reset_eco.tcl','RESET_ECO_EDIT_COMPLETE_NOT_QUALIFIED.txt'),
        'apply':('dc','dc_apply.tcl','DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt'),
        'reload':('pt','pt_reset_eco.tcl','RESET_ECO_RELOAD_COMPLETE_NOT_QUALIFIED.txt')}
SCHEMA='ingress1064-n3-bounded-reset-eco-stage-v1'
MAPPED_SHA='882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e'


def seed_inputs(a,base,base_hash,chain):
    require(a.seed_apply and a.seed_reload,'bounded reset requires both completed integrated seed apply and freshreload')
    apply=a.seed_apply.resolve();reload=a.seed_reload.resolve()
    ap=json.loads((apply/'execution.json').read_text());schema=ap.get('schema')
    extras={'ingress1064-n3-zero-clock-buffer-cleanup-v1':'CLOCK_CLEANUP_RELOAD_COMPLETE_NOT_TIMING_CLOSURE.txt',
        'ingress1064-n3-async-edge-envelope-v1':'RESET_RELOAD_COLLECTED_NOT_TIMING_CLOSURE.txt',
        'ingress1064-n3-parallel-reset-stage-v1':'RESET_RELOAD_COLLECTED_NOT_TIMING_CLOSURE.txt',
        'ingress1064-n3-bounded-eco-stage-v1':'RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt',
        'ingress1064-n3-clock-eco-stage-v1':'RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt',
        'ingress1064-n3-electrical-eco-stage-v1':'RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt',
        'ingress1064-n3-dead-cone-stage-v1':'PRUNE_RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt'}
    require(schema in extras,'unsupported integrated reset seed schema')
    rp=json.loads((reload/'execution.json').read_text())
    for receipt,stage in [(ap,'apply'),(rp,'reload')]:
        require(receipt.get('schema')==schema and receipt.get('stage')==stage and receipt.get('status')=='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE' and receipt.get('returncode')==0 and receipt.get('completion_marker')is True and receipt.get('tool_timed_out')is False and receipt.get('source_drift')==[] and receipt.get('native_tool_errors')==[] and receipt.get('missing_outputs')==[] and receipt.get('baseline_execution_sha256')==base_hash and receipt.get('libraries')==chain['libraries'],'completed integrated seed receipt/library identity mismatch')
    require(ap.get('package_sha256')==rp.get('package_sha256') and rp.get('prior_execution_sha256')==sha(apply/'execution.json'),'integrated seed apply/freshreload package or prior mismatch')
    for key in set(ap)|set(rp):
        if key.endswith('_plan_sha256')or key in {'seed_identity','seed_apply_execution_sha256','seed_reload_execution_sha256','waveform_settings','selection'}:
            require(ap.get(key)==rp.get(key),'integrated seed plan/ancestor field mismatch: '+key)
    require(all(any(Path(x['path']).name==name and x.get('sha256')==sha(apply/name) and x.get('bytes')==(apply/name).stat().st_size for x in rp.get('inputs',[]))for name in ['mapped.v','mapped.ddc']),'integrated seed reload does not bind applied V/DDC bytes')
    svfs=sorted(n for n in ap.get('outputs',{})if n.endswith('.svf'));require('eco.svf'in svfs,'integrated seed missing own SVF')
    inputs=bind_outputs(ap,apply,['DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt','mapped.v','mapped.ddc','mapped.sdc','original-clock-association.tsv']+svfs)
    inputs+=bind_outputs(rp,reload,[extras[schema],'persisted-coverage.rpt','persisted-all_violators.rpt','original-clock-association.tsv'])
    if schema=='ingress1064-n3-dead-cone-stage-v1':
        more,clock_lineage=prune_clock_partition(apply,reload,ap,rp);inputs+=more
    else:
        require(clock_table(apply/'original-clock-association.tsv')==clock_table(reload/'original-clock-association.tsv'),'integrated seed current clock associations changed')
        clock_lineage=dict(mode='SEMANTIC_CURRENT_CLOCK_ASSOCIATIONS_UNCHANGED',current_reload_clock_sha256=sha(reload/'original-clock-association.tsv'))
    inputs += [verify(p/'execution.json',sha(p/'execution.json'))for p in [apply,reload]]
    identity=dict(mode='EXPLICIT_COMPLETED_INTEGRATED_SEED_RETAINED_READ_ONLY',schema=schema,apply_dir=str(apply),reload_dir=str(reload),apply_execution_sha256=sha(apply/'execution.json'),reload_execution_sha256=sha(reload/'execution.json'),mapped_sha256=sha(apply/'mapped.v'),ddc_sha256=sha(apply/'mapped.ddc'),seed_svfs=[dict(source_name=n,retained_name='seed-svf/'+n,sha256=sha(apply/n))for n in svfs],ancestor_seed_identity=ap.get('seed_identity'),seed_clock_lineage=clock_lineage)
    return apply/'mapped.v',apply/'mapped.ddc',inputs,identity


def prior_inputs(root,stage,package_hash,baseline_hash,plan_hash,seed):
    r=json.loads((root/'execution.json').read_text())
    require(r.get('schema')==SCHEMA and r.get('stage')==stage and r.get('status')=='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE' and r.get('returncode')==0 and r.get('tool_timed_out')is False and r.get('completion_marker')is True and r.get('source_drift')==[] and r.get('native_tool_errors')==[] and r.get('missing_outputs')==[] and r.get('report_guard_errors')==[], 'prior reset native collection/guard incomplete')
    require(r.get('package_sha256')==package_hash and r.get('baseline_execution_sha256')==baseline_hash and r.get('reset_eco_plan_sha256')==plan_hash and r.get('seed_identity')==seed,'reset prior package/seed/plan differs')
    names=['execution.json']
    if stage in {'probe','split'}:names=['changes.dctcl','changes.ptsh','changes.text','original-clock-association.tsv','after-coverage.rpt','after-all_violators.rpt','reset-root-metrics.tsv','reset-inserted-metrics.tsv','buffer-functions.tsv']
    if stage=='apply':names=['mapped.v','mapped.ddc','mapped.sdc','eco.svf','original-clock-association.tsv']+[n for n in r['outputs']if n.startswith('seed-svf/')and n.endswith('.svf')]
    marker=STAGES[stage][2]
    return r,bind_outputs(r,root,names+[marker])+[verify(root/'execution.json',sha(root/'execution.json'))]


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
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--baseline-pt-dir',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--prior',type=Path)
    p.add_argument('--seed-apply',type=Path)
    p.add_argument('--seed-reload',type=Path)
    execution=p.add_mutually_exclusive_group()
    execution.add_argument('--run',action='store_true')
    execution.add_argument('--dry-run',dest='run',action='store_false',help='verify bound local inputs without tool or library access (default)')
    p.set_defaults(run=False)
    p.add_argument('--timeout-seconds',type=int,default=1800)
    p.add_argument('--max-buffers',type=int,default=128)
    p.add_argument('--required-margin',type=float,default=0.03)
    p.add_argument('--max-paths-per-query',type=int,default=1024)
    p.add_argument('--max-added-area',type=float,default=5000.0)
    p.add_argument('--allow-coordinated-busy-jobs',action='store_true')
    p.add_argument('--coordination-note')
    a=p.parse_args()
    require(0<a.timeout_seconds<=3600 and 0<a.max_buffers<=2048 and 0<a.max_added_area<=10000,'bounded electrical experiment limits exceeded')
    package=Path(__file__).resolve().parent;seal=package/'package-files.json'
    entries=json.loads(seal.read_text());inputs=[]
    for name,digest in entries.items():
        q=Path(name);require(not q.is_absolute()and'..'not in q.parts,'unsafe sealed path')
        inputs.append(verify(package/q,digest))
    require({'run_reset_eco_stage.py','pt_reset_eco.tcl','prepare_reset_eco.py','reset_eco_plan.py','reset-eco-plan.json.gz','run_reset_stage.py'}<=set(entries),'reset ECO tools/plan not sealed; use prepare_reset_eco.py')
    base=a.baseline.resolve();ptroot=a.baseline_pt_dir.resolve()
    more,base_receipt,chain=baseline(base,ptroot);inputs+=more
    require([(x['role'],x['sha256'])for x in chain['libraries']]==[
        ('standard_cell','f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723'),
        ('sram','c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f')],
        'electrical chain must retain exact original standard-cell and SRAM DB hashes')
    require(sha(base/'mapped.v')==MAPPED_SHA,'electrical plan is not original1064 fixed map')
    base_hash=sha(base/'execution.json');mapped,ddc,more,seed=seed_inputs(a,base,base_hash,chain);inputs+=more
    require(seed is not None,'bounded reset ECO requires explicit completed integrated seed apply+freshreload')
    planpath=package/'reset-eco-plan.json.gz';plan=json.loads(gzip.decompress(planpath.read_bytes()));validate(plan);plan_hash=sha(planpath)
    require(plan['seed_mapped_sha256']==sha(mapped),'reset plan is not bound to this final integrated seed map')
    require(a.required_margin>=0.03 and a.required_margin==plan['required_margin_ns'] and 64<=a.max_paths_per_query<=4096,'reset margin/query budget differs from reviewed plan')
    require(a.max_buffers>=len(plan['groups'])or a.stage=='probe','reset budget must cover full explicit128group plan')
    if a.stage!='probe':
        require(a.prior is not None,'prior reset scopeprobe/split/apply is mandatory')
        expected={'split':'probe','apply':'split','reload':'apply'}[a.stage]
        prior_root=a.prior.resolve();prior,more=prior_inputs(prior_root,expected,sha(seal),base_hash,plan_hash,seed);inputs+=more
    else:require(a.prior is None,'scopeprobe starts fresh from same explicit completed integrated seed')
    if a.stage=='reload':mapped=prior_root/'mapped.v';ddc=prior_root/'mapped.ddc'
    record=dict(schema=SCHEMA,stage=a.stage,status='SEALED_INPUTS_REVIEWED_NOT_EXECUTED',mode='reset_bounded',
        mutation_goal='FOUR_LOAD_API_SCOPE_PROBE_NOT_ELECTRICAL_OPTIMIZATION' if a.stage=='probe' else 'BOUNDED_NONRESET_SPLIT_REQUIRES_ELECTRICAL_IMPROVEMENT',
        package_sha256=sha(seal),reset_eco_plan_sha256=plan_hash,baseline_execution_sha256=base_hash,
        baseline_mapped_sha256=sha(base/'mapped.v'),baseline_pt_execution_sha256=sha(ptroot/'execution.json'),
        baseline_pt_dir=str(ptroot),seed_identity=seed,source_mapped_sha256=sha(mapped),source_ddc_sha256=sha(ddc),
        prior_execution_sha256=sha(a.prior.resolve()/'execution.json')if a.prior else None,
        top=TOP,hardware_profile=PROFILE,max_cores=8,user_authorized_cap=8,max_buffers=a.max_buffers,
        max_added_area_raw=a.max_added_area,reset_groups=1 if a.stage=='probe'else len(plan['groups']),
        reset_roots=17,required_margin_ns=a.required_margin,query_scope='SEVENTEEN_ROOT_WORST64_CONTEXTS_PLUS_COMPLETE_GLOBAL_COVERAGE',
        physical_pulse_signoff='UNRESOLVED',existing_unknown_no_clock='RETAINED_NOT_MET',
        generated_reset_tcl_sha256=__import__('hashlib').sha256(emit(plan,a.stage if a.stage!='apply'else'split')).hexdigest(),
        run_requested=a.run,qualification='NOT_QUALIFIED',timing_verdict='NOT_TIMING_CLOSURE')
    if not a.run:print(json.dumps(record,sort_keys=True));return 0
    jobs=heavy_jobs()
    if jobs or a.allow_coordinated_busy_jobs:
        require(a.allow_coordinated_busy_jobs and a.coordination_note and len(a.coordination_note.strip())>=16,'coordinated busy-job note required')
    allowed=sorted(os.sched_getaffinity(0));require(len(allowed)>=10,'cap8 reserves at least2 allowed CPUs')
    os.sched_setaffinity(0,allowed[:8]);record.update(linux_affinity=allowed[:8],online_cpus=os.cpu_count(),loadavg=list(os.getloadavg()))
    toolrole,script,marker=STAGES[a.stage];tool=chain[toolrole]
    identity=verify(tool['path'],tool['sha256'],external=True)
    libraries=[verify(x['path'],x['sha256'],external=True)for x in chain['libraries']]
    require([x['role']for x in chain['libraries']]==['standard_cell','sram'],'native library role order differs')
    out=a.out.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False)
    payload=emit(plan,a.stage if a.stage!='apply'else'split')
    planfile=out/'reset-eco-plan.tcl';planfile.write_bytes(payload);inputs.append(verify(planfile,sha(planfile)))
    config=['set ::eco_baseline '+tcl(base),'set ::eco_mapped '+tcl(mapped),'set ::eco_mapped_sha '+tcl(sha(mapped)),
        'set ::eco_ddc '+tcl(ddc),'set ::eco_mode {reset_bounded}',
        'set ::reset_eco_action '+tcl(a.stage if a.stage!='apply'else'split'),
        'set ::reset_eco_plan_file '+tcl(planfile),'set ::reset_eco_plan_sha '+tcl(sha(planfile)),
        'set ::reset_required_margin '+repr(a.required_margin),'set ::reset_max_paths_per_query '+str(a.max_paths_per_query),
        'set ::eco_selected_targets {}','set ::eco_read_only_clock_roots {}',
        'set ::eco_buffer_reference {BUFV2_12TR40}','set ::eco_max_buffers '+str(a.max_buffers),
        'set ::eco_max_per_pin 8','set ::eco_max_paths_per_query 8192',
        'set ::eco_max_added_area '+repr(a.max_added_area),'set ::eco_hold_margin 0.03','set ::eco_setup_margin 0.03',
        'set ::eco_link_libraries [list * '+' '.join(tcl(x['path'])for x in chain['libraries'])+']',
        'set ::eco_library_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256'])for x in chain['libraries'])+']',
        'set ::eco_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256'])for x in inputs)+']']
    if a.stage=='apply':
        shutil.copyfile(prior_root/'original-clock-association.tsv',out/'original-clock-association.tsv')
        config+=['set ::eco_changes '+tcl(prior_root/'changes.dctcl'),'set ::eco_changes_sha '+tcl(sha(prior_root/'changes.dctcl'))]
        if seed:
            for item in seed['seed_svfs']:
                target=out/item['retained_name'];target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                shutil.copyfile(Path(seed['apply_dir'])/item['source_name'],target)
                inputs.append(verify(target,item['sha256']))
    if a.stage!='apply':config+=['set ::reset_eco_reference_clocks '+tcl((prior_root if a.stage=='reload'else Path(seed['reload_dir']))/'original-clock-association.tsv')]
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
    if a.stage in {'probe','split'}:
        required=['changes.dctcl','changes.ptsh','changes.text','cell-delta.tsv','net-delta.tsv','reset-root-metrics.tsv','reset-group-ledger.tsv','reset-inserted-metrics.tsv','before-reset-root-paths.tsv','after-reset-root-paths.tsv','before-coverage.rpt','after-coverage.rpt','after-all_violators.rpt','original-clock-association.tsv','buffer-functions.tsv','leaf-pin-directions.tsv','reference-metadata.tsv','RESET_PHYSICAL_PULSE_SIGNOFF_UNRESOLVED.txt']
    elif a.stage=='apply':required=['mapped.v','mapped.ddc','mapped.sdc','eco.svf','area-upper-bound.tsv','original-clock-association.tsv']+[x['retained_name']for x in seed['seed_svfs']]
    else:required=['reset-root-metrics.tsv','reset-inserted-metrics.tsv','persisted-reset-root-paths.tsv','persisted-coverage.rpt','persisted-all_violators.rpt','persisted-setup.rpt','persisted-hold.rpt','persisted-recovery.rpt','persisted-removal.rpt','persisted-min_pulse_width.rpt','original-clock-association.tsv','buffer-functions.tsv','leaf-pin-directions.tsv','reference-metadata.tsv','RESET_PHYSICAL_PULSE_SIGNOFF_UNRESOLVED.txt']
    required+=['required-reports.list','host-options.rpt']
    if(out/'required-reports.list').is_file():required+=(out/'required-reports.list').read_text().splitlines()
    missing=[x for x in required if x not in outputs or(outputs[x]['bytes']==0 and x!='required-reports.list')]
    guard_errors=[];guard_result=None
    if code==0 and not missing and a.stage in {'probe','split','reload'}:
        try:
            reference=Path(seed['reload_dir']);before_cov=reference/'persisted-coverage.rpt';before_drc=reference/'persisted-all_violators.rpt'
            phase='persisted'if a.stage=='reload'else'after'
            guard_result=report_guard(before_cov,out/(phase+'-coverage.rpt'),before_drc,out/(phase+'-all_violators.rpt'))
            dump(out/'report-guard.json',guard_result)
        except (OSError,ValueError,KeyError)as error:guard_errors.append(str(error))
    complete=(out/marker).is_file();ok=code==0 and complete and not timeout and not drift and not errors and not missing and not guard_errors
    record.update(status='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE'if ok else'NATIVE_STAGE_FAILED',returncode=code,tool_timed_out=timeout,finished_epoch=time.time(),completion_marker=complete,source_drift=drift,native_tool_errors=errors,missing_outputs=missing,report_guard_errors=guard_errors,report_guard_result=guard_result,outputs=outputs)
    dump(receipt,record)
    if ok and a.stage in {'probe','split','reload'}:
        dump(out/'function-proof.json',dict(schema='xu-native-buffer-function-proof-v1',native_execution=dict(path='execution.json',sha256=sha(receipt)),report=dict(path='buffer-functions.tsv',sha256=sha(out/'buffer-functions.tsv')),direction_report=dict(path='leaf-pin-directions.tsv',sha256=sha(out/'leaf-pin-directions.tsv')),reference_metadata=dict(path='reference-metadata.tsv',sha256=sha(out/'reference-metadata.tsv'))))
    print(json.dumps({k:record[k]for k in ['stage','status','returncode','completion_marker','source_drift','native_tool_errors','missing_outputs']},sort_keys=True));return 0 if ok else 1


if __name__=='__main__':
    try:sys.exit(main())
    except(OSError,ValueError,KeyError)as error:print('FAIL: '+str(error),file=sys.stderr);sys.exit(1)
