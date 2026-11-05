#!/usr/bin/env python3
"""Append the reviewed own9c16 query to the live original153 queue; never launch it."""
import hashlib
import importlib.util
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent
D=Path.home()/'Desktop'
B=D/'xu-score-optimization-20261102'
C=B/'unified-experiment-control-20261105-150'
WORKER=D/'xu-campaign-batch154/control153/xu_experiments.py'
WORKER_SHA='877a1624d45bdae7dd5095809f69e3e9c95eafafac17f354fe52f9781c9ef025'
JOB=HERE/'s2c_readonly177.json'
JOB_SHA='a86e46ab86453c48e8dbf57df4ef40c3401e824448c4bb8ec0510457869bba8d'


def main():
    assert WORKER.is_file() and not WORKER.is_symlink()
    assert hashlib.sha256(WORKER.read_bytes()).hexdigest()==WORKER_SHA
    spec=importlib.util.spec_from_file_location('xu182_frozen153',str(WORKER))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    assert m.sha(JOB)==JOB_SHA
    state=m.read(C/'state.json');actual=m.process_identity(state['controller_pid'])
    assert state['worker']==m.identity(WORKER) and m.same_process(state['controller_identity'],actual)
    scopes=sorted(B.glob('unified-experiment-control-20261105-150.scope-two163-*/receipt.json'))
    assert scopes
    scope=m.identity(scopes[-1]);v=m.read(scope['path'])
    assert v['status']=='DEFERRED_ORIGINAL_WORKERS_PRESERVED_CONTROLLER_RESUMED_NOT_QUALIFIED'
    assert v['preserved_profiles']==['s2e','s2c'] and v['workers_signalled']==v['workers_restarted']==0
    previous=m.identity(B/'two-candidate-autopack-registration-20261105-173.json')
    v=m.read(previous['path'])
    assert v['status']=='REGISTERED_AUTOPACK173_NOT_QUALIFIED' and v['qualification']=='NOT_QUALIFIED'
    assert v['workers_signalled']==v['workers_restarted']==v['experiments_directly_launched']==0
    oldreg=C/'registrations/two_candidate_autopack173.json'
    assert m.identity(oldreg)==v['registration']
    assert m.sha(oldreg)=='a79b39149053169415020e4d17446e321e7dd21c63c23e379cb9805714c8d598'
    job=m.validate_job(m.read(JOB))
    assert job['id']=='s2c_readonly177' and job['native'] is True
    assert job['dependencies']==[dict(id='two_candidate_autopack173',policy='terminal'),dict(id='s2c_unknown167',policy='success')]
    assert job['kind']=='launch' and job['launch_mode']=='direct'
    assert job['process_contains']==job['output_root'] and job['argv'][-2:]==['--out',job['output_root']]
    assert job['argv'][:3]==['/bin/python3','-B','-u']
    assert job['argv'][3]==str(D/'xu-s2c-readonly177/readonly177.py')
    before=m.check_records(job['frozen_inputs'])
    target=C/'registrations'/JOB.name
    assert (target.is_file() and target.read_bytes()==JOB.read_bytes()) or (not target.exists() and not Path(job['output_root']).exists() and not Path(job['output_root']).is_symlink())
    m.register(C,JOB)
    assert target.read_bytes()==JOB.read_bytes()
    after=m.check_records(job['frozen_inputs']);assert after==before
    assert m.identity(scope['path'])==scope and m.identity(previous['path'])==previous and m.identity(oldreg)==v['registration']
    latest=m.read(C/'state.json')
    assert m.same_process(actual,m.process_identity(latest['controller_pid']))
    receipt=B/'s2c-readonly177-registration-20261105-182.json'
    if not receipt.exists():
        m.save(receipt,dict(schema='xu-s2c-readonly177-registration182-v1',
            status='REGISTERED_OWN_S2C_READONLY177_NOT_QUALIFIED',qualification='NOT_QUALIFIED',
            job=m.identity(JOB),registration=m.identity(target),register=m.identity(Path(__file__).resolve()),
            controller_identity=actual,scope163=scope,registration173=previous,
            frozen_before=before,frozen_after=after,epoch=time.time(),
            workers_signalled=0,workers_restarted=0,experiments_directly_launched=0))
    else:
        v=m.read(receipt)
        assert v['registration']==m.identity(target) and v['frozen_before']==v['frozen_after']==before
    print('XU182_REGISTERED_OWN_S2C177',str(receipt),flush=True)
    print('XU182_CONTROLLER',latest['controller_pid'],'LIVE_VERIFIED',flush=True)


if __name__=='__main__':main()
