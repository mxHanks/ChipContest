"""Check two-slot autonomous rows against the real xu wrapper and SRAM RTL."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest


class XuAutoGroupWrapperTests(unittest.TestCase):
    def test_real_fifo_all_groups_numeric_lanes_and_retirement_backpressure(self):
        if not shutil.which('iverilog') or not shutil.which('vvp'):
            self.skipTest('iverilog and vvp are required for direct stream wrapper simulation')
        root = Path(__file__).resolve().parents[2]
        perips = root / 'third-party/e203_hbirdv2/rtl/e203/perips'
        sources = ['BiasSramPrefetch.sv', 'BiasBankCache.sv', 'LinearAutoGroupCore.sv', 'LinearCachedCore.sv', 'LinearComputeCore.sv',
                   'DotProductEngine.sv', 'MacController.sv', 'MacPEArray.sv',
                   'MacPE.sv', 'XRowBuffer.sv', 'WeightBankArray.sv',
                   'WeightBank.sv', 'Sram1024x16.sv', 'mem_1024x16.sv',
                   'accel_icb_slave.v']
        log_directory = os.environ.get('XU_AUTOGROUP_WRAPPER_LOG_DIR')

        def save_log(name, output):
            if log_directory:
                destination = Path(log_directory)
                destination.mkdir(parents=True, exist_ok=True)
                (destination / name).write_text(output)

        with tempfile.TemporaryDirectory(prefix='xu-autogroup-wrapper-') as temporary:
            binary = Path(temporary) / 'wrapper.vvp'
            built = subprocess.run(
                ['iverilog', '-g2012', '-s', 'tb_xu_autogroup_wrapper', '-o', str(binary),
                 str(root / 'tests/e203/tb_xu_autogroup_wrapper.sv'),
                 *[str(perips / name) for name in sources]],
                cwd=temporary, universal_newlines=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=180)
            save_log('compile.log', built.stdout + built.stderr)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run(['vvp', str(binary)], cwd=temporary,
                                    universal_newlines=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=60)
            save_log('simulation.log', result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('XU_AUTOGROUP_WRAPPER_PASS', result.stdout)
            self.assertNotRegex(result.stdout + result.stderr,
                                re.compile(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', re.IGNORECASE))


if __name__ == '__main__':
    unittest.main()
