#!/usr/bin/env python3
"""Register173 into the existing frozen153 controller. Never launch/init/signal."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent
D=Path.home()/'Desktop'
B=D/'xu-score-optimization-20261102'
C=B/'unified-experiment-control-20261105-150'
WORKER=D/'xu-campaign-batch154/control153/xu_experiments.py'
WORKER_SHA='877a1624d45bdae7dd5095809f69e3e9c95eafafac17f354fe52f9781c9ef025'
PLAN170_SHA='8a3e6ac5b4cd7ba3cf039d4a00b653825f541b5375911775337a13d472cc7808'
JOB=HERE/'two_candidate_autopack173.json'
JOB_SHA='a79b39149053169415020e4d17446e321e7dd21c63c23e379cb9805714c8d598'
ID='two_candidate_autopack173'


def need(ok,message):
    if not ok:raise ValueError(message)


def live(m):
    state=m.read(C/'state.json');actual=m.process_identity(state['controller_pid'])
    need(state['worker']==m.identity(WORKER)and m.same_process(state['controller_identity'],actual),'original153 controller must be live with same PID/startticks/argv')
    need(actual['uid']==os.getuid()and str(WORKER)in actual['argv']and str(C)in actual['argv'],'actual153 controller argv/scope differs')
    return state,actual


def register():
    need(WORKER.is_file()and not WORKER.is_symlink()and hashlib.sha256(WORKER.read_bytes()).hexdigest()==WORKER_SHA,'frozen153 worker differs')
    spec=importlib.util.spec_from_file_location('xu173_frozen153',str(WORKER));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    need(JOB.is_file()and not JOB.is_symlink()and m.sha(JOB)==JOB_SHA,'frozen173 job differs');job=m.validate_job(m.read(JOB))
    need(job['id']==ID and job['native']is True and job['kind']=='launch'and job['launch_mode']=='direct','173 direct exclusive-slot registration required')
    out=B/'two-candidate-autopack-20261105-173'
    need(job['output_root']==job['process_contains']==str(out)and job['argv'][-2:]==['--out',str(out)],'unique173 process marker/output differs')
    need(job['dependencies']==[dict(id='s2c_unknown167',policy='terminal'),dict(id='s2e_final155_power12_166',policy='terminal'),dict(id='s2e_streamaudit164',policy='success')],'173 exact dependency gates differ')
    state,controller_before=live(m)
    policies=sorted(B.glob('unified-experiment-control-20261105-150.scope-two163-*/receipt.json'));need(policies,'scope163 receipt missing')
    scope=m.identity(policies[-1]);policy=m.read(policies[-1])
    need(policy['status']=='DEFERRED_ORIGINAL_WORKERS_PRESERVED_CONTROLLER_RESUMED_NOT_QUALIFIED'and
         policy['preserved_profiles']==['s2e','s2c']and policy['workers_signalled']==policy['workers_restarted']==0,'original two-candidate scope differs')
    receipt170=m.identity(B/'two-candidate-registration-20261105-170.json');enrolled=m.read(receipt170['path'])
    need(enrolled['status']=='REGISTERED_TWO_CANDIDATE_FOLLOWUPS_NOT_QUALIFIED'and enrolled['qualification']=='NOT_QUALIFIED'and
         enrolled['workers_signalled']==enrolled['workers_restarted']==0,'actual170 registration receipt differs')
    plan=m.identity(D/'xu-two-candidate-batch170/manifest170.json')
    need(plan==enrolled['plan']and plan['sha256']==PLAN170_SHA,'original deployed170 plan changed')
    required=['s2c_unknown167','s2e_final155_preflight166','s2e_final155_power12_166']
    need([row['job']for row in enrolled['jobs']]==required,'original170 three jobs missing/reordered')
    previous=[]
    for row in enrolled['jobs']:
        path=C/'registrations'/(row['job']+'.json');actual=m.identity(path)
        need(actual==row['registration']and row['frozen_before']==row['frozen_after'],'170 immutable registration/receipt differs')
        need(m.check_records(m.read(path)['frozen_inputs'])==row['frozen_after'],'170 deployed runtime changed')
        previous.append(actual)
    need((C/'registrations/s2e_streamaudit164.json').is_file(),'actual164 registration required')
    before=m.check_records(job['frozen_inputs']);registered=C/'registrations'/JOB.name
    archive=B/'xu-server-two-candidate-20261105-171.tar.xz'
    need((registered.is_file()and not registered.is_symlink()and registered.read_bytes()==JOB.read_bytes())or
         (not registered.exists()and not registered.is_symlink()and not out.exists()and not out.is_symlink()and not archive.exists()and not archive.is_symlink()),
         'existing173 output/archive or different registration requires inspection')
    m.register(C,JOB)  # Frozen153 fsync+atomic registration only. No job execution.
    after=m.check_records(job['frozen_inputs']);need(before==after,'173 runtime changed while registering')
    need(previous==[m.identity(C/'registrations'/(name+'.json'))for name in required],'original170 registration changed')
    need(m.identity(scope['path'])==scope and m.identity(receipt170['path'])==receipt170,'scope163/170 source receipt changed')
    _,controller_after=live(m);need(m.same_process(controller_before,controller_after),'controller identity changed while enrolling')
    receipt=B/'two-candidate-autopack-registration-20261105-173.json'
    registration=m.identity(registered)
    if not receipt.exists():
        m.save(receipt,dict(schema='xu-two-candidate-autopack-registration173-v1',status='REGISTERED_AUTOPACK173_NOT_QUALIFIED',qualification='NOT_QUALIFIED',
            job=m.identity(JOB),registration=registration,register=m.identity(Path(__file__).resolve()),frozen_before=before,frozen_after=after,
            controller_identity=controller_after,scope163=scope,registration170=receipt170,original170_registrations=previous,
            epoch=time.time(),workers_signalled=0,workers_restarted=0,experiments_directly_launched=0))
    else:
        old=m.read(receipt);need(old['registration']==registration and old['frozen_before']==old['frozen_after']==before,'existing173 receipt differs')
    print('XU173_REGISTERED_AUTOPACK '+str(receipt),flush=True)
    print('XU173_CONTROLLER '+str(state['controller_pid'])+' LIVE_VERIFIED',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.parse_args();register()


if __name__=='__main__':main()
