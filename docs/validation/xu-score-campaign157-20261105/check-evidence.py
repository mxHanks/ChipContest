#!/usr/bin/env python3
"""Independent157 deployment/migration/enrollment/running-snapshot audit; no EDA."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

HERE=Path(__file__).resolve().parent
B='/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/'
D='/storage2/2026contest/server4/s4_23usr/Desktop/xu-campaign-batch154/'
C='unified-experiment-control-20261105-150/'
P134='s2e-own-timing-repair-20261105-134/'
P155='s2e-own-timing-repair-20261105-155/'
OLD={'s2e_power130','eight_freeze138','s2e_timing134','baseline_rdc142'}
RELEASE_SHA='29a3a238ca27182b814035203a2e5cae3f651066f599bf859596546c4f752590'
RELEASE_TAR_SHA='8de2a0f7181cd7e52b1ac92ada842cbd8d8003e75fbd68c2ed93d967118c6003'


def need(ok,message):
    if not ok:raise ValueError(message)


def ident(raw):return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def file_ident(path):return ident(Path(path).read_bytes())


def package(path,digest,size,count=None,total=None):
    need(file_ident(path)==dict(bytes=size,sha256=digest),'original package differs: '+str(path))
    payload={};manifest=None
    with tarfile.open(str(path),'r:xz') as tar:
        for member in tar:
            p=PurePosixPath(member.name)
            need(member.isfile() and not p.is_absolute() and '..' not in p.parts and member.name not in payload and
                 'private-manuals' not in p.parts and 'private-docs' not in p.parts,'unsafe/duplicate/private member')
            raw=tar.extractfile(member).read();need(len(raw)==member.size,'truncated tar member')
            payload[member.name]=raw
            if member.name=='manifest.json':manifest=json.loads(raw)
    if manifest is not None:
        payload.pop('manifest.json')
        need(len(manifest)==len(payload) and {r['path'] for r in manifest}==set(payload),'original manifest inventory differs')
        for r in manifest:need(ident(payload[r['path']])=={k:r[k] for k in ('bytes','sha256')},'original payload differs: '+r['path'])
    if count is not None:need(len(payload)==count,'original payload count differs')
    if total is not None:need(sum(len(raw) for raw in payload.values())==total,'original payload bytes differ')
    return payload


def one_name(payload,prefix,pattern):
    found=[n for n in payload if n.startswith(prefix) and re.fullmatch(pattern,n[len(prefix):])]
    need(len(found)==1,'one original receipt required: '+prefix+pattern)
    return found[0]


def audit(p,release,history):
    js=lambda name:json.loads(p[name])
    checked=set()
    def receipt(row):
        path=row['path']
        need(path.startswith(B),'unexpected server output receipt scope')
        relative=path[len(B):]
        need(relative in p and ident(p[relative])=={k:row[k] for k in ('bytes','sha256')},'server/local original receipt differs: '+relative)
        checked.add(relative)
    manifest=json.loads(release['release154.json'])
    need(ident(release['release154.json'])['sha256']==RELEASE_SHA and p['desktop/release154.json']==release['release154.json'],
         'installed/returned original release154 manifest differs')
    need(manifest['schema']=='xu-campaign-release154-v1' and manifest['qualification']=='NOT_QUALIFIED' and
         manifest['job_count']==20 and manifest['native_cap']==1 and len(manifest['files'])==86,'release scope differs')
    names=set()
    for row in manifest['files']:
        path=PurePosixPath(row['path']);need(not path.is_absolute() and '..' not in path.parts and row['path'] not in names,'unsafe release file')
        names.add(row['path']);need(ident(release[row['path']])=={k:row[k] for k in ('bytes','sha256')},'release body differs')
    need(set(release)==names|{'release154.json'},'release154 complete file set differs')
    install=js('desktop/xu-campaign-batch154-install.json')
    need(install==dict(archive_sha256=RELEASE_TAR_SHA,files=86,jobs=20,manifest_sha256=RELEASE_SHA,
        status='INSTALLED_FROZEN_RELEASE154_NOT_STARTED_NOT_QUALIFIED',target=D[:-1]),'server installation receipt differs')
    state=js(C+'state.json')
    migrate_name=one_name(p,C,r'migration153-[^/]+\.json');migration=js(migrate_name)
    qname=one_name(p,'campaign-enrollment-20261105-154/',r'quiesce150-[^/]+\.json');quiesce=js(qname)
    ename=one_name(p,'campaign-enrollment-20261105-154/',r'enroll-[^/]+\.json');enrollment=js(ename)
    snapshot_prefix=migration['snapshot'][len(B):]+'/'
    snapshot=js(snapshot_prefix+'SNAPSHOT153.json');before=js(snapshot_prefix+'state.json')
    need(migration['snapshot'].startswith(B+C.rstrip('/')+'.before153-') and
         migration['status']=='MIGRATED_SAME_OUT_CONTROLLER153_RUNNING_NOT_QUALIFIED' and
         migration['workers_signalled']==migration['workers_restarted']==0 and migration['qualification']=='NOT_QUALIFIED',
         'exact migration/zero worker touch receipt differs')
    need(quiesce['status']=='ORIGINAL_CONTROLLER_STOPPED_EXPERIMENTS_UNTOUCHED' and quiesce['workers_signalled']==0 and
         quiesce['qualification']=='NOT_QUALIFIED','quiesce must only stop original controller')
    oldid=quiesce['old_controller_identity']
    need(oldid['pid']==159584 and oldid['start_ticks']==117325331 and oldid['uid']==14023 and
         oldid['argv']==['/bin/python3','-B','/storage2/2026contest/server4/s4_23usr/Desktop/xu-experiment-control150/xu_experiments.py',
                         'run','--out',B+C.rstrip('/')],'exact quiesced original process identity differs')
    need(migration['old_state_identity']==quiesce['controller_state'] and
         ident(p[snapshot_prefix+'state.json'])=={k:migration['old_state_identity'][k] for k in ('bytes','sha256')},
         'quiesce/migration/full-snapshot original state differs')
    receipt(migration['snapshot_manifest'])
    need(snapshot['status']=='FULL_CONTROLLER_TREE_SNAPSHOT_VERIFIED' and snapshot['source']==B+C.rstrip('/') and
         len(snapshot['files'])==13,'pre-migration full snapshot inventory differs')
    missing=[]
    for row in snapshot['files']:
        relative=row['relative'];name=snapshot_prefix+relative
        if name in p:
            need(ident(p[name])=={k:row[k] for k in ('bytes','sha256')},'snapshot body differs: '+relative)
        else:
            need(relative in ('controller.lock','register.lock') and row['bytes']==0 and
                 row['sha256']==hashlib.sha256(b'').hexdigest(),'unexpected missing snapshot body')
            missing.append(relative)
    need(sorted(missing)==['controller.lock','register.lock'],'only two empty locks may be absent from returned snapshot')
    legacy=json.loads(history[C+'state.json'])
    need(set(before['jobs'])==OLD and before['jobs']==legacy['jobs'],'pre-migration four original jobs changed since151')
    need(all(state['jobs'][name]==before['jobs'][name] for name in OLD),'migration/resumed controller changed original four job records')
    original_runs=[]
    for row in snapshot['files']:
        if not row['relative'].startswith(('runs/','registrations/')):continue
        name=row['relative'];need(p[snapshot_prefix+name]==p[C+name]==history[C+name],'original registration/run bytes changed: '+name)
        original_runs.append(name)
    need(len(original_runs)==6,'four old registrations/two old launcher logs required')
    proof=migration['original_controller_stop_proof']
    need(proof['confirmed_original_controller_stopped'] is True and proof['matching_live_controllers']==[] and
         proof['recorded_pid_current_identity'] is None and proof['recorded_original_controller_pid']==159584 and
         proof['original_worker']==before['worker'],'original controller exit/rebind proof differs')
    need(proof['original_worker']['sha256']=='d7813ac3745ff1aa5b5efc92eef298a6577abef774259f9285aae605c466db2f',
         'original controller150 bytes differ')
    worker=migration['new_worker']
    need(worker['path']==D+'control153/xu_experiments.py' and worker==state['worker']==enrollment['controller'] and
         worker['sha256']==manifest['controller_sha256'] and
         ident(release['control153/xu_experiments.py'])=={k:worker[k] for k in ('bytes','sha256')},'same deployed153 worker differs')
    need(ident(release['control153/bundle-manifest153.json'])=={k:migration['bundle_manifest'][k] for k in ('bytes','sha256')},
         '153 runtime bundle manifest differs')
    live=js('live157-observation.json');observations={r['name']:r for r in live['observations']}
    controller=observations['controller153']['actual'];running155=observations['s2e_timing155']['actual']
    need(controller==migration['confirmed_controller_identity']==state['controller_identity'] and
         controller['pid']==migration['spawn_pid']==228660 and controller['start_ticks']==118030075 and
         controller['argv']==migration['argv'],'actual157 /proc controller identity differs from confirmed migration')
    need(all(observations[name]['actual'] is None for name in ('s2e_power130','s2e_timing134','baseline_rdc142')),
         'old original worker unexpectedly still live in157 observation')
    need(enrollment['status']=='REGISTERED_ATOMIC_BATCH_NOT_QUALIFIED' and enrollment['qualification']=='NOT_QUALIFIED' and
         enrollment['job_count']==len(enrollment['jobs'])==20,'actual complete20 enrollment receipt required')
    jobs={name[len('jobs/'):-5]:json.loads(raw) for name,raw in release.items() if name.startswith('jobs/') and name.endswith('.json')}
    need(set(jobs)==set(enrollment['jobs']) and set(state['jobs'])==set(jobs)|OLD,'actual24-node queue differs from release/original jobs')
    reported_inputs=0
    for name,job in jobs.items():
        raw=release['jobs/'+name+'.json'];actual=p[C+'registrations/'+name+'.json'];row=enrollment['jobs'][name]
        need(raw==actual and ident(raw)['sha256']==row['registration_sha256'] and row['already_registered'] is False and
             row['frozen_input_count']==len(job['frozen_inputs']),'actual enrollment bytes/input count differs: '+name)
        receipt(state['jobs'][name]['registration']);reported_inputs+=row['frozen_input_count']
    alljobs={name:js(C+'registrations/'+name+'.json') for name in state['jobs']}
    visited=set();visiting=set()
    def visit(name):
        need(name in alljobs and name not in visiting,'missing dependency or cycle: '+name)
        if name in visited:return
        visiting.add(name)
        for dep in alljobs[name]['dependencies']:visit(dep['id'])
        visiting.remove(name);visited.add(name)
    for name in alljobs:visit(name)
    for key in ('result_state','process_contains'):
        need(len({j[key] for j in alljobs.values()})==24,'queue identity collision: '+key)
    for name in jobs:
        expected='RUNNING' if name=='s2e_timing155' else 'WAIT_DEPENDENCY'
        need(state['jobs'][name]['status']==expected,'157 current new queue status differs: '+name)
    events=[json.loads(line) for line in p[C+'events.jsonl'].decode().splitlines()]
    previous=[json.loads(line) for line in p[snapshot_prefix+'events.jsonl'].decode().splitlines()]
    need(events[:len(previous)]==previous,'migration changed append-only event history')
    new_events=events[len(previous):]
    need({e.get('job') for e in new_events if e['event']=='QUEUED'}==set(jobs),'complete20 QUEUED events absent')
    need([(e['event'],e.get('job')) for e in new_events if e['event'] in ('START_INTENT','SPAWNED')]==
         [('START_INTENT','s2e_timing155'),('SPAWNED','s2e_timing155')],'original worker restart or unexpected new dispatch occurred')

    timing=js(P155+'state.json');failed=json.loads(history[P134+'state.json'])
    need(timing['status']=='RUNNING_NOT_QUALIFIED' and timing['phase']=='final/fm' and timing['pid']==228701 and
         timing['qualification']=='NOT_QUALIFIED' and len(timing['runs'])==7 and
         'frozen_after' not in timing and 'finished_epoch' not in timing,
         '155 must remain explicitly running with terminal integrity checks pending')
    resume=timing['resume155']
    need(resume['csv_field_limit']==67108864 and resume['original_terminal']['sha256']==ident(history[P134+'state.json'])['sha256'] and
         resume['adopted_phases']==[['original-inventory','dc'],['original-inventory','pt'],['hold-gating','dc'],
                                   ['posthold-inventory','dc'],['posthold-inventory','pt']],
         '155 exact original failure/phase adoption differs')
    native=[]
    for index,run in enumerate(timing['runs']):
        receipt(run['log']);receipt(run['script'])
        log=p[run['log']['path'][len(B):]].decode()
        need(run['returncode']==0 and run['marker_count']==1 and not run['errors'] and
             not re.search(r'^\s*(?:Error:|Error-\[|Fatal:|XU_FATAL:)',log,re.M),'155 completed native receipt/log failed')
        marker=('XU_S2E_TIMING134_PT_DONE_NOT_QUALIFIED' if run['tool']=='pt' else
                'XU_S2E_TIMING134_HOLD_DONE_NOT_QUALIFIED' if index==2 else
                'XU_S2E_TIMING134_INVENTORY_DONE_NOT_QUALIFIED' if index<5 else
                'XU_S2E_TIMING134_REPAIR_DONE_NOT_QUALIFIED')
        need(sum(line.strip()==marker for line in log.splitlines())==1,'155 unique completed native marker absent')
        if index<5:
            original=failed['runs'][index]
            need(run['execution_provenance']=='ADOPTED_ORIGINAL134_NATIVE_PHASE_NOT_RERUN' and
                 run['original_native_run']==original and
                 p[run['log']['path'][len(B):]]==history[original['log']['path'][len(B):]],'155 adoption rewrote original native run/log')
            original_script=history[original['script']['path'][len(B):]]
            expected=original_script.replace((B+P134.rstrip('/')).encode(),(B+P155.rstrip('/')).encode())
            need(p[run['script']['path'][len(B):]]==expected,'155 adopted script changed beyond output path relocation')
        else:need('execution_provenance' not in run and Path(run['directory']).name=='final','155 final DC/PT must be fresh native runs')
        native.append(dict(index=index,tool=run['tool'],scope='ADOPTED_ORIGINAL134' if index<5 else 'NEW_FINAL155',returncode=0,
            marker_count=1,log_sha256=run['log']['sha256'],script_sha256=run['script']['sha256']))
    need(running155==state['jobs']['s2e_timing155']['worker_identity'] and
         running155==js(C+'runs/s2e_timing155/spawn.json')['worker_identity'] and running155['pid']==228701 and
         running155['start_ticks']==118031670 and running155['argv']==jobs['s2e_timing155']['argv'],
         'actual157 /proc155 worker identity differs from original spawn')
    receipt(state['jobs']['s2e_timing155']['result_state_snapshot'])
    need(state['jobs']['s2e_timing155']['worker_identity_alive'] is True and state['jobs']['s2e_timing155']['live_processes']==[running155],
         'controller must retain one actual live155 worker')
    fm=p[P155+'final/fm.log'].decode()
    need('Formality (R)' in fm and 'Elaborating design' in fm and
         not any(line.strip() in ('Verification SUCCEEDED','XU_S2E_TIMING134_FORMALITY_PASS') for line in fm.splitlines()),
         '157 FM log must remain a partial elaboration snapshot, not proof completion')
    need(all(run['tool']!='fm' for run in timing['runs']),'157 has no completed FM execution receipt')
    verify=p[P155+'final/verify.tcl'].decode()
    need('XU_S2E_TIMING134_FORMALITY_PASS' in verify and all(r['path'] in verify for r in timing['svf_chain']) and
         timing['svf_chain'][0]['sha256']=='1a00803ebb654285dad15c76978fe1da50dd9732860f6af82a9a2d9117e668a9' and
         timing['svf_chain'][1]['sha256']=='1c47a3c93d0730408d8a7fc30483e1508e349ead3cb1e71dedfa3a78067ce7ee',
         '155 own89/original134-hold/final155 FM input chain differs')
    omitted=live['omitted_large_text'];old_omitted=json.loads(history['live151-observation.json'])['omitted_large_text']
    need(len(omitted)==len(old_omitted)==2,'exactly two large native cell bodies omitted')
    for now,old in zip(omitted,old_omitted):
        need(now['path']==old['path'].replace(B+P134,B+P155) and
             all(now[k]==old[k] for k in ('bytes','sha256')) and now['path'][len(B):] not in p,
             '155 omitted native cell identity differs from adopted134')
    return dict(schema='xu-campaign157-independent-audit-v1',qualification='NOT_QUALIFIED',
        original_payload_files=167,original_payload_bytes=40767862,release_files=86,release_manifest_sha256=RELEASE_SHA,
        release_archive_sha256=RELEASE_TAR_SHA,locally_matched_server_output_receipts=len(checked),
        migration=dict(status=migration['status'],old_controller=oldid,confirmed_current_controller=controller,
            workers_signalled=0,workers_restarted=0,original_four_job_dicts_unchanged=True,
            original_registration_and_run_bodies_unchanged=original_runs,full_snapshot_inventory_entries=13,
            locally_returned_snapshot_bodies=11,unreturned_zero_byte_lock_files=sorted(missing)),
        enrollment=dict(status=enrollment['status'],new_jobs=20,all_registration_bytes_equal_original_release=True,
            server_reported_verified_frozen_input_count=reported_inputs,combined_queue_nodes=24,dependency_graph='ACYCLIC_COMPLETE',
            current_status_counts=dict(Counter(r['status'] for r in state['jobs'].values())),
            status_by_job={n:r['status'] for n,r in state['jobs'].items()}),
        timing155=dict(status=timing['status'],phase=timing['phase'],live_worker=running155,completed_runs=native,
            adopted_original_phases=5,new_completed_native_phases=2,full_fm='RUNNING_SNAPSHOT_COMPLETION_NOT_PROVEN',
            terminal_input_recheck='PENDING',final_mapped_receipt=list(timing['final_outputs'].values())[0],
            omitted_large_text=omitted),
        observation_epoch=live['epoch'],limitations=[
            'This is the immutable157 historical snapshot, not a current process-liveness assertion.',
            'Enrollment byte counts and successful input checks are original server receipts; external library/source bodies are not all returned.',
            'Two approximately99MB native-cells.tsv bodies and mapped/SVF bodies are absent; their hashes are receipts only.',
            'Five155 phases are explicit134 adoptions, not new native executions. Only final DC/PT completed in157.',
            'Full FM, terminal before/after rehash, complete150MHz qualification, measured energy eligibility and contest scoring remain unproven.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-results',action='store_true');args=parser.parse_args()
    if not args.write_results:
        manifest=json.loads((HERE/'input-manifest.json').read_text())
        for name,row in manifest['files'].items():need(file_ident(HERE/name)==row,'local delivery differs: '+name)
    p=package(HERE/'xu-server-autonomous-campaign-20261105-157.tar.xz',
        '37a340dc1d24f0d6b7eecc0194a492fee6077953818dea141b25021e4f30fe18',591260,167,40767862)
    release=package(HERE/'xu-campaign-batch154.tar.xz',RELEASE_TAR_SHA,201028)
    history=package(HERE.parent/'xu-score-terminal151-20261105/xu-server-control-terminal-20261105-151.tar.xz',
        '84ad6475f61d14f68f51c52a4f2ecac4ae26aa43fe4c48227e579b435c1235ff',672360,191,50892386)
    result=audit(p,release,history);raw=(json.dumps(result,sort_keys=True,indent=2)+'\n').encode();path=HERE/'analysis157.json'
    if args.write_results:
        need(not path.exists(),'fresh independent analysis required');path.write_bytes(raw)
    else:need(path.read_bytes()==raw,'saved independent157 analysis differs')
    print(json.dumps(dict(status='ACTUAL157_INSTALL_MIGRATION_ENROLLMENT_AND_RUNNING155_SNAPSHOT_VERIFIED',
        qualification='NOT_QUALIFIED',new_jobs=20,total_queue_nodes=24,adopted134_phases=5,new_native155_completed_phases=2,
        full_fm='COMPLETION_NOT_PROVEN'),sort_keys=True))


if __name__=='__main__':main()
