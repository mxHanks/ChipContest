#!/usr/bin/env python3
"""Host identity/failure/coverage guards; these checks assert no native EDA pass."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import coverage186 as api


class Host186(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = api.read(api.HERE / 'references186.json')
        cls.targets = api.read(api.HERE / 'targets186.json')
        cls.query, cls.method = api.render(cls.ref, cls.targets)

    def test_actual185_frozen_targets(self):
        p = Path(self.targets['source_targets185']['path'])
        c = Path(self.targets['source_checks185']['path'])
        self.assertEqual(api.identity(p)['sha256'], self.targets['source_targets185']['sha256'])
        self.assertEqual(api.identity(c)['sha256'], self.targets['source_checks185']['sha256'])
        self.assertEqual(len(self.targets['objects']), 9257)
        self.assertEqual(sum('pulse_' in x['role'] for x in self.targets['objects']), 9219)

    def test_actual178_and155_provenance(self):
        root = api.HERE.parent / 'xu-score-resume-20261103'
        pre = root / 'preflight178/s2e-final155-power-preflight-20261105-166'
        old = root / 'serverfailed159/s2e-own-timing-repair-20261105-155/state.json'
        api.verify_provenance(self.ref, api.read(pre / 'prepared.json'), api.read(pre / 'execution.json'),
                              api.read(pre / 'result.json'), api.read(old))
        bad = copy.deepcopy(api.read(pre / 'result.json'))
        bad['input_sha256_after'] = {}
        with self.assertRaises(ValueError):
            api.verify_provenance(self.ref, api.read(pre / 'prepared.json'), api.read(pre / 'execution.json'), bad, api.read(old))

    def test_exact_original155_method_and_no_allprop(self):
        original = (api.HERE / 'frozen-own155-sta.tcl').read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), self.ref['original_sta']['sha256'])
        self.assertEqual(self.method, self.ref['target_context']['analysis_clock_contract'])
        self.assertIn('set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\n', self.method)
        self.assertNotIn('set_propagated_clock', self.query)
        with self.assertRaises(ValueError):
            api.own_setup(self.ref, original.replace(b'set XU_PLL_DIV 0', b'set XU_PLL_DIV 1'))

    def test_native_exact_inventory_and_bounded_deep(self):
        self.assertIn('dict get $xu_counts $n] != 1', self.query)
        self.assertIn('dict exists $xu_wanted $n', self.query)
        self.assertIn('get_lib_pins -quiet -of_objects $p', self.query)
        self.assertIn('if {[string first {deep_} $role] < 0} {continue}', self.query)
        self.assertNotIn('all_fanout', self.query)
        self.assertIn('pulse_RDN_low', self.query)
        self.assertIn('fifo_tx_data_reg[0]/E', self.query)

    def test_no_new_graph_or_constraint_mutation(self):
        for token in ('create_clock', 'create_generated_clock', 'set_case_analysis', 'set_false_path', 'set_disable_timing',
                      'set_clock_latency', 'set_min_delay', 'set_max_delay', 'insert_buffer', 'set_logic_zero', 'set_logic_one'):
            self.assertNotIn(token, self.query)
        self.assertNotIn('get_attribute $arc full_name', self.query)
        self.assertIn('get_lib_timing_arcs -of_objects $lc', self.query)
        self.assertIn('from_lib_pin to_lib_pin', self.query)
        for line in self.query.splitlines():
            if 'report_timing ' in line:
                self.assertNotIn('-slack', line)
                self.assertNotIn('-max_paths', line)
                self.assertNotIn('-nworst', line)

    def test_undefined_optional_attribute_preserves_raw_error(self):
        template = (api.HERE / 'query186.tcl.in').read_text()
        procs = template[template.index('set xu_status '):template.index('set xu_targets ')]
        # This fixture executes only the real Tcl attribute wrapper. Native
        # redirect/get_attribute are deliberately simulated, never a PT claim.
        stub = '''proc redirect {flag name body} {
 upvar 1 $name output
 set output {Error: attribute unsupported in fixture (ATTR-1)}
 uplevel 1 $body
}
proc get_attribute {args} {return {}}
'''
        with tempfile.TemporaryDirectory() as root:
            result = subprocess.run(['tclsh'], cwd=root, input=stub + procs + '\nputs [xu186_attr _sel1 absent owner#arc0]\nclose $xu_attr_diag\nclose $xu_status\n',
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            self.assertEqual(result.stdout.strip(), 'ABSENT_OR_EMPTY:absent')
            self.assertEqual(result.stderr, '')
            diagnostics = (Path(root) / 'attribute-diagnostics.tsv').read_text()
            self.assertIn('Error: attribute unsupported in fixture (ATTR-1)', diagnostics)
            self.assertIn('owner#arc0', diagnostics)

    def test_tcl_script_complete_without_execution(self):
        script = 'set f [open {' + str(api.HERE / 'query186.tcl.in') + '} r]\nset s [read $f]\nclose $f\nputs [info complete $s]\n'
        result = subprocess.run(['tclsh'], input=script, text=True, stdout=subprocess.PIPE, check=True)
        self.assertEqual(result.stdout.strip(), '1')

    def test_malformed_targets_rejected(self):
        for change in ('duplicate', 'counts', 'unsafe'):
            data = copy.deepcopy(self.targets)
            if change == 'duplicate': data['objects'].append(data['objects'][0])
            elif change == 'counts': data['pulse_counts']['E_high'] = 23
            else: data['objects'][0]['name'] += '\n'
            with self.assertRaises(ValueError): api.render(self.ref, data)

    def test_native_marker_version_and_error_context(self):
        version = 'Version T-2022.03-SP5-1\n'
        for text, code in [(version + 'puts {' + api.MARKER + '}\n', 0), (version + api.MARKER + '\n', 1),
                           (version + (api.MARKER + '\n') * 2, 0), ('Version other\n' + api.MARKER + '\n', 0)]:
            with self.assertRaises(ValueError): api.inspect_log(text, code)
        log = api.inspect_log(version + 'XU186_REPORT_BEGIN optional.rpt\nError: retained optional\nXU186_REPORT_END optional.rpt catch=1\n' + api.MARKER + '\n', 0)
        self.assertEqual(log['errors'], [dict(report='optional.rpt', line='Error: retained optional')])

    def test_fresh_root_never_restarts(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.object(api.subprocess, 'Popen') as proc:
            with self.assertRaises(FileExistsError): api.run(Path(root), 1)
            proc.assert_not_called()

    def report_fixture(self, out):
        names = api.required_names()
        (out / 'query-status.tsv').write_text('report\tcatch_code\tmessage\n' + ''.join(x + '\t0\t\n' for x in sorted(names)))
        files = names | {'static-metadata.tsv', 'driver-load.tsv', 'net-startpoints.tsv', 'design-arcs.tsv', 'library-arcs.tsv',
                         'tool-version.rpt', 'attribute-diagnostics.tsv'}
        for name in files: (out / name).write_text('No constrained paths.\n')

    def test_required_report_gaps_and_native_errors_fail(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root); self.report_fixture(out)
            self.assertEqual(len(api.review(out, dict(errors=[]))), len(api.required_names()))
            path = out / 'check-timing.rpt'
            path.write_text('')
            with self.assertRaises(ValueError): api.review(out, dict(errors=[]))
            path.write_text('Error: native required failure\n')
            with self.assertRaises(ValueError): api.review(out, dict(errors=[]))
            path.write_text('No constrained paths.\n')
            with self.assertRaises(ValueError): api.review(out, dict(errors=[dict(report=None, line='Error: unattributed')]))
            path.unlink()
            with self.assertRaises(ValueError): api.review(out, dict(errors=[]))

    def metadata_fixture(self, out):
        fields = ['role', 'object', 'class', 'owner', 'ref', 'lib_pin', 'min_pulse_width_high', 'min_pulse_width_low']
        rows = []
        for item in self.targets['objects']:
            pin = '/' in item['name']
            rows.append(dict(role=item['role'], object=item['name'], **{'class': 'pin' if pin else 'port'},
                             owner='native-owner' if pin else '', ref='native-ref' if pin else '', lib_pin='lib/pin' if pin else '',
                             min_pulse_width_high='ABSENT_OR_EMPTY:min_pulse_width_high', min_pulse_width_low='0.010'))
        def emit(data):
            with (out / 'static-metadata.tsv').open('w', newline='') as stream:
                w = csv.DictWriter(stream, fields, delimiter='\t'); w.writeheader(); w.writerows(data)
        emit(rows)
        (out / 'attribute-diagnostics.tsv').write_text('object_handle\tcontext\tattribute\tcatch_code\tvalue\traw_diagnostics\n')
        return rows, emit

    def test_all_exact_native_rows_and_sentinels(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root); rows, emit = self.metadata_fixture(out)
            summary = api.review_metadata(out, self.targets)
            self.assertEqual(summary['exact_object_count'], 9257)
            self.assertEqual(summary['pulse_counts'], self.targets['pulse_counts'])
            self.assertEqual(summary['pulse_width_unavailable_or_empty'], {'E_high': 24})
            self.assertEqual(summary['pulse_or_recovery_exemptions'], 0)
            emit(rows[:-1])
            with self.assertRaises(ValueError): api.review_metadata(out, self.targets)
            bad = copy.deepcopy(rows); bad[0]['role'] = 'invented'; emit(bad)
            with self.assertRaises(ValueError): api.review_metadata(out, self.targets)
            bad = copy.deepcopy(rows); next(x for x in bad if 'pulse_' in x['role'])['lib_pin'] = ''; emit(bad)
            with self.assertRaises(ValueError): api.review_metadata(out, self.targets)

    def test_changed_input_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / 'input'; p.write_text('before'); row = api.identity(p); p.write_text('after')
            with self.assertRaises(ValueError): api.checked_inputs(dict(server_inputs=[row], library_compiler_root=root))

    def test_bundle_and_unique_native_job(self):
        import job186
        manifest = api.bundle()
        self.assertEqual({x['name'] for x in manifest['runtime']}, api.RUNTIME)
        j = job186.job()
        self.assertTrue(j['native'])
        self.assertEqual(j['process_contains'], j['output_root'])
        self.assertEqual(j['result_state'], j['output_root'] + '/state.json')
        self.assertEqual(j['dependencies'], [dict(id='s2c_readonly177', policy='terminal'), dict(id='s2e_final155_preflight166', policy='success')])
        self.assertEqual(len(j['frozen_inputs']), len({x['path'] for x in j['frozen_inputs']}))
        self.assertEqual(j['success_statuses'], [api.SUCCESS]); self.assertEqual(j['failure_statuses'], [api.FAILURE])


if __name__ == '__main__':
    unittest.main(verbosity=2)
