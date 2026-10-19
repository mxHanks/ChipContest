"""Portable reader tests with inert temporary files; no HDL/tool PASS claim.

Only the expensive exported-model prerequisite is mocked. Command records,
source inventories, hashes, staged image shapes and the SoC parser are real.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class PortableSoCBaselineTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('portable_soc_baseline_subject',
                                                     ROOT/'scripts/verify/sram_soc_baseline.py')
        self.s = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.s)
        self.temp = tempfile.TemporaryDirectory(prefix='kwt-portable-baseline-reader-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        process_guard = patch('subprocess.Popen', side_effect=AssertionError('reader must launch no process'))
        process_guard.start(); self.addCleanup(process_guard.stop)
        root_patch = patch.object(self.s, 'ROOT', self.root)
        root_patch.start(); self.addCleanup(root_patch.stop)
        self.E = self.s.E
        self.platform = self.root/'independently-selected-platform'
        self.manifest = self.root/'portable-platform.json'
        self.out = self.root/'new-machine-baseline'
        self.out.mkdir()
        self.report_path = self.out/'result.json'
        self.make_fixture()
        model_patch = patch.object(self.s.SOC.L, 'load_module', return_value=object())
        model_patch.start(); self.addCleanup(model_patch.stop)
        export_patch = patch.object(self.s.SOC.E, 'validate_export',
                                  return_value=(self.export_manifest, self.provenance, self.images))
        self.export_reader = export_patch.start(); self.addCleanup(export_patch.stop)

    def file(self, name, payload=b'INERT HOST READER FIXTURE\n'):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload.encode() if isinstance(payload, str) else payload)
        return path

    def write_report(self):
        self.E.write_json(self.report_path, self.r)

    def identity(self, paths):
        return self.E.source_identity(paths, self.s.CONFIG, self.out/'source_identity.json')

    def resign_identity(self):
        value = self.r['identity']
        value['source_id'] = hashlib.sha256(json.dumps(
            {key: item for key, item in value.items() if key != 'source_id'},
            sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        self.E.write_json(self.out/'source_identity.json', value)

    def save_command(self, index):
        command = self.r['commands'][index]
        command['log'] = self.E.record(command['log']['path'])
        state = Path(command['native_state']['path'])
        self.E.write_json(state, {key: value for key, value in command.items() if key != 'native_state'})
        command['native_state'] = self.E.record(state)

    def command(self, name, argv, timeout, text=''):
        log = self.file(self.out.relative_to(self.root)/(name+'.log'), text)
        process = {'pid': 123, 'process_start_ticks': '456', 'pid_namespace': 'pid:[789]',
                   'boot_id': '00000000-1111-2222-3333-444444444444'}
        command = {'schema': 'kwt-sram-command-v1', 'status': 'EXITED', 'argv': list(map(str, argv)),
                   'cwd': str(self.out), 'host': 'inert-reader-fixture', 'supervisor': process.copy(),
                   'started_utc': '2026-10-18T00:00:00.000+00:00', 'timeout_seconds': timeout,
                   'timed_out': False, 'interrupted': False, 'exit_code': 0, **process,
                   'finished_utc': '2026-10-18T00:00:00.001+00:00', 'elapsed_seconds': 0.001,
                   'log': self.E.record(log)}
        state = self.out/(name+'.command.json')
        self.E.write_json(state, command)
        return {**command, 'native_state': self.E.record(state)}

    def soc_text(self):
        rows = []
        for task in range(12):
            start = 10*task+1
            rows.append(f'PASS E203_SRAM_TASK task={task} outputs=25344 load_commits=22976 '
                        f'start={start} first_config={start+1} first_x={start+2} '
                        f'last_write_rsp={start+3} ack_rsp={start+4} end={start+5} '
                        'window_cycles=6 core_cycles=4 output_write_responses=50688 ack_responses=1')
        rows += ['PASS E203_SRAM_RECOVERY soft_aborts=1 hard_resets=1 pending_response_reset=1',
                 'PASS E203_SRAM_SUITE tasks=12 outputs=304128 development_window_cycles=72 platform=open_fork_development',
                 f'- {self.root/"sim/tb_e203_kwt_sram.sv"}:154: Verilog $finish']
        return '\n'.join(rows)+'\n'

    def make_fixture(self):
        s = self.s
        paths = [self.platform/'rtl/e203/subsys/e203_subsys_perips.v',
                 self.platform/'rtl/e203/soc/e203_soc_top.v']
        paths += [self.platform/'rtl/e203/core'/f'unit_{index:03d}.v' for index in range(134)]
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('// INERT PLATFORM SOURCE\n')
        paths[0].write_text('head\nkwt_icb_slave u_kwt_accel\ntail\n')
        paths[1].write_text('head\nkwt_shared512_model u_kwt_shared\ntail\n')
        self.platform_sources = sorted(paths)
        self.platform_json = {'schema': 'kwt-e203-development-platform-v1',
                              'source_metadata': {'historical_report': 'traceability-only'},
                              'files': [{**self.E.record(path), 'path': path.relative_to(self.platform).as_posix()}
                                        for path in self.platform_sources]}
        self.E.write_json(self.manifest, self.platform_json)
        for name in (*s.PRODUCERS, *s.COMMON, *s.SOC_SOURCES, *s.FW):
            self.file(name)
        backend_config = {'schema': 'kwt-sram-backends-v1', 'top': 'kwt_linear_engine_rowpair_sram',
                          'numeric_contract': 'fixed16_acc48_v1', 'logical_bank_count': 20,
                          'logical_payload_bits': 415744, 'configured_bits': 462848,
                          'interface': copy.deepcopy(s.SOURCES.INTERFACE), 'common_sources': list(s.COMMON),
                          'backends': {'BEHAVIORAL': {'SRAM_BACKEND': 0}}}
        self.E.write_json(self.root/'configs/sram-backends.json', backend_config)
        patched = []
        for source, needle, replacement in (
            (paths[0], 'kwt_icb_slave u_kwt_accel', 'kwt_icb_slave_sram #(.SRAM_BACKEND(0)) u_kwt_accel'),
            (paths[1], 'kwt_shared512_model u_kwt_shared', 'kwt_shared512_checked_model u_kwt_shared')):
            target = self.out/source.name
            target.write_text(source.read_text().replace(needle, replacement))
            patched.append(target)
        generated = dict(zip(paths[:2], patched))
        common = [self.root/name for name in s.COMMON]
        compile_sources = [*common, *[self.root/name for name in s.SOC_SOURCES],
                           *[generated.get(path, path) for path in self.platform_sources]]
        fw = [self.root/name for name in s.FW]
        identity_paths = list(dict.fromkeys([*[self.root/name for name in s.PRODUCERS],
                                             *compile_sources, *fw, *paths[:2]]))
        identity = self.identity(identity_paths)
        self.compiler = self.file('inert-toolchain/riscv-none-elf-gcc')
        self.objcopy = self.file('inert-toolchain/riscv-none-elf-objcopy')
        self.verilator = self.file('inert-tools/verilator')
        tools = {}
        for name, path in (('gcc', self.compiler), ('objcopy', self.objcopy), ('verilator', self.verilator)):
            original_name = str(path) if name != 'verilator' else 'verilator'
            safe = re.sub(r'[^A-Za-z0-9_.+-]', '_', original_name)
            log = self.out/('version-'+safe+'.log')
            log.write_text('INERT VERSION RECORD; NOT EXECUTED\n')
            tools[name] = {'status': 'PASS', 'executable': self.E.record(path),
                           'version': log.read_text().strip(), 'command': {
                               'argv': [str(path), '--version'], 'cwd': str(self.root),
                               'exit_code': 0, 'timed_out': False, 'timeout_seconds': 15,
                               'log': self.E.record(log)}}
        self.export_manifest = {'schema': 'kwt_ffn_export_v1',
                                'input': {'kind': 'synthetic_zero_silence_smoke'}}
        export_path = self.root/'independent-export/manifest.json'
        export_path.parent.mkdir()
        self.E.write_json(export_path, self.export_manifest)
        self.provenance = [self.E.record(export_path)]
        self.images, staged = [], []
        for layer in range(12):
            image = {}
            for role, (bits, count) in s.SOC.E.MEMORY_SPECS.items():
                payload = (('0'*(bits//4)+'\n')*count).encode('ascii')
                path = self.file(f'independent-export/layer_{layer:02d}/{role}.mem', payload)
                self.provenance.append(self.E.record(path))
                image[role] = payload
                target = self.file(self.out.relative_to(self.root)/f'vectors/layer_{layer:02d}/{role}.mem', payload)
                staged.append(self.E.record(target))
            self.images.append(image)
        self.file(self.out.relative_to(self.root)/'firmware.elf', b'\x7fELFINERT')
        payload = b'\x13\x00\x00\x00'
        self.file(self.out.relative_to(self.root)/'firmware.bin', payload)
        self.file(self.out.relative_to(self.root)/'firmware.hex',
                  ''.join(f'{byte:02x}\n' for byte in payload.ljust(65536, b'\0')))
        simulation = self.file(self.out.relative_to(self.root)/'obj/simulation')
        firmware = [self.E.record(self.out/name) for name in ('firmware.elf', 'firmware.bin', 'firmware.hex')]
        core = self.platform/'rtl/e203/core'
        perips = self.platform/'rtl/e203/perips'
        argv = [self.compiler, '-march=rv32imac_zicsr_zifencei', '-mabi=ilp32', '-msmall-data-limit=0',
                '-Os', '-ffreestanding', '-fno-builtin', '-nostdlib', '-Wl,--build-id=none', '-DKWT_TASKS=12',
                '-I'+str(self.root/'soc/include'), '-T', fw[2], fw[0], fw[1], '-o', self.out/'firmware.elf']
        commands = [self.command('firmware', argv, 60),
                    self.command('objcopy', [self.objcopy, '-O', 'binary', self.out/'firmware.elf', self.out/'firmware.bin'], 60)]
        argv = ['verilator', '--binary', '--timing', '--assert', '-Wno-fatal', '-Wno-PINMISSING',
                '-Wno-PINCONNECTEMPTY', '--top-module', 'tb_e203_kwt_sram', '--Mdir', self.out/'obj',
                '-o', 'simulation', '-j', '2', '--threads', '1', '-DDISABLE_SV_ASSERTION=1',
                '-I'+str(core), '-I'+str(perips), '-I'+str(perips/'apb_i2c'), *compile_sources]
        commands += [self.command('compile', argv, 240, 'INERT BUILD LOG; NO EXECUTION CLAIM\n'),
                     self.command('run', [simulation, f'+VECTORS={self.out/"vectors"}',
                                          f'+FIRMWARE={self.out/"firmware.hex"}', '+TASKS=12'], 1800,
                                  self.soc_text())]
        measured = s.S.accept_soc(commands[-1], self.soc_text(), 12)
        self.r = {'schema': 'kwt-sram-soc-v2', 'status': 'PASS', 'phase': 'complete', 'scope': s.SCOPE,
                  'configuration': copy.deepcopy(s.CONFIG), 'measurement_scope': s.MEASUREMENT_SCOPE,
                  'official_platform': 'BLOCKED', 'timing': 'BLOCKED', 'area': 'BLOCKED', 'power': 'BLOCKED',
                  'identity': identity, 'inputs': [*identity['inputs'], *staged,
                      self.E.record(self.compiler), self.E.record(self.objcopy), *firmware, self.E.record(simulation)],
                  'commands': commands, 'tools': tools, 'firmware': firmware,
                  'simulation': self.E.record(simulation), 'vector_provenance': self.provenance,
                  'vector_scope': self.export_manifest['input']['kind'],
                  'workload_sha256': hashlib.sha256(b''.join(image[role] for image in self.images
                                                    for role in s.SOC.E.MEMORY_SPECS)).hexdigest(), **measured}
        self.write_report()

    def verify(self):
        return self.s.verify_baseline(self.report_path, self.platform, platform_manifest=self.manifest)

    def test_complete_inert_fixture_uses_explicit_platform_and_real_soc_parser(self):
        result = self.verify()
        self.assertEqual(result['sources'], self.platform_sources)
        self.assertEqual(result['native_commands'], 4)
        self.assertEqual(result['measurement']['outputs'], 304128)
        self.assertEqual(result['measurement']['development_window_cycles'], 72)
        self.assertEqual(result['firmware'], self.r['firmware'])
        self.assertEqual(result['dependency_paths'], [Path(item['path']) for item in result['dependencies']])
        self.assertIn(self.E.record(self.manifest), result['dependencies'])
        self.assertTrue(all(path.is_relative_to(self.root) for path in result['dependency_paths']))
        self.export_reader.assert_called_once()
        self.assertEqual(self.export_reader.call_args.kwargs['source_root'], self.root/'vendor/kwt1-237e4097')

    def test_inventory_source_metadata_is_only_traceability(self):
        self.platform_json['source_metadata']['historical_report'] = '/unavailable/history.json'
        self.E.write_json(self.manifest, self.platform_json)
        self.verify()

    def test_unsafe_inventory_paths_are_rejected(self):
        for name in ('/outside.v', '../escape.v', 'rtl/e203/../bad.v', 'rtl/./e203/bad.v',
                     'rtl//e203/bad.v', 'rtl\\e203\\bad.v', 'other/bad.v', 'rtl/e203/bad.sv', ''):
            with self.subTest(name=name):
                value = copy.deepcopy(self.platform_json); value['files'][0]['path'] = name
                self.E.write_json(self.manifest, value)
                with self.assertRaises(ValueError):
                    self.verify()

    def test_missing_or_duplicate_inventory_member_rejected(self):
        for values in (self.platform_json['files'][:-1],
                       self.platform_json['files']+[self.platform_json['files'][0]],
                       [self.platform_json['files'][0], *self.platform_json['files'][:-1]]):
            self.E.write_json(self.manifest, {**self.platform_json, 'files': values})
            with self.assertRaises(ValueError):
                self.verify()

    def test_added_platform_verilog_is_rejected_even_when_not_in_baseline(self):
        self.file(self.platform.relative_to(self.root)/'rtl/e203/core/extra.v')
        with self.assertRaisesRegex(ValueError, 'actual platform Verilog set'):
            self.verify()

    def test_same_count_platform_rename_is_rejected(self):
        source = self.platform_sources[0]
        source.rename(source.with_name('unreviewed.v'))
        with self.assertRaises((OSError, ValueError)):
            self.verify()

    def test_platform_sha_size_and_record_types_are_checked(self):
        for key, value in (('sha256', '0'*64), ('size_bytes', 0), ('size_bytes', False), ('sha256', 'bad')):
            with self.subTest(key=key, value=value):
                modified = copy.deepcopy(self.platform_json); modified['files'][0][key] = value
                self.E.write_json(self.manifest, modified)
                with self.assertRaises(ValueError):
                    self.verify()

    def test_platform_file_and_directory_symlinks_are_forbidden(self):
        path = self.platform_sources[0]
        payload = path.read_bytes(); path.unlink()
        target = self.file('linked-source.v', payload)
        path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'linked'):
            self.verify()
        path.unlink(); path.write_bytes(payload)
        directory = self.platform/'rtl/e203/linked-dir'; directory.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'linked'):
            self.verify()

    def test_platform_root_symlink_is_forbidden(self):
        linked = self.root/'platform-alias'; linked.symlink_to(self.platform, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'linked'):
            self.s.verify_baseline(self.report_path, linked, platform_manifest=self.manifest)

    def test_changed_report_configuration_and_completion_fail_closed(self):
        original = copy.deepcopy(self.r)
        for key, value in (('schema', 'kwt-sram-soc-v1'), ('status', 'RUNNING'), ('phase', 'simulation'),
                           ('configuration', {**self.s.CONFIG, 'tasks': 2}),
                           ('configuration', {**self.s.CONFIG, 'backend': 'ff'}),
                           ('configuration', {**self.s.CONFIG, 'jobs': 3}),
                           ('configuration', {**self.s.CONFIG, 'frequency_mhz': 150.0})):
            with self.subTest(key=key, value=value):
                self.r = copy.deepcopy(original); self.r[key] = value; self.write_report()
                with self.assertRaises(ValueError):
                    self.verify()

    def test_scope_and_official_acceptance_claims_are_rejected(self):
        for key in ('scope', 'measurement_scope', 'official_platform', 'timing', 'area', 'power'):
            value = self.r[key]; self.r[key] = 'PASS'; self.write_report()
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify()
            self.r[key] = value

    def test_canonical_source_id_and_saved_identity_are_independent_checks(self):
        self.r['identity']['source_id'] = '0'*64; self.write_report()
        with self.assertRaisesRegex(ValueError, 'canonical'):
            self.verify()
        self.resign_identity(); self.write_report()
        saved = json.loads((self.out/'source_identity.json').read_text())
        saved['source_id'] = '0'*64; self.E.write_json(self.out/'source_identity.json', saved)
        with self.assertRaisesRegex(ValueError, 'saved baseline source'):
            self.verify()

    def test_rehashed_identity_cannot_omit_mandatory_producer(self):
        self.r['identity']['inputs'] = [item for item in self.r['identity']['inputs']
                                       if not item['path'].endswith('/scripts/verify/run_sram_soc.py')]
        self.resign_identity(); self.write_report()
        with self.assertRaisesRegex(ValueError, 'mandatory baseline source'):
            self.verify()

    def test_identity_configuration_requires_exact_json_number_types(self):
        self.r['identity']['configuration'] = {**self.s.CONFIG, 'frequency_mhz': 150.0}
        self.resign_identity(); self.write_report()
        with self.assertRaisesRegex(ValueError, 'baseline source configuration'):
            self.verify()

    def test_changed_current_model_is_rejected(self):
        (self.root/'model/fixed16_acc48.py').write_text('CHANGED')
        with self.assertRaisesRegex(ValueError, 'file identity differs'):
            self.verify()

    def test_inputs_must_cover_identity_tools_firmware_and_all_48_vectors(self):
        original = copy.deepcopy(self.r['inputs'])
        for ending in ('run_sram_soc.py', 'riscv-none-elf-gcc', 'firmware.elf', 'layer_11/y.mem'):
            self.r['inputs'] = [item for item in original if not item['path'].endswith(ending)]
            self.write_report()
            with self.subTest(ending=ending), self.assertRaises(ValueError):
                self.verify()

    def test_duplicate_or_size_changed_input_record_is_rejected(self):
        original = copy.deepcopy(self.r['inputs'])
        self.r['inputs'].append(self.r['inputs'][0]); self.write_report()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.verify()
        self.r['inputs'] = original; self.r['inputs'][0]['size_bytes'] += 1; self.write_report()
        with self.assertRaisesRegex(ValueError, 'file identity differs'):
            self.verify()

    def test_private_patch_is_recomputed_and_unique(self):
        path = self.out/'e203_subsys_perips.v'
        path.write_text(path.read_text().replace('SRAM_BACKEND(0)', 'SRAM_BACKEND(3)'))
        with self.assertRaisesRegex(ValueError, 'private behavioral platform patch'):
            self.verify()

    def test_private_patch_comparison_preserves_exact_generated_bytes(self):
        path = self.out/'e203_soc_top.v'
        path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        with self.assertRaisesRegex(ValueError, 'private behavioral platform patch'):
            self.verify()

    def test_four_command_plan_is_exact(self):
        self.r['commands'].pop(); self.write_report()
        with self.assertRaisesRegex(ValueError, 'four native commands'):
            self.verify()

    def test_each_native_argv_cwd_and_timeout_is_checked(self):
        original = copy.deepcopy(self.r['commands'])
        for index in range(4):
            for key, value in (('argv', ['unrelated-command']), ('cwd', str(self.root)), ('timeout_seconds', 0)):
                self.r['commands'] = copy.deepcopy(original)
                self.r['commands'][index][key] = value
                self.save_command(index); self.write_report()
                with self.subTest(index=index, key=key), self.assertRaises(ValueError):
                    self.verify()
        self.r['commands'] = original

    def test_compile_source_order_and_members_cannot_be_substituted(self):
        command = self.r['commands'][2]
        command['argv'][-1] = str(self.platform_sources[0])
        self.save_command(2); self.write_report()
        with self.assertRaisesRegex(ValueError, 'native argv/cwd'):
            self.verify()

    def test_native_boolean_exit_timeout_interruption_and_missing_metadata_rejected(self):
        original = copy.deepcopy(self.r['commands'][0])
        for key, value in (('exit_code', False), ('timed_out', 0), ('interrupted', True),
                           ('status', 'RUNNING'), ('elapsed_seconds', -1), ('pid', 0), ('supervisor', {})):
            self.r['commands'][0] = {**copy.deepcopy(original), key: value}
            self.save_command(0); self.write_report()
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify()
        self.r['commands'][0] = copy.deepcopy(original); del self.r['commands'][0]['host']
        self.save_command(0); self.write_report()
        with self.assertRaisesRegex(ValueError, 'complete native state fields'):
            self.verify()

    def test_saved_state_compares_all_fields_not_only_exit_and_argv(self):
        self.r['commands'][0]['host'] = 'changed-only-in-report'; self.write_report()
        with self.assertRaisesRegex(ValueError, 'complete native saved state'):
            self.verify()

    def test_native_logs_and_saved_state_must_keep_their_recorded_bytes(self):
        (self.out/'firmware.log').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'file identity differs'):
            self.verify()

    def test_firmware_bin_to_padded_hex_relationship_is_recomputed(self):
        path = self.out/'firmware.hex'; path.write_text('00\n'*65536)
        record = self.E.record(path)
        self.r['firmware'][2] = record
        self.r['inputs'] = [record if item['path'] == str(path) else item for item in self.r['inputs']]
        self.write_report()
        with self.assertRaisesRegex(ValueError, 'BIN/padded HEX'):
            self.verify()

    def test_firmware_and_simulation_artifact_identities_are_checked(self):
        for path in (self.out/'firmware.elf', self.out/'obj/simulation'):
            payload = path.read_bytes(); path.write_bytes(payload+b'changed')
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'file identity differs'):
                self.verify()
            path.write_bytes(payload)

    def test_tool_paths_are_taken_from_actual_commands_and_tool_records(self):
        self.r['tools']['gcc']['executable'] = self.E.record(self.verilator); self.write_report()
        with self.assertRaises(ValueError):
            self.verify()

    def test_current_tool_bytes_and_version_text_are_rechecked(self):
        self.compiler.write_bytes(b'CHANGED TOOL')
        with self.assertRaisesRegex(ValueError, 'file identity differs'):
            self.verify()

    def test_vector_workload_and_fresh_export_coverage_are_recomputed(self):
        self.r['workload_sha256'] = '0'*64; self.write_report()
        with self.assertRaisesRegex(ValueError, 'workload SHA256'):
            self.verify()
        self.r['workload_sha256'] = hashlib.sha256(b''.join(image[role] for image in self.images
                                                for role in self.s.SOC.E.MEMORY_SPECS)).hexdigest()
        self.r['vector_provenance'] = self.r['vector_provenance'][:-1]; self.write_report()
        with self.assertRaisesRegex(ValueError, 'provenance coverage'):
            self.verify()

    def test_missing_original_export_manifest_is_rejected(self):
        self.r['vector_provenance'] = [item for item in self.r['vector_provenance']
                                       if not item['path'].endswith('/manifest.json')]
        self.write_report()
        with self.assertRaisesRegex(ValueError, 'one original export manifest'):
            self.verify()

    def test_provenance_size_is_verified_alongside_sha(self):
        self.r['vector_provenance'][0]['size_bytes'] += 1; self.write_report()
        with self.assertRaisesRegex(ValueError, 'file identity differs'):
            self.verify()

    def test_nonexport_provenance_json_may_be_a_list(self):
        path = self.file('independent-export/source-inventory.json', '[{"source": "inert"}]\n')
        self.provenance.append(self.E.record(path)); self.write_report()
        self.verify()

    def test_staged_vectors_must_equal_the_revalidated_export(self):
        path = self.out/'vectors/layer_00/x.mem'
        path.write_bytes(path.read_bytes().replace(b'0000', b'0001', 1))
        record = self.E.record(path)
        self.r['inputs'] = [record if item['path'] == str(path) else item for item in self.r['inputs']]
        self.write_report()
        with self.assertRaisesRegex(ValueError, 'staged vector bytes differ'):
            self.verify()

    def test_staged_vector_shape_and_known_hex_are_checked_without_trusting_mock(self):
        path = self.out/'vectors/layer_00/x.mem'
        for payload in (b'0000\n', b'xxxx\n'*6336):
            path.write_bytes(payload)
            self.images[0]['x'] = payload
            record = self.E.record(path)
            self.r['inputs'] = [record if item['path'] == str(path) else item for item in self.r['inputs']]
            self.write_report()
            with self.subTest(payload=payload[:8]), self.assertRaisesRegex(ValueError, 'shape/known hex'):
                self.verify()

    def test_extra_actual_vector_file_is_rejected(self):
        self.file(self.out.relative_to(self.root)/'vectors/unbound.mem')
        with self.assertRaisesRegex(ValueError, 'actual staged vector file set'):
            self.verify()

    def test_summary_is_recomputed_from_complete_soc_log(self):
        original = copy.deepcopy(self.r)
        for key, value in (('outputs', 0), ('development_window_cycles', 71), ('per_task', []),
                           ('recovery', {'soft_aborts': 1, 'hard_resets': 0, 'pending_response_reset': 1}),
                           ('recovery', {'soft_aborts': True, 'hard_resets': 1, 'pending_response_reset': 1})):
            self.r = copy.deepcopy(original); self.r[key] = value; self.write_report()
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'recomputed baseline measurement'):
                self.verify()

    def test_final_finish_family_counts_and_failure_diagnostics_are_strict(self):
        original = self.soc_text()
        for text in (original+'extra output after finish\n',
                     original.replace('Verilog $finish', 'premature stop'),
                     original+'PASS E203_SRAM_TASK malformed\n',
                     original.replace('PASS E203_SRAM_RECOVERY ', 'PASS E203_SRAM_UNBOUND arbitrary\nPASS E203_SRAM_RECOVERY '),
                     original.replace('output_write_responses=50688', 'output_write_responses=50687', 1),
                     original+'%Error: injected failure\n'):
            (self.out/'run.log').write_text(text); self.save_command(3); self.write_report()
            with self.subTest(text=text[-100:]), self.assertRaises(ValueError):
                self.verify()


if __name__ == '__main__':
    unittest.main()
