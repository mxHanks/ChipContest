#!/usr/bin/env python3
"""Independent offline review of207. Native PT execution is explicitly absent."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT/'build/xu-native-query207'
ACTUAL = ROOT/'build/xu-score-resume-20261103/final191'


def imported(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Review207(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = imported(SOURCE/'query207.py', 'xu210_review207')
        cls.api.bundle()
        cls.s2c = cls.api.load_api('177')
        cls.s2e = cls.api.load_api('186')
        cls.ref2c = cls.api.read(cls.s2c.HERE/'references177.json')
        cls.ref2e = cls.api.read(cls.s2e.HERE/'references186.json')

    def test_native_clock_attribute_has_actual_evidence(self):
        original = ACTUAL/'s2c-own9c16-readonly-20261105-177'
        clock = (original/'target-clock-reset.rpt').read_text()
        native = (original/'target-native.rpt').read_text()
        self.assertRegex(clock, r'clocks=_sel\d+')
        self.assertIn("Error: unknown option '-of_objects' (CMD-010)", clock)
        self.assertRegex(native, r'clocks\s+xu_hfextclk xu_plldiv_envelope')

    def test_frozen_original_sources_are_unmodified(self):
        for folder, original in [('frozen177', 'xu-s2c-readonly177'), ('frozen186', 'xu-s2e-coverage186')]:
            for path in sorted((SOURCE/folder).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts:
                    expected = ROOT/'build'/original/path.relative_to(SOURCE/folder)
                    self.assertTrue(expected.is_file())
                    self.assertEqual(path.read_bytes(), expected.read_bytes(), str(path))

    def test_actual190_frozen_bodies_and_manifest_bind(self):
        ref = self.api.read(SOURCE/'references207.json')
        archive_manifest = self.api.read(ACTUAL/'manifest.json')
        declared = {r['path']: r for r in archive_manifest['files']}
        self.assertEqual(ref['original191_archive_sha256'], '44770417f09a4244cbeea5690b4f21923e5d641de365094010ca7eeaf7c998b3')
        for row in ref['common190']:
            path = SOURCE/'frozen190'/row['name']
            archive_name = 's2c-common-scope-preflight-20261105-190/'+row['name']
            raw = (ACTUAL/archive_name).read_bytes()
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(sha(path), row['sha256'])
            self.assertEqual(path.stat().st_size, row['bytes'])
            self.assertEqual(declared[archive_name], dict(path=archive_name, bytes=row['bytes'], sha256=row['sha256']))

    def test_three_derived_queries_have_exact_own_methods(self):
        original2c, method2c = self.s2c.render_query(self.ref2c)
        original2e, method2e = self.s2e.render(self.ref2e, self.api.read(self.s2e.HERE/'targets186.json'))
        actual190 = (ACTUAL/'s2c-common-scope-preflight-20261105-190/task_00/power.tcl').read_text()
        common_method = actual190[actual190.index('set XU_CLOCK_MODE envelope\n'):actual190.index('# Exact post-elaboration macro groups;')]
        expected = {'s2c_original177': method2c, 's2c_common190': common_method, 's2e_final155186': method2e}
        for case in self.api.CASES:
            api = self.s2e if case == 's2e_final155186' else self.s2c
            ref = self.ref2e if case == 's2e_final155186' else self.ref2c
            text, derivation = self.api.derive(case, api, ref)
            with self.subTest(case=case):
                self.assertEqual(derivation['clock_method'], expected[case])
                self.assertEqual(text.count(expected[case]), 1)
                self.assertNotRegex(text, r'get_clocks\s+[^\n\]]*-of_objects')
                self.assertNotRegex(text, r'report_annotated_check[^\n]*-list_annotated[^\n]*-list_not_annotated')
                self.assertEqual(text.count('report_annotated_check -list_annotated}'), 1)
                self.assertEqual(text.count('report_annotated_check -list_not_annotated}'), 1)
                self.assertIn(api.MARKER, text)
                self.assertIn('set xu207_clock_map [open pin-clocks207.tsv w]', text)
                target = self.ref2e['target_context']['netlist'] if api is self.s2e else self.ref2c['next_minimal_readonly_query']['target']
                self.assertIn('read_verilog {'+target['path']+'}', text)
                self.assertNotIn('get_lib_pins -quiet -of_objects $p', text)
        self.assertIn('set_propagated_clock [all_clocks]', method2c)
        self.assertNotIn('set_propagated_clock [all_clocks]', common_method)
        self.assertNotIn('set_propagated_clock [all_clocks]', method2e)
        self.assertNotEqual(method2c, common_method)
        self.assertEqual(self.ref2c['next_minimal_readonly_query']['target']['sha256'], '9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892')
        self.assertEqual(self.ref2e['target_context']['netlist']['sha256'], '3440182eca862290a874bedc4eb3f94168681a7028d584d15217a13dbeafa794')

    def fixture177(self):
        root = Path(tempfile.mkdtemp(prefix='xu210-guard-'))
        self.addCleanup(shutil.rmtree, str(root))
        original = ACTUAL/'s2c-own9c16-readonly-20261105-177'
        for name in self.s2c.ESSENTIAL | {'query-status.tsv'}:
            shutil.copyfile(str(original/name), str(root/name))
        return root, original

    def test_original_required_failure_is_still_rejected(self):
        root, original = self.fixture177()
        review = self.s2c.inspect_log((original/'pt.log').read_text(), 0)
        with self.assertRaisesRegex(ValueError, 'required read-only report is unavailable'):
            self.s2c.review_reports(root, review)
        with self.assertRaisesRegex(ValueError, 'native returncode/unique actual marker differs'):
            self.s2e.inspect_log((ACTUAL/'s2e-own155-coverage-readonly-20261105-186/pt.log').read_text(), 1)

    def test_required_report_native_errors_are_not_masked(self):
        root, original = self.fixture177()
        status = (root/'query-status.tsv').read_text().splitlines()
        fixed = [line if not line.startswith('target-clock-reset.rpt\t') else 'target-clock-reset.rpt\t0\t' for line in status]
        (root/'query-status.tsv').write_text('\n'.join(fixed)+'\n')
        (root/'target-clock-reset.rpt').write_text('SYNTHETIC_REPAIRED_REQUIRED_REPORT_FOR_GUARD_TEST_ONLY\n')
        errors = self.s2c.inspect_log((original/'pt.log').read_text(), 0)
        errors['native_error_context'] = [r for r in errors['native_error_context'] if r['report'] != 'target-clock-reset.rpt']
        reports = self.s2c.review_reports(root, errors)
        self.assertTrue(any(r['catch_code'] != 0 for r in reports), 'original optional gaps must remain visible')
        for name in sorted(self.s2c.ESSENTIAL):
            with self.subTest(report=name):
                raw = (root/name).read_bytes()
                (root/name).write_bytes(raw+b'\nError: injected nonthrowing native failure\n')
                with self.assertRaisesRegex(ValueError, 'native required report emitted Error:'):
                    self.s2c.review_reports(root, errors)
                (root/name).write_bytes(raw)
        errors['native_error_context'].append(dict(report=None, line='Error: unattributed native failure'))
        with self.assertRaisesRegex(ValueError, 'required/unattributed Error'):
            self.s2c.review_reports(root, errors)

    def test_clock_mapping_does_not_invent_values_or_allow_partial186(self):
        root = Path(tempfile.mkdtemp(prefix='xu210-map-'))
        self.addCleanup(shutil.rmtree, str(root))
        header = 'request\tpin_handle\tpin_name\tpin_class\tattribute_status\traw_attribute\tclock_handle\tclock_name\tclock_class\tdiagnostics\n'
        table = root/'pin-clocks207.tsv'
        table.write_text(header+'1\tp1\tCK\tpin\tNATIVE_CLOCK_COLLECTION\t_sel1\tc1\thf\tclock\t\n' + '2\tp2\tRDN\tpin\tABSENT_OR_EMPTY\t\t\t\t\t\n')
        result = self.api.clock_mapping_review(root, ['CK', 'RDN'])
        self.assertEqual(result['unique_pins'], 2)
        with self.assertRaisesRegex(ValueError, 'not every frozen186'):
            self.api.clock_mapping_review(root, ['CK', 'RDN', 'E'])
        table.write_text(header+'1\tp1\tCK\tpin\tABSENT_OR_EMPTY\t\tc1\thf\tclock\t\n')
        with self.assertRaisesRegex(ValueError, 'must not invent'):
            self.api.clock_mapping_review(root)
        table.write_text(header+'1\tp1\tCK\tpin\tFAILED_NATIVE_DIAGNOSTICS\t\t\t\t\tError\n')
        with self.assertRaisesRegex(ValueError, 'unresolved API failure'):
            self.api.clock_mapping_review(root)

    def test_native_slot_job_is_unique_and_dependencies_terminal(self):
        job = self.api.read(SOURCE/'native_query207.json')
        self.assertEqual(job['dependencies'], [dict(id='two_candidate_finalpack191', policy='terminal')])
        self.assertTrue(job['native'])
        self.assertEqual(job['kind'], 'launch')
        self.assertEqual(job['launch_mode'], 'direct')
        self.assertEqual(job['process_contains'], job['output_root'])
        self.assertEqual(Path(job['result_state']).parent.as_posix(), job['output_root'])
        self.assertEqual(job['argv'][-2:], ['--out', job['output_root']])
        self.assertEqual(job['success_statuses'], [self.api.SUCCESS])
        self.assertEqual(job['failure_statuses'], [self.api.FAILURE])

    def test_tcl_15_cases(self):
        root = Path(tempfile.mkdtemp(prefix='xu210-tcl-final-'))
        self.addCleanup(shutil.rmtree, str(root))
        proc = subprocess.run(['tclsh', str(HERE/'stub210.tcl'), str(SOURCE/'compat207.tcl')],
                              cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(proc.returncode, 0, proc.stdout.decode())
        self.assertIn(b'PASSED_15_CASES_NOT_NATIVE_QUALIFICATION', proc.stdout)

    def test_case_timeout_stops_later_internal_native_launches(self):
        parent = Path(tempfile.mkdtemp(prefix='xu210-timeout-'))
        self.addCleanup(shutil.rmtree, str(parent))
        calls = []
        def timeout_case(case_id, out, timeout):
            calls.append(case_id)
            out.mkdir()
            state = dict(case_id=case_id, status='FAIL_CASE207_NOT_QUALIFIED', native_runs=1,
                         native_timeout=True, error='SYNTHETIC_NATIVE_WRAPPER_TIMEOUT', returncode=None)
            self.api.write(out/'state.json', state)
            return state
        with mock.patch.object(self.api, 'run_case', side_effect=timeout_case):
            rc = self.api.run(parent/'run', 1)
        state = self.api.read(parent/'run/state.json')
        self.assertEqual(rc, 1)
        self.assertEqual(calls, [self.api.CASES[0]], 'later cases would bypass153 after native timeout')
        self.assertEqual(state['status'], self.api.FAILURE)
        self.assertTrue((parent/'run/output-manifest207.json').is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
