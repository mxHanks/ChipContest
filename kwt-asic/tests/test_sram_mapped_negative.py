import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mapped_negative',ROOT/'scripts/verify/run_sram_mapped_negative.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class NegativeGolden(unittest.TestCase):
    def test_private_mutation_changes_only_first_output_bit(self):
        original=b'000000000000\n'+b'ffffffffffff\n'*25343
        changed=M.flip_first_golden_bit(original)
        self.assertEqual(changed,b'000000000001\n'+b'ffffffffffff\n'*25343)
        self.assertEqual(original[:12],b'000000000000')

    def test_incomplete_or_unknown_golden_rejected(self):
        for bad in (b'0\n',b'xxxxxxxxxxxx\n'*25344,b'000000000000\n'*25343):
            with self.assertRaises(ValueError):M.flip_first_golden_bit(bad)
