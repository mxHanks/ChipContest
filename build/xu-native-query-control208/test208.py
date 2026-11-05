#!/usr/bin/env python3
"""Local actual frozen jobs + no-clobber installer; no server/network/EDA."""
import copy
import importlib.util
import json
from pathlib import Path
import runpy
import shutil
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


class Checks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.home=Path(self.tmp.name)
        self.d=self.home/'Desktop';self.d.mkdir();(self.d/'xu-score-optimization-20261102').mkdir()
        self.transport=json.loads((HERE/'transport208.json').read_text())
        shutil.copyfile(HERE/'runtime208.tar.gz',self.d/self.transport['archive']['name'])
        self.api=load(HERE/'register208.py','xu208_host')
        self.m=load(HERE.parent/'xu-campaign-batch154/control153/xu_experiments.py','xu153_host208')
        self.api.B=Path('/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102')
        self.api.C=self.d/'controller';(self.api.C/'registrations').mkdir(parents=True)
        self.guard=json.loads((HERE/'frozen-jobs208.json').read_text())

    def install(self):
        with mock.patch.object(Path,'home',return_value=self.home):runpy.run_path(str(HERE/'install208.py'))

    def test_actual_jobs_exact_dependency_chain(self):
        jobs,records=self.api.validate_jobs(self.m,self.guard)
        self.assertEqual([j['id']for p,j in jobs],self.api.IDS)
        self.assertEqual(len({j['output_root']for p,j in jobs}),2)
        self.assertTrue(all(j['native']for p,j in jobs))
        self.assertGreater(len(records),15)

    def test_guard_changed_job_rejected(self):
        guard=copy.deepcopy(self.guard);guard['jobs'][0]['sha256']='0'*64
        with self.assertRaises(ValueError):self.api.validate_jobs(self.m,guard)

    def test_duplicate_records_require_same_sha_and_size(self):
        a=dict(path='x',sha256='a',bytes=1)
        self.assertEqual(self.api.merged([a,dict(path='x',sha256='a')]),[a])
        for other in [dict(path='x',sha256='b'),dict(path='x',sha256='a',bytes=2)]:
            with self.assertRaises(ValueError):self.api.merged([a,other])

    def test_conflicting_existing_registration_rejected(self):
        (self.api.C/'registrations/native_query207.json').write_text('{}')
        with self.assertRaises(ValueError):self.api.validate_jobs(self.m,self.guard)

    def test_install_and_idempotent_preserve_bytes(self):
        self.install();before=(self.d/'xu-native-query-control208/register208.py').read_bytes()
        self.install();self.assertEqual(before,(self.d/'xu-native-query-control208/register208.py').read_bytes())
        value=json.loads((self.d/'xu-score-optimization-20261102/followup208-install.json').read_text())
        self.assertEqual(value['new_native_runs'],0)

    def test_conflicting_destination_rejected_before_other_writes(self):
        folder=self.d/'xu-native-query-control208';folder.mkdir();p=folder/'register208.py';p.write_bytes(b'original')
        with self.assertRaises(AssertionError):self.install()
        self.assertEqual(p.read_bytes(),b'original');self.assertFalse((self.d/'xu-native-query207').exists())

    def test_destination_symlink_rejected(self):
        (self.d/'xu-native-query207').symlink_to(self.home,target_is_directory=True)
        with self.assertRaises(AssertionError):self.install()
        self.assertFalse((self.home/'query207.py').exists())

    def test_archive_mutation_rejected_before_writes(self):
        p=self.d/self.transport['archive']['name'];p.write_bytes(b'changed')
        with self.assertRaises(AssertionError):self.install()
        self.assertFalse((self.d/'xu-native-query207').exists())


if __name__=='__main__':unittest.main()
