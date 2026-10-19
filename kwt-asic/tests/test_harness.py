"""Exercise state corruption and portable artifact boundaries."""
import contextlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('harness', Path(__file__).parents[1] / 'scripts/harness.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class HarnessTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'harness').mkdir()
        self.state = self.root / 'harness/tasks.json'
        self.root_patch = patch.object(harness, 'ROOT', self.root)
        self.state_patch = patch.object(harness, 'STATE', self.state)
        self.root_patch.start()
        self.state_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.state_patch.stop)

    def write_tasks(self, tasks):
        self.state.write_text(json.dumps({'tasks': tasks}))

    def run_quiet(self, fn, *args, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*args, **kwargs)

    def test_changed_evidence_invalidates_pass(self):
        p = self.root / 'proof.json'
        p.write_text('{"status":"PASS"}')
        src = self.root / 'core.sv'
        src.write_text('original source')
        self.write_tasks([{'id': 'a', 'status': 'PASS', 'source_bindings': [
            {'path': 'core.sv', 'sha256': harness.digest(src)}], 'evidence': [
            {'path': 'proof.json', 'sha256': harness.digest(p)}]}])
        self.assertEqual(self.run_quiet(harness.validate), 0)
        p.write_text('{"status":"FAIL"}')
        self.assertEqual(self.run_quiet(harness.validate), 1)

    def test_source_change_invalidates_unchanged_success_report(self):
        src = self.root / 'core.sv'
        src.write_text('tested source')
        proof = self.root / 'proof.json'
        proof.write_text('{"status":"PASS"}')
        self.write_tasks([{'id': 'a', 'status': 'PASS', 'source_bindings': [
            {'path': 'core.sv', 'sha256': harness.digest(src)}], 'evidence': [
            {'path': 'proof.json', 'sha256': harness.digest(proof)}]}])
        self.assertEqual(self.run_quiet(harness.validate), 0)
        src.write_text('changed source after PASS')
        self.assertEqual(self.run_quiet(harness.validate), 1)

    def test_cycle_and_premature_pass_rejected(self):
        self.write_tasks([{'id': 'a', 'status': 'PASS', 'depends_on': ['b']},
                          {'id': 'b', 'status': 'TODO', 'depends_on': ['a']}])
        self.assertEqual(self.run_quiet(harness.validate), 1)

    def test_missing_proof_rejected(self):
        self.write_tasks([{'id': 'a', 'status': 'PASS', 'evidence': [
            {'path': '../outside.json', 'sha256': '0' * 64}]}])
        self.assertEqual(self.run_quiet(harness.validate), 1)

    def test_package_preserves_source_and_excludes_private_assets(self):
        self.write_tasks([{'id': 'a', 'status': 'TODO'}])
        for name in ['AGENTS.md', 'PROGRESS.md', 'DECISION.md', 'src/rtl/core.sv',
                     '.env', '.tools/bin/private', 'soc/platform/restricted.lib']:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(name)
        self.assertEqual(self.run_quiet(harness.archive, 'portable', package=True), 0)
        archives = list((self.root / 'artifacts/releases').rglob('*.tar.gz'))
        self.assertEqual(len(archives), 1)
        with tarfile.open(archives[0]) as archive:
            names = archive.getnames()
            self.assertIn('portable/src/rtl/core.sv', names)
            self.assertNotIn('portable/.env', names)
            self.assertNotIn('portable/.tools/bin/private', names)
            self.assertNotIn('portable/soc/platform/restricted.lib', names)
            self.assertEqual(archive.extractfile('portable/src/rtl/core.sv').read(), b'src/rtl/core.sv')

    def test_checkpoint_has_recoverable_source_bytes_and_public_tech_docs(self):
        self.write_tasks([{'id':'a','status':'TODO'}])
        expected=['src/rtl/core.sv','reports/PPA_PRELIMINARY.md','tech/official_sram/README.md']
        for name in expected+['AGENTS.md','PROGRESS.md','DECISION.md','tech/official_sram/private.lib']:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(name)
        self.assertEqual(self.run_quiet(harness.archive,'recoverable'),0)
        checkpoints=list((self.root/'artifacts/checkpoints').iterdir())
        self.assertEqual(len(checkpoints),1)
        output=checkpoints[0]
        for name in expected:
            with self.subTest(name=name):
                saved=output/name
                self.assertTrue(saved.is_file(),'checkpoint contains a hash but cannot restore '+name)
                self.assertEqual(saved.read_text(),name)
        self.assertFalse((output/'tech/official_sram/private.lib').exists())
        (self.root/'src/rtl/core.sv').write_text('later edit')
        self.assertEqual((output/'src/rtl/core.sv').read_text(),'src/rtl/core.sv')


if __name__ == '__main__':
    unittest.main()
