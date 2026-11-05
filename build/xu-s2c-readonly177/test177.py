#!/usr/bin/env python3
"""Host semantics/identity/failure guards; no EDA result is asserted here."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import readonly177 as api


class Host177(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = api.read(api.HERE / 'references177.json')

    def test_actual175_frozen_metadata(self):
        p = Path(self.ref['actual175']['path'])
        if not p.exists():
            self.skipTest('local historical175 unavailable; runtime references remain frozen')
        a = p.read_bytes()
        self.assertEqual(hashlib.sha256(a).hexdigest(), self.ref['actual175']['sha256'])
        self.assertEqual(json.loads(a)['next_minimal_readonly_query'], self.ref['next_minimal_readonly_query'])

    def test_own57_template_original(self):
        data = (api.HERE / 'frozen-ownS2c-power57.tcl').read_bytes()
        self.assertEqual(len(data), 45200)
        self.assertEqual(api.digest(data), 'c99c65389f03d0a5d49b11bb50d9ce5a0440ae259ec72fe2c30f886c97e159b8')
        setup, method = api.clock_setup(self.ref, data)
        self.assertIn('set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\n', method)
        self.assertIn('set_propagated_clock [all_clocks]\nupdate_timing\n', method)
        self.assertNotIn('155', setup)
        self.assertNotIn('116', setup)

    def test_reject_clock_template_corruption(self):
        original = (api.HERE / 'frozen-ownS2c-power57.tcl').read_bytes()
        with self.assertRaises(ValueError):
            api.clock_setup(self.ref, original.replace(b'set XU_PLL_DIV 0', b'set XU_PLL_DIV 1'))

    def test_target_literal_and_native_unique(self):
        query, method = api.render_query(self.ref)
        self.assertIn('dp_gt0.vec_31_dfflr/qout_r_reg[0]', query)
        self.assertNotIn('dp_gt0/vec_31_dfflr', query)
        self.assertIn('if {[get_object_name $c] eq $xu_exact}', query)
        self.assertIn('[sizeof_collection $xu_cell] != 1', query)
        self.assertIn('[dict size $xu_pins] != 4', query)
        self.assertIn('wrong direction', query)
        self.assertIn(method, query)

    def test_bad_target_components_rejected(self):
        ref = copy.deepcopy(self.ref)
        ref['next_minimal_readonly_query']['target_identifier_components'][-2] = 'dp_gt0/vec_31_dfflr'
        with self.assertRaises(ValueError):
            api.render_query(ref)

    def test_no_constraint_tb_or_model_mutation(self):
        query, _ = api.render_query(self.ref)
        for token in ('set_false_path', 'set_case_analysis', 'create_clock', 'create_generated_clock', 'set_clock_latency',
                      'set_min_delay', 'insert_buffer', 'set_disable_timing', 'force ', 'set_logic_zero', 'set_logic_one'):
            self.assertNotIn(token, query)
        self.assertIn('report_timing -delay_type min -to $xu_D -path_type full_clock_expanded', query)
        self.assertIn('all_fanout -flat -endpoints_only -from $xu_Q', query)
        self.assertNotIn('all_fanout -flat -trace_arcs all', query)
        self.assertIn('STOP_OWNER', query)

    def test_model_summary_no_body_or_table(self):
        fixture = b'''`timescale 1ns/1ps
primitive UTEST (out,in,clk,notify); output out; input in,clk,notify; reg out; table 0 (01) ? : ? : 0; endtable endprimitive
module DRNQV0_12TR40 (D,CK,RDN,Q); input D,CK,RDN; output Q; reg NOTIFIER; wire n0;
UTEST u0 (n0,D,CK,NOTIFIER); assign Q = n0;
specify $hold (posedge CK, posedge D, 0.010, NOTIFIER); endspecify endmodule'''
        s = api.model_summary(fixture)
        self.assertEqual(s['timing_checks'][0]['kind'], 'hold')
        self.assertEqual(s['timing_checks'][0]['arguments'], ['posedge CK', 'posedge D', '0.010', 'NOTIFIER'])
        self.assertEqual(s['primitive_instances'][0]['port_connections']['notify'], 'NOTIFIER')
        self.assertEqual(s['bounded_assign_relations'], [dict(destination='Q', expression='n0')])
        self.assertEqual(s['source_timescale_tokens'], ['1ns/1ps'])
        serial = json.dumps(s)
        self.assertNotIn('endprimitive', serial)
        self.assertNotIn('(01)', serial)
        self.assertFalse(s['module_body_exported'])
        self.assertFalse(s['udp_table_exported'])

    def test_model_ambiguity_rejected(self):
        data = b'module DRNQV0_12TR40(); specify endspecify endmodule'
        with self.assertRaises(ValueError):
            api.model_summary(data + data)
        with self.assertRaises(ValueError):
            api.model_summary(b'module DRNQV0_12TR40(); endmodule')

    def test_native_marker_requires_actual_output(self):
        version = 'Version T-2022.03-SP5-1\n'
        with self.assertRaises(ValueError):
            api.inspect_log(version + 'puts {' + api.MARKER + '}\n', 0)
        with self.assertRaises(ValueError):
            api.inspect_log(version + api.MARKER + '\n', 1)
        with self.assertRaises(ValueError):
            api.inspect_log(version + (api.MARKER + '\n') * 2, 0)
        with self.assertRaises(ValueError):
            api.inspect_log('Version NEW\n' + api.MARKER + '\n', 0)
        good = api.inspect_log(version + 'Warning: original kept\nError: optional report kept\n' + api.MARKER + '\n', 0)
        self.assertEqual(good['native_warning_count'], 1)
        self.assertEqual(good['native_error_lines'], ['Error: optional report kept'])

    def test_fresh_root_refuses_restart(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(subprocess, 'Popen') as popen:
                with self.assertRaises(FileExistsError):
                    api.run(Path(root), 1)
                popen.assert_not_called()

    def test_required_report_missing_error_and_zero_path_guards(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root)
            status = 'report\tcatch_code\tmessage\n' + ''.join(n + '\t0\t\n' for n in sorted(api.REQUIRED))
            (out / 'query-status.tsv').write_text(status)
            for name in api.ESSENTIAL:
                (out / name).write_text('No paths.\n')
            clean = dict(native_error_context=[])
            self.assertEqual(len(api.review_reports(out, clean)), len(api.REQUIRED))
            (out / 'min-to-D.rpt').write_text('')
            with self.assertRaises(ValueError):
                api.review_reports(out, clean)
            (out / 'min-to-D.rpt').write_text('Error: unavailable native query\n')
            with self.assertRaises(ValueError):
                api.review_reports(out, clean)
            (out / 'min-to-D.rpt').write_text('No paths.\n')
            with self.assertRaises(ValueError):
                api.review_reports(out, dict(native_error_context=[dict(report=None, line='Error: unexplained')]))
            (out / 'min-to-D.rpt').unlink()
            with self.assertRaises(ValueError):
                api.review_reports(out, clean)

    def test_changed_input_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / 'input'
            p.write_text('original')
            expected = api.identity(p)
            ref = copy.deepcopy(self.ref)
            ref['next_minimal_readonly_query']['target'] = expected
            p.write_text('changed')
            with self.assertRaises(ValueError):
                api.checked_inputs(ref)

    def test_job_native_slot_unique_path_dependency(self):
        import job177
        j = job177.job()
        self.assertTrue(j['native'])
        self.assertEqual(j['process_contains'], j['output_root'])
        self.assertEqual(j['result_state'], j['output_root'] + '/state.json')
        self.assertEqual(j['dependencies'], [dict(id='two_candidate_autopack173', policy='terminal'),
                                             dict(id='s2c_unknown167', policy='success')])
        self.assertEqual(j['success_statuses'], [api.SUCCESS])
        self.assertEqual(j['failure_statuses'], [api.FAILURE])
        self.assertEqual(len(j['frozen_inputs']), len({x['path'] for x in j['frozen_inputs']}))

    def test_runtime_bundle(self):
        self.assertEqual(api.bundle()['qualification'], 'NOT_QUALIFIED')


if __name__ == '__main__':
    unittest.main(verbosity=2)
