"""Strict opt-in parser coverage, isolated from the stable eight-PE fixtures."""
from pathlib import Path
import sys, unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/scripts'))
import e203_soc as soc
import xu_firmware_contract as contract

class Batch16ContractTests(unittest.TestCase):
    def setUp(self):
        self.s = contract.NICE_BATCH16_SCHEDULE
        self.layers = [dict(layer=0, cycles=1000000)]
        self.batch = ('BATCH16_TASK layer=0 requests=1584 snapshots=3168 pops_retired=3168 '
                      'blocks_written=1584 lanes=25344 no_write_before_both_pops=1\n')
        self.direct = ('DIRECT_TASK layer=0 snapshots=3168 lanes=25344 pops_retired=3168 '
                       'result_mmio_reads=0\n')
        self.nice = ('NICE_TASK layer=0 requests=1584 responses=1584 oitf_retired=1584 '
                     'status_polls=3168 result_reads=0 pops_retired=3168 shared_writes=25344\n')
    def test_opt_in_flags_and_work(self):
        self.assertEqual(contract.compiler_defines(contract.configuration(self.s)),
                         contract.compiler_defines(contract.configuration(contract.NICE_DIRECT_SCHEDULE)) +
                         ['-DXU_NICE_DRAIN16=1'])
        self.assertEqual(contract.simulator_arguments(self.s),
                         contract.simulator_arguments(contract.NICE_DIRECT_SCHEDULE) + ['+NICE_BATCH16=1'])
        c=contract.task_contract(self.s)
        self.assertEqual(c, {**contract.task_contract(contract.NICE_DIRECT_SCHEDULE),
                            'nice_requests':1584, 'nice_responses':1584, 'nice_oitf_retired':1584,
                            'batch16_blocks':1584})
        self.assertEqual((c['mmio_writes'], c['direct_snapshots'], c['direct_lanes'],
                          c['starts'], c['mac_fire'], c['macs']),
                         (12330,3168,25344,3168,202752,1622016))
    def test_exact_markers(self):
        self.assertEqual(len(soc.check_batch16_activity(self.batch,self.layers,self.s)),1)
        self.assertEqual(len(soc.check_direct_activity(self.direct,self.layers,self.s)),1)
        self.assertEqual(len(soc.check_nice_activity(self.nice+self.direct+self.batch,self.layers,self.s)),1)
    def test_batch_marker_negative_cases(self):
        bad=['',self.batch*2,self.batch.replace('layer=0','layer=1'),
             self.batch.replace('requests=1584','requests=3168'),
             self.batch.replace('snapshots=3168','snapshots=3167'),
             self.batch.replace('pops_retired=3168','pops_retired=3167'),
             self.batch.replace('blocks_written=1584','blocks_written=1583'),
             self.batch.replace('lanes=25344','lanes=25343'),
             self.batch.replace('no_write_before_both_pops=1','no_write_before_both_pops=0'),
             self.batch.replace('lanes=25344','lanes=-1'),
             self.batch.replace(' no_write_before_both_pops=1',''),
             self.batch.rstrip()+' extra=0\n']
        for v in bad:
            with self.subTest(v=v),self.assertRaises(ValueError):
                soc.check_batch16_activity(v,self.layers,self.s)
    def test_old_schedules_reject_batch_marker(self):
        for old in contract.SCHEDULES:
            if old==self.s:continue
            with self.subTest(old=old):
                self.assertEqual(soc.check_batch16_activity('',self.layers,old),[])
                with self.assertRaises(ValueError):soc.check_batch16_activity(self.batch,self.layers,old)
    def test_nice_counts_and_second_bundle_required(self):
        log=self.nice+self.direct+self.batch
        for before,after in [('requests=1584','requests=3168'),('responses=1584','responses=3168'),
                             ('oitf_retired=1584','oitf_retired=3168'),('status_polls=3168','status_polls=3167'),
                             ('pops_retired=3168','pops_retired=1584'),('result_reads=0','result_reads=1'),
                             ('shared_writes=25344','shared_writes=25343')]:
            with self.subTest(before=before),self.assertRaises(ValueError):
                soc.check_nice_activity(log.replace(before,after,1),self.layers,self.s)
        with self.assertRaises(ValueError):soc.check_nice_activity(self.nice+self.batch,self.layers,self.s)
        with self.assertRaises(ValueError):soc.check_nice_activity(self.nice+self.direct,self.layers,self.s)
    def test_legacy_direct_keeps_3168_instructions(self):
        old=contract.NICE_DIRECT_SCHEDULE
        legacy=self.nice.replace('=1584','=3168')+self.direct
        self.assertEqual(len(soc.check_nice_activity(legacy,self.layers,old)),1)
        with self.assertRaises(ValueError):soc.check_nice_activity(legacy+self.batch,self.layers,old)
        with self.assertRaises(ValueError):soc.check_nice_activity(self.nice+self.direct,self.layers,old)

    def test_physical_eight_pe_marker(self):
        marker='PE8_TASK layer=0 pes=8 physical_groups=3168 physical_mac_cycles=202752 logical_macs=1622016 checked_cycles=1000000\n'
        self.assertEqual(len(soc.check_pe8_activity(marker,self.layers,self.s)),1)
        for bad in ['', marker*2, marker.replace('pes=8','pes=16'),
                    marker.replace('physical_groups=3168','physical_groups=1584'),
                    marker.replace('physical_mac_cycles=202752','physical_mac_cycles=101376'),
                    marker.replace('logical_macs=1622016','logical_macs=811008'),
                    marker.replace('checked_cycles=1000000','checked_cycles=1000001')]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                soc.check_pe8_activity(bad,self.layers,self.s)
        self.assertEqual(soc.check_pe16_activity('',self.layers,self.s),[])

if __name__=='__main__':unittest.main()
