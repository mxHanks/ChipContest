"""Portable entry control tests using inert plans, never claiming CPU results."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class SRAMAdapterSoCV2Tests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('portable_cpu_subject',ROOT/'scripts/verify/run_sram_adapter_soc_v2.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.plan={'status':'FILES_VERIFIED','sources':[],'dependencies':[],'dependency_paths':[],
                   'scope':'inert-host-fixture','intake':None,'manifest':None,'development':True}

    def run_entry(self,argv,plan=None,baseline_error=None):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            def identity(paths,config,out):
                return {'schema':'inert-host-fixture','configuration':config,'inputs':[],'source_id':'fixture'}
            with patch.object(self.m,'ROOT',root),patch.object(self.m.E,'source_identity',side_effect=identity),\
                 patch.object(self.m.E,'record',side_effect=lambda p:{'path':str(p),'sha256':'0'*64,'size_bytes':0}),\
                 patch.object(self.m.PLAN,'plan_inputs',return_value=plan or self.plan),\
                 patch.object(self.m.PRIOR,'verify_system_report',return_value={'dependencies':[],'dependency_paths':[]}),\
                 patch.object(self.m.BASE,'verify_baseline',return_value={'dependencies':[],'sources':[]},side_effect=baseline_error) as baseline,\
                 patch.object(self.m.SYSTEM,'tool_inputs',return_value=[]),\
                 patch.object(self.m.E,'run_command',side_effect=AssertionError('host preflight must not launch tools')):
                code=self.m.main(argv)
                reports=list((root/'artifacts/runs').glob('*/result.json'));self.assertEqual(len(reports),1)
                return code,json.loads(reports[0].read_text()),baseline.call_args

    def test_missing_current_baseline_stops_before_tools(self):
        code,r,called=self.run_entry(['--development-adapter','--system-report','inert.json'])
        self.assertEqual((code,r['status']),(2,'BLOCKED'));self.assertFalse(r['commands']);self.assertIsNone(called)
        self.assertIsNone(r['configuration']['baseline_report'])

    def test_missing_system_proof_cannot_be_bypassed_with_baseline(self):
        code,r,called=self.run_entry(['--development-adapter','--baseline-report','fresh.json'])
        self.assertEqual((code,r['status']),(2,'BLOCKED'));self.assertFalse(r['commands']);self.assertIsNone(called)

    def test_current_package_gate_precedes_baseline_and_tools(self):
        code,r,called=self.run_entry([],plan=dict(self.plan,status='BLOCKED'))
        self.assertEqual((code,r['status']),(2,'BLOCKED'));self.assertIsNone(called);self.assertFalse(r['commands'])

    def test_explicit_report_and_platform_reach_validator_without_global_rebinding(self):
        old=(self.m.S.BASELINE,self.m.S.PLATFORM)
        code,r,called=self.run_entry(['--development-adapter','--system-report','system.json','--baseline-report','/new/run/result.json',
                                      '--platform','/new/platform','--compiler','/new/tool/gcc','--preflight-only'])
        self.assertEqual((code,r['status'],r['phase']),(0,'PASS','preflight-complete'))
        self.assertEqual(called.args,(Path('/new/run/result.json'),Path('/new/platform')))
        self.assertEqual(r['configuration']['compiler'],'/new/tool/gcc')
        self.assertEqual(r['acceptance'],'PREFLIGHT_ONLY');self.assertEqual(r['development_cpu_functional'],'NOT_RUN')
        self.assertFalse(r['commands']);self.assertFalse(r['binaries']);self.assertNotIn('outputs',r)
        self.assertEqual((self.m.S.BASELINE,self.m.S.PLATFORM),old)

    def test_invalid_or_missing_current_baseline_is_not_a_functional_pass(self):
        for error,status,code in ((ValueError('stale source'),'FAIL',1),(FileNotFoundError('missing'),'BLOCKED',2)):
            with self.subTest(error=error):
                actual,r,_=self.run_entry(['--development-adapter','--system-report','system.json','--baseline-report','fresh.json','--preflight-only'],baseline_error=error)
                self.assertEqual((actual,r['status']),(code,status));self.assertFalse(r['commands']);self.assertNotIn('outputs',r)


if __name__=='__main__':unittest.main()
