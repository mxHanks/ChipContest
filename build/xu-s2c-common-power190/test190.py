#!/usr/bin/env python3
"""Local190 host checks. Actual original evidence + explicitly synthetic lifecycle; no EDA."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
WORK = HERE.parent.parent
sp = importlib.util.spec_from_file_location('power190', str(HERE / 'power190.py'))
api = importlib.util.module_from_spec(sp)
sp.loader.exec_module(api)
import sys
sys.modules['power190'] = api
jobs_sp = importlib.util.spec_from_file_location('jobs190', str(HERE / 'jobs190.py'))
jobs = importlib.util.module_from_spec(jobs_sp)
jobs_sp.loader.exec_module(jobs)
OLD = WORK / 'build/xu-score-resume-20261103/next-results-export-69/s2c-full-soc-power12-20261104-57'
INV = WORK / 'build/xu-score-resume-20261103/terminal-results-export-22/s2c-pt-macro-pin-inventory-20261103-20'
ORIGINAL = api.read(OLD / 'prepared.json')
MACROS = api.base.inventory_rows(INV / 'macro-pins.tsv')
SCOPE = api.read(HERE / 'references190.json')['scope']


def task_local(i):
    task = copy.deepcopy(ORIGINAL['tasks'][i])
    for field, name in [('script', 'power.tcl'), ('measured_sram_pin_states', 'measured-sram-pins.json')]:
        task[field]['path'] = str(OLD / ('task_%02d' % i) / name)
    return task


class ActualEvidence(unittest.TestCase):
    def test_actual_prepared_execution_hashes(self):
        ref = api.read(HERE / 'references190.json')
        self.assertEqual(api.sha(OLD / 'prepared.json'), ref['prepared57']['sha256'])
        self.assertEqual(api.sha(OLD / 'execution.json'), ref['execution57']['sha256'])
        e = api.read(OLD / 'execution.json')
        self.assertEqual(e['input_sha256_before'], e['input_sha256_after'])
        self.assertEqual(e['input_sha256_before'], ORIGINAL['input_sha256'])
        self.assertEqual(len(e['input_sha256_before']), 367)

    def test_all12_native_original_logs(self):
        e = api.read(OLD / 'execution.json')
        for task, native in zip(ORIGINAL['tasks'], e['tasks']):
            api.base.checked_native_log(OLD / task['directory'] / 'pt.log', task['completion_marker'], native['execution']['returncode'])

    def test_all12_exact_clock_saif_marker_delta(self):
        for i in range(12):
            task = task_local(i)
            item = dict(task, saif=dict(path='/synthetic-new190/task_%02d/task-mapped.saif' % i), completion_marker='SYNTHETIC190_%d' % i)
            rendered = api.power_script(task, item, SCOPE)
            original = Path(task['script']['path']).read_text()
            self.assertNotIn('set_propagated_clock [all_clocks]', rendered)
            self.assertEqual(rendered.count('source {' + SCOPE['path'] + '}'), 1)
            self.assertEqual(rendered.count('set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1'), 1)
            inverse = rendered.replace('set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource {' + SCOPE['path'] + '}\nupdate_timing\n',
                                       'set_propagated_clock [all_clocks]\nupdate_timing\n')
            inverse = inverse.replace(api.tcl(item['saif']['path']), api.tcl(task['saif']['path'])).replace(item['completion_marker'], task['completion_marker'])
            self.assertEqual(inverse, original)
            self.assertIn('source {' + ORIGINAL['analysis_sdc']['path'] + '}', rendered)
            self.assertIn('read_verilog {' + ORIGINAL['netlist']['path'] + '}', rendered)

    def test_inventory_same_native_groups_and_pin_contract(self):
        text = api.inventory_script(task_local(0), SCOPE, 'SYNTHETIC_INVENTORY')
        self.assertEqual(text.count('if {[catch {'), 1)
        self.assertIn('$nc != 336 || $np != 22512', text)
        self.assertIn('set xu_all_macros', text)
        self.assertIn('RAMSP1024X16', text)
        self.assertNotIn('read_saif', text)
        self.assertNotIn('set_propagated_clock [all_clocks]', text)
        self.assertEqual(MACROS, api.read(INV / 'inventory.json')['macros'])

    def test_all12_unknowns_preserved(self):
        summaries = [api.measured_summary(task_local(i), MACROS) for i in range(12)]
        self.assertEqual({x['q_tx_positive'] for x in summaries}, {5280})
        self.assertEqual({x['q_tx_full_window'] for x in summaries}, {4256})
        self.assertEqual({x['pin_count'] for x in summaries}, {22512})
        self.assertEqual({x['duration_ticks'] for x in summaries}, {6604373333334})

    def test_no_clock_double_replacement_or_wrong_scope(self):
        original = Path(task_local(0)['script']['path']).read_text()
        with self.assertRaises(ValueError):
            api.common_clock(original, dict(SCOPE, sha256='0' * 64))
        with self.assertRaises(ValueError):
            api.common_clock(api.common_clock(original, SCOPE), SCOPE)
        with self.assertRaises(ValueError):
            api.common_clock(original + 'set_propagated_clock [all_clocks]\nupdate_timing\n', SCOPE)

    def test_measured_duplicate_or_dwell_corruption_rejected(self):
        task = task_local(0)
        original = api.read(task['measured_sram_pin_states']['path'])
        for defect in ['duplicate', 'dwell', 'unknown']:
            broken = copy.deepcopy(original)
            if defect == 'duplicate':
                broken['pins'][1] = copy.deepcopy(broken['pins'][0])
            elif defect == 'dwell':
                broken['pins'][0]['T0'] += 1
            else:
                broken['alias_unknown_bit_ticks'] += 1
            with patch.object(api, 'read', return_value=broken):
                with self.assertRaises(ValueError):
                    api.measured_summary(task, MACROS)

    def test_actual_report_diagnostic_precision(self):
        task = task_local(0)
        task['measured_summary'] = api.measured_summary(task, MACROS)
        d = api.diagnostic(OLD / 'task_00', task)
        self.assertEqual(d['diagnostic_energy_j'], '0.0002298321920000232')
        self.assertEqual(d['qualification'], 'NOT_QUALIFIED')
        self.assertIn('unknown Q', ' '.join(d['unresolved']))


class Guards(unittest.TestCase):
    def test_runtime_complete_freeze(self):
        rec = api.runtime()
        self.assertEqual(len(rec), 8)
        self.assertIn(str(HERE / 'manifest190.json'), rec)

    def test_runtime_omitted_duplicate_and_hash_rejected(self):
        manifest = api.read(HERE / 'manifest190.json')
        for mode in ['omit', 'duplicate', 'sha']:
            broken = copy.deepcopy(manifest)
            if mode == 'omit':
                broken['runtime'].pop()
            elif mode == 'duplicate':
                broken['runtime'][0] = broken['runtime'][1]
            else:
                broken['runtime'][0]['sha256'] = '0' * 64
            with patch.object(api, 'read', return_value=broken):
                with self.assertRaises(ValueError):
                    api.runtime()

    def test_unique_out_marker_and_dependencies(self):
        a, b = jobs.job('preflight190'), jobs.job('full12_190')
        self.assertEqual(a['id'], 's2c_common_preflight190')
        self.assertEqual(b['id'], 's2c_common_full12_190')
        self.assertEqual(a['dependencies'], [dict(id='s2e_coverage186', policy='terminal')])
        self.assertEqual(b['dependencies'], [dict(id=a['id'], policy='success')])
        for own, other in [(a, b), (b, a)]:
            self.assertEqual(own['process_contains'], own['output_root'])
            self.assertNotIn(other['output_root'], ' '.join(own['argv']))
            self.assertTrue(own['native'])

    def test_native_timeout_retains_execution_receipt(self):
        import subprocess
        class FakeProcess:
            pid = 12345
            returncode = -15
            calls = 0
            def wait(self, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired('synthetic', timeout)
                return self.returncode
            def terminate(self):
                pass
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / 'power.tcl'
            script.write_text('# synthetic only')
            with patch.object(api.subprocess, 'Popen', return_value=FakeProcess()):
                receipt = api.native(script, root, dict(path='/never-executed'), {}, 1)
            self.assertTrue(receipt['timed_out'])
            self.assertEqual(receipt['pid'], 12345)
            self.assertEqual(receipt['returncode'], -15)
            self.assertEqual(receipt['log'], api.identity(root / 'pt.log'))

    def test_samepid_frozen_commands(self):
        for name, ids in [('preflight190', '0'), ('full12_190', 'all')]:
            c = api.read(HERE / ('command-' + name + '.json'))
            self.assertEqual(c['entry_sha256'], api.sha(HERE / 'power190.py'))
            self.assertEqual(c['argv'][c['argv'].index('--task-ids') + 1], ids)
            self.assertEqual('--preflight-root' in c['argv'], ids == 'all')

    def test_fresh_output_never_restarted(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(api, 'native') as native:
                with self.assertRaises(ValueError):
                    api.main(['campaign', '--out', temp])
                native.assert_not_called()

    def test_full12_missing_preflight_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'notcreated'
            with self.assertRaises(ValueError):
                api.main(['campaign', '--out', str(out), '--task-ids', 'all'])
            self.assertFalse(out.exists())

    def test_native_report_pin_and_macro_completeness(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            states = root / 'states.json'
            api.write(states, dict(pins=[dict(mapped_path='a/Q[0]'), dict(mapped_path='a/Q[1]')]))
            task = dict(expected_reports=['sram-pins-before.rpt', 'sram-power.rpt'],
                        measured_sram_pin_states=dict(path=str(states)), macro_names=['a'])
            pin = root / 'sram-pins-before.rpt'
            pin.write_text('XU_SRAM_PIN name=a/Q[0]\nXU_SRAM_PIN name=a/Q[1]\n')
            power = root / 'sram-power.rpt'
            power.write_text('XU_SRAM_POWER_CELL name=a ref=RAMSP1024X16\n')
            self.assertEqual(len(api.checked_reports(root, task)), 2)
            pin.write_text('XU_SRAM_PIN name=a/Q[0]\n')
            with self.assertRaises(ValueError):
                api.checked_reports(root, task)
            pin.write_text('XU_SRAM_PIN name=a/Q[0]\nXU_SRAM_PIN name=a/Q[1]\n')
            power.write_text('XU_SRAM_POWER_CELL name=a ref=WRONG\n')
            with self.assertRaises(ValueError):
                api.checked_reports(root, task)
            power.write_text('Error: bad report\n')
            with self.assertRaises(ValueError):
                api.checked_reports(root, task)

    def synthetic_run(self, temp, fail=False):
        out = Path(temp)
        (out / 'task_00').mkdir()
        (out / 'lc/bin').mkdir(parents=True)
        states = out / 'states.json'
        api.write(states, dict(pins=[dict(mapped_path='a/Q[0]')]))
        task = dict(task_id=0, directory='task_00', expected_reports=['power.rpt', 'tool-version.rpt'],
                    macro_names=['a'], completion_marker='SYNTHETIC190_DONE',
                    measured_sram_pin_states=dict(path=str(states)), measured_summary=dict(synthetic=True),
                    activity_window=dict(formal_elapsed_cycles=990656, duration_ticks=6604373333334))
        (out / 'task_00/power.tcl').write_text('# synthetic; never EDA\n')
        m = dict(requested_task_ids=[0], tasks=[task], context=dict(synthetic=True), tool=dict(path='/not-run'),
                 library_compiler_root=str(out / 'lc'), input_sha256={str(states): api.sha(states)})
        api.write(out / 'prepared.json', m)
        def fake_native(script, directory, tool, env, timeout):
            (directory / 'power.rpt').write_text((OLD / 'task_00/power.rpt').read_text())
            (directory / 'tool-version.rpt').write_text(api.base.PT_VERSION)
            (directory / 'pt.log').write_text('Version ' + api.base.PT_VERSION + '\n' + task['completion_marker'] + '\n')
            return dict(returncode=1 if fail else 0, log=api.identity(directory / 'pt.log'))
        args = argparse.Namespace(out=out, task_ids=[0], timeout=30)
        state = dict(status='PREPARED_COMMON190_NOT_QUALIFIED')
        with patch.object(api, 'prepared_verify'), patch.object(api, 'native', side_effect=fake_native):
            if fail:
                with self.assertRaises(ValueError):
                    api.run(args, state)
            else:
                api.run(args, state)
        return out, state

    def test_synthetic_native_lifecycle_and_no_repeat(self):
        with tempfile.TemporaryDirectory() as temp:
            out, state = self.synthetic_run(temp)
            self.assertEqual(state['status'], api.TASK0)
            self.assertEqual(api.read(out / 'execution.json')['input_sha256_before'], api.read(out / 'execution.json')['input_sha256_after'])
            with patch.object(api, 'prepared_verify'), patch.object(api, 'native') as native:
                with self.assertRaises(ValueError):
                    api.run(argparse.Namespace(out=out, task_ids=[0]), state)
                native.assert_not_called()

    def test_synthetic_native_failure_preserves_log_and_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            out, state = self.synthetic_run(temp, True)
            e = api.read(out / 'execution.json')
            self.assertEqual(e['status'], api.FAIL)
            self.assertTrue((out / 'task_00/pt.log').is_file())
            self.assertFalse((out / 'summary.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
