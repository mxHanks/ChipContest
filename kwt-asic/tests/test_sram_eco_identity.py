from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('eco_identity',ROOT/'scripts/verify/check_sram_eco_identity.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class BufferProjection(unittest.TestCase):
    def design(self):
        cells={'ff':{'type':'DFFR_X1','parameters':{},'port_directions':{'D':'input','Q':'output'},'connections':{'D':[1],'Q':[2]}},
               'buf':{'type':'BUF_X1','parameters':{},'port_directions':{'A':'input','Z':'output'},'connections':{'A':[2],'Z':[3]}}}
        top={'cells':cells,'ports':{'x':{'direction':'input','bits':[1]},'y':{'direction':'output','bits':[3]}},
             'netnames':{n:{'bits':[b]} for n,b in [('x',1),('q',2),('y',3)]}}
        return {'modules':{'kwt_icb_slave_sram':top}}

    def candidate(self):
        old=self.design();new=deepcopy(old);t=new['modules']['kwt_icb_slave_sram']
        t['cells']['buf']['type']='BUF_X16'
        t['cells']['delay']={'type':'BUF_X1','parameters':{},'port_directions':{'A':'input','Z':'output'},'connections':{'A':[1],'Z':[4]}}
        t['cells']['ff']['connections']['D']=[4];t['netnames']['delay_net']={'bits':[4]}
        return old,new

    def test_identity_buffers_project_to_same_state_and_ports(self):
        old,new=self.candidate();result=M.project_buffers(old,new)
        self.assertEqual(result['added_noninverting_buffers'],1)
        self.assertEqual(result['equivalent_buffer_resizes'],['buf'])

    def test_wrong_buffer_or_rewired_original_cell_rejected(self):
        old,new=self.candidate();new['modules']['kwt_icb_slave_sram']['cells']['delay']['type']='INV_X1'
        with self.assertRaises(ValueError):M.project_buffers(old,new)
        old,new=self.candidate();new['modules']['kwt_icb_slave_sram']['cells']['ff']['connections']['D']=[2]
        with self.assertRaises(ValueError):M.project_buffers(old,new)

    def test_buffer_loop_and_drive_of_existing_net_rejected(self):
        for pin,target in [('A',4),('Z',2)]:
            old,new=self.candidate();new['modules']['kwt_icb_slave_sram']['cells']['delay']['connections'][pin]=[target]
            with self.assertRaises(ValueError):M.project_buffers(old,new)
