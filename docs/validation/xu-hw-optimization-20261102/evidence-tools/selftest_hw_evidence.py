#!/usr/bin/env python3
"""Exercise evidence semantic rejection without invoking a simulator or runtime tool.

The positive record is the locally generated, frozen-source combined real1 run.
Only Audit.passing_simulation is isolated here; these tests do not claim to cover
the end-to-end server archive, receipt, selection or final acceptance audit.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--local-runs', type=Path,
                        help='unpacked xu-hw-local-screening directory; defaults to the local build fixture')
    args = parser.parse_args()
    repo = args.repo.resolve()
    spec = importlib.util.spec_from_file_location('independent_hw_audit', Path(__file__).with_name('verify_hw_evidence.py'))
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    run = (args.local_runs or repo / 'build/xu-hw-local-97b3542') / 'H1H2-real1'
    original = verifier.read(run / 'result.json')
    source = verifier.read(repo / 'docs/validation/xu-hw-optimization-20261102/evidence-tools/runtime-source-97b3542.json')
    fixture = verifier.read(repo / 'tests/e203/vectors/kwt-silence-v1.json')

    def audit(directory=run.parent):
        value = verifier.Audit.__new__(verifier.Audit)
        environment = {key: original[key] for key in ['main_commit', 'e203_commit', 'source_sha256',
                       'runner_sha256', 'contract_sha256', 'versions', 'simulator_sha256']}
        environment['tool_sha256'] = {key: {'path': path} for key, path in original['tools'].items()}
        value.directory = directory
        value.transferred = {'files': {}}
        value.campaign = {'source': source, 'environment': environment, 'simulator': original['simulator']}
        value.fixture, value.vector_pool, value.extracted = fixture, {}, {}
        value.log_checks, value.artifact_checks, value.simulations = [], [], []
        return value

    checks = []

    def check(name, record, expected=None, instance=None):
        try:
            (instance or audit()).passing_simulation(run.name, record)
        except ValueError as exc:
            if expected is None or expected not in str(exc):
                raise AssertionError('{} rejected unexpectedly: {}'.format(name, exc))
            checks.append(dict(name=name, status='PASS', rejected=True, error=str(exc)))
        else:
            if expected is not None:
                raise AssertionError(name + ' was not rejected')
            checks.append(dict(name=name, status='PASS', rejected=False))

    check('unchanged_complete_local_record', copy.deepcopy(original))
    corruptions = [
        ('output_missing', lambda row: row.update(outputs=row['outputs'] - 1), 'incomplete numerical'),
        ('writeback_missing', lambda row: row.update(write_words=row['write_words'] - 1), 'incomplete numerical'),
        ('duplicate_layer', lambda row: row['layers'].append(copy.deepcopy(row['layers'][0])), 'unordered/duplicate/missing'),
        ('phase_partition_wrong', lambda row: row['layers'][0]['performance'].update(other=row['layers'][0]['performance']['other'] + 1), 'six phases'),
        ('mmio_transaction_wrong', lambda row: row['layers'][0]['performance'].update(mmio_writes=row['layers'][0]['performance']['mmio_writes'] + 1), 'fixed work/transaction'),
        ('mac_fire_wrong', lambda row: row['layers'][0]['performance'].update(mac_fire=row['layers'][0]['performance']['mac_fire'] + 1), 'fixed work/transaction'),
        ('mcycle_smaller_than_window', lambda row: row['layers'][0].update(firmware_cycles=row['layers'][0]['cycles'] - 1), 'firmware mcycle'),
        ('declared_work_wrong', lambda row: row['transaction_contract'].update(shared_reads=1), 'transaction contract'),
        ('compiler_mode_mismatch', lambda row: row['firmware_build']['configuration'].update(schedule='bias-dtcm'), 'compiler optimization'),
        ('vector_identity_mismatch', lambda row: row['vectors'].update({'layer_00/y.mem': '0' * 64}), 'real fixture identity'),
        ('runner_identity_mismatch', lambda row: row.update(runner_sha256='0' * 64), 'runner/contract source'),
        ('firmware_artifact_mismatch', lambda row: row.update(firmware_image_sha256='0' * 64), 'firmware artifact hash'),
    ]
    for name, mutate, expected in corruptions:
        record = copy.deepcopy(original)
        mutate(record)
        check(name, record, expected)
    with tempfile.TemporaryDirectory(prefix='xu-hw-audit-selftest-') as temporary:
        folder = Path(temporary)
        destination = folder / run.name
        destination.mkdir()
        log = (run / 'simulation.log').read_text()
        for name, corrupt_log, expected in [
            ('complete_log_failure_marker', log + '\nFATAL: injected corruption\n', 'failure marker'),
            ('complete_log_duplicate_task_pass', log + next(line for line in log.splitlines() if line.startswith('TASK_PASS ')) + '\n', 'malformed TASK_PASS'),
            ('complete_log_missing_perf_record', '\n'.join(line for line in log.splitlines() if not line.startswith('PERF_TASK ')), 'malformed PERF_TASK'),
            ('complete_log_wrong_completion', log.replace('SOC_PASS tasks=1', 'SOC_PASS tasks=2'), 'incomplete SOC_PASS'),
        ]:
            path = destination / 'simulation.log'
            path.write_text(corrupt_log)
            record = copy.deepcopy(original)
            record['log_sha256']['simulation.log'] = verifier.sha(path)
            check(name, record, expected, audit(folder))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(dict(status='PASS', runtime_modules_imported=False,
        scope='isolated semantic/log verifier tests against one complete local real1 record; not end-to-end server acceptance',
        source_result_sha256=verifier.sha(run / 'result.json'),
        verifier_sha256=verifier.sha(Path(__file__).with_name('verify_hw_evidence.py')),
        positive_controls=1, intentional_corruptions_rejected=len(checks) - 1, checks=checks), indent=2, sort_keys=True) + '\n')
    print('PASS: 1 positive control; {} intentional corruptions rejected'.format(len(checks) - 1))


if __name__ == '__main__':
    main()
