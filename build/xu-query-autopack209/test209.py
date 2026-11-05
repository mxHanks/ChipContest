#!/usr/bin/env python3
"""Exercise real Snapshot path/hash/no-clobber semantics with a local fixture."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,str(path))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class Checks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.d=Path(self.tmp.name)/'Desktop';self.d.mkdir();self.b=self.d/'xu-score-optimization-20261102';self.b.mkdir()
        self.m=load(HERE/'autopack209.py','xu209_test')
        self.m.D=self.d;self.m.B=self.b;self.m.OUT=self.b/'two-candidate-finalpack-20261105-209'
        self.m.ARCHIVE=self.b/'xu-server-two-candidate-final-20261105-209.tar.xz'
        source=self.d/'xu-query-autopack209/autopack209.py';source.parent.mkdir();source.write_bytes((HERE/'autopack209.py').read_bytes())
        self.m.__file__=str(source)
        self.m.EXPORTER=self.d/'exporter171.py'
        self.m.EXPORTER.write_bytes((HERE.parent/'xu-two-candidate-export171/exporter171.py').read_bytes())
        root=self.b/self.m.ROOTS[0];root.mkdir();self.root=root
        (root/'state.json').write_text('{"status":"FAIL_OWN_S2C_READONLY177_NOT_QUALIFIED"}\n')
        (root/'query-status.tsv').write_text('report\tcatch_code\tmessage\nraw.rpt\t1\tnative failure retained\n')
        (root/'vendor.db').write_bytes(b'NO LIBRARY BODY')
        (root/'model.v').write_bytes(b'NO MODEL BODY')

    def runpack(self):
        with mock.patch('sys.stdout',new=io.StringIO()),mock.patch('sys.stderr',new=io.StringIO()):
            return self.m.run(self.m.OUT)

    def contents(self):
        with tarfile.open(str(self.m.ARCHIVE),'r:xz')as t:return {n:t.extractfile(n).read()for n in t.getnames()}

    def test_failed_stage_and_missing_stages_preserved(self):
        self.assertEqual(self.runpack(),0);rows=self.contents()
        self.assertIn('FAIL_OWN_S2C',rows[self.m.ROOTS[0]+'/state.json'].decode())
        snapshot=json.loads(rows['snapshot171.json']);self.assertTrue(snapshot['missing_at_observation'])
        self.assertFalse(snapshot['rejected_sources']);self.assertTrue(all(x['metadata_unchanged_during_read']for x in snapshot['captures']))

    def test_model_and_library_bodies_excluded(self):
        self.assertEqual(self.runpack(),0)
        self.assertFalse(any(n.endswith(('.db','.v'))for n in self.contents()))

    def test_pin_body_hash_only(self):
        (self.root/'sram-pins-after.rpt').write_bytes(b'pin secret'*100)
        self.assertEqual(self.runpack(),0);rows=self.contents();snapshot=json.loads(rows['snapshot171.json'])
        self.assertFalse(any(n.endswith('sram-pins-after.rpt')for n in rows))
        self.assertEqual(snapshot['omitted_originals'][0]['bytes_observed'],1000)

    def test_symlink_source_rejects_export(self):
        (self.root/'bad.rpt').symlink_to(self.root/'state.json')
        self.assertEqual(self.runpack(),1);self.assertFalse(self.m.ARCHIVE.exists())
        self.assertEqual(json.loads((self.m.OUT/'state.json').read_text())['status'],self.m.FAIL)
        detail=json.loads((self.m.OUT/'source-rejections209.json').read_text())
        self.assertIn('bad.rpt',detail['rejected_sources'][0]['source_path'])

    def test_subdirectory_symlink_rejected(self):
        (self.root/'nested').symlink_to(self.d,target_is_directory=True)
        self.assertEqual(self.runpack(),1);self.assertFalse(self.m.ARCHIVE.exists())

    def test_output_not_overwritten(self):
        self.assertEqual(self.runpack(),0);before=self.m.ARCHIVE.read_bytes()
        with self.assertRaises(ValueError):self.runpack()
        self.assertEqual(self.m.ARCHIVE.read_bytes(),before)

    def test_existing_archive_preserved(self):
        self.m.ARCHIVE.write_bytes(b'original')
        self.assertEqual(self.runpack(),1);self.assertEqual(self.m.ARCHIVE.read_bytes(),b'original')

    def test_exporter_mutation_rejected(self):
        self.m.EXPORTER.write_bytes(b'invalid')
        self.assertEqual(self.runpack(),1);self.assertFalse(self.m.ARCHIVE.exists())

    def test_every_payload_hash_and_size(self):
        self.assertEqual(self.runpack(),0);rows=self.contents();manifest=json.loads(rows.pop('manifest.json'))
        self.assertEqual(set(rows),{x['path']for x in manifest['files']})
        for row in manifest['files']:
            raw=rows[row['path']];self.assertEqual(len(raw),row['bytes'])
            self.assertEqual(__import__('hashlib').sha256(raw).hexdigest(),row['sha256'])


if __name__=='__main__':unittest.main()
