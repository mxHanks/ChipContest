import importlib.util
from copy import deepcopy
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cap_eco',ROOT/'scripts/synth/run_sram_cap_candidate.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class MeasuredCapRepair(unittest.TestCase):
    def fixture(self):
        cells={};targets=[]
        for i in range(4):
            name='n'+str(i);kind='NOR3_X1' if i%2 else 'NOR4_X1'
            c={'type':kind,'connections':{'ZN':[i*10+1],'A1':[i*10+2]},'parameters':{},'port_directions':{'ZN':'output','A1':'input'}}
            cells[name]=c
            targets.append({'instance':name,'expected_cell':deepcopy(c),'replacement_type':kind[:-1]+'2','measured_driver_pin':name+'/ZN'})
        return {'modules':{M.TOP:{'cells':cells,'ports':{'y':{'direction':'output','bits':[1]}}}}},targets

    def test_all_measured_cells_preserve_pins_and_original(self):
        original,targets=self.fixture();before=deepcopy(original)
        edited,changes=M.resize_measured_cells(original,targets)
        self.assertEqual(original,before);self.assertEqual(len(changes),4)
        for name,cell in before['modules'][M.TOP]['cells'].items():
            self.assertEqual(edited['modules'][M.TOP]['cells'][name]['connections'],cell['connections'])
        self.assertEqual(edited['modules'][M.TOP]['ports'],before['modules'][M.TOP]['ports'])

    def test_stale_duplicate_and_changed_function_rejected(self):
        for kind in ('stale','duplicate','function','missing'):
            original,targets=self.fixture()
            if kind=='stale':targets[0]['expected_cell']['connections']['ZN']=[999]
            if kind=='duplicate':targets[1]=deepcopy(targets[0])
            if kind=='function':targets[0]['replacement_type']='NAND4_X2'
            if kind=='missing':targets.pop()
            with self.assertRaises(ValueError):M.resize_measured_cells(original,targets)
