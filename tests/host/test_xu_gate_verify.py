"""Evidence rejection tests for synthesis replay, independent of costly EDA runs."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('xu_gate_verify', ROOT/'tools/scripts/xu_gate_verify.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class GateEvidenceTests(unittest.TestCase):
    def test_vcs_functional_replay_explicitly_disables_model_timing(self):
        with mock.patch.object(gate, 'tool', return_value='/verified/vcs'):
            compile_command, run_command = gate.simulation_commands(
                'vcs', Path('/new/output'), [], [], [])
        self.assertIn('+nospecify', compile_command)
        self.assertIn('+notimingcheck', compile_command)
        self.assertIn('+TRACE=/new/output/transactions.trace', run_command)

    def directory(self, root, trace=None, log=None):
        root.mkdir()
        if trace is None:
            trace = ''.join('{} 1 038 00000000 0 00000001\n'.format(index) for index in range(10000))
        (root/'transactions.trace').write_text(trace)
        (root/'simulation.log').write_text(log or 'XU_GATE_WRAPPER_PASS accepted=10002 retired=10002\n')
        return root

    def test_rejects_unknown_gate_response_even_with_pass_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = self.directory(Path(temporary)/'gate')
            text = (directory/'transactions.trace').read_text().replace('00000001', 'xxxx0001', 1)
            (directory/'transactions.trace').write_text(text)
            with self.assertRaisesRegex(ValueError, 'unknown'):
                gate.check_simulation(directory)

    def test_rejects_duplicate_pass_unretired_or_fatal_result(self):
        logs = ['XU_GATE_WRAPPER_PASS accepted=10002 retired=10001\n',
                'XU_GATE_WRAPPER_PASS accepted=10002 retired=10002\n'*2,
                'FATAL: numeric result differs\nXU_GATE_WRAPPER_PASS accepted=10002 retired=10002\n']
        with tempfile.TemporaryDirectory() as temporary:
            for index, log in enumerate(logs):
                with self.subTest(log=log):
                    directory = self.directory(Path(temporary)/str(index), log=log)
                    with self.assertRaises(ValueError):
                        gate.check_simulation(directory)

    def test_rejects_trace_missing_accepted_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = self.directory(Path(temporary)/'gate')
            lines = (directory/'transactions.trace').read_text().splitlines()
            (directory/'transactions.trace').write_text('\n'.join(lines[:-1])+'\n')
            with self.assertRaisesRegex(ValueError, 'accepted count'):
                gate.check_simulation(directory)

    def test_resolves_nested_vendor_model_includes_and_rejects_absent_dependency(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model, header = root/'cells.v', root/'truth.vh'
            model.write_text('`include "truth.vh"\nmodule cell; endmodule\n')
            header.write_text('`define CELL_TRUTH 1\n')
            self.assertEqual(gate.include_dependencies([model], []), {model, header})
            header.unlink()
            with self.assertRaisesRegex(ValueError, 'unresolved model include'):
                gate.include_dependencies([model], [])


if __name__ == '__main__':
    unittest.main()
