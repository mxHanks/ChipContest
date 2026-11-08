"""Verify real SRAM and register ablation capability/clear behavior through ICB.

Generate both LinearAutoGroupCore variants from the same Scala snapshot first.
Set XU_BIAS_REGISTER_RTL_DIR to generated/LinearAutoGroupCoreRegisters; optionally
set XU_BIAS_SRAM_RTL_DIR to generated/LinearAutoGroupCore. No mock core is used.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest


class XuBiasCapabilityWrapperTests(unittest.TestCase):
    def test_elaborated_capability_and_clear_supported_or_completed_error(self):
        simulator = os.environ.get("XU_BIAS_CAPABILITY_SIM", "iverilog")
        self.assertIn(simulator, ("iverilog", "vcs"))
        for tool in (("iverilog", "vvp") if simulator == "iverilog" else ("vcs",)):
            self.assertIsNotNone(shutil.which(tool), "Required native tool is unavailable: " + tool)
        root = Path(__file__).resolve().parents[2]
        perips = root / "third-party/e203_hbirdv2/rtl/e203/perips"
        registers = os.environ.get("XU_BIAS_REGISTER_RTL_DIR")
        self.assertIsNotNone(registers, "Set XU_BIAS_REGISTER_RTL_DIR to the real generated register variant")
        variants = [(True, Path(os.environ.get("XU_BIAS_SRAM_RTL_DIR", str(perips)))),
                    (False, Path(registers))]
        log_directory = os.environ.get("XU_BIAS_CAPABILITY_LOG_DIR")
        for sram, rtl in variants:
            with self.subTest(sram=sram):
                self.assertTrue(rtl.is_dir(), "Generated RTL directory does not exist: " + str(rtl))
                self.assertTrue((rtl / "LinearAutoGroupCore.sv").is_file())
                core = (rtl / "LinearAutoGroupCore.sv").read_text()
                self.assertRegex(core, r"\bio_biasSramCapability\b",
                                 "Regenerate RTL from the capability-aware Scala source")
                inputs = [root / "tests/e203/tb_xu_bias_capability_wrapper.sv",
                          *sorted(rtl.glob("*.sv")), perips / "accel_icb_slave.v"]
                modules = {}
                for source in inputs:
                    for module in re.findall(r"(?m)^\s*module\s+(\w+)\b", source.read_text()):
                        self.assertNotIn(module, modules, "Duplicate generated module: " + module)
                        modules[module] = str(source)
                pins = {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}

                def save(name, content):
                    if log_directory:
                        destination = Path(log_directory) / ("sram" if sram else "registers")
                        destination.mkdir(parents=True, exist_ok=True)
                        (destination / name).write_text(content)

                save("inputs.json", json.dumps(pins, indent=2, sort_keys=True) + "\n")
                with tempfile.TemporaryDirectory(prefix="xu-bias-capability-") as temporary:
                    binary = Path(temporary) / ("wrapper.vvp" if simulator == "iverilog" else "simv")
                    define = "XU_EXPECT_BIAS_SRAM=" + str(int(sram))
                    if simulator == "vcs":
                        compile_command = ["vcs", "-full64", "-sverilog", "-timescale=1ns/1ps",
                                           "-top", "tb_xu_bias_capability_wrapper", "+define+" + define,
                                           "-Mdir=" + str(Path(temporary) / "csrc"), "-o", str(binary)]
                        simulate_command = [str(binary)]
                    else:
                        compile_command = ["iverilog", "-g2012", "-s", "tb_xu_bias_capability_wrapper",
                                           "-D" + define, "-o", str(binary)]
                        simulate_command = ["vvp", str(binary)]
                    built = subprocess.run([*compile_command, *map(str, inputs)], cwd=temporary,
                                           universal_newlines=True, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, timeout=180)
                    save("compile.log", built.stdout + built.stderr)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    result = subprocess.run(simulate_command, cwd=temporary, universal_newlines=True,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                    output = result.stdout + result.stderr
                    save("simulation.log", output)
                    self.assertEqual(result.returncode, 0, output)
                    marker = ("XU_BIAS_CAPABILITY_WRAPPER_PASS sram=%d capability=%s clear_commands=%d " %
                              (sram, "42530001" if sram else "00000000", sram))
                    self.assertEqual(output.count(marker), 1, output)
                    self.assertNotRegex(output, re.compile(r"\b(?:FATAL|FAIL(?:ED|URE)?)\b", re.IGNORECASE))
                self.assertEqual(pins, {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in pins},
                                 "Input RTL/testbench changed during native replay")


if __name__ == "__main__":
    unittest.main()
