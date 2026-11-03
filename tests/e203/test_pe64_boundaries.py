"""Actual64 wrapper boundary reads; uninitialized storage is not declared valid data."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


class XuPe64BoundaryTests(unittest.TestCase):
    def test_unaligned_and_exclusive_bounds_preserve_owned_head(self):
        backend = os.environ.get('XU_PE64_WRAPPER_SIM', 'iverilog')
        self.assertIn(backend, ('iverilog', 'vcs'))
        required = ['vcs'] if backend == 'vcs' else ['iverilog', 'vvp']
        missing = [tool for tool in required if not shutil.which(tool)]
        if missing:
            if 'XU_PE64_WRAPPER_SIM' in os.environ:
                self.fail('explicit PE64 backend unavailable: ' + ', '.join(missing))
            self.skipTest('PE64 boundary simulation needs ' + ', '.join(missing))
        root = Path(__file__).resolve().parents[2]
        perips = root / 'third-party/e203_hbirdv2/rtl/e203/perips'
        names = ['XuParallelAutoGroupCore64.sv', 'XuParallelComputeCore64.sv',
                 'XuParallelBiasCache64.sv', 'XuParallelWeightBank64.sv',
                 'MacController.sv', 'MacPE.sv', 'XRowBuffer.sv',
                 'Sram1024x16.sv', 'mem_1024x16.sv', 'xu_pe64_icb_slave.v']
        with tempfile.TemporaryDirectory(prefix='xu-pe64-boundary-') as temporary:
            directory = Path(temporary)
            binary = directory / ('simv' if backend == 'vcs' else 'sim.vvp')
            top = 'tb_xu_pe64_boundaries'
            sources = [root / ('tests/e203/' + top + '.sv')] + [perips / name for name in names]
            command = (['vcs', '-full64', '-sverilog', '-timescale=1ns/10ps', '-top', top,
                        '+define+DISABLE_SV_ASSERTION=1', '-Mdir=' + str(directory / 'csrc')]
                       if backend == 'vcs' else ['iverilog', '-g2012', '-s', top])
            command += ['-o', str(binary)] + [str(path) for path in sources]
            log_root = os.environ.get('XU_PE64_WRAPPER_LOG_DIR')

            def run(argv, name, timeout):
                result = subprocess.run(argv, cwd=directory, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, universal_newlines=True, timeout=timeout)
                if log_root:
                    destination = Path(log_root) / 'boundary'
                    destination.mkdir(parents=True, exist_ok=True)
                    (destination / name).write_text(json.dumps(dict(argv=argv, cwd=str(directory))) + '\n' + result.stdout)
                self.assertEqual(result.returncode, 0, result.stdout)
                return result.stdout

            run(command, 'compile.log', 600)
            text = run([str(binary)] if backend == 'vcs' else ['vvp', str(binary)], 'simulation.log', 120)
            self.assertEqual(re.findall(r'XU_PE64_BOUNDARY_PASS mode=(\d) unknown_reads=14 mode_error=1 pop_retired=1', text), ['0', '1', '2'])
            self.assertEqual(text.count('XU_PE64_BOUNDARIES_PASS modes=3'), 1)
            self.assertNotRegex(text, r'\b(?:FATAL|FAIL(?:ED|URE)?)\b')


if __name__ == '__main__':
    unittest.main()
