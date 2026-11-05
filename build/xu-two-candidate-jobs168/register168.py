#!/usr/bin/env python3
"""Enroll the reviewed own-S2e164 audit into the existing two-candidate queue."""
import hashlib
import importlib.util
from pathlib import Path
import time

D=Path.home()/'Desktop'
B=D/'xu-score-optimization-20261102'
C=B/'unified-experiment-control-20261105-150'
WORKER=D/'xu-campaign-batch154/control153/xu_experiments.py'
JOB=D/'s2e_streamaudit164-job.json'
WORKER_SHA='877a1624d45bdae7dd5095809f69e3e9c95eafafac17f354fe52f9781c9ef025'
JOB_SHA='c8047426b615ed131af6d7538b2b3bf3f714c492825b8a95e23a4c3c85e4c451'
assert hashlib.sha256(WORKER.read_bytes()).hexdigest()==WORKER_SHA
assert hashlib.sha256(JOB.read_bytes()).hexdigest()==JOB_SHA
spec=importlib.util.spec_from_file_location('xu168_frozen153',str(WORKER))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
state=m.read(C/'state.json')
assert state['worker']==m.identity(WORKER)
assert m.same_process(state['controller_identity'],m.process_identity(state['controller_pid'])),'observe/restore the original controller, never init'
policies=sorted(B.glob('unified-experiment-control-20261105-150.scope-two163-*/receipt.json'))
assert policies,'explicit two-candidate scope receipt missing'
policy=m.read(policies[-1])
assert policy['status']=='DEFERRED_ORIGINAL_WORKERS_PRESERVED_CONTROLLER_RESUMED_NOT_QUALIFIED'
assert policy['preserved_profiles']==['s2e','s2c'] and policy['workers_signalled']==policy['workers_restarted']==0
job=m.validate_job(m.read(JOB))
assert job['id']=='s2e_streamaudit164' and job['process_contains']==job['output_root']
assert job['dependencies']==[dict(id='s2e_power130',policy='success')]
before=m.check_records(job['frozen_inputs'])
registered=C/'registrations/s2e_streamaudit164.json'
assert registered.exists() or not Path(job['output_root']).exists(),'existing audit must be inspected instead of repeated'
m.register(C,JOB)
assert registered.read_bytes()==JOB.read_bytes()
after=m.check_records(job['frozen_inputs']);assert before==after
receipt=B/'s2e-streamaudit164-registration-20261105-168.json'
if not receipt.exists():
    m.save(receipt,dict(schema='xu-two-candidate-registration168-v1',status='REGISTERED_OWN_S2E_AUDIT_NOT_QUALIFIED',
        qualification='NOT_QUALIFIED',job=m.identity(JOB),registration=m.identity(registered),
        controller_identity=state['controller_identity'],scope_receipt=m.identity(policies[-1]),
        frozen_before=before,frozen_after=after,epoch=time.time(),workers_restarted=0))
print('XU168_REGISTERED_OWN_S2E164',str(receipt),flush=True)
