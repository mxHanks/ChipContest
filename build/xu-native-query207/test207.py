import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('xu_query207_test', str(HERE / 'query207.py'))
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


class Queries207(unittest.TestCase):
    def generated(self, case):
        code = '186' if case == 's2e_final155186' else '177'
        api = q.load_api(code)
        ref = q.read(api.HERE / ('references' + code + '.json'))
        return q.derive(case, api, ref)

    def test_three_actual_clock_contracts(self):
        derived = {case: self.generated(case)[1] for case in q.CASES}
        self.assertIn('set_propagated_clock [all_clocks]', derived[q.CASES[0]]['clock_method'])
        for case in q.CASES[1:]:
            method = derived[case]['clock_method']
            self.assertNotIn('set_propagated_clock [all_clocks]', method)
            self.assertIn('set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1', method)
            self.assertIn('source {/storage2/2026contest/server4/s4_23usr/Desktop/xu-ts16.tcl}', method)
        ref, context, exact = q.common_context()
        self.assertEqual(derived[q.CASES[1]]['clock_method'], exact)
        # Preserve each actual method verbatim.190 additionally carries clock
        # period guard queries/update_timing; do not falsely claim byte-equal
        # method text merely because both source the same SDC/scope contents.
        ref186 = q.read(HERE / 'frozen186/references186.json')
        self.assertEqual(context['analysis_sdc']['sha256'], ref186['target_context']['constraints']['sha256'])
        self.assertEqual(context['clock_scope']['sha256'], ref186['target_context']['clock_scope']['sha256'])

    def test_unsupported_commands_removed_only_in_derived_queries(self):
        for case in q.CASES:
            text, derived = self.generated(case)
            self.assertNotIn('get_clocks -quiet -of_objects', text)
            self.assertNotIn('report_annotated_check -list_annotated -list_not_annotated', text)
            self.assertIn('annotated-check-annotated.rpt {report_annotated_check -list_annotated}', text)
            self.assertIn('annotated-check-not-annotated.rpt {report_annotated_check -list_not_annotated}', text)
            self.assertEqual(text.count(derived['original_completion_marker_retained']), 1)
        self.assertIn('get_clocks -quiet -of_objects', (HERE / 'frozen177/query177.tcl.in').read_text())
        self.assertIn('get_clocks -quiet -of_objects', (HERE / 'frozen186/query186.tcl.in').read_text())

    def test_exact_design_pin_library_mapping_replaces_unobserved_api(self):
        text, derived = self.generated('s2e_final155186')
        self.assertNotIn('get_lib_pins -quiet -of_objects $p', text)
        self.assertIn('set lp [xu207_libpin $p]', text)
        self.assertIn('get_lib_pins -of_objects $lc', text)
        self.assertIn('get_lib_cells -of_objects $owner', text)

    def test_original_required_reports_retained(self):
        api = q.load_api('177')
        self.assertEqual(api.REQUIRED, {'min-to-D.rpt', 'min-path-native.rpt', 'target-clock-reset.rpt',
                                      'target-libpins.rpt', 'check-timing.rpt', 'units.rpt',
                                      'analysis-coverage.rpt', 'Q-first-state-boundaries.rpt'})
        api2 = q.load_api('186')
        self.assertEqual(len(api2.required_names()), 62)

    def test_wrong_common_map_is_rejected(self):
        original = q.read
        def mutant(path):
            data = original(path)
            if Path(path).name == 'prepared.json':
                data = copy.deepcopy(data)
                data['context']['netlist']['sha256'] = '0' * 64
            return data
        with mock.patch.object(q, 'read', side_effect=mutant):
            with self.assertRaisesRegex(ValueError, 'map/SDC/scope'):
                q.common_context()

    def test_wrong_common_method_is_rejected(self):
        original = q.method_from
        with mock.patch.object(q, 'method_from', side_effect=lambda t: original(t) + '\n' if 'power_enable_analysis' in t else original(t)):
            # Both original files contain power settings, so a uniformly bad
            # trailing method is caught by its exact update_timing contract.
            with self.assertRaises(ValueError):
                q.common_context()

    def test_later_cases_run_after_first_failure(self):
        calls = []
        def fake(case, out, timeout):
            calls.append(case)
            out.mkdir()
            state = dict(status='FAIL_CASE207_NOT_QUALIFIED' if len(calls) == 1 else 'EXECUTED_CASE207_NOT_QUALIFIED',
                         native_runs=0, qualification='NOT_QUALIFIED')
            q.write(out / 'state.json', state)
            return state
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'fresh'
            with mock.patch.object(q, 'run_case', side_effect=fake):
                self.assertEqual(q.run(out, 1), 1)
            state = q.read(out / 'state.json')
            self.assertEqual(calls, q.CASES)
            self.assertEqual(len(state['cases']), 3)
            self.assertEqual(state['status'], q.FAILURE)
            self.assertTrue((out / 'output-manifest207.json').is_file())

    def test_fresh_root_guard(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'fresh207'):
                q.run(Path(d), 1)

    def test_mapping_cannot_fill_absent_clocks(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'pin-clocks207.tsv'
            p.write_text('request\tpin_handle\tpin_name\tpin_class\tattribute_status\traw_attribute\tclock_handle\tclock_name\tclock_class\tdiagnostics\n'
                         '1\tp1\ttarget/CK\tpin\tABSENT_OR_EMPTY\t\tc1\tFAKE\tclock\t\n')
            with self.assertRaisesRegex(ValueError, 'invent clock'):
                q.clock_mapping_review(Path(d))

    def test_generated_tcl_has_complete_braces(self):
        for case in q.CASES:
            text, _ = self.generated(case)
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / 'query.tcl'
                path.write_text(text)
                script = 'set f [open {' + str(path) + '} r];set s [read $f];close $f;if {![info complete $s]} {exit 1}\n'
                result = subprocess.run(['tclsh'], input=script, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
