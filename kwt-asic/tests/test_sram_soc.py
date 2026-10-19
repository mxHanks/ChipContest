"""The SoC scoreboard must prove write-response/ACK ordering and recovery."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/verify'))
spec=importlib.util.spec_from_file_location('sram_soc_candidate',ROOT/'scripts/verify/run_sram_soc.py')
SOC=importlib.util.module_from_spec(spec);spec.loader.exec_module(SOC)


def complete_log():
    return ('PASS E203_SRAM_TASK task=0 outputs=25344 load_commits=22976 start=100 first_config=120 first_x=140 '
            'last_write_rsp=1500 ack_rsp=1550 end=1600 window_cycles=1501 core_cycles=1200 '
            'output_write_responses=50688 ack_responses=1\n'
            'PASS E203_SRAM_TASK task=1 outputs=25344 load_commits=22976 start=1601 first_config=1620 first_x=1640 '
            'last_write_rsp=3000 ack_rsp=3050 end=3100 window_cycles=1500 core_cycles=1200 '
            'output_write_responses=50688 ack_responses=1\n'
            'PASS E203_SRAM_RECOVERY soft_aborts=1 hard_resets=1 pending_response_reset=1\n'
            'PASS E203_SRAM_SUITE tasks=2 outputs=50688 development_window_cycles=3001 platform=open_fork_development\n')


class SRAMSoCEvidenceTests(unittest.TestCase):
    def validate(self, text):
        self.assertTrue(hasattr(SOC,'validate_soc_log'),'SoC completion/event validator is not implemented')
        return SOC.validate_soc_log(text,2)

    def test_complete_ordered_tasks_and_recovery(self):
        result=self.validate(complete_log())
        self.assertEqual(result['development_window_cycles'],3001)
        self.assertEqual(result['outputs'],50688)

    def test_missing_or_duplicate_final_marker_rejected(self):
        text=complete_log();line=text.splitlines()[-1]
        for modified in (text.replace(line,''),text+line+'\n'):
            with self.subTest(modified=modified):
                with self.assertRaises(ValueError):self.validate(modified)

    def test_task_order_and_output_count_checked(self):
        for modified in (complete_log().replace('task=1','task=0'),complete_log().replace('outputs=25344','outputs=25343',1)):
            with self.assertRaises(ValueError):self.validate(modified)

    def test_start_must_include_configuration(self):
        with self.assertRaises(ValueError):self.validate(complete_log().replace('start=100','start=130'))

    def test_ack_must_follow_last_write_response(self):
        with self.assertRaises(ValueError):self.validate(complete_log().replace('ack_rsp=1550','ack_rsp=1499'))

    def test_final_response_must_follow_ack(self):
        with self.assertRaises(ValueError):self.validate(complete_log().replace('end=1600','end=1500'))

    def test_all_store_responses_and_single_ack_required(self):
        for modified in (complete_log().replace('output_write_responses=50688','output_write_responses=50687',1),
                         complete_log().replace('ack_responses=1','ack_responses=0',1)):
            with self.assertRaises(ValueError):self.validate(modified)

    def test_recovery_cannot_be_inferred_from_normal_tasks(self):
        with self.assertRaises(ValueError):self.validate(complete_log().replace('hard_resets=1','hard_resets=0'))

    def test_window_arithmetic_and_no_overlapping_tasks(self):
        for modified in (complete_log().replace('window_cycles=1501','window_cycles=1500'),
                         complete_log().replace('start=1601','start=1599')):
            with self.assertRaises(ValueError):self.validate(modified)


class SRAMSoCEntryTests(unittest.TestCase):
    def test_staging_uses_verified_image_bytes_with_canonical_names(self):
        self.assertTrue(hasattr(SOC,'stage_verified_vectors'),'verified vector staging is missing')
        images=[{key:(key+str(layer)+'\n').encode() for key in ('x','w','bias','y')} for layer in range(2)]
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'vectors'
            records=SOC.stage_verified_vectors(images,target)
            self.assertEqual(len(records),8)
            for layer,image in enumerate(images):
                for key,payload in image.items():
                    self.assertEqual((target/f'layer_{layer:02d}'/(key+'.mem')).read_bytes(),payload)
            SOC.NATIVE.verify_records(records)
            (target/'layer_00/x.mem').write_bytes(b'changed\n')
            with self.assertRaises(ValueError):SOC.NATIVE.verify_records(records)

    def test_staging_refuses_to_overwrite_previous_vectors(self):
        self.assertTrue(hasattr(SOC,'stage_verified_vectors'),'verified vector staging is missing')
        images=[{key:b'0\n' for key in ('x','w','bias','y')}]
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'vectors'
            SOC.stage_verified_vectors(images,target)
            with self.assertRaises(FileExistsError):SOC.stage_verified_vectors(images,target)
            self.assertEqual((target/'layer_00/x.mem').read_bytes(),b'0\n')

    def command(self, directory, text, code=0):
        return SOC.NATIVE.run_command([sys.executable,'-c',f'print({text!r});raise SystemExit({code})'],
            Path(directory),Path(directory)/'run.log',10,1)

    def test_real_entry_requires_new_markers_and_native_exit(self):
        self.assertTrue(hasattr(SOC,'accept_soc_command'),'new SoC evidence gate is not connected')
        with tempfile.TemporaryDirectory() as directory:
            command=self.command(directory,complete_log())
            self.assertEqual(SOC.accept_soc_command(command,2)['outputs'],50688)
        with tempfile.TemporaryDirectory() as directory:
            command=self.command(directory,complete_log(),1)
            with self.assertRaises(ValueError):SOC.accept_soc_command(command,2)

    def test_executable_and_firmware_identity_bound_before_run(self):
        with tempfile.TemporaryDirectory() as directory:
            firmware=Path(directory)/'firmware.hex';firmware.write_text('old image')
            binary=Path(directory)/'simulation';binary.write_text('old executable')
            inputs=[SOC.NATIVE.record(firmware),SOC.NATIVE.record(binary)]
            command=self.command(directory,complete_log())
            firmware.write_text('new image')
            with self.assertRaises(ValueError):SOC.accept_soc_command(command,2,inputs)

    def test_real_entry_rejects_old_markers_changed_log_and_missing_state(self):
        self.assertTrue(hasattr(SOC,'accept_soc_command'),'new SoC evidence gate is not connected')
        with tempfile.TemporaryDirectory() as directory:
            command=self.command(directory,'PASS E203_KWT_SUITE tasks=2 outputs=50688 full_window_cycles=3001 frequency_mhz=150 platform=open_fork_development')
            with self.assertRaises(ValueError):SOC.accept_soc_command(command,2)
        with tempfile.TemporaryDirectory() as directory:
            command=self.command(directory,complete_log())
            Path(command['log']['path']).write_text(complete_log()+'changed\n')
            with self.assertRaises(ValueError):SOC.accept_soc_command(command,2)
        with tempfile.TemporaryDirectory() as directory:
            command=self.command(directory,complete_log())
            Path(command['native_state']['path']).unlink()
            with self.assertRaises(ValueError):SOC.accept_soc_command(command,2)


if __name__=='__main__':unittest.main()
