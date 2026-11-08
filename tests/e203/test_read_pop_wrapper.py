"""Paired NICE/accelerator read-pop transport, alias ownership and legacy Y32 ABI.

The new hardware pair always uses 17 transactions. NICE_READ_POP selects the
SoC observer/contract for that RTL snapshot; it is not a hardware runtime switch.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest


class ReadPopTransportTests(unittest.TestCase):
    def test_matching_drain_and_alias_numeric_ownership_errors_and_backpressure(self):
        if not shutil.which('iverilog') or not shutil.which('vvp'):
            self.skipTest('iverilog and vvp are required for read-pop transport checks')
        root = Path(__file__).resolve().parents[2]
        rtl = root / 'third-party/e203_hbirdv2/rtl/e203'
        logs = os.environ.get('XU_READ_POP_LOG_DIR')

        def run(command, name, cwd):
            result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=90)
            output = result.stdout + result.stderr
            if logs:
                destination = Path(logs)
                destination.mkdir(parents=True, exist_ok=True)
                (destination / (name + '.log')).write_text(output)
            return result.returncode, output

        with tempfile.TemporaryDirectory(prefix='xu-read-pop-') as temporary:
            unit = Path(temporary) / 'drain8.vvp'
            rc, output = run(['iverilog', '-g2012', '-I' + str(rtl / 'core'),
                '-s', 'tb_nice_drain8', '-o', str(unit),
                str(root / 'experiments/nice_reachability/tb_nice_drain8.sv'),
                str(rtl / 'subsys/xu_nice_drain8.v')], 'drain8-compile', temporary)
            self.assertEqual(rc, 0, output)
            rc, output = run(['vvp', str(unit)], 'drain8-simulation', temporary)
            self.assertEqual(rc, 0, output)
            self.assertIn('NICE_DRAIN8_UNIT_PASS cases=61 commands=817 responses=817 '
                'all_error_transactions=17 groups=32 alias_errors=1 post_pop_write_errors=8', output)
            self.assertNotRegex(output, re.compile(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', re.I))

            sources = ['BiasSramPrefetch.sv', 'BiasBankCache.sv', 'LinearAutoGroupCore.sv',
                'LinearCachedCore.sv', 'LinearComputeCore.sv', 'DotProductEngine.sv',
                'MacController.sv', 'MacPEArray.sv', 'MacPE.sv', 'XRowBuffer.sv',
                'WeightBankArray.sv', 'WeightBank.sv', 'Sram1024x16.sv',
                'mem_1024x16.sv', 'accel_icb_slave.v']
            binary = Path(temporary) / 'wrapper.vvp'
            rc, output = run(['iverilog', '-g2012', '-s', 'tb_xu_read_pop_wrapper',
                '-o', str(binary), str(root / 'tests/e203/tb_xu_read_pop_wrapper.sv'),
                *[str(rtl / 'perips' / name) for name in sources]], 'wrapper-compile', temporary)
            self.assertEqual(rc, 0, output)
            rc, output = run(['vvp', str(binary)], 'wrapper-simulation', temporary)
            self.assertEqual(rc, 0, output)
            self.assertIn('READ_POP_WRAPPER_PASS alias_pops=32 legacy_pops=1 pop_events=33 '
                'real_groups=32 normal_lane7_reads=64 rejected_writes_and_unaligned=1 '
                'active_empty_guard=1 inactive_valid_diagnostic=1 stable_stalled_head=1', output)
            self.assertNotRegex(output, re.compile(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', re.I))
            rc, output = run(['vvp', str(binary), '+ALIAS_LEGAL_EXTREMES'],
                'alias-legal-extremes', temporary)
            self.assertEqual(rc, 0, output)
            self.assertIn('READ_POP_ALIAS_INTERFACE_DIAGNOSTIC_PASS '
                'forced_legal_extremes_not_mac_results=2', output)
            for plusarg, marker in [('ALIAS_BAD_HIGH', 'XU_Y32_RANGE_ERROR lane=7'),
                    ('ALIAS_BAD_LOW', 'XU_Y32_RANGE_ERROR lane=7'),
                    ('ALIAS_BAD_UNKNOWN', 'XU_Y32_UNKNOWN_ERROR lane=7')]:
                with self.subTest(illegal_input=plusarg):
                    rc, output = run(['vvp', str(binary), '+' + plusarg], plusarg.lower(), temporary)
                    self.assertNotEqual(rc, 0, output)
                    self.assertIn(marker, output)
                    self.assertNotIn('READ_POP_WRAPPER_PASS', output)


if __name__ == '__main__':
    unittest.main()
