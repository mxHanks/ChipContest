#!/usr/bin/env python3
"""Freeze the reviewed S2c167 and same155 S2e166 jobs for existing controller153."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
D = Path('/storage2/2026contest/server4/s4_23usr/Desktop')
B = D / 'xu-score-optimization-20261102'


def record(local, remote):
    raw = local.read_bytes()
    return dict(path=str(remote), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def save(name, value):
    (HERE / name).write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def main():
    power = ROOT / 'build/xu-s2e-final-power166'
    observe = ROOT / 'build/xu-s2c-unknown167'
    private = ROOT / 'build/xu-mapped-private147'
    power_manifest = json.loads((power / 'manifest166.json').read_text())
    observe_manifest = json.loads((observe / 'manifest167.json').read_text())
    for item in power_manifest['files']:
        actual = record(power / item['path'], Path(item['path']))
        assert actual == item, ('166 manifest mismatch', item['path'])
    for item in observe_manifest['runtime_files']:
        actual = record(observe / item['name'], Path(item['name']))
        assert actual['sha256'] == item['sha256'] and actual['bytes'] == item['bytes']
    frozen166 = [record(power / n, D / 'xu-s2e-final-power166' / n)
                 for n in power_manifest['runtime_files'] + ['manifest166.json']]
    frozen167 = [record(observe / n, D / 'xu-s2c-unknown167' / n)
                 for n in ['unknown167.py', 'observer167.c.in', 'manifest167.json']]
    for name, digest in observe_manifest['original147_files'].items():
        r = record(private / name, D / 'xu-campaign-batch154/private147' / name)
        assert r['sha256'] == digest, ('original147 mismatch', name)
        frozen167.append(r)

    def job(name, argv, out, result, success, failure, deps, inputs):
        return dict(schema='xu-experiment-control150-job-v1', qualification='NOT_QUALIFIED',
            id=name, kind='launch', launch_mode='direct', native=True,
            argv=['/bin/python3', '-B', '-u'] + [str(v) for v in argv],
            output_root=str(out), process_contains=str(out), result_state=str(out / result),
            success_statuses=success, failure_statuses=[failure], frozen_inputs=inputs,
            dependencies=[dict(id=i, policy=p) for i, p in deps])

    out167 = B / 's2c-passive-unknown-20261105-167'
    first = job('s2c_unknown167', [D / 'xu-s2c-unknown167/unknown167.py',
        '--adapter147', D / 'xu-campaign-batch154/private147', '--out', out167, '--run'],
        out167, 'state.json', observe_manifest['diagnostic_terminal_statuses'],
        observe_manifest['failure_status'], [('s2e_streamaudit164', 'terminal')], frozen167)
    out0 = B / 's2e-final155-power-preflight-20261105-166'
    out12 = B / 's2e-final155-power12-20261105-166'
    common = [D / 'xu-s2e-final-power166/power166.py', 'campaign',
        '--activity', B / 's2e-formal-activity12-20261105-120/result.json',
        '--source-root', B / 'ChipContest-s2e-74',
        '--tool-root', B / 'ChipContest-s2e-activity-tools-109',
        '--ppa-root', B / 's2e-ppa-campaign-20261104-89',
        '--formality-root', B / 's2e-own-formality-audit-20261104-109',
        '--target-root', B / 's2e-own-timing-repair-20261105-155']
    def wrapped(name, args, out):
        filename = name + '-command.json'
        save(filename, dict(schema='xu-frozen-inprocess-command170-v1', qualification='NOT_QUALIFIED',
            entry=frozen166[0], argv=[str(v) for v in args], out=str(out)))
        extra = [record(HERE / 'run170.py', D / 'xu-two-candidate-batch170/run170.py'),
                 record(HERE / filename, D / 'xu-two-candidate-batch170' / filename)]
        return [D / 'xu-two-candidate-batch170/run170.py', '--command',
                D / 'xu-two-candidate-batch170' / filename, '--out', out], frozen166 + extra

    pre_argv, pre_inputs = wrapped('s2e_final155_preflight166', common + ['--task-ids', '0', '--out', out0], out0)
    preflight = job('s2e_final155_preflight166', pre_argv,
        out0, 'result.json', [power_manifest['task0_success']], power_manifest['failure'],
        [('s2c_unknown167', 'terminal'), ('s2e_timing155', 'success')], pre_inputs)
    full_argv, full_inputs = wrapped('s2e_final155_power12_166', common + ['--task-ids', 'all',
        '--preflight-root', out0, '--out', out12], out12)
    full = job('s2e_final155_power12_166', full_argv, out12, 'result.json',
        [power_manifest['full12_success']], power_manifest['failure'],
        [('s2e_final155_preflight166', 'success')], full_inputs)
    jobs = [first, preflight, full]
    for j in jobs:
        assert j['process_contains'] in j['argv'] and j['process_contains'] == j['output_root']
        save(j['id'] + '.json', j)
    save('manifest170.json', dict(schema='xu-two-candidate-batch170-v1', qualification='NOT_QUALIFIED',
        profiles=['s2e', 's2c'], native_cap=1, worker_sha256='877a1624d45bdae7dd5095809f69e3e9c95eafafac17f354fe52f9781c9ef025',
        jobs=[record(HERE / (j['id'] + '.json'), D / 'xu-two-candidate-batch170' / (j['id'] + '.json')) for j in jobs],
        registration_order=[j['id'] for j in jobs],
        no_existing_job_restarted=True,
        explanation='S2c passive diagnosis; independent same155 S2e task0 then success-gated full12. All results remain unqualified.'))
    print('XU170_FROZEN_THREE_JOBS', ','.join(j['id'] for j in jobs))


if __name__ == '__main__':
    main()
