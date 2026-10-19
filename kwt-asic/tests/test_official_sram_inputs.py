"""File-only official-package readiness, with deliberately non-EDA fixtures.

Fixture bytes exercise source classification and provenance/path/SHA handling.
They are not SRAM models, pin specifications, or functional/technology evidence.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'scripts/verify/official_sram_inputs.py'
STAGES = ('simulation', 'synthesis', 'timing', 'ppa')


class OfficialSRAMInputInspectionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), 'official file-only input inspector is not implemented')
        spec = importlib.util.spec_from_file_location('official_sram_inputs_test_subject', MODULE)
        self.subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.subject)
        self.temporary = tempfile.TemporaryDirectory(prefix='kwt-official-input-files-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest_path = self.root / 'configs/official-sram-package.json'
        self.manifest_path.parent.mkdir()
        self.package = self.empty_package()

    @staticmethod
    def empty_package():
        return {
            'schema': 'kwt-official-sram-package-v1',
            'logical_adapter_module': 'kwt_official_sram_adapter',
            'provenance': {'provider': '', 'release': '', 'document': None},
            'pin_specification': None,
            'adapter_sources': [],
            'functional_sources': [],
            'synthesis_sources': [],
            'liberty': {'setup': [], 'hold': [], 'power': []},
            'area_table': None,
        }

    def file_ref(self, relative, data=b'File-classification fixture only; no hardware claim.\n'):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {'path': relative, 'sha256': hashlib.sha256(data).hexdigest()}

    def add_simulation_material(self):
        self.package['provenance'] = {
            'provider': 'unit-test file supplier', 'release': 'fixture-not-official',
            'document': self.file_ref('package/provenance.txt'),
        }
        self.package['pin_specification'] = self.file_ref('package/pins.txt')
        self.package['adapter_sources'] = [self.file_ref('src/adapter.sv')]
        self.package['functional_sources'] = [self.file_ref('package/functional.v')]

    def add_synthesis_material(self):
        self.package['synthesis_sources'] = [self.file_ref('package/definitions.v')]
        self.package['liberty']['setup'] = [self.file_ref('package/timing.lib')]

    def add_timing_material(self):
        # A single Liberty may legitimately serve several roles.
        self.package['liberty']['hold'] = copy.deepcopy(self.package['liberty']['setup'])

    def add_ppa_material(self, area_name='package/area.csv'):
        self.package['liberty']['power'] = copy.deepcopy(self.package['liberty']['setup'])
        self.package['area_table'] = self.file_ref(area_name)

    def complete_package(self):
        self.add_simulation_material()
        self.add_synthesis_material()
        self.add_timing_material()
        self.add_ppa_material()

    def inspect(self, package=None):
        payload = self.package if package is None else package
        self.manifest_path.write_text(json.dumps(payload), encoding='utf-8')
        result = self.subject.inspect_package(self.root, self.manifest_path)
        self.assertIsInstance(result, dict)
        self.assertIn(result.get('status'), ('PASS', 'BLOCKED', 'FAIL'))
        self.assertIsInstance(result.get('stages'), dict)
        self.assertEqual(set(result['stages']), set(STAGES))
        for name in STAGES:
            stage = result['stages'][name]
            self.assertIn(stage.get('status'), ('FILES_VERIFIED', 'BLOCKED', 'FAIL'))
            self.assertIsInstance(stage.get('source_files'), list)
            self.assertEqual(len(stage['source_files']), len(set(stage['source_files'])))
            for source in stage['source_files']:
                self.assertIsInstance(source, str)
                self.assertTrue(Path(source).is_absolute())
                self.assertTrue(Path(source).is_relative_to(self.root))
        return result

    def assert_stage_statuses(self, result, statuses):
        self.assertEqual({name: result['stages'][name]['status'] for name in STAGES}, statuses)

    def assert_fails(self, package=None):
        result = self.inspect(package)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any(result['stages'][name]['status'] == 'FAIL' for name in STAGES))
        return result

    def test_empty_package_is_blocked_without_fallback(self):
        result = self.inspect()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assert_stage_statuses(result, dict.fromkeys(STAGES, 'BLOCKED'))
        self.assertEqual(result['stages']['simulation']['source_files'], [])

    def test_simulation_does_not_wait_for_timing_power_or_area(self):
        self.add_simulation_material()
        result = self.inspect()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assert_stage_statuses(result, {
            'simulation': 'FILES_VERIFIED', 'synthesis': 'BLOCKED',
            'timing': 'BLOCKED', 'ppa': 'BLOCKED',
        })
        self.assertEqual(set(result['stages']['simulation']['source_files']), {
            str(self.root / 'src/adapter.sv'), str(self.root / 'package/functional.v'),
        })

    def test_synthesis_has_its_own_source_set_and_no_hold_requirement(self):
        self.add_simulation_material()
        self.add_synthesis_material()
        # Synthesis readiness must not depend on the simulation model existing.
        self.package['functional_sources'] = []
        result = self.inspect()
        self.assert_stage_statuses(result, {
            'simulation': 'BLOCKED', 'synthesis': 'FILES_VERIFIED',
            'timing': 'BLOCKED', 'ppa': 'BLOCKED',
        })
        self.assertEqual(set(result['stages']['synthesis']['source_files']), {
            str(self.root / 'src/adapter.sv'), str(self.root / 'package/definitions.v'),
        })

    def test_timing_does_not_wait_for_power_or_area(self):
        self.add_simulation_material()
        self.add_synthesis_material()
        self.add_timing_material()
        result = self.inspect()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assert_stage_statuses(result, {
            'simulation': 'FILES_VERIFIED', 'synthesis': 'FILES_VERIFIED',
            'timing': 'FILES_VERIFIED', 'ppa': 'BLOCKED',
        })

    def test_complete_material_verifies_files_only_and_deduplicates_shared_liberty(self):
        self.complete_package()
        result = self.inspect()
        self.assertEqual(result['status'], 'PASS')
        self.assert_stage_statuses(result, dict.fromkeys(STAGES, 'FILES_VERIFIED'))
        dependencies = result['dependencies']
        self.assertIsInstance(dependencies, list)
        paths = [item['path'] for item in dependencies]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(paths.count(str(self.root / 'package/timing.lib')), 1)
        required = {
            str(self.root / relative) for relative in (
                'package/provenance.txt', 'package/pins.txt', 'src/adapter.sv',
                'package/functional.v', 'package/definitions.v', 'package/timing.lib', 'package/area.csv',
            )
        }
        self.assertTrue(required <= set(paths))
        for item in dependencies:
            self.assertTrue(Path(item['path']).is_absolute())
            self.assertEqual(item['sha256'], hashlib.sha256(Path(item['path']).read_bytes()).hexdigest())

    def test_content_is_not_regex_compiled_or_misrepresented_as_functional_proof(self):
        # Deliberately not legal HDL/Liberty: this API verifies file inventory,
        # while real parsing/elaboration remains the relevant tool's job.
        self.complete_package()
        result = self.inspect()
        self.assertEqual(result['status'], 'PASS')
        self.assertNotIn('PASS', [stage['status'] for stage in result['stages'].values()])

    def test_wrong_schema_or_logical_adapter_module_is_rejected(self):
        self.complete_package()
        for key, value in [('schema', 'wrong-schema'), ('logical_adapter_module', 'other_adapter')]:
            with self.subTest(field=key):
                package = copy.deepcopy(self.package)
                package[key] = value
                self.assert_fails(package)

    def test_missing_provenance_or_pin_blocks_ready_file_lists(self):
        self.complete_package()
        for role in ('document', 'provider', 'release', 'pin_specification'):
            with self.subTest(role=role):
                package = copy.deepcopy(self.package)
                if role == 'pin_specification':
                    package[role] = None
                else:
                    package['provenance'][role] = None if role == 'document' else ''
                result = self.inspect(package)
                self.assertEqual(result['status'], 'BLOCKED')
                self.assert_stage_statuses(result, dict.fromkeys(STAGES, 'BLOCKED'))

    def test_changed_file_or_invalid_digest_is_rejected(self):
        self.complete_package()
        for digest in ('0' * 64, 'bad', 'A' * 64):
            with self.subTest(digest=digest):
                package = copy.deepcopy(self.package)
                package['functional_sources'][0]['sha256'] = digest
                self.assert_fails(package)

    def test_absolute_parent_escape_and_parent_segment_paths_are_rejected(self):
        self.complete_package()
        for path in (str(self.root / 'package/functional.v'), '../outside.v',
                     'package/../package/functional.v'):
            with self.subTest(path=path):
                package = copy.deepcopy(self.package)
                package['functional_sources'][0]['path'] = path
                self.assert_fails(package)

    def test_file_symlink_and_symlink_parent_are_rejected(self):
        self.complete_package()
        (self.root / 'package/alias.v').symlink_to(self.root / 'package/functional.v')
        (self.root / 'alias-directory').symlink_to(self.root / 'package', target_is_directory=True)
        for path in ('package/alias.v', 'alias-directory/functional.v'):
            with self.subTest(path=path):
                package = copy.deepcopy(self.package)
                package['functional_sources'][0]['path'] = path
                self.assert_fails(package)

    def test_directory_and_empty_documents_are_rejected(self):
        self.complete_package()
        package = copy.deepcopy(self.package)
        package['functional_sources'][0] = {'path': 'package', 'sha256': hashlib.sha256(b'').hexdigest()}
        self.assert_fails(package)
        for role in ('provenance', 'pin_specification'):
            with self.subTest(role=role):
                package = copy.deepcopy(self.package)
                empty = self.file_ref('package/empty-' + role + '.txt', b'')
                if role == 'provenance':
                    package['provenance']['document'] = empty
                else:
                    package['pin_specification'] = empty
                self.assert_fails(package)

    def test_role_file_types_are_checked_before_claiming_readiness(self):
        self.complete_package()
        for role, name in [('adapter_sources', 'package/adapter.txt'),
                           ('functional_sources', 'package/model.lib'),
                           ('synthesis_sources', 'package/definitions.json'),
                           ('setup', 'package/timing.sv'),
                           ('hold', 'package/timing.csv'),
                           ('power', 'package/power.v'),
                           ('area_table', 'package/area.lib')]:
            with self.subTest(role=role):
                package = copy.deepcopy(self.package)
                ref = self.file_ref(name)
                if role in ('setup', 'hold', 'power'):
                    package['liberty'][role] = [ref]
                elif role == 'area_table':
                    package[role] = ref
                else:
                    package[role] = [ref]
                self.assert_fails(package)

    def test_all_documented_area_table_types_are_accepted(self):
        self.complete_package()
        for suffix in ('.json', '.csv', '.tsv'):
            with self.subTest(suffix=suffix):
                package = copy.deepcopy(self.package)
                package['area_table'] = self.file_ref('package/area' + suffix)
                self.assertEqual(self.inspect(package)['status'], 'PASS')

    def test_duplicate_rtl_is_rejected_in_each_actual_compile_set(self):
        self.complete_package()
        for first, second in [('functional_sources', 'functional_sources'),
                              ('adapter_sources', 'functional_sources'),
                              ('adapter_sources', 'synthesis_sources')]:
            with self.subTest(first=first, second=second):
                package = copy.deepcopy(self.package)
                package[second].append(copy.deepcopy(package[first][0]))
                self.assert_fails(package)

    def test_same_conditional_verilog_file_may_serve_mutually_exclusive_uses(self):
        self.complete_package()
        self.package['synthesis_sources'] = copy.deepcopy(self.package['functional_sources'])
        result = self.inspect()
        self.assertEqual(result['status'], 'PASS')
        for stage in ('simulation', 'synthesis'):
            self.assertEqual(set(result['stages'][stage]['source_files']), {
                str(self.root / 'src/adapter.sv'), str(self.root / 'package/functional.v'),
            })
        paths = [item['path'] for item in result['dependencies']]
        self.assertEqual(paths.count(str(self.root / 'package/functional.v')), 1)

    def test_missing_digest_or_referenced_file_is_blocked(self):
        self.complete_package()
        for ref in ({'path': 'package/functional.v'},
                    {'path': 'package/functional.v', 'sha256': None},
                    {'path': 'package/missing.v', 'sha256': '0' * 64}):
            with self.subTest(ref=ref):
                package = copy.deepcopy(self.package)
                package['functional_sources'] = [ref]
                result = self.inspect(package)
                self.assertEqual(result['status'], 'BLOCKED')
                self.assertEqual(result['stages']['simulation']['status'], 'BLOCKED')
                self.assertEqual(result['stages']['synthesis']['status'], 'FILES_VERIFIED')

    def test_unknown_root_fields_fail_every_stage(self):
        self.complete_package()
        self.package['unsupported_readiness_override'] = 'READY'
        result = self.assert_fails()
        self.assert_stage_statuses(result, dict.fromkeys(STAGES, 'FAIL'))

    def test_source_roles_require_lists_and_refs_require_path_and_sha(self):
        self.complete_package()
        for role in ('adapter_sources', 'functional_sources', 'synthesis_sources'):
            with self.subTest(role=role):
                package = copy.deepcopy(self.package)
                package[role] = package[role][0]
                self.assert_fails(package)
        for malformed in ({'path': '', 'sha256': '0' * 64},
                          {'path': 123, 'sha256': '0' * 64}):
            with self.subTest(ref=malformed):
                package = copy.deepcopy(self.package)
                package['functional_sources'] = [malformed]
                self.assert_fails(package)

    def test_malformed_json_returns_fail_instead_of_throwing(self):
        self.manifest_path.write_text('{broken-json', encoding='utf-8')
        result = self.subject.inspect_package(self.root, self.manifest_path)
        self.assertIsInstance(result, dict)
        self.assertEqual(result['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
