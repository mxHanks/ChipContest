#!/usr/bin/env python3
"""Register reviewed jobs into the existing frozen153 controller; never launch directly."""
import hashlib
import importlib.util
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
D = Path.home() / 'Desktop'
B = D / 'xu-score-optimization-20261102'
C = B / 'unified-experiment-control-20261105-150'
WORKER = D / 'xu-campaign-batch154/control153/xu_experiments.py'
WORKER_SHA = '877a1624d45bdae7dd5095809f69e3e9c95eafafac17f354fe52f9781c9ef025'
PLAN_SHA = '8a3e6ac5b4cd7ba3cf039d4a00b653825f541b5375911775337a13d472cc7808'


def main():
    assert hashlib.sha256(WORKER.read_bytes()).hexdigest() == WORKER_SHA
    spec = importlib.util.spec_from_file_location('xu170_frozen153', str(WORKER))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.sha(HERE / 'manifest170.json') == PLAN_SHA
    plan = m.read(HERE / 'manifest170.json')
    assert plan['profiles'] == ['s2e', 's2c'] and plan['native_cap'] == 1
    assert plan['worker_sha256'] == WORKER_SHA and plan['qualification'] == 'NOT_QUALIFIED'
    state = m.read(C / 'state.json')
    assert state['worker'] == m.identity(WORKER)
    assert m.same_process(state['controller_identity'], m.process_identity(state['controller_pid'])), 'inspect original controller; never init'
    policies = sorted(B.glob('unified-experiment-control-20261105-150.scope-two163-*/receipt.json'))
    assert policies
    policy = m.read(policies[-1])
    assert policy['status'] == 'DEFERRED_ORIGINAL_WORKERS_PRESERVED_CONTROLLER_RESUMED_NOT_QUALIFIED'
    assert policy['preserved_profiles'] == ['s2e', 's2c'] and policy['workers_signalled'] == policy['workers_restarted'] == 0
    assert (C / 'registrations/s2e_streamaudit164.json').is_file()
    paths = []
    checked = []
    for row, expected_id in zip(plan['jobs'], plan['registration_order']):
        path = HERE / (expected_id + '.json')
        assert m.identity(path) == row
        job = m.validate_job(m.read(path))
        assert job['id'] == expected_id and job['native'] is True
        assert job['process_contains'] == job['output_root'] and job['output_root'] in job['argv']
        before = m.check_records(job['frozen_inputs'])
        registered = C / 'registrations' / path.name
        assert (registered.is_file() and registered.read_bytes() == path.read_bytes()) or (not registered.exists() and not Path(job['output_root']).exists()), 'existing output/registration requires inspection'
        paths.append(path)
        checked.append(dict(job=expected_id, frozen_before=before))
    assert len(paths) == len(plan['jobs']) == len(plan['registration_order']) == 3
    for path in paths:
        m.register(C, path)
    for path, row in zip(paths, checked):
        row['registration'] = m.identity(C / 'registrations' / path.name)
        row['frozen_after'] = m.check_records(m.read(path)['frozen_inputs'])
        assert row['frozen_before'] == row['frozen_after']
    receipt = B / 'two-candidate-registration-20261105-170.json'
    if not receipt.exists():
        m.save(receipt, dict(schema='xu-two-candidate-registration170-v1',
            status='REGISTERED_TWO_CANDIDATE_FOLLOWUPS_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
            plan=m.identity(HERE / 'manifest170.json'), register=m.identity(Path(__file__).resolve()),
            controller_identity=state['controller_identity'], scope_receipt=m.identity(policies[-1]),
            jobs=checked, epoch=time.time(), workers_signalled=0, workers_restarted=0))
    print('XU170_REGISTERED_THREE_TWO_CANDIDATE_JOBS', str(receipt), flush=True)
    print('XU170_CONTROLLER', state['controller_pid'], 'LIVE_VERIFIED', flush=True)


if __name__ == '__main__':
    main()
