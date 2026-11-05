#!/usr/bin/env python3
"""Append reviewed ownS2e/S2c jobs to original153. No direct EDA launch."""
import hashlib
import importlib.util
import json
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent
D=Path.home()/'Desktop';B=D/'xu-score-optimization-20261102'
C=B/'unified-experiment-control-20261105-150'
WORKER=D/'xu-campaign-batch154/control153/xu_experiments.py'
WORKER_SHA='877a1624d45bdae7dd5095809f69e3e9c95eafafac17f354fe52f9781c9ef025'
IDS=['native_query207','two_candidate_finalpack209']
DEPS=[[('two_candidate_finalpack191','terminal')],[('native_query207','terminal')]]


def need(value,message):
    if not value:raise ValueError(message)


def merged(records):
    unique={}
    for row in records:
        clean={k:row[k]for k in ('path','sha256','bytes')if k in row}
        old=unique.get(clean['path'])
        if old is not None:
            need(old['sha256']==clean['sha256'] and
                 ('bytes' not in old or 'bytes' not in clean or old['bytes']==clean['bytes']),
                 'conflicting frozen guard/runtime identity')
            old.update(clean)
        else:unique[clean['path']]=clean
    return [unique[p]for p in sorted(unique)]


def validate_jobs(m,guard):
    need(guard['schema']=='xu-two-candidate-control208-v1' and len(guard['jobs'])==2,'exact two-job frozen guard required')
    jobs=[];inputs=[]
    for i,row in enumerate(guard['jobs']):
        p=HERE/row['name']
        need(p.name==row['name'] and m.identity(p)==dict(path=str(p),bytes=row['bytes'],sha256=row['sha256']), 'frozen208 job bytes differ')
        job=m.validate_job(m.read(p))
        need(job['id']==IDS[i] and job['kind']=='launch' and job['launch_mode']=='direct' and job['native'] is True,'only fixed two-candidate native jobs supported')
        need(job['dependencies']==[dict(id=d,policy=k)for d,k in DEPS[i]],'exact reviewed dependency chain required')
        need(job['argv'][:3]==['/bin/python3','-B','-u'] and job['argv'][-2:]==['--out',job['output_root']], 'foreground exact argv required')
        need(job['process_contains']==job['output_root'] and Path(job['output_root']).parent==B,'unique original-campaign output required')
        need(Path(job['result_state']).parent==Path(job['output_root']),'own result state required')
        inputs.extend(job['frozen_inputs'])
        old=C/'registrations'/(job['id']+'.json')
        need((old.is_file() and old.read_bytes()==p.read_bytes()) or
             (not old.exists() and not Path(job['output_root']).exists() and not Path(job['output_root']).is_symlink()),
             'changed registration or unadopted existing output')
        jobs.append((p,job))
    need(len({j['output_root']for p,j in jobs})==2,'two unique output roots required')
    return jobs,merged(inputs)


def main():
    need(WORKER.is_file() and not WORKER.is_symlink(),'original153 runtime required')
    need(hashlib.sha256(WORKER.read_bytes()).hexdigest()==WORKER_SHA,'controller runtime identity differs')
    spec=importlib.util.spec_from_file_location('xu208_frozen153',str(WORKER))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    state=m.read(C/'state.json');actual=m.process_identity(state['controller_pid'])
    need(state['worker']==m.identity(WORKER) and m.same_process(state['controller_identity'],actual),'original153 must be alive; never start a second controller')
    scopes=sorted(B.glob('unified-experiment-control-20261105-150.scope-two163-*/receipt.json'))
    need(scopes,'original two-candidate scope receipt missing')
    scope=m.identity(scopes[-1]);v=m.read(scope['path'])
    need(v['status']=='DEFERRED_ORIGINAL_WORKERS_PRESERVED_CONTROLLER_RESUMED_NOT_QUALIFIED' and
         v['preserved_profiles']==['s2e','s2c'] and v['workers_signalled']==v['workers_restarted']==0,'original scope163 differs')
    previous=m.identity(B/'s2c-readonly177-registration-20261105-182.json');v=m.read(previous['path'])
    need(v['status']=='REGISTERED_OWN_S2C_READONLY177_NOT_QUALIFIED' and v['qualification']=='NOT_QUALIFIED' and
         v['workers_signalled']==v['workers_restarted']==v['experiments_directly_launched']==0,'actual182 registration missing')
    oldreg=C/'registrations/s2c_readonly177.json'
    need(m.identity(oldreg)==v['registration'] and m.sha(oldreg)=='a86e46ab86453c48e8dbf57df4ef40c3401e824448c4bb8ec0510457869bba8d','own177 registration changed')
    guard_path=HERE/'frozen-jobs208.json';guard_identity=m.identity(guard_path)
    guard=m.read(guard_path)
    need(guard['ancestry198']['path']==str(B/'two-candidate-followup-registration-20261105-198.json'),'exact original198 ancestry required')
    ancestor=m.read(guard['ancestry198']['path'])
    need(ancestor['status']=='REGISTERED_TWO_CANDIDATE_FOLLOWUP198_NOT_QUALIFIED' and len(ancestor['registrations'])==4,'actual198 must have registered the prior chain')
    terminal191=C/'registrations/two_candidate_finalpack191.json'
    need(m.sha(terminal191)=='a4d97e89daadf68947331575350ffd2d8b9bbf2117f14ba650506f821b35312b','frozen preceding191 registration required')
    jobs,records=validate_jobs(m,guard)
    job_identities=[dict(path=str(HERE/r['name']),bytes=r['bytes'],sha256=r['sha256'])for r in guard['jobs']]
    need(all(m.identity(p)==job_identities[i]for i,(p,j) in enumerate(jobs)),'job changed after guard validation')
    records += job_identities+[m.identity(WORKER),m.identity(Path(__file__).resolve()),
        guard_identity,scope,previous,m.identity(oldreg),guard['ancestry198']]
    records=merged(records)
    before=m.check_records(records)
    registrations=[]
    for index,(p,job) in enumerate(jobs):
        need(m.same_process(actual,m.process_identity(state['controller_pid'])),'original controller exited before registration')
        expected=job_identities[index]
        need(m.identity(p)==expected,'frozen job changed before registration')
        m.register(C,p)
        target=C/'registrations'/(job['id']+'.json')
        actual_job=m.identity(target)
        need(m.identity(p)==expected and all(actual_job[k]==expected[k]for k in ('bytes','sha256')),
             'registered bytes must match original frozen guard; preserve and inspect if registration changed')
        registrations.append(m.identity(target))
    after=m.check_records(records);need(before==after,'frozen job inputs changed during registration')
    need(m.identity(guard_path)==guard_identity and m.identity(scope['path'])==scope and m.identity(previous['path'])==previous,'registration guard/ancestry changed')
    latest=m.read(C/'state.json');need(m.same_process(actual,m.process_identity(latest['controller_pid'])),'same153 controller must remain live')
    receipt=B/'two-candidate-followup-registration-20261105-208.json'
    if receipt.exists():
        v=m.read(receipt);need(v['registrations']==registrations and v['frozen_before']==v['frozen_after']==before,'existing receipt differs')
    else:
        m.save(receipt,dict(schema='xu-two-candidate-control208-receipt-v1',
            status='REGISTERED_TWO_CANDIDATE_FOLLOWUP208_NOT_QUALIFIED',qualification='NOT_QUALIFIED',
            controller_identity=actual,scope163=scope,registration182=previous,guard=guard_identity,
            register=m.identity(Path(__file__).resolve()),registrations=registrations,
            frozen_before=before,frozen_after=after,epoch=time.time(),
            workers_signalled=0,workers_restarted=0,experiments_directly_launched=0))
    print('XU208_REGISTERED_TWO_CANDIDATE_FOLLOWUP',str(receipt),flush=True)
    print('XU208_CONTROLLER',latest['controller_pid'],'LIVE_VERIFIED',flush=True)


if __name__=='__main__':main()
