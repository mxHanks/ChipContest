"""New hardware modes must account for every accepted bus transaction."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/scripts'))
import xu_firmware_contract as contract
import xu_perf_report as perf


class HardwareContractTests(unittest.TestCase):
    def test_exact_work_and_mode_mismatch_rejection(self):
        for schedule, writes in [('bias-dtcm', 156326), ('bias-hw', 81064),
                                 ('bias-dtcm-window', 130982), ('bias-hw-window', 55720),
                                 ('bias-hw-stream16-window', 33094)]:
            with self.subTest(schedule=schedule):
                work = contract.task_contract(schedule)
                self.assertEqual(work['mmio_writes'], writes)
                self.assertEqual(work['shared_reads'], 23232)
                self.assertEqual(work['bias_mmio_writes'], 768 if schedule.startswith('bias-hw') else 76032)
                counters = dict.fromkeys(set(contract.PERFORMANCE_FIELDS) - {'layer', 'cycles'}, 0)
                counters.update(w_load=300000, x_load=100000, bias_load=200000,
                                compute_wait=250000, writeback=1000000, other=150000,
                                busy=215424, mmio_reads=60000)
                counters.update({k: work[k] for k in ['mac_fire', 'starts', 'dones',
                                                    'shared_reads', 'shared_writes', 'mmio_writes']})
                source = dict(status='PASS', mode='real', tasks=1, firmware_schedule=schedule,
                              firmware_opt='-O2', firmware_experiment='both-unroll-no-masks',
                              transaction_contract=work, outputs=25344, write_words=50688,
                              layers=[dict(layer=0, cycles=2000000, firmware_cycles=2000080,
                                           performance=counters)])
                self.assertEqual(perf.summarize(source, 150)['aggregate']['cycles'], 2000000)
                for other in contract.SCHEDULES:
                    if other == schedule:
                        continue
                    bad = copy.deepcopy(source)
                    bad['firmware_schedule'] = other
                    # Both metadata and actual counters must reject a wrong mode.
                    with self.assertRaises(ValueError): perf.summarize(bad, 150)
                    bad.pop('transaction_contract')
                    with self.assertRaises(ValueError): perf.summarize(bad, 150)

    def test_scalar_stream_is_opt_in_and_keeps_source_and_output_work(self):
        stream = contract.task_contract('bias-hw-stream16-window')
        legacy = contract.task_contract('bias-hw-window')
        self.assertEqual(legacy['mmio_writes'] - stream['mmio_writes'], 22626)
        for field in ['w_shared_reads', 'x_shared_reads', 'bias_shared_reads',
                      'shared_reads', 'shared_writes', 'starts', 'dones', 'mac_fire',
                      'macs', 'outputs', 'bias_mmio_writes']:
            self.assertEqual(stream[field], legacy[field])
        for schedule in contract.SCHEDULES:
            defines = contract.compiler_defines(contract.configuration(schedule))
            self.assertEqual('-DXU_HARDWARE_STREAM16=1' in defines,
                             schedule == 'bias-hw-stream16-window')
            self.assertNotIn('-DXU_HARDWARE_STREAM16=0', defines)

    def test_new_compiler_modes_are_independent(self):
        for schedule in contract.SCHEDULES:
            defines = contract.compiler_defines(contract.configuration(schedule))
            for name, enabled in [('BIAS_DTCM', schedule.startswith('bias-dtcm')),
                                  ('HARDWARE_BIAS_CACHE', schedule.startswith('bias-hw')),
                                  ('HARDWARE_RESULT_WINDOW', schedule.endswith('-window'))]:
                prefix = 'XU_FIRMWARE_' if name == 'BIAS_DTCM' else 'XU_'
                self.assertIn('-D' + prefix + name + '=' + str(int(enabled)), defines)


if __name__ == '__main__':
    unittest.main()
