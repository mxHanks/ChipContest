"""Y32 CPU transport retains exact payload work and separate format evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/scripts'))
import e203_soc as soc
import xu_firmware_contract as contract
import xu_perf_report as perf


def task_log(schedule, tasks=1):
    work = contract.task_contract(schedule)
    lines = []
    for layer in range(tasks):
        counters = dict.fromkeys(contract.PERFORMANCE_FIELDS, 0)
        counters.update(layer=layer, cycles=1000000, w_load=1000000,
                        busy=215424, mmio_reads=60000)
        counters.update({key: work[key] for key in [
            'mac_fire', 'starts', 'dones', 'mmio_writes', 'shared_reads', 'shared_writes']})
        lines.append(f'TASK_PASS layer={layer} outputs=25344 writes={work["shared_writes"]} '
                     'cycles=1000000 firmware_cycles=1000080')
        lines.append('PERF_TASK ' + ' '.join(f'{key}={counters[key]}'
                                            for key in contract.PERFORMANCE_FIELDS))
        if schedule in contract.AUTOGROUP_SCHEDULES:
            lines.append(f'AUTO_TASK layer={layer} rows=99 pops_retired=3168 '
                         'compute_writeback_overlap=100 fifo_full_wait=200')
        if schedule in contract.Y32_SCHEDULES:
            lines.append(f'RESULT_TASK_Y32 layer={layer} words=25344 logical_results=25344')
        elif schedule in contract.PAIRED_HI_SCHEDULES:
            lines.append(f'RESULT_TASK layer={layer} legacy_words=25344 packed_words=12672 logical_words=50688')
        if schedule in contract.PACKED16_SCHEDULES:
            lines.append(f'W_PACKED16_TASK layer={layer} source_words=8192 uploaded_values=16384')
        if schedule in contract.NICE_SCHEDULES:
            lines.append(f'NICE_TASK layer={layer} requests=3168 responses=3168 oitf_retired=3168 '
                         'status_polls=3168 result_reads=25344 pops_retired=3168 shared_writes=25344')
        if schedule == contract.NICE_READ_POP_SCHEDULE:
            lines.append(f'READ_POP_TASK layer={layer} alias_reads=3168 explicit_pops=0')
    lines.append(f'SOC_PASS tasks={tasks} outputs={tasks*25344} '
                 f'writes={tasks*work["shared_writes"]}')
    return '\n'.join(lines) + '\n'


class Y32FirmwareContractTests(unittest.TestCase):
    def test_exact_y32_and_packed_source_work(self):
        for schedule, w_reads in [(contract.Y32_SCHEDULE, 16384),
                                  (contract.Y32_PACKED16_SCHEDULE, 8192)]:
            with self.subTest(schedule=schedule):
                work = contract.task_contract(schedule)
                self.assertEqual(work, dict(w_shared_reads=w_reads, x_shared_reads=6336,
                    bias_shared_reads=512, shared_reads=w_reads+6336+512, shared_writes=25344,
                    bias_mmio_writes=768, mmio_writes=15497, starts=3168, dones=3168,
                    mac_fire=202752, macs=1622016, outputs=25344,
                    result_mmio_reads=25344, y32_mmio_reads=25344, w_mmio_upload_words=8192,
                    rows=99, pops_retired=3168))
                flags = contract.compiler_defines(contract.configuration(schedule))
                for flag in ['XU_HARDWARE_BIAS_CACHE', 'XU_HARDWARE_RESULT_WINDOW',
                             'XU_HARDWARE_PACK32', 'XU_HARDWARE_AUTO_GROUP', 'XU_HARDWARE_Y32']:
                    self.assertIn('-D'+flag+'=1', flags)
                self.assertEqual('-DXU_SHARED_W_PACKED16=1' in flags, w_reads == 8192)
        for schedule in contract.SCHEDULES:
            if schedule in contract.Y32_SCHEDULES:
                continue
            flags = contract.compiler_defines(contract.configuration(schedule))
            self.assertFalse(any('Y32' in flag for flag in flags))
            self.assertEqual('-DXU_SHARED_W_PACKED16=1' in flags,
                             schedule in contract.PACKED16_SCHEDULES)
            self.assertEqual(contract.simulator_arguments(schedule),
                             ['+SHARED_W_PACKED16=1'] if schedule in contract.PACKED16_SCHEDULES else [])

    def test_packed_w_only_retains_original_output_abi_and_checks(self):
        schedule = contract.PAIRED_HI_PACKED16_SCHEDULE
        work = contract.task_contract(schedule)
        old = contract.task_contract(contract.PAIRED_HI_SCHEDULE)
        self.assertEqual({**old, 'w_shared_reads':8192, 'shared_reads':15040}, work)
        flags = contract.compiler_defines(contract.configuration(schedule))
        self.assertIn('-DXU_HARDWARE_PAIRED_HI=1', flags)
        self.assertIn('-DXU_SHARED_W_PACKED16=1', flags)
        self.assertNotIn('-DXU_HARDWARE_Y32=1', flags)
        log = task_log(schedule, 12)
        layers = soc.check_log(log, 12, schedule)
        self.assertEqual(len(soc.check_performance(log, layers, schedule)), 12)
        for bad in [log.replace('source_words=8192', 'source_words=8191'),
                    log.replace('packed_words=12672', 'packed_words=12671')]:
            with self.assertRaises(ValueError):
                soc.check_performance(bad, layers, schedule)
        with self.assertRaises(ValueError):
            soc.check_log(log, 12, contract.Y32_PACKED16_SCHEDULE)

    def test_packed_w_only_metadata_does_not_claim_output_quantization(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            soc.synthetic(directory, 1)
            old = soc.vector_identity(directory, 1)
            result = soc.vector_identity(directory, 1, contract.PAIRED_HI_PACKED16_SCHEDULE)
            self.assertTrue(all(result['vectors'][p]==h for p,h in old['vectors'].items()))
            p = result['vector_profile']
            self.assertEqual((p['format'], p['y_bits'], p['y_exp'], p['output_right_shift']),
                             ('fixed16_acc48_wpacked16_v1',48,-27,0))
            self.assertEqual(p['y']['bytes'],202752)
            self.assertEqual(p['rounding'],'exact')
            self.assertEqual(p['y_file'],'y.mem')
            self.assertNotIn('y32_file',p)
            self.assertEqual(p['w']['bytes'],32768)

    def test_request_window_cannot_drop_initial_wait_or_final_response(self):
        layers = [dict(layer=0, cycles=100)]
        valid = 'WINDOW_TASK layer=0 first_request=10 first_accept=17 final_y_response=109 first_request_wait=7\n'
        self.assertEqual(soc.check_task_windows(valid,layers)[0]['first_request_wait'],7)
        self.assertEqual(soc.check_task_windows('',layers),[])
        for bad in [valid+valid, valid.replace('wait=7','wait=0'),
                    valid.replace('response=109','response=108'),
                    valid.replace('first_request=10','first_request=17'),
                    valid.replace('layer=0','layer=1'), valid.replace('first_accept=17','first_accept=9')]:
            with self.assertRaises(ValueError): soc.check_task_windows(bad,layers)

    def test_y32_completion_requires_exact_counts_for_all_12_tasks(self):
        for schedule in contract.Y32_SCHEDULES:
            log = task_log(schedule, 12)
            layers = soc.check_log(log, 12, schedule)
            self.assertEqual([row['layer'] for row in layers], list(range(12)))
            self.assertIn('SOC_PASS tasks=12 outputs=304128 writes=304128', log)
            self.assertEqual(len(soc.check_performance(log, layers, schedule)), 12)
            for bad in [log.replace('writes=25344', 'writes=50688'),
                        log.replace('writes=304128', 'writes=608256'),
                        log + log, log.replace('layer=11', 'layer=12')]:
                with self.subTest(schedule=schedule, bad=bad[:100]), self.assertRaises(ValueError):
                    soc.check_log(bad, 12, schedule)
            with self.assertRaises(ValueError):
                soc.check_log(log, 12)
        with self.assertRaises(ValueError):
            soc.check_log(task_log('baseline'), 1, contract.Y32_SCHEDULE)

    def test_y32_activity_is_mandatory_and_cannot_accept_legacy_records(self):
        layers = [dict(layer=0, cycles=1000000)]
        valid = 'RESULT_TASK_Y32 layer=0 words=25344 logical_results=25344\n'
        legacy = 'RESULT_TASK layer=0 legacy_words=50688 packed_words=0 logical_words=50688\n'
        for schedule in contract.Y32_SCHEDULES:
            self.assertEqual(soc.check_result_activity(valid, layers, schedule),
                             [dict(layer=0, words=25344, logical_results=25344)])
            for bad in ['', valid+valid, valid+legacy, legacy,
                        valid.replace('words=25344', 'words=25343'),
                        valid.replace('logical_results=25344', 'logical_results=25343'),
                        valid.replace('layer=0', 'layer=1'),
                        valid.replace('words=25344', 'words=-1')]:
                with self.subTest(schedule=schedule, bad=bad), self.assertRaises(ValueError):
                    soc.check_result_activity(bad, layers, schedule)
            auto = ('AUTO_TASK layer=0 rows=99 pops_retired=3168 '
                    'compute_writeback_overlap=100 fifo_full_wait=200\n')
            for bad in ['', auto.replace('rows=99', 'rows=98'),
                        auto.replace('pops_retired=3168', 'pops_retired=3167'),
                        auto.replace('overlap=100', 'overlap=0')]:
                with self.assertRaises(ValueError):
                    soc.check_autogroup_activity(bad, layers, schedule)
        with self.assertRaises(ValueError):
            soc.check_result_activity(valid, layers, 'bias-hw-autogroup-window')

    def test_packed16_source_and_upload_activity_is_mandatory(self):
        layers = [dict(layer=0, cycles=1000000)]
        valid = 'W_PACKED16_TASK layer=0 source_words=8192 uploaded_values=16384\n'
        schedule = contract.Y32_PACKED16_SCHEDULE
        self.assertEqual(soc.check_weight_activity(valid, layers, schedule),
                         [dict(layer=0, source_words=8192, uploaded_values=16384)])
        for bad in ['', valid+valid, valid.replace('8192', '8191'),
                    valid.replace('16384', '16383'), valid.replace('layer=0', 'layer=1'),
                    valid.replace('8192', '-1')]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                soc.check_weight_activity(bad, layers, schedule)
        with self.assertRaises(ValueError):
            soc.check_weight_activity(valid, layers, contract.Y32_SCHEDULE)

    def test_performance_report_retains_y32_contract_and_rejects_cross_mode(self):
        for schedule in contract.Y32_SCHEDULES:
            log = task_log(schedule)
            layers = soc.check_log(log, 1, schedule)
            layers[0]['performance'] = soc.check_performance(log, layers, schedule)[0]
            source = dict(status='PASS', mode='real', tasks=1, firmware_schedule=schedule,
                transaction_contract=contract.task_contract(schedule), outputs=25344,
                write_words=25344, layers=layers,
                result_activity=soc.check_result_activity(log, layers, schedule),
                nice_activity=soc.check_nice_activity(log, layers, schedule))
            self.assertEqual(perf.summarize(source, 150)['aggregate']['counters']['shared_writes'], 25344)
            for field, value in [('write_words', 50688), ('result_activity', []),
                                 ('firmware_schedule', 'bias-hw-autogroup-window')]:
                bad = copy.deepcopy(source)
                bad[field] = value
                with self.subTest(schedule=schedule, field=field), self.assertRaises(ValueError):
                    perf.summarize(bad, 150)

    def test_versioned_vectors_record_helper_model_and_payload_identities(self):
        for schedule in contract.Y32_SCHEDULES:
            with self.subTest(schedule=schedule), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                soc.synthetic(directory, 1)
                original = {p.name:soc.sha(p) for p in (directory/'layer_00').iterdir()}
                legacy = soc.vector_identity(directory, 1)
                identity = soc.vector_identity(directory, 1, schedule)
                self.assertNotIn('profile_source_sha256', legacy)
                self.assertEqual(len(legacy['vectors']), 4)
                self.assertEqual(set(identity['profile_source_sha256']), {
                    'tools/model/export_s3_vectors.py', 'model/s3_y32.py', 'model/fixed16_acc48.py'})
                for name, digest in original.items():
                    self.assertEqual(soc.sha(directory/'layer_00'/name), digest)
                self.assertIn('layer_00/y32.mem', identity['vectors'])
                self.assertIn('profile.json', identity['vectors'])
                self.assertEqual(identity['vector_profile']['format'], 'fixed16_acc48_y32_rne9_v1')
                self.assertEqual(identity['vector_profile']['w']['bytes'],
                                 32768 if schedule in contract.PACKED16_SCHEDULES else 65536)
                y48 = soc.read_mem(directory/'layer_00/y.mem', 48, 25344)
                y32 = soc.read_mem(directory/'layer_00/y32.mem', 32, 25344)
                for old, new in zip(y48, y32):
                    quotient, remainder = divmod(old, 512)
                    self.assertEqual(new, quotient + int(remainder > 256 or
                                                        (remainder == 256 and quotient % 2)))
                if schedule in contract.PACKED16_SCHEDULES:
                    weights = soc.read_mem(directory/'layer_00/w.mem', 16, 16384)
                    packed = soc.read_mem(directory/'layer_00/w_packed16.mem', 32, 8192)
                    for index, word in enumerate(packed):
                        self.assertEqual(word & 0xffffffff,
                            (weights[2*index] & 0xffff) | ((weights[2*index+1] & 0xffff) << 16))

    def test_runner_selects_plusargs_and_output_counts_without_running_tools(self):
        for schedule in ['baseline', *contract.Y32_SCHEDULES]:
            with self.subTest(schedule=schedule), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                binary = root/'simulator'
                binary.write_bytes(b'not executed')
                out = root/'out'
                commands = []
                def fake_run(command, cwd, logfile, timeout=1800):
                    commands.append(command)
                    return task_log(schedule) if command[0] == str(binary) else 'tool version\n'
                with patch('sys.argv', ['e203_soc.py', '--mode', 'vectors', '--vectors', str(root),
                                       '--out', str(out), '--firmware-schedule', schedule]), \
                     patch.object(soc, 'ROOT', root), \
                     patch.object(soc, 'E203', root/'third-party/e203_hbirdv2'), \
                     patch.object(soc.shutil, 'which', return_value='/unused/tool'), \
                     patch.object(soc.subprocess, 'check_output', return_value='commit\n'), \
                     patch.object(soc, 'verify_submodule', return_value='submodule'), \
                     patch.object(soc, 'vector_identity', return_value={'vectors':{'x.mem':'hash'}}) as vectors, \
                     patch.object(soc, 'compile_firmware', return_value=root/'firmware') as compile_fw, \
                     patch.object(soc, 'matrix_sources', return_value=[]), \
                     patch.object(soc, 'build_simulator', return_value=(binary, [str(binary)])), \
                     patch.object(soc, 'run', side_effect=fake_run):
                    self.assertEqual(soc.main(), 0)
                result = json.loads((out/'result.json').read_text())
                self.assertEqual(result['write_words'], contract.task_contract(schedule)['shared_writes'])
                vectors.assert_called_once_with(root, 1, schedule)
                self.assertEqual(compile_fw.call_args.args[2], schedule)
                command = commands[-1]
                self.assertEqual('+OUTPUT_Y32=1' in command, schedule in contract.Y32_SCHEDULES)
                self.assertEqual('+SHARED_W_PACKED16=1' in command,
                                 schedule in contract.PACKED16_SCHEDULES)
                self.assertEqual('+NICE_DRAIN8=1' in command, schedule in contract.NICE_SCHEDULES)
                self.assertEqual('+NICE_READ_POP=1' in command,
                                 schedule == contract.NICE_READ_POP_SCHEDULE)

    def test_read_pop_changes_only_transport_work_and_keeps_firmware_abi(self):
        old, new = contract.NICE_SCHEDULE, contract.NICE_READ_POP_SCHEDULE
        self.assertEqual(contract.task_contract(new),
                         {**contract.task_contract(old), 'mmio_writes': 12329})
        self.assertEqual(contract.task_contract(old)['mmio_writes'], 15497)
        for optimization in contract.OPTIMIZATIONS:
            for experiment in contract.EXPERIMENTS:
                self.assertEqual(
                    contract.compiler_defines(contract.configuration(new, optimization, experiment)),
                    contract.compiler_defines(contract.configuration(old, optimization, experiment)))
        self.assertEqual(contract.simulator_arguments(new),
                         contract.simulator_arguments(old) + ['+NICE_READ_POP=1'])
        self.assertIn(new, contract.Y32_SCHEDULES)
        self.assertIn(new, contract.PACKED16_SCHEDULES)
        self.assertIn(new, contract.NICE_SCHEDULES)

    def test_read_pop_records_require_alias_retirement_and_forbid_explicit_pops(self):
        schedule = contract.NICE_READ_POP_SCHEDULE
        layers = [dict(layer=0, cycles=1000000)]
        marker = 'READ_POP_TASK layer=0 alias_reads=3168 explicit_pops=0\n'
        self.assertEqual(soc.check_read_pop_activity(marker, layers, schedule),
                         [dict(layer=0, alias_reads=3168, explicit_pops=0)])
        for bad in ['', marker+marker, marker.replace('layer=0', 'layer=1'),
                    marker.replace('reads=3168', 'reads=3167'),
                    marker.replace('reads=3168', 'reads=3169'),
                    marker.replace('reads=3168', 'reads=-1'),
                    marker.replace('explicit_pops=0', 'explicit_pops=1'),
                    marker.replace(' explicit_pops=0', ''), marker.rstrip()+' other=0\n']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                soc.check_read_pop_activity(bad, layers, schedule)
        complete = task_log(schedule)
        self.assertEqual(len(soc.check_performance(complete, layers, schedule)), 1)
        with self.assertRaises(ValueError):
            soc.check_performance(complete.replace(marker, ''), layers, schedule)
        for old in contract.SCHEDULES:
            if old == schedule:
                continue
            self.assertEqual(soc.check_read_pop_activity('', layers, old), [])
            with self.subTest(old=old), self.assertRaises(ValueError):
                soc.check_read_pop_activity(marker, layers, old)
        with self.assertRaises(ValueError):
            soc.check_performance(task_log(contract.NICE_SCHEDULE)+marker,
                                  layers, contract.NICE_SCHEDULE)

    def test_nice_records_require_real_instruction_retirement_and_payload_counts(self):
        schedule = contract.NICE_SCHEDULE
        layers = [dict(layer=0, cycles=1000000)]
        marker = ('NICE_TASK layer=0 requests=3168 responses=3168 oitf_retired=3168 '
                  'status_polls=3168 result_reads=25344 pops_retired=3168 shared_writes=25344\n')
        records = soc.check_nice_activity(marker, layers, schedule)
        self.assertEqual(records[0]['oitf_retired'], 3168)
        self.assertIn('-DXU_NICE_DRAIN8=1', contract.compiler_defines(contract.configuration(schedule)))
        for bad in ['', marker+marker, marker.replace('layer=0', 'layer=1'),
                    marker.replace('responses=3168', 'responses=3167'),
                    marker.replace('oitf_retired=3168', 'oitf_retired=0'),
                    marker.replace('status_polls=3168', 'status_polls=3167'),
                    marker.replace('result_reads=25344', 'result_reads=25343'),
                    marker.replace('shared_writes=25344', 'shared_writes=25343')]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                soc.check_nice_activity(bad, layers, schedule)
        with self.assertRaises(ValueError):
            soc.check_nice_activity(marker, layers, contract.Y32_PACKED16_SCHEDULE)


if __name__ == '__main__':
    unittest.main()
