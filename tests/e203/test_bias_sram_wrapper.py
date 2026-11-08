"""Exercise the generated S3 bias SRAM through its real asynchronous ICB wrapper."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest


class XuBiasSramWrapperTests(unittest.TestCase):
    def test_masks_async_snapshots_retirement_clear_reset_and_runtime_protection(self):
        simulator = os.environ.get("XU_BIAS_WRAPPER_SIM", "iverilog")
        self.assertIn(simulator, ("iverilog", "vcs"), "unknown XU_BIAS_WRAPPER_SIM")
        if simulator == "iverilog" and (not shutil.which("iverilog") or not shutil.which("vvp")):
            self.skipTest("iverilog and vvp are required for real wrapper simulation")
        if simulator == "vcs":
            self.assertIsNotNone(shutil.which("vcs"), "XU_BIAS_WRAPPER_SIM=vcs requires vcs")
        root = Path(__file__).resolve().parents[2]
        perips = root / "third-party/e203_hbirdv2/rtl/e203/perips"
        self.assertTrue((perips / "BiasSramPrefetch.sv").is_file(),
                        "Install the generated S3 bias SRAM core before running this test")
        # All generated SV dependencies include any specialized SRAM wrapper
        # emitted by CIRCT. Ordinary peripheral .v files are unrelated to this
        # top; only the actual ICB accelerator wrapper is needed from that set.
        inputs = [root / "tests/e203/tb_xu_bias_sram_wrapper.sv",
                  *sorted(perips.glob("*.sv")), perips / "accel_icb_slave.v"]
        modules = {}
        for source in inputs:
            for module in re.findall(r"(?m)^\s*module\s+(\w+)\b", source.read_text()):
                self.assertNotIn(module, modules,
                                 "Duplicate module %s in %s and %s" % (module, modules.get(module), source))
                modules[module] = str(source)
        log_directory = os.environ.get("XU_BIAS_WRAPPER_LOG_DIR")

        def save(name, content):
            if log_directory:
                directory = Path(log_directory)
                directory.mkdir(parents=True, exist_ok=True)
                (directory / name).write_text(content)

        save("inputs.json", json.dumps({str(path.relative_to(root)):
                                        hashlib.sha256(path.read_bytes()).hexdigest()
                                        for path in inputs}, indent=2, sort_keys=True) + "\n")
        with tempfile.TemporaryDirectory(prefix="xu-bias-sram-wrapper-") as temporary:
            binary = Path(temporary) / ("wrapper.vvp" if simulator == "iverilog" else "simv")
            if simulator == "vcs":
                compile_command = ["vcs", "-full64", "-sverilog", "-timescale=1ns/1ps",
                                   "-top", "tb_xu_bias_sram_wrapper",
                                   "-Mdir=" + str(Path(temporary) / "csrc"), "-o", str(binary)]
                simulate_command = [str(binary)]
            else:
                compile_command = ["iverilog", "-g2012", "-s", "tb_xu_bias_sram_wrapper",
                                   "-o", str(binary)]
                simulate_command = ["vvp", str(binary)]
            built = subprocess.run([*compile_command, *map(str, inputs)], cwd=temporary,
                                   universal_newlines=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=180)
            save("compile.log", built.stdout + built.stderr)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run(simulate_command, cwd=temporary, universal_newlines=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
            output = result.stdout + result.stderr
            save("simulation.log", output)
            self.assertEqual(result.returncode, 0, output)
            for marker in ("XU_BIAS_READ_OVERLAP_PASS", "XU_BIAS_WRITE_OVERLAP_PASS",
                           "XU_BIAS_RESET_RETAINS_PASS items=256",
                           "XU_BIAS_RUNTIME_REJECT_PASS operations=5"):
                self.assertIn(marker, output)
            self.assertRegex(output, r"XU_BIAS_CLEAR_PASS cycles=(?:7[6-9][0-9]|[89][0-9]{2}|1000)")
            self.assertRegex(output, r"XU_BIAS_SRAM_WRAPPER_PASS masks=8192 items=256 "
                                    r"read_words=[1-9][0-9]* accepted=[1-9][0-9]* "
                                    r"retired=[1-9][0-9]* core_commands=[1-9][0-9]* "
                                    r"overlaps=[3-9][0-9]* clear_cycles=[1-9][0-9]*")
            self.assertNotRegex(output, re.compile(r"\b(?:FATAL|FAIL(?:ED|URE)?)\b", re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
