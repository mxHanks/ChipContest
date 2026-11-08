from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/scripts'))
import e203_soc as soc
import xu_firmware_contract as contract

class StreamContractTests(unittest.TestCase):
    def setUp(self):
        self.s=contract.NICE_STREAM_SCHEDULE
        self.layers=[dict(layer=0,cycles=1000000)]
        self.stream=('STREAM_TASK layer=0 requests=99 groups=3168 snapshots=3168 pops_retired=3168 '
                     'shared_writes=25344 final_response_before_completion=1\n')
        self.direct='DIRECT_TASK layer=0 snapshots=3168 lanes=25344 pops_retired=3168 result_mmio_reads=0\n'
        self.nice=('NICE_TASK layer=0 requests=99 responses=99 oitf_retired=99 '
                   'status_polls=3168 result_reads=0 pops_retired=3168 shared_writes=25344\n')
    def test_opt_in_flags_and_work(self):
        old=contract.NICE_DIRECT_SCHEDULE
        self.assertEqual(contract.compiler_defines(contract.configuration(self.s)),
                         contract.compiler_defines(contract.configuration(old))+['-DXU_NICE_DRAINN=1'])
        self.assertEqual(contract.simulator_arguments(self.s),contract.simulator_arguments(old)+['+NICE_STREAM=1'])
        self.assertEqual(contract.task_contract(self.s),{**contract.task_contract(old),
            'nice_requests':99,'nice_responses':99,'nice_oitf_retired':99,'stream_groups':3168})
        c=contract.task_contract(self.s)
        self.assertEqual((contract.PES,c['starts'],c['dones'],c['mac_fire'],c['macs']),
                         (8,3168,3168,202752,1622016))
    def test_exact_records(self):
        self.assertEqual(len(soc.check_stream_activity(self.stream,self.layers,self.s)),1)
        self.assertEqual(len(soc.check_direct_activity(self.direct,self.layers,self.s)),1)
        self.assertEqual(len(soc.check_nice_activity(self.nice+self.direct+self.stream,self.layers,self.s)),1)
    def test_stream_negative_markers(self):
        bad=['',self.stream*2,self.stream.replace('layer=0','layer=1'),
             self.stream.replace('requests=99','requests=3168'),
             self.stream.replace('groups=3168','groups=3167'),
             self.stream.replace('snapshots=3168','snapshots=3167'),
             self.stream.replace('pops_retired=3168','pops_retired=3167'),
             self.stream.replace('shared_writes=25344','shared_writes=25343'),
             self.stream.replace('final_response_before_completion=1','final_response_before_completion=0'),
             self.stream.replace('groups=3168','groups=-1'),
             self.stream.replace(' final_response_before_completion=1',''),
             self.stream.rstrip()+' extra=0\n']
        for v in bad:
            with self.subTest(v=v),self.assertRaises(ValueError):soc.check_stream_activity(v,self.layers,self.s)
    def test_legacy_schedules_reject_stream_marker(self):
        for old in contract.SCHEDULES:
            if old==self.s:continue
            with self.subTest(old=old):
                self.assertEqual(soc.check_stream_activity('',self.layers,old),[])
                with self.assertRaises(ValueError):soc.check_stream_activity(self.stream,self.layers,old)
    def test_nice_counts_and_marker_presence(self):
        log=self.nice+self.direct+self.stream
        for before,after in [('requests=99','requests=3168'),('responses=99','responses=3168'),
                             ('oitf_retired=99','oitf_retired=3168'),('status_polls=3168','status_polls=3167'),
                             ('pops_retired=3168','pops_retired=99'),('result_reads=0','result_reads=1'),
                             ('shared_writes=25344','shared_writes=25343')]:
            with self.subTest(before=before),self.assertRaises(ValueError):
                soc.check_nice_activity(log.replace(before,after,1),self.layers,self.s)
        with self.assertRaises(ValueError):soc.check_nice_activity(self.nice+self.direct,self.layers,self.s)
        with self.assertRaises(ValueError):soc.check_nice_activity(self.nice+self.stream,self.layers,self.s)
    def test_legacy_direct_keeps_3168_instructions(self):
        old=contract.NICE_DIRECT_SCHEDULE
        legacy=self.nice.replace('requests=99','requests=3168').replace('responses=99','responses=3168').replace('oitf_retired=99','oitf_retired=3168')+self.direct
        self.assertEqual(len(soc.check_nice_activity(legacy,self.layers,old)),1)
        with self.assertRaises(ValueError):soc.check_nice_activity(legacy+self.stream,self.layers,old)
        with self.assertRaises(ValueError):soc.check_nice_activity(self.nice+self.direct,self.layers,old)

if __name__=='__main__':unittest.main()
