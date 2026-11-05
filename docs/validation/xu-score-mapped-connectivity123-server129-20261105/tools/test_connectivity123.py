#!/usr/bin/env python3
"""Mechanism/negative checks only. These fixtures are not mapped DUT evidence."""
import ast
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('xu_connectivity123', str(HERE / 'xu_mapped_connectivity123.py'))
xu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xu)

LIBRARY = '''
module BUF (A, Z); input A; output Z; buf (Z,A); endmodule
module DFF (D, CK, Q); input D,CK; output Q; reg NOTIFIER; endmodule
module VEC (A,Z); input [1:0] A; output [1:0] Z; endmodule
'''
DESIGN = r'''
module leaf (a, y);
 input a; output y;
 wire \internal.name[0] ;
 BUF \u.gate[0] (.A(a), .Z(\internal.name[0] ));
 assign y = \internal.name[0] ;
endmodule
module xu_soc_ppa_top (src,ck,dst,before,after);
 input src,ck; output dst,before,after;
 wire n;
 leaf u_child (.a(src),.y(n));
 assign before = n;
 DFF u_state (.D(n),.CK(ck),.Q(after));
 BUF u_final (.A(after),.Z(dst));
endmodule
'''


class Checks(unittest.TestCase):
    def setUp(self):
        self.graph = xu.analyze(DESIGN, [LIBRARY])

    def query(self, a, b, allow=False):
        return self.graph.path(self.graph.node((), a), self.graph.node((), b), allow)

    def test_escaped_atomic_names_are_not_hierarchy_or_select(self):
        path = self.query('src', 'before')
        self.assertTrue(path['found'])
        self.assertIn(('u_child', 'u.gate[0]'), self.graph.instances)
        self.assertIn((('u_child',), 'internal.name[0]'), self.graph.ids)

    def test_ports_and_assign_are_directional(self):
        self.assertTrue(self.query('src', 'before')['found'])
        self.assertFalse(self.query('before', 'src')['found'])
        self.assertEqual([x['kind'] for x in self.query('src', 'before')['edges']],
                         ['hierarchy_input', 'combinational_potential_relation',
                          'combinational_potential_relation', 'continuous_assign',
                          'hierarchy_output', 'continuous_assign'])

    def test_sequential_barrier_is_primary_default(self):
        result = self.query('src', 'dst')
        self.assertFalse(result['found'])
        self.assertEqual(result['stateful_frontier_count'], 1)
        self.assertEqual(result['stateful_frontier'][0]['instance'], ['u_state'])

    def test_secondary_path_explicitly_exposes_state(self):
        result = self.query('src', 'dst', True)
        self.assertTrue(result['found'])
        self.assertTrue(result['sequential_arcs_allowed'])
        self.assertEqual(sum(x['kind'] == 'stateful_boundary' for x in result['edges']), 2)

    def test_constants_do_not_create_alias_paths(self):
        graph = xu.analyze("module xu_soc_ppa_top(a,y);input a;output y;assign y=1'b0;endmodule", [LIBRARY])
        self.assertFalse(graph.path(graph.node((), 'a'), graph.node((), 'y'))['found'])

    def test_exact_vector_concat_and_replication(self):
        widths = {'a': (3, 0), 'b': (0, 1)}
        self.assertEqual(xu.expression(['a'], widths), ['a[3]', 'a[2]', 'a[1]', 'a[0]'])
        self.assertEqual(xu.expression(['b'], widths), ['b[0]', 'b[1]'])
        self.assertEqual(xu.expression(['{', 'a', '[', '1', ':', '0', ']', ',', "2'b00", '}'], widths),
                         ['a[1]', 'a[0]', None, None])
        self.assertEqual(xu.expression(['{', '2', '{', 'b', '}', '}'], widths), ['b[0]', 'b[1]'] * 2)

    def test_vector_hierarchy_preserves_bit_order(self):
        design = '''module leaf(a,y);input[1:0]a;output[1:0]y;assign y=a;endmodule
        module xu_soc_ppa_top(a,y);input[3:0]a;output[1:0]y;leaf l(.a({a[0],a[3]}),.y(y));endmodule'''
        graph = xu.analyze(design, [LIBRARY])
        self.assertTrue(graph.path(graph.node((), 'a[0]'), graph.node((), 'y[1]'))['found'])
        self.assertFalse(graph.path(graph.node((), 'a[0]'), graph.node((), 'y[0]'))['found'])

    def test_ansi_continuation_keeps_vector_width(self):
        parsed = xu.modules('module m(input wire [3:0] a,b, output y);endmodule')['m']
        self.assertEqual(parsed['widths'], {'a': (3, 0), 'b': (3, 0), 'y': None})

    def test_comments_strings_and_attributes_do_not_invent_modules(self):
        parsed = xu.modules('''// module fake();endmodule
        (* origin = "module pretend; endmodule" *)
        module real(a);input a;endmodule /* module another;endmodule */''')
        self.assertEqual(list(parsed), ['real'])

    def test_library_body_not_exported(self):
        result = json.dumps(self.graph.cells)
        self.assertNotIn('reg NOTIFIER', result)
        self.assertNotIn('buf (Z,A)', result)
        self.assertIn('pin_directions', result)

    def test_conditional_schema_consistency_and_state_union(self):
        parsed = xu.modules('module m(A,Z);input A;output Z;endmodule\nmodule m(A,Z);input A;output Z;reg NOTIFIER;endmodule', False)
        self.assertTrue(parsed['m']['stateful'])
        with self.assertRaisesRegex(ValueError, 'schema disagreement'):
            xu.modules('module m(A);input A;endmodule module m(A);output A;endmodule', False)

    def test_negative_nonconstant_declaration(self):
        with self.assertRaises(ValueError):
            xu.modules('module m(a);input[W-1:0]a;endmodule')

    def test_negative_expression_operator_not_silently_aliased(self):
        with self.assertRaises(ValueError):
            xu.analyze('module xu_soc_ppa_top(a,y);input a;output y;assign y=~a;endmodule', [LIBRARY])

    def test_negative_pin_width_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'width mismatch'):
            xu.analyze('module xu_soc_ppa_top(a,y);input a;output[1:0]y;VEC v(.A(a),.Z(y));endmodule', [LIBRARY])

    def test_negative_unknown_type_and_pin(self):
        with self.assertRaisesRegex(ValueError, 'unknown module/cell'):
            xu.analyze('module xu_soc_ppa_top(a,y);input a;output y;MYSTERY v(.A(a),.Z(y));endmodule', [LIBRARY])
        with self.assertRaisesRegex(ValueError, 'unknown pin'):
            xu.analyze('module xu_soc_ppa_top(a,y);input a;output y;BUF v(.WRONG(a),.Z(y));endmodule', [LIBRARY])

    def test_negative_duplicate_pin_and_hierarchy(self):
        with self.assertRaisesRegex(ValueError, 'duplicate/trailing pin'):
            xu.analyze('module xu_soc_ppa_top(a,y);input a;output y;BUF v(.A(a),.A(a),.Z(y));endmodule', [LIBRARY])
        with self.assertRaisesRegex(ValueError, 'duplicate instance'):
            xu.analyze('module xu_soc_ppa_top(a,y);input a;output y;BUF v(.A(a),.Z(y));BUF v(.A(a),.Z(y));endmodule', [LIBRARY])

    def test_negative_select_bounds_direction_and_undeclared(self):
        for values in (['a', '[', '4', ']'], ['a', '[', '0', ':', '3', ']'], ['missing']):
            with self.assertRaises(ValueError):
                xu.expression(values, {'a': (3, 0)})

    def test_identity_detects_content_mutation_and_read_only_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'source.v'; file.write_bytes(b'original')
            first = xu.identity(file)
            self.assertEqual(first['sha256'], hashlib.sha256(b'original').hexdigest())
            self.assertEqual(file.read_bytes(), b'original')
            file.write_bytes(b'modified')
            self.assertNotEqual(first, xu.identity(file))

    def test_python36_grammar_and_no_subprocess_or_simulator_api(self):
        source = (HERE / 'xu_mapped_connectivity123.py').read_text()
        ast.parse(source, feature_version=(3, 6))
        self.assertNotIn('import subprocess', source)
        self.assertNotIn('vpi_put_value', source)
        self.assertNotIn('vpi_control', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
