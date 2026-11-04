"""S2e PPA host refusal/generation checks; fake DB fixtures are never EDA evidence."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
IMPL=load('xu_s2e_host_impl',ROOT/'tools/ppa/xu_soc_implementation.py')
PPA=IMPL.ppa_module()
SERVER=load('xu_s2e_host_server',ROOT/'tools/ppa/xu_s2e_ppa_server.py')


class XuS2ePpaTests(unittest.TestCase):
    def test_new_profile_preserves_original_s2c_pin_and_geometry(self):
        self.assertEqual(PPA.SOURCE_PROFILES['s2c-autogroup']['commit'],'49a9436e01ea8ceeead94242e4a99c16e31a0865')
        self.assertEqual(PPA.SOURCE_PROFILES['s2e-paired-hi']['commit'],SERVER.CHILD)
        self.assertEqual(PPA.S2E_MAIN_COMMIT,SERVER.MAIN)
        inv=dict(platform_source_manifest_sha256='HOST_FIXTURE')
        a=PPA.template(inv,'s2c-autogroup');b=PPA.template(inv,'s2e-paired-hi')
        for key in ['memory_groups','defines','retained_instances','top','replacements']:
            self.assertEqual(a[key],b[key],key)
        self.assertEqual(sum(g['count'] for g in b['memory_groups']),336)
        self.assertEqual({g['macro_ref'] for g in b['memory_groups']},{'RAMSP1024X16'})
        for name,expected in SERVER.ASSETS.items(): self.assertEqual(PPA.sha(ROOT/name),expected)

    def test_incomplete_acceptance_and_existing_output_refuse_before_eda(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2e-refusal-') as temporary:
            root=Path(temporary);acceptance=root/'acceptance';acceptance.mkdir()
            (acceptance/'state.json').write_text(json.dumps(dict(status='RUNNING_NOT_QUALIFIED')))
            with self.assertRaisesRegex(ValueError,'complete frozen S2e VCS'):
                SERVER.checked_acceptance(root,acceptance)
            state=dict(status='EXECUTED_VCS_ACCEPTANCE_NOT_PPA_OR_ENERGY_QUALIFIED',expected_main=SERVER.MAIN,expected_e203=SERVER.CHILD,
                       frozen_before={'HOST':1},frozen_after={'HOST':2})
            (acceptance/'state.json').write_text(json.dumps(state))
            with self.assertRaisesRegex(ValueError,'runtime freeze differs'):
                SERVER.checked_acceptance(root,acceptance)
            out=root/'old-output';out.mkdir();sentinel=out/'raw.log';sentinel.write_bytes(b'keep old bytes\n')
            with mock.patch.object(sys,'argv',['xu_s2e_ppa_server.py','--out',str(out)]), \
                 mock.patch.object(SERVER.subprocess,'Popen') as start:
                with self.assertRaisesRegex(ValueError,'fresh independent PPA output'):
                    SERVER.main()
            start.assert_not_called();self.assertEqual(sentinel.read_bytes(),b'keep old bytes\n')

    @unittest.skipUnless(os.environ.get('XU_S2E_SOURCE_ROOT'),'explicit frozen local candidate source required')
    def test_actual_frozen_source_generates_full_mapping_and_own_svf_formal_inputs(self):
        source=Path(os.environ['XU_S2E_SOURCE_ROOT']).resolve()
        profile=PPA.source_profile_identity(source,'s2e-paired-hi')
        self.assertEqual(profile['main_source_freeze']['main_commit'],SERVER.MAIN)
        self.assertEqual(profile['changed_files'],['rtl/e203/perips/LinearAutoGroupCore.sv','rtl/e203/perips/accel_icb_slave.v'])
        with self.assertRaisesRegex(ValueError,'approved s2c-autogroup pin'):
            PPA.source_profile_identity(source,'s2c-autogroup')
        with tempfile.TemporaryDirectory(prefix='xu-s2e-real-freeze-fake-libs-') as temporary:
            root=Path(temporary);standard=root/'HOST-FAKE-STD.db';sram=root/'HOST-FAKE-RAM.db'
            standard.write_text('HOST FIXTURE ONLY NOT A LIBRARY\n');sram.write_text('HOST SRAM FIXTURE ONLY\n')
            receipt=IMPL.generate(source,root/'implementation',standard,PPA.sha(standard),sram,PPA.sha(sram),profile='s2e-paired-hi')
            self.assertEqual(receipt['macro_total'],336)
            impl=json.loads((root/'implementation/implementation.json').read_text())
            PPA.prepare(source,root/'ppa',impl,True)
            prepared=json.loads((root/'ppa/prepared.json').read_text())
            PPA.verify_prepared(source,root/'ppa',prepared)
            text=SERVER.formal_script(prepared,root/'ppa')
            self.assertIn('set_svf {'+str(root/'ppa/default.svf')+'}',text)
            self.assertIn('read_verilog -i {'+str(root/'ppa/mapped.v')+'}',text)
            self.assertEqual(text.count('read_db -technology_library'),2)
            self.assertIn('if {[verify]}',text)
            self.assertIn('XU_S2E_FULL_SOC_FORMALITY_PASS',text)
            self.assertEqual(PPA.sha(root/'ppa/constraints.sdc'),SERVER.SDC_SHA)
            synth=(root/'ppa/synth.tcl').read_text()
            self.assertIn('compile_ultra -no_autoungroup',synth)
            self.assertNotIn('set_false_path',text)
            altered=root/'ppa/rtl/perips/accel_icb_slave.v'
            altered.write_text(altered.read_text()+'\n// HOST INJECTED MUTATION\n')
            with self.assertRaisesRegex(ValueError,'prepared source changed'):
                PPA.verify_prepared(source,root/'ppa',prepared)


if __name__=='__main__':unittest.main()
