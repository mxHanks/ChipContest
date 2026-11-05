"""Implementation identity/qualification guards; library files are host fixtures only."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_soc_implementation', ROOT/'tools/ppa/xu_soc_implementation.py')
IMPL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPL)
PPA = IMPL.ppa_module(ROOT)


class XuSocImplementationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temporary.name)
        cls.standard = cls.directory/'standard.db'
        cls.sram = cls.directory/'sram.db'
        cls.standard.write_text('HOST STANDARD-CELL LIBRARY FIXTURE ONLY\n')
        cls.sram.write_text('HOST SRAM LIBRARY FIXTURE ONLY\n')
        # This generator supports the pre-S2e f49 baseline only. Exercise its
        # real RTL bytes without checking out or changing the production child.
        cls.source_root = cls.directory/'frozen-baseline'
        for relative in ['tools', 'tests/e203']:
            shutil.copytree(str(ROOT/relative), str(cls.source_root/relative),
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        child = cls.source_root/PPA.SUB
        child.mkdir(parents=True)
        archive = subprocess.check_output(
            ['git', 'archive', '--format=tar', IMPL.FROZEN_E203, 'rtl/e203'],
            cwd=str(ROOT/PPA.SUB))
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            for member in source.getmembers():
                relative = Path(member.name)
                if relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('unsafe frozen baseline source path')
                destination = child/relative
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(source.extractfile(member).read())
                else:
                    raise ValueError('unexpected frozen baseline source type')
        cls.main_commit = PPA.git(ROOT, 'rev-parse', 'HEAD')
        cls.review_dir = cls.directory/'review'
        subprocess.run([sys.executable, str(cls.source_root/'tools/ppa/xu_review_full_soc_clocks.py'),
                        '--out', str(cls.review_dir)], check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, universal_newlines=True)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        original_git = PPA.git

        def fixture_git(root, *arguments):
            # Only the temporary exported tree lacks Git metadata. Inventory,
            # hashes, topology, clock review and preparation remain real.
            root = Path(root).resolve()
            if root in [self.source_root, self.source_root/PPA.SUB]:
                self.assertEqual(arguments, ('rev-parse', 'HEAD'))
                return self.main_commit if root == self.source_root else IMPL.FROZEN_E203
            return original_git(root, *arguments)

        git_patch = mock.patch.object(PPA, 'git', side_effect=fixture_git)
        git_patch.start()
        self.addCleanup(git_patch.stop)
        module_patch = mock.patch.object(IMPL, 'ppa_module', return_value=PPA)
        module_patch.start()
        self.addCleanup(module_patch.stop)

    def generate(self, out, review=None, standard_sha=None, root=None):
        return IMPL.generate(root or self.source_root, out,
                             self.standard, standard_sha or PPA.sha(self.standard),
                             self.sram, PPA.sha(self.sram), review or self.review_dir/'clock-review.json')

    def test_frozen_baseline_manifest_prepares_and_retains_unreviewed_gaps(self):
        out = self.directory/'generated'
        receipt = self.generate(out)
        impl = json.loads((out/'implementation.json').read_text())
        proof = json.loads((out/'mapping-proof.json').read_text())
        self.assertEqual(receipt['status'], 'GENERATED_NOT_QUALIFIED')
        self.assertEqual(receipt['macro_total'], 336)
        self.assertIn('mapped-equivalence:NOT_RUN', receipt['qualification_gaps'])
        self.assertEqual(proof['status'], 'UNREVIEWED')
        self.assertTrue(all(check['status'] == 'NOT_RUN' and check['log'] is None for check in proof['checks'].values()))
        self.assertEqual(impl['source_freeze']['e203_commit'], IMPL.FROZEN_E203)
        self.assertEqual([group['count'] for group in impl['memory_groups']], [32,32,256,16])
        prepared = PPA.prepare(self.source_root, self.directory/'prepared', impl, allow_unqualified=True)
        source_list = (self.directory/'prepared/rtl.f').read_text()
        self.assertNotIn('contract_model', source_list)
        self.assertNotIn('vendor-models', source_list)
        self.assertEqual(prepared['qualification_gaps'], receipt['qualification_gaps'])
        with self.assertRaisesRegex(ValueError, 'allow-unqualified'):
            PPA.checked_implementation(impl, PPA.inventory(self.source_root))

    def test_s2e_source_is_rejected_by_the_legacy_baseline_generator(self):
        self.assertEqual(PPA.git(ROOT/PPA.SUB, 'rev-parse', 'HEAD'),
                         'a0767db69628ef30e53de2d1e93dd0360c0ccf76')
        out = self.directory/'s2e-output'
        with self.assertRaisesRegex(ValueError, 'E203 child commit differs from frozen f49a5fc'):
            self.generate(out, root=ROOT)
        self.assertFalse(out.exists())

    def test_supplied_library_digest_cannot_be_replaced_by_computed_digest(self):
        out = self.directory/'bad-library'
        with self.assertRaisesRegex(ValueError, 'supplied SHA256 differs'):
            self.generate(out, standard_sha='0'*64)
        self.assertFalse(out.exists())

    def test_stale_clock_review_source_is_rejected_before_output(self):
        review = json.loads((self.review_dir/'clock-review.json').read_text())
        review['source_files']['tools/ppa/xu_soc_ppa_top.sv']['sha256'] = '0'*64
        path = self.directory/'stale-clock-review.json'
        path.write_text(json.dumps(review))
        out = self.directory/'stale-review-output'
        with self.assertRaisesRegex(ValueError, 'clock-reviewed source changed'):
            self.generate(out, review=path)
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
