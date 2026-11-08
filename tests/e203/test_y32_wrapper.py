"""Check Y32 RNE snapshots and FIFO ownership with the real xu wrapper/core RTL."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest


class XuY32WrapperTests(unittest.TestCase):
    def test_real_y32_numeric_legacy_ownership_and_illegal_domain_assertions(self):
        simulator = os.environ.get('XU_Y32_WRAPPER_SIM', 'iverilog')
        self.assertIn(simulator, ('iverilog', 'vcs'), 'unknown XU_Y32_WRAPPER_SIM')
        if simulator == 'iverilog' and (not shutil.which('iverilog') or not shutil.which('vvp')):
            self.skipTest('iverilog and vvp are required for direct wrapper simulation')
        if simulator == 'vcs':
            self.assertIsNotNone(shutil.which('vcs'), 'XU_Y32_WRAPPER_SIM=vcs requires vcs')
        root = Path(__file__).resolve().parents[2]
        perips = root / 'third-party/e203_hbirdv2/rtl/e203/perips'
        sources = ['BiasSramPrefetch.sv', 'BiasBankCache.sv', 'LinearAutoGroupCore.sv', 'LinearCachedCore.sv', 'LinearComputeCore.sv',
                   'DotProductEngine.sv', 'MacController.sv', 'MacPEArray.sv',
                   'MacPE.sv', 'XRowBuffer.sv', 'WeightBankArray.sv',
                   'WeightBank.sv', 'Sram1024x16.sv', 'mem_1024x16.sv',
                   'accel_icb_slave.v']
        log_directory = os.environ.get('XU_Y32_WRAPPER_LOG_DIR')

        def save_log(name, output):
            if log_directory:
                destination = Path(log_directory)
                destination.mkdir(parents=True, exist_ok=True)
                (destination / name).write_text(output)

        with tempfile.TemporaryDirectory(prefix='xu-y32-wrapper-') as temporary:
            binary = Path(temporary) / ('wrapper.vvp' if simulator == 'iverilog' else 'simv')
            inputs = [str(root / 'tests/e203/tb_xu_y32_wrapper.sv'),
                      *[str(perips / name) for name in sources]]
            if simulator == 'vcs':
                compile_command = ['vcs', '-full64', '-sverilog', '-timescale=1ns/1ps',
                                   '-top', 'tb_xu_y32_wrapper',
                                   '+define+DISABLE_SV_ASSERTION=1',
                                   '-Mdir=' + str(Path(temporary) / 'csrc'), '-o', str(binary),
                                   *inputs]
                simulate_command = [str(binary)]
            else:
                compile_command = ['iverilog', '-g2012', '-s', 'tb_xu_y32_wrapper',
                                   '-o', str(binary), *inputs]
                simulate_command = ['vvp', str(binary)]
            built = subprocess.run(compile_command, cwd=temporary,
                                   universal_newlines=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=180)
            save_log('compile.log', built.stdout + built.stderr)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run(simulate_command, cwd=temporary,
                                    universal_newlines=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=60)
            output = result.stdout + result.stderr
            save_log('simulation.log', output)
            self.assertEqual(result.returncode, 0, output)
            self.assertIn('XU_Y32_INTERFACE_DIAGNOSTIC_BEGIN legal_forced_fifo_patterns_not_mac_results', output)
            self.assertIn('XU_Y32_INTERFACE_DIAGNOSTIC_PASS', output)
            self.assertIn('XU_PAIRED_HI_INTERFACE_DIAGNOSTIC_PASS', output)
            self.assertRegex(output, r'XU_Y32_WRAPPER_PASS real_y32_reads=512 '
                                    r'positive_ties=[1-9][0-9]* negative_ties=[1-9][0-9]* '
                                    r'even_ties=[1-9][0-9]* odd_ties=[1-9][0-9]* '
                                    r'legal_min_seen=[1-9][0-9]* legal_max_seen=[1-9][0-9]* '
                                    r'y32_overlap=[1-9][0-9]*')
            self.assertRegex(output, r'real_rows=2 real_groups=64 real_lanes=512 real_paired_reads=256')
            self.assertNotRegex(output, re.compile(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', re.IGNORECASE))

            for plusarg, marker in [('Y32_BAD_HIGH', 'XU_Y32_RANGE_ERROR lane=0'),
                                    ('Y32_BAD_LOW', 'XU_Y32_RANGE_ERROR lane=0'),
                                    ('Y32_BAD_UNKNOWN', 'XU_Y32_UNKNOWN_ERROR lane=0')]:
                with self.subTest(illegal_input=plusarg):
                    rejected = subprocess.run([*simulate_command, '+' + plusarg], cwd=temporary,
                                              universal_newlines=True, stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE, timeout=60)
                    rejected_output = rejected.stdout + rejected.stderr
                    save_log(plusarg.lower() + '.log', rejected_output)
                    self.assertNotEqual(rejected.returncode, 0, rejected_output)
                    self.assertIn(marker, rejected_output)
                    self.assertNotIn('XU_Y32_WRAPPER_PASS', rejected_output)


if __name__ == '__main__':
    unittest.main()
