import hashlib
from pathlib import Path
import tempfile
import unittest

import activity145 as runtime
import build_manifest161

HERE=Path(__file__).resolve().parent
FAILED_LOG_SHA='572ef7596d46a6cc34507cbea7e28d1a287af2bfb4a7f89ec050f165b68c213d'


class FirmwareInput161(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='xu161-host-')
        self.root=Path(self.temporary.name)
        self.binary=self.root/'soc';self.binary.write_bytes(b'host fixture simulator')
        self.elf=self.root/'accel_soc';self.elf.write_bytes(b'host fixture ELF')
        self.image=self.root/'accel_soc.verilog';self.image.write_text('@00000000\n01 00 00 00\n')
        self.receipt=dict(elf=runtime.identity(self.elf),image=runtime.identity(self.image))

    def tearDown(self):
        self.temporary.cleanup()

    def test_original_native_tb_loads_the_actual_bound_image_once(self):
        actual=(HERE/'fixtures/actual145-s2b-tb.sv').read_text()
        self.assertEqual(actual.count('$readmemh({testcase,".verilog"},program_bytes);'),1)
        command=runtime.task_run_command(self.binary,self.image,self.receipt,self.root/'task_00',0,4000000)
        testcase=command[1].split('=',1)[1]
        self.assertEqual(Path(testcase+'.verilog'),self.image)
        self.assertNotIn('.verilog.verilog',testcase+'.verilog')
        self.assertEqual(runtime.identity(Path(testcase+'.verilog')),self.receipt['image'])
        self.assertEqual(command,[str(self.binary),'+TESTCASE='+str(self.elf),
            '+VECTORS='+str(self.root/'task_00/vectors'),'+TASKS=1','+XU_GLOBAL_TASK=0',
            '+MAX_CYCLES=4000000','+DUMPWAVE=0'])

    def test_same_frozen_binary_and_input_image_are_used_for_all_original_tasks(self):
        expected_binary=runtime.identity(self.binary)
        for task_id in range(12):
            directory=self.root/('task_%02d'%task_id)
            command=runtime.task_run_command(self.binary,self.image,self.receipt,directory,task_id,4000000)
            self.assertEqual(runtime.identity(command[0]),expected_binary)
            self.assertEqual(command[1],'+TESTCASE='+str(self.elf))
            self.assertEqual(command[2],'+VECTORS='+str(directory/'vectors'))
            self.assertEqual(command[4],'+XU_GLOBAL_TASK='+str(task_id))
            self.assertEqual(command[5],'+MAX_CYCLES=4000000')

    def test_missing_image_changed_image_and_wrong_prefix_are_rejected_before_native_run(self):
        self.image.unlink()
        with self.assertRaises(ValueError):runtime.firmware_testcase_prefix(self.image,self.receipt)
        self.image.write_text('different bytes')
        with self.assertRaises(ValueError):runtime.firmware_testcase_prefix(self.image,self.receipt)
        self.receipt['image']=runtime.identity(self.image)
        other=self.root/'other_elf';other.write_bytes(self.elf.read_bytes())
        self.receipt['elf']=runtime.identity(other)
        with self.assertRaises(ValueError):runtime.firmware_testcase_prefix(self.image,self.receipt)

    def test_actual_native_missing_program_warning_is_rejected_without_waiting_for_timeout(self):
        path=HERE/'fixtures/actual145-s2b-task00.log'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),FAILED_LOG_SHA)
        log=path.read_text()
        self.assertIn('accel_soc.verilog.verilog',log)
        self.assertNotIn('XU_CLEAR_BEGIN145',log)
        early=log[:log.index('XU_CACHE_RELOAD')]
        self.assertNotIn('SoC timeout',early)
        with self.assertRaisesRegex(ValueError,'161 firmware/file read diagnostic'):
            runtime.reject_firmware_read_warning(early)
        for warning in ('Warning-[STASKW_CO1] Cannot open file',
                        'Warning-[STASKW_RMCOF] Cannot open file','file could not be opened'):
            with self.assertRaises(ValueError):runtime.reject_firmware_read_warning(warning)
        runtime.reject_firmware_read_warning('XU_CLEAR_BEGIN145\nXU_SOURCE_REQUEST145\nSOC_PASS tasks=1\n')

    def test_file_guard_preserves_the_complete_original_tb(self):
        original=(HERE/'fixtures/actual145-s2b-tb.sv').read_text()
        def once(text,old,new):
            if text.count(old)!=1:raise ValueError('anchor differs')
            return text.replace(old,new)
        guarded=runtime.guarded_firmware_read(original,once)
        begin=guarded.index('    begin : xu_firmware_input161\n')
        end=guarded.index('    $readmemh({testcase,".verilog"},program_bytes);',begin)
        self.assertEqual(guarded[:begin]+guarded[end:],original)
        self.assertIn('$fopen({testcase,".verilog"},"r")',guarded[begin:end])
        self.assertIn('$fatal(1,"XU161_REJECT firmware image cannot be opened")',guarded[begin:end])
        with self.assertRaises(ValueError):runtime.guarded_firmware_read(guarded,once)

    def test_scope_has_six_profiles_and_retains_power146_import_interface(self):
        self.assertEqual(list(runtime.PROFILES161),build_manifest161.PROFILES)
        self.assertNotIn('pe32',runtime.PROFILES161)
        self.assertNotIn('pe64',runtime.PROFILES161)
        self.assertIn('compact32_128',runtime.PROFILES161)
        self.assertTrue(callable(runtime.verify_result))


if __name__=='__main__':unittest.main()
