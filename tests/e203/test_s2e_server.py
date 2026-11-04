"""Offline gate tests for the future server's two complete VCS result comparison."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/scripts'))
import xu_s2e_server_accept as entry
import xu_firmware_contract as contract


class XuS2eServerTests(unittest.TestCase):
    def record(self, paired):
        schedule=contract.PAIRED_HI_SCHEDULE if paired else 'bias-hw-autogroup-window'
        work=contract.task_contract(schedule)
        counters=dict.fromkeys(set(contract.PERFORMANCE_FIELDS)-{'layer','cycles'},0)
        counters.update(w_load=300000,x_load=100000,bias_load=200000,compute_wait=250000,
                        writeback=1000000,other=150000,busy=215424,mmio_reads=60000)
        for key in ['mac_fire','starts','dones','shared_reads','shared_writes','mmio_writes']:
            counters[key]=work[key]
        result=dict(status='PASS',mode='real',tasks=12,simulator='vcs',firmware_schedule=schedule,
                    firmware_opt='-O2',firmware_experiment='both-unroll-no-masks',
                    transaction_contract=work,outputs=304128,write_words=608256,
                    layers=[dict(layer=i,cycles=2000000,performance=dict(counters)) for i in range(12)],
                    result_activity=[dict(layer=i,legacy_words=25344 if paired else 50688,
                                          packed_words=12672 if paired else 0,logical_words=50688)
                                     for i in range(12)])
        for key in ['main_commit','e203_commit','source_sha256','runner_sha256','contract_sha256',
                    'versions','tools','vectors','fixture','simulator_sha256']:
            result[key]={'offline_mock_identity':key}
        return result

    def test_complete_same_physical_comparison_and_negative_controls(self):
        paired,control=self.record(True),self.record(False)
        rows,fields=entry.compare_real12(paired,control)
        self.assertEqual(len(rows),12)
        self.assertEqual(rows[0]['paired_result_reads'],38016)
        self.assertEqual(rows[0]['control_result_reads'],50688)
        mutations=[lambda p:p.update(tasks=11),lambda p:p.update(outputs=25344),
                   lambda p:p.update(simulator='iverilog'),lambda p:p.update(firmware_opt='-O3'),
                   lambda p:p.update(simulator_sha256='different'),
                   lambda p:p['layers'].reverse(),lambda p:p['result_activity'].pop(),
                   lambda p:p['result_activity'][0].update(logical_words=50687),
                   lambda p:p['layers'][0]['performance'].update(shared_writes=50687)]
        for mutate in mutations:
            bad=copy.deepcopy(paired)
            mutate(bad)
            with self.assertRaises(ValueError): entry.compare_real12(bad,control)


if __name__=='__main__': unittest.main()
