#!/usr/bin/env python3
"""Independent xu211 integration review of the frozen xu209 exporter."""
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
P = REPO / 'build/xu-query-autopack209'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class Review(unittest.TestCase):
    def setUp(self):
        harness = load(P / 'test209.py', 'xu211_original_fixture')
        self.fixture = harness.Checks()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.m = self.fixture.m
        self.checker = load(REPO / 'build/xu-two-candidate-export171/check_unpack171.py', 'xu211_safe171')

    def test_safe171_inspect_and_unpack_actual209_fixture_archive(self):
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
        self.assertEqual(json.loads((output / 'selection209.json').read_text())['jobs'], self.m.JOBS)
        self.assertEqual(self.m.JOBS, ['native_query207'])
        self.assertEqual(self.m.ROOTS, ['native-query-replay-20261105-207'])

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
        rejected = json.loads((self.m.OUT / 'source-rejections209.json').read_text())
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

    def test_frozenaa37599_bytes_and_manifest(self):
        manifest = json.loads((P / 'manifest209.json').read_text())
        for row in manifest['files']:
            raw = (P / row['path']).read_bytes()
            old = subprocess.check_output(['git', 'show', 'aa37599:build/xu-query-autopack209/' + row['path']], cwd=str(REPO))
            self.assertEqual(raw, old)
            self.assertEqual(len(raw), row['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'])
        self.assertEqual(self.m.EXPORTER_SHA, hashlib.sha256(self.m.EXPORTER.read_bytes()).hexdigest())

    def test_controller_dependency_and_identity_contract(self):
        job = json.loads((P / 'two_candidate_finalpack209.json').read_text())
        self.assertIs(job['native'], True)
        self.assertEqual(job['launch_mode'], 'direct')
        self.assertEqual(job['output_root'], job['process_contains'])
        self.assertEqual(job['argv'][-2:], ['--out', job['output_root']])
        self.assertEqual(job['result_state'], job['output_root'] + '/state.json')
        self.assertEqual(job['dependencies'], [dict(id='native_query207', policy='terminal')])
        self.assertEqual(job['success_statuses'], [self.m.SUCCESS])
        self.assertEqual(job['failure_statuses'], [self.m.FAIL])
        self.assertEqual([r['sha256'] for r in job['frozen_inputs']], [
            hashlib.sha256((P / 'autopack209.py').read_bytes()).hexdigest(), self.m.EXPORTER_SHA])

    def test_only_declared191_namespace_and_scope_changes(self):
        old = (REPO / 'build/xu-two-candidate-finalpack191/finalpack191.py').read_text()
        old_jobs = "JOBS=['s2c_readonly177','s2e_coverage186','s2c_common_preflight190','s2c_common_full12_190']"
        old_roots = "ROOTS=['s2c-own9c16-readonly-20261105-177',\n       's2e-own155-coverage-readonly-20261105-186',\n       's2c-common-scope-preflight-20261105-190',\n       's2c-common-scope-power12-20261105-190']"
        self.assertEqual(old.count(old_jobs), 1); self.assertEqual(old.count(old_roots), 1)
        expected = old.replace(old_jobs, "JOBS=['native_query207']").replace(old_roots, "ROOTS=['native-query-replay-20261105-207']")
        expected = expected.replace('191', '209').replace('xu-two-candidate-finalpack209/finalpack209.py', 'xu-query-autopack209/autopack209.py')
        # Namespace renaming never changes the frozen171 digest, which itself
        # happens to contain the decimal substring191.
        expected = expected.replace(self.m.EXPORTER_SHA.replace('191', '209'), self.m.EXPORTER_SHA)
        expected = expected.replace('xu-two-candidate-finalpack209-state-v1', 'xu-query-autopack209-state-v1')
        receipts = '''    s.add(s.base/'two-candidate-followup-registration-20261105-208.json',
          'two-candidate-followup-registration-20261105-208.json')
    s.add(s.base/'followup208-install.json','followup208-install.json')
    s.names(s.desktop/'xu-native-query-control208','desktop/xu-native-query-control208',
            ['register208.py','frozen-jobs208.json'],s.desktop)
'''
        expected = expected.replace('    for root in ROOTS:\n', receipts + '    for root in ROOTS:\n')

        self.assertEqual((P / 'autopack209.py').read_text(), expected)

    def test_namespace_cannot_capture_other_candidate_roots(self):
        foreign = self.fixture.b / 's2e-final155-power12-20261105-166'
        foreign.mkdir(); (foreign / 'report.rpt').write_text('OTHER_EXPERIMENT_BODY')
        self.assertEqual(self.fixture.runpack(), 0)
        self.assertFalse(any(b'OTHER_EXPERIMENT_BODY' in data for data in self.fixture.contents().values()))
        self.assertEqual(self.m.OUT.name, 'two-candidate-finalpack-20261105-209')
        self.assertEqual(self.m.ARCHIVE.name, 'xu-server-two-candidate-final-20261105-209.tar.xz')

    def test_208_original_receipts_and_frozen_registration_are_copied(self):
        expected = {}
        for name in ['two-candidate-followup-registration-20261105-208.json', 'followup208-install.json']:
            (self.fixture.b / name).write_text('{"original":"preserved208"}\n')
            expected[name] = (self.fixture.b / name).read_bytes()
        root = self.fixture.d / 'xu-native-query-control208'; root.mkdir()
        for name in ['register208.py', 'frozen-jobs208.json']:
            (root / name).write_text('# ORIGINAL208_REVIEW_FIXTURE\n')
            expected['desktop/xu-native-query-control208/' + name] = (root / name).read_bytes()
        self.assertEqual(self.fixture.runpack(), 0); rows = self.fixture.contents()
        for name, raw in expected.items(): self.assertEqual(rows[name], raw)

    def test_208_missing_receipts_are_explicit(self):
        self.assertEqual(self.fixture.runpack(), 0); rows = self.fixture.contents()
        missing = {r['archive_path'] for r in json.loads(rows['snapshot171.json'])['missing_at_observation']}
        self.assertTrue({'two-candidate-followup-registration-20261105-208.json', 'followup208-install.json',
             'desktop/xu-native-query-control208/register208.py', 'desktop/xu-native-query-control208/frozen-jobs208.json'} <= missing)

    def test_208_receipt_symlink_rejected(self):
        path = self.fixture.b / 'followup208-install.json'; path.symlink_to(self.fixture.root / 'state.json')
        self.assertEqual(self.fixture.runpack(), 1)
        self.assertFalse(self.m.ARCHIVE.exists())
        rejected = json.loads((self.m.OUT / 'source-rejections209.json').read_text())
        self.assertTrue(any(r['source_path'] == str(path) for r in rejected['rejected_sources']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
