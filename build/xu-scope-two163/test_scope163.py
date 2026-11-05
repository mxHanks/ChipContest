import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('defer163', str(HERE / 'scope163.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Defer163Tests(unittest.TestCase):
    def token(self):
        return dict(pid=123, uid=14023, start_ticks=12, argv=m.controller_argv(m.OUT))

    def setup_rows(self, directory):
        out = Path(directory)
        jobs, rows = {}, {}
        for name in sorted(m.TARGETS):
            target = out / ('worker-' + name)
            jobs[name] = dict(output_root=str(target), result_state=str(target / 'result.json'),
                              process_contains=str(target))
            rows[name] = dict(status='WAIT_DEPENDENCY', registration={'sha256': m.TARGETS[name]})
        for name in ['mapped_private147', 's2e_power130', 's2e_timing155', 's2e_streamaudit156', 'baseline_rdc142', 'unrelated_future_job']:
            rows[name] = dict(status='WAIT_DEPENDENCY', registration={'sha256': name})
        return out, jobs, dict(jobs=rows, schema='original', qualification='NOT_QUALIFIED', worker={'sha256': 'same'})

    def test_exact_sixteen_targets_and_two_preserved_profiles(self):
        self.assertEqual(set(m.PRESERVED_PROFILES), {'s2e', 's2c'})
        self.assertEqual(set(m.TARGETS), {kind + '_' + profile
                         for kind in ['activity145', 'power146']
                         for profile in m.DEFERRED_PROFILES})
        self.assertEqual(len(m.TARGETS), 16)
        self.assertNotIn('mapped_private147', m.TARGETS)
        self.assertNotIn('s2e_power130', m.TARGETS)
        release_path = HERE.parent / 'xu-campaign-batch154' / 'release154.json'
        self.assertEqual(m.sha(release_path), m.RELEASE_SHA)
        release = m.read(release_path)
        files = {item['path']: item for item in release['files']}
        for name, digest in m.TARGETS.items():
            key = 'jobs/' + name + '.json'
            self.assertEqual(files[key]['sha256'], digest)
            self.assertEqual(m.sha(release_path.parent / key), digest)

    def test_all_terminal_and_started_rows_preserved_verbatim(self):
        for status in m.DONE:
            with tempfile.TemporaryDirectory() as temporary:
                out, jobs, state = self.setup_rows(temporary)
                for name in m.TARGETS:
                    state['jobs'][name]['status'] = status
                    state['jobs'][name]['original_evidence'] = {'unchanged': [1, 2]}
                updated, actions = m.defer_rows(state, jobs, out, [], {})
                self.assertEqual(updated, state)
                self.assertTrue(all(not value['row_changed'] for value in actions.values()))
        for key in m.STARTED_KEYS:
            with tempfile.TemporaryDirectory() as temporary:
                out, jobs, state = self.setup_rows(temporary)
                for name in m.TARGETS:
                    state['jobs'][name][key] = None
                updated, _ = m.defer_rows(state, jobs, out, [], {})
                self.assertEqual(updated, state)

    def test_exact_process_accepts_only_complete_identity(self):
        token = self.token()
        self.assertEqual(m.exact_controller(token, copy.deepcopy(token), m.OUT, 14023), token)
        for key, replacement in [('pid', 124), ('uid', 14024), ('start_ticks', 13),
                                 ('argv', token['argv'] + ['--once'])]:
            changed = copy.deepcopy(token); changed[key] = replacement
            with self.assertRaises(ValueError):
                m.exact_controller(token, changed, m.OUT, 14023)
        for invalid in [None, {}, dict(token, argv=['/bin/python3', 'other.py'])]:
            with self.assertRaises(ValueError):
                m.exact_controller(invalid, token, m.OUT, 14023)

    def test_only_sixteen_pending_rows_can_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            out, jobs, state = self.setup_rows(temporary)
            before = copy.deepcopy(state)
            updated, actions = m.defer_rows(state, jobs, out, [], {'path': '/immutable-policy', 'sha256': 'p'})
            self.assertEqual(state, before)
            self.assertEqual({name for name in state['jobs'] if state['jobs'][name] != updated['jobs'][name]}, set(m.TARGETS))
            for name in m.TARGETS:
                self.assertEqual(updated['jobs'][name]['status'], 'ADOPTED_TERMINAL_REVIEW_PENDING')
                self.assertEqual(updated['jobs'][name]['administrative_status'], m.ADMIN)
                self.assertNotIn('reported_status', updated['jobs'][name])
                self.assertTrue(actions[name]['row_changed'])
            self.assertEqual(updated['worker'], state['worker'])

    def test_actual_failed32_live64_only_pending64power_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            out, jobs, state = self.setup_rows(temporary)
            for row in state['jobs'].values():
                row['status'] = 'FAILED_REVIEW_REQUIRED'
            state['jobs']['power146_pe64']['status'] = 'WAIT_DEPENDENCY'
            state['jobs']['activity145_pe32']['status'] = 'FAILED_REVIEW_REQUIRED'
            state['jobs']['power146_pe32']['status'] = 'BLOCKED_DEPENDENCY_NOT_QUALIFIED'
            state['jobs']['activity145_pe64'].update(status='RUNNING', pid=15, worker_identity={'pid': 15}, started_epoch=1)
            updated, actions = m.defer_rows(state, jobs, out, [], {})
            self.assertEqual({name for name in state['jobs'] if state['jobs'][name] != updated['jobs'][name]}, {'power146_pe64'})
            for name in state['jobs']:
                if name != 'power146_pe64':
                    self.assertEqual(updated['jobs'][name], state['jobs'][name])

    def test_start_artifacts_results_or_live_process_prevent_mutation(self):
        for evidence in ['result', 'output', 'run', 'process', 'started', 'live_processes']:
            with tempfile.TemporaryDirectory() as temporary:
                out, jobs, state = self.setup_rows(temporary)
                name = 'power146_pe64'; job = jobs[name]; row = state['jobs'][name]
                processes = []
                if evidence in ['result', 'output']:
                    Path(job['output_root']).mkdir()
                    if evidence == 'result':
                        Path(job['result_state']).write_text('{"status":"ORIGINAL"}\n')
                elif evidence == 'run':
                    (out / 'runs' / name).mkdir(parents=True)
                elif evidence == 'process':
                    processes = [dict(uid=os.getuid(), argv=['python3', job['process_contains']])]
                elif evidence == 'started':
                    row['start_intent'] = True
                elif evidence == 'live_processes':
                    row['live_processes'] = [{'pid': 17}]
                updated, actions = m.defer_rows(state, jobs, out, processes, {})
                self.assertEqual(updated['jobs'][name], row)
                self.assertFalse(actions[name]['row_changed'])
                if evidence == 'result':
                    self.assertEqual(Path(job['result_state']).read_text(), '{"status":"ORIGINAL"}\n')

    def test_snapshot_keeps_complete_original_bytes_and_registrations(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / 'out'; out.mkdir(); (out / 'registrations').mkdir()
            original = b'{"jobs":{},"raw_spacing":  1}\n'
            (out / 'state.json').write_bytes(original)
            (out / 'events.jsonl').write_bytes(b'{"event":"original"}\n')
            (out / 'SUMMARY.md').write_text('original summary\n')
            for name in ['s2e', 's2c', 'preserved_other']:
                (out / 'registrations' / (name + '.json')).write_text('{"id":"' + name + '"}\n')
            destination = Path(temporary) / 'before'
            result = m.snapshot(out, destination, m.read(out / 'state.json'), {n:{} for n in ['s2e', 's2c', 'preserved_other']})
            self.assertEqual((destination / 'state.json').read_bytes(), original)
            self.assertEqual(len(m.read(destination / 'manifest.json')['files']), 6)
            self.assertEqual(result['sha256'], m.sha(destination / 'manifest.json'))
            for source in out.rglob('*'):
                if source.is_file():
                    self.assertEqual(source.read_bytes(), (destination / source.relative_to(out)).read_bytes())

    def test_frozen153_observe_keeps_admin_done_terminal_policy_continues(self):
        spec = importlib.util.spec_from_file_location('xu153_test', str(HERE.parent / 'xu-experiment-control153' / 'xu_experiments.py'))
        control = importlib.util.module_from_spec(spec); spec.loader.exec_module(control)
        self.assertEqual(control.DONE, m.DONE)
        with tempfile.TemporaryDirectory() as temporary:
            out, jobs, state = self.setup_rows(temporary)
            updated, _ = m.defer_rows(state, jobs, out, [], {})
            name = 'power146_pe64'; row = updated['jobs'][name]
            control.observe(dict(jobs[name], kind='launch', launch_mode='direct', success_statuses=['PASS'], failure_statuses=['FAIL']), row, [])
            self.assertIn(row['status'], control.DONE)
            self.assertNotEqual(row['status'], 'COMPLETED_DIAGNOSTIC_NOT_QUALIFIED')
            # Controller153 terminal dependencies proceed; success dependencies fail.
            self.assertFalse(row['status'] not in control.DONE)
            self.assertTrue(row['status'] in control.DONE and row['status'] != 'COMPLETED_DIAGNOSTIC_NOT_QUALIFIED')


if __name__ == '__main__':
    unittest.main(verbosity=2)
