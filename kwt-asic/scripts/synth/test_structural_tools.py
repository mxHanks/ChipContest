"""Checks for structural reporting and narrowly scoped frontend adaptation."""
import importlib.util
from pathlib import Path
import unittest

SPEC=importlib.util.spec_from_file_location('run_structural',Path(__file__).with_name('run_structural.py'))
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class StructuralChecks(unittest.TestCase):
    def test_cast_whitelist(self):
        text, info=MOD.lower_casts("int'(load_addr)+int'(block_index)")
        self.assertEqual(text,"$signed(32'(load_addr))+$signed(32'(block_index))")
        self.assertEqual(info['replacements'],2)
        self.assertIn('NOT_PROVEN',info['four_state_equivalence'])

    def test_reject_unreviewed_cast(self):
        for source in ("int'(other)","int'(load_addr+1)","int ' (load_addr)"):
            with self.assertRaises(ValueError): MOD.lower_casts(source)

    def test_multiport_memory_not_mislabeled_single_port(self):
        params={key:format(value,'032b') for key,value in dict(WIDTH=16,SIZE=32,RD_PORTS=2,WR_PORTS=2,RD_CLK_ENABLE=3,WR_CLK_ENABLE=3).items()}
        report=MOD.summarize({'modules':{'m':{'cells':{'ram':{'type':'$mem_v2','parameters':params}}}}},'m')
        self.assertEqual(report['memory_bits'],512)
        self.assertTrue(report['memories'][0]['requires_bank_partition_or_multiport_mapping'])
        self.assertEqual(len(report['mapping_warnings']),1)

    def test_unknown_parameter_rejected(self):
        with self.assertRaises(ValueError): MOD.integer('000x')

    def test_unelaborated_hierarchy_rejected(self):
        with self.assertRaises(ValueError): MOD.summarize({'modules':{'m':{},'child':{}}},'m')


if __name__=='__main__': unittest.main(verbosity=2)
