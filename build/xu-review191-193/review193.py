#!/usr/bin/env python3
"""Independent xu193 integration review of the frozen xu191 exporter."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
P = REPO / 'build/xu-two-candidate-finalpack191'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class Review(unittest.TestCase):
    def setUp(self):
        harness = load(P / 'test191.py', 'xu193_original_fixture')
        self.fixture = harness.Checks()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.m = self.fixture.m
        self.checker = load(REPO / 'build/xu-two-candidate-export171/check_unpack171.py', 'xu193_safe171')

    def test_safe171_inspect_and_unpack_real191_package(self):
        self.assertEqual(self.fixture.runpack(), 0)
        archive = self.m.ARCHIVE
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        report, declared = self.checker.inspect(archive, digest)
        self.assertEqual(report['status'], 'VERIFIED_ALL_PACKAGED_BYTES_NOT_QUALIFIED')
        output = self.fixture.d / 'checked193'
        extracted = self.checker.unpack(archive, output, digest)
        self.assertEqual(extracted['payload_files'], len(declared))
        for name, row in declared.items():
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), row['sha256'])
        self.assertEqual(json.loads((output / 'selection191.json').read_text())['jobs'], self.m.JOBS)
        self.assertNotIn('s2e_final155_power12_166', self.m.JOBS)

    def test_scope_bodies_are_excluded_and_reports_retained(self):
        for suffix in ['.lib', '.sv', '.v', '.db', '.saif', '.sdf', '.sdc', '.c', '.py', '.pdf']:
            (self.fixture.root / ('vendor' + suffix)).write_text('FORBIDDEN_SOURCE_BODY')
        (self.fixture.root / 'raw.rpt').write_text('NATIVE_DIAGNOSTIC_REPORT')
        self.assertEqual(self.fixture.runpack(), 0)
        rows = self.fixture.contents()
        self.assertEqual(rows[self.m.ROOTS[0] + '/raw.rpt'], b'NATIVE_DIAGNOSTIC_REPORT')
        self.assertFalse(any(b'FORBIDDEN_SOURCE_BODY' in body for body in rows.values()))

    def test_blocked_parent_rejected_and_failure_preserved(self):
        folder = self.fixture.root / 'private-manuals'; folder.mkdir()
        (folder / 'manual.txt').write_text('PRIVATE_MANUAL_BODY')
        self.assertEqual(self.fixture.runpack(), 1)
        self.assertFalse(self.m.ARCHIVE.exists())
        self.assertEqual(json.loads((self.m.OUT / 'state.json').read_text())['status'], self.m.FAIL)
        self.assertTrue(self.m.ARCHIVE.with_name(self.m.ARCHIVE.name + '.failure171.json').is_file())
        self.assertTrue((folder / 'manual.txt').is_file())
        # safe_name rejects blocked archive components before Snapshot.add
        # opens a file; the path is retained in the terminal error itself.
        self.assertIn('private-manuals/manual.txt', json.loads((self.m.OUT / 'state.json').read_text())['error'])

    def test_symlink_rejection_path_receipt(self):
        p = self.fixture.root / 'bad.rpt'; p.symlink_to(self.fixture.root / 'state.json')
        self.assertEqual(self.fixture.runpack(), 1)
        rejected = json.loads((self.m.OUT / 'source-rejections191.json').read_text())
        self.assertEqual(rejected['qualification'], 'NOT_QUALIFIED')
        self.assertEqual(rejected['rejected_sources'][0]['source_path'], str(p))
        self.assertFalse(self.m.ARCHIVE.exists())

    def test_large_report_hash_only(self):
        p = self.fixture.root / 'large.rpt'
        with p.open('wb') as stream:
            for _ in range(17): stream.write(b'z' * 1048576)
        self.assertEqual(self.fixture.runpack(), 0)
        rows = self.fixture.contents()
        self.assertNotIn(self.m.ROOTS[0] + '/large.rpt', rows)
        omitted = json.loads(rows['snapshot171.json'])['omitted_originals']
        target = [row for row in omitted if row['archive_path'].endswith('/large.rpt')]
        self.assertEqual(len(target), 1)
        self.assertEqual(target[0]['observed_bytes_sha256'], hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertTrue(target[0]['metadata_unchanged_during_read'])

    def test_frozen83012fd_bytes_and_manifest(self):
        manifest = json.loads((P / 'manifest191.json').read_text())
        for row in manifest['files']:
            raw = (P / row['path']).read_bytes()
            old = subprocess.check_output(['git', 'show', '83012fd:build/xu-two-candidate-finalpack191/' + row['path']], cwd=str(REPO))
            self.assertEqual(raw, old)
            self.assertEqual(len(raw), row['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'])
        self.assertEqual(self.m.EXPORTER_SHA, hashlib.sha256(self.m.EXPORTER.read_bytes()).hexdigest())

    def test_controller_dependency_and_identity_contract(self):
        job = json.loads((P / 'two_candidate_finalpack191.json').read_text())
        self.assertIs(job['native'], True)
        self.assertEqual(job['launch_mode'], 'direct')
        self.assertEqual(job['output_root'], job['process_contains'])
        self.assertEqual(job['argv'][-2:], ['--out', job['output_root']])
        self.assertEqual(job['result_state'], job['output_root'] + '/state.json')
        self.assertEqual(job['dependencies'], [dict(id=k, policy='terminal') for k in [
            's2c_readonly177', 's2e_coverage186', 's2c_common_full12_190']])
        self.assertEqual(job['success_statuses'], [self.m.SUCCESS])
        self.assertEqual(job['failure_statuses'], [self.m.FAIL])
        self.assertEqual([r['sha256'] for r in job['frozen_inputs']], [
            hashlib.sha256((P / 'finalpack191.py').read_bytes()).hexdigest(), self.m.EXPORTER_SHA])


if __name__ == '__main__':
    unittest.main(verbosity=2)
