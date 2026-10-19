"""Host parser/patch tests; synthetic markers establish no CPU/HDL result."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class SRAMAdapterSoCTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('adapter_soc_subject',ROOT/'scripts/verify/run_sram_adapter_soc.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.command={'status':'EXITED','exit_code':0,'timed_out':False,'interrupted':False}
        self.text=('PASS E203_SRAM_TASK task=0 outputs=25344 load_commits=22976 start=1 first_config=2 first_x=3 '
                   'last_write_rsp=4 ack_rsp=5 end=6 window_cycles=6 core_cycles=4 output_write_responses=50688 ack_responses=1\n'
                   'PASS E203_SRAM_RECOVERY soft_aborts=1 hard_resets=1 pending_response_reset=1\n'
                   'PASS E203_SRAM_SUITE tasks=1 outputs=25344 development_window_cycles=6 platform=open_fork_development\n'
                   '- /source/bench.sv:154: Verilog $finish\n')

    def test_complete_scope_preserves_per_task_response_order_and_recovery(self):
        result=self.m.accept_soc(self.command,self.text,1)
        self.assertEqual(result['outputs'],25344)
        self.assertEqual(result['development_window_cycles'],6)
        self.assertEqual(result['recovery']['pending_response_reset'],1)

    def test_bad_extra_missing_and_failed_families_are_rejected(self):
        for text in ('',self.text+self.text,self.text+'INFO PASS E203_SRAM_TASK malformed\n',
                     self.text+'PASS E203_SRAM_RECOVERY malformed\n',
                     self.text+'PASS E203_SRAM_SUITE malformed\n',
                     self.text.replace('output_write_responses=50688','output_write_responses=50687'),
                     self.text.replace('ack_rsp=5','ack_rsp=4'),
                     self.text.replace('window_cycles=6','window_cycles=5',1),
                     self.text.replace('Verilog $finish','early exit'),
                     self.text+'- /other.sv:1: Verilog $finish\n',
                     self.text+'%Error: unrelated failure\n'):
            with self.subTest(text=text[-120:]),self.assertRaises(ValueError):
                self.m.accept_soc(self.command,text,1)

    def test_native_incomplete_and_boolean_exit_cannot_pass(self):
        bad=[dict(self.command,exit_code=False),dict(self.command,exit_code=-11),dict(self.command,status='RUNNING'),
             dict(self.command,timed_out=0),dict(self.command,interrupted=True)]
        for key in self.command:
            item=dict(self.command);del item[key];bad.append(item)
        for command in bad:
            with self.subTest(command=command),self.assertRaises(ValueError):self.m.accept_soc(command,self.text,1)

    def test_twelve_task_default_does_not_accept_one_task(self):
        with self.assertRaises(ValueError):self.m.accept_soc(self.command,self.text)

    def test_patch_is_unique_and_changes_only_target(self):
        text='head\noriginal needle\ntail\n'
        self.assertEqual(self.m.patch_once(text,'original needle','new needle'),'head\nnew needle\ntail\n')
        for text in ('missing','original needle\noriginal needle'):
            with self.subTest(text=text),self.assertRaises(ValueError):self.m.patch_once(text,'original needle','new')

    def warnings(self,run):
        return ('%Warning-UNOPTFLAT: /platform/cpu.v:2: unchanged signal\n  path: unchanged\n'
                '%Warning-LATCH: '+str(run)+'/soc.v:3: platform latch\n  unchanged body\n')

    def test_only_exact_baseline_loop_and_latch_diagnostics_are_grandfathered(self):
        old,new=Path('/old/run'),Path('/new/run')
        result=self.m.compare_platform_warnings(self.warnings(new),self.warnings(old),new,old)
        self.assertEqual(result['UNOPTFLAT']['count'],1)
        self.assertEqual(result['LATCH']['status'],'UNCHANGED_DEVELOPMENT_LIMITATION')

    def test_warning_diagnostic_excludes_following_native_make_output(self):
        old,new=Path('/old/run'),Path('/new/run')
        result=self.m.compare_platform_warnings(self.warnings(new)+'make[1]: Entering directory /new/run\ng++ new_backend.cpp\n',
                                               self.warnings(old)+'make: Entering directory /old/run\ng++ old_backend.cpp\n',new,old)
        self.assertEqual(result['LATCH']['count'],1)

    def test_missing_extra_or_changed_warning_block_rejected(self):
        old,new=Path('/old/run'),Path('/new/run');base=self.warnings(old);text=self.warnings(new)
        for changed in (text.replace('unchanged signal','new signal'),text+text,
                        text.replace('path: unchanged','path: different'),'',
                        text.replace('%Warning-LATCH:','%Warning-OTHER:')):
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                self.m.compare_platform_warnings(changed,base,new,old)

    def test_cpu_payload_must_match_but_elf_keeps_its_own_identity(self):
        before=[{'path':'/old/'+name,'sha256':str(i)*64,'size_bytes':100+i}
                for i,name in enumerate(('firmware.elf','firmware.bin','firmware.hex'))]
        actual=[dict(item,path=item['path'].replace('/old/','/new/')) for item in before]
        actual[0]['sha256']='f'*64
        self.m.check_firmware_payload(actual,before)
        for index in (1,2):
            changed=[dict(x) for x in actual];changed[index]['sha256']='a'*64
            with self.assertRaises(ValueError):self.m.check_firmware_payload(changed,before)
        with self.assertRaises(ValueError):self.m.check_firmware_payload(actual[:2],before)


if __name__=='__main__':unittest.main()
