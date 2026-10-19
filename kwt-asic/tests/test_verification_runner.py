"""Regression guards against reporting an incomplete or failed simulator as PASS."""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("migration_checks", Path(__file__).resolve().parents[1] / "scripts/verify/run_checks.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class CompletionEvidenceTests(unittest.TestCase):
    def test_clean_finish_without_completion_marker_is_failure(self):
        self.assertIsNotNone(RUNNER.completion_error({"exit_code": 0}, "$finish", [r"^PASS ALL$"]))

    def test_partial_scenario_marker_is_failure(self):
        self.assertIsNotNone(RUNNER.completion_error({"exit_code": 0}, "PASS PARTIAL", [r"^PASS ALL$"]))

    def test_pass_marker_cannot_hide_nonzero_exit(self):
        self.assertIsNotNone(RUNNER.completion_error({"exit_code": 1}, "PASS ALL", [r"^PASS ALL$"]))

    def test_pass_marker_cannot_hide_timeout(self):
        self.assertIsNotNone(RUNNER.completion_error({"exit_code": 0, "timed_out": True}, "PASS ALL", [r"^PASS ALL$"]))

    def test_pass_marker_cannot_hide_failure_diagnostic(self):
        self.assertIsNotNone(RUNNER.completion_error({"exit_code": 0}, "PASS ALL\nFATAL: watchdog", [r"^PASS ALL$"]))

    def test_complete_success_is_accepted(self):
        self.assertIsNone(RUNNER.completion_error({"exit_code": 0}, "PASS ALL\n- test.sv: $finish", [r"^PASS ALL$"]))

    def test_group_does_not_pass_if_another_scenario_is_blocked(self):
        self.assertEqual(RUNNER.aggregate([{"status": "PASS"}, {"status": "BLOCKED"}]), "BLOCKED")


if __name__ == "__main__":
    unittest.main()
