import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('resize_eco',ROOT/'scripts/synth/run_sram_resize_candidate.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class SlewRepair(unittest.TestCase):
    def design(self):
        cells={'gate':{'type':'NOR4_X1','connections':{'A1':[1],'A2':[2],'A3':[3],'A4':[4],'ZN':[5]},
                       'port_directions':{'A1':'input','A2':'input','A3':'input','A4':'input','ZN':'output'}}}
        for i in range(10):cells['sink'+str(i)]={'type':'BUF_X1' if i<2 else 'NAND2_X1','connections':{'A':[5]},'port_directions':{'A':'input'}}
        return {'modules':{M.TOP:{'cells':cells}}}

    def test_only_unique_measured_driver_strength_changes(self):
        old=self.design();new,change=M.repair_measured_nor4(old)
        self.assertEqual(old['modules'][M.TOP]['cells']['gate']['type'],'NOR4_X1')
        self.assertEqual(new['modules'][M.TOP]['cells']['gate']['type'],'NOR4_X2')
        self.assertEqual(change['before']['connections'],change['after']['connections'])
        self.assertEqual(len(change['loads']),10)

    def test_missing_or_ambiguous_topology_rejected(self):
        old=self.design();old['modules'][M.TOP]['cells'].pop('sink0')
        with self.assertRaises(ValueError):M.repair_measured_nor4(old)
        old=self.design();old['modules'][M.TOP]['cells']['other']=dict(old['modules'][M.TOP]['cells']['gate'])
        with self.assertRaises(ValueError):M.repair_measured_nor4(old)
