"""Runner qualification only; actual HDL is exercised by the native entry."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('sram_update_reset_subject', ROOT/'scripts/verify/run_sram_update_reset.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class SRAMUpdateResetTests(unittest.TestCase):
    def case(self, bank=0, depth=128, width=16, backend=3):
        return dict(name='parser-fixture', bank=bank, depth=depth, width=width, backend=backend)

    def command(self, **changes):
        return dict({'status': 'EXITED', 'exit_code': 0, 'timed_out': False, 'interrupted': False}, **changes)

    def marker(self, case):
        return (f'PASS KWT_SRAM_UPDATE_RESET backend={case["backend"]} bank={case["bank"]} '
                f'width={case["width"]} depth={case["depth"]} '+
                ' '.join(f'{key}={value}' for key, value in M.expected_counts(case).items())+
                ' signature=0123456789abcdef\n')

    def test_plan_covers_legal_primitives_and_all_actual_bank_shapes(self):
        expected = {(0, 16, 128), (0, 16, 1024), (0, 16, 4096), (1, 16, 3136),
                    (1, 16, 3200), (1, 16, 2048), (1, 40, 32), (1, 41, 512)}
        plan = M.shape_plan()
        self.assertEqual(len(plan), 8)
        self.assertEqual({(c['bank'], c['width'], c['depth']) for c in plan}, expected)
        self.assertEqual(len({c['name'] for c in plan}), 8)

    def test_counts_are_hand_checked_for_real_boundary_sets(self):
        # 2 probe addresses for units/bias32, 4 for W2048, 8 for X/result.
        self.assertEqual(list(M.expected_counts(self.case()).values()), [4, 8, 4, 5, 4])
        self.assertEqual(list(M.expected_counts(self.case(bank=1, depth=2048)).values()), [8, 14, 8, 7, 4])
        self.assertEqual(list(M.expected_counts(self.case(bank=1, depth=3200)).values()), [16, 26, 16, 11, 4])
        self.assertEqual(list(M.expected_counts(self.case(bank=1, depth=32, width=40)).values()), [4, 8, 4, 5, 4])
        self.assertEqual(sum(sum(M.expected_counts(c).values()) for c in M.shape_plan()), 360)

    def test_precise_completion_accepts_all_three_backends(self):
        for shape in M.shape_plan():
            for backend in (0, 2, 3):
                case = dict(shape, backend=backend)
                with self.subTest(case=case):
                    result = M.accept_case(case, self.command(), self.marker(case)+'file.sv:120: $finish called\n')
                    self.assertEqual(result['status'], 'PASS')
                    self.assertEqual(result['signature'], '0123456789abcdef')

    def test_native_exit_flags_and_missing_fields_are_mandatory(self):
        case = self.case(); marker = self.marker(case)
        bad = [self.command(exit_code=1), self.command(exit_code=-11), self.command(exit_code=False),
               self.command(status='RUNNING'), self.command(timed_out=True), self.command(interrupted=True),
               self.command(timed_out=0), self.command(interrupted=None)]
        for key in ('status', 'exit_code', 'timed_out', 'interrupted'):
            item = self.command(); del item[key]; bad.append(item)
        for command in bad:
            with self.subTest(command=command), self.assertRaises(ValueError):
                M.accept_case(case, command, marker)

    def test_rejects_wrong_geometry_signature_and_each_counter(self):
        case = self.case(); marker = self.marker(case)
        bad = ['', marker+marker, 'INFO '+marker, marker.rstrip()+' extra\n',
               marker.replace('backend=3', 'backend=0'), marker.replace('bank=0', 'bank=1'),
               marker.replace('width=16', 'width=40'), marker.replace('depth=128', 'depth=1024'),
               marker.replace('0123456789abcdef', '0123456789abcde'),
               marker.replace('0123456789abcdef', '0123456789abcdeg')]
        for key, value in M.expected_counts(case).items():
            bad.append(marker.replace(f'{key}={value}', f'{key}={value+1}'))
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ValueError):
                M.accept_case(case, self.command(), text)

    def test_positive_marker_never_masks_failure_diagnostics(self):
        case = self.case()
        for diagnostic in ('FATAL: fixture.sv:12: mismatch', 'ERROR: bad data', 'FAIL coverage',
                           '%Error runtime', 'Aborting simulation', 'Assertion failed: invalid'):
            with self.subTest(diagnostic=diagnostic), self.assertRaises(ValueError):
                M.accept_case(case, self.command(), self.marker(case)+diagnostic+'\n')

    def test_reset_mutations_only_change_selected_official_branch_pin(self):
        original = (ROOT/'src/rtl/memory/kwt_sram_1rw.sv').read_text()
        begin = original.index('end else if (BACKEND == 3)')
        end = original.index('end else begin : g_bad_backend', begin)
        for fault, token in (('reset-write-leak', '.wr_en(wr_en)'), ('reset-read-leak', '.rd_en(rd_en)')):
            actual = M.mutate_primitive(original, fault)
            self.assertEqual(actual[:begin], original[:begin])
            self.assertEqual(actual[actual.index('end else begin : g_bad_backend', begin):], original[end:])
            self.assertIn(token, actual[begin:actual.index('end else begin : g_bad_backend', begin)])
        self.assertEqual((ROOT/'src/rtl/memory/kwt_sram_1rw.sv').read_text(), original)

    def test_fault_injection_rejects_unknown_or_ambiguous_sources(self):
        original = (ROOT/'src/rtl/memory/kwt_sram_1rw.sv').read_text()
        for source, fault in ((original, 'unknown'), (original+original, 'overwrite-dropped'), ('', 'overwrite-dropped')):
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                M.mutate_primitive(source, fault)


if __name__ == '__main__': unittest.main()
