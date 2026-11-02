"""Reject activity/energy shortcuts and verify streaming per-bit accounting."""
import copy
from decimal import Decimal
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('xu_soc_activity', ROOT/'tools/scripts/xu_soc_activity.py')
activity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activity)


class StreamingActivityTests(unittest.TestCase):
    def convert(self, source, begin, end, scope='tb/soc'):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'window.saif'
            result = activity.vcd_to_saif(io.StringIO(source), output, begin, end, scope)
            parsed = activity.read_saif(output)
        return result, parsed

    def test_bus_bits_aliases_unknown_dwell_and_boundary_events(self):
        source = '''$timescale 10 ps $end
$scope module tb $end
$scope module soc $end
$var wire 2 ! data [0:1] $end
$var wire 2 ! alias [1:0] $end
$var wire 1 " scalar $end
$upscope $end
$upscope $end
$enddefinitions $end
$dumpvars b00 ! 0" $end
#10 b01 ! 1"
#20 b11 !
#30 bzz !
#40 b00 ! 0"
#50
'''
        result, parsed = self.convert(source, 10, 40)
        signals = {s['path']:s for s in parsed['signals']}
        self.assertEqual(result['digital_signal_bits'], 5)
        self.assertEqual(result['independent_vcd_codes'], 2)
        self.assertEqual(Decimal(parsed['duration_seconds']), Decimal('3e-10'))
        # Ascending VCD ranges retain left-to-right bit identity. The event at
        # start is included; the event at end is excluded; Z time remains Z.
        self.assertEqual([signals['tb/soc/data[0]'][key] for key in ['T0','T1','TZ','TC']], [10,10,10,1])
        self.assertEqual([signals['tb/soc/data[1]'][key] for key in ['T0','T1','TZ','TC']], [0,20,10,1])
        self.assertEqual(signals['tb/soc/alias[1]']['TC'], signals['tb/soc/data[0]']['TC'])
        self.assertEqual(signals['tb/soc/scalar']['T1'], 30)
        self.assertEqual(signals['tb/soc/scalar']['TC'], 1)

    def test_dumpon_snapshot_is_not_an_event_and_off_gap_is_rejected(self):
        header = '''$timescale 1 ns $end
$scope module tb $end
$scope module soc $end
$var wire 1 ! q $end
$upscope $end $upscope $end
$enddefinitions $end
$dumpvars 0! $end
#1 $dumpoff x! $end
#10 $dumpon 1! $end
#20
'''
        _, parsed = self.convert(header, 10, 20)
        self.assertEqual(parsed['signals'][0]['TC'], 0)
        self.assertEqual(parsed['signals'][0]['T1'], 10)
        with self.assertRaisesRegex(ValueError, 'disabled'):
            self.convert(header, 5, 20)
        with self.assertRaisesRegex(ValueError, 'before task end'):
            self.convert(header, 10, 30)

    @unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'), 'Icarus required for independent waveform experiment')
    def test_real_sv_probe_waveform_matches_hand_counted_saif_expectation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            subprocess.run(['iverilog', '-g2012', '-DXU_PROBE_VCD', '-s', 'xu_activity_probe',
                            '-o', str(directory/'sim.vvp'), str(ROOT/'tools/ppa/xu_activity_probe.sv')], check=True)
            result = subprocess.run(['vvp', str(directory/'sim.vvp')], cwd=str(directory),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
            self.assertIn(b'XU_ACTIVITY_PROBE_FINISHED mode=all', result.stdout)
            for name, begin, end in [('first', 22000000, 62000000), ('second', 82000000, 122000000)]:
                with (directory/'probe.vcd').open() as source:
                    activity.vcd_to_saif(source, directory/(name+'.saif'), begin, end, 'xu_activity_probe/u_probe')
                self.assertTrue(activity.match_probe(activity.read_saif(directory/(name+'.saif')), name))

    def test_saif_rejects_dwell_duration_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'bad.saif'
            path.write_text('(SAIFILE (TIMESCALE 1 ns) (DURATION 10) (INSTANCE dut (NET (q (T0 9)(T1 0)(TX 0)(TC 0)))))')
            with self.assertRaisesRegex(ValueError, 'dwell'):
                activity.read_saif(path)


class EnergyEvidenceTests(unittest.TestCase):
    def file(self, directory, name, text):
        path = directory/name
        path.write_text(text)
        return dict(path=str(path), sha256=activity.sha(path))

    def fixture(self, directory):
        common = self.file(directory, 'design', 'frozen netlist / constraints / firmware / Liberty for host fixture only')
        scopes = [dict(name=name, prefix='tb/soc/'+name) for name in sorted(activity.REQUIRED_SCOPES)]
        configuration = dict(nominal_hz=150000000, power_method='averaged', pvt='host fixture',
                             interconnect_model='explicit pre-layout estimate',
                             netlist=common, constraints=common, firmware=common, testbench=common,
                             libraries=[dict(common, role='standard_cell'), dict(common, role='sram')],
                             memories=[dict(name=name, logical_bits=bits, macro_count=bits//16384)
                                       for name,bits in activity.REQUIRED_MEMORY_BITS.items()],
                             hf_clock_path='tb/soc/clk', activity_scopes=scopes)
        tasks = []
        for index in range(12):
            # A deliberately unequal duration/power pair distinguishes
            # duration-weighted energy from an incorrect mean(P)*mean(t).
            ticks = (index+1)*1000
            body = '(NET (clk (T0 {half})(T1 {half})(TX 0)(TC {edges})))'.format(half=ticks//2, edges=(index+1)*300)
            for group in scopes:
                body += '(INSTANCE '+group['name']+' (NET (a (T0 '+str(ticks)+')(T1 0)(TX 0)(TC 1))'
                body += '(b (T0 '+str(ticks)+')(T1 0)(TX 0)(TC 1))))'
            saif = self.file(directory, 'task-{}.saif'.format(index),
                             '(SAIFILE (TIMESCALE 1 ns)(DURATION '+str(ticks)+')(INSTANCE tb (INSTANCE soc '+body+')))')
            boundary = self.file(directory, 'task-{}.log'.format(index),
                                 'XU_CACHE_RELOAD task={} done_before_begin=1 scope=shared_fixture\n'.format(index)+
                                 'XU_ACTIVITY_BEGIN task={} tick=10\n'.format(index)+
                                 'XU_ACTIVITY_END task={} tick={}\n'.format(index, ticks+10))
            macro_review = dict(schema='xu-sram-power-coverage-v1', status='REVIEWED',
                                saif_sha256=saif['sha256'], netlist_sha256=common['sha256'],
                                library_sha256=[common['sha256']]*2,
                                groups=[dict(name=g['name'], expected_count=g['macro_count'], observed_count=g['macro_count'],
                                             library_power_modeled_count=g['macro_count'], missing_input_pin_count=0,
                                             unknown_input_pin_count=0, total_power_w='0.01') for g in configuration['memories']])
            review = self.file(directory, 'task-{}-sram.json'.format(index), json.dumps(macro_review))
            cache = self.file(directory, 'task-{}-cache.json'.format(index), json.dumps(dict(
                schema='xu-task-cache-policy-review-v1', status='REVIEWED', task_id=index,
                configuration_sha256=activity.canonical_hash(configuration), saif_sha256=saif['sha256'],
                task_cache_invalidated_before_begin=True, complete_parameter_upload_inside_window=True,
                no_cross_task_reuse=True, evidence=[common])))
            tasks.append(dict(task_id=index, configuration_sha256=activity.canonical_hash(configuration), saif=saif,
                              input_manifest=common, cache_reload_log=boundary, boundary_log=boundary, cache_review=cache,
                              window=dict(begin_tick=10, end_tick=ticks+10, timescale_seconds='1e-9',
                                          hf_period_seconds=str(Decimal(1)/150000000), convention='edge_to_edge',
                                          start_event='first_input_or_parameter_read_accepted', end_event='final_y_write_response_retired'),
                              power=dict(total_w=str(index+1), report=common, activity_before=common, activity_after=common,
                                         annotation_review=common, sram_review=review, unannotated_policy='propagate_and_review')))
        return dict(schema='xu-soc-activity-energy-v1', configuration=configuration, tasks=tasks)

    def test_twelve_task_energy_uses_each_window_duration(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = activity.audit_energy(self.fixture(Path(temporary)))
            self.assertEqual(Decimal(result['total_energy_joules']), Decimal('0.000650'))
            self.assertEqual(Decimal(result['energy_per_task_joules']), Decimal('0.000650')/12)
            self.assertEqual(Decimal(result['duration_weighted_power_w']), Decimal(650)/78)
            self.assertEqual(result['status'], 'AUDITED_ESTIMATE_NOT_CONTEST_QUALIFIED')

    def test_missing_task_mixed_design_wrong_duration_and_wrong_frequency_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            baseline = self.fixture(Path(temporary))
            for label, mutate in [
                ('twelve', lambda m: m['tasks'].pop()),
                ('frozen', lambda m: m['tasks'][0].update(configuration_sha256='different')),
                ('duration', lambda m: m['tasks'][0]['window'].update(end_tick=1011)),
                ('150 MHz', lambda m: m['tasks'][0]['window'].update(hf_period_seconds='4e-9')),
                ('zero', lambda m: m['tasks'][0]['power'].update(unannotated_policy='zero')),
                ('cache', lambda m: m['tasks'][0].pop('cache_review')),
            ]:
                candidate = copy.deepcopy(baseline)
                mutate(candidate)
                with self.subTest(label=label), self.assertRaisesRegex(ValueError, label):
                    activity.audit_energy(candidate)

    def test_wrapper_only_activity_and_unmodeled_sram_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            baseline = self.fixture(Path(temporary))
            candidate = copy.deepcopy(baseline)
            candidate['configuration']['activity_scopes'][0]['prefix'] = 'tb/soc/nonexistent'
            freeze = activity.canonical_hash(candidate['configuration'])
            for task in candidate['tasks']:
                task['configuration_sha256'] = freeze
                review_path = Path(task['cache_review']['path'])
                cache = json.loads(review_path.read_text())
                cache['configuration_sha256'] = freeze
                review_path.write_text(json.dumps(cache))
                task['cache_review']['sha256'] = activity.sha(review_path)
            with self.assertRaisesRegex(ValueError, 'scope absent'):
                activity.audit_energy(candidate)
            baseline = self.fixture(Path(temporary))
            path = Path(baseline['tasks'][0]['power']['sram_review']['path'])
            review = json.loads(path.read_text())
            review['groups'][0]['library_power_modeled_count'] = 0
            path.write_text(json.dumps(review))
            baseline['tasks'][0]['power']['sram_review']['sha256'] = activity.sha(path)
            with self.assertRaisesRegex(ValueError, 'unmodeled'):
                activity.audit_energy(baseline)


if __name__ == '__main__':
    unittest.main()
