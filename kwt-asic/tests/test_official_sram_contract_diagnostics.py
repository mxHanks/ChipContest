"""Synthetic log tests: expected rejection must not hide another failure."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'scripts/verify/run_official_sram_contract.py'


class OfficialSRAMContractDiagnosticTests(unittest.TestCase):
    def setUp(self):
        name = 'official_sram_contract_diagnostics_test_subject'
        spec = importlib.util.spec_from_file_location(name, MODULE)
        self.subject = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {name: self.subject}):
            spec.loader.exec_module(self.subject)
        self.case = next(case for case in self.subject.negative_cases()
                         if case['binary_name'] == 'unit-w16-d128' and case['error_case'] == 1)
        self.command = {'status': 'EXITED', 'exit_code': 1,
                        'timed_out': False, 'interrupted': False}
        self.expected = 'FATAL: fixture.sv:42: KWT_SRAM_SINGLE_PORT_CONFLICT\n'

    def test_designated_fatal_alone_is_an_expected_rejection(self):
        result = self.subject.accept_case(self.case, self.command, self.expected, negative=True)
        self.assertEqual(result['status'], 'EXPECTED_REJECTION')

    def test_designated_fatal_does_not_mask_another_failure(self):
        extra_failures = (
            'ERROR: unrelated native problem\n',
            'FAIL unrelated checker\n',
            '%Error unrelated simulator problem\n',
            'FATAL: malformed unrelated failure\n',
            'runtime: Assertion failed: unrelated invariant\n',
            'Aborting simulation after unrelated failure\n',
        )
        for extra in extra_failures:
            for before in (False, True):
                with self.subTest(extra=extra.strip(), before=before):
                    text = extra + self.expected if before else self.expected + extra
                    try:
                        result = self.subject.accept_case(self.case, self.command, text, negative=True)
                    except ValueError:
                        continue
                    self.assertIsInstance(result, dict)
                    self.assertEqual(result.get('status'), 'FAIL', result)


if __name__ == '__main__':
    unittest.main()
