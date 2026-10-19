"""File planning and synthetic evidence-format qualification; no EDA.

Every binary, tool, model and native log below is deliberately inert fixture
bytes in a temporary directory. No artifacts archive or HDL tool is required.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT/'scripts/verify/sram_adapter_plan.py'


class SRAMAdapterPlanTests(unittest.TestCase):
    def setUp(self):
        name = 'sram_adapter_plan_test_subject'
        spec = importlib.util.spec_from_file_location(name, MODULE)
        self.subject = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {name: self.subject}):
            spec.loader.exec_module(self.subject)
        self.temp = tempfile.TemporaryDirectory(prefix='kwt-adapter-plan-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root/'package.json'
        self.fixture = self.root/'fixture.sv'
        self.fixture.write_text('// '+self.subject.C.SENTINEL+'\n')
        for target, attribute, value in ((self.subject, 'ROOT', self.root),
                                         (self.subject.C, 'FIXTURE', self.fixture)):
            patched = patch.object(target, attribute, value)
            patched.start()
            self.addCleanup(patched.stop)

    def ref(self, name, text):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def package(self, adapter='module kwt_official_sram_adapter; endmodule\n'):
        # These bytes qualify only file planning; no HDL is parsed or executed.
        value = {
            'schema': 'kwt-official-sram-package-v1',
            'logical_adapter_module': 'kwt_official_sram_adapter',
            'provenance': {'provider': 'private planning fixture', 'release': 'not-official',
                           'document': self.ref('origin.txt', 'classification fixture only\n')},
            'pin_specification': self.ref('logical.txt', 'no official pin claim\n'),
            'adapter_sources': [self.ref('adapter.sv', adapter)],
            'functional_sources': [self.ref('functional.v', 'module private_model; endmodule\n')],
            'synthesis_sources': [], 'liberty': {'setup': [], 'hold': [], 'power': []},
            'area_table': None,
        }
        self.manifest.write_text(json.dumps(value))
        return value

    def supplied_plan(self):
        with patch.object(self.subject, 'ROOT', self.root):
            return self.subject.plan_inputs(self.manifest)

    def development_plan(self):
        return self.subject.plan_inputs(self.manifest, development=True)

    def synthetic_report(self):
        """Produce complete small format fixtures, never an execution claim."""
        out = self.root/'report'
        out.mkdir()
        subject = self.subject
        base = [self.root/'src/rtl/memory/kwt_sram_1rw.sv', self.root/'src/rtl/memory/kwt_sram_bank.sv']
        tbs = [self.root/'sim/tb_kwt_sram_1rw.sv', self.root/'sim/tb_kwt_sram_bank.sv']
        compiler, runtime = self.root/'.tools/bin/iverilog', self.root/'.tools/bin/vvp'
        tools = [compiler, runtime, self.root/'.tools/eda/usr/bin/iverilog',
                 self.root/'.tools/eda/usr/bin/vvp', self.root/'.tools/eda/usr/lib/x86_64-linux-gnu/ivl/inert.fixture']
        for path in base+tbs+tools:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('INERT UNIT TEST FILE; NO HDL OR TOOL EXECUTION\n')
        producer = [Path(subject.C.__file__), Path(subject.INTAKE.__file__), Path(subject.E.__file__)]
        configuration = {'manifest': str(self.manifest), 'development_qualification': 'good',
                         'timeout_seconds': 30, 'backend': 3, 'positive_plan': subject.C.positive_cases(),
                         'negative_plan': subject.C.negative_cases(), 'scope': 'primitive/bank logical contract only'}
        initial = subject.E.source_identity(producer, configuration, out/'runner_identity.json')
        identity = subject.E.source_identity([*producer, *base, *tbs, *tools, self.fixture], configuration, out/'source_identity.json')
        commands, cases, binaries = [], [], []
        def command(name, argv, text='', exit_code=0):
            log = out/(name+'.log');log.write_text(text)
            state = {'schema': 'kwt-sram-command-v1', 'status': 'EXITED', 'exit_code': exit_code,
                     'timed_out': False, 'interrupted': False, 'argv': list(map(str, argv)),
                     'cwd': str(self.root), 'log': subject.E.record(log), 'timeout_seconds': 30,
                     'started_utc': '2026-10-18T00:00:00.000+00:00', 'finished_utc': '2026-10-18T00:00:00.001+00:00'}
            path = out/(name+'.command.json');subject.E.write_json(path, state)
            item = {**state, 'native_state': subject.E.record(path)}
            commands.append(item)
            return item
        versions = {'iverilog': 'INERT compiler version fixture\n', 'vvp': 'INERT runtime version fixture\n'}
        command('iverilog-version', [compiler, '-V'], versions['iverilog'])
        command('vvp-version', [runtime, '-V'], versions['vvp'])
        for case in subject.C.positive_cases():
            target = out/(case['name']+'.vvp');target.write_text('INERT BINARY FIXTURE\n')
            binaries.append(subject.E.record(target))
            tb = tbs[0] if case['top'] == 'tb_kwt_sram_1rw' else tbs[1]
            argv = [compiler, '-g2012', '-s', case['top'], '-o', target]
            argv += [f'-P{case["top"]}.{k}={v}' for k,v in (('WIDTH',case['width']),('DEPTH',case['depth']),('BACKEND',3))]
            command(case['name']+'-compile', [*argv, *base, self.fixture, tb])
            w,d=case['width'],case['depth']
            if case['top'] == 'tb_kwt_sram_1rw':
                text=f'PASS KWT_SRAM_UNIT width={w} depth={d} checks={d+16} signature=0123456789abcdef\n'
            else:
                text=(f'PASS KWT_SRAM_BANK_WIDTH_COVERAGE width={w} bits_both={w}\n'
                      f'PASS KWT_SRAM_BANK backend=3 width={w} depth={d} checks={2*d+5}\n')
            text+=f'{tb}:1: $finish called at 100 (1ps)\n'
            item=command(case['name'],[runtime,target],text)
            cases.append({**subject.C.accept_case(case,item,text),'command':item})
        for case in subject.C.negative_cases():
            text='FATAL: fixture.sv:1: '+case['diagnostics'][0]+'\n'
            item=command(case['name'],[runtime,out/(case['binary_name']+'.vvp'),f'+ERROR_CASE={case["error_case"]}'],text,1)
            cases.append({**subject.C.accept_case(case,item,text,negative=True),'command':item})
        report={'schema':'kwt-official-sram-contract-v1','status':'PASS','backend':3,
                'scope':subject.DEV_SCOPE,'development_qualification':'good','official_validation':'NOT_RUN',
                'official_ppa':'BLOCKED','primitive_bank_contract':'PASS','positive_cases':8,'expected_rejections':15,
                'started_utc':'2026-10-18T00:00:00.000+00:00','finished_utc':'2026-10-18T00:01:00.000+00:00',
                'initial_identity':initial,'identity':identity,'tool_versions':versions,
                'commands':commands,'cases':cases,'binaries':binaries,'generated_inputs':[]}
        report.update({key:'NOT_RUN' for key in ('core_validation','icb_validation','soc_validation','synthesis')})
        path=out/'result.json';subject.E.write_json(path,report)
        return path

    def test_default_missing_package_is_blocked_without_a_fallback(self):
        value = json.loads((ROOT/'configs/official-sram-package.json').read_text())
        self.manifest.write_text(json.dumps(value))
        result = self.subject.plan_inputs(self.manifest)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['sources'], [])
        self.assertEqual(result['scope'], 'supplied_source_primitive_bank_contract_only')
        self.assertEqual(result['intake']['stages']['simulation']['status'], 'BLOCKED')

    def test_development_is_explicit_fixture_only_and_binds_all_helpers(self):
        result = self.development_plan()
        self.assertEqual(result['status'], 'FILES_VERIFIED')
        self.assertEqual(result['sources'], [self.subject.C.FIXTURE.resolve()])
        self.assertIsNone(result['intake'])
        self.assertIsNone(result['manifest'])
        paths = {Path(r['path']) for r in result['dependencies']}
        for path in (MODULE, Path(self.subject.C.__file__), Path(self.subject.INTAKE.__file__),
                     Path(self.subject.E.__file__), self.subject.C.FIXTURE):
            self.assertIn(path.resolve(), paths)
        self.assertEqual(len(paths), len(result['dependencies']))
        self.assertTrue(all(isinstance(p, Path) for p in result['dependency_paths']))

    def test_supplied_simulation_does_not_require_higher_stage_files(self):
        self.package()
        result = self.supplied_plan()
        self.assertEqual(result['status'], 'FILES_VERIFIED')
        self.assertEqual(result['sources'], [self.root/'adapter.sv', self.root/'functional.v'])
        self.assertEqual(result['intake']['stages']['synthesis']['status'], 'BLOCKED')
        self.assertEqual(result['intake']['official_validation'], 'NOT_RUN')
        paths = {r['path'] for r in result['dependencies']}
        self.assertIn(str(self.manifest), paths)
        self.assertTrue({str(p) for p in result['sources']} <= paths)

    def test_supplied_rejects_fixture_path_and_copied_sentinel(self):
        self.package('// '+self.subject.C.SENTINEL+'\nmodule kwt_official_sram_adapter; endmodule\n')
        result = self.supplied_plan()
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['sources'], [])
        self.assertIn('fixture forbidden', result['error'])
        self.package()
        with patch.object(self.subject.C, 'FIXTURE', self.root/'adapter.sv'):
            result = self.supplied_plan()
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('fixture forbidden', result['error'])

    def test_supplied_refuses_unbound_external_consumption(self):
        for source in ('`include "unknown.svh"\n', '$readmemh("data.hex", storage);\n',
                       '$readmemb("data.bin", storage);\n', '$fopen("data");\n',
                       '$sdf_annotate("timing.sdf");\n', 'import "DPI-C" function int foreign();\n'):
            with self.subTest(source=source.strip()):
                self.package(source)
                result = self.supplied_plan()
                self.assertEqual(result['status'], 'FAIL')
                self.assertEqual(result['sources'], [])
                self.assertIn('auxiliary-input support', result['error'])

    def test_bad_sha_cannot_become_a_file_verified_plan(self):
        value = self.package()
        value['functional_sources'][0]['sha256'] = '0'*64
        self.manifest.write_text(json.dumps(value))
        result = self.supplied_plan()
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['sources'], [])

    def test_complete_synthetic_report_is_revalidated_without_executing_tools(self):
        accepted = self.synthetic_report()
        result = self.subject.verify_primitive_report(accepted, self.development_plan(), self.manifest, development=True)
        self.assertEqual(result['report'], self.subject.E.record(accepted))
        self.assertEqual((result['positive_cases'], result['expected_rejections'], result['native_commands']), (8, 15, 33))
        self.assertEqual(result['scope'], 'development_logical_adapter_only')
        paths = {Path(r['path']) for r in result['dependencies']}
        self.assertIn(MODULE.resolve(), paths)
        self.assertIn(accepted, paths)
        self.assertEqual(sum(p.suffix == '.vvp' for p in paths), 8)
        self.assertEqual(sum(p.name.endswith('.command.json') for p in paths), 33)

    def test_report_cannot_be_used_with_a_changed_or_different_plan(self):
        plan = self.development_plan()
        altered = copy.deepcopy(plan)
        altered['sources'] = []
        with self.assertRaisesRegex(ValueError, 'adapter plan differs'):
            self.subject.verify_primitive_report(self.root/'unused.json', altered, self.manifest, development=True)
        accepted = self.synthetic_report()
        self.package()
        with patch.object(self.subject, 'ROOT', self.root):
            supplied = self.subject.plan_inputs(self.manifest)
            with self.assertRaisesRegex(ValueError, 'scope differs'):
                self.subject.verify_primitive_report(accepted, supplied, self.manifest)

    def test_report_metadata_or_native_evidence_cannot_be_trusted_as_pass(self):
        accepted = self.synthetic_report()
        saved = json.loads(accepted.read_text())
        original_read = self.subject._read_json
        mutations = (
            ('status', lambda r: r.update(status='FAIL')),
            ('schema', lambda r: r.update(schema='unknown')),
            ('backend', lambda r: r.update(backend=0)),
            ('qualification', lambda r: r.update(development_qualification='bad-data')),
            ('count', lambda r: r.update(expected_rejections=14)),
            ('canonical source', lambda r: r['identity'].update(source_id='0'*64)),
            ('native hash', lambda r: r['commands'][0]['log'].update(sha256='0'*64)),
            ('compile parameter', lambda r: r['commands'][2]['argv'].__setitem__(6, '-Ptb_kwt_sram_1rw.BACKEND=0')),
            ('case', lambda r: r['cases'][0].update(checks=1)),
        )
        for name, mutate in mutations:
            with self.subTest(mutation=name):
                altered = copy.deepcopy(saved)
                mutate(altered)
                def read(path):
                    return copy.deepcopy(altered) if Path(path) == accepted else original_read(path)
                with patch.object(self.subject, '_read_json', side_effect=read):
                    with self.assertRaises((ValueError, OSError)):
                        self.subject.verify_primitive_report(accepted, self.development_plan(), self.manifest, development=True)

    def test_missing_report_is_rejected(self):
        with self.assertRaises(OSError):
            self.subject.verify_primitive_report(self.root/'absent.json', self.development_plan(), self.manifest, development=True)


if __name__ == '__main__':
    unittest.main()
