"""Real child processes exercise interrupted-run and false-PASS protection."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'scripts/verify/sram_evidence.py'


class SRAMRunEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), 'durable SRAM command evidence is not implemented')
        spec = importlib.util.spec_from_file_location('sram_evidence', MODULE)
        self.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.helper)
        self.tmp = tempfile.TemporaryDirectory(prefix='kwt-run-evidence-')
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)

    def execute(self, code, timeout=5):
        return self.helper.run_command([sys.executable, '-u', '-c', code], self.out,
                                       self.out/'run.log', timeout, 1)

    def test_native_exit_and_completion_are_separate(self):
        command = self.execute('print("COMPLETE outputs=3")')
        self.assertEqual(command['exit_code'], 0)
        self.assertEqual(json.loads((self.out/'run.command.json').read_text())['status'], 'EXITED')
        self.assertEqual(self.helper.inspect_command(self.out/'run.command.json'), 'EXITED')
        self.assertIsNone(self.helper.completion_error(command, [r'^COMPLETE outputs=3$']))
        self.assertIsNotNone(self.helper.completion_error(command, [r'^MISSING$']))

    def test_zero_exit_without_unique_marker_is_rejected(self):
        command = self.execute('print("COMPLETE"); print("COMPLETE")')
        self.assertIsNotNone(self.helper.completion_error(command, [r'^COMPLETE$']))

    def test_marker_does_not_override_nonzero_exit(self):
        command = self.execute('print("COMPLETE"); raise SystemExit(7)')
        self.assertEqual(command['exit_code'], 7)
        self.assertIsNotNone(self.helper.completion_error(command, [r'^COMPLETE$']))

    def test_report_cannot_override_saved_native_exit(self):
        command = self.execute('print("COMPLETE"); raise SystemExit(7)')
        command['exit_code'] = 0
        self.assertIsNotNone(self.helper.completion_error(command, [r'^COMPLETE$']))

    def test_existing_output_cannot_be_reused(self):
        self.execute('print("COMPLETE")')
        before = (self.out/'run.command.json').read_bytes()
        with self.assertRaises(FileExistsError):
            self.execute('print("replacement")')
        self.assertEqual((self.out/'run.command.json').read_bytes(), before)

    def test_late_failure_after_marker_is_rejected(self):
        command = self.execute('print("COMPLETE"); print("FATAL: late mismatch")')
        self.assertIsNotNone(self.helper.completion_error(command, [r'^COMPLETE$']))

    def test_timeout_saves_terminal_native_status(self):
        command = self.execute('import time; print("started",flush=True); time.sleep(30)', timeout=.15)
        state = json.loads((self.out/'run.command.json').read_text())
        self.assertEqual(state['status'], 'TIMED_OUT')
        self.assertTrue(command['timed_out'])
        self.assertNotEqual(command['exit_code'], 0)
        self.assertIsNotNone(self.helper.completion_error(command, [r'^COMPLETE$']))

    def test_log_changed_after_native_exit_is_rejected(self):
        command = self.execute('print("COMPLETE")')
        (self.out/'run.log').write_text('COMPLETE\nextra\n')
        self.assertIsNotNone(self.helper.completion_error(command, [r'^COMPLETE$']))

    def test_source_change_is_detected_by_identity(self):
        source = self.out/'source.sv'; source.write_text('original\n')
        identity = self.helper.source_identity([source], {'top':'engine','backend':0}, self.out/'source_identity.json')
        self.helper.verify_records(identity['inputs'])
        source.write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.helper.verify_records(identity['inputs'])

    def test_fabricated_running_file_is_not_a_live_process(self):
        state = self.out/'stale.command.json'
        state.write_text(json.dumps({'status':'RUNNING','pid':os.getpid(),'process_start_ticks':'incorrect',
                                    'boot_id':self.helper.process_identity(os.getpid())['boot_id'],
                                    'pid_namespace':str(Path('/proc/self/ns/pid').readlink())}))
        self.assertEqual(self.helper.inspect_command(state), 'NOT_RUNNING')

    def test_foreign_pid_namespace_is_unknown_even_if_pid_matches(self):
        state=self.out/'foreign.command.json'
        value={'status':'RUNNING',**self.helper.process_identity(os.getpid()),'pid_namespace':'pid:[foreign]'}
        state.write_text(json.dumps(value))
        self.assertEqual(self.helper.inspect_command(state),'UNKNOWN')
        value.pop('pid_namespace');state.write_text(json.dumps(value))
        self.assertEqual(self.helper.inspect_command(state),'UNKNOWN')

    def test_missing_state_is_unknown(self):
        self.assertEqual(self.helper.inspect_command(self.out/'missing.json'), 'UNKNOWN')

    def test_missing_executable_saves_launch_failure(self):
        command = self.helper.run_command([str(self.out/'not-an-executable')], self.out, self.out/'run.log', 5, 1)
        self.assertIsNone(command['exit_code'])
        self.assertEqual(self.helper.inspect_command(self.out/'run.command.json'), 'LAUNCH_FAILED')

    def test_signal_saves_interruption_and_reaps_owned_child(self):
        worker = ('import sys; sys.path.insert(0,'+repr(str(MODULE.parent))+'); '
                  'from sram_evidence import run_command; '
                  'run_command([sys.executable,"-u","-c","import time; time.sleep(30)"],'
                  +repr(str(self.out))+','+repr(str(self.out/'run.log'))+',40,1)')
        process = subprocess.Popen([sys.executable,'-c',worker], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic()+5
            state = self.out/'run.command.json'
            while time.monotonic()<deadline:
                if state.exists() and self.helper.inspect_command(state)=='RUNNING': break
                time.sleep(.01)
            self.assertEqual(self.helper.inspect_command(state), 'RUNNING')
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=5)
            data = json.loads(state.read_text())
            self.assertEqual(data['status'], 'INTERRUPTED')
            self.assertNotEqual(data['exit_code'], 0)
            self.assertIsNone(self.helper.process_identity(data['pid']))
        finally:
            if process.poll() is None: process.kill(); process.wait()

    def test_timeout_cleans_nested_detached_process(self):
        pidfile=self.out/'grandchild.pid'
        child='import time; time.sleep(30)'
        code=('import subprocess,sys,time,pathlib; '
              'p=subprocess.Popen([sys.executable,"-c",'+repr(child)+'],start_new_session=True); '
              'pathlib.Path('+repr(str(pidfile))+').write_text(str(p.pid)); time.sleep(30)')
        command=self.execute(code,timeout=.15)
        pid=int(pidfile.read_text())
        try:
            deadline=time.monotonic()+2
            while self.helper.process_identity(pid) is not None and time.monotonic()<deadline:time.sleep(.01)
            self.assertIsNone(self.helper.process_identity(pid),'detached descendant survived parent timeout')
            self.assertTrue(command['timed_out'])
        finally:
            if self.helper.process_identity(pid) is not None:os.kill(pid,signal.SIGKILL)


if __name__ == '__main__': unittest.main()
