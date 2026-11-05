#!/usr/bin/env python3
"""Independent synthetic preflight guard negatives; no EDA or server access."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / 'build/xu-s2c-common-power190'
spec = importlib.util.spec_from_file_location('independent190_for194', str(DIR / 'power190.py'))
api = importlib.util.module_from_spec(spec); spec.loader.exec_module(api)
OLD = ROOT / 'build/xu-score-resume-20261103/next-results-export-69/s2c-full-soc-power12-20261104-57'


def fixture(root):
    taskdir = root / 'task_00'; taskdir.mkdir()
    (taskdir / 'power.rpt').write_text((OLD / 'task_00/power.rpt').read_text())
    (taskdir / 'pt.log').write_text('Version ' + api.base.PT_VERSION + '\nSYNTHETIC194_NOT_EDA\n')
    states = root / 'states.json'; api.write(states, dict(pins=[]))
    context = dict(synthetic194=True)
    task = dict(task_id=0, completion_marker='SYNTHETIC194_NOT_EDA', expected_reports=['power.rpt'],
                measured_sram_pin_states=dict(path=str(states)), measured_summary=dict(synthetic194=True),
                activity_window=dict(duration_ticks=6604373333334))
    m = dict(requested_task_ids=[0], preflight=None, context=context, input_sha256={}, tasks=[task])
    api.write(root / 'prepared.json', m)
    diagnostic = api.diagnostic(taskdir, task)
    entry = dict(status='EXECUTED_DIAGNOSTIC_NOT_QUALIFIED', execution=dict(returncode=0, log=api.identity(taskdir / 'pt.log')),
                 frozen_inputs_sha256=api.canonical({}), reports=api.checked_reports(taskdir, task), diagnostic=diagnostic)
    summary = dict(status=api.TASK0, qualification='NOT_QUALIFIED', task_count=1, tasks=[entry], context=context,
                   sum_diagnostic_energy_j=diagnostic['diagnostic_energy_j'])
    api.write(root / 'summary.json', summary)
    execution = dict(status=api.TASK0, qualification='NOT_QUALIFIED', input_sha256_before={}, input_sha256_after={},
                     prepared=api.identity(root / 'prepared.json'), summary=api.identity(root / 'summary.json'), tasks=[entry])
    result = dict(status=api.TASK0, qualification='NOT_QUALIFIED', summary=api.identity(root / 'summary.json'))
    return context, m, execution, summary, result


def emit(root, m, execution, summary, result):
    api.write(root / 'prepared.json', m)
    execution['prepared'] = api.identity(root / 'prepared.json')
    api.write(root / 'summary.json', summary)
    execution['summary'] = result['summary'] = api.identity(root / 'summary.json')
    api.write(root / 'execution.json', execution); api.write(root / 'result.json', result)


class Independent194(unittest.TestCase):
    def test_checked_preflight_positive_and_eight_negative_guards(self):
        modes = ['valid', 'prepared_only', 'wrong_context', 'changed_log_receipt', 'input_changed',
                 'wrong_frozen_digest', 'wrong_taskset', 'changed_report', 'missing_actual_marker']
        for mode in modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); context, m, e, s, r = fixture(root)
                if mode == 'prepared_only': r['status'] = 'PREPARED_COMMON190_NOT_QUALIFIED'
                if mode == 'wrong_context': s['context'] = dict(wrong=True)
                if mode == 'changed_log_receipt': e['tasks'][0]['execution']['log']['sha256'] = '0' * 64
                if mode == 'input_changed': e['input_sha256_after'] = {'unrelated': '0' * 64}
                if mode == 'wrong_frozen_digest': e['tasks'][0]['frozen_inputs_sha256'] = '0' * 64
                if mode == 'wrong_taskset': m['requested_task_ids'] = list(range(12))
                if mode == 'changed_report': (root / 'task_00/power.rpt').write_text('changed\n')
                if mode == 'missing_actual_marker': (root / 'task_00/pt.log').write_text('Version ' + api.base.PT_VERSION + '\nputs {SYNTHETIC194_NOT_EDA}\n')
                emit(root, m, e, s, r)
                # Isolate post-prepare native-receipt guards. prepared_verify is
                # independently covered by original-data review194 and190 tests.
                # This synthetic fixture is never a native/prepared qualification.
                with patch.object(api, 'prepared_verify'):
                    if mode == 'valid':
                        receipt = api.checked_preflight(root, context, {})
                        self.assertEqual(receipt['status'], api.TASK0)
                    else:
                        with self.assertRaises(ValueError): api.checked_preflight(root, context, {})

    def test_jobs_and_same_pid_commands_cannot_match_other_output(self):
        import sys
        with patch.dict(sys.modules, {'power190': api}):
            sp = importlib.util.spec_from_file_location('jobs_for194', str(DIR / 'jobs190.py'))
            jobs = importlib.util.module_from_spec(sp); sp.loader.exec_module(jobs)
            a, b = jobs.job('preflight190'), jobs.job('full12_190')
        for own, other in [(a, b), (b, a)]:
            self.assertEqual(own['process_contains'], own['output_root'])
            self.assertNotIn(other['output_root'], ' '.join(own['argv']))
            self.assertEqual(own['argv'][3], str(jobs.ROOT / 'run190.py'))
        self.assertEqual(b['dependencies'], [dict(id=a['id'], policy='success')])


if __name__ == '__main__':
    unittest.main(verbosity=2)
