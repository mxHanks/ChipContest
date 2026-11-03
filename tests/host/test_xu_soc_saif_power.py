"""Synthetic host handoffs and failure guards, never PT/silicon power results."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_saif_power_test', ROOT / 'tools/scripts/xu_soc_saif_power.py')
power = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(power)
collector, ppa = power.collector, power.ppa


def log_fixture(task=0):
    cycles, begin = 2000000, 31000000
    end = begin + round((cycles - 1) * 20000000 / 3)
    request = begin - 20000000
    perf = dict((key, 0) for key in collector.contract.PERFORMANCE_FIELDS)
    perf.update(collector.contract.task_contract('bias-hw-window'))
    perf.update(layer=0, cycles=cycles, w_load=cycles, busy=perf['mac_fire'])
    return '\n'.join([
        'TASK_PASS layer=0 outputs=25344 writes=50688 cycles=%d firmware_cycles=10' % cycles,
        'PERF_TASK ' + ' '.join('%s=%d' % (key, perf[key]) for key in collector.contract.PERFORMANCE_FIELDS),
        'SOC_PASS tasks=1 outputs=25344 writes=50688',
        'PPA_WINDOW_BEGIN layer=0 cycle=100 time_ns=1.0 tick_fs=%d' % begin,
        'PPA_WINDOW_END layer=0 cycle=%d time_ns=2.0 tick_fs=%d' % (99 + cycles, end),
        'XU_CLOCK_STATIC_PASS checked_hf_edges=%d' % (cycles + 100),
        'XU_ACTIVITY_BEGIN task=%d tick=%d' % (task, request), 'XU_ACTIVITY_END task=%d tick=%d' % (task, end),
        'XU_CACHE_INITIAL task=%d fresh_process=1 cache_enable=0 busy=0 prior_uploads=0 prior_starts=0' % task,
        'XU_CACHE_UPLOAD_PASS task=%d w=16384 bias=256 x=6336 rows=99 starts=3168 window=inside checked_data=1' % task,
        'XU_TASK_CLEAR_BEGIN task=%d cycle=50 tick=1' % task,
        'XU_TASK_CLEAR_LAST_WRITE task=%d cycle=90 tick=2 writes=33697' % task,
        'XU_TASK_CLEAR_OBSERVED writes=33697 w=16384 bias=256 legacy_bias=8 x=64 drained=1 cache_enable=0 idle=1 source_request=1 task_setup_writes=2',
        'XU_SOURCE_REQUEST task=%d cycle=97 tick=%d' % (task, request),
        'XU_SOURCE_ACCEPT task=%d cycle=100 tick=%d' % (task, begin),
        ('XU_TASK_WINDOW task=%d request_cycle=97 accept_cycle=100 end_cycle=%d initial_wait_cycles=3 '
         'legacy_inclusive_cycles=%d formal_inclusive_cycles=%d formal_elapsed_cycles=%d') % (task, 99 + cycles, cycles, cycles + 3, cycles + 2)])


def synthetic_raw(path, config, duration):
    alias = collector.sram_alias
    mapping, pairs = alias.validate_mapping(config['mapping_file']['path'])
    root = ['SAIFILE', ['DESIGN', '"xu synthetic host fixture, not measured VCS activity"'],
            ['TIMESCALE', '1', 'fs'], ['DURATION', str(duration)]]
    branches = {}

    def append(name, values):
        parts = name.split('/')
        for depth in range(1, len(parts)):
            scope = '/'.join(parts[:depth])
            if scope not in branches:
                node = ['INSTANCE', alias.atom(parts[depth - 1])]
                (root if depth == 1 else branches['/'.join(parts[:depth - 1])]).append(node)
                branches[scope] = node
        parent = branches['/'.join(parts[:-1])]
        section = next((node for node in parent[2:] if node[0] == 'NET'), None)
        if section is None:
            section = ['NET']
            parent.append(section)
        section.append([alias.atom(parts[-1])] + [[key, str(value)] for key, value in values.items()])

    for source, target in pairs.items():
        dtcm = '/u_e203_dtcm_ram/' in target
        pin = target.rsplit('/', 1)[1]
        values = dict(T0=duration, T1=0, TX=0, TC=0)
        if dtcm and pin in ('CEN', 'RET1N'):
            values.update(T0=0, T1=duration)
        elif dtcm and pin == 'Q[0]':
            values.update(T0=0, TX=duration)
        elif not dtcm and pin == 'CLK':
            values.update(T0=duration // 2, T1=duration - duration // 2, TC=4000004)
        append(source, values)
    prefix = power.STRIP
    append(prefix + '/hfextclk', dict(T0=duration // 2, T1=duration - duration // 2, TX=0, TC=4000004))
    for name in ('cmd', 'rsp'):
        append(prefix + '/u_soc/u_e203_cpu_top/u_e203_biu/' + name, dict(T0=duration, T1=0, TX=0, TC=1))
    with path.open('w') as stream:
        alias.write_sexpr(stream, root)


class SaifPowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = ppa.inventory(ROOT)

    def implementation(self, directory):
        impl = ppa.template(self.inventory)
        impl['replacements'] = {ppa.RTL + '/general/sirv_sim_ram.v': power.identity(ROOT / 'tools/ppa/xu_sirv_sram_adapter.sv'),
                                ppa.RTL + '/perips/mem_1024x16.sv': power.identity(ROOT / 'tools/ppa/xu_weight_sram_adapter.sv')}
        impl['added_sources'] = [power.identity(ROOT / 'tools/ppa' / name) for name in ('xu_soc_ppa_top.sv', 'xu_shared_icb_sram.sv')]
        impl['libraries'] = []
        for role in ('standard_cell', 'sram'):
            path = directory / (role + '.db')
            path.write_text('SYNTHETIC HOST LIBRARY IDENTITY ONLY, NOT PT: ' + role)
            impl['libraries'].append(dict(power.identity(path), role=role))
        impl['constraints'] = power.identity(ROOT / 'tools/ppa/xu_full_soc.sdc')
        review = dict(status='REVIEWED', constraints_sha256=impl['constraints']['sha256'])
        for key in ('primary_clocks', 'generated_clock_policy', 'reset_exceptions', 'clock_domain_crossings', 'untested_check_policy'):
            review[key] = 'SYNTHETIC HOST REVIEW ONLY'
        path = directory / 'review.json'
        power.write(path, review)
        impl['clock_review'] = power.identity(path)
        path = directory / 'proof.json'
        power.write(path, ppa.mapping_review_template(impl))
        impl['mapping_proof'] = power.identity(path)
        path = directory / 'implementation.json'
        power.write(path, impl)
        return path, impl

    def fixture(self, directory):
        impl_path, impl = self.implementation(directory)
        netlist = directory / 'mapped.v'
        netlist.write_text('// SYNTHETIC HOST NETLIST IDENTITY, NEVER PT EXECUTED\n')
        vendor = directory / 'vendor.sv'
        vendor.write_text('// SYNTHETIC HOST VENDOR IDENTITY\n')
        build = directory / 'simulator'
        build.mkdir()
        alias_config = collector.prepare_sram_pin_alias(build, ROOT / 'tools/ppa/xu_weight_sram_adapter.sv')
        original = directory / 'original/layer_00'
        original.mkdir(parents=True)
        hashes = {}
        for tensor in collector.TENSORS:
            path = original / (tensor + '.mem')
            path.write_text('0000\n')
            hashes[path.name] = power.sha(path)
        task_dir = directory / 'task_00'
        task_dir.mkdir()
        manifest = collector.materialize_task(original.parent, task_dir / 'vectors', 0, dict(layer=0, sha256=hashes))
        log = log_fixture()
        (task_dir / 'simulation.log').write_text(log)
        layer, window = collector.checked_log(log, 0, 'bias-hw-window', True)
        synthetic_raw(task_dir / 'task.saif', alias_config, window['duration_ticks'])
        inspected = collector.inspect_task_activity(task_dir, window, collector.STATIC_SCOPE_DECLARATIONS, alias_config)
        sources = {str(ROOT / relative): record['sha256'] for relative, record in self.inventory['platform_source'].items()
                   if relative not in impl['replacements']}
        sources.update({record['path']: record['sha256'] for record in list(impl['replacements'].values()) + impl['added_sources']})
        sources[alias_config['observer_source']['path']] = alias_config['observer_source']['sha256']
        config = dict(rtl_sources_sha256=sources, netlist=power.identity(netlist), constraints=impl['constraints'],
                      analysis_sdc_sha256=impl['constraints']['sha256'], nominal_hz=150000000,
                      activity_scope=collector.SCOPE, monitoring_policy='rtl_on', sram_pin_alias=alias_config,
                      firmware_configuration=dict(schedule='bias-hw-window', optimization='-O2', experiment='none'),
                      task_clear_recipe=dict(name='cpu-mmio-clear-before-source-request-v1'),
                      declared_static_scopes=collector.STATIC_SCOPE_DECLARATIONS)
        # These are synthetic identity fixtures, not actual compiler or VCS receipts.
        for key in ('firmware_image', 'firmware_elf', 'original_tb', 'testbench', 'vendor_model'):
            config[key] = power.identity(vendor)
        config_hash = collector.activity.canonical_hash(config)
        task = dict(task_id=0, status='COLLECTED_REVIEW_PENDING', local_scoreboard_layer=0,
                    configuration_sha256=config_hash, layer=layer, activity_window=window,
                    boundary_log=power.identity(task_dir / 'simulation.log'), input_manifest=power.identity(task_dir / 'vectors/input-manifest.json'),
                    saif=inspected['saif'], sram_pin_alias_capture=inspected['sram_pin_alias_capture'],
                    cache_policy={key: True for key in ('fresh_process', 'reset_cache_enable_zero_observed',
                                  'complete_fixture_matched_uploads_inside_window_observed', 'no_prior_task_in_process', 'physical_initial_clearing_proven')})
        report = dict(schema='xu-soc-isolated-task-activity-v1', status='PARTIAL_COLLECTED_REVIEW_PENDING',
                      requested_task_ids=[0], taskset_complete=False, clear_task_before_window=True, sram_pin_alias=True,
                      nominal_hz=150000000, clock_mode='nominal150', configuration=config, configuration_sha256=config_hash,
                      tasks=[task], runner=power.identity(collector.__file__), helpers=[power.identity(collector.activity.__file__)],
                      original_task_vectors=[dict(layer=i, sha256=hashes) for i in range(12)],
                      taskset_inputs_sha256=collector.activity.canonical_hash({'0': manifest}),
                      binary=power.identity(vendor), vendor_model=power.identity(vendor), firmware_build=dict(fixture=power.identity(vendor)),
                      firmware_input_sources_sha256={str(vendor): power.sha(vendor)}, build_command=['HOST_SYNTHETIC_NOT_VCS'])
        activity = directory / 'result.json'
        power.write(activity, report)
        macros = []
        for macro in alias_config['mapping']['macros']:
            canonical = collector.sram_alias.slash(macro['instance'])[len(power.STRIP) + 1:]
            # Synthetic modeled DC spelling: literal dotted leaf after storage.
            actual = canonical.replace('/macro_storage/', '/macro_storage.').replace('/depth_bank', '.depth_bank').replace('/width_lane', '.width_lane')
            if '/macro_storage.' in actual:
                actual = actual.rsplit('/macro', 1)[0] + '.macro'
            macros.append(dict(instance=actual, ref_name='RAMSP1024X16', lib_cell='HOST_LIBRARY/RAMSP1024X16',
                pins=[dict(name=name, full_name=actual + '/' + name, direction='out' if name.startswith('Q[') else 'in')
                      for name in sorted(power.mapped_macros.PIN_NAMES)]))
        power.write(directory / 'mapped-inventory.json', dict(schema=power.mapped_macros.INVENTORY_SCHEMA,
            status='EXPORTED_REVIEW_PENDING', netlist=power.identity(netlist), libraries=impl['libraries'],
            provenance=dict(host_fixture=power.identity(vendor), scope='SYNTHETIC HOST INVENTORY; not actual PT export'),
            macro_count=336, pin_bit_count=22512, macros=macros))
        return impl_path, impl, activity, report, netlist

    def power_prepare(self, activity, *args, **kwargs):
        kwargs.setdefault('mapped_sram_inventory', Path(activity).parent / 'mapped-inventory.json')
        return power.prepare(activity, *args, **kwargs)

    def prepare(self, directory):
        impl_path, impl, activity, report, netlist = self.fixture(directory)
        out = directory / 'power-probe'
        prepared = self.power_prepare(activity, impl_path, None, netlist, impl['constraints']['path'], out)
        return out, prepared, report

    def test_prepare_keeps_partial_unknowns_exact_inputs_and_manual_supported_saif_options(self):
        with tempfile.TemporaryDirectory() as temporary:
            out, prepared, report = self.prepare(Path(temporary))
            self.assertEqual(prepared['status'], 'PARTIAL_PREPARED_REVIEW_PENDING')
            self.assertEqual(prepared['qualification'], 'NOT_QUALIFIED')
            self.assertTrue(prepared['qualification_gaps'])
            self.assertFalse(prepared['taskset_complete'])
            script = (out / 'task_00/power.tcl').read_text()
            self.assertIn('read_saif ', script)
            self.assertIn('-strip_path {tb_xu_soc_ppa/dut}', script)
            self.assertIn('-report_inconsistent_annotation inconsistent.rpt', script)
            self.assertNotIn('read_vcd', script)
            self.assertNotIn('read_saif -rtl', script)
            self.assertIn('set XU_CLOCK_MODE envelope', script)
            self.assertIn('total must be exactly 336', script)
            self.assertIn('get_lib_cells -of_objects $xu_all_macros', script)
            self.assertNotIn('string map {. /}', script)
            self.assertIn('task-mapped.saif', script)
            self.assertEqual(prepared['tasks'][0]['mapped_macro_bridge_receipt']['relocated_pin_bits_added_as_port'], 21440)
            self.assertEqual(prepared['tasks'][0]['mapped_macro_bridge_receipt']['unchanged_pin_bits_verified'], 1072)
            for phase in ('before', 'after'):
                self.assertIn('source-default-%s.rpt' % phase, script)
                self.assertIn('sram-pins-%s.rpt' % phase, script)
            self.assertIn('XU_SRAM_LIBERTY_WHEN_INTERNAL_POWER_MODE_REVIEW_PENDING', script)
            states = power.read_json(out / 'task_00/measured-sram-pins.json')['pins']
            self.assertEqual(len(states), 22512)
            self.assertEqual(sum(1 for pin in states if pin['TX']), 32)
            self.assertGreater(sum(pin['TX'] for pin in states), 0)
            self.assertIn(report['tasks'][0]['sram_pin_alias_capture']['raw_saif']['path'], prepared['input_sha256'])
            with self.assertRaisesRegex(ValueError, 'must be new'):
                self.power_prepare(prepared['activity']['path'], None, None, prepared['netlist']['path'], prepared['analysis_sdc']['path'], out)

    def test_mismatched_netlist_sdc_source_taskset_and_unsimulated_status_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            impl_path, impl, activity, report, netlist = self.fixture(directory)
            other = directory / 'other'
            other.write_text('different identity\n')
            for field, mutate, net, sdc, ids in [
                ('netlist', lambda x: None, other, impl['constraints']['path'], [0]),
                ('sdc', lambda x: None, netlist, other, [0]),
                ('missing task', lambda x: None, netlist, impl['constraints']['path'], [1]),
                ('not simulated', lambda x: x.update(status='PARTIAL_PREPARED_NOT_SIMULATED'), netlist, impl['constraints']['path'], [0]),
                ('missing clear', lambda x: x.update(clear_task_before_window=False), netlist, impl['constraints']['path'], [0]),
                ('missing pin alias', lambda x: x.update(sram_pin_alias=False), netlist, impl['constraints']['path'], [0]),
            ]:
                changed = copy.deepcopy(report)
                mutate(changed)
                power.write(activity, changed)
                with self.subTest(field=field), self.assertRaises(ValueError):
                    self.power_prepare(activity, impl_path, None, net, sdc, directory / ('out-' + field.replace(' ', '-')), ids)
            changed = copy.deepcopy(report)
            key = next(key for key in changed['configuration']['rtl_sources_sha256'] if 'third-party' in key)
            changed['configuration']['rtl_sources_sha256'].pop(key)
            changed['configuration_sha256'] = collector.activity.canonical_hash(changed['configuration'])
            power.write(activity, changed)
            with self.assertRaisesRegex(ValueError, 'source differs'):
                self.power_prepare(activity, impl_path, None, netlist, impl['constraints']['path'], directory / 'out-source')

    def test_raw_log_request_window_and_macro_inventory_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            impl_path, impl, activity, report, netlist = self.fixture(directory)
            for label, mutate in [('window', lambda x: x['tasks'][0]['activity_window'].update(duration_ticks=1)),
                                  ('macro', lambda x: x['tasks'][0]['saif']['macro_inventory']['shared'].update(observed_count=255)),
                                  ('normalization', lambda x: x['tasks'][0]['sram_pin_alias_capture']['normalization'].update(alias_unknown_bit_ticks=0))]:
                changed = copy.deepcopy(report)
                mutate(changed)
                power.write(activity, changed)
                with self.subTest(label=label), self.assertRaises(ValueError):
                    self.power_prepare(activity, impl_path, None, netlist, impl['constraints']['path'], directory / ('out-' + label))
            changed = copy.deepcopy(report)
            log = Path(changed['tasks'][0]['boundary_log']['path'])
            log.write_text(log.read_text().replace('source_request=1 task_setup_writes=2', 'source_request=0 task_setup_writes=2'))
            changed['tasks'][0]['boundary_log'] = power.identity(log)
            power.write(activity, changed)
            with self.assertRaisesRegex(ValueError, 'clear evidence missing'):
                self.power_prepare(activity, impl_path, None, netlist, impl['constraints']['path'], directory / 'out-log')

    def test_ppa_prepared_bundle_is_checked_and_full_twelve_cannot_use_partial_collector(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            impl_path, impl, activity, report, netlist = self.fixture(directory)
            ppa_out = directory / 'ppa-prepared'
            ppa.prepare(ROOT, ppa_out, impl, allow_unqualified=True)
            out = directory / 'power-prepared'
            prepared = self.power_prepare(activity, None, ppa_out / 'prepared.json', netlist,
                                     ppa_out / 'constraints.sdc', out)
            self.assertEqual(prepared['ppa_prepared']['sha256'], power.sha(ppa_out / 'prepared.json'))
            self.assertIn(str(ppa_out / 'clock-review.tcl'), prepared['input_sha256'])
            with self.assertRaisesRegex(ValueError, 'absent from completed collector'):
                self.power_prepare(activity, impl_path, None, netlist, impl['constraints']['path'],
                              directory / 'all-twelve', list(range(12)))
            (ppa_out / 'sta.tcl').write_text('changed generated PPA control\n')
            with self.assertRaisesRegex(ValueError, 'generated control changed'):
                self.power_prepare(activity, None, ppa_out / 'prepared.json', netlist,
                              ppa_out / 'constraints.sdc', directory / 'bad-ppa')

    def test_library_roles_macro_count_and_runtime_input_mutation_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            impl_path, impl, activity, report, netlist = self.fixture(directory)
            for label, mutate in [('role', lambda x: x['libraries'][0].pop('role')),
                                  ('macro count', lambda x: x['memory_groups'][0].update(count=31))]:
                changed = copy.deepcopy(impl)
                mutate(changed)
                power.write(impl_path, changed)
                with self.subTest(label=label), self.assertRaises(ValueError):
                    self.power_prepare(activity, impl_path, None, netlist, impl['constraints']['path'], directory / ('out-' + label.replace(' ', '-')))
            power.write(impl_path, impl)
            out = directory / 'probe'
            prepared = self.power_prepare(activity, impl_path, None, netlist, impl['constraints']['path'], out)
            Path(impl['libraries'][0]['path']).write_text('changed after prepare\n')
            with self.assertRaisesRegex(ValueError, 'SHA256 differs'):
                power.run(out, sys.executable)
            self.assertFalse((out / 'execution.json').exists())

    def test_zero_exit_and_marker_without_reports_is_not_success_and_reuse_is_blocked(self):
        with tempfile.TemporaryDirectory() as temporary:
            out, prepared, _ = self.prepare(Path(temporary))
            task = prepared['tasks'][0]
            # A host command only exercises orchestration rejection. It is never
            # a simulated successful EDA result and cannot produce EXECUTED.
            with mock.patch.object(power, 'execute') as execute:
                def fake(command, directory, log, timeout, environment):
                    log.write_text(task['completion_marker'] + '\n')
                    return dict(command=command, returncode=0, log=power.identity(log))
                execute.side_effect = fake
                with self.assertRaisesRegex(ValueError, 'regular non-symlink file missing'):
                    power.run(out, sys.executable)
            receipt = power.read_json(out / 'execution.json')
            self.assertEqual(receipt['status'], 'FAIL')
            self.assertEqual(receipt['qualification'], 'NOT_QUALIFIED')
            self.assertEqual(receipt['tasks'][0]['execution']['returncode'], 0)
            self.assertEqual(receipt['input_sha256_before'], receipt['input_sha256_after'])
            with self.assertRaisesRegex(ValueError, 'execution output exists'):
                power.run(out, sys.executable)

    def test_missing_macro_or_pin_report_and_inconsistent_annotation_file_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            state = directory / 'states.json'
            power.write(state, dict(pins=[dict(mapped_path='macro/CLK')]))
            task = dict(macro_names=['macro'], measured_sram_pin_states=power.identity(state), expected_reports=power.report_names())
            for name in task['expected_reports']:
                (directory / name).write_text('host report fixture, not PT\n' if name != 'inconsistent.rpt' else '')
            (directory / 'sram-power.rpt').write_text('XU_SRAM_POWER_CELL name=macro ref=RAMSP1024X16\n')
            for phase in ('before', 'after'):
                (directory / ('sram-pins-%s.rpt' % phase)).write_text('XU_SRAM_PIN name=macro/CLK\n')
            self.assertEqual(len(power.checked_reports(directory, task)), len(task['expected_reports']))
            (directory / 'clocks.rpt').write_text('  Error: redirected reporting command failed\n')
            with self.assertRaisesRegex(ValueError, 'diagnostic failure in report: clocks.rpt'):
                power.checked_reports(directory, task)
            (directory / 'clocks.rpt').write_text('host report fixture, not PT\n')
            (directory / 'sram-power.rpt').write_text('missing macro\n')
            with self.assertRaisesRegex(ValueError, 'SRAM power cell'):
                power.checked_reports(directory, task)
            (directory / 'sram-power.rpt').write_text('XU_SRAM_POWER_CELL name=macro ref=RAMSP1024X16\n')
            (directory / 'sram-pins-after.rpt').write_text('missing pins\n')
            with self.assertRaisesRegex(ValueError, 'SRAM pin report'):
                power.checked_reports(directory, task)

    def test_tcl_catch_rejects_failure_before_unique_marker_and_escaping_is_strict(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'guard.tcl'
            path.write_text(ppa.guarded_tcl('error {injected host failure}', 'NEVER_SUCCESS'))
            result = subprocess.run(['tclsh', str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('NEVER_SUCCESS', result.stdout)
            self.assertIn('XU_FATAL:', result.stdout)
        for value in ('path\nsource evil', 'a}b', 'a\\b'):
            with self.assertRaises(ValueError):
                power.tcl(value)

    def test_real_host_process_records_return_code_and_kills_timeout_group(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            result = power.execute([sys.executable, '-c', 'import sys; print("host stderr", file=sys.stderr); sys.exit(3)'],
                                   directory, directory / 'nonzero.log', 5)
            self.assertEqual(result['returncode'], 3)
            self.assertIn('host stderr', (directory / 'nonzero.log').read_text())
            result = power.execute([sys.executable, '-c', 'import time; time.sleep(30)'],
                                   directory, directory / 'timeout.log', 1)
            self.assertNotEqual(result['returncode'], 0)
            self.assertIn('PT timeout; process group killed', (directory / 'timeout.log').read_text())

    def test_library_compiler_environment_reaches_real_host_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaisesRegex(ValueError, 'Library Compiler root/bin'):
                power.execution_environment(directory / 'missing')
            (directory / 'bin').mkdir()
            environment = power.execution_environment(directory)
            self.assertEqual(environment['SYNOPSYS_LC_ROOT'], str(directory))
            self.assertTrue(environment['PATH'].startswith(str(directory / 'bin') + os.pathsep))
            log = directory / 'host-environment.log'
            result = power.execute([sys.executable, '-c', 'import os; print(os.environ["SYNOPSYS_LC_ROOT"]); print(os.environ["PATH"].split(os.pathsep)[0])'],
                                   directory, log, 5, environment)
            self.assertEqual(result['returncode'], 0)
            self.assertEqual(log.read_text().splitlines()[1:], [str(directory), str(directory / 'bin')])

    def test_mapped_inventory_identity_and_mapped_activity_mutation_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            impl_path, impl, activity, report, netlist = self.fixture(directory)
            inventory_path = directory / 'mapped-inventory.json'
            inventory = power.read_json(inventory_path)
            with self.assertRaisesRegex(ValueError, 'actual mapped SRAM pin inventory required'):
                power.prepare(activity, impl_path, None, netlist, impl['constraints']['path'], directory / 'missing')
            for label, mutate, error in [
                ('netlist', lambda x: x['netlist'].update(sha256='0' * 64), 'inventory netlist differs'),
                ('library', lambda x: x['libraries'][0].update(sha256='0' * 64), 'inventory libraries differ'),
                ('pin', lambda x: x['macros'][0]['pins'].pop(), '67 bit pins'),
            ]:
                changed = copy.deepcopy(inventory); mutate(changed); power.write(inventory_path, changed)
                with self.subTest(label=label), self.assertRaisesRegex(ValueError, error):
                    self.power_prepare(activity, impl_path, None, netlist, impl['constraints']['path'], directory / label)
            power.write(inventory_path, inventory)
            out = directory / 'prepared'
            prepared = self.power_prepare(activity, impl_path, None, netlist, impl['constraints']['path'], out)
            Path(prepared['tasks'][0]['saif']['path']).write_text('tampered mapped activity')
            with self.assertRaisesRegex(ValueError, 'SHA256 differs'):
                power.run(out, sys.executable)


if __name__ == '__main__':
    unittest.main()
