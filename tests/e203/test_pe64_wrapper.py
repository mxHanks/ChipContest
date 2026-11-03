"""Run new 64PE adapter itself in both wide and legacy-compatible modes."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


class XuPe64WrapperTests(unittest.TestCase):
    def test_real_single_w_array_three_width_contracts(self):
        backend = os.environ.get('XU_PE64_WRAPPER_SIM', 'iverilog')
        self.assertIn(backend, ('iverilog', 'vcs'))
        needed = ['vcs'] if backend == 'vcs' else ['iverilog', 'vvp']
        missing = [name for name in needed if not shutil.which(name)]
        if missing:
            if 'XU_PE64_WRAPPER_SIM' in os.environ:
                self.fail('explicit PE64 backend unavailable: ' + ', '.join(missing))
            self.skipTest('PE64 direct simulation needs ' + ', '.join(missing))
        root = Path(__file__).resolve().parents[2]
        perips = root / 'third-party/e203_hbirdv2/rtl/e203/perips'
        names = ['XuParallelAutoGroupCore64.sv', 'XuParallelComputeCore64.sv',
                 'XuParallelBiasCache64.sv', 'XuParallelWeightBank64.sv',
                 'MacController.sv', 'MacPE.sv', 'XRowBuffer.sv',
                 'Sram1024x16.sv', 'mem_1024x16.sv', 'xu_pe64_icb_slave.v']
        log_root = os.environ.get('XU_PE64_WRAPPER_LOG_DIR')
        for kind, define, lanes in [('wide64', None, 64), ('compat32', 'XU_DIRECT_MODE32=1', 32), ('compat8', 'XU_DIRECT_MODE8=1', 8)]:
            top='tb_xu_pe64_wrapper'
            work=(2*(256//lanes), 3*(256//lanes)+3)
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix='xu-pe64-' + kind + '-') as temporary:
                directory = Path(temporary)
                binary = directory / ('simv' if backend == 'vcs' else 'sim.vvp')
                sources = [root / ('tests/e203/' + top + '.sv')] + [perips / name for name in names]
                command = (['vcs', '-full64', '-sverilog', '-timescale=1ns/10ps', '-top', top,
                            '+define+DISABLE_SV_ASSERTION=1', '-Mdir=' + str(directory / 'csrc')]
                           if backend == 'vcs' else ['iverilog', '-g2012', '-s', top])
                if define: command += [('+'+'define+' if backend=='vcs' else '-D')+define]
                command += ['-o', str(binary)] + [str(path) for path in sources]

                def run(argv, name, timeout):
                    result = subprocess.run(argv, cwd=directory, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, universal_newlines=True, timeout=timeout)
                    if log_root:
                        destination = Path(log_root) / kind
                        destination.mkdir(parents=True, exist_ok=True)
                        (destination / name).write_text(json.dumps(dict(argv=argv, cwd=str(directory))) + '\n' + result.stdout)
                    self.assertEqual(result.returncode, 0, result.stdout)
                    return result.stdout

                run(command, 'compile.log', 600)
                text = run([str(binary)] if backend == 'vcs' else ['vvp', str(binary)], 'simulation.log', 120)
                marker = 'XU_PE64_WRAPPER_PASS mode_lanes='+str(lanes)
                found = re.findall(marker + r' rows=2 groups=(\d+) lanes=512 overlap=(\d+) launches=(\d+) dones=(\d+) accepted=(\d+) retired=(\d+)', text)
                self.assertEqual(len(found), 1, text)
                groups, overlap, launches, dones, accepted, retired = map(int, found[0])
                self.assertEqual((groups, launches, dones), (work[0], work[1], work[1]))
                self.assertGreater(overlap, 0)
                self.assertEqual(accepted, retired)
                activity = re.findall(r'XU_PE64_DIRECT_ACTIVITY physical_pes=64 mac_beats=(\d+) lane_macs=(\d+)', text)
                self.assertEqual(activity, [(str(work[1]*64), str(49664+128*lanes))])
                self.assertNotRegex(text, r'\b(?:FATAL|FAIL(?:ED|URE)?)\b')


if __name__ == '__main__':
    unittest.main()
