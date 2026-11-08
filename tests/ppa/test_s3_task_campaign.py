"""Generation/measurement contracts for the isolated S3 campaign clock seam."""
import importlib.util
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('s3_task_campaign', ROOT/'tools/ppa/s3_task_campaign.py')
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


class S3TaskCampaignClockTests(unittest.TestCase):
    def test_development_clock_seam_preserves_exact_source(self):
        original = (ROOT/'tests/e203/tb_accel_soc.sv').read_text()
        self.assertEqual(campaign.apply_platform_clocks(original,'development'),original)

    def test_explicit_clocks_preserve_original_assertions_and_other_text(self):
        original = (ROOT/'tests/e203/tb_accel_soc.sv').read_text()
        generated = campaign.apply_platform_clocks(original,'150mhz')
        self.assertTrue(generated.startswith('`timescale 1ns/1fs\n'))
        self.assertIn('  always #3.333333333 clk = ~clk;',generated)
        self.assertIn('  always #15258.7890625 lfclk = ~lfclk;',generated)
        for assertion in re.findall(r'\$fatal\([^;]*;',original):
            self.assertIn(assertion,generated)
        restored = generated.removeprefix('`timescale 1ns/1fs\n')
        restored = re.sub(r'  initial begin : s3_measure_(?:hf|lf)_clock\n.*?  end\n',
                          '',restored,flags=re.S)
        restored = restored.replace('  reg clk = 0, lfclk = 0, rst_n = 0;\n\n',
                                    '  reg clk = 0, lfclk = 0, rst_n = 0;\n',1)
        restored = restored.replace('  always #3.333333333 clk = ~clk;','  always #2 clk = ~clk;')
        restored = restored.replace('  always #15258.7890625 lfclk = ~lfclk;','  always #33 lfclk = ~lfclk;')
        self.assertEqual(restored,original)
        with self.assertRaisesRegex(AssertionError,'clock declaration'):
            campaign.apply_platform_clocks(original.replace('  always #2 clk = ~clk;',
                                                             '  always #3 clk = ~clk;'),'150mhz')

    def test_actual_rounding_records_required_and_checked(self):
        log = ('S3_CLOCK_PROFILE domain=hf requested_half_ns=3.333333333 '
               'measured_half_ns=3.333333000 period_ns=6.666666000 '
               'frequency_hz=150000015.000001490 precision_fs=1\n'
               'S3_CLOCK_PROFILE domain=lf requested_half_ns=15258.7890625 '
               'measured_half_ns=15258.789063000 period_ns=30517.578126000 '
               'frequency_hz=32767.999998926 precision_fs=1\n')
        self.assertEqual(len(campaign.check_clock_observations(log,'150mhz')),2)
        for bad in [log.splitlines()[0], log+log, log.replace('6.666666000','6.660000000'),
                    log.replace('150000015.000001490','150000000.000000000')]:
            with self.subTest(log=bad), self.assertRaises(ValueError):
                campaign.check_clock_observations(bad,'150mhz')
        self.assertEqual(campaign.check_clock_observations('','development'),[])

    def test_vendor_assertions_remove_only_explicit_vcs_waiver(self):
        original = ['vcs','-full64','+define+DISABLE_SV_ASSERTION=1','-f','frozen.f']
        self.assertEqual(campaign.vcs_assertion_command(original,False),original)
        self.assertEqual(campaign.vcs_assertion_command(original,True),
                         ['vcs','-full64','-f','frozen.f'])
        self.assertEqual(original[2],'+define+DISABLE_SV_ASSERTION=1')
        with self.assertRaisesRegex(ValueError,'macro configuration'):
            campaign.vcs_assertion_command(['vcs','-full64'],True)

    def test_vendor_assertions_reject_icarus_before_output_creation(self):
        with self.assertRaises(SystemExit) as caught:
            campaign.main(['--out','/this-path-must-not-be-created',
                           '--bias-kind','sram','--simulator','iverilog','--platform-assertions'])
        self.assertEqual(caught.exception.code,2)


if __name__=='__main__':
    unittest.main()
