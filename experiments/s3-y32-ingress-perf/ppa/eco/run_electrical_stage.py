#!/usr/bin/env python3
"""Native guarded hierarchy-local electrical topology, probe, split, DC replay and fresh PT.

No transport code. Original SDC/libraries stay fixed. Optional completed hold or
clock apply+fresh-reload seed retains the applied DDC and every seed SVF.
Only 51 nonreset nets are split; 17 asynchronous reset nets remain unresolved.
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
from prepare_electrical import emit, validate_plan

STAGES={'topology':('pt','pt_electrical_edit.tcl','ELECTRICAL_EDIT_COLLECTED_NOT_TIMING_CLOSURE.txt'),
        'probe':('pt','pt_electrical_edit.tcl','ELECTRICAL_EDIT_COLLECTED_NOT_TIMING_CLOSURE.txt'),
        'split':('pt','pt_electrical_edit.tcl','ELECTRICAL_EDIT_COLLECTED_NOT_TIMING_CLOSURE.txt'),
        'apply':('dc','dc_apply.tcl','DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt'),
        'reload':('pt','pt_electrical_edit.tcl','RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt')}
SCHEMA='ingress1064-n3-electrical-eco-stage-v1'
MAPPED_SHA='882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e'


def clean_receipt(root,schema,stage,base_hash):
    r=json.loads((root/'execution.json').read_text())
    require(r.get('schema')==schema and r.get('stage')==stage and r.get('returncode')==0 and
        r.get('status')=='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE' and
        r.get('completion_marker') is True and r.get('tool_timed_out') is False and r.get('source_drift')==[] and
        r.get('native_tool_errors')==[] and r.get('missing_outputs')==[] and
        r.get('baseline_execution_sha256')==base_hash,'prior/seed native stage is incomplete or has a different original baseline')
    marker={'apply':'DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt','reload':'RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt'}.get(stage,'ELECTRICAL_EDIT_COLLECTED_NOT_TIMING_CLOSURE.txt')
    bind_outputs(r,root,[marker])
    return r


def seed_inputs(a,base,base_hash,chain):
    if not a.seed_apply and not a.seed_reload:
        return base/'mapped.v',base/'mapped.ddc',[],None
    require(a.seed_apply and a.seed_reload,'seed requires BOTH completed apply and successful fresh PT reload')
    apply=a.seed_apply.resolve();reload=a.seed_reload.resolve()
    schema=json.loads((apply/'execution.json').read_text()).get('schema')
    require(schema in {'ingress1064-n3-bounded-eco-stage-v1','ingress1064-n3-clock-eco-stage-v1'},'seed must be completed hold or clock lineage')
    ap=clean_receipt(apply,schema,'apply',base_hash);rp=clean_receipt(reload,schema,'reload',base_hash)
    key='clock_plan_sha256' if schema.endswith('clock-eco-stage-v1') else 'target_plan_sha256'
    require(ap.get(key) and ap.get(key)==rp.get(key) and ap.get('package_sha256')==rp.get('package_sha256') and
        rp.get('prior_execution_sha256')==sha(apply/'execution.json') and
        ap.get('libraries')==rp.get('libraries')==chain['libraries'] and
        ap.get('seed_identity')==rp.get('seed_identity'),'seed reload not bound to supplied applied DDC/library/lineage')
    if schema.endswith('clock-eco-stage-v1'):
        require(rp.get('source_mapped_sha256')==sha(apply/'mapped.v'),'clock seed reload source map differs')
    else:
        require(all(any(Path(x['path']).name==name and x.get('sha256')==sha(apply/name) and x.get('bytes')==(apply/name).stat().st_size for x in rp.get('inputs',[])) for name in ['mapped.v','mapped.ddc']),
            'hold seed fresh reload does not bind applied mapped V/DDC input bytes')
    svfs=sorted(name for name in ap.get('outputs',{}) if name.endswith('.svf'))
    require('eco.svf' in svfs,'seed lacks native ECO SVF')
    inputs=bind_outputs(ap,apply,['mapped.v','mapped.ddc','mapped.sdc','original-clock-association.tsv']+svfs)
    inputs+=bind_outputs(rp,reload,['persisted-coverage.rpt','persisted-all_violators.rpt','original-clock-association.tsv','buffer-functions.tsv','leaf-pin-directions.tsv','reference-metadata.tsv'])
    require(sha(apply/'original-clock-association.tsv')==sha(reload/'original-clock-association.tsv'),'seed clock association drift after persistence')
    inputs += [verify(apply/'execution.json',sha(apply/'execution.json')),verify(reload/'execution.json',sha(reload/'execution.json'))]
    identity={'mode':'EXPLICIT_COMPLETED_HOLD_OR_CLOCK_SEED_RETAINED','schema':schema,'apply_dir':str(apply),
        'apply_execution_sha256':sha(apply/'execution.json'),'reload_dir':str(reload),'reload_execution_sha256':sha(reload/'execution.json'),
        'mapped_sha256':sha(apply/'mapped.v'),'ddc_sha256':sha(apply/'mapped.ddc'),
        'seed_svfs':[{ 'source_name':name,'retained_name':'seed-svf/'+name,'sha256':sha(apply/name)} for name in svfs],
        'seed_plan_sha256':ap[key],'ancestor_seed_identity':ap.get('seed_identity')}
    return apply/'mapped.v',apply/'mapped.ddc',inputs,identity


def verify_plan(package):
    plan=json.loads(gzip.decompress((package/'electrical-targets.json.gz').read_bytes()))
    validate_plan(plan)
    return plan


def prior_inputs(root,expected,package_hash,base_hash,plan_hash,seed_identity):
    r=clean_receipt(root,SCHEMA,expected,base_hash)
    require(r.get('package_sha256')==package_hash and r.get('electrical_plan_sha256')==plan_hash and
        r.get('seed_identity')==seed_identity,'prior electrical stage has different package/plan/seed lineage')
    names={'topology':['electrical-metrics.tsv','original-clock-association.tsv','buffer-functions.tsv'],
           'probe':['changes.dctcl','electrical-metrics.tsv','electrical-group-ledger.tsv','original-clock-association.tsv','buffer-functions.tsv'],
           'split':['changes.dctcl','changes.ptsh','electrical-metrics.tsv','electrical-group-ledger.tsv','inserted-electrical-metrics.tsv','original-clock-association.tsv','buffer-functions.tsv','cell-delta.tsv','net-delta.tsv'],
           'apply':['mapped.v','mapped.ddc','mapped.sdc','eco.svf','original-clock-association.tsv']}[expected]
    if expected=='apply':names += sorted(n for n in r['outputs'] if n.startswith('seed-svf/') and n.endswith('.svf'))
    names+=['electrical-reset-review.tsv'] if expected!='apply'else[]
    inputs=bind_outputs(r,root,names)+[verify(root/'execution.json',sha(root/'execution.json'))]
    if expected in {'topology','probe','split'}:
        rows=list(csv.DictReader((root/'electrical-metrics.tsv').read_text().splitlines(),delimiter='\t'))
        before=[x for x in rows if x['phase']=='before'];after=[x for x in rows if x['phase']=='after']
        require(len(before)==68 and {x['net_id']for x in before}=={'e%03d'%i for i in range(68)},'prior native topology does not cover all68 exact root IDs')
        reset=list(csv.DictReader((root/'electrical-reset-review.tsv').read_text().splitlines(),delimiter='\t'))
        require(len(reset)==17 and len({x['net_id']for x in reset})==17 and all(x['status']=='UNRESOLVED_ASYNCHRONOUS_RESET_REVIEW_REQUIRED' and x['mutation_authorized']=='0'for x in reset),
            'prior native reset roots must remain17 visible unresolved and unauthorized')
        if expected!='topology':
            require(len(after)==68 and {x['net_id']for x in after}=={x['net_id']for x in before},'prior native after metrics omit electrical/reset roots')
        if expected=='probe':
            b=next(x for x in before if x['net_id']=='e000');a=next(x for x in after if x['net_id']=='e000')
            require(int(b['flattened_sink_count'])==213 and int(a['flattened_sink_count'])==210 and
                float(a['native_max_capacitance'])<float(b['native_max_capacitance']) and
                float(a['native_max_transition_ns'])<=float(b['native_max_transition_ns']),
                'native U2548 4-load probe cut/capacitance/slew gate did not pass')
    return r,inputs


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
    p.add_argument('--max-buffers',type=int,default=198)
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
    require({'run_electrical_stage.py','pt_electrical_edit.tcl','prepare_electrical.py','electrical-targets.json.gz'}<=set(entries),'electrical runner/tools/plan not sealed; use prepare_electrical.py')
    base=a.baseline.resolve();ptroot=a.baseline_pt_dir.resolve()
    more,base_receipt,chain=baseline(base,ptroot);inputs+=more
    require([(x['role'],x['sha256'])for x in chain['libraries']]==[
        ('standard_cell','f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723'),
        ('sram','c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f')],
        'electrical chain must retain exact original standard-cell and SRAM DB hashes')
    require(sha(base/'mapped.v')==MAPPED_SHA,'electrical plan is not original1064 fixed map')
    base_hash=sha(base/'execution.json');mapped,ddc,more,seed=seed_inputs(a,base,base_hash,chain);inputs+=more
    plan=verify_plan(package);plan_hash=sha(package/'electrical-targets.json.gz')
    for selection in ['topology','probe','split','reload']:emit(plan,selection)
    require(a.max_buffers>=198 or a.stage in {'topology','probe'},'buffer budget does not cover all198 explicit nonreset groups')
    if a.stage!='topology':
        require(a.prior is not None,'prior native electrical stage is mandatory')
        expected={'probe':'topology','split':'probe','apply':'split','reload':'apply'}[a.stage]
        prior_root=a.prior.resolve();prior,more=prior_inputs(prior_root,expected,sha(seal),base_hash,plan_hash,seed);inputs+=more
    else:require(a.prior is None,'topology starts from explicitly bound original baseline/seed')
    if a.stage=='reload':mapped=prior_root/'mapped.v';ddc=prior_root/'mapped.ddc'
    record=dict(schema=SCHEMA,stage=a.stage,status='SEALED_INPUTS_REVIEWED_NOT_EXECUTED',mode='electrical',
        package_sha256=sha(seal),electrical_plan_sha256=plan_hash,baseline_execution_sha256=base_hash,
        baseline_mapped_sha256=sha(base/'mapped.v'),baseline_pt_execution_sha256=sha(ptroot/'execution.json'),
        baseline_pt_dir=str(ptroot),seed_identity=seed,source_mapped_sha256=sha(mapped),source_ddc_sha256=sha(ddc),
        prior_execution_sha256=sha(a.prior.resolve()/'execution.json')if a.prior else None,
        top=TOP,hardware_profile=PROFILE,max_cores=8,user_authorized_cap=8,max_buffers=a.max_buffers,
        max_added_area_raw=a.max_added_area,electrical_groups=1 if a.stage=='probe'else 198 if a.stage in {'split','apply','reload'}else 0,
        asynchronous_reset_nets_visible_unresolved=17,asynchronous_reset_edits_authorized=False,
        generated_electrical_tcl_sha256=__import__('hashlib').sha256(emit(plan,a.stage if a.stage!='apply'else'split')).hexdigest(),
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
    planfile=out/'electrical-plan.tcl';planfile.write_bytes(payload);inputs.append(verify(planfile,sha(planfile)))
    config=['set ::eco_baseline '+tcl(base),'set ::eco_mapped '+tcl(mapped),'set ::eco_mapped_sha '+tcl(sha(mapped)),
        'set ::eco_ddc '+tcl(ddc),'set ::eco_mode {electrical}',
        'set ::eco_electrical_action '+tcl(a.stage if a.stage!='apply'else'split'),
        'set ::eco_electrical_plan_file '+tcl(planfile),'set ::eco_electrical_plan_sha '+tcl(sha(planfile)),
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
    if a.stage!='apply':
        if a.prior:config+=['set ::eco_reference_clocks '+tcl(prior_root/'original-clock-association.tsv')]
        elif seed:config+=['set ::eco_reference_clocks '+tcl(Path(seed['reload_dir'])/'original-clock-association.tsv')]
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
    if a.stage in {'topology','probe','split'}:
        required=['electrical-metrics.tsv','electrical-reset-review.tsv','original-clock-association.tsv','buffer-functions.tsv','leaf-pin-directions.tsv','reference-metadata.tsv','before-coverage.rpt','before-all_violators.rpt']
        if a.stage!='topology':required+=['changes.dctcl','changes.ptsh','changes.text','cell-delta.tsv','net-delta.tsv','electrical-group-ledger.tsv','inserted-electrical-metrics.tsv','after-coverage.rpt','after-all_violators.rpt']
    elif a.stage=='apply':required=['mapped.v','mapped.ddc','mapped.sdc','eco.svf','area-upper-bound.tsv','original-clock-association.tsv']+([x['retained_name']for x in seed['seed_svfs']]if seed else[])
    else:required=['electrical-metrics.tsv','electrical-reset-review.tsv','inserted-electrical-metrics.tsv','persisted-coverage.rpt','persisted-all_violators.rpt','persisted-setup.rpt','persisted-hold.rpt','persisted-removal.rpt','persisted-gating_hold.rpt','persisted-min_pulse_width.rpt','original-clock-association.tsv','buffer-functions.tsv','leaf-pin-directions.tsv','reference-metadata.tsv']
    required+=['required-reports.list','host-options.rpt']
    if(out/'required-reports.list').is_file():required+=(out/'required-reports.list').read_text().splitlines()
    missing=[x for x in required if x not in outputs or(outputs[x]['bytes']==0 and x!='required-reports.list')]
    complete=(out/marker).is_file();ok=code==0 and complete and not timeout and not drift and not errors and not missing
    record.update(status='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE'if ok else'NATIVE_STAGE_FAILED',returncode=code,tool_timed_out=timeout,finished_epoch=time.time(),completion_marker=complete,source_drift=drift,native_tool_errors=errors,missing_outputs=missing,outputs=outputs)
    dump(receipt,record)
    if ok and a.stage in {'topology','probe','split','reload'}:
        dump(out/'function-proof.json',dict(schema='xu-native-buffer-function-proof-v1',native_execution=dict(path='execution.json',sha256=sha(receipt)),report=dict(path='buffer-functions.tsv',sha256=sha(out/'buffer-functions.tsv')),direction_report=dict(path='leaf-pin-directions.tsv',sha256=sha(out/'leaf-pin-directions.tsv')),reference_metadata=dict(path='reference-metadata.tsv',sha256=sha(out/'reference-metadata.tsv'))))
    print(json.dumps({k:record[k]for k in ['stage','status','returncode','completion_marker','source_drift','native_tool_errors','missing_outputs']},sort_keys=True));return 0 if ok else 1


if __name__=='__main__':
    try:sys.exit(main())
    except(OSError,ValueError,KeyError)as error:print('FAIL: '+str(error),file=sys.stderr);sys.exit(1)
