import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mapped_replay_reader',ROOT/'scripts/verify/run_sram_mapped_replay.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class RecordCompatibility(unittest.TestCase):
    def test_same_actual_identity_can_use_two_length_spellings(self):
        a={'path':str(ROOT/'sim/kwt_icb_pair_checker.sv'),'sha256':'a'*64,'bytes':8}
        b={'path':a['path'],'sha256':a['sha256'],'size_bytes':8}
        self.assertEqual(M.compatible_record_map([a,b]),{a['path']:b})
        self.assertEqual(M.compatible_record_map([a,dict(b,project_relative_path='sim/kwt_icb_pair_checker.sv')]),{a['path']:b})

    def test_different_hash_length_or_unsupported_fields_rejected(self):
        a={'path':str(ROOT/'sim/kwt_icb_pair_checker.sv'),'sha256':'a'*64,'size_bytes':8}
        for b in [dict(a,sha256='b'*64),dict(a,size_bytes=7),dict(a,bytes=9),dict(a,unknown=True),
                  {'path':a['path'],'sha256':a['sha256']},dict(a,size_bytes=True),
                  dict(a,project_relative_path='sim/wrong.sv'),dict(a,project_relative_path='../wrong.sv')]:
            with self.assertRaises(ValueError):M.compatible_record_map([a,b])
