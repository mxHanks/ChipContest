"""Physical parallelism stays distinct from ABI schedule and useful MAC work."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/scripts'))
import e203_soc as soc
import xu_firmware_contract as contract
import xu_perf_report as perf
import server_accept as accept


class XuPe32ContractTests(unittest.TestCase):
    schedule = 'bias-hw-pe32-autogroup-window'

    def test_wide_and_compat_work_counts_and_compiler_flags(self):
        wide = contract.task_contract(self.schedule)
        self.assertEqual((wide['starts'], wide['dones'], wide['mac_fire'], wide['mmio_writes']),
                         (792, 792, 50688, 13121))
        self.assertEqual(wide['macs'], 1622016)
        old = contract.task_contract('bias-hw-autogroup-window')
        self.assertEqual((old['starts'], old['mac_fire'], old['mmio_writes']), (3168, 202752, 15497))
        self.assertEqual(wide['shared_reads'], old['shared_reads'])
        self.assertEqual(wide['shared_writes'], old['shared_writes'])
        flags = contract.compiler_defines(contract.configuration(self.schedule, '-O2', 'both-unroll-no-masks'))
        for name in ['PE32', 'PACK32', 'AUTO_GROUP', 'BIAS_CACHE', 'RESULT_WINDOW']:
            self.assertIn('-DXU_HARDWARE_' + name + '=1', flags)
        self.assertFalse(any('PE32' in arg for arg in contract.compiler_defines(contract.configuration())))

    def test_physical_activity_rejects_wrong_lanes_beats_layers_or_missing_rows(self):
        for schedule, beats in [(self.schedule, 50688), ('bias-hw-autogroup-window', 202752)]:
            with self.subTest(schedule=schedule):
                layers = [dict(layer=0, cycles=1000000)]
                record = 'PE_TASK layer=0 physical_pes=32 mac_beats=' + str(beats) + ' lane_macs=1622016 useful_macs=1622016\n'
                good = soc.check_pe_activity(record, layers, schedule, 'pe32')
                self.assertEqual(good[0]['lane_macs'], 1622016)
                for bad in ['', record + record, record.replace('layer=0', 'layer=1'),
                            record.replace('physical_pes=32', 'physical_pes=8'),
                            record.replace('lane_macs=1622016', 'lane_macs=6488064'),
                            record.replace('mac_beats=' + str(beats), 'mac_beats=1')]:
                    with self.assertRaises(ValueError): soc.check_pe_activity(bad, layers, schedule, 'pe32')
                with self.assertRaises(ValueError): soc.check_pe_activity(record, layers, schedule, 'pe8')

    def test_server_acceptance_selects_same_pe32_for_every_soc_step(self):
        steps = accept.acceptance_steps(Path('/tmp/xu-pe32-new'), 'rv-', 'vcs',
            firmware_schedule=self.schedule, accel_variant='pe32')
        for name, command, _ in steps:
            if name == 'host':
                self.assertIn('XU_PE32_WRAPPER_SIM=vcs', command)
            elif name != 'numeric':
                self.assertEqual(command[command.index('--accel-variant') + 1], 'pe32')
        with self.assertRaises(ValueError):
            accept.acceptance_steps(Path('/tmp/xu-pe32-new'), 'rv-', 'vcs',
                                    firmware_schedule=self.schedule, accel_variant='pe8')

    def test_build_identity_and_report_keep_physical_variant(self):
        report = dict(source_sha256={}, versions={}, runner_sha256='xu')
        pe8 = soc.build_key(report, 'verilator', False)
        report['accel_variant'] = 'pe32'
        self.assertNotEqual(pe8, soc.build_key(report, 'verilator', False))
        self.assertIn('+define+XU_ACCEL_PE32=1', soc.vcs_build_command(Path('/tmp/xu'), Path('/tmp/rtl.f'), [], False, 'pe32'))
        counters = dict.fromkeys(set(contract.PERFORMANCE_FIELDS) - {'layer', 'cycles'}, 0)
        counters.update(w_load=1000000, busy=53856, mmio_reads=50688,
                        **{k:v for k,v in contract.task_contract(self.schedule).items() if k in counters})
        source = dict(status='PASS', mode='real', tasks=1, outputs=25344, write_words=50688,
                      firmware_schedule=self.schedule, accel_variant='pe32',
                      layers=[dict(layer=0, cycles=1000000, firmware_cycles=1000071, performance=counters)],
                      pe_activity=[dict(layer=0, physical_pes=32, mac_beats=50688, lane_macs=1622016, useful_macs=1622016)])
        summary = perf.summarize(source, 150)
        self.assertEqual(summary['pes'], 32)
        self.assertEqual(summary['conditional_peak_gmac_per_second'], 4.8)
        self.assertEqual(summary['source_identity']['accel_variant'], 'pe32')
        for change in [lambda x:x.pop('pe_activity'), lambda x:x.update(accel_variant='pe8'),
                       lambda x:x['pe_activity'][0].update(lane_macs=6488064)]:
            bad = copy.deepcopy(source); change(bad)
            with self.assertRaises(ValueError): perf.summarize(bad, 150)


if __name__ == '__main__': unittest.main()
