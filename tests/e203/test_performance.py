"""Performance reports must retain the complete numerical work and timing window."""
import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/scripts'))
import e203_soc as soc
import xu_perf_report as perf


class PerformanceTests(unittest.TestCase):
    def record(self):
        return ('PERF_TASK layer=0 cycles=2368078 w_load=300000 x_load=100000 '
                'bias_load=600000 compute_wait=250000 writeback=1118078 other=0 '
                'busy=215424 mac_fire=202752 mmio_reads=60000 mmio_writes=156326 '
                'shared_reads=73408 shared_writes=50688 shared_stall=10000 '
                'mmio_stall=0 starts=3168 dones=3168\n')

    def test_counter_contract_rejects_partial_or_inconsistent_measurement(self):
        layers = [dict(layer=0, cycles=2368078, firmware_cycles=2368150)]
        good = self.record()
        counters = soc.check_performance(good, layers)
        self.assertEqual(counters[0]['mac_fire'] * 8, 1622016)
        for bad in ['', good + good, good.replace('layer=0', 'layer=1'),
                    good.replace('cycles=2368078', 'cycles=2368079'),
                    good.replace('writeback=1118078', 'writeback=1118079'),
                    good.replace('mac_fire=202752', 'mac_fire=202751'),
                    good.replace('dones=3168', 'dones=3167'),
                    good.replace('shared_writes=50688', 'shared_writes=50687'),
                    good.replace('shared_stall=10000', 'shared_stall=3000000'),
                    good.replace('busy=215424', 'busy=1')]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                soc.check_performance(bad, layers)

    def test_frequency_changes_time_but_not_cycle_efficiency(self):
        layers = [dict(layer=i, cycles=2368078 if i == 0 else 2368074,
                       firmware_cycles=2368150 if i == 0 else 2368146) for i in range(12)]
        source = dict(status='PASS', mode='real', tasks=12, layers=layers)
        report = perf.summarize(source, 150.0)
        self.assertEqual(report['aggregate']['cycles'], 28416892)
        self.assertAlmostEqual(report['aggregate']['conditional_mean_latency_ms'], 15.787162222222222)
        self.assertAlmostEqual(report['aggregate']['conditional_tasks_per_second'], 63.3426062217, places=7)
        self.assertAlmostEqual(report['aggregate']['end_to_end_peak_fraction'], 0.0856189338, places=9)
        doubled = perf.summarize(source, 300.0)
        self.assertEqual(doubled['aggregate']['cycles'], report['aggregate']['cycles'])
        self.assertEqual(doubled['aggregate']['conditional_mean_latency_ms'] * 2,
                         report['aggregate']['conditional_mean_latency_ms'])
        self.assertEqual(doubled['aggregate']['end_to_end_peak_fraction'],
                         report['aggregate']['end_to_end_peak_fraction'])
        for bad in [0, -1, math.nan, math.inf]:
            with self.assertRaises(ValueError): perf.summarize(source, bad)
        for field, value in [('status', 'FAIL'), ('mode', 'synthetic'), ('tasks', 13)]:
            bad = copy.deepcopy(source)
            bad[field] = value
            with self.assertRaises(ValueError): perf.summarize(bad, 150)

    def test_report_rechecks_activity_and_aggregates_phases(self):
        layer = dict(layer=0, cycles=2368078, firmware_cycles=2368150,
                     performance=soc.check_performance(self.record(),
                         [dict(layer=0, cycles=2368078)])[0])
        source = dict(status='PASS', mode='real', tasks=1, layers=[layer])
        report = perf.summarize(source, 150)
        self.assertEqual(report['aggregate']['counters'], layer['performance'])
        self.assertAlmostEqual(sum(report['aggregate']['phase_fraction'].values()), 1)
        for key, value in [('busy', 999999999), ('starts', 1), ('shared_writes', 50687)]:
            bad = copy.deepcopy(source)
            bad['layers'][0]['performance'][key] = value
            with self.assertRaises(ValueError): perf.summarize(bad, 150)


if __name__ == '__main__':
    unittest.main()
