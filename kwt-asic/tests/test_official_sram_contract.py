"""Pure Python qualification of planning and native-result acceptance.

The log strings below are synthetic parser fixtures. They do not compile an
adapter, exercise an SRAM model, or establish any official functional result.
"""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'scripts/verify/run_official_sram_contract.py'
UNIT_TOP = 'tb_kwt_sram_1rw'
BANK_TOP = 'tb_kwt_sram_bank'
POSITIVE_PLAN = {
    'unit-w16-d128': (UNIT_TOP, 16, 128),
    'unit-w16-d1024': (UNIT_TOP, 16, 1024),
    'unit-w16-d4096': (UNIT_TOP, 16, 4096),
    'bank-w16-d3136': (BANK_TOP, 16, 3136),
    'bank-w16-d3200': (BANK_TOP, 16, 3200),
    'bank-w16-d2048': (BANK_TOP, 16, 2048),
    'bank-w40-d32': (BANK_TOP, 40, 32),
    'bank-w41-d512': (BANK_TOP, 41, 512),
}
UNIT_DIAGNOSTICS = {
    1: {'KWT_SRAM_SINGLE_PORT_CONFLICT'},
    2: {'KWT_SRAM_SINGLE_PORT_CONFLICT'},
    3: {'KWT_SRAM_UNINITIALIZED_READ'},
    6: {'KWT_SRAM_UNKNOWN_ENABLE'},
    7: {'KWT_SRAM_READ_ADDRESS_INVALID'},
    8: {'KWT_SRAM_UNKNOWN_WRITE_DATA'},
    9: {'KWT_SRAM_WRITE_ADDRESS_INVALID'},
}
BANK_DIAGNOSTICS = {
    1: {'KWT_SRAM_BANK_UNKNOWN_ENABLE'},
    2: {'KWT_SRAM_BANK_UNKNOWN_ENABLE'},
    3: {'KWT_SRAM_BANK_UNKNOWN_ENABLE'},
    4: {'KWT_SRAM_BANK_UNKNOWN_ENABLE'},
    5: {'KWT_SRAM_BANK simultaneous read/write forbidden'},
    6: {'KWT_SRAM_BANK address out of logical range'},
    7: {'KWT_SRAM_BANK address out of logical range'},
    8: {'KWT_SRAM_BANK unknown address', 'KWT_SRAM_UNKNOWN_ENABLE'},
}


class OfficialSRAMContractTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), 'official contract runner is not implemented')
        name = 'official_sram_contract_test_subject'
        spec = importlib.util.spec_from_file_location(name, MODULE)
        self.subject = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {name: self.subject}):
            spec.loader.exec_module(self.subject)
        self.positives = self.subject.positive_cases()
        self.negatives = self.subject.negative_cases()

    @staticmethod
    def command(exit_code=0, **changes):
        result = {
            'status': 'EXITED', 'exit_code': exit_code,
            'timed_out': False, 'interrupted': False,
        }
        result.update(changes)
        return result

    def positive(self, name):
        return next(case for case in self.positives if case['name'] == name)

    @staticmethod
    def positive_log(case):
        width, depth = case['width'], case['depth']
        if case['top'] == UNIT_TOP:
            return (
                f'PASS KWT_SRAM_UNIT width={width} depth={depth} '
                f'checks={depth + 16} signature=0123456789abcdef\n'
            )
        return (
            f'PASS KWT_SRAM_BANK_WIDTH_COVERAGE width={width} bits_both={width}\n'
            f'PASS KWT_SRAM_BANK backend=3 width={width} depth={depth} '
            f'checks={2 * depth + 5}\n'
        )

    @staticmethod
    def fatal_log(diagnostic):
        return f'FATAL: fixture.sv:42: {diagnostic}\n       Time: 35000 Scope: fixture.dut\n'

    def assert_rejected(self, case, command, text, negative=False):
        try:
            result = self.subject.accept_case(copy.deepcopy(case), command, text, negative=negative)
        except ValueError:
            return
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('status'), 'FAIL', result)

    def test_positive_plan_is_only_three_legal_primitives_and_five_actual_banks(self):
        self.assertIsInstance(self.positives, list)
        self.assertEqual(len(self.positives), 8)
        self.assertEqual(len({case['name'] for case in self.positives}), 8)
        actual = {case['name']: (case['top'], case['width'], case['depth'])
                  for case in self.positives}
        self.assertEqual(actual, POSITIVE_PLAN)

    def test_negative_plan_uses_unit128_and_non_power_two_bank3200(self):
        self.assertIsInstance(self.negatives, list)
        self.assertEqual(len(self.negatives), 15)
        self.assertEqual(len({case['name'] for case in self.negatives}), 15)
        expected = {('unit-w16-d128', number) for number in UNIT_DIAGNOSTICS}
        expected |= {('bank-w16-d3200', number) for number in BANK_DIAGNOSTICS}
        self.assertEqual({(case['binary_name'], case['error_case']) for case in self.negatives}, expected)
        for case in self.negatives:
            with self.subTest(case=case['name']):
                self.assertIsInstance(case['name'], str)
                self.assertTrue(case['name'])
                self.assertIsInstance(case['diagnostics'], list)
                self.assertTrue(case['diagnostics'])
                self.assertTrue(all(isinstance(value, str) and value for value in case['diagnostics']))
                self.assertEqual(len(case['diagnostics']), len(set(case['diagnostics'])))
                permitted = (UNIT_DIAGNOSTICS if case['binary_name'] == 'unit-w16-d128'
                             else BANK_DIAGNOSTICS)[case['error_case']]
                self.assertLessEqual(set(case['diagnostics']), permitted)
        # Unit ERROR_CASE 4/5 cast DEPTH to its power-of-two address width and
        # therefore wrap to zero. Only the non-power-two bank may test ranges.
        self.assertFalse(any(case['binary_name'] == 'unit-w16-d128' and
                             case['error_case'] in (4, 5) for case in self.negatives))

    def test_all_positive_cases_accept_exact_geometry_and_check_count(self):
        for case in self.positives:
            with self.subTest(case=case['name']):
                result = self.subject.accept_case(case, self.command(), self.positive_log(case))
                self.assertIsInstance(result, dict)
                self.assertEqual(result.get('status'), 'PASS')
                if 'checks' in result:
                    expected = case['depth'] + 16 if case['top'] == UNIT_TOP else 2 * case['depth'] + 5
                    self.assertEqual(result['checks'], expected)

    def test_unit_rejects_missing_duplicate_contaminated_or_malformed_marker(self):
        case = self.positive('unit-w16-d128')
        good = self.positive_log(case)
        other = self.positive_log(self.positive('unit-w16-d1024'))
        bad_logs = [
            '', good + good, good + other,
            good.replace('width=16', 'width=40'),
            good.replace('depth=128', 'depth=1024'),
            good.replace('checks=144', 'checks=143'),
            good.replace('0123456789abcdef', '0123456789abcde'),
            good.replace('0123456789abcdef', '0123456789abcdeg'),
            'INFO ' + good, good.rstrip() + ' extra\n',
        ]
        for index, text in enumerate(bad_logs):
            with self.subTest(log=index):
                self.assert_rejected(case, self.command(), text)

    def test_bank_rejects_bad_backend_geometry_count_or_width_coverage(self):
        case = self.positive('bank-w41-d512')
        good = self.positive_log(case)
        coverage, completion = good.splitlines(keepends=True)
        bad_logs = [
            '', coverage, completion, good + completion, good + coverage,
            good + coverage.replace('bits_both=41', 'bits_both=40'),
            good.replace('backend=3', 'backend=0'),
            good.replace('width=41', 'width=40'),
            good.replace('depth=512', 'depth=3200'),
            good.replace('checks=1029', 'checks=1030'),
            good.replace('bits_both=41', 'bits_both=40'),
            coverage + 'INFO ' + completion,
            coverage + completion.rstrip() + ' extra\n',
        ]
        for index, text in enumerate(bad_logs):
            with self.subTest(log=index):
                self.assert_rejected(case, self.command(), text)

    def test_positive_requires_explicit_clean_native_zero_exit(self):
        case = self.positive('unit-w16-d128')
        commands = [
            self.command(1), self.command(137), self.command(-11), self.command(False),
            self.command(status='RUNNING'), self.command(status='FAILED'),
            self.command(timed_out=True), self.command(interrupted=True),
            self.command(timed_out=None), self.command(interrupted=None),
            self.command(timed_out=0), self.command(interrupted=0),
        ]
        for field in ('status', 'exit_code', 'timed_out', 'interrupted'):
            incomplete = self.command()
            del incomplete[field]
            commands.append(incomplete)
        for index, command in enumerate(commands):
            with self.subTest(command=index):
                self.assert_rejected(case, command, self.positive_log(case))

    def test_all_negatives_accept_only_designated_fatal_diagnostics(self):
        for case in self.negatives:
            for diagnostic in case['diagnostics']:
                with self.subTest(case=case['name'], diagnostic=diagnostic):
                    result = self.subject.accept_case(case, self.command(1),
                                                      self.fatal_log(diagnostic), negative=True)
                    self.assertIsInstance(result, dict)
                    self.assertEqual(result.get('status'), 'EXPECTED_REJECTION')

    def test_negative_requires_explicit_clean_native_fatal_exit_one(self):
        case = self.negatives[0]
        text = self.fatal_log(case['diagnostics'][0])
        commands = [
            self.command(0), self.command(2), self.command(137), self.command(-11), self.command(True),
            self.command(1, status='RUNNING'), self.command(1, status='SIGNALED'),
            self.command(1, timed_out=True), self.command(1, interrupted=True),
            self.command(1, timed_out=None), self.command(1, interrupted=None),
            self.command(1, timed_out=0), self.command(1, interrupted=0),
        ]
        for field in ('status', 'exit_code', 'timed_out', 'interrupted'):
            incomplete = self.command(1)
            del incomplete[field]
            commands.append(incomplete)
        for index, command in enumerate(commands):
            with self.subTest(command=index):
                self.assert_rejected(case, command, text, negative=True)

    def test_negative_rejects_wrong_reason_or_diagnostic_outside_fatal_line(self):
        case = next(case for case in self.negatives if case['binary_name'] == 'unit-w16-d128'
                    and case['error_case'] == 6)
        diagnostic = case['diagnostics'][0]
        bad_logs = [
            '', self.fatal_log('UNRELATED_NATIVE_ERROR'),
            f'INFO expected {diagnostic}\n',
            f'WARNING: {diagnostic}\n',
            self.fatal_log('UNRELATED_NATIVE_ERROR') + f'INFO expected {diagnostic}\n',
            self.fatal_log(diagnostic + '_EXTRA'),
        ]
        for index, text in enumerate(bad_logs):
            with self.subTest(log=index):
                self.assert_rejected(case, self.command(1), text, negative=True)

    def test_negative_rejects_fallthrough_sentinel_or_any_positive_marker(self):
        case = self.negatives[0]
        fatal = self.fatal_log(case['diagnostics'][0])
        contaminations = [
            'FATAL: fixture.sv:99: EXPECTED_DIAGNOSTIC_NOT_TRIGGERED\n',
            self.positive_log(self.positive('unit-w16-d128')),
            self.positive_log(self.positive('bank-w16-d3200')),
        ]
        for index, suffix in enumerate(contaminations):
            with self.subTest(log=index):
                self.assert_rejected(case, self.command(1), fatal + suffix, negative=True)


if __name__ == '__main__':
    unittest.main()
