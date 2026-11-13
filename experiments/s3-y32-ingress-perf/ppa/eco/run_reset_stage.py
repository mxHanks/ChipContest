#!/usr/bin/env python3
"""Read-only native reset diagnostics on the original or completed integrated seed.

Only --stage diagnose exists. No mutation/apply/reload option is provided, and
collection completion never authorizes reset edits. Unknown per-receiver checks,
pulse/no_clock and physical reset contracts remain explicit.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
sys.dont_write_bytecode=True
from run_stage import baseline,bind_outputs,dump,heavy_jobs,require,sha,tcl,verify,TOP,PROFILE
from prepare_reset import emit,validate
SCHEMA='ingress1064-n3-reset-diagnostic-stage-v1'
MAPPED_SHA='882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e'

def clean_receipt(root,schema,stage,base_hash):
    r=json.loads((root/'execution.json').read_text())
    require(r.get('schema')==schema and r.get('stage')==stage and r.get('returncode')==0 and
        r.get('status')=='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE' and
        r.get('completion_marker') is True and r.get('tool_timed_out') is False and r.get('source_drift')==[] and
        r.get('native_tool_errors')==[] and r.get('missing_outputs')==[] and
        r.get('baseline_execution_sha256')==base_hash,'prior/seed native stage is incomplete or has a different original baseline')
    require(stage in {'apply','reload'},'reset seed must be an applied map or fresh reload')
    marker='DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt' if stage=='apply' else ('PRUNE_RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt' if schema=='ingress1064-n3-dead-cone-stage-v1' else 'RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt')
    bind_outputs(r,root,[marker])
    return r


def read_table(path,columns):
    lines=path.read_text().splitlines()
    rows=[line.replace(r'\t','\t').split('\t')for line in lines]
    require(rows and rows[0]==columns,'invalid native ledger header: '+str(path))
    require(all(len(row)==len(columns)for row in rows[1:]),'invalid native ledger row width: '+str(path))
    return [dict(zip(columns,row))for row in rows[1:]]


def clock_table(path):
    rows=read_table(path,['pin','clocks']);result={}
    for row in rows:
        pin=row['pin'];require(pin and pin not in result,'missing/duplicate native clock pin: '+str(path))
        result[pin]=row['clocks']
    return result


def prune_clock_partition(apply,reload,ap,rp):
    """Bind original clocks to exact retained+proven-deleted partition.

    Prune apply still carries its incoming clock table. Fresh PT emits the
    retained current table plus a removal ledger, explaining all36 dead states.
    Equality of the two original-clock-association files is therefore invalid.
    """
    bindings=bind_outputs(ap,apply,['deleted-leaves.tsv'])
    bindings+=bind_outputs(rp,reload,['retained-clock-association.tsv','removed-clock-association.tsv'])
    deleted={};states=set()
    for row in read_table(apply/'deleted-leaves.tsv',['wave','instance','reference','is_sequential']):
        name=row['instance'];ref=row['reference'];sequential=row['is_sequential']
        require(name and name not in deleted and not ref.startswith('RAMSP') and sequential in {'true','false'},'invalid/duplicate/SRAM prune deletion ledger')
        require(row['wave'].isdigit(),'invalid native prune deletion wave')
        deleted[name]=ref
        if sequential=='true':states.add(name)
    require(len(deleted)==1796 and len(states)==36,'prune clock partition needs exact1796 deleted leaves and36 deleted state parents')
    original=clock_table(apply/'original-clock-association.tsv')
    retained=clock_table(reload/'retained-clock-association.tsv')
    current=clock_table(reload/'original-clock-association.tsv')
    removed={};parents=set()
    for row in read_table(reload/'removed-clock-association.tsv',['pin','clocks','proven_deleted_parent']):
        pin=row['pin'];parent=row['proven_deleted_parent']
        require(pin and pin not in removed and '/'in pin and pin.rsplit('/',1)[0]==parent and parent in states,
            'removed clock pin lacks its exact proven deleted state parent')
        require(pin in original and original[pin]==row['clocks'],'removed clock association differs from incoming prune seed')
        removed[pin]=row['clocks'];parents.add(parent)
    require(parents==states,'removed clock parents do not exactly cover all36 proven deleted state leaves')
    require(not(set(retained)&set(removed)) and set(retained)|set(removed)==set(original),
        'incoming prune clock pins are not exactly partitioned into retained and removed')
    require(all(original[pin]==clocks for pin,clocks in retained.items()),'retained prune clock association changed')
    require(current==retained,'fresh prune actual clock table differs from retained partition')
    identity=dict(mode='EXACT_PRUNE_RETAINED_AND_PROVEN_DELETED_CLOCK_PARTITION',original_clock_pins=len(original),
        retained_clock_pins=len(retained),removed_clock_pins=len(removed),proven_deleted_state_parents=len(parents),
        incoming_clock_sha256=sha(apply/'original-clock-association.tsv'),current_reload_clock_sha256=sha(reload/'original-clock-association.tsv'),
        retained_clock_sha256=sha(reload/'retained-clock-association.tsv'),removed_clock_sha256=sha(reload/'removed-clock-association.tsv'),
        deleted_leaves_sha256=sha(apply/'deleted-leaves.tsv'))
    return bindings,identity


def seed_inputs(a,base,base_hash,chain):
    if not a.seed_apply and not a.seed_reload:
        return base/'mapped.v',base/'mapped.ddc',[],None
    require(a.seed_apply and a.seed_reload,'seed requires BOTH completed apply and successful fresh PT reload')
    apply=a.seed_apply.resolve();reload=a.seed_reload.resolve()
    schema=json.loads((apply/'execution.json').read_text()).get('schema')
    require(schema in {'ingress1064-n3-bounded-eco-stage-v1','ingress1064-n3-clock-eco-stage-v1','ingress1064-n3-electrical-eco-stage-v1','ingress1064-n3-dead-cone-stage-v1'},'seed must be completed hold/clock/electrical/prune apply plus fresh reload')
    ap=clean_receipt(apply,schema,'apply',base_hash);rp=clean_receipt(reload,schema,'reload',base_hash)
    key={'ingress1064-n3-bounded-eco-stage-v1':'target_plan_sha256','ingress1064-n3-clock-eco-stage-v1':'clock_plan_sha256','ingress1064-n3-electrical-eco-stage-v1':'electrical_plan_sha256','ingress1064-n3-dead-cone-stage-v1':'prune_plan_sha256'}[schema]
    require(ap.get(key) and ap.get(key)==rp.get(key) and ap.get('package_sha256')==rp.get('package_sha256') and
        rp.get('prior_execution_sha256')==sha(apply/'execution.json') and
        ap.get('libraries')==rp.get('libraries')==chain['libraries'] and
        ap.get('seed_identity')==rp.get('seed_identity'),'seed reload not bound to supplied applied DDC/library/lineage')
    if schema in {'ingress1064-n3-clock-eco-stage-v1','ingress1064-n3-electrical-eco-stage-v1'}:
        require(rp.get('source_mapped_sha256')==sha(apply/'mapped.v'),'seed reload source map differs')
    else:
        require(all(any(Path(x['path']).name==name and x.get('sha256')==sha(apply/name) and x.get('bytes')==(apply/name).stat().st_size for x in rp.get('inputs',[])) for name in ['mapped.v','mapped.ddc']),
            'seed fresh reload does not bind applied mapped V/DDC input bytes')
    svfs=sorted(name for name in ap.get('outputs',{}) if name.endswith('.svf'))
    require('eco.svf' in svfs,'seed lacks native ECO SVF')
    inputs=bind_outputs(ap,apply,['mapped.v','mapped.ddc','mapped.sdc','original-clock-association.tsv']+svfs)
    inputs+=bind_outputs(rp,reload,['persisted-coverage.rpt','persisted-all_violators.rpt','original-clock-association.tsv','buffer-functions.tsv','leaf-pin-directions.tsv','reference-metadata.tsv'])
    if schema=='ingress1064-n3-dead-cone-stage-v1':
        extra,clock_lineage=prune_clock_partition(apply,reload,ap,rp);inputs+=extra
    else:
        require(clock_table(apply/'original-clock-association.tsv')==clock_table(reload/'original-clock-association.tsv'),
            'seed clock association drift after persistence')
        clock_lineage=dict(mode='UNCHANGED_COMPLETE_SEED_CLOCK_ASSOCIATION',current_reload_clock_sha256=sha(reload/'original-clock-association.tsv'))
    inputs += [verify(apply/'execution.json',sha(apply/'execution.json')),verify(reload/'execution.json',sha(reload/'execution.json'))]
    identity={'mode':'EXPLICIT_COMPLETED_INTEGRATED_SEED_RETAINED_READ_ONLY','schema':schema,'apply_dir':str(apply),
        'apply_execution_sha256':sha(apply/'execution.json'),'reload_dir':str(reload),'reload_execution_sha256':sha(reload/'execution.json'),
        'mapped_sha256':sha(apply/'mapped.v'),'ddc_sha256':sha(apply/'mapped.ddc'),
        'seed_svfs':[{ 'source_name':name,'retained_name':'seed-svf/'+name,'sha256':sha(apply/name)} for name in svfs],
        'seed_plan_sha256':ap[key],'ancestor_seed_identity':ap.get('seed_identity'),'seed_clock_lineage':clock_lineage}
    return apply/'mapped.v',apply/'mapped.ddc',inputs,identity


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
    p.add_argument('--stage',choices=['diagnose'],default='diagnose')
    p.add_argument('--baseline',type=Path,required=True);p.add_argument('--baseline-pt-dir',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--seed-apply',type=Path);p.add_argument('--seed-reload',type=Path)
    mode=p.add_mutually_exclusive_group();mode.add_argument('--run',action='store_true');mode.add_argument('--dry-run',dest='run',action='store_false');p.set_defaults(run=False)
    p.add_argument('--timeout-seconds',type=int,default=3600);p.add_argument('--max-receivers',type=int,default=1477)
    p.add_argument('--max-paths-per-query',type=int,default=8192);p.add_argument('--required-margin',type=float,default=0.03)
    p.add_argument('--allow-coordinated-busy-jobs',action='store_true');p.add_argument('--coordination-note')
    a=p.parse_args()
    require(0<a.timeout_seconds<=3600 and 1477<=a.max_receivers<=2000 and 64<=a.max_paths_per_query<=8192 and 0<a.required_margin<=0.5,'bounded reset diagnostic limits exceeded')
    package=Path(__file__).resolve().parent;seal=package/'package-files.json';entries=json.loads(seal.read_text());inputs=[]
    for name,digest in entries.items():
        q=Path(name);require(not q.is_absolute()and'..'not in q.parts,'unsafe sealed reset path');inputs.append(verify(package/q,digest))
    require({'run_reset_stage.py','prepare_reset.py','pt_reset_diagnose.tcl','reset-diagnostic-plan.json.gz'}<=set(entries),'first seal reset diagnostics with prepare_reset.py')
    base=a.baseline.resolve();ptroot=a.baseline_pt_dir.resolve();more,receipt,chain=baseline(base,ptroot);inputs+=more
    require(sha(base/'mapped.v')==MAPPED_SHA,'reset origin map must be exact original1064')
    require([(x['role'],x['sha256'])for x in chain['libraries']]==[
        ('standard_cell','f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723'),
        ('sram','c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f')],'original reset diagnostic libraries changed')
    base_hash=sha(base/'execution.json');mapped,ddc,more,seed=seed_inputs(a,base,base_hash,chain);inputs+=more
    planpath=package/'reset-diagnostic-plan.json.gz';plan=json.loads(gzip.decompress(planpath.read_bytes()));validate(plan);payload=emit(plan)
    record=dict(schema=SCHEMA,stage='diagnose',mode='reset_read_only',status='SEALED_INPUTS_REVIEWED_NOT_EXECUTED',
        package_sha256=sha(seal),reset_plan_sha256=sha(planpath),generated_tcl_sha256=hashlib.sha256(payload).hexdigest(),
        baseline_execution_sha256=base_hash,baseline_mapped_sha256=MAPPED_SHA,baseline_pt_execution_sha256=sha(ptroot/'execution.json'),
        seed_identity=seed,source_mapped_sha256=sha(mapped),source_ddc_sha256=sha(ddc),
        top=TOP,hardware_profile=PROFILE,max_cores=8,user_authorized_cap=8,max_receivers=a.max_receivers,
        max_paths_per_query=a.max_paths_per_query,required_margin_ns=a.required_margin,reset_roots=17,electrical_sinks_original=1478,
        actual_async_receivers_static=1477,unauthorized_static_groups=128,mutation_authorized=False,
        run_requested=a.run,qualification='NOT_QUALIFIED',timing_verdict='NOT_TIMING_CLOSURE',
        diagnostic_only_reason='Current per-receiver known max/min, nonregression, release-cycle/pulse/RDC evidence must precede a separate reset edit tool. No mutation or replay is implemented.')
    if not a.run:print(json.dumps(record,sort_keys=True));return 0
    jobs=heavy_jobs()
    if jobs or a.allow_coordinated_busy_jobs:require(a.allow_coordinated_busy_jobs and a.coordination_note and len(a.coordination_note.strip())>=16,'explicit busy-job coordination note required')
    allowed=sorted(os.sched_getaffinity(0));require(len(allowed)>=10,'cap8 reserves at least2 allowed CPUs');os.sched_setaffinity(0,allowed[:8])
    role='pt';identity=verify(chain[role]['path'],chain[role]['sha256'],external=True)
    libraries=[verify(x['path'],x['sha256'],external=True)for x in chain['libraries']]
    out=a.out.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False)
    planfile=out/'reset-plan.tcl';planfile.write_bytes(payload);inputs.append(verify(planfile,sha(planfile)))
    config=['set ::eco_baseline '+tcl(base),'set ::eco_mapped '+tcl(mapped),'set ::eco_mapped_sha '+tcl(sha(mapped)),
        'set ::eco_ddc '+tcl(ddc),'set ::eco_mode {reset_diagnostic_read_only}',
        'set ::reset_plan_file '+tcl(planfile),'set ::reset_plan_sha '+tcl(sha(planfile)),
        'set ::reset_max_receivers '+str(a.max_receivers),'set ::reset_max_paths_per_query '+str(a.max_paths_per_query),
        'set ::reset_required_margin '+repr(a.required_margin),'set ::eco_selected_targets {}','set ::eco_read_only_clock_roots {}',
        'set ::eco_buffer_reference {BUFV2_12TR40}','set ::eco_max_buffers 0','set ::eco_max_added_area 0.0',
        'set ::eco_link_libraries [list * '+' '.join(tcl(x['path'])for x in chain['libraries'])+']',
        'set ::eco_library_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256'])for x in chain['libraries'])+']',
        'set ::eco_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256'])for x in inputs)+']']
    if seed:config+=['set ::reset_reference_clocks '+tcl(Path(seed['reload_dir'])/'original-clock-association.tsv')]
    configuration=out/'config.tcl';configuration.write_text('\n'.join(config)+'\n')
    env=os.environ.copy();env.update(XU_ECO_PACKAGE=str(package),XU_ECO_CONFIG=str(configuration),XU_ECO_HOST_TOOL='pt')
    lc=chain['library_compiler'];verify(Path(lc['root'])/'bin/lc_shell',lc['launcher_sha256'],external=True);env['SYNOPSYS_LC_ROOT']=lc['root']
    proofroot=out/'native-library-proof';proofroot.mkdir(mode=0o700);proofenv=env.copy();proofenv['XU_ECO_HOST_TOOL']='dc'
    dc=verify(chain['dc']['path'],chain['dc']['sha256'],external=True);proofcmd=[chain['dc']['path'],'-f',str(package/'dc_library_proof.tcl')]
    proof=dict(tool=dc,libraries=chain['libraries'],command=proofcmd,max_cores=8,config_sha256=sha(configuration),started_epoch=time.time())
    record.update(status='RUNNING_NATIVE_DC_FUNCTION_QUERY',native_dc_function=proof,linux_affinity=allowed[:8],observed_jobs=jobs,coordination_note=a.coordination_note)
    execution=out/'execution.json'
    code,timeout=wait_process(proofcmd,proofroot,proofenv,min(a.timeout_seconds,300),record,execution,proofroot/'native.log')
    errors=re.findall(r'^(?:Error:|Fatal:).*$',(proofroot/'native.log').read_text(errors='replace'),re.M)
    complete=(proofroot/'DC_LIBRARY_FUNCTION_PROOF_COMPLETE.txt').is_file()
    proof_files={q.relative_to(proofroot).as_posix():dict(sha256=sha(q),bytes=q.stat().st_size)for q in sorted(proofroot.rglob('*'))if q.is_file()}
    drift=[x['path']for x in inputs+libraries+[dc]if not Path(x['path']).is_file()or sha(x['path'])!=x['sha256']]
    proof.update(returncode=code,tool_timed_out=timeout,completion_marker=complete,native_tool_errors=errors,source_drift=drift,outputs=proof_files,finished_epoch=time.time())
    if code or timeout or errors or drift or not complete or not {'dc-library-proof.tsv','host-options.rpt'}<=set(proof_files):
        record.update(status='NATIVE_DIAGNOSTIC_STAGE_FAILED',returncode=code,completion_marker=False,native_tool_errors=errors,source_drift=drift,missing_outputs=[],failure_stage='native_dc_identity_function_proof');dump(execution,record);return 1
    function=proofroot/'dc-library-proof.tsv';inputs.append(verify(function,sha(function)))
    configuration.write_text(configuration.read_text()+'set ::eco_dc_function_file '+tcl(function)+'\nset ::eco_dc_function_sha '+tcl(sha(function))+'\n')
    cmd=[chain['pt']['path'],'-f',str(package/'pt_reset_diagnose.tcl')]
    record.update(status='RUNNING_NATIVE_READ_ONLY_DIAGNOSIS',command=cmd,tool=identity,libraries=chain['libraries'],inputs=inputs,config_sha256=sha(configuration),started_epoch=time.time())
    code,timeout=wait_process(cmd,out,env,a.timeout_seconds,record,execution,out/'native.log')
    errors=re.findall(r'^(?:Error:|Fatal:).*$',(out/'native.log').read_text(errors='replace'),re.M)
    drift=[x['path']for x in inputs+libraries+[identity]if not Path(x['path']).is_file()or sha(x['path'])!=x['sha256']]
    if sha(configuration)!=record['config_sha256']:drift.append(str(configuration))
    outputs={q.relative_to(out).as_posix():dict(sha256=sha(q),bytes=q.stat().st_size)for q in sorted(out.rglob('*'))if q.is_file()and q.name!='execution.json'}
    required=['reset-root-metrics.tsv','reset-native-electrical-members.tsv','reset-receiver-summary.tsv','reset-receiver-metrics.tsv','reset-query-attempts.tsv','reset-native-paths.tsv','reset-release-context-spread.tsv','reset-diagnostic-coverage.rpt','reset-diagnostic-all_violators.rpt','reset-diagnostic-recovery.rpt','reset-diagnostic-removal.rpt','reset-diagnostic-min_pulse_width.rpt','original-clock-association.tsv','cell-delta.tsv','net-delta.tsv','buffer-functions.tsv','leaf-pin-directions.tsv','reference-metadata.tsv','required-reports.list','host-options.rpt','RESET_EDITS_NOT_AUTHORIZED.txt']
    if(out/'required-reports.list').is_file():required+=(out/'required-reports.list').read_text().splitlines()
    missing=[n for n in required if n not in outputs or outputs[n]['bytes']==0]
    complete=(out/'RESET_DIAGNOSTIC_COLLECTION_COMPLETE_NOT_AUTHORIZED.txt').is_file();ok=code==0 and not timeout and complete and not errors and not drift and not missing
    record.update(status='NATIVE_DIAGNOSTIC_COLLECTION_COMPLETE_NOT_AUTHORIZED'if ok else'NATIVE_DIAGNOSTIC_STAGE_FAILED',returncode=code,tool_timed_out=timeout,completion_marker=complete,native_tool_errors=errors,source_drift=drift,missing_outputs=missing,outputs=outputs,finished_epoch=time.time())
    dump(execution,record)
    print(json.dumps({k:record[k]for k in ['status','returncode','completion_marker','mutation_authorized','source_drift','native_tool_errors','missing_outputs']},sort_keys=True));return 0 if ok else 1

if __name__=='__main__':
    try:sys.exit(main())
    except(OSError,ValueError,KeyError)as error:print('FAIL: '+str(error),file=sys.stderr);sys.exit(1)
