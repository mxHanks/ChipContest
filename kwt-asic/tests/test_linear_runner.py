"""Protect the new linear regression's complete-task/coverage acceptance gate."""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("linear_runner", Path(__file__).resolve().parents[1] / "scripts/verify/run_linear.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def complete_log(tasks=2):
    return "\n".join([f"PASS KWT_LINEAR_TASK task={t} outputs=25344 core_cycles=235000" for t in range(tasks)] +
                     [f"PASS KWT_LINEAR_SUITE tasks={tasks} outputs={tasks*25344} resets=1 illegal=3 input_bubbles=200 stalls=200 stable=200 busy_load_rejections=470000 full_window_cycles=520000"])


class LinearCompletionTests(unittest.TestCase):
    def test_full_evidence_is_accepted(self):
        error, coverage = RUNNER.check_completion({"exit_code": 0}, complete_log(), 2)
        self.assertIsNone(error)
        self.assertEqual(coverage["outputs"], 50688)

    def test_suite_without_every_task_cannot_pass(self):
        log = complete_log().split("\n", 1)[1]
        self.assertIsNotNone(RUNNER.check_completion({"exit_code": 0}, log, 2)[0])

    def test_duplicate_task_cannot_pass(self):
        log = complete_log().replace("task=1", "task=0")
        self.assertIsNotNone(RUNNER.check_completion({"exit_code": 0}, log, 2)[0])

    def test_wrong_output_count_cannot_pass(self):
        self.assertIsNotNone(RUNNER.check_completion({"exit_code": 0}, complete_log().replace("outputs=50688", "outputs=50687"), 2)[0])

    def test_absent_stall_coverage_cannot_pass(self):
        self.assertIsNotNone(RUNNER.check_completion({"exit_code": 0}, complete_log().replace("stable=200", "stable=0"), 2)[0])

    def test_success_line_followed_by_fatal_cannot_pass(self):
        self.assertIsNotNone(RUNNER.check_completion({"exit_code": 0}, complete_log()+"\nFATAL: late failure", 2)[0])

    def test_timeout_cannot_pass(self):
        self.assertIsNotNone(RUNNER.check_completion({"exit_code": 0, "timed_out": True}, complete_log(), 2)[0])

    def test_vectors_are_deterministic_and_task_specific(self):
        first = RUNNER.generate_case(0, 77)
        self.assertEqual(first, RUNNER.generate_case(0, 77))
        self.assertNotEqual(first, RUNNER.generate_case(6, 77))
        self.assertEqual(len(first[0]), 99)
        self.assertEqual(len(first[1]), 64)
        self.assertEqual(len(first[1][0]), 256)
        self.assertEqual(first[2][0], -(1 << 39))

    def test_cancellation_has_nonzero_opposite_products(self):
        x, w, bias, category = RUNNER.generate_case(5, 77)
        self.assertEqual(category, "cancellation")
        for r in (0, 1, 98):
            for c in (0, 127, 255):
                products = [x[r][k] * w[k][c] for k in range(64)]
                self.assertTrue(any(value > 0 for value in products))
                self.assertTrue(any(value < 0 for value in products))
                self.assertEqual(sum(products), 0)
                self.assertEqual(bias[c] + sum(products), bias[c])


if __name__ == "__main__":
    unittest.main()
