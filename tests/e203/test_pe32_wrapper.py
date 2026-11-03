"""Run new 32PE adapter itself in both wide and legacy-compatible modes."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


class XuPe32WrapperTests(unittest.TestCase):
    environment = 'XU_PE32_WRAPPER'
    bank128 = False

    def run_real_single_w_array_both_abis(self, designated_model=None):
        backend = os.environ.get(self.environment+'_SIM', 'iverilog')
        self.assertIn(backend, ('iverilog', 'vcs'))
        needed = ['vcs'] if backend == 'vcs' else ['iverilog', 'vvp']
        missing = [name for name in needed if not shutil.which(name)]
        if missing:
            if self.environment+'_SIM' in os.environ:
                self.fail('explicit PE32 backend unavailable: ' + ', '.join(missing))
            self.skipTest('PE32 direct simulation needs ' + ', '.join(missing))
        root = Path(__file__).resolve().parents[2]
        perips = root / 'third-party/e203_hbirdv2/rtl/e203/perips'
        names = ['XuParallelAutoGroupCore32.sv', 'XuParallelComputeCore32.sv',
                 'XuParallelBiasCache32.sv', 'XuParallelWeightBank32.sv',
                 'MacController.sv', 'MacPE.sv', 'XRowBuffer.sv',
                 'Sram1024x16.sv', 'mem_1024x16.sv', 'xu_pe32_icb_slave.v']
        if self.bank128:
            names = ['XuParallelAutoGroupCore32Bank128.sv', 'XuParallelComputeCore32Bank128.sv',
                     'XuParallelBiasCache32.sv', 'XuParallelWeightBank32Bank128.sv',
                     'MacController.sv', 'MacPE.sv', 'XRowBuffer.sv',
                     'Sram128x16.sv', 'mem_128x16.sv', 'xu_pe32_bank128_icb_slave.v']
        if designated_model is not None:
            self.assertTrue(self.bank128, 'designated 128 model belongs to bank128 only')
            names.remove('mem_128x16.sv')
        log_root = os.environ.get(self.environment+'_LOG_DIR')
        for kind, top, work in [('wide', 'tb_xu_pe32_wrapper', (16, 27)),
                                ('compat', 'tb_xu_pe32_compat_wrapper', (64, 99))]:
            if designated_model is not None:
                kind += '-designated-macro'
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix='xu-pe32-' + kind + '-') as temporary:
                directory = Path(temporary)
                binary = directory / ('simv' if backend == 'vcs' else 'sim.vvp')
                sources = [root / ('tests/e203/' + top + '.sv')] + [perips / name for name in names]
                if designated_model is not None:
                    sources += [root / 'tools/ppa/xu_weight128_sram_adapter.sv', designated_model]
                command = (['vcs', '-full64', '-sverilog', '-timescale=1ns/10ps', '-top', top,
                            '+define+DISABLE_SV_ASSERTION=1', '-Mdir=' + str(directory / 'csrc')]
                           if backend == 'vcs' else ['iverilog', '-g2012', '-s', top])
                if self.bank128:
                    command += ['+define+XU_PE32_BANK128=1' if backend=='vcs' else '-DXU_PE32_BANK128=1']
                if designated_model is not None:
                    command += ['+define+ARM_UD_MODEL' if backend=='vcs' else '-DARM_UD_MODEL']
                command += ['-o', str(binary)] + [str(path) for path in sources]

                def run(argv, name, timeout):
                    result = subprocess.run(argv, cwd=directory, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, universal_newlines=True, timeout=timeout)
                    if log_root:
                        destination = Path(log_root) / kind
                        destination.mkdir(parents=True, exist_ok=True)
                        record = dict(argv=argv, cwd=str(directory))
                        if designated_model is not None:
                            record['designated_model'] = dict(path=str(designated_model),
                                sha256=hashlib.sha256(designated_model.read_bytes()).hexdigest())
                        (destination / name).write_text(json.dumps(record) + '\n' + result.stdout)
                    self.assertEqual(result.returncode, 0, result.stdout)
                    return result.stdout

                run(command, 'compile.log', 600)
                text = run([str(binary)] if backend == 'vcs' else ['vvp', str(binary)], 'simulation.log', 120)
                marker = 'XU_PE32' + ('_COMPAT' if kind.startswith('compat') else '') + '_WRAPPER_PASS'
                found = re.findall(marker + r' rows=2 groups=(\d+) lanes=512 overlap=(\d+) launches=(\d+) dones=(\d+) accepted=(\d+) retired=(\d+)', text)
                self.assertEqual(len(found), 1, text)
                groups, overlap, launches, dones, accepted, retired = map(int, found[0])
                self.assertEqual((groups, launches, dones), (work[0], work[1], work[1]))
                self.assertGreater(overlap, 0)
                self.assertEqual(accepted, retired)
                activity = re.findall(r'XU_PE32_DIRECT_ACTIVITY physical_pes=32 mac_beats=(\d+) lane_macs=(\d+)', text)
                self.assertEqual(activity, [('1728', '53760')] if kind.startswith('wide') else [('6336', '50688')])
                self.assertNotRegex(text, r'\b(?:FATAL|FAIL(?:ED|URE)?)\b')

    def test_real_single_w_array_both_abis(self):
        self.run_real_single_w_array_both_abis()


if __name__ == '__main__':
    unittest.main()
