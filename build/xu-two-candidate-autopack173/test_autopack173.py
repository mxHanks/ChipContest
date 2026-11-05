#!/usr/bin/env python3
"""Local mocks only. No server job, native EDA, production output or qualification."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import export_job173 as w

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent


class Test173(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='xu173-MOCK-ONLY-');self.addCleanup(self.temp.cleanup)
        self.d=Path(self.temp.name)/'Desktop';self.b=self.d/'xu-score-optimization-20261102';self.b.mkdir(parents=True)
        self.out=self.b/'two-candidate-autopack-20261105-173';self.archive=self.b/'xu-server-two-candidate-20261105-171.tar.xz'
        self.exporter=self.d/'exporter171.py';shutil.copyfile(ROOT/'build/xu-two-candidate-export171/exporter171.py',self.exporter)
        self.patches=patch.multiple(w,D=self.d,B=self.b,OUT=self.out,ARCHIVE=self.archive,EXPORTER=self.exporter)
        self.patches.start();self.addCleanup(self.patches.stop)

    def mock_export(self,base,desktop,path,limit):
        self.assertEqual((base,desktop,path,limit),(self.b,self.d,self.archive,16*1024*1024))
        self.called_pid=os.getpid();path.write_bytes(b'MOCK_EXPORT_ONLY_NOT_NATIVE_NOT_QUALIFIED')
        row=w.identity(path);row.update(files=1,payload_bytes=1);return row

    def result(self):return json.loads((self.out/'state.json').read_text())

    def test_same_pid_mock_success_and_fixed_frozen_input(self):
        with patch.object(w,'load_exporter',return_value=SimpleNamespace(export=self.mock_export)):
            self.assertEqual(w.run(self.out),0)
        s=self.result();self.assertEqual(s['status'],w.SUCCESS);self.assertEqual(s['pid'],self.called_pid)
        self.assertEqual(s['qualification'],'NOT_QUALIFIED');self.assertTrue(s['inputs_equal_before_after'])
        self.assertEqual(s['new_experiments_launched'],0)

    def test_real_module_load_checks_sha_without_export(self):
        module=w.load_exporter();self.assertTrue(callable(module.export));self.assertFalse(self.archive.exists())

    def test_mock_exception_retains_failure_state(self):
        def fail(*unused):raise RuntimeError('MOCK_EXPORT_FAILURE_NOT_NATIVE')
        with patch.object(w,'load_exporter',return_value=SimpleNamespace(export=fail)):
            self.assertEqual(w.run(self.out),1)
        self.assertEqual(self.result()['status'],w.FAIL)

    def test_frozen_exporter_change_rejected_before_mock_call(self):
        self.exporter.write_text('changed')
        with patch.object(w,'load_exporter')as load:self.assertEqual(w.run(self.out),1);load.assert_not_called()
        self.assertEqual(self.result()['status'],w.FAIL)

    def test_existing_archive_preserved(self):
        self.archive.write_bytes(b'ORIGINAL_KEEP')
        self.assertEqual(w.run(self.out),1);self.assertEqual(self.archive.read_bytes(),b'ORIGINAL_KEEP')
        self.assertEqual(self.result()['status'],w.FAIL)

    def test_existing_output_not_overwritten_or_restarted(self):
        self.out.mkdir();state=self.out/'state.json';state.write_text('ORIGINAL_KEEP')
        with self.assertRaises(ValueError):w.run(self.out)
        self.assertEqual(state.read_text(),'ORIGINAL_KEEP')

    def test_mock_input_mutation_cannot_succeed(self):
        def mutate(*args):
            result=self.mock_export(*args);self.exporter.write_text('mutated after mock export');return result
        with patch.object(w,'load_exporter',return_value=SimpleNamespace(export=mutate)):
            self.assertEqual(w.run(self.out),1)
        self.assertEqual(self.result()['status'],w.FAIL);self.assertTrue(self.archive.is_file())

    def test_mock_wrong_package_identity_cannot_succeed(self):
        def wrong(*args):
            result=self.mock_export(*args);result['sha256']='0'*64;return result
        with patch.object(w,'load_exporter',return_value=SimpleNamespace(export=wrong)):
            self.assertEqual(w.run(self.out),1)
        self.assertEqual(self.result()['status'],w.FAIL)

    def test_job_validates_frozen153_and_unique_marker(self):
        path=ROOT/'build/xu-campaign-batch154/control153/xu_experiments.py'
        spec=importlib.util.spec_from_file_location('xu173_test_original153',str(path));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        job=m.validate_job(json.loads((HERE/'two_candidate_autopack173.json').read_text()))
        self.assertEqual(job['dependencies'],[dict(id='s2c_unknown167',policy='terminal'),dict(id='s2e_final155_power12_166',policy='terminal'),dict(id='s2e_streamaudit164',policy='success')])
        self.assertTrue(job['native']);self.assertEqual(job['output_root'],job['process_contains'])
        self.assertEqual(job['argv'][-2:],['--out',job['output_root']]);self.assertEqual(job['argv'].count(job['output_root']),1)
        self.assertEqual(job['success_statuses'],[w.SUCCESS]);self.assertEqual(job['failure_statuses'],[w.FAIL])
        self.assertEqual(job['frozen_inputs'][0]['sha256'],hashlib.sha256((HERE/'export_job173.py').read_bytes()).hexdigest())
        self.assertEqual(job['frozen_inputs'][1]['sha256'],w.EXPORTER_SHA)

    def test_no_direct_launch_init_signal_in_registrar(self):
        source=(HERE/'register173.py').read_text();tree=ast.parse(source,feature_version=6)
        calls=[ast.unparse(n.func)for n in ast.walk(tree)if isinstance(n,ast.Call)]
        self.assertIn('m.register',calls)
        for forbidden in ['m.initialize','m.run','os.kill','os.killpg','subprocess.Popen','subprocess.run','os.system']:
            self.assertNotIn(forbidden,calls)
        ast.parse((HERE/'export_job173.py').read_text(),feature_version=6)


if __name__=='__main__':unittest.main(verbosity=2)
