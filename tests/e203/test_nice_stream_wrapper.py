"""Optional direct stream: all groups, first-error abort, real numeric data.

The wrapper uploads real W/X/bias and computes the MAC oracle independently.
Unit fixtures isolate descriptor/timeout/error/reset cases; no FIFO payload is
forced or preloaded. Legacy direct errors remain part of this regression.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest


class NiceDirectStreamTests(unittest.TestCase):
    def test_unit_real_mac_backpressure_first_error_and_reset(self):
        root = Path(__file__).resolve().parents[2]
        rtl = root / 'third-party/e203_hbirdv2/rtl/e203'
        logs = os.environ.get('XU_STREAM_LOG_DIR')

        def run(command, name, cwd):
            result = subprocess.run(command, cwd=cwd, text=True,
                                    capture_output=True, timeout=90)
            output = result.stdout + result.stderr
            if logs:
                destination = Path(logs)
                destination.mkdir(parents=True, exist_ok=True)
                (destination / (name + '.log')).write_text(output)
            self.assertEqual(result.returncode, 0, output)
            return output

        with tempfile.TemporaryDirectory(prefix='xu-direct-stream-') as temporary:
            for module, marker in [
                ('tb_nice_stream_errors',
                 'NICE_STREAM8_PASS cases=118 success_counts=32 status_abort_groups=32 postpop_write_errors=24 resets=14'),
                ('tb_nice_stream_disabled',
                 'NICE_STREAM8_DISABLED_PASS compile_time_enable=0 no_side_effect=1'),
                ('tb_nice_direct_errors',
                 'NICE_DIRECT_ERRORS_PASS cases=19 bus_error_positions=9 direct_status_errors=2 commit_error=1 shared_error_lanes=8 resets=4'),
            ]:
                binary = Path(temporary) / (module + '.vvp')
                run(['iverilog', '-g2012', '-I' + str(rtl / 'core'), '-s', module,
                     '-o', str(binary), str(root / 'tests/e203' / (module + '.sv')),
                     str(rtl / 'subsys/xu_nice_drain8.v')], module + '-compile', temporary)
                output = run(['vvp', str(binary)], module + '-simulation', temporary)
                self.assertIn(marker, output)

            sources = ['BiasSramPrefetch.sv', 'BiasBankCache.sv', 'LinearAutoGroupCore.sv',
                       'LinearCachedCore.sv', 'LinearComputeCore.sv', 'DotProductEngine.sv',
                       'MacController.sv', 'MacPEArray.sv', 'MacPE.sv', 'XRowBuffer.sv',
                       'WeightBankArray.sv', 'WeightBank.sv', 'Sram1024x16.sv',
                       'mem_1024x16.sv', 'accel_icb_slave.v']
            binary = Path(temporary) / 'wrapper.vvp'
            run(['iverilog', '-g2012', '-I' + str(rtl / 'core'), '-s',
                 'tb_xu_nice_stream_wrapper', '-o', str(binary),
                 str(root / 'tests/e203/tb_xu_nice_stream_wrapper.sv'),
                 str(rtl / 'subsys/xu_nice_drain8.v'),
                 *[str(rtl / 'perips' / name) for name in sources]],
                'wrapper-compile', temporary)
            output = run(['vvp', str(binary)], 'wrapper-simulation', temporary)
            self.assertIn('STREAM_WRAPPER_PASS real_groups=32 real_y32_lanes=256', output)
            self.assertIn('shared_write_error_index=59 completion_stall=17', output)
            self.assertIn('DIRECT_REAL_NUMERIC_PASS legal_min=32 legal_max=32 positive_ties=75 '
                          'negative_ties=75 even_ties=75 odd_ties=75 force_used=0', output)
            for phase in (1, 2, 3):
                output = run(['vvp', str(binary), '+RESET_PHASE=' + str(phase)],
                             'reset-phase-' + str(phase), temporary)
                self.assertIn('DIRECT_RESET_PASS phase=' + str(phase) +
                              ' mode_disabled=1 stale_bundle=0 stale_pop=0', output)


if __name__ == '__main__':
    unittest.main()
