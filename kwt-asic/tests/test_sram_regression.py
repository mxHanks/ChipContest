"""The real aggregate gate must inspect child evidence, not just stdout."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/verify'))
spec=importlib.util.spec_from_file_location('sram_regression',ROOT/'scripts/verify/run_sram_regression.py')
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)


class SRAMRegressionGateTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(R,'verify_child_result'),'aggregate child report gate is missing')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.report=self.root/'result.json'

    def command(self,status='PASS',payload=None,code=0,extra=''):
        self.report.write_text(json.dumps({'status':status,**(payload or {})}))
        text=json.dumps({'status':'PASS','report':str(self.report)})
        return R.E.run_command([sys.executable,'-c',f'print({text!r});print({extra!r});raise SystemExit({code})'],
            self.root,self.root/'child.log',10,1)

    def soc_fixture(self):
        # Synthetic parser fixture, never used as RTL/SoC acceptance evidence.
        text=('PASS E203_SRAM_TASK task=0 outputs=25344 load_commits=22976 start=100 first_config=120 first_x=140 '
              'last_write_rsp=1500 ack_rsp=1550 end=1600 window_cycles=1501 core_cycles=1200 '
              'output_write_responses=50688 ack_responses=1\n'
              'PASS E203_SRAM_RECOVERY soft_aborts=1 hard_resets=1 pending_response_reset=1\n'
              'PASS E203_SRAM_SUITE tasks=1 outputs=25344 development_window_cycles=1501 platform=open_fork_development\n')
        inner=R.E.run_command([sys.executable,'-c',f'print({text!r})'],self.root,self.root/'simulation.log',10,1)
        return {'schema':'kwt-sram-soc-v2','configuration':{'tasks':1},'commands':[inner]}

    def test_bare_pass_without_supported_schema_and_execution_is_rejected(self):
        with self.assertRaises(ValueError):R.verify_child_result(self.command(),self.root)

    def test_top_level_pass_cannot_hide_native_failure(self):
        fixture=self.soc_fixture();fixture['commands'][0]['exit_code']=7
        with self.assertRaises(ValueError):R.verify_child_result(self.command(payload=fixture),self.root)

    def test_top_level_pass_cannot_hide_missing_design_completion(self):
        inner=R.E.run_command([sys.executable,'-c','print("only started")'],self.root,self.root/'simulation.log',10,1)
        fixture={'schema':'kwt-sram-soc-v2','configuration':{'tasks':2},'commands':[inner]}
        with self.assertRaises(ValueError):R.verify_child_result(self.command(payload=fixture),self.root)

    def test_complete_report_must_match_requested_tasks_and_backend(self):
        fixture=self.soc_fixture();fixture['configuration']['backend']='behavioral'
        command=self.command(payload=fixture)
        for expected in ({'schema':'kwt-sram-soc-v2','configuration':{'tasks':12}},
                         {'schema':'kwt-sram-soc-v2','configuration':{'backend':'ff'}}):
            with self.subTest(expected=expected):
                with self.assertRaises(ValueError):R.verify_child_result(command,self.root,expected)

    def test_reads_child_status_instead_of_trusting_stdout(self):
        command=self.command('FAIL')
        with self.assertRaises(ValueError):R.verify_child_result(command,self.root)

    def test_rechecks_hashed_child_inputs_and_reports(self):
        source=self.root/'source.sv';source.write_text('first')
        command=self.command(payload={**self.soc_fixture(),'inputs':[R.E.record(source)]})
        result=R.verify_child_result(command,self.root)
        self.assertEqual(result['result']['path'],str(self.report))
        source.write_text('changed')
        with self.assertRaises(ValueError):R.verify_child_result(command,self.root)

    def test_native_failure_and_duplicate_summary_rejected(self):
        command=self.command(code=1)
        with self.assertRaises(ValueError):R.verify_child_result(command,self.root)
        (self.root/'child.log').unlink();(self.root/'child.command.json').unlink()
        summary=json.dumps({'status':'PASS','report':str(self.report)})
        command=self.command(extra=summary)
        with self.assertRaises(ValueError):R.verify_child_result(command,self.root)

    def test_report_outside_run_root_rejected(self):
        command=self.command()
        with self.assertRaises(ValueError):R.verify_child_result(command,self.root/'different-run')


if __name__=='__main__':unittest.main()
