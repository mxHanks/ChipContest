"""Real generated SRAM scheduler: lookahead ownership and exact MAC values.

The optional baseline top uses the same dependencies/testbench and original
public ports. It proves the observed inter-launch improvement without mocking
producer completion or forcing any internal storage.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest


class BiasDemandScheduleTests(unittest.TestCase):
    def test_real_scheduler_demand_take_backpressure_reset_and_manual(self):
        root = Path(__file__).resolve().parents[2]
        perips = root / "third-party/e203_hbirdv2/rtl/e203/perips"
        log_directory = os.environ.get("XU_BIAS_DEMAND_LOG_DIR")
        if log_directory:
            logs = Path(log_directory)
        else:
            temporary_logs = tempfile.TemporaryDirectory(prefix="bias-demand-logs-")
            self.addCleanup(temporary_logs.cleanup)
            logs = Path(temporary_logs.name)
        logs.mkdir(parents=True, exist_ok=True)
        deps = ["BiasSramPrefetch.sv", "LinearComputeCore.sv", "DotProductEngine.sv",
                "MacController.sv", "MacPEArray.sv", "MacPE.sv", "XRowBuffer.sv",
                "WeightBankArray.sv", "WeightBank.sv", "Sram1024x16.sv", "mem_1024x16.sv"]
        baseline = os.environ.get("XU_BIAS_DEMAND_BASELINE_RTL")
        variants = [("candidate", perips / "LinearAutoGroupCore.sv", 0)]
        if baseline:
            self.assertEqual(hashlib.sha256(Path(baseline).read_bytes()).hexdigest(),
                             "ebc9c411a6318000369f6c466381767a469bb9d33454e4c955df713c728f9ab4",
                             "baseline must be the frozen pre-lookahead generated RTL")
            variants.append(("baseline", Path(baseline), 1))
        summaries = {}
        commands = []
        def run(argv, name, cwd):
            result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=180)
            commands.append({"name": name, "argv": argv, "cwd": str(cwd), "returncode": result.returncode})
            output = result.stdout + result.stderr
            (logs / (name + ".log")).write_text(output)
            (logs / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
            self.assertEqual(result.returncode, 0, output)
            return output
        with tempfile.TemporaryDirectory(prefix="bias-demand-schedule-") as temporary:
            for name, top, old in variants:
                binary = Path(temporary) / (name + ".vvp")
                run(["iverilog", "-g2012", "-s", "tb_bias_demand_schedule", "-o", str(binary),
                     str(root / "tests/e203/tb_bias_demand_schedule.sv"), str(top),
                     *[str(perips / x) for x in deps]], name + "-compile", temporary)
                output = run(["vvp", str(binary), "+BASELINE=" + str(old)], name + "-simulation", temporary)
                self.assertIn("BIAS_DEMAND_SCHEDULE_PASS rows=7 groups=224 resets=3 manual=1 baseline=" + str(old), output)
                rows = [dict((key, int(value)) for key, value in re.findall(r"(\w+)=(\d+)", line))
                        for line in output.splitlines() if line.startswith("BIAS_DEMAND_ROW ")]
                self.assertEqual(len(rows), 7)
                continuous = [row for row in rows if row["scenario"] == 1]
                self.assertEqual(len(continuous), 6)
                for row in continuous:
                    self.assertEqual(row["min_interval"], row["max_interval"])
                summaries[name] = {"rows": rows, "top_sha256": hashlib.sha256(top.read_bytes()).hexdigest()}
            if baseline:
                base = summaries["baseline"]["rows"][0]["min_interval"]
                cand = summaries["candidate"]["rows"][0]["min_interval"]
                self.assertEqual(base, 69, "original scheduler accepts next demand after enqueue")
                self.assertEqual(cand, 68, "lookahead permits launch immediately after enqueue")
                self.assertEqual(base - cand, 1, "lookahead must remove the actual one-edge demand handshake gap")
                summaries["launch_interval_delta"] = cand - base
        (logs / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
