from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('counter_eco',ROOT/'scripts/synth/run_sram_counter_hold_candidate.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class CounterFeedbackECO(unittest.TestCase):
    def design(self):
        top={'ports':{},'netnames':{'u_engine.b_loaded':{'bits':[4,6]},'u_engine.x_loaded':{'bits':[5,7]}},'cells':{}}
        for name,bit in [('bff',4),('xff',5)]:
            top['cells'][name]={'type':'DFFR_X1','port_directions':{'D':'input','Q':'output'},'connections':{'D':[2],'Q':[bit]}}
        return {'modules':{M.TOP:top}}

    def test_only_two_counter_D_branches_gain_noninverting_buffers(self):
        old=self.design();snapshot=deepcopy(old);new,changes=M.counter_eco(old)
        self.assertEqual(old,snapshot);self.assertEqual(len(changes),2)
        a=old['modules'][M.TOP];b=new['modules'][M.TOP]
        self.assertEqual(len(b['cells']),len(a['cells'])+2)
        for change in changes:
            buf=b['cells'][change['inserted_buffer']]
            self.assertEqual(buf['type'],'BUF_X1');self.assertEqual(buf['connections']['A'],[2])
            self.assertEqual(buf['connections']['Z'],b['cells'][change['endpoint']]['connections']['D'])
            self.assertEqual(b['cells'][change['endpoint']]['connections']['Q'],a['cells'][change['endpoint']]['connections']['Q'])

    def test_missing_counter_or_wrong_cell_rejected(self):
        for name in ('bff','xff'):
            bad=self.design();bad['modules'][M.TOP]['cells'][name]['type']='DFF_X1'
            with self.assertRaises(ValueError):M.counter_eco(bad)
