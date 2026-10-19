"""Parser scope tests; synthetic logs do not establish HDL/official results."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class SRAMAdapterSystemTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('adapter_system_subject',ROOT/'scripts/verify/run_sram_adapter_system.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.command={'status':'EXITED','exit_code':0,'timed_out':False,'interrupted':False}
        self.icb=('ICB_ADAPTER_PASS transactions=193938 hold_checks=86 actual_core_outputs=25348 complete_tasks=1 aborted_tasks=1\n'
                  'PASS ICB_BACKEND3_MONITOR accepted_outputs=25348 response_holds=86 accepted_commands=193939 accepted_responses=193938 reset_discarded_responses=1\n')

    def test_icb_accepts_actual_handshake_counts_and_one_reset_discard(self):
        result=self.m.accept_icb(self.command,self.icb)
        self.assertEqual(result['accepted_core_outputs'],25348)
        self.assertEqual(result['accepted_commands'],result['accepted_responses']+1)
        self.assertEqual(result['reset_discarded_responses'],1)

    def test_icb_rejects_missing_wrong_duplicate_or_contaminated_markers(self):
        bad=['',self.icb.splitlines()[0]+'\n',self.icb+self.icb,
             self.icb.replace('accepted_outputs=25348','accepted_outputs=25344'),
             self.icb.replace('accepted_responses=193938','accepted_responses=193937'),
             self.icb.replace('accepted_commands=193939','accepted_commands=193938'),
             self.icb.replace('response_holds=86','response_holds=85'),
             self.icb.replace('reset_discarded_responses=1','reset_discarded_responses=0'),
             self.icb+'INFO ICB_ADAPTER_PASS incomplete\n',
             self.icb+'PASS ICB_BACKEND3_MONITOR malformed\n',
             self.icb+'FATAL: fake.sv:3: unrelated\n']
        for text in bad:
            with self.subTest(text=text),self.assertRaises(ValueError):self.m.accept_icb(self.command,text)

    def test_icb_requires_clean_explicit_native_fields(self):
        bad=[dict(self.command,exit_code=False),dict(self.command,exit_code=-11),
             dict(self.command,status='RUNNING'),dict(self.command,timed_out=True),
             dict(self.command,interrupted=None)]
        for key in self.command:
            item=dict(self.command);del item[key];bad.append(item)
        for command in bad:
            with self.subTest(command=command),self.assertRaises(ValueError):self.m.accept_icb(command,self.icb)

    def core_fixture(self):
        # Source-bundled tiny format fixture; no raw artifacts prerequisite.
        return {'engine':'rowpair','lanes':8,'tasks':2,'pipe_mul':1,'result_buffers':2,'stalls':'none'}, (ROOT/'tests/fixtures/sram-core-format.log').read_text()

    def test_core_reader_preserves_existing_full_conservation_contract(self):
        config,text=self.core_fixture();coverage=self.m.accept_core(self.command,text,config)
        self.assertEqual(coverage['suite']['tasks'],2)
        self.assertEqual(coverage['suite']['outputs'],50688)
        self.assertEqual(coverage['suite']['reset_interrupts'],3)

    def test_core_rejects_extra_families_and_wrong_conservation(self):
        config,text=self.core_fixture()
        for changed in (text+'INFO PASS ROWPAIR_BENCH_TASK malformed\n',
                        text+'PASS ROWPAIR_BENCH_SUITE malformed\n',
                        text.replace('outputs=25344','outputs=25343',1),
                        text.replace('resets=3','resets=2')):
            with self.subTest(changed=changed[-80:]),self.assertRaises(ValueError):self.m.accept_core(self.command,changed,config)

    def test_core_rejects_incomplete_native_even_with_prior_good_log(self):
        config,text=self.core_fixture()
        for command in (dict(self.command,exit_code=1),dict(self.command,interrupted=True),dict(self.command,timed_out=0)):
            with self.subTest(command=command),self.assertRaises(ValueError):self.m.accept_core(command,text,config)


if __name__=='__main__':unittest.main()
