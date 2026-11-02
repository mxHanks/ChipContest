"""Implementation identity/qualification guards; library files are host fixtures only."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

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
        cls.review_dir = cls.directory/'review'
        subprocess.run([sys.executable, str(ROOT/'tools/ppa/xu_review_full_soc_clocks.py'),
                        '--out', str(cls.review_dir)], check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, universal_newlines=True)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def generate(self, out, review=None, standard_sha=None):
        return IMPL.generate(ROOT, out, self.standard, standard_sha or PPA.sha(self.standard),
                             self.sram, PPA.sha(self.sram), review or self.review_dir/'clock-review.json')

    def test_actual_source_manifest_prepares_and_retains_unreviewed_gaps(self):
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
        prepared = PPA.prepare(ROOT, self.directory/'prepared', impl, allow_unqualified=True)
        source_list = (self.directory/'prepared/rtl.f').read_text()
        self.assertNotIn('contract_model', source_list)
        self.assertNotIn('vendor-models', source_list)
        self.assertEqual(prepared['qualification_gaps'], receipt['qualification_gaps'])
        with self.assertRaisesRegex(ValueError, 'allow-unqualified'):
            PPA.checked_implementation(impl, PPA.inventory(ROOT))

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
