"""Generation/measurement contracts for the isolated S3 campaign clock seam."""
import importlib.util
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


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

    def test_vendor_assertions_reject_non_vcs_before_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)/'must-not-exist'
            for simulator in ['iverilog','verilator']:
                with self.subTest(simulator=simulator), self.assertRaises(SystemExit) as caught:
                    campaign.main(['--out',str(out),'--bias-kind','sram',
                                   '--simulator',simulator,'--platform-assertions'])
                self.assertEqual(caught.exception.code,2)
                self.assertFalse(out.exists())


class S3TaskCampaignSimulatorTests(unittest.TestCase):
    def setUp(self):
        self.out = Path('/campaign')
        self.soc = SimpleNamespace(vcs_build_command=lambda out, filelist, includes, waves:
            ['vcs','+define+DISABLE_SV_ASSERTION=1','-o',str(out/'accel_soc'),'-f',str(filelist)])

    def build(self, simulator, waves=False, platform_assertions=False):
        return campaign.simulator_build_command(self.soc,simulator,self.out,self.out/'rtl.f',
                                                ['/frozen/rtl/core'],waves,platform_assertions)

    def test_verilator_preserves_procedural_assertions_and_separates_artifacts(self):
        build, binary, program = self.build('verilator')
        self.assertEqual(build[:7],['verilator','--binary','--timing','--assert',
                                    '-CFLAGS','-std=gnu++20','-j'])
        self.assertEqual(build[build.index('-j')+1],'2')
        self.assertIn('-Wno-fatal',build)
        self.assertIn('-DDISABLE_SV_ASSERTION=1',build)
        self.assertIn('-I/frozen/rtl/core',build)
        self.assertEqual(build[build.index('-Mdir')+1],str(binary.parent))
        self.assertEqual(build[build.index('-o')+1],binary.name)
        self.assertEqual(program,[str(binary)])
        self.assertNotEqual(binary,self.out/'accel_soc')
        self.assertNotIn('--trace',build)
        self.assertIn('--trace',self.build('verilator',waves=True)[0])
        self.assertFalse(any('SYNTHESIS' in x or 'no-assert' in x for x in build))

    def test_existing_vcs_and_icarus_commands_and_assertion_boundary(self):
        build, binary, program = self.build('vcs',platform_assertions=True)
        self.assertEqual(binary,self.out/'simv')
        self.assertEqual(program,[str(binary)])
        self.assertEqual(build[build.index('-o')+1],str(binary))
        self.assertNotIn('+define+DISABLE_SV_ASSERTION=1',build)
        self.assertIn('+define+DISABLE_SV_ASSERTION=1',self.build('vcs')[0])
        build, binary, program = self.build('iverilog')
        self.assertEqual(binary,self.out/'soc.vvp')
        self.assertEqual(program,['vvp',str(binary)])
        self.assertIn('-DDISABLE_SV_ASSERTION=1',build)
        for simulator in ['iverilog','verilator']:
            with self.subTest(simulator=simulator), self.assertRaisesRegex(ValueError,'requires VCS'):
                self.build(simulator,platform_assertions=True)

    def test_command_hash_covers_exact_argv_boundaries(self):
        self.assertEqual(campaign.command_sha256(['tool',Path('/a b'),'c']),
                         campaign.command_sha256(['tool','/a b','c']))
        self.assertNotEqual(campaign.command_sha256(['tool','a b','c']),
                            campaign.command_sha256(['tool','a','b c']))
        self.assertNotEqual(campaign.command_sha256(['tool','a','b']),
                            campaign.command_sha256(['tool','b','a']))

    def test_versions_cover_invoked_native_tools(self):
        for simulator, expected in [('verilator',{'verilator','g++','make'}),
                                    ('vcs',{'vcs'}),('iverilog',{'iverilog','vvp'})]:
            with self.subTest(simulator=simulator):
                commands = campaign.version_commands(simulator,'rv-')
                self.assertEqual({x[0] for x in commands},
                    {campaign.sys.executable,'rv-gcc','rv-objcopy','rv-objdump','gcc'}|expected)

    def test_failed_native_launch_retains_exact_command_receipt(self):
        soc = SimpleNamespace(contract=SimpleNamespace(configuration=lambda *args:{}))
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)/'campaign'
            with mock.patch.object(campaign,'snapshot_inputs'), \
                 mock.patch.object(campaign,'load',side_effect=[soc,None]), \
                 mock.patch.object(campaign.subprocess,'run',side_effect=FileNotFoundError('missing native tool')), \
                 mock.patch.object(campaign.sys,'path',list(campaign.sys.path)):
                code = campaign.main(['--out',str(out),'--bias-kind','sram','--simulator','verilator'])
            report = json.loads((out/'result.json').read_text())
            self.assertEqual(code,1)
            self.assertEqual(report['status'],'FAIL')
            self.assertEqual(len(report['steps']),1)
            step = report['steps'][0]
            self.assertEqual(step['command'],[campaign.sys.executable,'--version'])
            self.assertEqual(step['command_sha256'],campaign.command_sha256(step['command']))
            self.assertFalse(step['waitpid_completed'])
            self.assertIsNone(step['native_exit'])

    def test_mocked_verilator_campaign_reports_development_scope_and_complete_receipts(self):
        # No compiler or simulator is executed. Exercise the real driver/report
        # and the same 150MHz clock observations used for native acceptance.
        clocks = ('S3_CLOCK_PROFILE domain=hf requested_half_ns=3.333333333 '
                  'measured_half_ns=3.333333000 period_ns=6.666666000 '
                  'frequency_hz=150000015.000001490 precision_fs=1\n'
                  'S3_CLOCK_PROFILE domain=lf requested_half_ns=15258.7890625 '
                  'measured_half_ns=15258.789063000 period_ns=30517.578126000 '
                  'frequency_hz=32767.999998926 precision_fs=1\n')
        contract = SimpleNamespace(configuration=lambda *args:{},compiler_defines=lambda config:[],
                                   simulator_arguments=lambda schedule:[],NICE_SCHEDULES=set(),
                                   NICE_STREAM_SCHEDULE='bias-hw-autogroup-y32-packed16-nice-direct-stream-window')
        soc = SimpleNamespace(contract=contract,load_fixture=lambda *args:{},check_vectors=lambda *args:{},
                              vector_identity=lambda *args:{},check_log=lambda *args:[{'cycles':3}],
                              check_performance=lambda *args:[{}],
                              check_task_windows=lambda *args:[{'first_request_wait':0}])
        clear = SimpleNamespace(firmware_wrapper=lambda *args:'frozen firmware wrapper',
                                observer_declarations=lambda:'// clear observer',
                                CLEAR_COUNTS={'sram':{'accepted_writes':42}})

        def snapshot(repo, source):
            firmware = source/'tests/e203/firmware'
            firmware.mkdir(parents=True)
            (firmware/'main.c').write_text('frozen main')
            (source/'tests/e203/tb_accel_soc.sv').write_text((ROOT/'tests/e203/tb_accel_soc.sv').read_text())
            (source/'tools/ppa').mkdir(parents=True)
            (source/'tools/ppa/s3_task_clear_protocol.py').write_text('frozen clear helper')

        def run(command, **kwargs):
            if '--version' in command:
                kwargs['stdout'].write('mock tool version\n')
            elif command[0]=='rv-gcc':
                Path(command[command.index('-o')+1]).write_bytes(b'RISC-V ELF')
            elif command[0]=='rv-objcopy':
                Path(command[-1]).write_text('@80000000\n00\n')
            elif command[0]=='rv-objdump':
                kwargs['stdout'].write('80000086 <write_tohost>\n')
            elif command[0]=='verilator':
                binary = Path(command[command.index('-Mdir')+1])/command[command.index('-o')+1]
                binary.parent.mkdir(parents=True)
                binary.write_bytes(b'native simulator')
            else:
                kwargs['stdout'].write(clocks+S3TaskCampaignStartupTests.STARTUP_LOG+
                                       'S3_TASK_CLEAR_OBSERVED mode_sram=1 writes=42 clear_cycles=5\n')
            return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)/'campaign'
            with mock.patch.object(campaign,'snapshot_inputs',side_effect=snapshot), \
                 mock.patch.object(campaign,'load',side_effect=[soc,clear]), \
                 mock.patch.object(campaign.subprocess,'run',side_effect=run) as native, \
                 mock.patch.object(campaign.sys,'path',list(campaign.sys.path)):
                # The real fixture extraction is mocked, but the layer-view
                # contract still expects its frozen tensor directory.
                def fixture(vectors, tasks):
                    (vectors/'layer_00').mkdir(parents=True)
                    (vectors/'layer_00/tensor.hex').write_text('00\n')
                    return {}
                soc.load_fixture = fixture
                code = campaign.main(['--out',str(out),'--bias-kind','sram','--layers','0',
                                      '--simulator','verilator','--cross-prefix','rv-',
                                      '--platform-clocks','150mhz','--startup-profile','external-reset'])
            report = json.loads((out/'result.json').read_text())
            plan = json.loads((out/'plan.json').read_text())
            self.assertEqual(code,0,report.get('error'))
            self.assertEqual(report['status'],'DEVELOPMENT_PASS_POLICY_PENDING')
            self.assertEqual(report['simulator_evidence'],dict(simulator='verilator',logic_semantics='2-state',
                vendor_sva='disabled',chisel_procedural_assertions='enabled_with_--assert',
                qualification='DEVELOPMENT_ONLY_NOT_VCS_OR_GATE_LEVEL_SIGNOFF'))
            self.assertEqual(plan['simulator_evidence'],report['simulator_evidence'])
            self.assertEqual(report['startup_configuration'],campaign.startup_configuration('external-reset'))
            self.assertEqual(plan['startup_configuration'],report['startup_configuration'])
            self.assertEqual(len(report['task_results'][0]['startup_observations']),3)
            self.assertEqual(len(report['task_results'][0]['measured_clocks']),2)
            self.assertNotEqual(report['firmware_elf'],report['simulator_binary'])
            self.assertNotEqual(report['firmware_elf_sha256'],report['simulator_sha256'])
            self.assertEqual(len(report['steps']),native.call_count)
            for step in report['steps']:
                self.assertEqual(step['command_sha256'],campaign.command_sha256(step['command']))
                self.assertTrue(step['waitpid_completed'])
            self.assertEqual(set(report['versions']),
                             {x[0] for x in campaign.version_commands('verilator','rv-')})
            self.assertEqual(report['source_drift'],[])


class S3TaskCampaignStartupTests(unittest.TestCase):
    STARTUP_LOG = ('S3_STARTUP_PROFILE event=second_assert time_ns=8011013.000000 cpu_reset_n=1\n'
                   'S3_STARTUP_PROFILE event=second_release time_ns=8011133.000000 held_ns=120.000000 cpu_reset_n=0\n'
                   'S3_STARTUP_PROFILE event=measurement_begin time_ns=8011133.000000 external_reset_n=1 cycle=0\n')

    def test_historical_preserves_exact_testbench_and_requires_no_new_records(self):
        original = (ROOT/'tests/e203/tb_accel_soc.sv').read_text()
        self.assertEqual(campaign.apply_startup_profile(original,'historical'),original)
        self.assertEqual(campaign.check_startup_observations('','historical'),[])
        with self.assertRaisesRegex(ValueError,'unexpected startup'):
            campaign.check_startup_observations(self.STARTUP_LOG,'historical')

    def test_external_reset_has_real_pin_edges_transaction_guard_and_separate_watchdog(self):
        original = (ROOT/'tests/e203/tb_accel_soc.sv').read_text()
        generated = campaign.apply_startup_profile(original,'external-reset')
        for assertion in re.findall(r'\$fatal\([^;]*;',original):
            self.assertIn(assertion,generated)
        self.assertIn('wait (`CPU.u_e203_cpu.rst_core===1\'b1);\n    @(negedge clk);',generated)
        self.assertIn('    rst_n=0;\n    #120ns;',generated)
        self.assertIn('cycles <= s3_startup_complete ? cycles+1 : 0;',generated)
        self.assertIn('S3 startup reset prewarm issued a transaction',generated)
        self.assertIn('#10ms;',generated)
        self.assertIn('if (cycles > max_cycles)',generated)
        self.assertNotIn('force ',generated)
        self.assertNotIn('DBG_S3_TAG_a9f2',generated)
        with self.assertRaisesRegex(AssertionError,'reset release'):
            campaign.apply_startup_profile(original.replace('#120 rst_n=1;','#121 rst_n=1;'),'external-reset')

    def test_external_reset_records_are_ordered_and_verify_actual_low_interval(self):
        self.assertEqual(len(campaign.check_startup_observations(self.STARTUP_LOG,'external-reset')),3)
        for bad in ['',self.STARTUP_LOG+self.STARTUP_LOG,
                    '\n'.join(reversed(self.STARTUP_LOG.splitlines())),
                    self.STARTUP_LOG.replace('held_ns=120.000000','held_ns=119.000000'),
                    self.STARTUP_LOG.replace('time_ns=8011133.000000','time_ns=8011134.000000'),
                    self.STARTUP_LOG.replace('cpu_reset_n=0','cpu_reset_n=1'),
                    self.STARTUP_LOG.replace('cycle=0','cycle=1')]:
            with self.subTest(log=bad), self.assertRaises(ValueError):
                campaign.check_startup_observations(bad,'external-reset')

    def test_external_reset_rejects_other_simulators_before_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)/'must-not-exist'
            for simulator in ['vcs','iverilog']:
                with self.subTest(simulator=simulator), self.assertRaises(SystemExit) as caught:
                    campaign.main(['--out',str(out),'--bias-kind','sram','--simulator',simulator,
                                   '--startup-profile','external-reset'])
                self.assertEqual(caught.exception.code,2)
                self.assertFalse(out.exists())


if __name__=='__main__':
    unittest.main()
