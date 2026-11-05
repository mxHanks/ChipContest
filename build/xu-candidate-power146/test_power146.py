#!/usr/bin/env python3
"""Host checks only: exact mixed-macro mapping, native evidence and fail-closed CLI."""
import argparse
import copy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bridge146 as bridge
import common146 as common
import native146 as native
import power146 as power
import build_jobs146 as jobs

reader = common.load('xu146_test_reader', HERE/'assets/xu_soc_activity.py')
helper = common.load('xu146_test_helper', HERE/'assets/xu_sram_activity_alias.py')


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='xu146-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.groups = [dict(name='group%d' % i, macro_ref=ref, count=1,
                            instance_pattern='u_accel_icb_slave/core/banks_*')
                       for i, ref in enumerate(bridge.PIN_WIDTHS)]
        self.rtl = dict(schema='xu-profile-macro-inventory145-v1', status='ELABORATED_REVIEW_PENDING_NOT_QUALIFIED',
            dut_scope='tb_xu_soc_ppa.dut', macro_count=2, pin_bit_count=131, macros=[])
        self.tsv = self.root/'macro-pins.tsv'
        rows = ['kind\tcell\tref_or_pin\tlibcell_or_direction']
        for i, (ref, widths) in enumerate(bridge.PIN_WIDTHS.items()):
            relative = 'u_accel_icb_slave/core/banks_%d/macro' % i
            native_name = 'u_accel_icb_slave/core/banks_%d.macro' % i
            self.rtl['macros'].append(dict(relative_instance=relative, instance='tb_xu_soc_ppa.dut.'+relative.replace('/', '.'),
                ref_name=ref, pin_widths=widths, group='group%d' % i))
            rows.append('MACRO\t%s\t%s\tlib/%s' % (native_name, ref, ref))
            for name in sorted(bridge.pin_names(ref)):
                rows.append('PIN\t%s\t%s/%s\t%s' % (native_name, native_name, name, 'out' if name.startswith('Q[') else 'in'))
        self.tsv.write_text('\n'.join(rows)+'\n')
        self.inventory = bridge.inventory_rows(self.tsv, self.groups)

    def saif(self, path, conflict=False):
        stats = lambda: [['T0', '2'], ['T1', '2'], ['TX', '2'], ['TZ', '1'], ['TB', '3'], ['TC', '7'], ['IG', '5']]
        core = ['INSTANCE', 'core']
        for i, macro in enumerate(self.rtl['macros']):
            pins = ['PORT']+[[helper.atom(name)]+stats() for name in sorted(bridge.pin_names(macro['ref_name']))]
            core.append(['INSTANCE', 'banks_%d' % i, ['INSTANCE', 'macro', pins,
                ['NET', [helper.atom('behavioral_memory[0]')]+stats()]]])
        if conflict:
            core.append(['INSTANCE', r'banks_0\.macro', ['PORT', ['CLK', ['T0', '3'], ['T1', '1'],
                ['TX', '2'], ['TZ', '1'], ['TB', '3'], ['TC', '7'], ['IG', '5']]]])
        tree = ['SAIFILE', ['SAIFVERSION', '"2.0"'], ['TIMESCALE', '1', 'fs'], ['DURATION', '10'],
            ['INSTANCE', 'tb_xu_soc_ppa', ['INSTANCE', 'dut', ['NET', [helper.atom('literal.name[0]')]+stats()],
            ['INSTANCE', 'u_accel_icb_slave', core]]]]
        with path.open('w') as stream: helper.write_sexpr(stream, tree)

    def measured(self):
        pairs, _ = bridge.bijection(self.rtl, self.inventory)
        return [dict(path=value, mapped_path=value[len(bridge.STRIP)+1:], kind='PORT', T0=2, T1=2, TX=2, TZ=1, TB=3, TC=7, IG=5)
                for value in pairs.values()]

    def reports(self, pins, wrapped=False):
        for phase in ('before', 'after'):
            with (self.root/('sram-pins-%s.rpt' % phase)).open('w') as stream:
                for index, pin in enumerate(pins):
                    name = pin['mapped_path']
                    stream.write('XU_SRAM_PIN name='+name+'\nDesign : xu_soc_ppa_top\n')
                    stream.write('    string activity_checker_status Annotated\n')
                    stream.write('    string full_name'+('\n        ' if wrapped and index == 0 else ' ')+name+'\n')
                    for kind, attr, value in [('double', 'glitch_rate', '0'), ('float', 'static_probability', '0.5'),
                                              ('double', 'toggle_rate', '0'), ('float', 'x_probability', '0')]:
                        stream.write('    %s %s %s\n' % (kind, attr, value))
            for source in ('file', 'default', 'propagated', 'no_switching_activity'):
                (self.root/('source-%s-%s.rpt' % (source, phase))).write_text('List of nets with activity from '+source+'\n\tnet\t'+pins[0]['mapped_path']+'\n')


class BridgeChecks(Fixture):
    def test_complete_mixed_67_64_bit_inventory(self):
        self.assertEqual([len(row['pins']) for row in self.inventory], [67, 64])
        pairs, rows = bridge.bijection(self.rtl, self.inventory)
        self.assertEqual(len(pairs), 131); self.assertEqual(len(rows), 2)
        self.assertTrue(any('/banks_0.macro/A[9]' in p for p in pairs.values()))
        self.assertTrue(any('/banks_1.macro/A[6]' in p for p in pairs.values()))

    def test_omitted_pin_extra_macro_and_wrong_direction_rejected(self):
        original = self.tsv.read_text()
        attempts = [original.replace(next(line+'\n' for line in original.splitlines() if line.startswith('PIN\t')), '', 1),
            original+'MACRO\tunexpected\tRAMSP128X16\tlib/RAMSP128X16\n', original.replace('\tout\n', '\tin\n', 1)]
        for text in attempts:
            self.tsv.write_text(text)
            with self.assertRaises(ValueError): bridge.inventory_rows(self.tsv, self.groups)

    def test_native_literal_dot_collision_is_rejected(self):
        changed = copy.deepcopy(self.inventory)
        changed.append(dict(changed[0], instance=changed[0]['instance'].replace('banks_0.macro', 'banks_0/macro')))
        with self.assertRaisesRegex(ValueError, 'collision'): bridge.bijection(self.rtl, changed)

    def test_wrong_group_or_ref_is_rejected(self):
        for key, value in [('group', 'other'), ('ref_name', 'RAMSP128X16')]:
            changed = copy.deepcopy(self.inventory); changed[0][key] = value
            with self.assertRaises(ValueError): bridge.bijection(self.rtl, changed)

    def test_lossless_unknowns_and_unrelated_literal_dots(self):
        source, mapped = self.root/'raw.saif', self.root/'mapped.saif'; self.saif(source)
        before = common.identity(source)
        receipt, measured = bridge.relocate(source, mapped, self.rtl, self.inventory, reader, helper)
        self.assertEqual(common.identity(source), before)
        self.assertEqual(receipt['pin_bit_count'], 131)
        self.assertEqual(measured['measured_summary']['measured_unknown_bit_ticks'], 131*6)
        signals = {(r['kind'], r['path']): r for r in reader.read_saif(mapped)['signals']}
        self.assertEqual(signals['NET', bridge.STRIP+'/literal.name[0]']['TB'], 3)
        self.assertEqual(signals['PORT', bridge.STRIP+'/u_accel_icb_slave/core/banks_0.macro/A[9]']['IG'], 5)
        self.assertEqual(signals['NET', bridge.STRIP+'/u_accel_icb_slave/core/banks_0/macro/behavioral_memory[0]']['TX'], 2)
        self.assertEqual(receipt['measured_summary']['duration_ticks'], 10)

    def test_conflicting_existing_native_pin_fails(self):
        source, mapped = self.root/'raw.saif', self.root/'mapped.saif'; self.saif(source, conflict=True)
        with self.assertRaisesRegex(ValueError, 'conflict'): bridge.relocate(source, mapped, self.rtl, self.inventory, reader, helper)
        self.assertFalse(mapped.exists())

    def test_existing_output_is_never_clobbered(self):
        source, mapped = self.root/'raw.saif', self.root/'mapped.saif'; self.saif(source); mapped.write_text('keep')
        with self.assertRaises(ValueError): bridge.relocate(source, mapped, self.rtl, self.inventory, reader, helper)
        self.assertEqual(mapped.read_text(), 'keep')


class NativeChecks(Fixture):
    def test_streaming_report_unknown_q_never_promoted_by_getter_zero(self):
        pins = self.measured(); self.reports(pins, wrapped=True)
        measured = self.root/'measured.json'; common.write(measured, dict(pins=pins))
        before = common.identity(self.root/'sram-pins-before.rpt')
        read_text = Path.read_text
        def guarded(path, *args, **kwargs):
            if path.name.startswith('sram-pins-'): raise AssertionError('native report read all at once')
            return read_text(path, *args, **kwargs)
        with patch.object(Path, 'read_text', guarded): result = native.audit(self.root, measured)
        self.assertEqual(result['qualification'], 'NOT_QUALIFIED')
        self.assertEqual(result['phases'][0]['original'], before)
        self.assertEqual(result['phases'][0]['selected_attribute_counts']['MEASURED_UNKNOWN_ANY_POSITIVE'], 131)
        self.assertEqual(result['phases'][0]['selected_attribute_counts']['x_probability:NATIVE_ZERO'], 131)
        self.assertIn('getter', ' '.join(result['limitations']))
        self.assertEqual(result['phases'][1]['before_after_counts']['x_probability:UNCHANGED'], 131)
        self.assertEqual(result['phases'][0]['source_membership_counts']['file'], 1)

    def test_duplicate_native_pin_and_missing_required_attribute_fail(self):
        pins = self.measured()[:1]
        for mode in ('duplicate', 'missing'):
            self.reports(pins)
            path = self.root/'sram-pins-before.rpt'
            text = path.read_text()
            path.write_text(text+text if mode == 'duplicate' else text.replace('    float x_probability 0\n', ''))
            with self.assertRaises(ValueError): native.audit_phase(self.root, 'before', {p['mapped_path']: p for p in pins}, None, self.root/(mode+'.jsonl'))

    def test_independent_audit_does_not_touch_original_compact_outputs(self):
        pins = self.measured(); self.reports(pins)
        measured = self.root/'measured.json'; common.write(measured, dict(pins=pins))
        first = native.audit(self.root, measured)
        original = common.identity(self.root/'native-audit.json')
        target = self.root/'audit'; target.mkdir(); second = native.audit(self.root, measured, target)
        self.assertEqual(common.identity(self.root/'native-audit.json'), original)
        for left, right in zip(first['phases'], second['phases']): self.assertEqual(left['compact']['sha256'], right['compact']['sha256'])

    def test_sentinel_and_nonfinite_getters_are_distinguished(self):
        self.assertEqual(native.category('x_probability', '-1'), 'NATIVE_SENTINEL')
        self.assertEqual(native.category('toggle_rate', '-1'), 'NATIVE_SENTINEL')
        self.assertEqual(native.category('x_probability', 'NaN'), 'NATIVE_TEXT')
        self.assertEqual(native.category('static_probability', None), 'ABSENT_FROM_NATIVE_REPORT')


class RuntimeChecks(Fixture):
    def test_selected_map_accelerator_area_has_exact_hierarchy_boundary(self):
        path = self.root/'area.tsv'
        path.write_text('cell\tlibcell\tarea_native_library_units\n'+power.ACCEL+'/macro\tlib/RAMSP1024X16\t2000000\n'+
            power.ACCEL+'/gate\tlib/AND2\t5.5\n'+power.ACCEL+'Other/gate\tlib/AND2\t700000\n'+'u_other/gate\tlib/AND2\t10\n')
        result = power.measured_area(path)
        self.assertEqual(result['accelerator']['area_mm2_diagnostic'], '2.0000055')
        self.assertEqual(result['full_soc']['area_mm2_diagnostic'], '2.7000155')
        self.assertTrue(result['accelerator']['diagnostic_within_limit'])
        self.assertEqual(result['accelerator']['sram_leaf_count'], 1)
        path.write_text(path.read_text().replace('2000000', '2300000'))
        self.assertFalse(power.measured_area(path)['accelerator']['diagnostic_within_limit'])

    def test_missing_accelerator_area_cannot_reuse_full_soc_area(self):
        path = self.root/'area.tsv'; path.write_text('cell\tlibcell\tarea_native_library_units\nu_other\tlib/AND2\t1\n')
        with self.assertRaises(ValueError): power.measured_area(path)

    def test_duration_uses_each_actual_layer_and_power_is_full_soc(self):
        path = self.root/'power.rpt'
        path.write_text('Design : xu_soc_ppa_top\nDynamic Power Units = 1 W\nLeakage Power Units = 1 W\n'+
            '\n'.join(label+' = '+value+' (x)' for label, value in [('Net Switching Power', '0.01'),
            ('Cell Internal Power', '0.02'), ('Cell Leakage Power', '0.005'), ('Total Power', '0.035')])+'\n')
        base = dict(layer=dict(cycles=990656), activity_window=dict(formal_elapsed_cycles=868343, duration_ticks=5788953333333,
                    timescale_seconds='1e-15'), measured_summary=dict(measured_unknown_bit_ticks=10))
        result = power.diagnostic(self.root, base, dict(status='same_map'))
        self.assertEqual(Decimal(result['diagnostic_energy_j']), Decimal('5788953333333e-15')*Decimal('.035'))
        changed = copy.deepcopy(base); changed['activity_window']['duration_ticks'] = 6604373333334
        self.assertNotEqual(power.diagnostic(self.root, changed, {})['diagnostic_energy_j'], result['diagnostic_energy_j'])
        self.assertEqual(result['qualification'], 'NOT_QUALIFIED')
        path.write_text(path.read_text().replace('xu_soc_ppa_top', 'wrapper'))
        with self.assertRaises(ValueError): power.diagnostic(self.root, base, {})

    def test_native_run_is_durable_and_resume_never_reexecutes(self):
        marker = 'TEST146_DONE'
        command = [sys.executable, '-c', 'print("Version T-2022.03-SP5-1"); print("'+marker+'")']
        state = common.execute(command, self.root, marker, 10, None)
        self.assertEqual(state['returncode'], 0)
        log = common.identity(self.root/'pt.log')
        with self.assertRaises(ValueError): common.execute(command, self.root, marker, 10, None)
        resumed = common.execute(command, self.root, marker, 10, None, resume=True)
        self.assertEqual(resumed['pid'], state['pid']); self.assertEqual(common.identity(self.root/'pt.log'), log)
        with (self.root/'pt.log').open('a') as stream: stream.write('Error: changed native log\n')
        with self.assertRaises(ValueError): common.execute(command, self.root, marker, 10, None, resume=True)

    def test_failed_fresh_campaign_saves_failure_and_repeat_preserves_it(self):
        out = self.root/'failed'
        command = [sys.executable, '-B', str(HERE/'power146.py'), 'campaign', '--profile', 'not-a-profile',
            '--source-root', str(self.root), '--freeze-receipt', str(self.root/'missing'), '--adoption-receipt', str(self.root/'missing'),
            '--activity-root', str(self.root/'activity'), '--out', str(out)]
        first = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(first.returncode, 1)
        failure = common.identity(out/'execution.json')
        self.assertEqual(common.read(out/'execution.json')['status'], 'FAIL_DIAGNOSTIC_NOT_QUALIFIED')
        second = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(second.returncode, 1); self.assertEqual(common.identity(out/'execution.json'), failure)

    def test_eight_generated_jobs_depend_on_own_activity_and_freeze(self):
        receipts = HERE.parent/'xu-score-resume-20261103/queue149/eight-candidate-freeze-queue-20261105-138'
        if not receipts.exists(): self.skipTest('actual149 snapshot absent on this host')
        args = argparse.Namespace(bundle_root=Path('/deployed146'), activity_tools=Path('/deployed145'), output_root=Path('/power146'),
            activity_root=Path('/activity145'), freeze_root=Path('/freeze138'), receipt_snapshot=receipts,
            local_activity_tools=HERE.parent/'xu-profile-activity145', jobs_out=self.root/'jobs', python='/bin/python3',
            pt=power.PT, lc_root=power.LC, timeout=21600, inventory_timeout=900)
        result = jobs.build(args)
        self.assertEqual(result['candidate_count'], 8)
        identities, outputs = set(), set()
        for row in result['jobs']:
            job = common.read(args.jobs_out/(row['job_id']+'.json'))
            self.assertEqual(job['dependencies'], [dict(id='eight_freeze138', policy='success'), dict(id='activity145_'+row['profile'], policy='success')])
            self.assertEqual(job['process_contains'], job['output_root'])
            self.assertEqual(job['success_statuses'], [power.STATUS])
            self.assertEqual(job['failure_statuses'], ['FAIL_DIAGNOSTIC_NOT_QUALIFIED'])
            self.assertIn('/power146/'+row['profile'], job['argv'])
            self.assertTrue(any(r['path'] == '/freeze138/'+row['profile']+'/freeze.json' for r in job['frozen_inputs']))
            identities.add(job['id']); outputs.add(job['output_root'])
        self.assertEqual((len(identities), len(outputs)), (8, 8))
        with self.assertRaises(ValueError): jobs.build(args)

    def test_json_duplicates_and_symlink_inputs_are_rejected(self):
        path = self.root/'input.json'; path.write_text('{"a":1,"a":2}')
        with self.assertRaises(ValueError): common.read(path)
        alias = self.root/'alias'; alias.symlink_to(path)
        with self.assertRaises(ValueError): common.identity(alias)

    def test_tcl_uses_same_selected_map_and_reports_all_native_sram_pins(self):
        manifest = dict(netlist=dict(path='/own/mapped.v'), analysis_sdc=dict(path='/own/constraints.sdc'),
            libraries=[dict(path='/db/ss.db')], memory_groups=self.groups, accelerator_hierarchy=power.ACCEL)
        script = power.inventory_tcl(manifest, 'UNIQUE')
        self.assertIn('read_verilog {/own/mapped.v}', script)
        self.assertIn('mapped-leaf-area.tsv', script)
        self.assertIn('RAMSP128X16', script)
        power_script = power.power_tcl(manifest, dict(macro_names=[m['instance'] for m in self.inventory],
            saif=dict(path='/measured/task-mapped.saif'), completion_marker='POWER_DONE'))
        self.assertIn('report_power -verbose', power_script)
        self.assertIn('report_attribute -application $p', power_script)
        self.assertEqual(power_script.count('POWER_DONE'), 1)
        self.assertNotIn('set_switching_activity', power_script)
        with self.assertRaises(ValueError): common.tcl('/unsafe{path}')


if __name__ == '__main__': unittest.main()
