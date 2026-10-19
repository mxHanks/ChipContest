import importlib.util
from pathlib import Path
import unittest
from copy import deepcopy

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('minimum_eco',ROOT/'scripts/synth/run_sram_minimum_candidate.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class TargetedECO(unittest.TestCase):
    def design(self):
        def c(kind,a,z):return {'type':kind,'port_directions':{'A':'input','Z':'output'},'connections':{'A':[a],'Z':[z]}}
        ff={'type':'DFFR_X1','port_directions':{'D':'input','Q':'output'},'connections':{'D':[1],'Q':[3]}}
        acc={'type':'DFFR_X1','port_directions':{'D':'input','Q':'output'},'connections':{'D':[3],'Q':[4]}}
        top={'ports':{'clk':{'direction':'input','bits':[1]}},'cells':{'reset':c('BUF_X1',1,2),'valid':ff,'acc':acc,'macro':c('opaque',5,6)},
             'netnames':{n:{'bits':[b]} for n,b in [('clk',1),('u_engine.rst_n',2),('u_engine.read_valid',3),('u_engine.accumulate_valid',4),('macro_a',5),('macro_z',6),('unused_alias',100)]}}
        return {'modules':{M.TOP:top}}

    def test_isolated_changes_keep_original_macro_and_external_ports(self):
        old=self.design();new,changes=M.minimum_eco(old,6,1)
        a=old['modules'][M.TOP];b=new['modules'][M.TOP]
        self.assertEqual(a['cells']['reset']['type'],'BUF_X1')
        self.assertEqual(a['cells']['macro'],b['cells']['macro'])
        self.assertEqual(a['ports'],b['ports'])
        self.assertEqual(b['cells']['reset']['type'],'BUF_X16')
        self.assertEqual(len(b['cells'])-len(a['cells']),7)
        self.assertFalse(set(b['cells'])&set(b['netnames']))
        self.assertEqual(sum(x['action']=='insert' for x in changes),7)
        current=b['cells']['reset']['connections']['A'][0]
        for i in reversed(range(6)):
            buf=b['cells'][f'kwt_eco_reset_{i:02d}'];self.assertEqual(buf['connections']['Z'],[current]);current=buf['connections']['A'][0]
        self.assertEqual(current,1)
        self.assertTrue(all(x['Z']>100 for x in changes if x['action']=='insert'))

    def test_unexpected_path_driver_or_stage_count_rejected(self):
        bad=self.design();bad['modules'][M.TOP]['cells']['acc']['connections']['D']=[7]
        with self.assertRaises(ValueError):M.minimum_eco(bad)
        for stages in (0,9):
            with self.assertRaises(ValueError):M.minimum_eco(self.design(),stages,1)

    def test_json_bit_renumbering_is_allowed_but_changed_connection_is_not(self):
        expected,_=M.minimum_eco(self.design());actual=deepcopy(expected)
        top=actual['modules'][M.TOP]
        for net in list(top['netnames'].values())+list(top['ports'].values()):net['bits']=[b+1000 for b in net['bits']]
        for cell in top['cells'].values():cell['connections']={p:[b+1000 for b in bits] for p,bits in cell['connections'].items()}
        M.verify_emitted_graph(expected,actual)
        top['cells']['acc']['connections']['D']=[1003]
        with self.assertRaises(ValueError):M.verify_emitted_graph(expected,actual)
