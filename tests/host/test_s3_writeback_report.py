"""Unit fixtures exercise saved-evidence analysis, never claim simulation evidence."""

import copy
import hashlib
import importlib.util
import json
import struct
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('s3_writeback_report', ROOT / 'tools/analysis/s3_writeback_report.py')
reporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reporter)


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value))


def unit_elf(entry=0x80000000, memsz=32, payload=b'unit-loaded-code', metadata=b'unit-nonloaded-metadata'):
    ident = b'\x7fELF\x01\x01\x01' + bytes(9)
    header = struct.pack('<16sHHIIIIIHHHHHH', ident, 2, 243, 1, entry,
                         52, 0, 1, 52, 32, 1, 0, 0, 0)
    program_header = struct.pack('<IIIIIIII', 1, 84, 0x80000000, 0x80000000,
                                 len(payload), memsz, 5, 4)
    return header + program_header + payload + metadata


def unit_campaign(root, cycles=1000000, rtl='baseline', layers=(0, 1), read_pop=False, direct=False):
    """Manufacture parser inputs in temporary storage, not reusable run artifacts."""
    root.mkdir()
    root = root.resolve()
    source = root / 'source/rtl/subsys/xu_nice_drain8.v'
    source.parent.mkdir(parents=True)
    source.write_text(rtl)
    sources = {'rtl/subsys/xu_nice_drain8.v': sha(rtl)}
    for relative, text in (('tests/e203/firmware/main.c', 'unit-main'),
                           ('tools/ppa/s3_task_clear_protocol.py', 'unit-clear-helper'),
                           ('tests/e203/firmware/accel.c', 'unit-accel-direct' if direct else 'unit-accel'),
                           ('tools/scripts/xu_firmware_contract.py', 'unit-contract-direct' if direct else 'unit-contract'),
                           ('rtl/perips/accel_icb_slave.v', 'unit-wrapper-direct' if direct else 'unit-wrapper')):
        path = root / 'source' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        sources[relative] = sha(text)
    generated_clear = '#include "' + str(root / 'source/tests/e203/firmware/main.c') + '"\nunit-generated-clear-main\n'
    (root / 's3_clear_main.c').write_text(generated_clear)
    (root / 'tb.sv').write_text('unit-generated-testbench')
    (root / 'rtl.f').write_text(''.join(str(root / 'source' / p) + '\n'
        for p in sorted(sources) if p.startswith('rtl/')) + str(root / 'tb.sv') + '\n')
    save_json(root / 'clear-recipe.json', dict(
        frozen_main_sha256=sha('unit-main'), helper_sha256=sha('unit-clear-helper'),
        generated_c_sha256=sha(generated_clear), generated_tb_sha256=sha('unit-generated-testbench'),
        clear_counts={'unit_fixture_only': True}, tasks_per_process=1, reset='fresh native process',
        policy='REVIEW_PENDING', fifo_payload_physical_zero='UNPROVEN'))
    assert not (direct and read_pop)
    schedule = reporter.DIRECT_SCHEDULE if direct else reporter.READ_POP_SCHEDULE if read_pop else reporter.SCHEDULE
    args = dict(out=str(root), repo='/unit-fixture-repository', schedule=schedule,
                simulator='verilator', bias_kind='sram', cross_prefix='/unit/bin/riscv-',
                layers=','.join(map(str, layers)), first_source_stall=0,
                max_cycles=3000000, waves=False, platform_clocks='development', platform_assertions=False)
    value = dict(status=reporter.PASS, source_drift=[],
                 configuration=dict(schedule=schedule, optimization='-O2', experiment='both-unroll-no-masks'),
                 bias_kind='sram', original_layers=list(layers),
                 clock_configuration=reporter.clock_configuration('development'),
                 platform_assertions='historical_DISABLED_SV_ASSERTION_define',
                 chisel_procedural_assertions='retained', original_source_sha256=sources,
                 versions={'unit-fixture-tool': 'unit-fixture-version'}, fixture={'unit_fixture': True},
                 integer_reference={'unit_fixture': True}, steps=[], task_results=[],
                 cache_policy='REVIEW_PENDING', fifo_payload_physical_zero='UNPROVEN')

    def step(name, command, output):
        log = root / (name + '.log')
        log.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(command) + '\n' + output
        log.write_text(text)
        value['steps'].append(dict(name=name, command=command, native_exit=0,
                                   waitpid_completed=True, log_sha256=sha(text)))

    loaded_payload = b'unit-direct-code' if direct else b'unit-loaded-code'
    elf_bytes = unit_elf(payload=loaded_payload)
    image = '@00000000\n' + ' '.join('%02X' % byte for byte in loaded_payload) + '\n'
    (root / 'accel_soc').write_bytes(elf_bytes)
    for name, payload in [('accel_soc.verilog', image), ('simv', 'unit-simv-' + rtl)]:
        (root / name).write_text(payload)
    value.update(firmware_elf_sha256=hashlib.sha256(elf_bytes).hexdigest(), firmware_image_sha256=sha(image),
                 simulator_sha256=sha('unit-simv-' + rtl))
    step('version-unit-fixture-tool', ['unit-fixture-tool', '--version'], 'unit-fixture-version')
    step('firmware-build', ['unit-fixture-gcc', '-DXU_NICE_DRAIN8=1', *(['-DXU_NICE_DIRECT=1'] if direct else []),
                           str(root / 'source/tests/e203/firmware/accel.c'), '-o', str(root / 'accel_soc')],
         'unit fixture firmware build\n')
    step('simulator-build', ['unit-fixture-compiler', '-o', str(root / 'simv')], 'unit fixture build\n')
    for layer in layers:
        vector_root = root / ('task-%02d/vectors' % layer)
        vector_root.mkdir(parents=True)
        vector_text = 'unit-vector-' + str(layer)
        (vector_root / 'profile.json').write_text(vector_text)
        vectors = {'profile.json': sha(vector_text)}
        (vector_root / 'layer_00').mkdir()
        for name in ('x', 'w', 'bias', 'y', 'y32', 'w_packed16'):
            relative = 'layer_00/' + name + '.mem'
            (vector_root / relative).write_text('unit-' + name + '-' + str(layer))
            vectors[relative] = sha('unit-' + name + '-' + str(layer))
        performance = dict.fromkeys(reporter.PERFORMANCE, 0)
        performance.update(w_load=100, x_load=200, bias_load=300, compute_wait=400,
                           writeback=cycles - 1100, other=100, mmio_reads=3170 if direct else 28513,
                           mmio_writes=12330 if direct else 12329 if read_pop else 15497,
                           shared_reads=15040, shared_writes=25344, starts=3168, dones=3168,
                           mac_fire=202752, busy=210000)
        nice = dict(layer=0, requests=3168, responses=3168, oitf_retired=3168, status_polls=3168,
                    result_reads=0 if direct else 25344, pops_retired=3168, shared_writes=25344)
        window = dict(layer=0, first_request=200001, first_accept=200001,
                      final_y_response=200000 + cycles, first_request_wait=0)
        clear = dict(mode_sram='1', writes='32930', commands='32935', responses='32935',
                     clear_cycles='200000', response_end_cycle='200000', gap_to_source_request='1',
                     nice_idle='1')
        auto = dict(layer=0, rows=99, pops_retired=3168, compute_writeback_overlap=123,
                    fifo_full_wait=456)
        task = dict(original_layer=layer, native_layer=0, cycles=cycles, performance=performance,
                    nice_activity=nice, window=window, clear=clear, measured_clocks=[],
                    vectors=vectors, vector_profile={'unit_fixture': True},
                    profile_source_sha256={'unit_fixture': sha('unit-exporter')})
        value['task_results'].append(task)
        output = 'S3_CLEAR_OBSERVER_ARM cycle=1 actual_accel_reset_n=1\n'
        for marker, fields in [('PERF_TASK', dict(layer=0, cycles=cycles, **performance)),
                               ('NICE_TASK', nice), ('AUTO_TASK', auto), ('WINDOW_TASK', window),
                               ('S3_TASK_CLEAR_OBSERVED', clear)]:
            output += marker + ' ' + ' '.join('%s=%s' % item for item in fields.items()) + '\n'
        output += 'TASK_PASS layer=0 outputs=25344 writes=25344 cycles=%d firmware_cycles=%d\n' % (cycles, cycles)
        output += 'SOC_PASS tasks=1 outputs=25344 writes=25344\n'
        if read_pop:
            output += 'READ_POP_TASK layer=0 alias_reads=3168 explicit_pops=0\n'
        if direct:
            output += 'DIRECT_TASK layer=0 snapshots=3168 lanes=25344 pops_retired=3168 result_mmio_reads=0\n'
        step('task-%02d/simulation' % layer,
             [str(root / 'simv'), '+TASKS=1', *(['+NICE_DIRECT=1'] if direct else ['+NICE_READ_POP=1'] if read_pop else [])], output)
    value.update(cycles=cycles * len(layers), outputs=25344 * len(layers))
    save_json(root / 'result.json', value)
    save_json(root / 'plan.json', dict(value, arguments=args, simulator='verilator'))
    return root / 'result.json'


class S3WritebackReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='s3-report-unit-fixtures-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.base = unit_campaign(root / 'base')
        self.candidate = unit_campaign(root / 'candidate', cycles=990000, rtl='candidate')

    def pair(self):
        return reporter.load_campaign(self.base), reporter.load_campaign(self.candidate)

    def test_per_layer_totals_and_gap_exclusion(self):
        base, candidate = self.pair()
        result = reporter.compare(base, candidate,
                                  {'rtl/subsys/xu_nice_drain8.v': (sha('baseline'), sha('candidate'))})
        self.assertEqual(result['totals']['baseline']['payload_plus_clear_cycles'], 2400000)
        self.assertEqual(result['totals']['candidate']['payload_plus_clear_cycles'], 2380000)
        self.assertEqual(result['totals']['delta']['payload_plus_clear_cycles'], -20000)
        self.assertEqual(result['totals']['candidate']['clear_to_source_gap'], 2)
        self.assertEqual([row['original_layer'] for row in result['layers']], [0, 1])
        self.assertEqual(result['totals']['delta']['phases']['writeback'], -20000)
        self.assertEqual(result['totals']['baseline']['auto']['fifo_full_wait'], 912)
        self.assertEqual(result['totals']['baseline']['nice']['shared_writes'], 50688)

    def test_exact_declaration_required_and_cannot_hide_other_changes(self):
        base, candidate = self.pair()
        with self.assertRaisesRegex(ValueError, 'source changes differ'):
            reporter.compare(base, candidate)
        with self.assertRaisesRegex(ValueError, 'source changes differ'):
            reporter.compare(base, candidate, {'rtl/subsys/xu_nice_drain8.v': (sha('baseline'), sha('wrong'))})
        candidate['source_sha256']['new-file.v'] = sha('new')
        with self.assertRaisesRegex(ValueError, 'source file set differs'):
            reporter.compare(base, candidate)

    def test_configuration_tools_clocks_layers_and_commands_must_match(self):
        base, original = self.pair()
        for key in ('versions', 'clock_configuration', 'configuration', 'original_layers',
                    'bias_kind', 'first_source_stall', 'cross_prefix', 'simulator', 'waves',
                    'fixture', 'integer_reference', 'platform_assertions', 'commands'):
            candidate = copy.deepcopy(original)
            candidate['conditions'][key] = 'unit-mismatch'
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'conditions differ'):
                reporter.compare(base, candidate)

    def test_vectors_profile_and_actual_clock_records_must_match(self):
        base, original = self.pair()
        for key in ('vectors', 'vector_profile', 'profile_source_sha256', 'measured_clocks'):
            candidate = copy.deepcopy(original)
            candidate['rows'][0][key] = 'unit-mismatch'
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'task input/clock differs'):
                reporter.compare(base, candidate,
                                 {'rtl/subsys/xu_nice_drain8.v': (sha('baseline'), sha('candidate'))})

    def test_raw_logs_and_snapshots_are_rehashed(self):
        for relative in ('task-00/simulation.log', 'source/rtl/subsys/xu_nice_drain8.v',
                         'task-00/vectors/profile.json', 'accel_soc', 'accel_soc.verilog', 'simv',
                         'tb.sv', 's3_clear_main.c'):
            path = self.base.parent / relative
            original = path.read_bytes()
            path.write_bytes(original + b'unit-tamper')
            with self.subTest(path=relative), self.assertRaisesRegex(ValueError, 'artifact SHA differs'):
                reporter.load_campaign(self.base)
            path.write_bytes(original)

    def test_partial_campaign_or_source_drift_rejected(self):
        original = json.loads(self.base.read_text())
        for key, value in [('status', 'RUNNING'), ('source_drift', ['rtl/changed.v']),
                           ('task_results', original['task_results'][:1])]:
            mutated = copy.deepcopy(original)
            mutated[key] = value
            save_json(self.base, mutated)
            with self.subTest(key=key), self.assertRaises(ValueError):
                reporter.load_campaign(self.base)
        save_json(self.base, original)

    def test_firmware_identity_cannot_change_for_rtl_only_experiment(self):
        base, candidate = self.pair()
        candidate['firmware_loaded_elf']['header']['e_entry'] += 4
        with self.assertRaisesRegex(ValueError, 'firmware image'):
            reporter.compare(base, candidate,
                             {'rtl/subsys/xu_nice_drain8.v': (sha('baseline'), sha('candidate'))})

    def test_duplicate_keys_and_path_escape_rejected(self):
        duplicate = self.base.parent / 'duplicate.json'
        duplicate.write_text('{"a": 1, "a": 2}')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            reporter.read_json(duplicate)
        with self.assertRaisesRegex(ValueError, 'unsafe artifact path'):
            reporter.artifact(self.base.parent, '../escape', sha('unused'))

    def test_changed_clear_work_is_not_comparable(self):
        base, candidate = self.pair()
        candidate['rows'][0]['clear']['commands'] = '32936'
        with self.assertRaisesRegex(ValueError, 'clear work differs'):
            reporter.compare(base, candidate,
                             {'rtl/subsys/xu_nice_drain8.v': (sha('baseline'), sha('candidate'))})

    def read_pop_pair(self):
        candidate_path = unit_campaign(Path(self.temp.name) / 'read-pop', cycles=980000,
                                       rtl='candidate', read_pop=True)
        return reporter.load_campaign(self.base), reporter.load_campaign(candidate_path), candidate_path

    def test_explicit_read_pop_exception_is_directed_and_keeps_source_declarations(self):
        base, candidate, _ = self.read_pop_pair()
        expected = {'rtl/subsys/xu_nice_drain8.v': (sha('baseline'), sha('candidate'))}
        with self.assertRaisesRegex(ValueError, 'conditions differ'):
            reporter.compare(base, candidate, expected)
        with self.assertRaisesRegex(ValueError, 'source changes differ'):
            reporter.compare(base, candidate, allow_read_pop_transport=True)
        result = reporter.compare(base, candidate, expected, allow_read_pop_transport=True)
        self.assertIsNotNone(result['transport_exception'])
        self.assertEqual(result['totals']['delta']['transport'], dict(alias_reads=6336, explicit_pops=-6336))
        self.assertEqual(result['totals']['delta']['bus_counters']['mmio_writes'], -6336)
        for before, after in ((candidate, base), (base, base), (candidate, candidate)):
            with self.subTest(direction=(before['result_path'], after['result_path'])):
                with self.assertRaisesRegex(ValueError, 'directed old-NICE'):
                    reporter.compare(before, after, expected, allow_read_pop_transport=True)

    def test_transport_exception_never_allows_macro_or_firmware_drift(self):
        base, original, _ = self.read_pop_pair()
        expected = {'rtl/subsys/xu_nice_drain8.v': (sha('baseline'), sha('candidate'))}
        for drift in ('compiler_macro', 'elf', 'image', 'optimization', 'clock', 'startup'):
            candidate = copy.deepcopy(original)
            if drift == 'compiler_macro':
                next(step for step in candidate['conditions']['commands']
                     if step['name'] == 'firmware-build')['command'].append('-DUNEXPECTED_PROFILE=1')
            elif drift in ('elf', 'image'):
                if drift == 'elf':
                    candidate['firmware_loaded_elf']['header']['e_entry'] += 4
                else:
                    candidate['firmware_image_sha256'] = sha(drift)
            elif drift == 'optimization':
                candidate['conditions']['configuration']['optimization'] = '-O3'
            elif drift == 'clock':
                candidate['conditions']['clock_configuration']['profile'] = '150mhz'
            else:
                candidate['conditions']['startup_profile'] = 'external-reset'
            with self.subTest(drift=drift), self.assertRaises(ValueError):
                reporter.compare(base, candidate, expected, allow_read_pop_transport=True)
        # A declared contract source change still cannot waive ELF equality for
        # the explicitly firmware-identical transport exception.
        base['source_sha256']['tools/scripts/xu_firmware_contract.py'] = sha('old contract')
        original['source_sha256']['tools/scripts/xu_firmware_contract.py'] = sha('new contract')
        expected['tools/scripts/xu_firmware_contract.py'] = (sha('old contract'), sha('new contract'))
        original['firmware_loaded_elf']['load_segments'][0]['memsz'] += 4
        with self.assertRaisesRegex(ValueError, 'firmware image'):
            reporter.compare(base, original, expected, allow_read_pop_transport=True)

    def test_transport_exception_requires_exactly_one_runtime_selector(self):
        base, original, _ = self.read_pop_pair()
        expected = {'rtl/subsys/xu_nice_drain8.v': (sha('baseline'), sha('candidate'))}
        for replacement in ([], ['+NICE_READ_POP=0'], ['+NICE_READ_POP=1', '+NICE_READ_POP=1']):
            candidate = copy.deepcopy(original)
            for step in candidate['conditions']['commands']:
                if step['name'].endswith('/simulation'):
                    step['command'].remove('+NICE_READ_POP=1')
                    step['command'].extend(replacement)
            with self.subTest(arguments=replacement), self.assertRaisesRegex(ValueError, 'exactly one'):
                reporter.compare(base, candidate, expected, allow_read_pop_transport=True)

    def test_read_pop_missing_or_wrong_transaction_record_is_rejected(self):
        _, _, path = self.read_pop_pair()
        report = json.loads(path.read_text())
        logpath = path.parent / 'task-00/simulation.log'
        original = logpath.read_text()
        for replacement in ('', 'READ_POP_TASK layer=0 alias_reads=3167 explicit_pops=0\n',
                            'READ_POP_TASK layer=0 alias_reads=3168\n',
                            'READ_POP_TASK layer=0 alias_reads=3168 explicit_pops=1\n'):
            logpath.write_text(original.replace('READ_POP_TASK layer=0 alias_reads=3168 explicit_pops=0\n', replacement))
            next(step for step in report['steps'] if step['name'] == 'task-00/simulation')['log_sha256'] = reporter.digest(logpath)
            save_json(path, report)
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                reporter.load_campaign(path)

    def direct_pair(self):
        root = Path(self.temp.name)
        before = unit_campaign(root / 'direct-base', read_pop=True)
        after = unit_campaign(root / 'direct-candidate', cycles=900000, rtl='candidate', direct=True)
        base, candidate = reporter.load_campaign(before), reporter.load_campaign(after)
        expected = {p: (value, candidate['source_sha256'][p])
                    for p, value in base['source_sha256'].items() if value != candidate['source_sha256'][p]}
        return base, candidate, expected, after

    def test_direct_exception_is_directed_explicit_and_reports_loaded_firmware_change(self):
        base, candidate, expected, _ = self.direct_pair()
        with self.assertRaisesRegex(ValueError, 'conditions differ'):
            reporter.compare(base, candidate, expected)
        with self.assertRaisesRegex(ValueError, 'source changes differ'):
            reporter.compare(base, candidate, allow_direct_transport=True)
        result = reporter.compare(base, candidate, expected, allow_direct_transport=True)
        self.assertIn('read-pop to direct', result['transport_exception'])
        self.assertEqual(result['totals']['delta']['transport'], dict(alias_reads=-6336, explicit_pops=0,
            direct_snapshots=6336, direct_lanes=50688, direct_pops=6336, result_mmio_reads=-50688))
        self.assertEqual(result['totals']['delta']['bus_counters']['mmio_writes'], 2)
        identity = result['firmware_identity']
        self.assertFalse(identity['loaded_image_sha256_equal'])
        self.assertFalse(identity['elf_load_contract_equal'])
        self.assertTrue(identity['loaded_firmware_change_allowed'])
        self.assertIn('DIRECT_CTRL', identity['loaded_firmware_change_reason'])
        self.assertTrue(all(value['verified'] for value in identity['independent_load_verification'].values()))
        # Comparing must leave its input evidence untouched.
        self.assertEqual(base['rows'][0]['transport'], dict(alias_reads=3168, explicit_pops=0))
        old = reporter.load_campaign(self.base)
        for before, after in ((candidate, base), (base, base), (candidate, candidate), (old, candidate)):
            with self.subTest(direction=(before['result_path'], after['result_path'])):
                with self.assertRaisesRegex(ValueError, 'directed read-pop to direct'):
                    reporter.compare(before, after, expected, allow_direct_transport=True)
        with self.assertRaisesRegex(ValueError, 'mutually exclusive'):
            reporter.compare(base, candidate, expected, allow_read_pop_transport=True, allow_direct_transport=True)

    def test_direct_exception_requires_paired_declared_sources_and_rejects_other_firmware(self):
        base, candidate, expected, _ = self.direct_pair()
        for path in reporter.DIRECT_REQUIRED_CHANGES:
            changed = copy.deepcopy(candidate)
            declared = copy.deepcopy(expected)
            changed['source_sha256'][path] = base['source_sha256'][path]
            del declared[path]
            with self.subTest(missing=path), self.assertRaisesRegex(ValueError, 'requires declared'):
                reporter.compare(base, changed, declared, allow_direct_transport=True)
        for path in ('tests/e203/firmware/main.c', 'tools/ppa/s3_task_clear_protocol.py'):
            changed, declared = copy.deepcopy(candidate), copy.deepcopy(expected)
            changed['source_sha256'][path] = sha('unit-unrelated-source-change')
            declared[path] = (base['source_sha256'][path], changed['source_sha256'][path])
            with self.subTest(unexpected=path), self.assertRaisesRegex(ValueError, 'unexpected source changes'):
                reporter.compare(base, changed, declared, allow_direct_transport=True)

    def test_direct_exception_rejects_rehashed_generated_clear_c_body_changes(self):
        base, candidate, expected, path = self.direct_pair()
        self.assertEqual(base['generated_clear_c_identity'], candidate['generated_clear_c_identity'])
        self.assertNotEqual(base['generated_c_sha256'], candidate['generated_c_sha256'])
        generated = path.parent / 's3_clear_main.c'
        recipe_path = path.parent / 'clear-recipe.json'
        original, recipe = generated.read_bytes(), json.loads(recipe_path.read_text())
        report, plan = json.loads(path.read_text()), json.loads((path.parent / 'plan.json').read_text())
        # Even a simultaneously rehashed and explicitly declared allowed C
        # source change cannot make an unrelated generated wrapper acceptable.
        source_path = 'tests/e203/firmware/accel.c'
        source = path.parent / 'source' / source_path
        source.write_text(source.read_text() + '\n/* declared direct source change */\n')
        source_hash = reporter.digest(source)
        report['original_source_sha256'][source_path] = source_hash
        plan['original_source_sha256'][source_path] = source_hash
        expected[source_path] = (base['source_sha256'][source_path], source_hash)
        save_json(path, report)
        save_json(path.parent / 'plan.json', plan)
        for content in (original + b'\n/* extra clear code */\n',
                        original.replace(b'unit-generated-clear-main', b'unit-changed-clear-main'),
                        original + str(path.parent).encode()):
            generated.write_bytes(content)
            recipe['generated_c_sha256'] = reporter.digest(generated)
            save_json(recipe_path, recipe)
            changed = reporter.load_campaign(path)
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, 'generated clear C differs'):
                reporter.compare(base, changed, expected, allow_direct_transport=True)

    def test_generated_clear_include_normalization_is_exact_and_keeps_other_paths(self):
        root = Path(self.temp.name)
        path = root / 'normalization.c'
        directive = '#include "' + str(root / 'source/tests/e203/firmware/main.c') + '"'
        for content in (directive + '\n' + directive, directive.replace('/source/', '/other/'),
                        '/* ' + directive + ' */', directive + ' /* suffix */'):
            path.write_text(content)
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, 'one exact'):
                reporter.generated_clear_c_identity(path, root)
        path.write_text(directive + '\nconst char *path="' + str(root) + '";\n')
        before = reporter.generated_clear_c_identity(path, root)
        other = root / 'other'
        other_directive = '#include "' + str(other / 'source/tests/e203/firmware/main.c') + '"'
        path.write_text(other_directive + '\nconst char *path="' + str(root) + '";\n')
        self.assertEqual(before, reporter.generated_clear_c_identity(path, other))
        path.write_text(other_directive + '\nconst char *path="' + str(other) + '";\n')
        self.assertNotEqual(before, reporter.generated_clear_c_identity(path, other))
    def test_direct_exception_only_normalizes_one_exact_macro_and_selector(self):
        base, original, expected, _ = self.direct_pair()
        mutations = ('missing_macro', 'duplicate_macro', 'false_macro', 'extra_macro',
                     'missing_selector', 'duplicate_selector', 'false_selector', 'old_selector',
                     'selector_in_build', 'macro_in_run', 'argument_order', 'optimization', 'clock', 'startup')
        for mutation in mutations:
            candidate = copy.deepcopy(original)
            build = next(step['command'] for step in candidate['conditions']['commands'] if step['name'] == 'firmware-build')
            run = next(step['command'] for step in candidate['conditions']['commands'] if step['name'].endswith('/simulation'))
            if mutation == 'missing_macro': build.remove('-DXU_NICE_DIRECT=1')
            elif mutation == 'duplicate_macro': build.append('-DXU_NICE_DIRECT=1')
            elif mutation == 'false_macro': build[build.index('-DXU_NICE_DIRECT=1')] = '-DXU_NICE_DIRECT=0'
            elif mutation == 'extra_macro': build.append('-DUNEXPECTED_PROFILE=1')
            elif mutation == 'missing_selector': run.remove('+NICE_DIRECT=1')
            elif mutation == 'duplicate_selector': run.append('+NICE_DIRECT=1')
            elif mutation == 'false_selector': run[run.index('+NICE_DIRECT=1')] = '+NICE_DIRECT=0'
            elif mutation == 'old_selector': run.append('+NICE_READ_POP=1')
            elif mutation == 'selector_in_build': build.append('+NICE_DIRECT=1')
            elif mutation == 'macro_in_run': run.append('-DXU_NICE_DIRECT=1')
            elif mutation == 'argument_order': run.reverse()
            elif mutation == 'optimization': candidate['conditions']['configuration']['optimization'] = '-O3'
            elif mutation == 'clock': candidate['conditions']['clock_configuration']['profile'] = '150mhz'
            else: candidate['conditions']['startup_profile'] = 'external-reset'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                reporter.compare(base, candidate, expected, allow_direct_transport=True)

    def test_direct_missing_duplicate_or_wrong_bundle_record_is_rejected(self):
        _, _, _, path = self.direct_pair()
        report = json.loads(path.read_text())
        logpath = path.parent / 'task-00/simulation.log'
        original = logpath.read_text()
        marker = 'DIRECT_TASK layer=0 snapshots=3168 lanes=25344 pops_retired=3168 result_mmio_reads=0\n'
        for replacement in ('', marker + marker, marker.replace('layer=0', 'layer=1'),
                            marker.replace('snapshots=3168', 'snapshots=3167'),
                            marker.replace('lanes=25344', 'lanes=25343'),
                            marker.replace('pops_retired=3168', 'pops_retired=3167'),
                            marker.replace('result_mmio_reads=0', 'result_mmio_reads=1'),
                            marker.replace(' result_mmio_reads=0', ''),
                            marker + 'READ_POP_TASK layer=0 alias_reads=3168 explicit_pops=0\n'):
            logpath.write_text(original.replace(marker, replacement))
            next(step for step in report['steps'] if step['name'] == 'task-00/simulation')['log_sha256'] = reporter.digest(logpath)
            save_json(path, report)
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                reporter.load_campaign(path)

    def test_direct_loading_rejects_missing_build_or_rehashed_wrong_profile_arguments(self):
        _, _, _, path = self.direct_pair()
        original_report = json.loads(path.read_text())
        buildpath = path.parent / 'firmware-build.log'
        runpath = path.parent / 'task-00/simulation.log'
        original_build, original_run = buildpath.read_text(), runpath.read_text()
        for mutation in ('no_build', 'no_macro', 'duplicate_macro', 'no_selector', 'old_selector'):
            report = copy.deepcopy(original_report)
            buildpath.write_text(original_build)
            runpath.write_text(original_run)
            if mutation == 'no_build':
                report['steps'] = [step for step in report['steps'] if step['name'] != 'firmware-build']
            else:
                is_build = mutation in ('no_macro', 'duplicate_macro')
                name = 'firmware-build' if is_build else 'task-00/simulation'
                step = next(step for step in report['steps'] if step['name'] == name)
                if mutation == 'no_macro': step['command'].remove('-DXU_NICE_DIRECT=1')
                elif mutation == 'duplicate_macro': step['command'].append('-DXU_NICE_DIRECT=1')
                elif mutation == 'no_selector': step['command'].remove('+NICE_DIRECT=1')
                else: step['command'].append('+NICE_READ_POP=1')
                logpath = buildpath if is_build else runpath
                output = logpath.read_text().split('\n', 1)[1]
                logpath.write_text(json.dumps(step['command']) + '\n' + output)
                step['log_sha256'] = reporter.digest(logpath)
            save_json(path, report)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                reporter.load_campaign(path)

    def test_direct_joint_saved_and_raw_counter_drift_is_rejected(self):
        _, _, _, path = self.direct_pair()
        original_report = json.loads(path.read_text())
        logpath = path.parent / 'task-00/simulation.log'
        original_log = logpath.read_text()
        mutations = [('NICE_TASK', 'nice_activity', key, 0) for key in
            ('requests', 'responses', 'oitf_retired', 'status_polls', 'pops_retired', 'shared_writes')]
        mutations += [('NICE_TASK', 'nice_activity', 'result_reads', 1)]
        mutations += [('PERF_TASK', 'performance', key, 0) for key in
            ('mac_fire', 'starts', 'dones', 'shared_reads', 'shared_writes', 'mmio_reads', 'mmio_writes')]
        mutations += [('PERF_TASK', 'performance', 'mmio_reads', 3171),
                      ('PERF_TASK', 'performance', 'mmio_writes', 12329)]
        for marker, category, key, value in mutations:
            report = copy.deepcopy(original_report)
            task = report['task_results'][0]
            old = task[category][key]
            task[category][key] = value
            line = next(line for line in original_log.splitlines(True) if line.startswith(marker + ' '))
            tokens = [('%s=%s' % (key, value)) if token == '%s=%s' % (key, old) else token for token in line.split()]
            logpath.write_text(original_log.replace(line, ' '.join(tokens) + '\n'))
            next(step for step in report['steps'] if step['name'] == 'task-00/simulation')['log_sha256'] = reporter.digest(logpath)
            save_json(path, report)
            with self.subTest(marker=marker, key=key, value=value), self.assertRaises(ValueError):
                reporter.load_campaign(path)

    def test_direct_image_and_elf_load_bytes_must_agree_independently(self):
        base, candidate, expected, path = self.direct_pair()
        original_report = json.loads(path.read_text())
        elfpath, imagepath = path.parent / 'accel_soc', path.parent / 'accel_soc.verilog'
        original_elf, original_image = elfpath.read_bytes(), imagepath.read_text()
        for image in ('not-a-verilog-image', original_image + '@00000000\n00\n',
                      '@00010000\n00\n', original_image.replace('75 ', '00 ', 1),
                      original_image + '00\n', '@00000000\n75\n'):
            report = copy.deepcopy(original_report)
            imagepath.write_text(image)
            report['firmware_image_sha256'] = reporter.digest(imagepath)
            save_json(path, report)
            with self.subTest(image=image), self.assertRaises(ValueError):
                reporter.load_campaign(path)
        imagepath.write_text(original_image)
        elfpath.write_bytes(unit_elf(payload=b'unit-wrong-code!'))
        report = copy.deepcopy(original_report)
        report['firmware_elf_sha256'] = reporter.digest(elfpath)
        save_json(path, report)
        with self.assertRaisesRegex(ValueError, 'image bytes differ from ELF'):
            reporter.load_campaign(path)
        elfpath.write_bytes(original_elf)
        save_json(path, original_report)
        # The read-pop side also needs its own ELF/image cross-check when the
        # direct exception permits its loaded bytes to differ from the candidate.
        baseline_image = Path(base['result_path']).parent / 'accel_soc.verilog'
        baseline_image.write_text('@00000000\n00\n')
        base['firmware_image_sha256'] = reporter.digest(baseline_image)
        with self.assertRaisesRegex(ValueError, 'missing from firmware image'):
            reporter.compare(base, candidate, expected, allow_direct_transport=True)

    def test_unknown_schedule_and_startup_profile_rejected_when_loading(self):
        original = json.loads(self.base.read_text())
        plan_path = self.base.parent / 'plan.json'
        original_plan = json.loads(plan_path.read_text())
        for kind in ('schedule', 'startup'):
            report, plan = copy.deepcopy(original), copy.deepcopy(original_plan)
            if kind == 'schedule':
                report['configuration']['schedule'] = plan['configuration']['schedule'] = 'unapproved-schedule'
                plan['arguments']['schedule'] = 'unapproved-schedule'
            else:
                plan['arguments']['startup_profile'] = 'unapproved-startup'
            save_json(self.base, report)
            save_json(plan_path, plan)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                reporter.load_campaign(self.base)
        save_json(self.base, original)
        save_json(plan_path, original_plan)

    def test_startup_seam_and_observations_must_match(self):
        base, original = self.pair()
        self.assertEqual(base['conditions']['startup_profile'], 'historical')
        self.assertEqual(base['conditions']['startup_configuration']['version'], 'historical-single-release')
        expected = {'rtl/subsys/xu_nice_drain8.v': (sha('baseline'), sha('candidate'))}
        for key in ('startup_profile', 'startup_configuration'):
            candidate = copy.deepcopy(original)
            candidate['conditions'][key] = 'external-reset'
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'conditions differ'):
                reporter.compare(base, candidate, expected)
        candidate = copy.deepcopy(original)
        candidate['rows'][0]['startup_observations'] = [{'unit_mismatched_seam': True}]
        with self.assertRaisesRegex(ValueError, 'startup reset semantics differ'):
            reporter.compare(base, candidate, expected)

    def test_external_reset_events_checked_but_absolute_times_can_differ(self):
        log = ('S3_STARTUP_PROFILE event=second_assert time_ns=1000.000000 cpu_reset_n=1\n'
               'S3_STARTUP_PROFILE event=second_release time_ns=1120.000000 held_ns=120.000000 cpu_reset_n=0\n'
               'S3_STARTUP_PROFILE event=measurement_begin time_ns=1120.000000 external_reset_n=1 cycle=0\n')
        before = reporter.startup_records(log, 'external-reset')
        after = reporter.startup_records(log.replace('1000.', '2000.').replace('1120.', '2120.'), 'external-reset')
        self.assertNotEqual(before, after)
        self.assertEqual(reporter.startup_signature(before), reporter.startup_signature(after))
        for invalid in (log.replace('held_ns=120.', 'held_ns=119.'),
                        log.replace('cycle=0', 'cycle=1'), log + log, log.splitlines()[0]):
            with self.subTest(log=invalid), self.assertRaises(ValueError):
                reporter.startup_records(invalid, 'external-reset')
        with self.assertRaisesRegex(ValueError, 'historical profile'):
            reporter.startup_records(log, 'historical')

    def test_generated_artifacts_recipe_and_rtl_filelist_checked(self):
        recipe_path = self.base.parent / 'clear-recipe.json'
        original = json.loads(recipe_path.read_text())
        for key in ('generated_c_sha256', 'generated_tb_sha256', 'helper_sha256', 'frozen_main_sha256'):
            recipe = copy.deepcopy(original)
            recipe[key] = sha('unit-wrong-recipe-value')
            save_json(recipe_path, recipe)
            with self.subTest(key=key), self.assertRaises(ValueError):
                reporter.load_campaign(self.base)
        save_json(recipe_path, original)
        filelist = self.base.parent / 'rtl.f'
        original_list = filelist.read_text()
        for text in ('', original_list + '/unit/unpinned-file.sv\n', original_list.splitlines()[0] + '\n'):
            filelist.write_text(text)
            with self.subTest(filelist=text), self.assertRaisesRegex(ValueError, 'RTL filelist differs'):
                reporter.load_campaign(self.base)
        filelist.write_text(original_list)

    def test_raw_measured_clocks_must_match_profile_and_saved_records(self):
        log = ('S3_CLOCK_PROFILE domain=hf requested_half_ns=3.333333333 '
               'measured_half_ns=3.333333000 period_ns=6.666666000 frequency_hz=150000015.000001490 precision_fs=1\n'
               'S3_CLOCK_PROFILE domain=lf requested_half_ns=15258.7890625 '
               'measured_half_ns=15258.789063000 period_ns=30517.578126000 frequency_hz=32767.999998926 precision_fs=1\n')
        self.assertEqual(len(reporter.clock_records(log, reporter.clock_configuration('150mhz'))), 2)
        for bad in (log.splitlines()[0], log + log, log.replace('6.666666000', '8.000000000'),
                    log.replace('150000015.000001490', '125000000.000000000')):
            with self.subTest(log=bad), self.assertRaises(ValueError):
                reporter.clock_records(bad, reporter.clock_configuration('150mhz'))
        report = json.loads(self.base.read_text())
        logpath = self.base.parent / 'task-00/simulation.log'
        logpath.write_text(logpath.read_text() + log)
        next(step for step in report['steps'] if step['name'] == 'task-00/simulation')['log_sha256'] = reporter.digest(logpath)
        save_json(self.base, report)
        # Even a rehashed log cannot add nominal-profile clocks to the old
        # development run while its saved clock observations remain empty.
        with self.assertRaisesRegex(ValueError, 'clock observations'):
            reporter.load_campaign(self.base)

    def test_saved_and_raw_work_counts_or_clear_timing_cannot_jointly_drift(self):
        original = json.loads(self.base.read_text())
        logpath = self.base.parent / 'task-00/simulation.log'
        original_log = logpath.read_text()
        for key in ('mac_fire', 'starts', 'dones', 'shared_reads', 'shared_writes', 'mmio_reads', 'gap_to_source_request'):
            report = copy.deepcopy(original)
            task = report['task_results'][0]
            category = task['clear'] if key == 'gap_to_source_request' else task['performance']
            old = category[key]
            new = '2' if key == 'gap_to_source_request' else 0
            category[key] = new
            logpath.write_text(original_log.replace('%s=%s' % (key, old), '%s=%s' % (key, new)))
            next(step for step in report['steps'] if step['name'] == 'task-00/simulation')['log_sha256'] = reporter.digest(logpath)
            save_json(self.base, report)
            with self.subTest(key=key), self.assertRaises(ValueError):
                reporter.load_campaign(self.base)

    def test_raw_version_log_must_match_summary_and_cwd_must_match_between_runs(self):
        base, candidate = self.pair()
        expected = {'rtl/subsys/xu_nice_drain8.v': (sha('baseline'), sha('candidate'))}
        candidate['conditions']['commands'][0]['cwd'] = '/unit-different-cwd'
        with self.assertRaisesRegex(ValueError, 'conditions differ'):
            reporter.compare(base, candidate, expected)
        report = json.loads(self.base.read_text())
        path = self.base.parent / 'version-unit-fixture-tool.log'
        path.write_text(path.read_text().replace('unit-fixture-version', 'unit-different-version'))
        next(step for step in report['steps'] if step['name'] == 'version-unit-fixture-tool')['log_sha256'] = reporter.digest(path)
        save_json(self.base, report)
        with self.assertRaisesRegex(ValueError, 'saved/raw tool versions differ'):
            reporter.load_campaign(self.base)

    def test_nonloaded_elf_metadata_can_differ_but_load_contract_cannot(self):
        expected = {'rtl/subsys/xu_nice_drain8.v': (sha('baseline'), sha('candidate'))}
        base = reporter.load_campaign(self.base)
        path = self.candidate.parent / 'accel_soc'
        saved = json.loads(self.candidate.read_text())
        path.write_bytes(unit_elf(metadata=b'unit-different-STT_FILE-name'))
        saved['firmware_elf_sha256'] = reporter.digest(path)
        save_json(self.candidate, saved)
        candidate = reporter.load_campaign(self.candidate)
        result = reporter.compare(base, candidate, expected)
        self.assertTrue(result['firmware_identity']['nonloaded_elf_metadata_may_differ'])
        self.assertTrue(result['firmware_identity']['loaded_image_sha256_equal'])
        self.assertTrue(result['firmware_identity']['elf_load_contract_equal'])
        for data in (unit_elf(entry=0x80000004), unit_elf(memsz=36),
                     unit_elf(payload=b'unit-changed-code')):
            path.write_bytes(data)
            saved['firmware_elf_sha256'] = reporter.digest(path)
            save_json(self.candidate, saved)
            candidate = reporter.load_campaign(self.candidate)
            with self.subTest(load_contract=candidate['firmware_loaded_elf']), self.assertRaisesRegex(ValueError, 'ELF load contract'):
                reporter.compare(base, candidate, expected)


if __name__ == '__main__':
    unittest.main()
