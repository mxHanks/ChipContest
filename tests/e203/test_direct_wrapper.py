"""Opt-in accelerator/NICE direct result interface: real MAC data, ownership,
backpressure, frozen error codes, first-error abort and common-reset release.
No force, golden preload, LSU/BIU changes or synthesis are used.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest


class DirectTransportTests(unittest.TestCase):
    def test_real_mac_bundle_ownership_backpressure_and_first_error(self):
        root=Path(__file__).resolve().parents[2]
        rtl=root / 'third-party/e203_hbirdv2/rtl/e203'
        logs=os.environ.get('XU_DIRECT_LOG_DIR')
        def run(command, name, cwd):
            result=subprocess.run(command,cwd=cwd,text=True,capture_output=True,timeout=90)
            output=result.stdout+result.stderr
            if logs:
                destination=Path(logs)
                destination.mkdir(parents=True,exist_ok=True)
                (destination/(name+'.log')).write_text(output)
            return result.returncode,output
        with tempfile.TemporaryDirectory(prefix='xu-direct-') as temporary:
            unit=Path(temporary)/'errors.vvp'
            rc,output=run(['iverilog','-g2012','-I'+str(rtl/'core'),'-s','tb_nice_direct_errors',
                '-o',str(unit),str(root/'tests/e203/tb_nice_direct_errors.sv'),
                str(rtl/'subsys/xu_nice_drain8.v')],'errors-compile',temporary)
            self.assertEqual(rc,0,output)
            rc,output=run(['vvp',str(unit)],'errors-simulation',temporary)
            self.assertEqual(rc,0,output)
            self.assertIn('NICE_DIRECT_ERRORS_PASS cases=19 bus_error_positions=9 direct_status_errors=2 commit_error=1 shared_error_lanes=8 resets=4',output)
            sources = ['BiasSramPrefetch.sv', 'BiasBankCache.sv', 'LinearAutoGroupCore.sv',
                'LinearCachedCore.sv', 'LinearComputeCore.sv', 'DotProductEngine.sv',
                'MacController.sv', 'MacPEArray.sv', 'MacPE.sv', 'XRowBuffer.sv',
                'WeightBankArray.sv', 'WeightBank.sv', 'Sram1024x16.sv',
                'mem_1024x16.sv', 'accel_icb_slave.v']
            binary = Path(temporary) / 'wrapper.vvp'
            rc, output = run(['iverilog', '-g2012', '-I' + str(rtl / 'core'), '-s', 'tb_xu_direct_wrapper',
                '-o', str(binary), str(root / 'tests/e203/tb_xu_direct_wrapper.sv'),
                str(rtl / 'subsys/xu_nice_drain8.v'), *[str(rtl / 'perips' / name) for name in sources]], 'wrapper-compile', temporary)
            self.assertEqual(rc, 0, output)
            rc,output=run(['vvp',str(binary)],'direct-simulation',temporary)
            self.assertEqual(rc,0,output)
            self.assertIn('DIRECT_WRAPPER_PASS real_groups=32 real_y32_lanes=256',output)
            self.assertIn('DIRECT_REAL_NUMERIC_PASS legal_min=32 legal_max=32 positive_ties=75 negative_ties=75 even_ties=75 odd_ties=75 force_used=0',output)
            for phase in (1,2,3):
                rc,output=run(['vvp',str(binary),'+RESET_PHASE='+str(phase)],'reset-phase-'+str(phase),temporary)
                self.assertEqual(rc,0,output)
                self.assertIn('DIRECT_RESET_PASS phase='+str(phase)+' mode_disabled=1 stale_bundle=0 stale_pop=0',output)


if __name__=='__main__': unittest.main()
