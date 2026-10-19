"""Protect optimization acceptance and comparisons against incomplete/false evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("engine_benchmark", Path(__file__).resolve().parents[1] / "scripts/verify/run_engine_benchmark.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def config(engine="opt", lanes=8, pipe_mul=1, stalls="none"):
    return {"engine": engine, "lanes": lanes, "pipe_mul": pipe_mul, "tasks": 2, "stalls": stalls, "seed": 77}


def complete_log(settings=None):
    settings = settings or config()
    metrics = RUNNER.expected_metrics(settings["engine"], settings["lanes"], settings["pipe_mul"])
    stalls = 123 if settings["stalls"] == "random" else 0
    cycles = metrics["core_cycles_without_stalls"] + stalls
    lines = [f"PASS ENGINE_BENCH_TASK task={task} outputs=25344 core_cycles={cycles} load_words=22976 load_cycles=23000 output_stalls={stalls} x_reads={metrics['x_reads']} w_reads={metrics['w_reads']} b_reads={metrics['b_reads']} window_cycles={23000+cycles+2}" for task in range(2)]
    lines.append(f"PASS ENGINE_BENCH_SUITE tasks=2 outputs=50688 resets=3 illegal=3 input_bubbles={int(stalls>0)*25} stalls={2*stalls} stable={2*stalls} busy_load_rejections=400000 full_window_cycles={2*(23000+cycles+10)}")
    return "\n".join(lines)


class EngineBenchmarkTests(unittest.TestCase):
    def accepted(self, log, settings=None, command=None):
        return RUNNER.check_completion(command or {"exit_code": 0}, log, settings or config())

    def test_complete_deterministic_evidence_passes(self):
        error, coverage = self.accepted(complete_log())
        self.assertIsNone(error)
        self.assertEqual(coverage["expected"]["core_cycles_without_stalls"], 234432)

    def test_complete_random_backpressure_evidence_passes(self):
        settings = config(stalls="random")
        self.assertIsNone(self.accepted(complete_log(settings), settings)[0])

    def test_baseline_and_pipeline_cycle_equations(self):
        for lanes in (8, 16):
            for engine, pipe in (("baseline", 0), ("opt", 0), ("opt", 1)):
                settings = config(engine, lanes, pipe)
                self.assertIsNone(self.accepted(complete_log(settings), settings)[0])
        self.assertEqual(RUNNER.expected_metrics("baseline", 8, 0)["core_cycles_without_stalls"], 231264)
        self.assertEqual(RUNNER.expected_metrics("opt", 16, 1)["core_cycles_without_stalls"], 129888)

    def test_missing_task_rejected(self):
        self.assertIsNotNone(self.accepted(complete_log().split("\n", 1)[1])[0])

    def test_duplicate_task_rejected(self):
        self.assertIsNotNone(self.accepted(complete_log().replace("task=1", "task=0"))[0])

    def test_wrong_output_count_rejected(self):
        self.assertIsNotNone(self.accepted(complete_log().replace("outputs=50688", "outputs=50687"))[0])

    def test_missing_tail_pipeline_reset_rejected(self):
        self.assertIsNotNone(self.accepted(complete_log().replace("resets=3", "resets=2"))[0])

    def test_read_enable_count_mismatch_rejected(self):
        self.assertIsNotNone(self.accepted(complete_log().replace("b_reads=25344", "b_reads=25343"))[0])

    def test_wrong_cycle_formula_rejected(self):
        self.assertIsNotNone(self.accepted(complete_log().replace("core_cycles=234432", "core_cycles=234431"))[0])

    def test_no_stall_benchmark_with_stalls_rejected(self):
        self.assertIsNotNone(self.accepted(complete_log().replace("output_stalls=0", "output_stalls=1"))[0])

    def test_incomplete_load_rejected(self):
        self.assertIsNotNone(self.accepted(complete_log().replace("load_words=22976", "load_words=22975"))[0])

    def test_missing_stable_output_checks_rejected(self):
        settings = config(stalls="random")
        self.assertIsNotNone(self.accepted(complete_log(settings).replace("stable=246", "stable=0"), settings)[0])

    def test_late_failure_and_timeout_rejected(self):
        self.assertIsNotNone(self.accepted(complete_log()+"\nFATAL: late failure")[0])
        self.assertIsNotNone(self.accepted(complete_log(), command={"exit_code": 0, "timed_out": True})[0])
        self.assertIsNotNone(self.accepted(complete_log(), command={"exit_code": 1})[0])

    def test_invalid_configs_rejected(self):
        for args in (("baseline", 8, 1), ("opt", 3, 1), ("opt", 8, 2), ("other", 8, 0)):
            with self.assertRaises(ValueError):
                RUNNER.expected_metrics(*args)

    def make_report(self, root, settings=None):
        settings = settings or config()
        log = root / "run.log"
        log.write_text(complete_log(settings))
        data = root / "x.mem"
        data.write_text("0000\n")
        command = {"exit_code": 0, "log": RUNNER.LINEAR.file_record(log)}
        error, coverage = RUNNER.check_completion(command, log.read_text(), settings)
        self.assertIsNone(error)
        record = RUNNER.LINEAR.file_record(data)
        report = {"schema": RUNNER.SCHEMA, "status": "PASS", "configuration": settings,
                  "inputs": [], "replayed_vectors": [record], "provenance": [], "commands": [command],
                  "rtl": {"status": "PASS", "coverage": coverage}, "simulator": "verilator",
                  "workload_sha256": RUNNER.vector_identity([record])}
        path = root / "result.json"
        path.write_text(json.dumps(report))
        return path, report

    def test_comparison_revalidates_log_and_inputs(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path, report = self.make_report(root)
            comparison = RUNNER.comparison_report([path])
            self.assertEqual(comparison["status"], "PASS")
            self.assertEqual(comparison["runs"][0]["relative_to_first_core_cycle_ratio"], 1.0)
            (root / "x.mem").write_text("0001\n")
            with self.assertRaisesRegex(ValueError, "changed"):
                RUNNER.comparison_report([path])

    def test_comparison_rejects_forged_coverage(self):
        with tempfile.TemporaryDirectory() as name:
            path, report = self.make_report(Path(name))
            report["rtl"]["coverage"]["per_task"][0]["core_cycles"] = 1
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "original complete"):
                RUNNER.comparison_report([path])

    def test_comparison_rejects_different_workload(self):
        with tempfile.TemporaryDirectory() as name:
            first, second = Path(name)/"a", Path(name)/"b"
            first.mkdir(); second.mkdir()
            path_a, report_a = self.make_report(first)
            path_b, report_b = self.make_report(second)
            (second/"x.mem").write_text("ffff\n")
            record = RUNNER.LINEAR.file_record(second/"x.mem")
            report_b["replayed_vectors"] = [record]
            report_b["workload_sha256"] = RUNNER.vector_identity([record])
            path_b.write_text(json.dumps(report_b))
            with self.assertRaisesRegex(ValueError, "identical word images"):
                RUNNER.comparison_report([path_a, path_b])

    def test_vector_identity_ignores_paths_but_not_content_order(self):
        records = [{"path": "first", "sha256": "a"}, {"path": "second", "sha256": "b"}]
        renamed = copy.deepcopy(records)
        renamed[0]["path"] = "elsewhere"
        self.assertEqual(RUNNER.vector_identity(records), RUNNER.vector_identity(renamed))
        self.assertNotEqual(RUNNER.vector_identity(records), RUNNER.vector_identity(records[::-1]))


if __name__ == "__main__":
    unittest.main()
