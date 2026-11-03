"""Bank geometry is a frozen physical variant, independent of the old schedules."""
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/scripts'))
import e203_soc as soc
import server_accept as accept


class XuPe32Bank128ContractTest(unittest.TestCase):
    def test_build_identity_and_exact_defines_select_the_independent_memory(self):
        self.assertEqual(soc.accelerator_defines('pe32-bank128'),['XU_ACCEL_PE32=1','XU_ACCEL_PE32_BANK128=1'])
        self.assertEqual(soc.accelerator_defines('pe32'),['XU_ACCEL_PE32=1'])
        self.assertEqual(soc.accelerator_defines('pe8'),[])
        with self.assertRaises(ValueError):soc.accelerator_defines('pe32-bank128=0')
        report=dict(source_sha256={},versions={},runner_sha256='xu')
        keys=[]
        for variant in ['pe8','pe32','pe32-bank128']:
            report['accel_variant']=variant;keys.append(soc.build_key(report,'vcs',False))
        self.assertEqual(len(set(keys)),3)
        argv=soc.vcs_build_command(Path('/tmp/xu'),Path('/tmp/rtl.f'),[],False,'pe32-bank128')
        self.assertIn('+define+XU_ACCEL_PE32_BANK128=1',argv)
        self.assertIn('+define+XU_ACCEL_PE32=1',argv)
        self.assertNotIn('+define+XU_ACCEL_PE32_BANK128=1',soc.vcs_build_command(Path('/tmp/xu'),Path('/tmp/rtl.f'),[],False,'pe32'))

    def test_every_acceptance_step_keeps_variant_and_required_actual_wrapper_tests(self):
        steps=accept.acceptance_steps(Path('/tmp/xu-bank128-new'),'rv-','vcs',
            firmware_schedule='bias-hw-pe32-autogroup-window',accel_variant='pe32-bank128')
        self.assertEqual([name for name,_,_ in steps],['host','numeric','vectors','doctor','baseline','synthetic1','synthetic2','real12'])
        for name,argv,_ in steps:
            if name=='host':
                self.assertIn('XU_PE32_BANK128_WRAPPER_SIM=vcs',argv)
                self.assertIn('XU_PE32_WRAPPER_SIM=vcs',argv)
            elif name!='numeric':self.assertEqual(argv[argv.index('--accel-variant')+1],'pe32-bank128')
        layer=dict(layer=0,cycles=1000000)
        text='PE_TASK layer=0 physical_pes=32 mac_beats=50688 lane_macs=1622016 useful_macs=1622016\n'
        self.assertEqual(soc.check_pe_activity(text,[layer],'bias-hw-pe32-autogroup-window','pe32-bank128')[0]['lane_macs'],1622016)
        with self.assertRaises(ValueError):soc.check_pe_activity(text.replace('physical_pes=32','physical_pes=64'),[layer],'bias-hw-pe32-autogroup-window','pe32-bank128')

    def test_original32_and8_generated_files_and_wrappers_remain_exact(self):
        root=Path(__file__).resolve().parents[2];child=root/'third-party/e203_hbirdv2'
        files=subprocess.check_output(['git','ls-tree','-r','--name-only','fc3977d','rtl/e203/perips'],cwd=str(child),universal_newlines=True).splitlines()
        frozen=[name for name in files if name.endswith('.sv') or name.endswith('/xu_pe32_icb_slave.v') or name.endswith('/accel_icb_slave.v')]
        for name in frozen:
            expected=subprocess.check_output(['git','show','fc3977d:'+name],cwd=str(child))
            self.assertEqual((child/name).read_bytes(),expected,name)
