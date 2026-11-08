"""Exercise the actual xu Chisel RTL through its legacy/additive ICB wrapper."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest


class XuCachedWrapperTests(unittest.TestCase):
    def test_cache_masks_legacy_modes_result_window_and_backpressure(self):
        simulator = os.environ.get('XU_WRAPPER_SIM', 'iverilog')
        self.assertIn(simulator, ('iverilog', 'vcs'), 'unknown XU_WRAPPER_SIM')
        if simulator == 'iverilog' and (not shutil.which('iverilog') or not shutil.which('vvp')):
            self.skipTest('iverilog and vvp are required for direct wrapper simulation')
        if simulator == 'vcs':
            self.assertIsNotNone(shutil.which('vcs'), 'XU_WRAPPER_SIM=vcs requires vcs')
        root = Path(__file__).resolve().parents[2]
        log_directory = os.environ.get('XU_WRAPPER_LOG_DIR')
        def save_log(name, output):
            if log_directory:
                destination = Path(log_directory)
                destination.mkdir(parents=True, exist_ok=True)
                (destination / name).write_text(output)
        perips = root / 'third-party/e203_hbirdv2/rtl/e203/perips'
        sources = ['BiasSramPrefetch.sv', 'BiasBankCache.sv', 'LinearAutoGroupCore.sv', 'LinearCachedCore.sv', 'LinearComputeCore.sv',
                   'DotProductEngine.sv', 'MacController.sv', 'MacPEArray.sv',
                   'MacPE.sv', 'XRowBuffer.sv', 'WeightBankArray.sv',
                   'WeightBank.sv', 'Sram1024x16.sv', 'mem_1024x16.sv',
                   'accel_icb_slave.v']
        with tempfile.TemporaryDirectory(prefix='xu-cache-wrapper-') as temporary:
            binary = Path(temporary) / ('wrapper.vvp' if simulator == 'iverilog' else 'simv')
            inputs = [str(root/'tests/e203/tb_xu_cached_wrapper.sv'),
                      *[str(perips/name) for name in sources]]
            if simulator == 'vcs':
                compile_command = ['vcs', '-full64', '-sverilog', '-timescale=1ns/10ps',
                                   '-top', 'tb_xu_cached_wrapper',
                                   '+define+DISABLE_SV_ASSERTION=1',
                                   '-Mdir=' + str(Path(temporary)/'csrc'), '-o', str(binary),
                                   *inputs]
                simulate_command = [str(binary)]
            else:
                compile_command = ['iverilog', '-g2012', '-s', 'tb_xu_cached_wrapper',
                                   '-o', str(binary), *inputs]
                simulate_command = ['vvp', str(binary)]
            built = subprocess.run(compile_command, cwd=temporary,
                                   universal_newlines=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=180)
            save_log('compile.log', built.stdout + built.stderr)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run(simulate_command, cwd=temporary, universal_newlines=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            save_log('simulation.log', result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('XU_CACHED_WRAPPER_PASS', result.stdout)
            self.assertNotRegex(result.stdout + result.stderr,
                                re.compile(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', re.IGNORECASE))


if __name__ == '__main__':
    unittest.main()
